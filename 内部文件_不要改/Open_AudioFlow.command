#!/bin/bash
set -u

cd "$(dirname "$0")"

APP="./AudioFlow Studio.app"
if [ ! -d "$APP" ] && [ -d "/Applications/AudioFlow Studio.app" ]; then
  APP="/Applications/AudioFlow Studio.app"
fi

echo "AudioFlow Studio Mac 打开修复"
echo

if [ ! -d "$APP" ]; then
  echo "没有找到 AudioFlow Studio.app。"
  echo "请把本文件和 AudioFlow Studio 放在同一个文件夹，或先把 AudioFlow Studio 拖到“应用程序”。"
  echo
  read -r -p "按回车键关闭窗口..."
  exit 1
fi

echo "正在处理首次打开权限..."
xattr -dr com.apple.quarantine "$APP" 2>/dev/null || true
chmod +x "$APP/Contents/MacOS/AudioFlow Studio" 2>/dev/null || true

echo "正在打开 AudioFlow Studio..."
open "$APP"

echo
echo "如果仍然弹出拦截窗口，请进入“系统设置 - 隐私与安全性”，找到 AudioFlow Studio，选择“仍要打开”。"
read -r -p "按回车键关闭窗口..."
