#!/usr/bin/env python3
"""Contract tests for console track-page derivation behavior."""

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
    def test_console_source_excludes_handoff_and_next_step_helpers(self) -> None:
        source = CONSOLE_APP.read_text(encoding="utf-8")
        self.assertNotIn("deriveNextStepStateForTrack", source)
        self.assertNotIn("deriveNextStepStateForTask", source)
        self.assertNotIn("handoff", source.lower())
        self.assertIn("deriveTrackPageState", source)

    def _derive_track_page_state(self, track_payload: dict) -> dict:
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
                classList: { add() {}, remove() {}, toggle() {}, contains() { return false; } },
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
                addEventListener() {},
              },
              document,
              navigator: { clipboard: { writeText: async () => {} } },
              setTimeout() {},
              clearTimeout() {},
            };
            context.globalThis = context;
            vm.createContext(context);

            const source = fs.readFileSync(process.env.CONSOLE_APP_PATH, "utf8");
            vm.runInContext(source + "\\nglobalThis.__consoleContract = { deriveTrackPageState };\\n", context);

            const trackPayload = JSON.parse(process.env.TRACK_PAYLOAD_JSON);
            const result = context.__consoleContract.deriveTrackPageState(trackPayload);
            process.stdout.write(JSON.stringify(result));
            """
        )

        env = os.environ.copy()
        env.update(
            {
                "CONSOLE_APP_PATH": str(CONSOLE_APP),
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
        self.assertEqual(completed.returncode, 0, msg=f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}")
        return json.loads(completed.stdout)

    def test_track_page_state_is_neutral(self) -> None:
        payload = self._derive_track_page_state(
            {
                "id": "track-alpha",
                "owner_buddy": "pm",
                "state": "active",
                "health": "ok",
                "outcome": "alpha",
                "now": {"next": "ship", "blocker": "none"},
            }
        )
        self.assertEqual(
            payload,
            {
                "trackId": "track-alpha",
                "ownerBuddy": "pm",
                "state": "active",
                "health": "ok",
                "outcome": "alpha",
                "nowNext": "ship",
                "nowBlocker": "none",
            },
        )
        serialized = json.dumps(payload).lower()
        self.assertNotIn("handoff", serialized)


if __name__ == "__main__":
    unittest.main()
