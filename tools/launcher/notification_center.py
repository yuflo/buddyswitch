"""Source-native inbound registration for daemon notify infrastructure."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class InboundSourceRegistration:
    event_type: str
    payload_contract: Mapping[str, Any]
    handler_factory: Callable[[], Any]
    owner_module: str


def _non_empty_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _factory_name(factory: Callable[[], Any]) -> str:
    name = getattr(factory, "__name__", None)
    if isinstance(name, str) and name:
        return name
    return type(factory).__name__


def _normalize_registration(registration: Any) -> InboundSourceRegistration:
    event_type = _non_empty_text(getattr(registration, "event_type", None), "event_type")
    payload_contract = getattr(registration, "payload_contract", None)
    if not isinstance(payload_contract, Mapping):
        raise ValueError("payload_contract must be an object")
    handler_factory = getattr(registration, "handler_factory", None)
    if not callable(handler_factory):
        raise ValueError("handler_factory must be callable")
    owner_module = _non_empty_text(getattr(registration, "owner_module", None), "owner_module")
    return InboundSourceRegistration(
        event_type=event_type,
        payload_contract=dict(payload_contract),
        handler_factory=handler_factory,
        owner_module=owner_module,
    )


def normalized_registrations(registrations: list[Any] | tuple[Any, ...]) -> list[InboundSourceRegistration]:
    normalized: list[InboundSourceRegistration] = []
    seen_event_types: set[str] = set()
    for registration in registrations:
        item = _normalize_registration(registration)
        if item.event_type in seen_event_types:
            raise ValueError(f"duplicate event_type registration: {item.event_type}")
        seen_event_types.add(item.event_type)
        normalized.append(item)
    return normalized


def _require_unified_handler(handler: Any, *, event_type: str) -> Any:
    if not callable(getattr(handler, "handles", None)) or not callable(getattr(handler, "handle", None)):
        raise ValueError(f"handler for event_type {event_type} must expose handles() and handle()")
    return handler


def handlers_from_registrations(registrations: list[Any] | tuple[Any, ...]) -> list[Any]:
    handlers: list[Any] = []
    for registration in normalized_registrations(registrations):
        handler = registration.handler_factory()
        handlers.append(_require_unified_handler(handler, event_type=registration.event_type))
    return handlers


def subscriptions_from_registrations(registrations: list[Any] | tuple[Any, ...]) -> list[str]:
    return [registration.event_type for registration in normalized_registrations(registrations)]


def registration_records(registrations: list[Any] | tuple[Any, ...]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for registration in normalized_registrations(registrations):
        records.append(
            {
                "event_type": registration.event_type,
                "payload_contract": dict(registration.payload_contract),
                "owner_module": registration.owner_module,
                "handler_name": _factory_name(registration.handler_factory),
            }
        )
    return records


if __name__ == "__main__":
    raise SystemExit("notification_center is not a standalone command")
