# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "AudioFlow Studio"
APP_VERSION = "3.6.4"

PUBLIC_LICENSE_SERVER_URL = os.getenv("AUDIOFLOW_LICENSE_SERVER", "http://122.51.121.200:13706")
LOCAL_LICENSE_SERVER_URL = "http://127.0.0.1:5000"
BUILTIN_LICENSE_SERVER_URL = PUBLIC_LICENSE_SERVER_URL
LICENSE_SERVER_CANDIDATES = [PUBLIC_LICENSE_SERVER_URL]
UPDATE_INFO_URL = os.getenv(
    "AUDIOFLOW_UPDATE_INFO_URL",
    PUBLIC_LICENSE_SERVER_URL.rstrip("/") + "/api/app/version",
)

CONTACT_TEXT = "问题咨询：Zhwdh141319\n备注：AI原创"
VERIFY_SECRET = os.getenv("AUDIOFLOW_VERIFY_SECRET", "change-this-signing-secret")
SUPPORTED_AUDIO_EXTS = {".mp3", ".wav"}
DEFAULT_OUTPUT_DIR = str(Path.home() / "Desktop" / "AudioFlow_Output")


def app_data_dir() -> Path:
    base = os.getenv("LOCALAPPDATA") or os.getenv("APPDATA") or str(Path.home())
    path = Path(base) / os.getenv("AUDIOFLOW_APP_DATA_NAME", "AudioFlowStudio")
    path.mkdir(parents=True, exist_ok=True)
    return path


def resource_path(relative: str) -> Path:
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / relative
    return Path(__file__).resolve().parent / relative
