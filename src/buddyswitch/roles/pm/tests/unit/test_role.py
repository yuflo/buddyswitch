"""PM Role-owned descriptor assertions."""

from buddyswitch.roles.pm.role import ROLE


def test_pm_role_contract() -> None:
    assert ROLE.id == "pm"
    assert ROLE.label == "PM"
    assert ROLE.scope == "Own product iteration and track progression."
    assert ROLE.skills == (
        "read-product-context",
        "synthesize-cross-functional-inputs",
        "frame-product-direction",
        "define-scope",
        "write-requirements",
        "write-acceptance-criteria",
        "make-product-decision",
        "decide-from-proof",
        "triage-track",
        "sequence-product-work",
        "track-tool",
        "artifact-tool",
        "demand-triage",
        "demand-orchestration",
    )
    assert ROLE.artifact_templates == ("brief", "decision", "note")
    assert ROLE.project_path == "projects/app"
    assert ROLE.source_access == "read-only"
    assert ROLE.browser_cockpit == "available"
    assert ROLE.search_api == "available"
