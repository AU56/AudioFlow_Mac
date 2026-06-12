# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import sys


SUSPICIOUS_ENV_NAMES = {
    "PYINSTALLER_RESET_ENVIRONMENT",
    "PYTHONINSPECT",
}


def runtime_guard_ok() -> tuple[bool, str]:
    if sys.gettrace() is not None:
        return False, "检测到调试环境，软件已停止运行。"
    for name in SUSPICIOUS_ENV_NAMES:
        if os.getenv(name):
            return False, "运行环境异常，请重新打开软件。"
    return True, ""
