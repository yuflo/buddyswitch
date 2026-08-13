from buddyswitch.foundation.role_host import RoleDescriptor


ROLE = RoleDescriptor(
    id="test",
    label="Test",
    scope="Validate behavior and report pass/fail/blocked outcomes.",
    skills=(
        "smoke-test",
        "track-tool",
        "artifact-tool",
        "demand-triage",
        "demand-orchestration",
    ),
    artifact_templates=("proof",),
    project_path="projects/app",
    source_access="read-only",
    browser_cockpit="available",
    search_api="available",
)
