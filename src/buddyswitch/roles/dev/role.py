from buddyswitch.foundation.role_host import RoleDescriptor


ROLE = RoleDescriptor(
    id="dev",
    label="Dev",
    scope="Implement approved scope in project code.",
    skills=(
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
    ),
    artifact_templates=("brief", "note"),
    project_path="projects/app",
    source_access="write",
    browser_cockpit="available",
    search_api="available",
)
