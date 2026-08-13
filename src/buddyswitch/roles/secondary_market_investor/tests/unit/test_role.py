"""Role-local proof for the directory-only extension package."""

from buddyswitch.roles.secondary_market_investor.role import ROLE


def test_secondary_market_investor_is_read_only_and_non_executing() -> None:
    assert ROLE.id == "secondary-market-investor"
    assert ROLE.label == "Secondary Market Investor"
    assert ROLE.scope == (
        "Evaluate long-horizon public-market bets without trading execution."
    )
    assert ROLE.source_access == "read-only"
    assert ROLE.browser_cockpit == "available"
    assert ROLE.project_path == "projects/app"
    assert ROLE.artifact_templates == ("brief", "decision", "note")
    assert ROLE.search_api == "available"
    assert ROLE.skills == (
        "secondary-market-investor-analysis",
        "track-tool",
        "artifact-tool",
        "demand-triage",
        "demand-orchestration",
    )
