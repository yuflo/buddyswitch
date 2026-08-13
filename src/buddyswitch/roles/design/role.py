from buddyswitch.foundation.role_host import RoleDescriptor


ROLE = RoleDescriptor(
    id="design",
    label="Design",
    scope="Shape UI/UX prototype direction and design artifact outcomes.",
    skills=(
        "shape-prototype",
        "track-tool",
        "artifact-tool",
        "demand-triage",
        "demand-orchestration",
    ),
    artifact_templates=("design", "brief"),
    project_path="projects/app",
    source_access="read-only",
    browser_cockpit="available",
    search_api="available",
)
