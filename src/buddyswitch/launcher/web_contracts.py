"""Stable product-neutral contracts for Web host contributions."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from buddyswitch.foundation.identity.model import ActorIdentityProfile


_HOST_EXACT_PATHS = (
    "/api/health",
    "/api/roles",
    "/api/instances",
    "/api/actors",
)
_HOST_PREFIXES = (
    "/api/instances/",
    "/api/actors/",
    "/api/operations/",
)


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
class HttpError(Exception):
    status: int
    code: str
    message: str
    details: dict[str, Any] | None = None


@dataclass(frozen=True)
class WebRouteRegistration:
    name: str
    factory: Callable[[WebHostAccess], WebRoute]
    exact_paths: tuple[str, ...] = ()
    prefixes: tuple[str, ...] = ()


def _matchers_overlap(
    left_exact: tuple[str, ...],
    left_prefixes: tuple[str, ...],
    right_exact: tuple[str, ...],
    right_prefixes: tuple[str, ...],
) -> bool:
    if set(left_exact) & set(right_exact):
        return True
    if any(path.startswith(prefix) for path in left_exact for prefix in right_prefixes):
        return True
    if any(path.startswith(prefix) for path in right_exact for prefix in left_prefixes):
        return True
    return any(
        left.startswith(right) or right.startswith(left)
        for left in left_prefixes
        for right in right_prefixes
    )


def _matchers_overlap_within_registration(
    exact_paths: tuple[str, ...],
    prefixes: tuple[str, ...],
) -> bool:
    if any(path.startswith(prefix) for path in exact_paths for prefix in prefixes):
        return True
    return any(
        left.startswith(right) or right.startswith(left)
        for index, left in enumerate(prefixes)
        for right in prefixes[index + 1 :]
    )


def _validate_exact_path(path: object, *, route_name: str) -> str:
    if (
        not isinstance(path, str)
        or not path.startswith("/api/")
        or path.endswith("/")
        or "?" in path
        or "#" in path
    ):
        raise ValueError(
            f"Web route exact path for '{route_name}' must be a query-free "
            "canonical '/api/...' path"
        )
    return path


def _validate_prefix(prefix: object, *, route_name: str) -> str:
    if (
        not isinstance(prefix, str)
        or not prefix.startswith("/api/")
        or not prefix.endswith("/")
        or "?" in prefix
        or "#" in prefix
    ):
        raise ValueError(
            f"Web route prefix for '{route_name}' must be a query-free "
            "canonical '/api/.../' prefix"
        )
    return prefix


def validate_web_route_registrations(
    registrations: tuple[WebRouteRegistration, ...],
) -> tuple[WebRouteRegistration, ...]:
    if not isinstance(registrations, tuple):
        raise ValueError("Web route registrations must be a tuple")

    names: set[str] = set()
    accepted: list[WebRouteRegistration] = []
    for registration in registrations:
        if not isinstance(registration, WebRouteRegistration):
            raise ValueError(
                "Web route contribution must be WebRouteRegistration"
            )
        if not isinstance(registration.name, str) or not registration.name.strip():
            raise ValueError("Web route name must be a non-empty string")
        name = registration.name.strip()
        if name in names:
            raise ValueError(f"duplicate Web route name: {name}")
        if not callable(registration.factory):
            raise ValueError(f"Web route factory for '{name}' must be callable")
        if not isinstance(registration.exact_paths, tuple):
            raise ValueError(f"Web route exact paths for '{name}' must be a tuple")
        if not isinstance(registration.prefixes, tuple):
            raise ValueError(f"Web route prefixes for '{name}' must be a tuple")
        if not registration.exact_paths and not registration.prefixes:
            raise ValueError(f"Web route '{name}' must declare at least one matcher")

        exact_paths = tuple(
            _validate_exact_path(path, route_name=name)
            for path in registration.exact_paths
        )
        prefixes = tuple(
            _validate_prefix(prefix, route_name=name)
            for prefix in registration.prefixes
        )
        if len(exact_paths) != len(set(exact_paths)):
            raise ValueError(f"duplicate Web route exact path for '{name}'")
        if len(prefixes) != len(set(prefixes)):
            raise ValueError(f"duplicate Web route prefix for '{name}'")
        if _matchers_overlap_within_registration(exact_paths, prefixes):
            raise ValueError(
                f"overlapping Web route matchers for '{name}'"
            )
        if _matchers_overlap(
            exact_paths,
            prefixes,
            _HOST_EXACT_PATHS,
            _HOST_PREFIXES,
        ):
            raise ValueError(f"Web route '{name}' overlaps a reserved host route")
        for existing in accepted:
            if _matchers_overlap(
                exact_paths,
                prefixes,
                existing.exact_paths,
                existing.prefixes,
            ):
                raise ValueError(
                    f"Web route '{name}' overlaps contributed route "
                    f"'{existing.name}'"
                )
        names.add(name)
        accepted.append(registration)
    return tuple(accepted)


@dataclass(frozen=True)
class WebWorkerRegistration:
    name: str
    factory: Callable[[str], WebWorker]
