"""Test access to the Python path already resolved by BuddySwitch."""

from __future__ import annotations

import os
from pathlib import Path


def configured_python() -> str:
    raw = os.environ.get("BUDDYSWITCH_PYTHON")
    if not raw:
        raise RuntimeError(
            "BUDDYSWITCH_PYTHON is not initialized; source tools/launcher/env.sh and call "
            "buddyswitch_env_init before running tests."
        )
    path = Path(raw)
    if not path.is_absolute():
        raise RuntimeError("BUDDYSWITCH_PYTHON must be an absolute path")
    return str(path)


PYTHON = configured_python()


def executable_python_source(source: str) -> str:
    return f"#!{PYTHON}\n{source.lstrip()}"
