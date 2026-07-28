from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = REPO_ROOT / "src" / "buddyswitch"
SCRIPTS_ROOT = PACKAGE_ROOT
LAUNCHER_ROOT = PACKAGE_ROOT / "launcher"
