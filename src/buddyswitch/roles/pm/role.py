from buddyswitch.foundation.role_host import RoleDescriptor


ROLE = RoleDescriptor(
    id="pm",
    label="PM",
    scope="Own product iteration and track progression.",
    skills=(
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
    ),
    artifact_templates=("brief", "decision", "note"),
    project_path="projects/app",
    source_access="read-only",
    browser_cockpit="available",
    search_api="available",
)
