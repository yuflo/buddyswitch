from buddyswitch.foundation.role_host import RoleDescriptor


ROLE = RoleDescriptor(
    id="market",
    label="Market",
    scope="Research demand, users, and competition.",
    skills=(
        "market-source-seed-atlas",
        "market-search-operator-builder",
        "source-quality-rater",
        "data-triangulator",
        "hallucination-guard",
        "weak-signal-scout",
        "workaround-miner",
        "market-tension-finder",
        "customer-voice-mining",
        "segment-map-builder",
        "icp-scorer",
        "positioning-message-map",
        "growth-bottleneck-diagnoser",
        "channel-strategy-mapper",
        "experiment-design-reviewer",
        "track-tool",
        "artifact-tool",
        "demand-triage",
        "demand-orchestration",
    ),
    artifact_templates=("brief",),
    project_path="projects/app",
    source_access="read-only",
    browser_cockpit="required",
    search_api="user-approved-only",
)
