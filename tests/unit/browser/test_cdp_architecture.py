from __future__ import annotations

import unittest

from tests.support.paths import REPO_ROOT


ROOT = REPO_ROOT
SESSION_PATH = ROOT / "scripts" / "env" / ("cdp_browser_" + "session.py")
LIFECYCLE_PATH = ROOT / "scripts" / "env" / "cdp_browser_lifecycle.py"
LEGACY_CURRENT_TARGET_FIELD = "current_" + "target_id"
LEGACY_PAGE_TARGET_MAP_FIELD = "page_id_to_" + "target_id"


class TestCdpArchitecture(unittest.TestCase):
    def test_actor_page_cdp_open_close_helpers_are_removed_or_readiness_scoped(self) -> None:
        self.assertFalse(SESSION_PATH.exists(), "actor page CDP session helper should not remain as a live module")
        lifecycle_source = LIFECYCLE_PATH.read_text(encoding="utf-8")
        forbidden = (
            "def create_background_page_" + "target",
            "def close_page_" + "target",
            "Target." + "closeTarget",
            "target_idle_expiry_after_" + "due_at",
            "forget_page_idle_" + "target",
            LEGACY_CURRENT_TARGET_FIELD,
            LEGACY_PAGE_TARGET_MAP_FIELD,
        )
        for token in forbidden:
            with self.subTest(token=token):
                self.assertNotIn(token, lifecycle_source)

        manager_source = (ROOT / "tools" / "launcher" / "browser_runtime_manager.py").read_text(encoding="utf-8")
        self.assertIn("cdp_background_page", manager_source)
        self.assertNotIn("create_background_page_" + "target", manager_source)
