"""Test Role-owned descriptor assertions."""

from buddyswitch.roles.test.role import ROLE


def test_test_role_contract() -> None:
    assert ROLE.id == "test"
    assert ROLE.label == "Test"
    assert ROLE.scope == "Validate behavior and report pass/fail/blocked outcomes."
    assert ROLE.skills == (
        "smoke-test",
        "track-tool",
        "artifact-tool",
        "demand-triage",
        "demand-orchestration",
    )
    assert ROLE.artifact_templates == ("proof",)
    assert ROLE.project_path == "projects/app"
    assert ROLE.source_access == "read-only"
    assert ROLE.browser_cockpit == "available"
    assert ROLE.search_api == "available"
