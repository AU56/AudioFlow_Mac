# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from settings import DEFAULT_OUTPUT_DIR, SUPPORTED_AUDIO_EXTS, app_data_dir, resource_path
from schemes import SCHEME_BY_ID
from platform_presets import PLATFORM_PRESETS

LogFn = Callable[[str], None]


def safe_name(name: str, max_len: int = 80) -> str:
    stem = Path(name).stem
    stem = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff._-]+", "_", stem).strip("._ ")
    return (stem or "audio")[:max_len]


def collect_audio_files(paths: list[str]) -> list[Path]:
    result: list[Path] = []
    for raw in paths:
        p = Path(str(raw).strip().strip('"')).expanduser()
        if not p.exists():
            continue
        if p.is_dir():
            for child in p.rglob("*"):
                if child.suffix.lower() in SUPPORTED_AUDIO_EXTS:
                    result.append(child.resolve())
        elif p.suffix.lower() in SUPPORTED_AUDIO_EXTS:
            result.append(p.resolve())
    seen = set(); unique=[]
    for f in result:
        k=str(f).lower()
        if k not in seen:
            unique.append(f); seen.add(k)
    return unique


def format_duration(seconds: float) -> str:
    seconds = max(0, int(seconds or 0))
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def format_size(size: int) -> str:
    if size >= 1024 * 1024:
        return f"{size / 1024 / 1024:.1f} MB"
    return f"{size / 1024:.1f} KB"


@dataclass
class AudioInfo:
    duration: float = 0
    size: int = 0
    sample_rate: int = 0


@dataclass
class QualityReport:
    mean_db: float | None = None
    max_db: float | None = None
    duration_delta: float = 0
    score: int = 0
    note: str = ""


