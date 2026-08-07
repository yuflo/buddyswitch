"""Deletion boundary for actor-private runtime files."""

from __future__ import annotations

from pathlib import Path


class ActorPrivateBoundaryError(ValueError):
    """Raised when a request would escape the actor-private file boundary."""


def _path_is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _resolved_existing_path_stays_in_root(path: Path, *, root: Path) -> bool:
    try:
        resolved = path.resolve(strict=True)
    except FileNotFoundError:
        return False
    return _path_is_within(resolved, root.resolve(strict=False))


def delete_private_file(*, root: Path, logical_name: str) -> bool:
    path = root / logical_name
    if path.exists() and path.is_dir():
        raise IsADirectoryError(logical_name)
    if path.exists() and not _resolved_existing_path_stays_in_root(path, root=root):
        raise ActorPrivateBoundaryError(
            "logical_name resolves outside the actor private file root"
        )
    if path.exists() and path.is_file():
        path.unlink()
        return True
    return False
