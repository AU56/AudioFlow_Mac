from __future__ import annotations

from raw_loader import exec_raw


exec_raw("engine.raw", globals())


_raw_process_pipeline = AudioEngine.process_pipeline
_raw_probe = AudioEngine.probe
_raw_measure_levels = AudioEngine.measure_levels
_raw_normalize_between_schemes = AudioEngine._normalize_between_schemes


def _cache_key_for_audio_file(file):
    try:
        from pathlib import Path

        path = Path(file).resolve()
        stat = path.stat()
        return (str(path), int(stat.st_size), int(getattr(stat, "st_mtime_ns", 0)))
    except Exception:
        return None


def _cached_probe(self, file):
    key = _cache_key_for_audio_file(file)
    if key is None:
        return _raw_probe(self, file)
    cache = getattr(self, "_audioflow_probe_cache", None)
    if cache is None:
        cache = {}
        try:
            self._audioflow_probe_cache = cache
        except Exception:
            return _raw_probe(self, file)
    if key not in cache:
        cache[key] = _raw_probe(self, file)
    return cache[key]


def _cached_measure_levels(self, file):
    key = _cache_key_for_audio_file(file)
    if key is None:
        return _raw_measure_levels(self, file)
    cache = getattr(self, "_audioflow_level_cache", None)
    if cache is None:
        cache = {}
        try:
            self._audioflow_level_cache = cache
        except Exception:
            return _raw_measure_levels(self, file)
    if key not in cache:
        cache[key] = _raw_measure_levels(self, file)
    return cache[key]


