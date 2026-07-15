#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"

APP_NAME="AudioFlow Studio"
APP_VERSION="3.6.18"
DIST_APP="dist/${APP_NAME}.app"
ZIP_NAME="AudioFlow_Studio_Mac.zip"
PAYLOAD_DIR="release_payload"

_echo_step() {
  echo "[AudioFlow] $1"
}

_echo_step "Building macOS app ${APP_VERSION}..."

if [ -n "${AUDIOFLOW_BUILD_PYTHON:-}" ] && [ -x "${AUDIOFLOW_BUILD_PYTHON}" ]; then
  PYTHON_BASE="${AUDIOFLOW_BUILD_PYTHON}"
elif [ -n "${pythonLocation:-}" ] && [ -x "${pythonLocation}/bin/python3" ]; then
  PYTHON_BASE="${pythonLocation}/bin/python3"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BASE="$(command -v python3)"
elif command -v /opt/homebrew/bin/python3 >/dev/null 2>&1; then
  PYTHON_BASE="/opt/homebrew/bin/python3"
elif command -v /usr/local/bin/python3 >/dev/null 2>&1; then
  PYTHON_BASE="/usr/local/bin/python3"
else
  echo "ERROR: python3 not found."
  exit 1
fi

_echo_step "Selected Python: ${PYTHON_BASE}"
"${PYTHON_BASE}" --version
"${PYTHON_BASE}" - <<'PY'
import platform
import sys
print("[AudioFlow] Python detail:", sys.version.replace("\n", " "))
print("[AudioFlow] Machine:", platform.machine())
if sys.version_info[:2] != (3, 12):
    raise SystemExit("ERROR: macOS client must be built with Python 3.12.x. Refusing this runtime.")
PY

if ! command -v ffmpeg >/dev/null 2>&1 || ! command -v ffprobe >/dev/null 2>&1; then
  echo "ERROR: ffmpeg/ffprobe not found. Install with: brew install ffmpeg"
  exit 1
fi

if ! command -v sox >/dev/null 2>&1; then
  echo "ERROR: sox not found. Install with: brew install sox"
  exit 1
fi

FFMPEG_BIN="$(command -v ffmpeg)"
FFPROBE_BIN="$(command -v ffprobe)"
SOX_BIN="$(command -v sox)"
export FFMPEG_BIN FFPROBE_BIN SOX_BIN

if [ ! -f "assets/audioflow.icns" ] && [ -f "assets/audioflow_256.png" ] && command -v iconutil >/dev/null 2>&1; then
  rm -rf assets/audioflow.iconset
  mkdir -p assets/audioflow.iconset
  sips -z 16 16     assets/audioflow_256.png --out assets/audioflow.iconset/icon_16x16.png >/dev/null
  sips -z 32 32     assets/audioflow_256.png --out assets/audioflow.iconset/icon_16x16@2x.png >/dev/null
  sips -z 32 32     assets/audioflow_256.png --out assets/audioflow.iconset/icon_32x32.png >/dev/null
  sips -z 64 64     assets/audioflow_256.png --out assets/audioflow.iconset/icon_32x32@2x.png >/dev/null
  sips -z 128 128   assets/audioflow_256.png --out assets/audioflow.iconset/icon_128x128.png >/dev/null
  sips -z 256 256   assets/audioflow_256.png --out assets/audioflow.iconset/icon_128x128@2x.png >/dev/null
  sips -z 256 256   assets/audioflow_256.png --out assets/audioflow.iconset/icon_256x256.png >/dev/null
  sips -z 512 512   assets/audioflow_256.png --out assets/audioflow.iconset/icon_256x256@2x.png >/dev/null
  sips -z 512 512   assets/audioflow_256.png --out assets/audioflow.iconset/icon_512x512.png >/dev/null
  cp assets/audioflow_256.png assets/audioflow.iconset/icon_512x512@2x.png
  iconutil -c icns assets/audioflow.iconset -o assets/audioflow.icns
fi

VENV_DIR=".venv-build-macos"
rm -rf "$VENV_DIR"
"$PYTHON_BASE" -m venv "$VENV_DIR"
PYTHON_BIN="$PWD/$VENV_DIR/bin/python"
"$PYTHON_BIN" -m pip install --upgrade pip setuptools wheel
"$PYTHON_BIN" -m pip install -r requirements_client.txt

