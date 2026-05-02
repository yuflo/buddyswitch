#!/usr/bin/env python3
"""Debug parser/router checks isolated from product runtime paths."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


class DebugParserIsolationTests(unittest.TestCase):
    def test_red_debug_parser_tools_live_under_scripts_debug(self) -> None:
        parse_path = ROOT / "scripts" / "debug" / "parse_switch.py"
        router_path = ROOT / "scripts" / "debug" / "codex_router.py"

        self.assertTrue(parse_path.exists(), msg=f"missing debug parser at {parse_path}")
        self.assertTrue(router_path.exists(), msg=f"missing debug router at {router_path}")

    def test_red_debug_parser_and_router_modules_are_importable_from_debug_path(self) -> None:
        parse_path = ROOT / "scripts" / "debug" / "parse_switch.py"
        router_path = ROOT / "scripts" / "debug" / "codex_router.py"

        parse_spec = importlib.util.spec_from_file_location("debug.parse_switch", parse_path)
        router_spec = importlib.util.spec_from_file_location("debug.codex_router", router_path)

        self.assertIsNotNone(parse_spec)
        self.assertIsNotNone(router_spec)
        self.assertIsNotNone(parse_spec.loader if parse_spec else None)
        self.assertIsNotNone(router_spec.loader if router_spec else None)

    def test_red_product_runtime_does_not_import_debug_parser_router(self) -> None:
        runtime_sources = (
            (ROOT / "scripts" / "switch_runtime.py").read_text(encoding="utf-8"),
            (ROOT / "scripts" / "runtime_kernel" / "resolve.py").read_text(encoding="utf-8"),
            (ROOT / "scripts" / "runtime_kernel" / "persist.py").read_text(encoding="utf-8"),
        )
        combined = "\n".join(runtime_sources)

        self.assertNotIn("from parse_switch import", combined)
        self.assertNotIn("import parse_switch", combined)
        self.assertNotIn("import codex_router", combined)
        self.assertNotIn("parse_switch(", combined)
        self.assertNotIn("codex_router.", combined)


if __name__ == "__main__":
    unittest.main()
