"""Stable product-neutral contracts for Web host contributions."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from buddyswitch.env.domain.identity import ActorIdentityProfile


@dataclass(frozen=True)
class ActorConsoleSectionRegistration:
    name: str
    project: Callable[[ActorIdentityProfile], Mapping[str, object]]


class WebRoute(Protocol):
    def prepare(self) -> None: ...

    def handle(
        self,
        method: str,
        path: str,
        body: bytes,
        headers: Mapping[str, str] | None,
    ) -> tuple[int, dict[str, Any]]: ...


class WebWorker(Protocol):
    def start(self) -> None: ...

    def stop(self) -> None: ...


@dataclass(frozen=True)
class WebHostAccess:
    list_instances: Callable[[], list[dict[str, Any]]]


@dataclass(frozen=True)
class WebRouteRegistration:
    name: str
    prefix: str
    factory: Callable[[WebHostAccess], WebRoute]


@dataclass(frozen=True)
class WebWorkerRegistration:
    name: str
    factory: Callable[[str], WebWorker]
