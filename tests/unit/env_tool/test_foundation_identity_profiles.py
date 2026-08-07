"""Direct behavior proof for Foundation identity profile persistence."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import buddyswitch.foundation.identity.profiles as identity_profiles
import buddyswitch.foundation.state.runtime as state_runtime
from tests.support.runtime import RuntimeTestWorkspace


def test_profile_lists_are_empty_then_sorted_and_reads_preserve_normalized_payloads() -> None:
    workspace = RuntimeTestWorkspace()
    try:
        assert identity_profiles.list_actor_identity_profiles() == []
        assert identity_profiles.list_external_profiles() == []

        identity_profiles.save_actor_identity_profile(
            {
                "identity": {"id": "act-zulu", "type": "actor"},
                "role_id": "dev",
                "label": "  Zulu  ",
            }
        )
        identity_profiles.save_actor_identity_profile(
            {
                "identity": {"id": "act-alpha", "type": "actor"},
                "role_id": "pm",
            }
        )
        identity_profiles.save_external_profile(
            {
                "identity": {"id": "ext-zulu", "type": "external"},
                "display_name": "  Zulu Web  ",
            }
        )
        identity_profiles.save_external_profile(
            {"identity": {"id": "ext-alpha", "type": "external"}}
        )

        assert [
            row["identity"]["id"]
            for row in identity_profiles.list_actor_identity_profiles()
        ] == ["act-alpha", "act-zulu"]
        assert [
            row["identity"]["id"]
            for row in identity_profiles.list_external_profiles()
        ] == ["ext-alpha", "ext-zulu"]
        assert identity_profiles.get_actor_identity_profile("act-zulu") == {
            "identity": {"id": "act-zulu", "type": "actor"},
            "role_id": "dev",
            "label": "Zulu",
        }
        assert identity_profiles.get_external_profile("ext-zulu") == {
            "identity": {"id": "ext-zulu", "type": "external"},
            "display_name": "Zulu Web",
        }
        assert identity_profiles.get_actor_identity_profile("act-missing") is None
        assert identity_profiles.get_external_profile("ext-missing") is None
        assert (
            state_runtime.OBJECTS_ROOT
            / "identities"
            / "actors"
            / "act-alpha.json"
        ).is_file()
        assert (
            state_runtime.OBJECTS_ROOT
            / "identities"
            / "externals"
            / "ext-alpha.json"
        ).is_file()
    finally:
        workspace.close()


def test_profile_reads_reject_corrupt_json_and_invalid_payloads() -> None:
    workspace = RuntimeTestWorkspace()
    try:
        actor_root = state_runtime.OBJECTS_ROOT / "identities" / "actors"
        actor_root.mkdir(parents=True)
        (actor_root / "act-corrupt.json").write_text("{bad\n", encoding="utf-8")
        with pytest.raises(ValueError, match="Invalid JSON in"):
            identity_profiles.get_actor_identity_profile("act-corrupt")

        (actor_root / "act-invalid.json").write_text(
            json.dumps(
                {
                    "identity": {"id": "ext-wrong-type", "type": "external"},
                    "role_id": "dev",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="must be an actor identity"):
            identity_profiles.get_actor_identity_profile("act-invalid")
    finally:
        workspace.close()


def test_invalid_profile_save_does_not_write() -> None:
    workspace = RuntimeTestWorkspace()
    try:
        actor_root = state_runtime.OBJECTS_ROOT / "identities" / "actors"
        with pytest.raises(ValueError, match="role_id"):
            identity_profiles.save_actor_identity_profile(
                {
                    "identity": {"id": "act-invalid-save", "type": "actor"},
                    "role_id": "Not Valid",
                }
            )
        assert not actor_root.exists()
    finally:
        workspace.close()


@pytest.mark.parametrize(
    ("save", "payload", "message", "relative_path"),
    (
        (
            identity_profiles.save_actor_identity_profile,
            {
                "identity": {"id": "act-guard-rejected", "type": "actor"},
                "role_id": "dev",
            },
            "runtime writes are blocked",
            Path("identities/actors/act-guard-rejected.json"),
        ),
        (
            identity_profiles.save_external_profile,
            {
                "identity": {"id": "ext-guard-rejected", "type": "external"},
                "display_name": "Rejected",
            },
            "Central IM writes are blocked",
            Path("identities/externals/ext-guard-rejected.json"),
        ),
    ),
)
def test_profile_write_guards_reject_without_writing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    save,
    payload: dict[str, object],
    message: str,
    relative_path: Path,
) -> None:
    shared_root = tmp_path / "shared"
    wrong_state_root = tmp_path / "wrong-state"
    try:
        with monkeypatch.context() as environment:
            environment.setenv("BUDDYSWITCH_SHARED_ROOT", str(shared_root))
            environment.setenv("BUDDYSWITCH_STATE_ROOT", str(wrong_state_root))
            environment.delenv("BUDDYSWITCH_ACTOR_ID", raising=False)
            environment.delenv("BUDDYSWITCH_WORKSPACE_DIR", raising=False)
            environment.delenv("BUDDYSWITCH_RUNTIME_WORKSPACE_ROOT", raising=False)
            state_runtime.refresh_runtime_roots_from_env()

            with pytest.raises(ValueError, match=message):
                save(payload)
            assert not (state_runtime.OBJECTS_ROOT / relative_path).exists()
    finally:
        state_runtime.refresh_runtime_roots_from_env()
