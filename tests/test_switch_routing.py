#!/usr/bin/env python3
"""Parser and router checks for BuddySwitch switch invocation handling."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import codex_router  # noqa: E402
import parse_switch  # noqa: E402


class ParseSwitchTests(unittest.TestCase):
    def test_parser_returns_structured_invocation(self) -> None:
        payload = parse_switch.parse_switch("switch market : quick scan")

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["intent"], "switch")
        self.assertEqual(payload["buddy"], "market")
        self.assertEqual(payload["task"], "quick scan")
        self.assertEqual(payload["invocation"]["normalized_text"], "switch market: quick scan")

    def test_parser_accepts_minor_spacing_variation(self) -> None:
        payload = parse_switch.parse_switch("switch market:quick scan")

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["task"], "quick scan")
        self.assertEqual(payload["normalized_text"], "switch market: quick scan")

    def test_parser_rejects_non_switch_input(self) -> None:
        payload = parse_switch.parse_switch("market: quick scan")

        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "E_INVALID_SYNTAX")

    def test_parser_rejects_unknown_buddy(self) -> None:
        payload = parse_switch.parse_switch("switch unknown: quick scan")

        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "E_UNKNOWN_AGENT")

    def test_parser_rejects_empty_task(self) -> None:
        payload = parse_switch.parse_switch("switch market:")

        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "E_EMPTY_TASK")


class RouterTests(unittest.TestCase):
    def test_router_exposes_invocation_and_profile(self) -> None:
        payload = codex_router.route_switch("switch market : quick scan")

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["invocation"]["intent"], "switch")
        self.assertEqual(payload["invocation"]["buddy"], "market")
        self.assertEqual(payload["invocation"]["normalized_text"], "switch market: quick scan")
        self.assertEqual(payload["profile"]["id"], "market")
        self.assertEqual(payload["profile"]["authority"]["permission_scope"], "manual_debug_apis")
        self.assertIn("research-scan", payload["profile"]["authority"]["routing_skills"])
        self.assertTrue(payload["profile"]["skills"])


if __name__ == "__main__":
    unittest.main()
