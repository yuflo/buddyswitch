from tests.integration.browser.market_evidence_harness import *  # noqa: F401,F403


class TestMarketEvidence(MarketEvidenceHarness):
    def test_market_evidence_requires_artifact_target(self) -> None:
        instance_json = self._instance_json(actor_id="act-market-target")
        _, artifact_id = self._seed_market_task_and_artifact(actor_id="act-market-target")

        missing_target = self._dispatch(
            instance_json=instance_json,
            actor_id="act-market-target",
            role="market",
            tool="evidence",
            action="issue_browser",
            args={"target_type": "artifact"},
        )
        self.assertFalse(missing_target.get("ok"), msg=missing_target)
        self.assertEqual((missing_target.get("error") or {}).get("code"), "E_EVIDENCE_PAYLOAD")

        wrong_type = self._dispatch(
            instance_json=instance_json,
            actor_id="act-market-target",
            role="market",
            tool="evidence",
            action="issue_browser",
            args={"target_type": "run", "target_id": "run-old"},
        )
        self.assertFalse(wrong_type.get("ok"), msg=wrong_type)
        self.assertEqual((wrong_type.get("error") or {}).get("code"), "E_EVIDENCE_TARGET_TYPE")

        ok_issue = self._dispatch(
            instance_json=instance_json,
            actor_id="act-market-target",
            role="market",
            tool="evidence",
            action="issue_browser",
            args={"target_type": "artifact", "target_id": artifact_id},
        )
        self.assertTrue(ok_issue.get("ok"), msg=ok_issue)
    def test_market_artifact_write_with_browser_evidence_is_runless(self) -> None:
        actor_id = "act-market-write"
        instance_json = self._instance_json(actor_id=actor_id)
        _, artifact_id = self._seed_market_task_and_artifact(actor_id=actor_id)

        issued = self._dispatch(
            instance_json=instance_json,
            actor_id=actor_id,
            role="market",
            tool="evidence",
            action="issue_browser",
            args={"target_type": "artifact", "target_id": artifact_id},
        )
        self.assertTrue(issued.get("ok"), msg=issued)
        token = issued.get("tool_evidence")
        self.assertIsInstance(token, dict, msg=issued)
        assert isinstance(token, dict)

        created = self._dispatch(
            instance_json=instance_json,
            actor_id=actor_id,
            role="market",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-market-evidence-r2",
                "title": "Market update",
                "summary": "runless evidence ref",
                "template": "brief",
                "body": "updated",
                "supersedes_artifact_id": artifact_id,
                "source_refs": [
                    {"type": "artifact", "id": artifact_id},
                    {"type": "note", "label": f"evidence:{token.get('token_id')}"},
                ],
            },
        )
        self.assertTrue(created.get("ok"), msg=created)
        self.assertTrue(created.get("state_changed"), msg=created)
        self.assertFalse(self._state_path("buddyswitch/content/runs").exists())
        self.assertFalse(self._runtime_path("runs/raw").exists())
    def test_approved_downgrade_records_reason_on_target_token(self) -> None:
        instance_json = self._instance_json(actor_id="act-market-downgrade")
        _, artifact_id = self._seed_market_task_and_artifact(actor_id="act-market-downgrade")

        approved = self._dispatch(
            instance_json=instance_json,
            actor_id="act-market-downgrade",
            role="market",
            tool="evidence",
            action="approve_downgrade",
            args={
                "target_type": "artifact",
                "target_id": artifact_id,
                "reason": "Browser unavailable; user approved fallback.",
            },
        )
        self.assertTrue(approved.get("ok"), msg=approved)
        evidence = approved.get("tool_evidence")
        self.assertIsInstance(evidence, dict, msg=approved)
        assert isinstance(evidence, dict)
        self.assertEqual(evidence.get("target_type"), "artifact")
        self.assertEqual(evidence.get("target_id"), artifact_id)
        self.assertEqual(evidence.get("reason"), "Browser unavailable; user approved fallback.")
        self.assertNotIn("run_id", evidence)
