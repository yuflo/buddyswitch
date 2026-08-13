"""PM Role-owned result-schema assertions."""

from pathlib import Path

from buddyswitch.roles.pm.role import ROLE
from tests.support import output_schema
from tests.support.role_package_contract import (
    assert_compact_result_schema,
    load_result_schema,
    sample_payload,
)


SCHEMA_PATH = Path(__file__).resolve().parents[2] / "assets" / "result-schema.json"


def test_pm_result_schema_contract() -> None:
    assert_compact_result_schema(
        path=SCHEMA_PATH,
        role_id=ROLE.id,
        template="brief",
    )


def test_pm_result_schema_rejects_track_advance_effect() -> None:
    schema = load_result_schema(SCHEMA_PATH)
    payload = sample_payload(role_id=ROLE.id, template="brief")
    payload["state_effects"] = {
        "track": {"action": "advance", "track_id": "track-onboarding"}
    }
    errors = output_schema.validate_output_payload(payload, schema)
    assert any("enum" in line or "advance" in line for line in errors)


def test_pm_result_schema_accepts_track_update_without_next_actor_fields() -> None:
    schema = load_result_schema(SCHEMA_PATH)
    payload = sample_payload(role_id=ROLE.id, template="brief")
    payload["state_effects"] = {
        "track": {
            "action": "update",
            "track_id": "track-onboarding",
            "title": "New title",
            "status": "active",
            "summary": "summary",
        }
    }
    assert output_schema.validate_output_payload(payload, schema) == []
