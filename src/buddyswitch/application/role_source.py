"""Application-owned projections of the current Role source."""

from __future__ import annotations

from pathlib import Path

from buddyswitch.runtime_support import env_manifest


def load_valid_role_ids(manifest_path: Path) -> frozenset[str]:
    """Project the validated current manifest to cleanup's narrow Role fact."""

    manifest = env_manifest.load_manifest(manifest_path)
    return frozenset(
        role["id"]
        for role in manifest["roles"]
        if isinstance(role, dict) and isinstance(role.get("id"), str)
    )
