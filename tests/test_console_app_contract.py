#!/usr/bin/env python3
"""Contract tests for console command derivation behavior."""

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
    def _derive_track_commands(self, workspace_payload: dict, track_payload: dict) -> dict:
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
              source + "\\nglobalThis.__consoleContract = { applyWorkspaceData, deriveSwitchCommandsForTrack };\\n",
              context,
            );

            const workspacePayload = JSON.parse(process.env.WORKSPACE_PAYLOAD_JSON);
            const trackPayload = JSON.parse(process.env.TRACK_PAYLOAD_JSON);
            context.__consoleContract.applyWorkspaceData(workspacePayload);
            const result = context.__consoleContract.deriveSwitchCommandsForTrack(trackPayload);
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

    def test_track_recommended_command_keeps_canonical_switch_when_test_guidance_exists(self) -> None:
        canonical_recommended = "switch market -> track-alpha: synthesize demand evidence into pm handoff"
        synthetic_test_guidance = "switch test -> track-alpha: Run smoke checks for latest implementation"

        track_payload = {
            "id": "track-alpha",
            "current_buddy": "dev",
            "next_buddy": "market",
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
                    "recommended_switch": canonical_recommended,
                    "reference_switches": {
                        "continue_current_task_in_track": "switch dev(task-dev) -> track-alpha: continue implementation"
                    },
                }
            ],
        }

        commands = self._derive_track_commands(workspace_payload, track_payload)
        self.assertEqual(commands["recommended"], canonical_recommended)
        self.assertEqual(commands["handoff"], synthetic_test_guidance)

    def test_track_handoff_prefers_persisted_reference_over_synthetic_test_guidance(self) -> None:
        canonical_recommended = "switch market -> track-alpha: synthesize demand evidence into pm handoff"
        persisted_handoff = "switch market -> track-alpha: deliver market sizing and risk caveats to pm"
        synthetic_test_guidance = "switch test -> track-alpha: Run smoke checks for latest implementation"

        track_payload = {
            "id": "track-alpha",
            "current_buddy": "dev",
            "next_buddy": "market",
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
                    "recommended_switch": canonical_recommended,
                    "reference_switches": {
                        "handoff_to_next_buddy": persisted_handoff,
                        "continue_current_task_in_track": "switch dev(task-dev) -> track-alpha: continue implementation",
                    },
                }
            ],
        }

        commands = self._derive_track_commands(workspace_payload, track_payload)
        self.assertEqual(commands["recommended"], canonical_recommended)
        self.assertEqual(commands["handoff"], persisted_handoff)
        self.assertNotEqual(commands["handoff"], synthetic_test_guidance)


if __name__ == "__main__":
    unittest.main()
