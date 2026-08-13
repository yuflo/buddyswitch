"""Generic assertions used by Role-owned result-schema tests."""

from __future__ import annotations

from pathlib import Path

from tests.support import output_schema


COMMON_REQUIRED_COMMIT_KEYS = {"execution_summary"}
COMMON_OPTIONAL_COMMIT_KEYS = {
    "working_notes",
    "artifacts",
    "state_effects",
    "contributors",
    "tool_evidence",
}


def load_result_schema(path: Path) -> dict[str, object]:
    return output_schema.load_output_schema(
        path.relative_to(output_schema.ROOT).as_posix()
    )


def sample_payload(*, role_id: str, template: str) -> dict[str, object]:
    return {
        "execution_summary": f"{role_id} result summary",
        "working_notes": ["Focused contract result."],
        "artifacts": [
            {
                "template": template,
                "title": f"{role_id} artifact",
                "summary": f"{role_id} artifact summary",
                "body": "x",
            }
        ],
    }


def assert_compact_result_schema(
    *,
    path: Path,
    role_id: str,
    template: str,
) -> None:
    schema = load_result_schema(path)
    properties = schema.get("properties")
    assert schema.get("required") == ["execution_summary"]
    assert schema.get("additionalProperties") is False
    assert isinstance(properties, dict)
    assert COMMON_REQUIRED_COMMIT_KEYS | COMMON_OPTIONAL_COMMIT_KEYS <= set(
        properties
    )
    assert "handoff" not in properties

    payload = sample_payload(role_id=role_id, template=template)
    assert output_schema.validate_output_payload(payload, schema) == []
    payload["handoff"] = {
        "next_role": "another-role",
        "reason": "retired",
        "context": "retired",
    }
    assert "$: unsupported property 'handoff'" in (
        output_schema.validate_output_payload(payload, schema)
    )
