# Env Client JSON Payload Code Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the skill-facing env client accept `--payload` as an inline JSON object string for every payload-bearing operation, and remove the active file-path payload contract that caused PM/Design buddy command failures and sandbox approval prompts.

**Architecture:** Keep the runtime broker, env.tool services, object store, and track/artifact publication contract unchanged. Repair only the CLI boundary and active skill guidance: `scripts/env/client.py` parses one JSON object string, dispatches that object through the existing broker path, and active skills teach that exact command shape. Do not preserve a dual file/string payload path.

**Tech Stack:** Python `argparse`, JSON parsing, broker-routed env.tool CLI, pytest/unittest, Markdown runtime skills and specs.

---

## Source Inputs

Required source reads before implementation:

- `AGENTS.md`
- `scripts/env/client.py`
- `tests/test_env_tool_router.py`
- `tests/test_runtime_skills.py`
- `tests/test_repo_consistency.py`
- `buddyswitch/skills/shared/artifact-tool/SKILL.md`
- `buddyswitch/skills/shared/track-tool/SKILL.md`
- `buddyswitch/skills/shared/buddybox-tool/SKILL.md`
- `buddyswitch/skills/shared/message-tool/SKILL.md`
- `buddyswitch/skills/shared/comment-tool/SKILL.md`
- `buddyswitch/skills/shared/task-tool/SKILL.md`
- Product-mode incident logs from PM and Design buddies showing `--payload "$payload"` failure and sandbox retry prompt.

## Current Bottleneck

The skill-facing CLI currently defines `--payload` as a filesystem path:

```python
create_artifact.add_argument("--payload", required=True, type=Path)
...
def _load_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
```

That contract is brittle for agents:

- PM and Design buddies naturally generated a JSON string in shell and passed it to `--payload`.
- The CLI treated that JSON string as a file path and failed.
- Codex then displayed "command failed; retry without sandbox?", which looked like a runtime permission problem even though the runtime broker had not rejected anything.
- The current help text says only `--payload PAYLOAD`, so it does not tell agents that a file path is expected.
- Active skills are inconsistent: some omit payload examples, while `buddybox-tool` explicitly teaches `/tmp/buddybox-write.json`.

The fix is a CLI contract change, not a runtime publication repair.

## Target CLI Contract

`--payload` means an inline JSON object string.

Valid:

```bash
python3 scripts/env/client.py artifact create-revision --payload '{"title":"Design Direction","summary":"Draft","template":"design","body":"# Body"}'
```

Valid for longer markdown bodies:

```bash
python3 scripts/env/client.py artifact create-revision --payload "$(python3 - <<'PY'
import json
print(json.dumps({
  "title": "Design Direction",
  "summary": "Draft",
  "template": "design",
  "body": "# Body\n\nLong markdown is fine here."
}))
PY
)"
```

Invalid:

```bash
python3 scripts/env/client.py artifact create-revision --payload /tmp/artifact.json
python3 scripts/env/client.py artifact create-revision --payload '["not", "an", "object"]'
python3 scripts/env/client.py artifact create-revision --payload '"not an object"'
python3 scripts/env/client.py artifact create-revision --payload 'not-json'
```

Invalid payloads reject before broker dispatch with:

- top-level `ok=false`
- `error.code="E_ENV_CLI"`
- an actionable message containing `--payload must be a JSON object string`
- no env.tool call
- no runtime state mutation

## Payload-Bearing Operations In Scope

Update every current CLI operation that uses `--payload`:

- `task create`
- `task update`
- `track create`
- `track update-now`
- `track add-material`
- `track add-update`
- `track add-proof`
- `artifact create-revision`
- `artifact update-metadata`
- `buddybox write`
- `message send`
- `comment add`

Operations that already use scalar flags stay unchanged:

