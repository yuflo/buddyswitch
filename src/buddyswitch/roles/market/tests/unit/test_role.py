"""Market Role-owned descriptor assertions."""

from buddyswitch.roles.market.role import ROLE


def test_market_role_contract() -> None:
    assert ROLE.id == "market"
    assert ROLE.label == "Market"
    assert ROLE.scope == "Research demand, users, and competition."
    assert ROLE.skills == (
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
    )
    assert ROLE.artifact_templates == ("brief",)
    assert ROLE.project_path == "projects/app"
    assert ROLE.source_access == "read-only"
    assert ROLE.browser_cockpit == "required"
    assert ROLE.search_api == "user-approved-only"
