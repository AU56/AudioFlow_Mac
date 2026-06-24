#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"

APP_NAME="AudioFlow Studio"
DIST_APP="dist/${APP_NAME}.app"
ZIP_NAME="AudioFlow_Studio_Mac.zip"

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
"$PYTHON_BIN" -m venv "$VENV_DIR"
PYTHON_BIN="$PWD/$VENV_DIR/bin/python"
"$PYTHON_BIN" -m pip install --upgrade pip setuptools wheel
"$PYTHON_BIN" -m pip install -r requirements_client.txt pyinstaller

export PATH="$PWD/$VENV_DIR/bin:$(dirname "$PYTHON_BIN"):$PATH"

rm -rf build dist "$ZIP_NAME"

if [ -f "assets/audioflow.icns" ]; then
  pyinstaller --noconfirm --clean --windowed \
    --name "$APP_NAME" \
    --icon "assets/audioflow.icns" \
    --add-binary "${FFMPEG_BIN}:tools/macos" \
    --add-binary "${FFPROBE_BIN}:tools/macos" \
    --add-binary "${SOX_BIN}:tools/macos" \
    --add-data "assets/audioflow.ico:assets" \
    --add-data "schemes.py:." \
    --add-data "settings.py:." \
    main.py
else
  pyinstaller --noconfirm --clean --windowed \
    --name "$APP_NAME" \
    --add-binary "${FFMPEG_BIN}:tools/macos" \
    --add-binary "${FFPROBE_BIN}:tools/macos" \
    --add-data "assets/audioflow.ico:assets" \
    --add-binary "${SOX_BIN}:tools/macos" \
    --add-data "schemes.py:." \
    --add-data "settings.py:." \
    main.py
fi

if [ ! -d "$DIST_APP" ]; then
  echo "ERROR: app build failed."
  exit 1
fi

PAYLOAD_DIR="release_payload"
rm -rf "$PAYLOAD_DIR"
mkdir -p "$PAYLOAD_DIR"
cp -R "$DIST_APP" "$PAYLOAD_DIR/"
if [ -f "使用说明.txt" ]; then
  cp "使用说明.txt" "$PAYLOAD_DIR/"
fi

(cd "$PAYLOAD_DIR" && ditto -c -k --sequesterRsrc . "../$ZIP_NAME")
echo "SUCCESS: $ZIP_NAME"
echo "Put $ZIP_NAME into backend data/updates with version.txt."
