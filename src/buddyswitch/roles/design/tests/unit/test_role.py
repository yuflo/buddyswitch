"""Design Role-owned descriptor assertions."""

from buddyswitch.roles.design.role import ROLE


def test_design_role_contract() -> None:
    assert ROLE.id == "design"
    assert ROLE.label == "Design"
    assert ROLE.scope == "Shape UI/UX prototype direction and design artifact outcomes."
    assert ROLE.skills == (
        "shape-prototype",
        "track-tool",
        "artifact-tool",
        "demand-triage",
        "demand-orchestration",
    )
    assert ROLE.artifact_templates == ("design", "brief")
    assert ROLE.project_path == "projects/app"
    assert ROLE.source_access == "read-only"
    assert ROLE.browser_cockpit == "available"
    assert ROLE.search_api == "available"
