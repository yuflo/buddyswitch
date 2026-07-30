"""Stable product-neutral contracts for Web host contributions."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from buddyswitch.env.domain.identity import ActorIdentityProfile


@dataclass(frozen=True)
class ActorConsoleSectionRegistration:
    name: str
    project: Callable[[ActorIdentityProfile], Mapping[str, object]]
