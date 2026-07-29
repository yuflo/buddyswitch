"""Atomic per-actor Demand aggregate repository."""

from __future__ import annotations

import copy
import fcntl
from pathlib import Path
from typing import Any, Callable, Mapping

from buddyswitch.env.repos import runtime_files


SCHEMA_VERSION = 5
_ACTOR_TARGET_FIELDS = {"actor_id", "role_id"}
_AGGREGATE_FIELDS = {
    "schema_version",
    "actor_target",
    "demands",
    "demand_pool_revision",
    "ingress_receipts",
}


def normalize_actor_target(actor_target: Mapping[str, Any]) -> dict[str, str]:
    if not isinstance(actor_target, Mapping):
        raise ValueError("actor_target must be an object")
    if set(actor_target) != _ACTOR_TARGET_FIELDS:
        raise ValueError("actor_target must contain exactly actor_id and role_id")
    return {
        "actor_id": runtime_files.require_id(
            actor_target.get("actor_id"),
            "actor_target.actor_id",
        ),
        "role_id": runtime_files.require_id(
            actor_target.get("role_id"),
            "actor_target.role_id",
        ),
    }


def _actor_state_path(actor_target: Mapping[str, Any]) -> Path:
    return (
        runtime_files.OBJECTS_ROOT
        / "demand-sys"
        / "actors"
        / f"{actor_target['actor_id']}-{actor_target['role_id']}.json"
    )


def actor_state_path(actor_target: Mapping[str, Any]) -> Path:
    return _actor_state_path(normalize_actor_target(actor_target))


def _actor_lock_path(actor_target: Mapping[str, Any]) -> Path:
    return (
        runtime_files.LOCAL_ROOT
        / "locks"
        / "demand-sys"
        / f"{actor_target['actor_id']}-{actor_target['role_id']}.lock"
    )


def actor_lock_path(actor_target: Mapping[str, Any]) -> Path:
    return _actor_lock_path(normalize_actor_target(actor_target))


def _empty_actor_state(actor_target: Mapping[str, str]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "actor_target": dict(actor_target),
        "demands": {},
        "demand_pool_revision": 0,
        "ingress_receipts": {},
    }


def _validate_actor_state(
    payload: Mapping[str, Any],
    expected_actor_target: Mapping[str, str],
) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("Demand actor aggregate must be an object")
    if set(payload) != _AGGREGATE_FIELDS:
        raise ValueError(
            "Demand actor aggregate must contain exactly schema_version, actor_target, "
            "demands, demand_pool_revision, and ingress_receipts"
        )
    schema_version = payload.get("schema_version")
    if type(schema_version) is not int or schema_version != SCHEMA_VERSION:
        raise ValueError(f"Demand actor aggregate schema_version must be {SCHEMA_VERSION}")
    actor_target = normalize_actor_target(payload.get("actor_target"))
    if actor_target != dict(expected_actor_target):
        raise ValueError("Demand actor aggregate actor_target does not match its repository path")
    demands_by_id = payload.get("demands")
    if not isinstance(demands_by_id, dict):
        raise ValueError("Demand actor aggregate demands must be an object")
    for demand_id, demand in demands_by_id.items():
        runtime_files.require_id(demand_id, "demand id")
        if not isinstance(demand, dict):
            raise ValueError(f"Demand actor aggregate demands.{demand_id} must be an object")
    demand_pool_revision = payload.get("demand_pool_revision")
    if type(demand_pool_revision) is not int or demand_pool_revision < 0:
        raise ValueError("Demand actor aggregate demand_pool_revision must be a non-negative integer")
    ingress_receipts = payload.get("ingress_receipts")
    if not isinstance(ingress_receipts, dict):
        raise ValueError("Demand actor aggregate ingress_receipts must be an object")
    for source_key, receipt in ingress_receipts.items():
        if not isinstance(source_key, str) or not source_key.strip():
            raise ValueError(
                "Demand actor aggregate ingress receipt keys must be non-empty strings"
            )
        if not isinstance(receipt, dict):
            raise ValueError(
                f"Demand actor aggregate ingress_receipts.{source_key} must be an object"
            )
    return {
        "schema_version": SCHEMA_VERSION,
        "actor_target": actor_target,
        "demands": copy.deepcopy(demands_by_id),
        "demand_pool_revision": demand_pool_revision,
        "ingress_receipts": copy.deepcopy(ingress_receipts),
    }


def _load_actor_state(
    path: Path,
    actor_target: Mapping[str, str],
) -> dict[str, Any]:
    if not path.exists():
        return _empty_actor_state(actor_target)
    return _validate_actor_state(
        runtime_files.read_json_object(path),
        actor_target,
    )


def load_actor_state(actor_target: Mapping[str, Any]) -> dict[str, Any]:
    """Return a validated deep copy or a fresh empty aggregate."""

    normalized_target = normalize_actor_target(actor_target)
    return _load_actor_state(_actor_state_path(normalized_target), normalized_target)


def transact_actor_state(
    actor_target: Mapping[str, Any],
    mutator: Callable[[dict[str, Any]], tuple[bool, Any]],
) -> Any:
    """Serialize one mutation and atomically replace the aggregate when changed."""

    if not callable(mutator):
        raise ValueError("mutator must be callable")
    normalized_target = normalize_actor_target(actor_target)
    state_path = _actor_state_path(normalized_target)
    lock_path = _actor_lock_path(normalized_target)
    runtime_files.require_runtime_workspace_write_root()
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    with lock_path.open("a+", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            state = _load_actor_state(state_path, normalized_target)
            mutation = mutator(state)
            if (
                not isinstance(mutation, tuple)
                or len(mutation) != 2
                or type(mutation[0]) is not bool
            ):
                raise ValueError("mutator must return a (bool, result) tuple")
            changed, result = mutation
            if changed:
                normalized_state = _validate_actor_state(state, normalized_target)
                runtime_files.write_json_object(state_path, normalized_state)
            return result
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
