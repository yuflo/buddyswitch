# Switch Command Residue Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the remaining runtime rejection of switch-prefixed request text so product-mode `prepare` treats it as ordinary user text inside the locked buddy instance.

**Architecture:** Keep launcher instance metadata as the only source of `active_buddy`. Product-mode `prepare` should validate product session and ordinary request state, then reserve a run without parsing user text as a routing command. Retired public launcher commands remain fail-closed in the launcher layer.

**Tech Stack:** Python runtime (`scripts/turn_runtime.py`), Python `unittest`/`pytest`, repository consistency checks, Markdown specs.

---

## Working Directory

Run all work from:

```bash
cd /Users/chen/Dev/buddyswitch/.worktrees/dev0210
```

Do not edit `/Users/chen/Dev/buddyswitch` main checkout. Keep source, tests, and docs inside the `dev0210` worktree.

## Current Bottleneck

The runtime still contains a router-era guard that rejects request text shaped like `switch <buddy>: <task>`. That behavior conflicts with the current product model: a launcher-managed instance is already locked to one buddy, and the user's text is only `request_text`.

This blocks ordinary requests such as `switch market: do competitor scan` even when the active PM instance should simply receive that text as the task demand.

## Preflight Gate

Target outcome:

- `prepare` accepts switch-prefixed text as ordinary request text.
- The prepared context preserves the exact input string.
- `active_buddy` comes from locked product session metadata, not from any text prefix.
- A run reservation is created exactly as for other non-empty ordinary requests.
- Launcher top-level retired commands still fail closed before Codex starts.

Confirmed facts:

- The runtime rejection helper is in `scripts/turn_runtime.py` near the prepare path.
- `_build_prepare_turn_context` currently returns a retired legacy-command error before resolving `active_buddy`.
- `tests/test_turn_runtime.py` contains a rejection test for `switch market: do competitor scan`.
- `docs/spec/2026-05-06-buddy-run-persist-test-plan.md` still describes switch-shaped requests as rejected.
- `tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_legacy_public_commands_fail_closed_with_hints` covers separate launcher-level retired commands.
- `tests/test_repo_consistency.py::test_launcher_help_keeps_instance_data_env_namespaces` already checks launcher help does not teach `switch pm:` or `switch market:`.

Open assumptions and invalidators:

- This change does not alter external CLI command routing. If launcher tests start accepting `buddyswitch-codex start`, `buddy`, `cleanup`, `reset`, `browser`, or `workspace`, stop and fix launcher scope.
- This change does not introduce a new switch router, recommendation field, or grammar contract.
- This change does not weaken existing prepare guardrails for empty input, missing product session, task/track binding conflicts, or forbidden legacy output paths.

Tools and permissions:

- No network access is required.
- No main checkout writes are required.
- Use `apply_patch` for manual edits.
- Use local `pytest` targeted loops first, then repository consistency tests.

Verification plan:

- First run new prepare tests and confirm they fail on the old behavior.
- Implement the smallest runtime deletion.
- Re-run targeted prepare tests.
- Run launcher/top-level legacy command checks.
- Run active-surface residue scans that exclude archive memos.

Stop condition:

- All targeted tests pass.
- Active runtime/test/spec surfaces no longer preserve the retired rejection behavior.
- Retired launcher commands remain fail-closed.

## Scope

In scope:

- Product-mode `prepare` behavior for switch-prefixed request text.
- Tests proving text preservation, active buddy authority, and run reservation.
- Active test plan wording under `docs/spec/2026-05-06-buddy-run-persist-test-plan.md`.
- Active documentation/help guardrails that prevent teaching `switch <buddy>:` as syntax.

Out of scope:

- Launcher command namespace cleanup.
- Runtime broker protocol changes.
- Buddy env profile or sandbox changes.
- Persist result schema changes.
- Any compatibility parser for old switch commands.

## File Map

Modify:

