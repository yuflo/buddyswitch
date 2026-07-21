"""Forward-only guards for retired external Task ingress."""

from __future__ import annotations

import unittest

from tests.support.paths import REPO_ROOT


def _source(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


class TaskSysExternalIngressRetirementTests(unittest.TestCase):
    def test_external_task_ingress_module_and_domain_action_are_absent(self) -> None:
        self.assertFalse((REPO_ROOT / "tools/launcher/task_sys_ingress.py").exists())
        domain = _source("scripts/env/domain/task_sys.py")
        self.assertNotIn("def ingest(", domain)
        self.assertNotIn("def _normalize_source(", domain)
        self.assertNotIn("def _normalize_context(", domain)
        self.assertNotIn("def _reject_unsupported_ingest_fields(", domain)
        self.assertNotIn("def _reject_non_task_sys_ingest_source(", domain)

    def test_track_and_im_handlers_have_no_task_creation_dependency(self) -> None:
        for relative_path in (
            "tools/launcher/track_comment_added_handler.py",
            "tools/launcher/im_wake_handler.py",
        ):
            with self.subTest(relative_path=relative_path):
                source = _source(relative_path)
                self.assertNotIn("task_sys_ingress", source)
                self.assertNotIn("task_sys_daemon_adapter", source)
                self.assertNotIn("task_sys.ingest", source)

    def test_task_runtime_has_no_retired_source_specific_branches(self) -> None:
        source = _source("tools/launcher/task_sys_runtime.py")
        for retired in (
            'source_type == "user.input"',
            'source_type == "im.message.created"',
            'source_type == "track.comment.added"',
            "For a user.input source:",
            "For an IM source message:",
            "[TRACK COMMENT TRIAGE]",
        ):
            with self.subTest(retired=retired):
                self.assertNotIn(retired, source)

    def test_context_does_not_reconstruct_track_relationships_from_task_source(self) -> None:
        source = _source("scripts/env/tools/context/_impl.py")
        self.assertNotIn('source_ref.get("track_id")', source)
        self.assertNotIn("visible_track_ids=visible_track_ids", source.split("visible_tasks =", 1)[1].split(")", 1)[0])


if __name__ == "__main__":
    unittest.main()
