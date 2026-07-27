"""Real installed-Codex proof for the native Goal contract BuddySwitch consumes."""

from __future__ import annotations

import unittest

import app_server

from tests.system.goal_mode.support import (
    RealCodexGoalHarness,
    ResponseSpec,
    completed_response,
    request_has_tool,
    update_goal_response,
)


class NativeGoalContractSystemTests(unittest.TestCase):
    def test_active_goal_continues_then_native_tool_completes_and_persists(self) -> None:
        harness = RealCodexGoalHarness(
            [
                completed_response("materialize", "Persistent thread materialized."),
                completed_response("goal-first-turn", "Work remains after this turn."),
                update_goal_response("goal-complete-call", "complete"),
                completed_response("goal-final-message", "Goal completion recorded."),
            ]
        )
        self.addCleanup(harness.close)
        self.assertIn("goals", harness.feature_output())
        self.assertIn("stable", harness.feature_output())
        self.assertIn("true", harness.feature_output())

        client = harness.client()
        self.addCleanup(client.close)
        thread_id = harness.materialize_thread(client)
        self.assertEqual(
            harness.thread_start_result["modelProvider"],
            "mock_provider",
            msg=harness.thread_start_result,
        )
        self.assertEqual(
            harness.materialize_completion["turn"]["status"],
            "completed",
            msg=harness.materialize_completion,
        )
        active_notification = client.request_with_notification(
            "thread/goal/set",
            {
                "threadId": thread_id,
                "objective": "Continue across turns and mark this Goal complete.",
                "status": "active",
            },
            notification_method="thread/goal/updated",
            notification_thread_id=thread_id,
        )
        self.assertEqual(active_notification["goal"]["status"], "active")

        requests = harness.responses.wait_for_request_count(3)
        self.assertEqual(len(requests), 3)
        self.assertTrue(
            request_has_tool(requests[2], "update_goal"),
            msg=requests[2]["body"],
        )
        completed_notification = harness.wait_for_notification(
            client,
            "thread/goal/updated",
            thread_id=thread_id,
            goal_status="complete",
        )
        self.assertEqual(completed_notification["goal"]["objective"], active_notification["goal"]["objective"])
        harness.responses.wait_for_request_count(4)

        client.close()
        reloaded = app_server.goal_get(harness.socket_path, thread_id)
        self.assertEqual(reloaded["goal"]["status"], "complete")
        self.assertEqual(reloaded["goal"]["threadId"], thread_id)

        cleared = app_server.goal_clear(harness.socket_path, thread_id)
        self.assertEqual(cleared, {"cleared": True})
        self.assertEqual(app_server.goal_get(harness.socket_path, thread_id), {"goal": None})

        report = harness.close()
        self.assertEqual(report.residuals, [])
        self.assertFalse(harness.root.exists())

    def test_goal_turn_error_becomes_queryable_blocked_state(self) -> None:
        harness = RealCodexGoalHarness(
            [
                completed_response("materialize-blocked", "Persistent thread materialized."),
                ResponseSpec.server_error("forced native Goal turn failure"),
            ]
        )
        self.addCleanup(harness.close)
        client = harness.client()
        self.addCleanup(client.close)
        thread_id = harness.materialize_thread(client)
        self.assertEqual(
            harness.thread_start_result["modelProvider"],
            "mock_provider",
            msg=harness.thread_start_result,
        )
        self.assertEqual(
            harness.materialize_completion["turn"]["status"],
            "completed",
            msg=harness.materialize_completion,
        )
        active_notification = client.request_with_notification(
            "thread/goal/set",
            {
                "threadId": thread_id,
                "objective": "Expose a stopped Goal after the model turn fails.",
                "status": "active",
            },
            notification_method="thread/goal/updated",
            notification_thread_id=thread_id,
        )
        self.assertEqual(active_notification["goal"]["status"], "active")
        harness.responses.wait_for_request_count(2)

        blocked = harness.wait_for_goal_status(thread_id, "blocked")
        self.assertEqual(blocked["threadId"], thread_id)
        self.assertEqual(blocked["objective"], active_notification["goal"]["objective"])

        client.close()
        self.assertEqual(
            app_server.goal_get(harness.socket_path, thread_id)["goal"]["status"],
            "blocked",
        )
        self.assertEqual(
            app_server.goal_clear(harness.socket_path, thread_id),
            {"cleared": True},
        )
        report = harness.close()
        self.assertEqual(report.residuals, [])
        self.assertFalse(harness.root.exists())
