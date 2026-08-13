"""Dev Role-owned descriptor assertions."""

from buddyswitch.roles.dev.role import ROLE


def test_dev_role_contract() -> None:
    assert ROLE.id == "dev"
    assert ROLE.label == "Dev"
    assert ROLE.scope == "Implement approved scope in project code."
    assert ROLE.skills == (
        "enter-dev-workspace",
        "read-implementation-context",
        "handle-empty-source-root",
        "plan-thin-slice-implementation",
        "implement-scoped-change",
        "debug-regression",
        "select-local-verification",
        "request-dev-code-review",
        "handle-review-feedback",
        "finish-dev-change",
        "pressure-test-dev-skill",
        "parallelize-independent-dev-work",
        "write-implementation-report",
        "prepare-review-readiness",
        "track-tool",
        "artifact-tool",
        "demand-triage",
        "demand-orchestration",
    )
    assert ROLE.artifact_templates == ("brief", "note")
    assert ROLE.project_path == "projects/app"
    assert ROLE.source_access == "write"
    assert ROLE.browser_cockpit == "available"
    assert ROLE.search_api == "available"
