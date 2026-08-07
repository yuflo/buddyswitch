"""Direct behavior proof for the canonical Foundation state owner."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

import buddyswitch.foundation.state.runtime as state_runtime


def test_runtime_root_precedence_and_refresh(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    shared_root = tmp_path / "shared"
    source_home = tmp_path / "source-home"
    explicit_state = tmp_path / "explicit-state"
    workspace = tmp_path / "workspace"
    fallback_workspace = tmp_path / "fallback-workspace"
    payload_workspace = tmp_path / "payload-workspace"

    try:
        with monkeypatch.context() as environment:
            environment.setenv("BUDDYSWITCH_SHARED_ROOT", str(shared_root))
            environment.setenv("BUDDYSWITCH_SOURCE_HOME", str(source_home))
            environment.setenv("BUDDYSWITCH_STATE_ROOT", str(explicit_state))
            environment.setenv("BUDDYSWITCH_WORKSPACE_DIR", str(workspace))
            environment.setenv(
                "BUDDYSWITCH_RUNTIME_WORKSPACE_ROOT",
                str(fallback_workspace),
            )
            state_runtime.refresh_runtime_roots_from_env()

            assert state_runtime.ROOT == shared_root.resolve(strict=False)
            assert state_runtime.STATE_ROOT == explicit_state.resolve(strict=False)
            assert state_runtime.OBJECTS_ROOT == explicit_state.resolve(strict=False) / "buddyswitch" / "objects"
            assert state_runtime.LOCAL_ROOT == explicit_state.resolve(strict=False) / "buddyswitch" / "local"
            assert state_runtime.runtime_workspace_root() == workspace.resolve(strict=False)
            assert state_runtime.runtime_workspace_root(
                {"workspace_dir": str(payload_workspace)}
            ) == payload_workspace.resolve(strict=False)
            assert state_runtime.actor_private_dir() == workspace.resolve(strict=False) / "private"

            environment.delenv("BUDDYSWITCH_SHARED_ROOT")
            environment.delenv("BUDDYSWITCH_STATE_ROOT")
            environment.delenv("BUDDYSWITCH_WORKSPACE_DIR")
            state_runtime.refresh_runtime_roots_from_env()

            expected_root = source_home.resolve(strict=False) / ".codex-buddyswitch"
            assert state_runtime.ROOT == expected_root
            assert state_runtime.STATE_ROOT == expected_root / "state"
            assert state_runtime.runtime_workspace_root() == fallback_workspace.resolve(strict=False)
    finally:
        state_runtime.refresh_runtime_roots_from_env()


def test_runtime_and_central_write_guards_allow_only_bound_roots(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    shared_root = tmp_path / "shared"
    state_root = shared_root / "state"
    runtime_workspace = tmp_path / "runtime-workspace"
    runtime_workspace.mkdir()
    (runtime_workspace / "AGENTS.md").write_text(
        state_runtime.RUNTIME_WORKSPACE_AGENTS_HEADER + "\n",
        encoding="utf-8",
    )
    source_checkout = tmp_path / "source-checkout"
    source_checkout.mkdir()

    try:
        with monkeypatch.context() as environment:
            environment.setenv("BUDDYSWITCH_SHARED_ROOT", str(shared_root))
            environment.setenv("BUDDYSWITCH_STATE_ROOT", str(state_root))
            environment.setenv("BUDDYSWITCH_ACTOR_ID", "act-test-guard")
            state_runtime.refresh_runtime_roots_from_env()

            state_runtime.require_runtime_workspace_write_root(runtime_workspace)
            state_runtime.require_runtime_workspace_write_root(source_checkout)
            state_runtime.require_central_im_write_root(source_checkout)

            environment.setenv("BUDDYSWITCH_STATE_ROOT", str(tmp_path / "wrong-state"))
            state_runtime.refresh_runtime_roots_from_env()
            with pytest.raises(ValueError, match="runtime writes are blocked"):
                state_runtime.require_runtime_workspace_write_root(source_checkout)
            with pytest.raises(ValueError, match="Central IM writes are blocked"):
                state_runtime.require_central_im_write_root(source_checkout)

            state_runtime.require_runtime_workspace_write_root(runtime_workspace)
            state_runtime.require_central_im_write_root(runtime_workspace)
    finally:
        state_runtime.refresh_runtime_roots_from_env()


def test_json_object_reads_report_missing_malformed_and_non_object(tmp_path: Path) -> None:
    missing = tmp_path / "missing.json"
    with pytest.raises(FileNotFoundError):
        state_runtime.read_json_object(missing)

    malformed = tmp_path / "malformed.json"
    malformed.write_text("{not-json\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid JSON in"):
        state_runtime.read_json_object(malformed)

    non_object = tmp_path / "array.json"
    non_object.write_text("[]\n", encoding="utf-8")
    with pytest.raises(ValueError, match="must contain a JSON object"):
        state_runtime.read_json_object(non_object)


def test_atomic_json_write_replaces_complete_object_and_leaves_no_temp_file(tmp_path: Path) -> None:
    target = tmp_path / "objects" / "record.json"
    target.parent.mkdir()
    target.write_text('{"old": true}\n', encoding="utf-8")

    state_runtime.write_json_object(target, {"new": {"value": 2}})

    assert json.loads(target.read_text(encoding="utf-8")) == {"new": {"value": 2}}
    assert list(target.parent.iterdir()) == [target]


def test_atomic_json_write_cleans_temp_file_when_replace_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    target = tmp_path / "objects" / "record.json"

    def fail_replace(_source: os.PathLike[str], _target: os.PathLike[str]) -> None:
        raise OSError("replace failed")

    monkeypatch.setattr(state_runtime.os, "replace", fail_replace)
    with pytest.raises(OSError, match="replace failed"):
        state_runtime.write_json_object(target, {"value": 1})

    assert target.parent.is_dir()
    assert list(target.parent.iterdir()) == []
