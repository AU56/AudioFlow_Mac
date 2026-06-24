# -*- coding: utf-8 -*-
from __future__ import annotations

import marshal
import sys
from pathlib import Path


def _resource_path(relative: str) -> Path:
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / relative
    return Path(__file__).resolve().parent / relative


_code = marshal.loads(_resource_path("engine.raw").read_bytes())
exec(_code, globals())