"$PYTHON_BIN" - <<'PY'
import marshal
from pathlib import Path
for name in ("main.raw", "engine.raw"):
    marshal.loads(Path(name).read_bytes())
from PySide6 import QtCore, QtWidgets
print("[AudioFlow] PySide6 Qt:", QtCore.qVersion())
print("[AudioFlow] PySide6 import check: OK")
PY

"$PYTHON_BIN" - <<'PY'
import schemes
bad = [
    str(s.get("index"))
    for s in schemes.SCHEMES
    if "rubberband" in str(s.get("af", "")).lower()
]
if bad:
    raise SystemExit("ERROR: macOS ffmpeg filter compatibility failed for schemes: " + ",".join(bad))
print("[AudioFlow] macOS ffmpeg filter compatibility: OK")
PY

"$PYTHON_BIN" - <<'PY'
import os
import subprocess
import tempfile
from pathlib import Path

import schemes


ffmpeg = os.environ["FFMPEG_BIN"]
sox = os.environ["SOX_BIN"]


def run(cmd, title):
    cp = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if cp.returncode != 0:
        print(f"[AudioFlow] Scheme smoke failed: {title}")
        print(cp.stderr[-3000:])
        raise SystemExit(cp.returncode)


with tempfile.TemporaryDirectory(prefix="audioflow_scheme_smoke_") as td:
    td = Path(td)
    src = td / "input.wav"
    run(
        [
            ffmpeg,
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=220:duration=8",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=880:duration=8",
            "-filter_complex",
            "[0:a][1:a]amix=inputs=2:duration=longest,volume=0.35",
            "-ar",
            "48000",
            "-ac",
            "2",
            "-c:a",
            "pcm_s16le",
            str(src),
        ],
        "create test audio",
    )

    passed = []
    for scheme in schemes.SCHEMES:
        idx = int(scheme["index"])
        engine = str(scheme.get("engine", "")).lower()
        if engine == "sox":
            out = td / f"scheme_{idx:02d}.wav"
            cmd = [sox, str(src), str(out)] + [str(x) for x in scheme.get("sox_args", [])]
        elif engine == "ffmpeg":
            out = td / f"scheme_{idx:02d}.mp3" if scheme.get("force_mp3") else td / f"scheme_{idx:02d}.wav"
            cmd = [
                ffmpeg,
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                str(src),
                "-af",
                str(scheme.get("af", "")),
            ] + [str(x) for x in scheme.get("extra_args", [])] + [str(out)]
        else:
            raise SystemExit(f"ERROR: unknown scheme engine {idx}: {engine}")

        run(cmd, f"{idx:02d} {scheme.get('name', '')}")
        if not out.exists() or out.stat().st_size <= 1024:
            raise SystemExit(f"ERROR: scheme {idx:02d} produced empty output")
        passed.append(f"{idx:02d}")

print("[AudioFlow] all schemes smoke test passed:", ",".join(passed))
PY

export PATH="$PWD/$VENV_DIR/bin:$PATH"

rm -rf build dist "$PAYLOAD_DIR" "$ZIP_NAME"

DATA_ARGS=()
for f in main.raw engine.raw *.rawcode; do
  if [ -f "$f" ]; then
    DATA_ARGS+=(--add-data "$f:.")
  fi
done
if [ -d "assets" ]; then
  DATA_ARGS+=(--add-data "assets:assets")
fi

COMMON_ARGS=(
  --noconfirm
  --clean
  --windowed
  --name "$APP_NAME"
  --add-binary "${FFMPEG_BIN}:tools/macos"
  --add-binary "${FFPROBE_BIN}:tools/macos"
  --add-binary "${SOX_BIN}:tools/macos"
  --add-binary "${SOX_BIN}:tools/sox-14-4-2"
  --hidden-import ctypes
  --hidden-import ctypes.wintypes
  --hidden-import concurrent
  --hidden-import concurrent.futures
  --hidden-import dataclasses
  --hidden-import hashlib
  --hidden-import hmac
  --hidden-import json
  --hidden-import marshal
  --hidden-import platform
  --hidden-import requests
  --hidden-import tempfile
  --hidden-import threading
  --hidden-import typing
  --hidden-import uuid
  --hidden-import zipfile
  --hidden-import PySide6.QtCore
  --hidden-import PySide6.QtGui
  --hidden-import PySide6.QtWidgets
  --hidden-import engine
  --hidden-import license_client
  --hidden-import platform_presets
  --hidden-import raw_loader
  --hidden-import schemes
  --hidden-import security_guard
  --hidden-import settings
  --hidden-import updater
  --collect-all requests
  --collect-all urllib3
  --collect-all certifi
  --collect-all idna
  --collect-all charset_normalizer
  "${DATA_ARGS[@]}"
)

