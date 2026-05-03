#!/usr/bin/env python3
"""Contract tests for console next-step state derivation behavior."""

from __future__ import annotations

import json
import os
import subprocess
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONSOLE_APP = ROOT / "framework" / "console" / "app.js"


class ConsoleAppContractTests(unittest.TestCase):
    def _derive_track_next_step_state(self, workspace_payload: dict, track_payload: dict) -> dict:
        script = textwrap.dedent(
            """
            const fs = require("fs");
            const vm = require("vm");

            function makeElement(tagName = "div") {
              return {
                tagName,
                children: [],
                className: "",
                textContent: "",
                type: "",
                disabled: false,
                dataset: {},
                append(...nodes) { this.children.push(...nodes); },
                appendChild(node) { this.children.push(node); return node; },
                replaceChildren(...nodes) { this.children = [...nodes]; },
                addEventListener() {},
                removeEventListener() {},
                setAttribute() {},
                classList: {
                  add() {},
                  remove() {},
                  toggle() {},
                  contains() { return false; },
                },
              };
            }

            const elements = new Map();
            const document = {
              getElementById(id) {
                if (!elements.has(id)) {
                  elements.set(id, makeElement("div"));
                }
                return elements.get(id);
              },
              createElement(tag) {
                return makeElement(tag);
              },
            };

            const context = {
              console,
              window: {
                location: { protocol: "file:" },
                prompt() {},
              },
              document,
              navigator: {
                clipboard: {
                  writeText: async () => {},
                },
              },
              setTimeout() {},
              clearTimeout() {},
            };
            context.globalThis = context;
            vm.createContext(context);

            const source = fs.readFileSync(process.env.CONSOLE_APP_PATH, "utf8");
            vm.runInContext(
              source + "\\nglobalThis.__consoleContract = { applyWorkspaceData, deriveNextStepStateForTrack };\\n",
              context,
            );

            const workspacePayload = JSON.parse(process.env.WORKSPACE_PAYLOAD_JSON);
            const trackPayload = JSON.parse(process.env.TRACK_PAYLOAD_JSON);
            context.__consoleContract.applyWorkspaceData(workspacePayload);
            const result = context.__consoleContract.deriveNextStepStateForTrack(trackPayload);
            process.stdout.write(JSON.stringify(result));
            """
        )

        env = os.environ.copy()
        env.update(
            {
                "CONSOLE_APP_PATH": str(CONSOLE_APP),
                "WORKSPACE_PAYLOAD_JSON": json.dumps(workspace_payload),
                "TRACK_PAYLOAD_JSON": json.dumps(track_payload),
            }
        )
        completed = subprocess.run(
            ["node", "-e", script],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(
            completed.returncode,
            0,
            msg=f"node harness failed\nstdout:\n{completed.stdout}\nstderr:\n{completed.stderr}",
        )
        return json.loads(completed.stdout)

    def _derive_task_next_step_state(self, workspace_payload: dict, task_payload: dict) -> dict:
        script = textwrap.dedent(
            """
            const fs = require("fs");
            const vm = require("vm");

            function makeElement(tagName = "div") {
              return {
                tagName,
                children: [],
                className: "",
                textContent: "",
                type: "",
                disabled: false,
                dataset: {},
                append(...nodes) { this.children.push(...nodes); },
                appendChild(node) { this.children.push(node); return node; },
                replaceChildren(...nodes) { this.children = [...nodes]; },
                addEventListener() {},
                removeEventListener() {},
                setAttribute() {},
                classList: {
                  add() {},
                  remove() {},
                  toggle() {},
                  contains() { return false; },
                },
              };
            }

            const elements = new Map();
            const document = {
              getElementById(id) {
                if (!elements.has(id)) {
                  elements.set(id, makeElement("div"));
                }
                return elements.get(id);
              },
              createElement(tag) {
                return makeElement(tag);
              },
            };

            const context = {
              console,
              window: {
                location: { protocol: "file:" },
                prompt() {},
              },
              document,
              navigator: {
                clipboard: {
                  writeText: async () => {},
                },
              },
              setTimeout() {},
              clearTimeout() {},
            };
            context.globalThis = context;
            vm.createContext(context);

            const source = fs.readFileSync(process.env.CONSOLE_APP_PATH, "utf8");
            vm.runInContext(
              source + "\\nglobalThis.__consoleContract = { applyWorkspaceData, deriveNextStepStateForTask };\\n",
              context,
            );

            const workspacePayload = JSON.parse(process.env.WORKSPACE_PAYLOAD_JSON);
            const taskPayload = JSON.parse(process.env.TASK_PAYLOAD_JSON);
            context.__consoleContract.applyWorkspaceData(workspacePayload);
            const result = context.__consoleContract.deriveNextStepStateForTask(taskPayload);
            process.stdout.write(JSON.stringify(result));
            """
        )

        env = os.environ.copy()
        env.update(
            {
                "CONSOLE_APP_PATH": str(CONSOLE_APP),
                "WORKSPACE_PAYLOAD_JSON": json.dumps(workspace_payload),
                "TASK_PAYLOAD_JSON": json.dumps(task_payload),
            }
        )
        completed = subprocess.run(
            ["node", "-e", script],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(
            completed.returncode,
            0,
            msg=f"node harness failed\nstdout:\n{completed.stdout}\nstderr:\n{completed.stderr}",
        )
        return json.loads(completed.stdout)

    def test_track_next_step_state_reports_buddy_state_without_switch_commands(self) -> None:
        track_payload = {
            "id": "track-alpha",
            "current_buddy": "dev",
            "next_buddy": "pm",
            "task_ids": ["task-dev"],
            "tasks": [
                {
                    "id": "task-dev",
                    "buddy": "dev",
                    "artifact_ids": ["artifact-dev"],
                    "run_ids": ["run-dev-1"],
                }
            ],
        }
        workspace_payload = {
            "tracks": [track_payload],
            "tasks": track_payload["tasks"],
            "artifacts": [
                {
                    "id": "artifact-dev",
                    "buddy": "dev",
                }
            ],
            "run_audits": [
                {
                    "run_id": "run-dev-1",
                    "track_id": "track-alpha",
                    "task_id": "task-dev",
                    "next_state": {
                        "task_id": "task-dev",
                        "track_id": "track-alpha",
                        "current_buddy": "dev",
                        "next_buddy": "market",
                        "mode": "handoff",
                    },
                    "receipt_paths": {
                        "run": "buddyswitch/content/runs/run-dev-1.json",
                        "task": "buddyswitch/objects/tasks/task-dev.json",
                        "track": "buddyswitch/objects/tracks/track-alpha.json",
                        "artifacts": ["buddyswitch/objects/artifacts/artifact-dev.json"],
                    },
                }
            ],
        }

        next_step = self._derive_track_next_step_state(workspace_payload, track_payload)
        self.assertEqual(next_step["trackId"], "track-alpha")
        self.assertEqual(next_step["currentBuddy"], "dev")
        self.assertEqual(next_step["nextBuddy"], "market")
        self.assertEqual(next_step["recommendedBuddy"], "market")
        self.assertEqual(next_step["mode"], "handoff")
        self.assertNotIn("switch", json.dumps(next_step).lower())

    def test_task_next_step_state_reports_current_and_recommended_buddy_without_switch_commands(self) -> None:
        task_payload = {
            "id": "task-dev",
            "buddy": "dev",
            "artifact_ids": ["artifact-dev"],
            "run_ids": ["run-dev-1"],
        }
        workspace_payload = {
            "tracks": [],
            "tasks": [task_payload],
            "artifacts": [
                {
                    "id": "artifact-dev",
                    "buddy": "dev",
                }
            ],
            "run_audits": [
                {
                    "run_id": "run-dev-1",
                    "task_id": "task-dev",
                    "next_state": {
                        "task_id": "task-dev",
                        "track_id": None,
                        "current_buddy": "dev",
                        "next_buddy": "test",
                        "mode": "handoff",
                    },
                    "receipt_paths": {
                        "run": "buddyswitch/content/runs/run-dev-1.json",
                        "task": "buddyswitch/objects/tasks/task-dev.json",
                        "track": None,
                        "artifacts": ["buddyswitch/objects/artifacts/artifact-dev.json"],
                    },
                }
            ],
        }

        next_step = self._derive_task_next_step_state(workspace_payload, task_payload)
        self.assertEqual(next_step["taskId"], "task-dev")
        self.assertEqual(next_step["currentBuddy"], "dev")
        self.assertEqual(next_step["recommendedBuddy"], "test")
        self.assertEqual(next_step["mode"], "handoff")
        self.assertNotIn("switch", json.dumps(next_step).lower())

    def test_standalone_task_without_run_audit_uses_task_buddy_not_synthetic_pm_switch(self) -> None:
        task_payload = {
            "id": "task-dev-zero",
            "buddy": "dev",
            "artifact_ids": [],
            "run_ids": [],
        }
        workspace_payload = {
            "tracks": [],
            "tasks": [task_payload],
            "artifacts": [],
            "run_audits": [],
        }

        next_step = self._derive_task_next_step_state(workspace_payload, task_payload)
        self.assertEqual(next_step["taskId"], "task-dev-zero")
        self.assertEqual(next_step["currentBuddy"], "dev")
        self.assertEqual(next_step["recommendedBuddy"], "dev")
        self.assertEqual(next_step["mode"], "continue_current_task")
        self.assertNotIn("switch", json.dumps(next_step).lower())
        self.assertNotIn("pm", str(next_step.get("summary", "")).lower())
        self.assertNotIn("handoff", str(next_step.get("summary", "")).lower())

    def test_refresh_workspace_busy_keeps_existing_data_and_status(self) -> None:
        script = textwrap.dedent(
            """
            const fs = require("fs");
            const vm = require("vm");

            function makeElement(tagName = "div") {
              return {
                tagName,
                children: [],
                className: "",
                textContent: "",
                type: "",
                disabled: false,
                dataset: {},
                append(...nodes) { this.children.push(...nodes); },
                appendChild(node) { this.children.push(node); return node; },
                replaceChildren(...nodes) { this.children = [...nodes]; },
                addEventListener() {},
                removeEventListener() {},
                setAttribute() {},
                classList: {
                  add() {},
                  remove() {},
                  toggle() {},
                  contains() { return false; },
                },
              };
            }

            const elements = new Map();
            const document = {
              getElementById(id) {
                if (!elements.has(id)) {
                  elements.set(id, makeElement("div"));
                }
                return elements.get(id);
              },
              createElement(tag) {
                return makeElement(tag);
              },
            };

            const context = {
              console,
              window: {
                location: { protocol: "file:" },
                prompt() {},
              },
              document,
              navigator: {
                clipboard: {
                  writeText: async () => {},
                },
              },
              setTimeout() {},
              clearTimeout() {},
            };
            context.globalThis = context;
            vm.createContext(context);

            const source = fs.readFileSync(process.env.CONSOLE_APP_PATH, "utf8");
            vm.runInContext(
              source + "\\nglobalThis.__consoleContract = { applyWorkspaceData, refreshWorkspaceData, workspace: () => workspace, status: () => ({ text: dataStatus.textContent, state: dataStatus.dataset.state }) };\\n",
              context,
            );

            context.__consoleContract.applyWorkspaceData({
              generated_at: "existing-snapshot",
              tracks: [{ id: "track-existing", title: "Existing Track", task_ids: [] }],
              tasks: [],
              artifacts: [],
              run_audits: [],
            });
            context.window.location.protocol = "http:";
            context.fetch = async () => ({
              ok: false,
              status: 503,
              json: async () => ({
                ok: false,
                error: "runtime_snapshot_busy",
                message: "Workspace is updating. Retry shortly.",
              }),
            });

            (async () => {
              const refreshed = await context.__consoleContract.refreshWorkspaceData({ silent: true });
              process.stdout.write(JSON.stringify({
                refreshed,
                workspace: context.__consoleContract.workspace(),
                status: context.__consoleContract.status(),
              }));
            })().catch((error) => {
              console.error(error);
              process.exit(1);
            });
            """
        )

        env = os.environ.copy()
        env.update({"CONSOLE_APP_PATH": str(CONSOLE_APP)})
        completed = subprocess.run(
            ["node", "-e", script],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(
            completed.returncode,
            0,
            msg=f"node harness failed\nstdout:\n{completed.stdout}\nstderr:\n{completed.stderr}",
        )
        result = json.loads(completed.stdout)

        self.assertFalse(result["refreshed"])
        self.assertEqual(result["workspace"]["generated_at"], "existing-snapshot")
        self.assertEqual(result["workspace"]["tracks"][0]["id"], "track-existing")
        self.assertEqual(result["status"]["text"], "Workspace is updating. Retry shortly.")
        self.assertEqual(result["status"]["state"], "warning")


if __name__ == "__main__":
    unittest.main()
