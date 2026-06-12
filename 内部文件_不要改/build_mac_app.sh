#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"

APP_NAME="AudioFlow Studio"
DIST_APP="dist/${APP_NAME}.app"
ZIP_NAME="AudioFlow_Studio_Mac.zip"
ICON_ARGS=()

echo "[AudioFlow] Building macOS app..."

if command -v /opt/homebrew/bin/python3 >/dev/null 2>&1; then
  PYTHON_BIN="/opt/homebrew/bin/python3"
elif command -v /usr/local/bin/python3 >/dev/null 2>&1; then
  PYTHON_BIN="/usr/local/bin/python3"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="$(command -v python3)"
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

if [ -f "assets/audioflow.icns" ]; then
  ICON_ARGS=(--icon "assets/audioflow.icns")
fi

VENV_DIR=".venv-build-macos"
"$PYTHON_BIN" -m venv "$VENV_DIR"
PYTHON_BIN="$PWD/$VENV_DIR/bin/python"
"$PYTHON_BIN" -m pip install --upgrade pip setuptools wheel
"$PYTHON_BIN" -m pip install -r requirements_client.txt pyinstaller

export PATH="$PWD/$VENV_DIR/bin:$(dirname "$PYTHON_BIN"):$PATH"

rm -rf build dist "$ZIP_NAME"

pyinstaller --noconfirm --clean --windowed \
  --name "$APP_NAME" \
  "${ICON_ARGS[@]}" \
  --add-binary "${FFMPEG_BIN}:tools/macos" \
  --add-binary "${FFPROBE_BIN}:tools/macos" \
  --add-binary "${SOX_BIN}:tools/macos" \
  --add-data "assets/audioflow.ico:assets" \
  --add-data "schemes.py:." \
  --add-data "settings.py:." \
  main.py

if [ ! -d "$DIST_APP" ]; then
  echo "ERROR: app build failed."
  exit 1
fi

ditto -c -k --sequesterRsrc --keepParent "$DIST_APP" "$ZIP_NAME"
echo "SUCCESS: $ZIP_NAME"
echo "Put $ZIP_NAME into backend data/updates with version.txt."
