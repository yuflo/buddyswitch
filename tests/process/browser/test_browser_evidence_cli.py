from collections.abc import Iterator
from contextlib import contextmanager
import json
import os
from pathlib import Path

import buddyswitch.foundation.process_runtime.process_identity as process_identity
from buddyswitch.foundation.runtime_broker import lifecycle
from tests.support.processes import ResourceLedger

from tests.integration.browser.market_evidence_harness import *  # noqa: F401,F403


class TestBrowserEvidenceCli(MarketEvidenceHarness):
    _SUCCESS_FIELDS = {
        "ok",
        "tool",
        "action",
        "current_identity",
        "active_role",
        "effect_summary",
        "state_changed",
        "durability",
        "allowed_next_actions",
        "state_changes",
        "created_ids",
        "tool_evidence",
        "mutates_product_state",
    }

    def _broker_paths(
        self,
        *,
        instance_json: Path,
        actor_id: str,
    ) -> lifecycle.BrokerPaths:
        instance_root = instance_json.parent
        runtime_dir = instance_root / "runtime"
        runtime_dir.mkdir(parents=True, exist_ok=True)
        marker_file = runtime_dir / "runtime-broker.socket"
        return lifecycle.BrokerPaths(
            socket_path=lifecycle.resolve_socket_path(
                actor_id,
                instance_root,
                marker_file,
            ),
            pid_file=runtime_dir / "runtime-broker.pid",
            marker_file=marker_file,
            log_file=runtime_dir / "runtime-broker.log",
        )

    @staticmethod
    def _broker_command(
        command: str,
        *,
        paths: lifecycle.BrokerPaths,
        instance_json: Path,
    ) -> list[str]:
        return [
            PYTHON,
            "-m",
            "buddyswitch.application.entrypoints.runtime_broker",
            command,
            "--socket",
            str(paths.socket_path),
            "--pid-file",
            str(paths.pid_file),
            "--marker-file",
            str(paths.marker_file),
            "--log-file",
            str(paths.log_file),
            "--instance-json",
            str(instance_json),
        ]

    def _start_broker(
        self,
        *,
        paths: lifecycle.BrokerPaths,
        instance_json: Path,
    ) -> process_identity.RecordedProcess:
        command = self._broker_command(
            "ensure",
            paths=paths,
            instance_json=instance_json,
        )
        ledger = ResourceLedger.from_environment()
        ledger.register_process_descriptor(
            pid_file=paths.pid_file,
            cleanup_strategy="runtime_broker_stop",
            cleanup_args={
                "socket_path": str(paths.socket_path),
                "pid_file": str(paths.pid_file),
                "marker_file": str(paths.marker_file),
                "log_file": str(paths.log_file),
            },
            command=command,
            owned_paths={
                "socket": paths.socket_path,
                "pid": paths.pid_file,
                "identity": process_identity.identity_file(paths.pid_file),
                "marker": paths.marker_file,
                "log": paths.log_file,
            },
        )
        completed = run_process(
            command,
            cwd=self.runtime_root,
            text=True,
            capture_output=True,
            check=False,
            timeout=10,
        )
        payload = json.loads(completed.stdout)
        self.assertEqual(completed.returncode, 0, msg=completed.stdout + completed.stderr)
        self.assertIs(payload.get("ok"), True, msg=payload)

        recorded = process_identity.read_record(paths.pid_file)
        self.assertIsNotNone(recorded)
        assert recorded is not None
        ledger.reconcile_descriptors()
        self.assertTrue(process_identity.matches(recorded))
        self.assertTrue(paths.socket_path.is_socket())
        self.assertEqual(paths.marker_file.read_text(encoding="utf-8"), str(paths.socket_path))
        self.assertTrue(process_identity.identity_file(paths.pid_file).is_file())
        return recorded

    @contextmanager
    def _running_broker(
        self,
        *,
        instance_json: Path,
        actor_id: str,
    ) -> Iterator[lifecycle.BrokerPaths]:
        paths = self._broker_paths(instance_json=instance_json, actor_id=actor_id)
        recorded: process_identity.RecordedProcess | None = None
        try:
            recorded = self._start_broker(
                paths=paths,
                instance_json=instance_json,
            )
            yield paths
        finally:
            self._stop_broker(
                paths=paths,
                instance_json=instance_json,
                recorded=recorded
                or process_identity.read_record(paths.pid_file),
            )

    def _stop_broker(
        self,
        *,
        paths: lifecycle.BrokerPaths,
        instance_json: Path,
        recorded: process_identity.RecordedProcess | None,
    ) -> None:
        completed = run_process(
            self._broker_command(
                "stop",
                paths=paths,
                instance_json=instance_json,
            ),
            cwd=self.runtime_root,
            text=True,
            capture_output=True,
            check=False,
            timeout=10,
        )
        payload = json.loads(completed.stdout)
        self.assertEqual(completed.returncode, 0, msg=completed.stdout + completed.stderr)
        self.assertIs(payload.get("ok"), True, msg=payload)
        if recorded is not None:
            self.assertFalse(process_identity.is_running(recorded))
        for path in (
            paths.socket_path,
            paths.pid_file,
            process_identity.identity_file(paths.pid_file),
            paths.marker_file,
        ):
            self.assertFalse(path.exists(), msg=path)

    def _run_evidence_command(
        self,
        *arguments: str,
        socket_path: Path,
    ) -> tuple[object, dict[str, object]]:
        environment = dict(os.environ)
        environment["BUDDYSWITCH_RUNTIME_BROKER_SOCKET"] = str(socket_path)
        completed = run_process(
            [
                PYTHON,
                "-m",
                "buddyswitch.application.entrypoints.browser_evidence",
                *arguments,
            ],
            cwd=self.runtime_root,
            env=environment,
            text=True,
            capture_output=True,
            check=False,
            timeout=10,
        )
        payload = json.loads(completed.stdout)
        self.assertIsInstance(payload, dict, msg=completed.stdout)
        return completed, payload

    def _state_snapshot(self) -> dict[str, bytes]:
        return {
            path.relative_to(self.runtime_state_root).as_posix(): path.read_bytes()
            for path in sorted(self.runtime_state_root.rglob("*"))
            if path.is_file()
        }

    def _assert_canonical_success(
        self,
        payload: dict[str, object],
        *,
        action: str,
        actor_id: str,
        artifact_id: str,
        evidence_kind: str,
        mode: str,
        reason: str | None = None,
    ) -> None:
        self.assertEqual(set(payload), self._SUCCESS_FIELDS)
        self.assertIs(payload.get("ok"), True)
        self.assertEqual(payload.get("tool"), "evidence")
        self.assertEqual(payload.get("action"), f"evidence.{action}")
        self.assertEqual(
            payload.get("current_identity"),
            {"id": actor_id, "type": "actor"},
        )
        self.assertEqual(payload.get("active_role"), "market")
        self.assertIs(payload.get("state_changed"), True)
        self.assertEqual(payload.get("durability"), "transient")
        self.assertIs(payload.get("mutates_product_state"), False)
        self.assertNotIn("feedback", payload)

        evidence = payload.get("tool_evidence")
        self.assertIsInstance(evidence, dict, msg=payload)
        assert isinstance(evidence, dict)
        expected_evidence_fields = {
            "token_id",
            "target_type",
            "target_id",
            "issued_by_identity_id",
            "mode",
            "evidence_kind",
            "issued_at",
        }
        if reason is not None:
            expected_evidence_fields.add("reason")
        self.assertEqual(set(evidence), expected_evidence_fields)
        self.assertEqual(evidence.get("target_type"), "artifact")
        self.assertEqual(evidence.get("target_id"), artifact_id)
        self.assertEqual(evidence.get("issued_by_identity_id"), actor_id)
        self.assertEqual(evidence.get("evidence_kind"), evidence_kind)
        self.assertEqual(evidence.get("mode"), mode)
        if reason is not None:
            self.assertEqual(evidence.get("reason"), reason)

        token_id = evidence.get("token_id")
        self.assertIsInstance(token_id, str)
        self.assertEqual(payload.get("created_ids"), [token_id])
        self.assertEqual(
            payload.get("state_changes"),
            [
                {
                    "object_type": "evidence_token",
                    "change": "issued",
                    "token_id": token_id,
                    "target_id": artifact_id,
                }
            ],
        )

    def test_stable_command_returns_canonical_success_for_issue_and_approve(self) -> None:
        actor_label = "act-market-cli-success"
        actor_id = self._runtime_actor_id(role="market", label=actor_label)
        instance_json = self._instance_json(actor_id=actor_label)
        artifact_id = self._seed_market_artifact(actor_id=actor_label)
        state_before = self._state_snapshot()
        with self._running_broker(
            instance_json=instance_json,
            actor_id=actor_id,
        ) as paths:
            cases = (
                (
                    "issue",
                    (
                        "issue",
                        "--target-type",
                        "artifact",
                        "--target-id",
                        artifact_id,
                    ),
                    "issue_browser",
                    "browser",
                    "browser-cockpit-preflight",
                    None,
                ),
                (
                    "approve-downgrade",
                    (
                        "approve-downgrade",
                        "--target-type",
                        "artifact",
                        "--target-id",
                        artifact_id,
                        "--reason",
                        "Browser unavailable; user approved fallback.",
                    ),
                    "approve_downgrade",
                    "downgrade",
                    "downgrade-approved",
                    "Browser unavailable; user approved fallback.",
                ),
            )
            for label, arguments, action, evidence_kind, mode, reason in cases:
                with self.subTest(command=label):
                    completed, payload = self._run_evidence_command(
                        *arguments,
                        socket_path=paths.socket_path,
                    )
                    self.assertEqual(
                        completed.returncode,
                        0,
                        msg=completed.stdout + completed.stderr,
                    )
                    self._assert_canonical_success(
                        payload,
                        action=action,
                        actor_id=actor_id,
                        artifact_id=artifact_id,
                        evidence_kind=evidence_kind,
                        mode=mode,
                        reason=reason,
                    )
        self.assertEqual(self._state_snapshot(), state_before)

    def test_stable_command_maps_rejection_and_unavailable_broker(self) -> None:
        actor_label = "act-market-cli-failure"
        actor_id = self._runtime_actor_id(role="market", label=actor_label)
        instance_json = self._instance_json(actor_id=actor_label)
        artifact_id = self._seed_market_artifact(actor_id=actor_label)
        state_before = self._state_snapshot()
        with self._running_broker(
            instance_json=instance_json,
            actor_id=actor_id,
        ) as paths:
            missing_artifact_id = "art-market-cli-missing"
            rejected, rejection = self._run_evidence_command(
                "issue",
                "--target-type",
                "artifact",
                "--target-id",
                missing_artifact_id,
                socket_path=paths.socket_path,
            )
            self.assertEqual(rejected.returncode, 1, msg=rejected.stdout + rejected.stderr)
            self.assertIs(rejection.get("ok"), False)
            error = rejection.get("error")
            self.assertIsInstance(error, dict, msg=rejection)
            assert isinstance(error, dict)
            self.assertEqual(error.get("code"), "E_EVIDENCE_PAYLOAD")
            self.assertEqual(
                error.get("message"),
                f"artifact not found: {missing_artifact_id}",
            )
            self.assertIs(rejection.get("state_changed"), False)
            self.assertEqual(rejection.get("durability"), "none")
            self.assertNotIn("tool_evidence", rejection)

        unavailable, unavailable_payload = self._run_evidence_command(
            "issue",
            "--target-type",
            "artifact",
            "--target-id",
            artifact_id,
            socket_path=paths.socket_path,
        )
        self.assertEqual(
            unavailable.returncode,
            1,
            msg=unavailable.stdout + unavailable.stderr,
        )
        self.assertIs(unavailable_payload.get("ok"), False)
        unavailable_error = unavailable_payload.get("error")
        self.assertIsInstance(unavailable_error, dict, msg=unavailable_payload)
        assert isinstance(unavailable_error, dict)
        self.assertEqual(
            unavailable_error.get("code"),
            "E_RUNTIME_BROKER_UNAVAILABLE",
        )
        self.assertIs(unavailable_payload.get("state_changed"), False)
        self.assertNotIn("tool_evidence", unavailable_payload)
        self.assertEqual(self._state_snapshot(), state_before)

    def test_browser_evidence_cli_target_type_is_artifact_only(self) -> None:
        help_result = run_process(
            [PYTHON, "-m", "buddyswitch.application.entrypoints.browser_evidence", "issue", "--help"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(help_result.returncode, 0, msg=help_result.stderr)
        self.assertIn("artifact", help_result.stdout)
        self.assertNotIn("memory", help_result.stdout)

        rejected = run_process(
            [
                PYTHON,
                "-m",
                "buddyswitch.application.entrypoints.browser_evidence",
                "issue",
                "--target-type",
                "memory",
                "--target-id",
                "mem-old",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(rejected.returncode, 2, msg=rejected.stdout + rejected.stderr)
        self.assertIn("invalid choice", rejected.stderr)
