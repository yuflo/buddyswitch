"""Market Role-owned result-schema assertions."""

from pathlib import Path

from buddyswitch.roles.market.role import ROLE
from tests.support.role_package_contract import assert_compact_result_schema


def test_market_result_schema_contract() -> None:
    assert_compact_result_schema(
        path=Path(__file__).resolve().parents[2] / "assets" / "result-schema.json",
        role_id=ROLE.id,
        template="brief",
    )