- `task get`
- `task archive`
- `track open`
- `track archive`
- `artifact get`
- `context get`
- `context summarize`
- `context list-sources`
- `buddybox desc`
- `buddybox list`
- `buddybox read`
- `buddybox delete`
- `evidence issue-browser`
- `evidence approve-downgrade`
- `search status`
- `search request`
- `search open-browser`
- `message list`
- `comment list`

## Non-Goals

- Do not change broker protocol or runtime kernel permissions.
- Do not change env.tool payload schemas.
- Do not change track/artifact publication semantics.
- Do not add `--payload-file`, `@file`, auto-detect path, stdin payloads, or dual compatibility routes.
- Do not update historical memo/spec docs unless an active-residue test requires it.
- Do not hide invalid JSON behind sandbox retry, shell fallback, or direct object-store writes.

## File Responsibility Map

- `scripts/env/client.py`: Owns the skill-facing CLI contract, argparse help text, JSON object parsing, and broker dispatch.
- `tests/test_env_client_payload_cli.py`: Focused CLI payload contract tests using the public CLI entry point and a mocked broker boundary.
- `tests/test_env_tool_router.py`: Existing env.tool surface tests; add help assertions that payload metavar and help text are precise.
- `tests/test_runtime_skills.py`: Active skill guidance tests for JSON object string payloads and no file-path examples.
- `tests/test_repo_consistency.py`: Active residue scan for stale payload-file guidance in runtime-visible docs/skills/launcher prompts.
- `buddyswitch/skills/shared/*.md`: Active shared tool skills that teach command shape and recovery behavior.

## Implementation Tasks

### Task 1: Add CLI Payload Contract Tests First

**Files:**

- Create: `tests/test_env_client_payload_cli.py`
- Modify: `tests/test_env_tool_router.py`

**Intent:** Define the user-visible CLI contract before changing implementation.

- [ ] **Step 1: Create `tests/test_env_client_payload_cli.py` with broker-boundary tests**

Use the public `client.main()` entry point. Patch only `request_runtime_broker` so the test verifies the CLI envelope without requiring a live product-mode broker.