def _cached_stream_meta(self, file):
    key = _cache_key_for_audio_file(file)
    if key is None:
        return None
    cache = getattr(self, "_audioflow_stream_meta_cache", None)
    if cache is None:
        cache = {}
        try:
            self._audioflow_stream_meta_cache = cache
        except Exception:
            return None
    if key in cache:
        return cache[key]
    try:
        import json
        import subprocess

        cp = subprocess.run(
            [
                str(self.ffprobe),
                "-v",
                "error",
                "-print_format",
                "json",
                "-show_entries",
                "format=duration:stream=codec_name,sample_rate,channels",
                str(file),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=8,
            shell=False,
            **self._startup_kwargs(),
        )
        data = json.loads(cp.stdout or "{}")
        stream = (data.get("streams") or [{}])[0] or {}
        fmt = data.get("format") or {}
        meta = {
            "duration": float(fmt.get("duration") or 0),
            "codec_name": str(stream.get("codec_name") or "").lower(),
            "sample_rate": str(stream.get("sample_rate") or ""),
            "channels": int(stream.get("channels") or 0),
        }
        cache[key] = meta
        return meta
    except Exception:
        return None


def _optimized_normalize_between_schemes(self, src_stage, source_duration, stage_dir, step, scheme):
    try:
        from pathlib import Path

        src_stage = Path(src_stage)
        target = Path(stage_dir) / f"stage_{int(step):02d}_legacy_bridge.wav"
        meta = _cached_stream_meta(self, src_stage)
        if not meta:
            return _raw_normalize_between_schemes(self, src_stage, source_duration, stage_dir, step, scheme)

        current_duration = float(meta.get("duration") or 0)
        duration_target = float(source_duration or 0)
        wanted_rate = self._scheme_stage_rate(scheme)
        close_duration = (
            current_duration > 1
            and duration_target > 1
            and abs(current_duration - duration_target) < 0.25
        )
        if (
            close_duration
            and meta.get("codec_name") == "pcm_s16le"
            and str(meta.get("sample_rate") or "") == str(wanted_rate)
            and int(meta.get("channels") or 0) == 2
        ):
            return src_stage

        cmd = [
            self.ffmpeg,
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            src_stage,
            "-vn",
        ]
        if current_duration > 1 and duration_target > 1 and abs(current_duration - duration_target) >= 0.25:
            cmd += ["-af", self._atempo_chain(current_duration / duration_target)]
        cmd += ["-ar", wanted_rate, "-ac", "2", "-c:a", "pcm_s16le", target]
        self._run(cmd, f"方案{int(scheme['index']):02d} 中间导出整理", capture=False)
        if target.exists() and target.stat().st_size > 1024:
            return target
        return src_stage
    except Exception:
        return _raw_normalize_between_schemes(self, src_stage, source_duration, stage_dir, step, scheme)


AudioEngine.probe = _cached_probe
AudioEngine.measure_levels = _cached_measure_levels
AudioEngine._normalize_between_schemes = _optimized_normalize_between_schemes


def _v30_no_extra_step(self, *args, **kwargs):
    return args[0] if args else None


def _v30_export_or_copy_final(self, src_stage, out_file, fmt, duration_target=None):
    import shutil
    from pathlib import Path

    src_stage = Path(src_stage)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    fmt = (fmt or "WAV").lower()
    duration_filter = None

    try:
        target_duration = float(duration_target or 0)
        if target_duration > 1:
            current_duration = float(self.probe(src_stage).duration or 0)
            if current_duration > 1 and abs(current_duration - target_duration) >= 0.25:
                duration_filter = self._atempo_chain(current_duration / target_duration)
                try:
                    self.log(f"duration lock: {current_duration:.2f}s -> {target_duration:.2f}s")
                except Exception:
                    pass
    except Exception as exc:
        try:
            self.log(f"\u65f6\u957f\u56de\u8d34\u8df3\u8fc7\uff1a{exc}")
        except Exception:
            pass

    def run_export(codec_args, desc):
        cmd = [
            self.ffmpeg,
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(src_stage),
        ]
        if duration_filter:
            cmd += ["-af", duration_filter]
        cmd += list(codec_args) + [str(out_file)]
        self._run(cmd, desc, capture=False)

    if fmt == "wav":
        if not duration_filter and src_stage.suffix.lower() == ".wav":
            shutil.copy2(src_stage, out_file)
            return
        if duration_filter:
            run_export(["-ar", "48000", "-ac", "2", "-c:a", "pcm_s24le"], "duration lock")
            return
        run_export(["-acodec", "pcm_s16le", "-ar", "48000", "-ac", "2"], "v3.0 final WAV export")
        return

    if fmt == "mp3":
        run_export(["-acodec", "libmp3lame", "-b:a", "320k"], "v3.0 final MP3 export")
        return

    run_export(self._codec_args_for_output(out_file), "v3.0 final audio export")


AudioEngine._apply_legacy_step_enhance = _v30_no_extra_step
AudioEngine._apply_legacy_scheme9_tone_match = _v30_no_extra_step
AudioEngine._apply_multiband_natural_polish = _v30_no_extra_step
AudioEngine._reserve_output_headroom = _v30_no_extra_step
AudioEngine._apply_detector_humanize = _v30_no_extra_step
AudioEngine._export_or_copy_final = _v30_export_or_copy_final


def _upload_acceptance_guard(self, out_file):
    from pathlib import Path
    import shutil

    out_file = Path(out_file)
    if not out_file.exists() or out_file.stat().st_size <= 1024:
        return out_file

    try:
        info = self.probe(out_file)
        mean_db, max_db = self.measure_levels(out_file)
        duration = float(getattr(info, "duration", 0) or 0)
    except Exception as exc:
        try:
            self.log(f"上传前质检跳过：{exc}")
        except Exception:
            pass
        return out_file

    warnings = []
    need_level_fix = False
    if duration and duration < 20:
        warnings.append("时长偏短")
    if mean_db is None or max_db is None:
        warnings.append("响度无法测量")
    else:
        if mean_db < -19 or max_db < -5.5:
            warnings.append("音量偏小")
            need_level_fix = True
        if mean_db > -8.0 or max_db >= -0.2:
            warnings.append("响度过满")
            need_level_fix = True

    if need_level_fix:
        tmp = out_file.with_name(out_file.stem + "_upload_guard_tmp" + out_file.suffix)
        try:
            self._run(
                [
                    self.ffmpeg,
                    "-y",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-i",
                    str(out_file),
                    "-af",
                    "highpass=f=28,lowpass=f=18500,loudnorm=I=-11.5:TP=-1.2:LRA=9,alimiter=limit=0.96",
                    "-ar",
                    "48000",
                    "-ac",
                    "2",
                    "-c:a",
                    "pcm_s24le",
                    str(tmp),
                ],
                "上传前稳态修正",
                capture=False,
            )
            if tmp.exists() and tmp.stat().st_size > 1024:
                shutil.move(str(tmp), str(out_file))
                mean_db, max_db = self.measure_levels(out_file)
                try:
                    self.log(
                        "上传前质检：已修正 "
                        + "、".join(warnings)
                        + f"，当前平均响度 {mean_db:.1f} dB，峰值 {max_db:.1f} dB"
                    )
                except Exception:
                    pass
        finally:
            try:
                if tmp.exists():
                    tmp.unlink()
            except Exception:
                pass
    else:
        try:
            note = "、".join(warnings) if warnings else "通过"
            if mean_db is not None and max_db is not None:
                self.log(f"上传前质检：{note}，平均响度 {mean_db:.1f} dB，峰值 {max_db:.1f} dB")
            else:
                self.log(f"上传前质检：{note}")
        except Exception:
            pass

    return out_file


def _process_pipeline_with_progress_heartbeat(
    self, src, out_dir, scheme_ids, fmt="wav", progress=None, platform_code=None
):
    if progress is None:
        out = _raw_process_pipeline(
            self, src, out_dir, scheme_ids, fmt=fmt, progress=None, platform_code=platform_code
        )
        return _upload_acceptance_guard(self, out)

    import threading
    import time

    stop_event = threading.Event()
    state_lock = threading.Lock()
    try:
        total_steps = max(1, len([int(x) for x in scheme_ids]))
    except Exception:
        total_steps = 1
    step_span = max(8, int(84 / total_steps))
    state = {"value": 0, "text": "处理中", "cap": 88}

    def emit_progress(value, text):
        value = max(0, min(100, int(value)))
        with state_lock:
            if value < state["value"]:
                value = state["value"]
            state["value"] = value
            if 5 <= value < 92:
                stage_offset = max(0, int((value - 5) / step_span))
                state["cap"] = min(91, 5 + ((stage_offset + 1) * step_span) - 3)
            elif value >= 92:
                state["cap"] = value
            if text:
                state["text"] = str(text)
            text = state["text"]
        try:
            progress(value, text)
        except Exception:
            pass

    def heartbeat():
        started = time.monotonic()
        while not stop_event.wait(0.7):
            with state_lock:
                current = int(state["value"])
                text = state["text"]
                cap = int(state["cap"])
            if current >= cap:
                continue
            elapsed = time.monotonic() - started
            step = 2 if elapsed > 18 else 1
            emit_progress(min(cap, current + step), text or "处理中")

    thread = threading.Thread(target=heartbeat, name="AudioFlowProgressHeartbeat", daemon=True)
    thread.start()
    try:
        out = _raw_process_pipeline(
            self,
            src,
            out_dir,
            scheme_ids,
            fmt=fmt,
            progress=emit_progress,
            platform_code=platform_code,
        )
        emit_progress(98, "上传前质检")
        return _upload_acceptance_guard(self, out)
    finally:
        stop_event.set()
        thread.join(timeout=0.2)


AudioEngine.process_pipeline = _process_pipeline_with_progress_heartbeat
