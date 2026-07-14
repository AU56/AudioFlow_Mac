from __future__ import annotations

import marshal
import sys
from pathlib import Path


def resource_path(relative: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / relative


def exec_raw(relative: str, namespace: dict) -> None:
    code = marshal.loads(resource_path(relative).read_bytes())
    exec(code, namespace)
