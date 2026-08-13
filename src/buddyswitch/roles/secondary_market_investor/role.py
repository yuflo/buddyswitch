from buddyswitch.foundation.role_host import RoleDescriptor


ROLE = RoleDescriptor(
    id="secondary-market-investor",
    label="Secondary Market Investor",
    scope="Evaluate long-horizon public-market bets without trading execution.",
    skills=(
        "secondary-market-investor-analysis",
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