- `tests/test_turn_runtime.py`: replace the rejection test with product-behavior positive coverage.
- `scripts/turn_runtime.py`: remove the switch-shaped request rejection from prepare.
- `docs/spec/2026-05-06-buddy-run-persist-test-plan.md`: update the active test plan wording.
- `tests/test_repo_consistency.py`: extend active surface guardrails against re-teaching switch command syntax and switch-router fields.

Do not modify:

- `buddyswitch-codex` command routing for retired top-level commands.
- `tools/launcher/**` unless verification proves launcher behavior regressed.
- `buddyswitch/manifest.toml`.

## Implementation Tasks

### Task 1: Add Failing Product Prepare Tests

**Files:**

- Modify: `tests/test_turn_runtime.py`

- [ ] **Step 1: Replace the rejection test with ordinary request acceptance**

Replace `test_prepare_rejects_legacy_command_shaped_request_without_reservation` with:

```python
    def test_prepare_accepts_switch_prefixed_text_as_ordinary_request(self) -> None:
        request_text = "switch market: do competitor scan"

        with patch.object(turn_runtime, "_load_product_mode_session", return_value=self._session(buddy="pm")):
            payload = turn_runtime.prepare_turn_context(request_text, manifest_path=MANIFEST)

        self.assertTrue(payload["ok"], msg=payload)
        self.assertEqual(payload["active_buddy"], "pm")
        self.assertEqual(payload["request_text"], request_text)

        run_envelope = payload["run_envelope"]
        self.assertEqual(run_envelope["status"], "reserved")
        self.assertEqual(run_envelope["turn_identity"]["active_buddy"], "pm")
        self.assertEqual(run_envelope["turn_identity"]["request_text"], request_text)
        self.assertEqual(run_envelope["turn_identity"]["instance_id"], "instance-test")

        reservations = self._runtime_state_snapshot()["reservations"]
        self.assertEqual(len(reservations), 1)
        reservation = next(iter(reservations.values()))
        self.assertEqual(reservation["run_id"], run_envelope["run_id"])
        self.assertEqual(reservation["status"], "reserved")
        self.assertEqual(reservation["turn_identity"]["active_buddy"], "pm")
        self.assertEqual(reservation["turn_identity"]["request_text"], request_text)
```

This test must prove observable runtime behavior: success, metadata authority, exact text preservation, and normal reservation. It must not assert a private detector was called or skipped.

- [ ] **Step 2: Add active-buddy authority coverage across switch prefixes**

Add this test below the acceptance test:

```python
    def test_prepare_uses_locked_buddy_for_switch_prefixed_text(self) -> None:
        cases = (
            ("pm", "switch market: do competitor scan"),
            ("market", "switch dev: summarize positioning gaps"),
            ("dev", "switch pm: implement launcher cleanup"),
        )

        for session_buddy, request_text in cases:
            with self.subTest(session_buddy=session_buddy, request_text=request_text):
                before_count = len(self._runtime_state_snapshot()["reservations"])
                with patch.object(
                    turn_runtime,
                    "_load_product_mode_session",
                    return_value=self._session(buddy=session_buddy),
                ):
                    payload = turn_runtime.prepare_turn_context(request_text, manifest_path=MANIFEST)

                self.assertTrue(payload["ok"], msg=payload)
                self.assertEqual(payload["active_buddy"], session_buddy)
                self.assertEqual(payload["request_text"], request_text)
                self.assertEqual(payload["run_envelope"]["turn_identity"]["active_buddy"], session_buddy)
                self.assertEqual(payload["run_envelope"]["turn_identity"]["request_text"], request_text)
                self.assertEqual(len(self._runtime_state_snapshot()["reservations"]), before_count + 1)
```

The mismatched text prefix is intentional: the product requirement is that text never overrides the locked instance buddy.

- [ ] **Step 3: Run the new tests and verify they fail before implementation**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_turn_runtime.py::TurnRuntimeBuddyRunTests::test_prepare_accepts_switch_prefixed_text_as_ordinary_request \
  tests/test_turn_runtime.py::TurnRuntimeBuddyRunTests::test_prepare_uses_locked_buddy_for_switch_prefixed_text \
  -q