```python
#!/usr/bin/env python3
"""CLI payload parsing contract tests for scripts/env/client.py."""

from __future__ import annotations

import contextlib
import importlib
import io
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


class EnvClientPayloadCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = importlib.import_module("env.client")

    def _run_client(self, argv: list[str], *, broker_response: dict[str, object] | None = None):
        response = broker_response if broker_response is not None else {"ok": True}
        stdout = io.StringIO()
        with mock.patch.object(sys, "argv", ["client.py", *argv]):
            with mock.patch.object(self.client, "request_runtime_broker", return_value=response) as broker:
                with contextlib.redirect_stdout(stdout):
                    code = self.client.main()
        return code, json.loads(stdout.getvalue()), broker

    def test_json_object_payload_dispatches_for_every_payload_operation(self) -> None:
        cases = [
            (["task", "create"], "task", "create", {"task_id": "task-json", "title": "Task", "buddy": "dev"}),
            (["task", "update"], "task", "update", {"task_id": "task-json", "summary": "Updated"}),
            (["track", "create"], "track", "create", {"track_id": "track-json", "title": "Track", "outcome": "Outcome", "appetite": "1 day", "now": {"next": "next", "blocker": None}}),
            (["track", "update-now"], "track", "update_now", {"track_id": "track-json", "now": {"next": "next", "blocker": None}}),
            (["track", "add-material"], "track", "add_material", {"track_id": "track-json", "artifact_id": "art-json", "label": "Brief", "summary": "Summary"}),
            (["track", "add-update"], "track", "add_update", {"track_id": "track-json", "summary": "Progress", "kind": "progress"}),
            (["track", "add-proof"], "track", "add_proof", {"track_id": "track-json", "artifact_id": "art-proof", "label": "Proof", "summary": "Summary"}),
            (["artifact", "create-revision"], "artifact", "create_revision", {"title": "Artifact", "summary": "Summary", "template": "brief", "body": "# Body"}),
            (["artifact", "update-metadata"], "artifact", "update_metadata", {"artifact_id": "art-json", "summary": "Updated"}),
            (["buddybox", "write"], "buddybox", "write", {"logical_name": "notes.md", "content": "hello"}),
            (["message", "send"], "message", "send", {"to_buddy": "design", "content": "Please review"}),
            (["comment", "add"], "comment", "add", {"target_type": "track", "target_id": "track-json", "content": "Looks good"}),
        ]

        for prefix, expected_tool, expected_action, payload in cases:
            with self.subTest(argv=prefix):
                code, output, broker = self._run_client([*prefix, "--payload", json.dumps(payload)])
                self.assertEqual(code, 0, msg=output)
                broker.assert_called_once_with(
                    "env.tool",
                    {"tool": expected_tool, "action": expected_action, "args": payload},
                )

    def test_payload_file_path_string_is_rejected_without_file_read(self) -> None:
        with mock.patch.object(sys, "argv", ["client.py", "artifact", "create-revision", "--payload", "/tmp/artifact.json"]):
            with mock.patch.object(self.client, "request_runtime_broker") as broker:
                with mock.patch("pathlib.Path.read_text", side_effect=AssertionError("must not read payload file")):
                    stdout = io.StringIO()
                    with contextlib.redirect_stdout(stdout):
                        code = self.client.main()

        output = json.loads(stdout.getvalue())
        self.assertEqual(code, 1, msg=output)
        self.assertFalse(output.get("ok"), msg=output)
        self.assertEqual(output.get("error", {}).get("code"), "E_ENV_CLI")
        self.assertIn("--payload must be a JSON object string", output.get("error", {}).get("message", ""))
        broker.assert_not_called()

    def test_malformed_payload_rejects_before_broker_dispatch(self) -> None:
        code, output, broker = self._run_client(["track", "add-material", "--payload", "{not-json"])
        self.assertEqual(code, 1, msg=output)
        self.assertFalse(output.get("ok"), msg=output)
        self.assertEqual(output.get("error", {}).get("code"), "E_ENV_CLI")
        self.assertIn("--payload must be a JSON object string", output.get("error", {}).get("message", ""))
        broker.assert_not_called()

    def test_non_object_json_payload_rejects_before_broker_dispatch(self) -> None:
        for raw in ("[]", '"text"', "null", "1", "true"):
            with self.subTest(raw=raw):
                code, output, broker = self._run_client(["message", "send", "--payload", raw])
                self.assertEqual(code, 1, msg=output)
                self.assertFalse(output.get("ok"), msg=output)
                self.assertEqual(output.get("error", {}).get("code"), "E_ENV_CLI")
                self.assertIn("--payload must be a JSON object string", output.get("error", {}).get("message", ""))
                broker.assert_not_called()


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Add help assertions to `tests/test_env_tool_router.py`**

Extend `test_cli_exposes_final_track_operations_without_handoff` or add a new test that runs help for representative payload operations:

```python
payload_help_cases = [
    ["task", "create", "--help"],
    ["track", "add-material", "--help"],
    ["artifact", "create-revision", "--help"],
    ["buddybox", "write", "--help"],
    ["message", "send", "--help"],
    ["comment", "add", "--help"],
]
for args in payload_help_cases:
    completed = subprocess.run(
        ["python3", "scripts/env/client.py", *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    self.assertEqual(completed.returncode, 0, msg=completed.stderr)
    self.assertIn("--payload JSON_OBJECT", completed.stdout)
    self.assertIn("JSON object string", completed.stdout)
    self.assertNotIn("--payload PAYLOAD", completed.stdout)
    self.assertNotIn("payload file", completed.stdout.lower())
```

- [ ] **Step 3: Run the new focused tests and verify they fail before implementation**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_env_client_payload_cli.py tests/test_env_tool_router.py -q
```

Expected before implementation:

- JSON string dispatch tests fail because current `_load_json_object` treats the JSON string as a path.
- Help assertions fail because argparse shows `--payload PAYLOAD` and no JSON object string guidance.

### Task 2: Change `scripts/env/client.py` to Parse JSON Object Strings

**Files:**

- Modify: `scripts/env/client.py`
- Test: `tests/test_env_client_payload_cli.py`
- Test: `tests/test_env_tool_router.py`

**Intent:** Replace the file-path payload contract with one direct JSON string parser.

- [ ] **Step 1: Replace `_load_json_object(path: Path)`**

Change it to parse raw JSON object text:

```python
def _load_json_object(raw: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"--payload must be a JSON object string: {exc.msg} at char {exc.pos}") from exc
    if not isinstance(payload, dict):
        raise ValueError("--payload must be a JSON object string")
    return payload
```

- [ ] **Step 2: Add one argparse helper for payload arguments**

Add this near `_parse_args()`:

```python
def _add_payload_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--payload",
        required=True,
        metavar="JSON_OBJECT",
        help="JSON object string to send as env.tool args; do not pass a file path.",
    )
```

- [ ] **Step 3: Replace every payload `add_argument`**

Replace all current instances of:

```python
parser.add_argument("--payload", required=True, type=Path)
```

with:

```python
_add_payload_argument(parser)
```

Apply this to the twelve in-scope operations:

- `task create`
- `task update`
- `track create`
- `track update-now`
- `track add-material`
- `track add-update`
- `track add-proof`
- `artifact create-revision`
- `artifact update-metadata`
- `buddybox write`
- `message send`
- `comment add`

- [ ] **Step 4: Keep `Path` only for locating the scripts root**

Do not remove:

```python
from pathlib import Path
SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
```

`Path` still has a legitimate module-loading responsibility.

- [ ] **Step 5: Run focused CLI tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_env_client_payload_cli.py tests/test_env_tool_router.py -q
```

Expected after implementation:

- All new CLI payload tests pass.
- Existing router surface tests remain green.

### Task 3: Update Active Shared Skills to Teach Inline JSON Payloads

**Files:**

- Modify: `buddyswitch/skills/shared/artifact-tool/SKILL.md`
- Modify: `buddyswitch/skills/shared/track-tool/SKILL.md`
- Modify: `buddyswitch/skills/shared/buddybox-tool/SKILL.md`
- Modify: `buddyswitch/skills/shared/message-tool/SKILL.md`
- Modify: `buddyswitch/skills/shared/comment-tool/SKILL.md`
- Modify: `buddyswitch/skills/shared/task-tool/SKILL.md`
- Test: `tests/test_runtime_skills.py`
- Test: `tests/test_repo_consistency.py`

**Intent:** Make active guidance match the new CLI contract so buddies generate the correct command on the first try.

- [ ] **Step 1: Add shared payload language to each affected skill**

Use this exact concept in each shared skill that has a mutating payload command:

```markdown
## CLI Payload Rule
- `--payload` takes one JSON object string.
- Do not pass a filesystem path to `--payload`.
- For long markdown bodies, generate the JSON string with `python3 - <<'PY'` and pass it through command substitution.
```

- [ ] **Step 2: Update `artifact-tool` with a canonical long-body example**

Add:

````markdown
```bash
python3 scripts/env/client.py artifact create-revision --payload "$(python3 - <<'PY'
import json
print(json.dumps({
  "title": "Design Direction",
  "summary": "Draft",
  "template": "design",
  "body": "# Design Direction\n\nLong markdown body."
}))
PY
)"
```
````

Keep the existing publication-path rules:

- `create-revision` creates private drafts only.
- Shared publication starts after `track.add-material` or `track.add-proof`.

- [ ] **Step 3: Update `track-tool` with add-material JSON string example**

Add:

````markdown
```bash
python3 scripts/env/client.py track add-material --payload '{"track_id":"track-alpha","artifact_id":"art-alpha","label":"Design Direction","summary":"Current design direction."}'
```
````

- [ ] **Step 4: Update `buddybox-tool` and delete `/tmp/buddybox-write.json` guidance**

Replace:

```bash
python3 scripts/env/client.py buddybox write --payload /tmp/buddybox-write.json
```

with:

```bash
python3 scripts/env/client.py buddybox write --payload '{"logical_name":"prototypes/landing.html","content":"<!doctype html>","content_type":"text/html"}'
```

- [ ] **Step 5: Update `message-tool`, `comment-tool`, and `task-tool`**

Add one command example each:

```bash
python3 scripts/env/client.py message send --payload '{"to_buddy":"design","content":"Please review the PRD on track-alpha."}'
python3 scripts/env/client.py comment add --payload '{"target_type":"track","target_id":"track-alpha","content":"Design direction is ready."}'
python3 scripts/env/client.py task create --payload '{"task_id":"task-alpha","title":"Review design direction","buddy":"design","summary":"Review shared material."}'
```

- [ ] **Step 6: Run skill-focused tests after adding test assertions in Task 4**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_runtime_skills.py tests/test_repo_consistency.py -q
```

Expected after Task 4 assertions are added:

- Active skills teach JSON object string payloads.
- Active skills do not teach payload file paths.

### Task 4: Add Active Guidance and Residue Tests

**Files:**

- Modify: `tests/test_runtime_skills.py`
- Modify: `tests/test_repo_consistency.py`

**Intent:** Prevent recurrence by testing the guidance surface that buddies actually read.

- [ ] **Step 1: Add skill guidance assertions to `tests/test_runtime_skills.py`**

Add a new test:

```python
def test_shared_tool_skills_teach_inline_json_payloads(self) -> None:
    skill_paths = [
        ROOT / "buddyswitch/skills/shared/task-tool/SKILL.md",
        ROOT / "buddyswitch/skills/shared/track-tool/SKILL.md",
        ROOT / "buddyswitch/skills/shared/artifact-tool/SKILL.md",
        ROOT / "buddyswitch/skills/shared/buddybox-tool/SKILL.md",
        ROOT / "buddyswitch/skills/shared/message-tool/SKILL.md",
        ROOT / "buddyswitch/skills/shared/comment-tool/SKILL.md",
    ]
    for path in skill_paths:
        text = path.read_text(encoding="utf-8").lower()
        with self.subTest(path=str(path.relative_to(ROOT))):
            self.assertIn("--payload", text)
            self.assertIn("json object string", text)
            self.assertNotIn("--payload /tmp", text)
            self.assertNotIn("payload file path", text)
            self.assertNotIn("payload file", text)
```

- [ ] **Step 2: Add active residue scan to `tests/test_repo_consistency.py`**

Add a test that scans active runtime guidance, not historical docs:

```python
def test_active_cli_guidance_has_no_payload_file_route(self) -> None:
    targets = [
        "AGENTS.md",
        "buddyswitch/skills",
        "framework/contracts",
        "tools/launcher/assets/buddies",
        "scripts/env/client.py",
    ]
    completed = subprocess.run(
        ["rg", "-uuu", "-n", "payload file|--payload /tmp|--payload <json-file>|--payload <file>|PAYLOAD_JSON_FILE", *targets],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    self.assertIn(completed.returncode, {0, 1}, msg=completed.stderr)
    hits = [line for line in completed.stdout.splitlines() if line.strip()]
    self.assertEqual(hits, [], msg="\n".join(hits))
```

Historical `docs/spec` and `docs/memo` are intentionally excluded from this active guidance scan.

- [ ] **Step 3: Run guidance tests and verify they fail before skill cleanup**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_runtime_skills.py tests/test_repo_consistency.py -q
```

Expected before skill cleanup:

- At least `buddybox-tool` fails because it still teaches `/tmp/buddybox-write.json`.

- [ ] **Step 4: Run guidance tests again after skill cleanup**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_runtime_skills.py tests/test_repo_consistency.py -q
```

Expected:

- All active guidance tests pass.

### Task 5: Product-Mode Smoke for the Real Buddy Failure

**Files:**

- No source files required.
- Runtime objects may be created only through launcher-managed env tools.

**Intent:** Verify the original Design buddy failure no longer recurs in the real runtime path.

- [ ] **Step 1: Start a Design buddy product-mode smoke**

Use the launcher in the current worktree:

```bash
./buddyswitch-codex instance start --buddy design -- exec "Read track freecallai-us-eu-landing-page and artifacts art-1f5257c017/art-8bc569a5b9. Create a revised design-direction artifact using artifact.create_revision with --payload as a JSON string, publish it to the same track with track.add_material using --payload as a JSON string, then verify with track.open and artifact.get. Do not write raw state files."
```

- [ ] **Step 2: Confirm the smoke does not request sandbox escalation**

Expected:

- No "retry without sandbox" prompt is needed for payload handling.
- If external browsing or unrelated shell access requests approval, record it separately and do not count it as payload-contract failure.

- [ ] **Step 3: Confirm runtime state through env tools**

Expected:

- Design buddy creates one new draft artifact via `artifact.create_revision`.
- Design buddy publishes it via `track.add_material`.
- `track.open` exposes the new artifact in `shared_materials`.
- `artifact.get` reads the full markdown body.
- No direct `buddyswitch/objects/**` edit occurs.

If the launcher cannot run in the current environment, record the blocker exactly and run the automated tests plus a non-product CLI smoke with mocked broker. Do not claim product-mode smoke passed when it did not run.

### Task 6: Final Verification and Cleanup

**Files:**

- Source files changed in Tasks 2-4.

**Intent:** Prove the full change set and ensure no stale payload-file route remains active.

- [ ] **Step 1: Run focused gates**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_env_client_payload_cli.py tests/test_env_tool_router.py tests/test_runtime_skills.py tests/test_repo_consistency.py -q
```

Expected:

- All selected tests pass.

- [ ] **Step 2: Run static syntax check**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile scripts/env/client.py tests/test_env_client_payload_cli.py tests/test_env_tool_router.py tests/test_runtime_skills.py tests/test_repo_consistency.py
```

Expected:

- Exit code 0.

- [ ] **Step 3: Run active residue scan**

```bash
rg -uuu -n "payload file|--payload /tmp|--payload <json-file>|--payload <file>|PAYLOAD_JSON_FILE" AGENTS.md buddyswitch/skills framework/contracts tools/launcher/assets/buddies scripts/env/client.py
```

Expected:

- No matches.

- [ ] **Step 4: Run main test suite**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider -q
```

Expected:

- Full suite passes with existing expected skips only.

- [ ] **Step 5: Check git status and worktree isolation**

```bash
git status --short
git branch --show-current
git rev-parse --show-toplevel
git -C /Users/chen/Dev/buddyswitch status --short
```

Expected:

- Current branch is `track-artifact-pm-runtime-repair`.
- Current top-level is `/Users/chen/Dev/buddyswitch/.worktrees/track-artifact-pm-runtime-repair`.
- Main checkout status does not include these changes.

## Acceptance Criteria

- `--payload` is documented and implemented as a JSON object string for every payload-bearing env client command.
- Passing a JSON object string dispatches the expected env.tool payload.
- Passing a path-like string does not read a file and rejects before broker dispatch.
- Passing malformed JSON or non-object JSON rejects before broker dispatch.
- Active shared skills teach inline JSON object payloads and no longer teach `/tmp/*.json` payload files.
- Product-mode Design buddy smoke completes the original failing flow without sandbox retry for payload handling, or a concrete environment blocker is recorded.
- Focused gates, syntax check, active residue scan, and main test suite pass.
