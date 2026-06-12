# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Any

import requests

from settings import UPDATE_INFO_URL, app_data_dir


def platform_key() -> str:
    if sys.platform == "darwin":
        return "macos"
    if sys.platform.startswith("win"):
        return "windows"
    return sys.platform


def _parts(version: str) -> tuple[int, ...]:
    nums = []
    for piece in str(version or "").replace("-", ".").split("."):
        if piece.isdigit():
            nums.append(int(piece))
        else:
            digits = "".join(ch for ch in piece if ch.isdigit())
            nums.append(int(digits or 0))
    return tuple(nums or [0])


def is_newer(latest: str, current: str) -> bool:
    return _parts(latest) > _parts(current)


def current_exe() -> Path | None:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve()
    return None


def fetch_update_info(current_version: str) -> dict[str, Any] | None:
    try:
        resp = requests.get(UPDATE_INFO_URL, params={"current": current_version, "platform": platform_key()}, timeout=8)
        if resp.status_code != 200:
            return None
        data = resp.json()
        if not data.get("ok"):
            return None
        latest = str(data.get("version") or "")
        if not latest or not is_newer(latest, current_version):
            return None
        if not data.get("download_url"):
            return None
        return data
    except Exception:
        return None


def download_update(info: dict[str, Any], progress=None) -> Path:
    update_dir = app_data_dir() / "updates"
    update_dir.mkdir(parents=True, exist_ok=True)
    suffix = ".zip" if platform_key() == "macos" else ".exe"
    target = update_dir / f"AudioFlow_Studio_v31.new{suffix}"
    tmp = target.with_suffix(".download")
    with requests.get(str(info["download_url"]), stream=True, timeout=(10, 300)) as resp:
        resp.raise_for_status()
        total = int(resp.headers.get("Content-Length") or 0)
        done = 0
        with tmp.open("wb") as f:
            for chunk in resp.iter_content(chunk_size=1024 * 1024 * 4):
                if chunk:
                    f.write(chunk)
                    done += len(chunk)
                    if progress and total:
                        progress(min(99, int(done * 100 / total)), "正在下载自动更新")
        if progress:
            progress(100, "更新包下载完成")
    expected = str(info.get("sha256") or "").strip().lower()
    if expected:
        h = hashlib.sha256()
        with tmp.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024 * 4), b""):
                h.update(chunk)
        actual = h.hexdigest().lower()
        if actual != expected:
            tmp.unlink(missing_ok=True)
            raise RuntimeError("更新包校验失败")
    tmp.replace(target)
    return target


def schedule_replace(downloaded_exe: Path) -> bool:
    exe = current_exe()
    if not exe:
        return False
    if platform_key() == "macos":
        return schedule_replace_macos(downloaded_exe, exe)
    if not sys.platform.startswith("win"):
        return False
    update_dir = downloaded_exe.parent
    script = update_dir / "install_update.cmd"
    lines = [
        "@echo off",
        "chcp 65001 >nul",
        "timeout /t 2 /nobreak >nul",
        ":wait_app",
        f'tasklist /FI "IMAGENAME eq {exe.name}" | find /I "{exe.name}" >nul',
        "if not errorlevel 1 (",
        "  timeout /t 1 /nobreak >nul",
        "  goto wait_app",
        ")",
        f'copy /Y "{downloaded_exe}" "{exe}" >nul',
        f'start "" "{exe}"',
        f'del "{downloaded_exe}" >nul 2>nul',
        'del "%~f0" >nul 2>nul',
    ]
    script.write_text("\r\n".join(lines), encoding="utf-8")
    subprocess.Popen(["cmd", "/c", str(script)], creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return True


def _current_app_bundle(exe: Path) -> Path | None:
    for parent in [exe, *exe.parents]:
        if parent.suffix.lower() == ".app":
            return parent
    return None


def schedule_replace_macos(downloaded_zip: Path, exe: Path) -> bool:
    app_bundle = _current_app_bundle(exe)
    if not app_bundle:
        return False
    update_dir = downloaded_zip.parent
    extract_dir = update_dir / "mac_extract"
    if extract_dir.exists():
        import shutil
        shutil.rmtree(extract_dir, ignore_errors=True)
    extract_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(downloaded_zip, "r") as zf:
        zf.extractall(extract_dir)
    candidates = list(extract_dir.glob("*.app"))
    if not candidates:
        raise RuntimeError("Mac 更新包内没有 .app")
    new_app = candidates[0]
    script = update_dir / "install_update.sh"
    script.write_text(
        "\n".join([
            "#!/bin/sh",
            "sleep 2",
            f'while pgrep -f "{app_bundle.name}/Contents/MacOS" >/dev/null 2>&1; do sleep 1; done',
            f'rm -rf "{app_bundle}"',
            f'cp -R "{new_app}" "{app_bundle}"',
            f'open "{app_bundle}"',
            f'rm -rf "{extract_dir}" "{downloaded_zip}"',
            'rm -f "$0"',
        ]),
        encoding="utf-8",
    )
    script.chmod(0o755)
    subprocess.Popen(["/bin/sh", str(script)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return True


def prepare_update(current_version: str, progress=None) -> tuple[bool, str]:
    info = fetch_update_info(current_version)
    if not info:
        return False, ""
    if progress:
        progress(0, f"发现新版 {info.get('version') or ''}，准备下载")
    downloaded = download_update(info, progress=progress)
    scheduled = schedule_replace(downloaded)
    if not scheduled:
        return False, ""
    return True, str(info.get("version") or "")