```

Expected before implementation:

```text
FAILED ... AssertionError: False is not true
```

The failure should come from prepare rejecting switch-prefixed text before creating a context. If the failure is caused by test setup, runtime root setup, or manifest loading, fix that first.

### Task 2: Remove Runtime Switch-Text Rejection

**Files:**

- Modify: `scripts/turn_runtime.py`

- [ ] **Step 1: Delete the retired request-shape detector**

Remove the helper immediately after `_ensure_no_legacy_outputs` that:

- strips leading whitespace from `request_text`;
- checks whether the lowercase text starts with `switch `;
- looks for a colon in the remainder;
- treats a non-empty prefix and body as a command-shaped request.

Do not replace it with a permissive parser. The runtime should not parse buddy routing from request text at all.

- [ ] **Step 2: Delete the prepare rejection branch**

In `_build_prepare_turn_context`, remove the branch between the product-session-required check and `active_buddy = product_session["active_buddy"]` that returns the retired legacy-command error.

After the edit, the prepare flow should be:

```python
    product_session = _load_product_mode_session(manifest_path)
    if product_session is None:
        return runtime_error(
            "E_PRODUCT_MODE_REQUIRED",
            "prepare-turn-context requires a launcher-managed buddy instance. Start a buddy instance and use an ordinary request.",
        )

    active_buddy = product_session["active_buddy"]
```

- [ ] **Step 3: Run the focused prepare tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_turn_runtime.py::TurnRuntimeBuddyRunTests::test_prepare_accepts_switch_prefixed_text_as_ordinary_request \
  tests/test_turn_runtime.py::TurnRuntimeBuddyRunTests::test_prepare_uses_locked_buddy_for_switch_prefixed_text \
  -q
```

Expected:

```text
2 passed
```

- [ ] **Step 4: Run prepare regression coverage**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_turn_runtime.py -k "switch_prefixed_text_as_ordinary_request or uses_locked_buddy_for_switch_prefixed_text or prepare" \
  -q
```

Expected:

```text
all selected tests passed
```

If task/track conflict or product-mode-required tests fail, do not weaken them. Fix only the switch-text cleanup scope.

### Task 3: Update Active Test Plan Wording

**Files:**

- Modify: `docs/spec/2026-05-06-buddy-run-persist-test-plan.md`

- [ ] **Step 1: Replace the old TG-02 case**

In `TG-02: Prepare Creates Buddy Run Context`, replace the old case that says switch-shaped requests are rejected with:

```markdown
3. Switch-prefixed request text prepares as ordinary text.
   - Input: `switch market: do competitor scan` in a PM product session.
   - Expected: context contains `active_buddy="pm"`, `request_text` exactly equal to the input, `current_task_id`, and `run_envelope.status="reserved"`.
   - Expected: no selected skill packet, switch router, switch recommendation, or reference switch field is present.
```

- [ ] **Step 2: Keep the task/track conflict case**

Keep the following case as the next negative prepare case:

```markdown
4. Task/track binding conflict remains rejected.
   - Expected: prepare fails without creating an inconsistent task binding.
```

- [ ] **Step 3: Check the edited section**

Run:

```bash
sed -n '218,232p' docs/spec/2026-05-06-buddy-run-persist-test-plan.md
```

Expected:

- TG-02 includes the switch-prefixed positive case.
- TG-02 still includes the task/track conflict negative case.
- TG-02 no longer describes switch-shaped request text as rejected.

### Task 4: Strengthen Active Surface Guardrails

**Files:**

- Modify: `tests/test_repo_consistency.py`

- [ ] **Step 1: Extend active product surface forbidden tokens**

In `test_active_product_paths_exclude_legacy_switch_wire`, append these tokens to `forbidden_tokens`:

```python
            "recommended_switch",
            "reference_switches",
            "switch <buddy>:",
            "switch pm:",
            "switch market:",
            "switch dev:",
