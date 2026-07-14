#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"

APP_NAME="AudioFlow Studio"
APP_VERSION="3.6.14"
DIST_APP="dist/${APP_NAME}.app"
ZIP_NAME="AudioFlow_Studio_Mac.zip"
PAYLOAD_DIR="release_payload"

echo "[AudioFlow] Building macOS app ${APP_VERSION}..."

if command -v /opt/homebrew/bin/python3 >/dev/null 2>&1; then
  PYTHON_BASE="/opt/homebrew/bin/python3"
elif command -v /usr/local/bin/python3 >/dev/null 2>&1; then
  PYTHON_BASE="/usr/local/bin/python3"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BASE="$(command -v python3)"
else
  echo "ERROR: python3 not found."
  exit 1
fi

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
"$PYTHON_BASE" -m venv "$VENV_DIR"
PYTHON_BIN="$PWD/$VENV_DIR/bin/python"
"$PYTHON_BIN" -m pip install --upgrade pip setuptools wheel
"$PYTHON_BIN" -m pip install -r requirements_client.txt pyinstaller

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
  pyinstaller "${COMMON_ARGS[@]}" --icon "assets/audioflow.icns" main.py
else
  pyinstaller "${COMMON_ARGS[@]}" main.py
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

find "$DIST_APP/Contents" -path "*/tools/macos/*" -type f -exec chmod +x {} \;
find "$DIST_APP/Contents" -path "*/tools/sox-14-4-2/*" -type f -exec chmod +x {} \;

codesign --force --deep --sign - "$DIST_APP"
codesign --verify --deep --strict "$DIST_APP"

mkdir -p "$PAYLOAD_DIR"
cp -R "$DIST_APP" "$PAYLOAD_DIR/"
cp "README_Mac.txt" "$PAYLOAD_DIR/"
if [ -f "Open_AudioFlow.command" ]; then
  chmod +x "Open_AudioFlow.command"
  cp "Open_AudioFlow.command" "$PAYLOAD_DIR/"
  chmod +x "$PAYLOAD_DIR/Open_AudioFlow.command"
fi

xattr -cr "$PAYLOAD_DIR" || true
(cd "$PAYLOAD_DIR" && ditto -c -k --sequesterRsrc . "../$ZIP_NAME")

echo "SUCCESS: $ZIP_NAME"