if [ -f "assets/audioflow.icns" ]; then
  "$PYTHON_BIN" -m PyInstaller "${COMMON_ARGS[@]}" --icon "assets/audioflow.icns" main.py
else
  "$PYTHON_BIN" -m PyInstaller "${COMMON_ARGS[@]}" main.py
fi

if [ ! -d "$DIST_APP" ]; then
  echo "ERROR: app build failed."
  exit 1
fi

/usr/libexec/PlistBuddy -c "Set :CFBundleDisplayName ${APP_NAME}" "$DIST_APP/Contents/Info.plist" || true
/usr/libexec/PlistBuddy -c "Set :CFBundleName ${APP_NAME}" "$DIST_APP/Contents/Info.plist" || true
/usr/libexec/PlistBuddy -c "Set :CFBundleIdentifier com.audioflow.studio" "$DIST_APP/Contents/Info.plist" || true
/usr/libexec/PlistBuddy -c "Set :CFBundleVersion ${APP_VERSION}" "$DIST_APP/Contents/Info.plist" || true
/usr/libexec/PlistBuddy -c "Set :CFBundleShortVersionString ${APP_VERSION}" "$DIST_APP/Contents/Info.plist" || true
/usr/libexec/PlistBuddy -c "Add :NSDesktopFolderUsageDescription string AudioFlow Studio 需要读取和保存您选择的桌面音频文件。" "$DIST_APP/Contents/Info.plist" || true
/usr/libexec/PlistBuddy -c "Add :NSDocumentsFolderUsageDescription string AudioFlow Studio 需要读取和保存您选择的文稿音频文件。" "$DIST_APP/Contents/Info.plist" || true
/usr/libexec/PlistBuddy -c "Add :NSDownloadsFolderUsageDescription string AudioFlow Studio 需要读取和保存您选择的下载音频文件。" "$DIST_APP/Contents/Info.plist" || true
/usr/libexec/PlistBuddy -c "Set :NSDesktopFolderUsageDescription AudioFlow Studio 需要读取和保存您选择的桌面音频文件。" "$DIST_APP/Contents/Info.plist" || true
/usr/libexec/PlistBuddy -c "Set :NSDocumentsFolderUsageDescription AudioFlow Studio 需要读取和保存您选择的文稿音频文件。" "$DIST_APP/Contents/Info.plist" || true
/usr/libexec/PlistBuddy -c "Set :NSDownloadsFolderUsageDescription AudioFlow Studio 需要读取和保存您选择的下载音频文件。" "$DIST_APP/Contents/Info.plist" || true

find "$DIST_APP/Contents" -path "*/tools/macos/*" -type f -exec chmod +x {} \;
find "$DIST_APP/Contents" -path "*/tools/sox-14-4-2/*" -type f -exec chmod +x {} \;

codesign --force --deep --sign - "$DIST_APP"
codesign --verify --deep --strict "$DIST_APP"

mkdir -p "$PAYLOAD_DIR"
cp -R "$DIST_APP" "$PAYLOAD_DIR/"
if [ -f "README_Mac.txt" ]; then
  mkdir -p "$PAYLOAD_DIR/${APP_NAME}.app/Contents/Resources"
  cp "README_Mac.txt" "$PAYLOAD_DIR/${APP_NAME}.app/Contents/Resources/README_Mac.txt"
fi

xattr -cr "$PAYLOAD_DIR" || true
(cd "$PAYLOAD_DIR" && ditto -c -k --sequesterRsrc . "../$ZIP_NAME")

_echo_step "SUCCESS: $ZIP_NAME"