```

Do not scan `docs/memo` or historical development plans in this consistency test. The guardrail should cover active product paths: README, framework docs/contracts, scripts, launcher buddy templates, and first-party skills.

- [ ] **Step 2: Run active surface checks**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_launcher_help_keeps_instance_data_env_namespaces \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_active_product_paths_exclude_legacy_switch_wire \
  -q
```

Expected:

```text
2 passed
```

If this fails because active docs still teach switch command syntax, remove that active wording. Do not weaken the guardrail.

### Task 5: Verify Launcher Boundary Is Unchanged

**Files:**

- Test only unless a regression appears.

- [ ] **Step 1: Run retired top-level command tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_legacy_public_commands_fail_closed_with_hints \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_launcher_help_and_reset_flow \
  -q
```

Expected:

```text
2 passed
```

This proves request text cleanup did not reopen retired public launcher commands.

- [ ] **Step 2: Run the memo's targeted verification set**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_turn_runtime.py -k "switch_prefixed_text_as_ordinary_request or uses_locked_buddy_for_switch_prefixed_text or prepare" \
  -q
```

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_repo_consistency.py tests/test_buddyswitch_launcher.py \
  -k "switch or legacy_command or launcher_help" \
  -q
```

Expected:

```text
all selected tests passed
```

- [ ] **Step 3: Run an active-surface residue scan without matching archive memos**

Run:

```bash
python3 - <<'PY'
from __future__ import annotations

from pathlib import Path

patterns = [
    "E_" + "LEGACY_COMMAND_INPUT",
    "_is_" + "legacy_command_shaped_request",
    "Legacy command-shaped request remains " + "rejected",
]
roots = [
    Path("scripts"),
    Path("tests"),
    Path("docs/spec/2026-05-06-buddy-run-persist-test-plan.md"),
    Path("README.md"),
    Path("framework"),
    Path("tools/launcher/assets"),
    Path("buddyswitch/skills"),
]

matches: list[str] = []
for root in roots:
    paths = [root] if root.is_file() else [path for path in root.rglob("*") if path.is_file()]
    for path in paths:
        if path.suffix not in {".md", ".py", ".json", ".toml", ".sh"}:
            continue
        text = path.read_text(encoding="utf-8")
        for pattern in patterns:
            if pattern in text:
                matches.append(f"{path}: {pattern}")

if matches:
    print("\n".join(matches))
    raise SystemExit(1)
PY
```

Expected:

```text
```

No output and exit code `0`.

### Task 6: Self-Review Before Completion

**Files:**

- Review modified source, tests, and docs.

- [ ] **Step 1: Inspect the diff**

Run:

```bash
git diff -- scripts/turn_runtime.py tests/test_turn_runtime.py tests/test_repo_consistency.py docs/spec/2026-05-06-buddy-run-persist-test-plan.md
```

Check:

- The runtime deletion fixes root cause rather than adding a local allowlist.
- No switch parser, router, grammar contract, recommendation field, or reference switch field was introduced.
- The request text remains exact in prepared context and reservation.
- Existing prepare guardrails remain intact.
- Launcher-level retired commands remain covered and unchanged.

- [ ] **Step 2: Run final targeted verification**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_turn_runtime.py tests/test_repo_consistency.py tests/test_buddyswitch_launcher.py \
  -k "switch or legacy_command or launcher_help or prepare" \
  -q
```

Expected:

```text
all selected tests passed
```

- [ ] **Step 3: Confirm only intended files changed**

Run:

```bash
git status --short
```

Expected changed implementation files:

- `scripts/turn_runtime.py`
- `tests/test_turn_runtime.py`
- `tests/test_repo_consistency.py`
- `docs/spec/2026-05-06-buddy-run-persist-test-plan.md`

Expected planning docs for this task:

- `docs/spec/2026-05-07-switch-command-residue-cleanup-development-plan.md`
- `docs/spec/2026-05-07-switch-command-residue-cleanup-test-plan.md`

Unrelated existing untracked memo files may remain untracked. Do not delete or stage unrelated files unless explicitly asked.