class AudioEngine:
    """AudioFlow processing engine."""


    def __init__(self, log: LogFn | None = None, ffmpeg_threads: int | None = None):
        self.log = log or (lambda _m: None)
        self.ffmpeg = self._find_tool("ffmpeg")
        self.ffprobe = self._find_tool("ffprobe")
        self.sox_dir = self._find_dir("tools/sox-14-4-2")
        self.sox = self._find_tool("sox", in_sox=True)
        self.ffmpeg_threads = self._resolve_ffmpeg_threads(ffmpeg_threads)

    def _resolve_ffmpeg_threads(self, value: int | None) -> int:
        raw = value if value is not None else os.getenv("AUDIOFLOW_FFMPEG_THREADS", "")
        try:
            return max(0, int(raw))
        except (TypeError, ValueError):
            return 0

    def _find_dir(self, relative: str) -> Path:
        p = resource_path(relative)
        if p.exists():
            return p.resolve()
        return Path(__file__).resolve().parent.joinpath(relative).resolve()

    def _tool_names(self, name: str) -> list[str]:
        base = Path(name).stem
        names = [base]
        if os.name == "nt":
            names.insert(0, base + ".exe")
        return list(dict.fromkeys(names))

    def _find_tool(self, filename: str, in_sox: bool = False) -> Path | None:
        candidates = []
        for name in self._tool_names(filename):
            if in_sox:
                candidates += [
                    resource_path(f"tools/sox-14-4-2/{name}"),
                    resource_path(f"tools/macos/{name}"),
                    Path(__file__).resolve().parent / "tools" / "sox-14-4-2" / name,
                    Path(__file__).resolve().parent / "tools" / "macos" / name,
                ]
            candidates += [
                resource_path(f"tools/{name}"),
                resource_path(f"tools/macos/{name}"),
                Path(__file__).resolve().parent / "tools" / name,
                Path(__file__).resolve().parent / "tools" / "macos" / name,
            ]
        for c in candidates:
            if c.exists():
                return c.resolve()
        for name in self._tool_names(filename):
            found = shutil.which(name)
            if found:
                return Path(found).resolve()
        return None

    def validate(self) -> tuple[bool, str]:
        missing = []
        if not self.ffmpeg or not self.ffmpeg.exists():
            missing.append("ffmpeg")
        if not self.sox or not self.sox.exists():
            missing.append("sox")
        if missing:
            hint = "Mac 版请先安装 ffmpeg/sox，或把对应平台工具放入 tools/macos。"
            return False, "缺少运行工具：" + ", ".join(missing) + "。" + hint
        return True, "OK"

    def _startup_kwargs(self) -> dict:
        kw: dict = {}
        if os.name == "nt":
            try:
                si = subprocess.STARTUPINFO()
                si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                si.wShowWindow = 0
                kw["startupinfo"] = si
                kw["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
            except Exception:
                pass
        return kw

    def _run(self, args: list, desc: str, cwd: Path | None = None, capture: bool = True) -> subprocess.CompletedProcess:
        env = os.environ.copy()
        cmd = [str(a) for a in args]
        if self.sox_dir and self.sox_dir.exists():
            env["PATH"] = str(self.sox_dir) + os.pathsep + env.get("PATH", "")
        if cmd and Path(cmd[0]).stem.lower() == "ffmpeg":
            if "-nostdin" not in cmd:
                cmd[1:1] = ["-nostdin"]
            if self.ffmpeg_threads and "-threads" not in cmd:
                cmd[1:1] = ["-threads", str(self.ffmpeg_threads)]
        self.log("执行：" + str(desc))
        cp = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            env=env,
            stdout=subprocess.DEVNULL if not capture else subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="ignore",
            shell=False,
            **self._startup_kwargs(),
        )
        if cp.returncode != 0:
            err = (cp.stderr or "").strip()[-1500:]
            raise RuntimeError(str(desc) + " 失败：" + str(err))
        return cp

    def probe(self, file: Path) -> AudioInfo:
        file = Path(file)
        size = file.stat().st_size if file.exists() else 0
        if not self.ffprobe or not self.ffprobe.exists():
            return AudioInfo(0, size)
        try:
            cp = subprocess.run(
                [str(self.ffprobe), "-v", "error", "-show_entries", "format=duration:stream=sample_rate", "-of", "json", str(file)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="ignore",
                timeout=8,
                shell=False,
                **self._startup_kwargs(),
            )
            data = json.loads(cp.stdout or "{}")
            duration = float(((data.get("format") or {}).get("duration") or 0))
            streams = data.get("streams") or []
            sample_rate = int((streams[0] or {}).get("sample_rate") or 0) if streams else 0
            return AudioInfo(duration, size, sample_rate)
        except Exception:
            return AudioInfo(0, size)

    def measure_levels(self, file: Path) -> tuple[float | None, float | None]:
        file = Path(file)
        if not self.ffmpeg or not self.ffmpeg.exists() or not file.exists():
            return None, None
        try:
            cp = subprocess.run(
                [str(self.ffmpeg), "-hide_banner", "-i", str(file), "-af", "volumedetect", "-f", "null", "NUL" if os.name == "nt" else "/dev/null"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="ignore",
                timeout=30,
                shell=False,
                **self._startup_kwargs(),
            )
            text = (cp.stdout or "") + "\n" + (cp.stderr or "")
            mean_match = re.search(r"mean_volume:\s*(-?\d+(?:\.\d+)?)\s*dB", text)
            max_match = re.search(r"max_volume:\s*(-?\d+(?:\.\d+)?)\s*dB", text)
            mean_db = float(mean_match.group(1)) if mean_match else None
            max_db = float(max_match.group(1)) if max_match else None
            return mean_db, max_db
        except Exception:
            return None, None

    def ensure_audible_output(self, file: Path) -> None:
        mean_db, max_db = self.measure_levels(file)
        if mean_db is None or max_db is None:
            return
        self.log(f"导出验音：平均响度 {mean_db:.1f} dB，峰值 {max_db:.1f} dB")
        if mean_db <= -42 or max_db <= -12:
            raise RuntimeError(f"导出结果异常偏小，已停止输出。检测到平均响度 {mean_db:.1f} dB，峰值 {max_db:.1f} dB。请优先尝试“纯音乐器乐 / 人声流行 / DJ电音”。")

    def quality_report(self, source: Path, output: Path) -> QualityReport:
        src_info = self.probe(source)
        out_info = self.probe(output)
        mean_db, max_db = self.measure_levels(output)
        score = 100
        notes: list[str] = []
        duration_delta = 0.0
        if src_info.duration > 1 and out_info.duration > 1:
            duration_delta = abs(float(out_info.duration) - float(src_info.duration))
            if duration_delta > 0.35:
                score -= 18
                notes.append(f"时长偏差 {duration_delta:.2f}s")
        if mean_db is not None:
            if mean_db < -24:
                score -= 16
                notes.append("整体偏小")
            elif mean_db > -8:
                score -= 10
                notes.append("整体偏满")
        if max_db is not None:
            if max_db >= -0.1:
                score -= 10
                notes.append("峰值过顶")
            elif max_db < -6:
                score -= 8
                notes.append("峰值偏低")
        if out_info.size <= 1024:
            score = 0
            notes.append("文件异常")
        score = max(0, min(100, int(score)))
        return QualityReport(mean_db, max_db, duration_delta, score, "，".join(notes) or "正常")

    def _stage_name(self, stage_dir: Path, step: int, scheme: dict, ext: str) -> Path:
        return stage_dir / f"stage_{step:02d}_scheme_{int(scheme['index']):02d}.{ext}"

    def _process_native_scheme(self, input_path: Path, stage_dir: Path, step: int, scheme_id: int, output_fmt: str = "WAV", apply_legacy: bool = True) -> Path:
        # Process one native scheme and return its temporary stage file.
        scheme = SCHEME_BY_ID[int(scheme_id)]
        force_mp3 = bool(scheme.get("force_mp3", False))
        ext = "mp3" if (force_mp3 or output_fmt.upper() == "MP3") else "wav"
        out_path = self._stage_name(stage_dir, step, scheme, ext)
        tmp_dir = Path(tempfile.mkdtemp(prefix=f"scheme_{scheme_id:02d}_", dir=str(stage_dir)))
        try:
            if scheme.get("engine") == "ffmpeg":
                extra = list(scheme.get("extra_args", []))
                if output_fmt.upper() == "MP3" or force_mp3:
                    extra = ["libmp3lame" if x in ("pcm_s24le", "pcm_s16le", "pcm_s32le") else x for x in extra]
                    if "-b:a" not in extra:
                        extra += ["-b:a", "320k"]
                    out_path = out_path.with_suffix(".mp3")
                cmd = [self.ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", input_path, "-af", scheme["af"]] + extra + [out_path]
                self._run(cmd, f"方案{int(scheme['index']):02d} {scheme['name']}", capture=False)

            elif scheme.get("engine") == "sox":
                tmp_in = tmp_dir / "in.wav"
                self._run([self.ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", input_path, "-acodec", "pcm_s24le", "-ar", "48000", tmp_in],
                          f"方案{int(scheme['index']):02d} 输入准备", capture=False)
                tmp_out = tmp_dir / "out.wav"
                self._run([self.sox, tmp_in, tmp_out] + list(scheme.get("sox_args") or []),
                          f"方案{int(scheme['index']):02d} {scheme['name']}", cwd=self.sox_dir, capture=False)
                if output_fmt.upper() == "MP3":
                    out_path = out_path.with_suffix(".mp3")
                    self._run([self.ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", tmp_out, "-acodec", "libmp3lame", "-b:a", "320k", out_path],
                              f"方案{int(scheme['index']):02d} MP3导出", capture=False)
                else:
                    shutil.copy2(tmp_out, out_path)
            else:
                raise RuntimeError(f"未知方案引擎：{scheme.get('engine')}")

            if apply_legacy:
                out_path = self._apply_legacy_step_enhance(out_path, scheme, tmp_dir)
            else:
                self.log(f"方案{int(scheme['index']):02d} 中间步保真桥接，跳过重复收尾层")
            if not out_path.exists() or out_path.stat().st_size <= 1024:
                raise RuntimeError(f"方案{int(scheme['index']):02d} 未生成有效文件")
            return out_path
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def _apply_legacy_step_enhance(self, out_path: Path, scheme: dict, tmp_dir: Path) -> Path:
        """Match the V3.0 per-scheme finishing layer before the next import."""
        scheme_num = str(scheme.get("num", ""))
        aphaser_af = (
            "aphaser=in_gain=0.97:out_gain=0.98:delay=2.0:decay=0.04:speed=0.12:type=t"
            if scheme_num in ("三", "四")
            else "aphaser=in_gain=0.95:out_gain=0.96:delay=2.0:decay=0.08:speed=0.12:type=t"
        )
        enhanced = Path(out_path)
        if enhanced.suffix.lower() == ".mp3":
            tmp_wav = tmp_dir / "pre_enh.wav"
            self._run([
                self.ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
                "-i", enhanced, "-acodec", "pcm_s16le", "-ar", "44100",
                "-ac", "2", tmp_wav,
            ], "legacy pre enhance convert", capture=False)
            enhanced = tmp_wav

        tmp_enh = tmp_dir / "enhanced.wav"
        try:
            self._run([
                self.ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
                "-i", enhanced, "-af", aphaser_af, "-ar", "44100", "-ac", "2",
                "-acodec", "pcm_s16le", tmp_enh,
            ], "legacy enhance aphaser", capture=False)
            enhanced = tmp_enh
        except Exception as exc:
            self.log(f"legacy enhance aphaser skipped: {exc}")

        tmp_itd = tmp_dir / "itd.wav"
        try:
            self._run([
                self.ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
                "-i", enhanced, "-af", "adelay=0.15|0:all=1", "-ar", "44100",
                "-ac", "2", "-acodec", "pcm_s16le", tmp_itd,
            ], "legacy enhance itd", capture=False)
            enhanced = tmp_itd
        except Exception as exc:
            self.log(f"legacy enhance itd skipped: {exc}")

        tmp_noise = tmp_dir / "noise.wav"
        noise_amp = 0.0005623413251903491
        try:
            self._run([
                self.ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
                "-i", enhanced, "-f", "lavfi", "-i",
                f"aevalsrc=random(0)*{noise_amp:.7f}|random(1)*{noise_amp:.7f}:s=44100:d=3600",
                "-filter_complex",
                "[1:a]highpass=f=800[noise];[0:a][noise]amix=inputs=2:duration=first:normalize=0[out]",
                "-map", "[out]", "-map_metadata", "-1", "-ar", "44100", "-ac", "2",
                "-acodec", "pcm_s16le", tmp_noise,
            ], "legacy enhance noise", capture=False)
            enhanced = tmp_noise
        except Exception as exc:
            self.log(f"legacy enhance noise skipped: {exc}")

        if enhanced != out_path:
            extra = list(scheme.get("extra_args") or [])
            ar = "44100"
            if "-ar" in extra:
                pos = extra.index("-ar")
                if pos + 1 < len(extra):
                    ar = str(extra[pos + 1])
            if out_path.suffix.lower() == ".mp3":
                self._run([
                    self.ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
                    "-i", enhanced, "-acodec", "libmp3lame", "-b:a", "320k", out_path,
                ], "legacy final mp3 restore", capture=False)
            else:
                self._run([
                    self.ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
                    "-i", enhanced, "-map_metadata", "-1", "-ar", ar, "-ac", "2",
                    "-acodec", "pcm_s16le", out_path,
                ], "legacy final wav restore", capture=False)
        return out_path

    def _mp3_bitrate_for_duration(self, duration: float) -> str:
        duration = max(1.0, float(duration or 0))
        target_bytes = 19 * 1024 * 1024
        max_kbps = int((target_bytes * 8) / duration / 1000)
        for kbps in (320, 256, 224, 192, 160, 128):
            if kbps <= max_kbps:
                return f"{kbps}k"
        return "128k"

    def _export_or_copy_final(self, src_stage: Path, out_file: Path, fmt: str, duration_target: float = 0) -> None:
        out_file.parent.mkdir(parents=True, exist_ok=True)
        fmt = fmt.lower()
        if fmt == "wav":
            cmd = [self.ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", src_stage, "-vn"]
            current_duration = float(self.probe(src_stage).duration or 0)
            duration_target = float(duration_target or 0)
            if current_duration > 1 and duration_target > 1 and abs(current_duration - duration_target) >= 0.25:
                factor = current_duration / duration_target
                self.log("duration lock: %.2fs -> %.2fs" % (current_duration, duration_target))
                cmd += ["-af", self._atempo_chain(factor)]
            cmd += ["-ar", "48000", "-ac", "2", "-c:a", "pcm_s16le", out_file]
            self._run(cmd, "final WAV export", capture=False)
            return
        if fmt == "mp3":
            duration = duration_target or float(self.probe(src_stage).duration or 0)
            bitrate = self._mp3_bitrate_for_duration(duration)
            self._run([
                self.ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
                "-i", src_stage, "-vn", "-map_metadata", "-1",
                "-codec:a", "libmp3lame", "-b:a", bitrate, out_file
            ], f"final MP3 export ({bitrate})", capture=False)
            return
        if src_stage.suffix.lower().lstrip(".") == fmt:
            shutil.copy2(src_stage, out_file)
            return
        if fmt == "flac":
            self._run([self.ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", src_stage, "-vn", "-compression_level", "5", out_file], "final FLAC export", capture=False)
        else:
            self._run([self.ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", src_stage, "-vn", "-c:a", "pcm_s16le", out_file], "final audio export", capture=False)

    def _atempo_chain(self, factor: float) -> str:
        parts: list[str] = []
        factor = max(0.25, min(4.0, float(factor or 1.0)))
        while factor < 0.5:
            parts.append("atempo=0.5")
            factor /= 0.5
        while factor > 2.0:
            parts.append("atempo=2.0")
            factor /= 2.0
        parts.append(f"atempo={factor:.6f}")
        return ",".join(parts)

    def _match_duration(self, src_stage: Path, target_duration: float, stage_dir: Path) -> Path:
        current_duration = float(self.probe(src_stage).duration or 0)
        target_duration = float(target_duration or 0)
        if current_duration <= 1 or target_duration <= 1:
            return src_stage
        if abs(current_duration - target_duration) < 0.25:
            return src_stage
        fixed = stage_dir / f"{src_stage.stem}_duration_lock.wav"
        factor = current_duration / target_duration
        self.log("duration lock: %.2fs -> %.2fs" % (current_duration, target_duration))
        self._run([
            self.ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
            "-i", src_stage, "-af", self._atempo_chain(factor),
            "-ar", "48000", "-ac", "2", "-c:a", "pcm_s24le", fixed
        ], "duration lock", capture=False)
        return fixed if fixed.exists() and fixed.stat().st_size > 1024 else src_stage

    def _scheme_stage_rate(self, scheme: dict) -> str:
        args = [str(x).lower() for x in (scheme.get("sox_args") or [])]
        if "rate" in args:
            idx = args.index("rate")
            if idx + 1 < len(args):
                raw = args[idx + 1].strip()
                if raw.endswith("k"):
                    try:
                        return str(int(float(raw[:-1]) * 1000))
                    except ValueError:
                        pass
                if raw.isdigit():
                    return raw
        return "44100"

    def _normalize_between_schemes(self, src_stage: Path, source_duration: float, stage_dir: Path, step: int, scheme: dict) -> Path:
        target = stage_dir / f"stage_{step:02d}_legacy_bridge.wav"
        current_duration = float(self.probe(src_stage).duration or 0)
        duration_target = float(source_duration or 0)
        wanted_rate = self._scheme_stage_rate(scheme)
        if current_duration > 1 and duration_target > 1 and abs(current_duration - duration_target) < 0.25:
            try:
                meta = subprocess.run(
                    [
                        self.ffprobe, "-v", "error", "-print_format", "json",
                        "-show_streams", src_stage
                    ],
                    capture_output=True, text=True, encoding="utf-8", errors="replace", check=False
                )
                data = json.loads(meta.stdout or "{}")
                stream = (data.get("streams") or [{}])[0]
                if (
                    str(stream.get("codec_name", "")).lower() == "pcm_s16le"
                    and str(stream.get("sample_rate", "")) == wanted_rate
                    and int(stream.get("channels") or 0) == 2
                ):
                    return src_stage
            except Exception:
                pass
        cmd = [self.ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", src_stage, "-vn"]
        if current_duration > 1 and duration_target > 1 and abs(current_duration - duration_target) >= 0.25:
            cmd += ["-af", self._atempo_chain(current_duration / duration_target)]
        cmd += ["-ar", wanted_rate, "-ac", "2", "-c:a", "pcm_s16le", target]
        self._run(cmd, f"方案{int(scheme['index']):02d} 中间导出整理", capture=False)
        return target if target.exists() and target.stat().st_size > 1024 else src_stage

    def _apply_detector_humanize(self, out_file: Path, fmt: str) -> None:
        if os.getenv("AUDIOFLOW_DETECT_PASS", "0").strip() == "0":
            return
        info = self.probe(out_file)
        duration = max(1.0, float(info.duration or 0))
        sample_rate = "48000" if int(info.sample_rate or 0) >= 48000 else "44100"
        tmp = out_file.with_name(out_file.stem + "_detectpass_tmp" + out_file.suffix)
        noise_len = duration + 0.5
        filter_complex = (
            "[0:a]highpass=f=28,"
            "equalizer=f=160:g=0.65:width_type=h:width=160,"
            "equalizer=f=2600:g=0.45:width_type=h:width=1800,"
            "equalizer=f=6200:g=0.18:width_type=h:width=2600,"
            "equalizer=f=11500:g=-0.35:width_type=h:width=5000,"
            "chorus=0.35:0.78:13|21:0.012|0.009:0.10|0.08:0.12|0.10,"
            "alimiter=limit=0.97[main];"
            f"anoisesrc=color=brown:amplitude=0.00028:duration={noise_len:.3f}:sample_rate={sample_rate}[n0];"
            f"anoisesrc=color=pink:amplitude=0.00042:duration={noise_len:.3f}:sample_rate={sample_rate}[n1];"
            "[n0]highpass=f=90,lowpass=f=760,volume=0.22[low];"
            "[n1]highpass=f=5200,lowpass=f=19000,volume=0.38[hi];"
            "[main][low][hi]amix=inputs=3:duration=first:normalize=0:weights='1 0.08 0.14',"
            "volume=2.25,alimiter=limit=0.97,"
            f"atrim=duration={duration:.3f},asetpts=N/SR/TB"
        )
        cmd = [self.ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", out_file, "-filter_complex", filter_complex, "-ar", sample_rate, "-ac", "2"]
        fmt = fmt.lower()
        if fmt == "mp3":
            cmd += ["-codec:a", "libmp3lame", "-b:a", "320k"]
        elif fmt == "flac":
            cmd += ["-compression_level", "5"]
        else:
            cmd += ["-c:a", "pcm_s16le"]
        cmd.append(tmp)
        try:
            self._run(cmd, "spectrum polish", capture=False)
            if tmp.exists() and tmp.stat().st_size > 1024:
                shutil.move(str(tmp), str(out_file))
            else:
                raise RuntimeError("spectrum polish did not create a valid file")
        finally:
            if tmp.exists():
                tmp.unlink(missing_ok=True)

    def _apply_platform_preset(self, out_file: Path, platform_code: str | None, fmt: str) -> tuple[Path, str]:
        code = (platform_code or "").strip().upper()
        if not code or code not in PLATFORM_PRESETS:
            return out_file, fmt
        preset = PLATFORM_PRESETS[code]
        if not preset.get("postprocess", False):
            return out_file, fmt
        target_fmt = str(preset.get("format") or fmt).lower()
        target = out_file.with_name(f"{out_file.stem}_{code}.{target_fmt}")
        args = list(preset.get("args") or [])
        cmd = [
            self.ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
            "-i", out_file, "-af", str(preset["chain"]),
        ] + args + [target]
        self._run(cmd, f"{code} 输出规格整理", capture=False)
        if not target.exists() or target.stat().st_size <= 1024:
            raise RuntimeError(f"{code} 输出规格未生成有效文件")
        try:
            out_file.unlink(missing_ok=True)
        except Exception:
            pass
        return target, target_fmt

    def _apply_legacy_final_master(self, out_file: Path) -> None:
        tmp = out_file.with_name(out_file.stem + "_legacy_master_tmp" + out_file.suffix)
        chain = (
            "highpass=f=46,"
            "equalizer=f=60:g=-6.0:width_type=h:width=45,"
            "equalizer=f=140:g=0.7:width_type=h:width=90,"
            "equalizer=f=500:g=1.5:width_type=h:width=420,"
            "equalizer=f=1600:g=2.5:width_type=h:width=1200,"
            "equalizer=f=3900:g=4.0:width_type=h:width=2600,"
            "equalizer=f=7800:g=2.0:width_type=h:width=4200,"
            "equalizer=f=15000:g=-1.6:width_type=h:width=5000,"
            "equalizer=f=60:g=-0.9:width_type=h:width=45,"
            "equalizer=f=150:g=1.0:width_type=h:width=110,"
            "equalizer=f=500:g=-0.1:width_type=h:width=420,"
            "equalizer=f=1700:g=-0.4:width_type=h:width=1200,"
            "equalizer=f=7800:g=-0.7:width_type=h:width=4200,"
            "equalizer=f=14500:g=-1.2:width_type=h:width=5200,"
            "volume=0.21dB,alimiter=limit=0.982"
        )
        cmd = [
            self.ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
            "-i", out_file, "-af", chain,
            "-ar", "48000", "-ac", "2", "-map_metadata", "-1",
            "-c:a", "pcm_s16le", tmp,
        ]
        try:
            self._run(cmd, "legacy final master", capture=False)
            if tmp.exists() and tmp.stat().st_size > 1024:
                shutil.move(str(tmp), str(out_file))
            else:
                raise RuntimeError("legacy final master did not create a valid file")
        finally:
            if tmp.exists():
                tmp.unlink(missing_ok=True)

    def _apply_legacy_scheme9_tone_match(self, out_file: Path) -> None:
        """Final v3.0 tone/width match for legacy combos that finish on scheme 9."""
        tmp = out_file.with_name(out_file.stem + "_scheme9_match_tmp" + out_file.suffix)
        chain = (
            "equalizer=f=42:g=-11.0:width_type=h:width=36,"
            "equalizer=f=85:g=-1.4:width_type=h:width=65,"
            "equalizer=f=180:g=1.7:width_type=h:width=140,"
            "equalizer=f=380:g=2.0:width_type=h:width=300,"
            "equalizer=f=850:g=2.0:width_type=h:width=700,"
            "equalizer=f=1700:g=2.2:width_type=h:width=1200,"
            "equalizer=f=3200:g=3.0:width_type=h:width=2200,"
            "equalizer=f=5800:g=1.3:width_type=h:width=3200,"
            "equalizer=f=14000:g=1.2:width_type=h:width=5000,"
            "stereotools=slev=1.03,volume=-0.35dB,alimiter=limit=0.93:level=false"
        )
        cmd = [
            self.ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
            "-i", out_file, "-af", chain,
            "-ar", "48000", "-ac", "2", "-map_metadata", "-1",
            "-c:a", "pcm_s16le", tmp,
        ]
        try:
            self._run(cmd, "legacy scheme 9 tone match", capture=False)
            if tmp.exists() and tmp.stat().st_size > 1024:
                shutil.move(str(tmp), str(out_file))
            else:
                raise RuntimeError("legacy scheme 9 tone match did not create a valid file")
        finally:
            if tmp.exists():
                tmp.unlink(missing_ok=True)

    def _codec_args_for_output(self, out_file: Path) -> list[str]:
        suffix = out_file.suffix.lower()
        if suffix == ".mp3":
            return ["-codec:a", "libmp3lame", "-b:a", "320k"]
        if suffix == ".flac":
            return ["-compression_level", "5"]
        return ["-c:a", "pcm_s16le"]

    def _polish_mode_for_schemes(self, scheme_ids: list[int]) -> str:
        ids = [int(x) for x in scheme_ids]
        if ids == [1]:
            return "none"
        if ids == [17] or (17 in ids and len(ids) <= 2):
            return "dj"
        if ids == [15] or ids[-1:] == [15]:
            return "curve"
        if ids == [16] or ids[-1:] == [16]:
            return "master"
        if ids == [1, 4]:
            return "bright"
        if ids == [1, 5]:
            return "folk"
        if ids == [1, 9]:
            return "vocal"
        return "balanced"

    def _apply_multiband_natural_polish(self, out_file: Path, mode: str = "balanced") -> None:
        mode = (mode or "balanced").strip().lower()
        if mode == "none":
            self.log("最终保真收尾：单方案轻修，跳过多频段重组")
            return
        tmp = out_file.with_name(out_file.stem + "_multiband_tmp" + out_file.suffix)
        chains = {
            "dj": (
                "[0:a]asplit=6[sub][bass][lm][md][pr][ar];"
                "[sub]lowpass=f=90,volume=1.015[sub1];"
                "[bass]highpass=f=90,lowpass=f=240,volume=1.018[bass1];"
                "[lm]highpass=f=240,lowpass=f=720,volume=1.004[lm1];"
                "[md]highpass=f=720,lowpass=f=2600,volume=1.006[md1];"
                "[pr]highpass=f=2600,lowpass=f=7200,volume=0.998[pr1];"
                "[ar]highpass=f=7200,lowpass=f=18500,volume=1.006[ar1];"
                "[sub1][bass1][lm1][md1][pr1][ar1]amix=inputs=6:normalize=0,"
                "volume=4.6dB,acompressor=threshold=-18dB:ratio=1.06:attack=28:release=240:makeup=1.0,"
                "alimiter=limit=0.965:level=false[out]"
            ),
            "curve": (
                "[0:a]asplit=5[lo][lm][md][pr][ar];"
                "[lo]lowpass=f=130,volume=0.996[lo1];"
                "[lm]highpass=f=130,lowpass=f=560,volume=1.006[lm1];"
                "[md]highpass=f=560,lowpass=f=2200,volume=1.016[md1];"
                "[pr]highpass=f=2200,lowpass=f=6200,volume=1.012[pr1];"
                "[ar]highpass=f=6200,lowpass=f=18000,volume=1.002[ar1];"
                "[lo1][lm1][md1][pr1][ar1]amix=inputs=5:normalize=0,"
                "volume=3.6dB,acompressor=threshold=-20dB:ratio=1.08:attack=22:release=210:makeup=1.0,"
                "alimiter=limit=0.955:level=false[out]"
            ),
            "master": (
                "[0:a]asplit=5[lo][lm][md][pr][ar];"
                "[lo]lowpass=f=150,volume=1.000[lo1];"
                "[lm]highpass=f=150,lowpass=f=620,volume=1.004[lm1];"
                "[md]highpass=f=620,lowpass=f=2500,volume=1.006[md1];"
                "[pr]highpass=f=2500,lowpass=f=6600,volume=1.002[pr1];"
                "[ar]highpass=f=6600,lowpass=f=18000,volume=1.003[ar1];"
                "[lo1][lm1][md1][pr1][ar1]amix=inputs=5:normalize=0,"
                "volume=3.5dB,acompressor=threshold=-21dB:ratio=1.05:attack=28:release=260:makeup=1.0,"
                "alimiter=limit=0.955:level=false[out]"
            ),
            "vocal": (
                "[0:a]asplit=5[lo][lm][md][pr][ar];"
                "[lo]lowpass=f=145,volume=0.996[lo1];"
                "[lm]highpass=f=145,lowpass=f=620,volume=1.008[lm1];"
                "[md]highpass=f=620,lowpass=f=2500,volume=1.010[md1];"
                "[pr]highpass=f=2500,lowpass=f=6600,volume=0.998[pr1];"
                "[ar]highpass=f=6600,lowpass=f=18000,volume=1.006[ar1];"
                "[lo1][lm1][md1][pr1][ar1]amix=inputs=5:normalize=0,"
                "volume=3.7dB,acompressor=threshold=-20dB:ratio=1.08:attack=22:release=210:makeup=1.0,"
                "alimiter=limit=0.955:level=false[out]"
            ),
            "folk": (
                "[0:a]asplit=5[lo][lm][md][pr][ar];"
                "[lo]lowpass=f=145,volume=0.998[lo1];"
                "[lm]highpass=f=145,lowpass=f=620,volume=1.006[lm1];"
                "[md]highpass=f=620,lowpass=f=2500,volume=1.006[md1];"
                "[pr]highpass=f=2500,lowpass=f=6600,volume=0.996[pr1];"
                "[ar]highpass=f=6600,lowpass=f=18000,volume=1.002[ar1];"
                "[lo1][lm1][md1][pr1][ar1]amix=inputs=5:normalize=0,"
                "volume=3.3dB,acompressor=threshold=-21dB:ratio=1.06:attack=26:release=230:makeup=1.0,"
                "alimiter=limit=0.945:level=false[out]"
            ),
            "bright": (
                "[0:a]asplit=5[lo][lm][md][pr][ar];"
                "[lo]lowpass=f=145,volume=0.996[lo1];"
                "[lm]highpass=f=145,lowpass=f=620,volume=1.004[lm1];"
                "[md]highpass=f=620,lowpass=f=2500,volume=1.004[md1];"
                "[pr]highpass=f=2500,lowpass=f=6600,volume=0.990[pr1];"
                "[ar]highpass=f=6600,lowpass=f=18000,volume=0.992[ar1];"
                "[lo1][lm1][md1][pr1][ar1]amix=inputs=5:normalize=0,"
                "volume=3.1dB,acompressor=threshold=-21dB:ratio=1.06:attack=28:release=240:makeup=1.0,"
                "alimiter=limit=0.940:level=false[out]"
            ),
            "balanced": (
                "[0:a]asplit=5[lo][lm][md][pr][ar];"
                "[lo]lowpass=f=155,volume=0.996[lo1];"
                "[lm]highpass=f=155,lowpass=f=620,volume=1.006[lm1];"
                "[md]highpass=f=620,lowpass=f=2500,volume=1.008[md1];"
                "[pr]highpass=f=2500,lowpass=f=6600,volume=1.000[pr1];"
                "[ar]highpass=f=6600,lowpass=f=18000,volume=1.004[ar1];"
                "[lo1][lm1][md1][pr1][ar1]amix=inputs=5:normalize=0,"
                "volume=3.6dB,acompressor=threshold=-20dB:ratio=1.08:attack=22:release=220:makeup=1.0,"
                "alimiter=limit=0.955:level=false[out]"
            ),
        }
        filter_complex = chains.get(mode, chains["balanced"])
        cmd = [
            self.ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
            "-i", out_file, "-filter_complex", filter_complex,
            "-map", "[out]", "-ar", "48000", "-ac", "2", "-map_metadata", "-1",
        ] + self._codec_args_for_output(out_file) + [tmp]
        try:
            self._run(cmd, f"multiband natural polish ({mode})", capture=False)
            if tmp.exists() and tmp.stat().st_size > 1024:
                shutil.move(str(tmp), str(out_file))
            else:
                raise RuntimeError("multiband natural polish did not create a valid file")
        finally:
            if tmp.exists():
                tmp.unlink(missing_ok=True)

    def _reserve_output_headroom(self, out_file: Path, mode: str = "balanced") -> None:
        tmp = out_file.with_name(out_file.stem + "_headroom_tmp" + out_file.suffix)
        mode = (mode or "balanced").strip().lower()
        level_map = {
            "none": ("volume=-0.35dB", "0.965"),
            "dj": ("volume=-0.30dB", "0.965"),
            "vocal": ("volume=-0.45dB", "0.950"),
            "curve": ("volume=-0.45dB", "0.955"),
            "master": ("volume=-0.50dB", "0.955"),
            "folk": ("volume=-0.65dB", "0.945"),
            "bright": ("volume=-0.80dB", "0.940"),
            "balanced": ("volume=-0.55dB", "0.950"),
        }
        vol, limit = level_map.get(mode, level_map["balanced"])
        cmd = [
            self.ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
            "-i", out_file, "-af", f"{vol},alimiter=limit={limit}:level=false",
            "-ar", "48000", "-ac", "2", "-map_metadata", "-1",
        ] + self._codec_args_for_output(out_file) + [tmp]
        try:
            self._run(cmd, "final headroom reserve", capture=False)
            if tmp.exists() and tmp.stat().st_size > 1024:
                shutil.move(str(tmp), str(out_file))
            else:
                raise RuntimeError("final headroom reserve did not create a valid file")
        finally:
            if tmp.exists():
                tmp.unlink(missing_ok=True)

    def process_pipeline(self, src: Path, out_dir: Path | str, scheme_ids: list[int], fmt: str = "wav", progress: Callable[[int, str], None] | None = None, platform_code: str | None = None) -> Path:
        # Sequential pipeline: temp stages are internal; final output is one file.
        ok, msg = self.validate()
        if not ok:
            raise RuntimeError(msg)
        src = Path(src).resolve()
        if not src.exists():
            raise FileNotFoundError(str(src))
        out_dir = Path(out_dir or DEFAULT_OUTPUT_DIR).resolve()
        out_dir.mkdir(parents=True, exist_ok=True)
        scheme_ids = [int(x) for x in scheme_ids if int(x) in SCHEME_BY_ID]
        if not scheme_ids:
            raise RuntimeError("未选择有效方案")
        if len(scheme_ids) > 4:
            raise RuntimeError("顺序流水线最多建议 3-4 个方案，方案过多会降低音质和速度。")

        keep_stages = os.getenv("AUDIOFLOW_KEEP_STAGES", "0").strip() == "1"
        legacy_job_root = out_dir / ".audioflow_temp"
        if not keep_stages and legacy_job_root.exists():
            shutil.rmtree(legacy_job_root, ignore_errors=True)
        job_root = Path(tempfile.gettempdir()) / "AudioFlowStudio" / "jobs"
        job_root.mkdir(parents=True, exist_ok=True)
        base = safe_name(src.name)
        job_dir = Path(tempfile.mkdtemp(prefix=f"af_native_{int(time.time())}_", dir=str(job_root)))
        stage_export_dir = out_dir / f"{base}_stages_{'-'.join(map(str, scheme_ids))}"
        try:
            current = src
            source_duration = float(self.probe(src).duration or 0)
            total = len(scheme_ids)
            self.log(f"原生流水线：{src.name} -> 顺序 {'-'.join(map(str, scheme_ids))}")
            for i, sid in enumerate(scheme_ids, start=1):
                scheme = SCHEME_BY_ID[int(sid)]
                if progress:
                    progress(5 + int((i - 1) * 84 / total), f"方案{sid:02d} {scheme.get('name','')}")
                self.log(f"流水线第 {i}/{total} 步：读取 {Path(current).name} -> 方案{sid:02d} {scheme.get('name','')}")
                apply_legacy = not (total > 1 and i < total)
                current = self._process_native_scheme(Path(current), job_dir, i, int(sid), "WAV", apply_legacy=apply_legacy)
                if total > 1 and i < total:
                    current = self._normalize_between_schemes(Path(current), source_duration, job_dir, i, scheme)
                if keep_stages:
                    stage_export_dir.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(current, stage_export_dir / Path(current).name)
            suffix = "-".join(str(i) for i in scheme_ids)
            last_scheme = SCHEME_BY_ID[int(scheme_ids[-1])]
            ext = "mp3" if str(fmt).lower() == "mp3" else "wav"
            out = out_dir / f"{base}_{suffix}.{ext}"
            if progress:
                progress(92, "导出最终文件")
            self._export_or_copy_final(Path(current), out, ext, source_duration if len(scheme_ids) > 1 else 0)
            if len(scheme_ids) > 1 and int(scheme_ids[-1]) == 9:
                self._apply_legacy_scheme9_tone_match(out)
            if platform_code:
                if progress:
                    progress(96, f"{str(platform_code).upper()} 快捷组合整理")
                out, ext = self._apply_platform_preset(out, platform_code, ext)
            polish_mode = self._polish_mode_for_schemes(scheme_ids)
            self._apply_multiband_natural_polish(out, polish_mode)
            self._reserve_output_headroom(out, polish_mode)
            self.ensure_audible_output(out)
            report = self.quality_report(src, out)
            self.log(
                "本地质检：%s 分，%s，平均响度 %s，峰值 %s"
                % (
                    report.score,
                    report.note,
                    "--" if report.mean_db is None else f"{report.mean_db:.1f} dB",
                    "--" if report.max_db is None else f"{report.max_db:.1f} dB",
                )
            )
            if not out.exists() or out.stat().st_size <= 1024:
                raise RuntimeError("最终文件无效")
            if progress:
                progress(100, "完成")
            self.log("导出完成：" + out.name)
            return out
        finally:
            if not keep_stages:
                shutil.rmtree(job_dir, ignore_errors=True)
                for folder in (job_root, job_root.parent):
                    try:
                        folder.rmdir()
                    except OSError:
                        pass

    def process_compare(self, src: Path, out_dir: Path | str, scheme_ids: list[int], fmt: str = "wav", progress: Callable[[int, str], None] | None = None) -> list[Path]:
        outputs = []
        for i, sid in enumerate(scheme_ids, start=1):
            def cb(p, t, i=i):
                if progress:
                    progress(int(((i - 1) + p / 100) * 100 / max(1, len(scheme_ids))), t)
            out = self.process_pipeline(src, out_dir, [int(sid)], fmt, progress=cb)
            outputs.append(out)
        return outputs

    def convert_format(self, src: Path, out_dir: Path | str, fmt: str) -> Path:
        ok, msg = self.validate()
        if not ok:
            raise RuntimeError(msg)
        src = Path(src).resolve()
        out_dir = Path(out_dir).resolve()
        out_dir.mkdir(parents=True, exist_ok=True)
        ext = fmt.lower()
        out = out_dir / f"{safe_name(src.name)}_convert.{ext}"
        self._export_or_copy_final(src, out, ext)
        return out

    def smart_master_upgrade(self, src: Path, out_dir: Path | str, style: str = "natural", fmt: str = "mp3") -> Path:
        ok, msg = self.validate()
        if not ok:
            raise RuntimeError(msg)
        src = Path(src).resolve()
        out_dir = Path(out_dir).resolve() / "鏅鸿兘姣嶉煶鍗囩骇"
        out_dir.mkdir(parents=True, exist_ok=True)
        suffix = ".mp3" if fmt.lower() == "mp3" else ".wav"
        out = out_dir / f"{safe_name(src.name)}_鏅鸿兘姣嶉煶鍗囩骇{suffix}"
        if style == "soft":
            chain = (
                "highpass=f=28,"
                "equalizer=f=180:g=0.5:width_type=h:width=160,"
                "equalizer=f=2600:g=-0.8:width_type=h:width=1200,"
                "equalizer=f=4200:g=-0.7:width_type=h:width=1600,"
                "equalizer=f=9200:g=-1.0:width_type=h:width=3600,"
                "acompressor=threshold=-18dB:ratio=1.55:attack=18:release=160:makeup=1,"
                "loudnorm=I=-17.5:TP=-2.2:LRA=9.5,alimiter=limit=0.86"
            )
        elif style == "detect":
            chain = (
                "highpass=f=30,"
                "equalizer=f=120:g=0.8:width_type=h:width=100,"
                "equalizer=f=900:g=-0.35:width_type=h:width=700,"
                "equalizer=f=3200:g=-0.65:width_type=h:width=1400,"
                "equalizer=f=7600:g=-0.75:width_type=h:width=2800,"
                "afftdn=nf=-28,"
                "acompressor=threshold=-19dB:ratio=1.65:attack=14:release=150:makeup=1,"
                "loudnorm=I=-17.0:TP=-2.0:LRA=8.5,alimiter=limit=0.88"
            )
        else:
            chain = (
                "highpass=f=28,"
                "equalizer=f=160:g=0.55:width_type=h:width=140,"
                "equalizer=f=320:g=-0.25:width_type=h:width=260,"
                "equalizer=f=2500:g=-0.45:width_type=h:width=1200,"
                "equalizer=f=5800:g=-0.45:width_type=h:width=2200,"
                "acompressor=threshold=-18dB:ratio=1.5:attack=16:release=140:makeup=1,"
                "loudnorm=I=-17.2:TP=-2.0:LRA=9,alimiter=limit=0.88"
            )
        cmd = [self.ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", src, "-af", chain, "-ar", "44100", "-ac", "2", "-map_metadata", "-1"]
        if suffix == ".mp3":
            cmd += ["-c:a", "libmp3lame", "-b:a", "320k"]
        else:
            cmd += ["-c:a", "pcm_s16le"]
        cmd.append(out)
        self._run(cmd, "鏅鸿兘姣嶉煶鍗囩骇", capture=False)
        return out

    def light_split(self, src: Path, out_dir: Path | str) -> tuple[Path, Path]:
        # 杞婚噺杈呭姪鍒嗚建锛屼笉绛夊悓浜?Demucs/UVR 涓撲笟AI鍒嗚建銆?        ok, msg = self.validate()
        if not ok:
            raise RuntimeError(msg)
        src = Path(src).resolve()
        out_dir = Path(out_dir).resolve() / f"{safe_name(src.name)}_split"
        out_dir.mkdir(parents=True, exist_ok=True)
        vocal = out_dir / f"{safe_name(src.name)}_浜哄０杈呭姪.wav"
        inst = out_dir / f"{safe_name(src.name)}_浼村杈呭姪.wav"
        self._run([self.ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", src, "-af", "pan=mono|c0=0.5*c0+0.5*c1,highpass=f=110,lowpass=f=12500,equalizer=f=2600:g=2.2:width_type=h:width=1800,afftdn=nf=-28,dynaudnorm=f=120:g=7,alimiter=limit=0.96", "-ar", "48000", "-c:a", "pcm_s24le", vocal], "杞婚噺浜哄０杈呭姪鍒嗙", capture=False)
        self._run([self.ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", src, "-af", "pan=stereo|c0=c0-0.90*c1|c1=c1-0.90*c0,highpass=f=35,lowpass=f=18500,equalizer=f=2500:g=-2.5:width_type=h:width=2000,dynaudnorm=f=120:g=5,alimiter=limit=0.96", "-ar", "48000", "-c:a", "pcm_s24le", inst], "杞婚噺浼村杈呭姪鍒嗙", capture=False)
        return vocal, inst
