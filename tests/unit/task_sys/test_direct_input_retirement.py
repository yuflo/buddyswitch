"""Forward-only guards for direct Actor input outside Task Sys."""

from __future__ import annotations

import unittest

from tests.support.paths import REPO_ROOT


def _source(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


class TaskSysDirectInputRetirementTests(unittest.TestCase):
    def test_task_sys_ingress_exposes_only_controlled_inbound_helpers(self) -> None:
        source = _source("tools/launcher/task_sys_ingress.py")

        self.assertIn("def ingest_im_message(", source)
        self.assertIn("def ingest_track_comment(", source)
        for retired in (
            "def ingest_user_input(",
            '"user.input"',
            'add_parser("user-input")',
            "import argparse",
            "def main(",
            'if __name__ == "__main__"',
        ):
            with self.subTest(retired=retired):
                self.assertNotIn(retired, source)

    def test_task_sys_runtime_has_no_direct_input_prompt_branch(self) -> None:
        source = _source("tools/launcher/task_sys_runtime.py")

        self.assertNotIn('source_type == "user.input"', source)
        self.assertNotIn("For a user.input source:", source)


if __name__ == "__main__":
    unittest.main()
