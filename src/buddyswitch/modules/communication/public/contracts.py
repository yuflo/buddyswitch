"""Communication Public input-port contracts."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol


class DemandEnqueue(Protocol):
    def __call__(
        self,
        state: Any,
        *,
        source_key: str,
        description: str,
        detail: str,
        source_refs: list[Mapping[str, Any]],
    ) -> dict[str, Any]: ...
