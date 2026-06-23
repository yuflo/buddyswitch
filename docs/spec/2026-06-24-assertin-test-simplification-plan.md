# AssertIn Test Simplification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans before implementing this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce brittle `assertIn` / `assertNotIn` tests while preserving the behavior contracts they currently protect.

**Architecture:** Treat containment assertions as test technique, not as a problem by itself. Keep them where they verify contract-critical presence or absence, replace them where structured assertions or smaller anchor checks express the behavior more clearly, and do the work in narrow batches with focused verification.

**Tech Stack:** Python `unittest`, `pytest`, BuddySwitch launcher/runtime tests, prompt renderer tests, CLI integration tests.

---

## Planning-Only Boundary

This document is a plan. It does not authorize production-code changes by itself.

Initial implementation should modify tests only. If a production-code issue appears while simplifying tests, stop and open a separate bug-fix task with its own failing regression test.

## Current Evidence

Checked on `main` after commit `2f04ac5`.

Direct text scan:

- `rg -n "assertIn\(|assertNotIn\(" tests | wc -l` -> 1796 call sites.
- `assertIn` call sites -> 979.
- `assertNotIn` call sites -> 817.

AST scan of direct `unittest` assertions inside `test_*` functions:

- Test functions scanned: 1019.
- Test functions using `assertIn` / `assertNotIn`: 534.
- Test functions using only `assertIn` / `assertNotIn` as unittest assertions: 76.
- Direct `assertIn` calls inside test functions: 928.
- Direct `assertNotIn` calls inside test functions: 796.

The scan methods differ because `rg` counts helper code and all textual call sites while the AST scan counts direct calls inside test functions. The conclusion is the same: containment assertions are widespread, but only a subset is brittle prompt or output wording coverage.

Highest-volume files by AST count:

- `tests/test_buddyswitch_launcher.py`: 312 direct calls.
- `tests/test_runtime_skills.py`: 149 direct calls.
- `tests/test_context_binding_env_tool.py`: 107 direct calls.
- `tests/test_repo_consistency.py`: 85 direct calls.
- `tests/test_message_available_handler.py`: 70 direct calls.
- `tests/test_artifact_env_tool.py`: 61 direct calls.
- `tests/test_env_tool_semantic_contract.py`: 53 direct calls.
- `tests/test_buddy_env_sandbox.py`: 50 direct calls.
- `tests/test_track_comment_added_handler.py`: 44 direct calls.
- `tests/test_task_input_context.py`: 32 direct calls.

Prompt / InnerTUI focused containment assertions:

- `tests/test_message_available_handler.py`: 53 prompt/TUI call sites.
- `tests/test_track_comment_added_handler.py`: 34 prompt/TUI call sites.
- `tests/test_task_input_context.py`: 28 prompt/TUI call sites.
- `tests/test_message_env_tool.py`: 7 prompt/TUI call sites.
- `tests/test_task_checkout_handler.py`: 2 prompt/TUI call sites.
- `tests/test_buddyswitch_launcher.py`: 1 prompt/TUI call site.

Source-string boundary assertions:

- Main concentration is `tests/test_daemon_communication_boundary.py`, `tests/test_daemon_core_decoupling.py`, `tests/test_message_available_handler.py`, and `tests/test_submit_turn.py`.

CLI stdout/stderr assertions:

- Main concentration is `tests/test_buddyswitch_launcher.py` with about 184 call sites matching stdout/stderr containment patterns.

## Assessment

`assertIn` is not inherently bad. It is appropriate when the tested behavior is exactly "this collection or rendered output must include this contract token." The problem is excessive line-by-line wording locks, especially for prompts where small wording improvements should not require broad test rewrites.

The tests currently mix four different purposes:

1. Contract anchors: headers, IDs, actor addresses, action names, tool names, and required forbidden tokens.
2. Full prose locks: exact explanatory sentences and multiple section labels.
3. Structural membership: actions in a list, fields in a payload, files in output.
4. Architecture guards: source-code string checks that prevent forbidden coupling or fallback paths.

Only the second group is clearly overfit. The first, third, and fourth groups should be kept or converted carefully.

## If All Containment Assertions Were Removed

Removing all `assertIn` / `assertNotIn` would create false confidence rather than test simplification.

Likely losses:

- Prompt regressions would pass silently when a renderer drops the required header, message ID, task ID, actor address, or tool name.
- The task checkpoint prompt could regress toward old checkout-only wording without a focused failure.
- Message and Track comment prompts could lose work-demand guidance or tool instructions and still route correctly at the handler level.
- Negative safety boundaries would weaken, including "do not expose message body", "do not mention fallback CLI", and "do not include side-thread internals".
- CLI tests would stop protecting user-visible output that is part of the launcher workflow.
- Source-boundary tests would stop catching reintroduced imports, fallback paths, or forbidden direct coupling.
- 76 test functions would lose most or all of their current assertion value.

Conclusion: do not remove containment assertions globally. Reduce only the brittle wording locks and convert repeated containment checks into clearer helpers or structured assertions.

## Keep / Replace Rules

Keep containment assertions when they protect one of these contracts:

- A rendered prompt or CLI output includes a dynamic ID, task ID, message ID, track ID, actor address, role, or thread ID.
- A prompt includes a tool or action name that the actor must use.
- A prompt or output excludes sensitive content, internal implementation details, fallback paths, or deprecated instructions.
- A list or set includes a legal action, permission, schema property, or expected runtime capability.
- A source boundary check guards a forbidden import or direct coupling and no stronger AST check exists yet.

Replace containment assertions when they are only:

- Exact prose wording that can be rephrased without changing behavior.
- Multiple section labels that test the same renderer path.
- Duplicate assertions already covered by a higher-level contract test.
- CLI text checks where JSON output or structured data is available.
- Source-string checks that can be replaced by AST import or symbol checks.

Do not replace:

- Negative leak checks.
- Permission and action boundary checks.
- Prompt tool-name checks.
- Dynamic routing identifiers.

## Target Outcome

The goal is not to minimize a raw count. The goal is to leave each test with enough assertions to explain the behavior it owns.

Suggested first target:

- Reduce `tests/test_task_input_context.py` prompt/TUI containment checks from 28 to roughly 12-16.
- Keep the checkpoint test at 6-8 high-signal anchors.
- Preserve all current behavior coverage for IDs, recent evidence, active-task continuation intent, stop semantics, and old checkout-only wording removal.

Suggested second target:

- Reduce message and Track comment prompt tests by grouping contract anchors through local helper assertions.
- Keep the actual required prompt contracts intact.

Suggested deferred target:

- Audit `tests/test_buddyswitch_launcher.py` stdout/stderr assertions separately. That file is high-volume but many assertions are integration-output contracts, so it should not be treated as prompt cleanup.

## Verification Guidance

This cleanup does not need new product tests by default. It changes how existing tests express prompt and output contracts; it should not change production behavior or introduce new runtime semantics.

Do not add meta-tests that assert helper behavior, raw `assertIn` counts, or the exact number of remaining containment assertions. Those checks would become another brittle test layer and would not prove product behavior. Use the existing prompt, handler, message, Track, checkout, and launcher tests as the behavior oracle.

Required verification approach:

1. Establish a baseline before editing each target file.
2. After each file-level cleanup, run that file's focused test command.
3. After all cleanup, run the combined prompt-related verification command in Task 5.
4. Run `git diff --check`.
5. Review the final diff and confirm it only simplifies tests, not renderer, handler, runtime, launcher, or env-tool behavior.

Add or change tests only if one of these is true:

- Simplification exposes a real contract that was not previously covered.
- A production-code change becomes necessary, which should stop this cleanup and become a separate bug-fix task.
- A current test was only passing because of duplicated wording checks and needs one clearer contract assertion to remain meaningful.

A lower containment count is useful evidence, not the success criterion. The success criterion is that the remaining tests still protect IDs, tool names, work-demand guidance, negative leak checks, checkpoint semantics, and deprecated wording removal while being easier to read and maintain.

## Implementation Tasks

### Task 1: Simplify task input context prompt assertions

**Files:**

- Modify: `tests/test_task_input_context.py`
- Do not modify: `scripts/env/domain/task_tui.py`

**Intent:** Keep the checkpoint behavior covered while removing sentence-by-sentence prompt locks.

- [ ] Step 1: Run the current focused test file.

Run:

```bash
python3 -m pytest tests/test_task_input_context.py -q
```

Expected:

```text
5 passed
```

- [ ] Step 2: Replace repeated membership checks for `available_actions` with set/subset assertions.

Recommended shape:

```python
self.assertGreaterEqual(set(view["available_actions"]), {"capture", "review"})
self.assertGreaterEqual(set(view["available_actions"]), {"switch_confirm", "checkout"})
```

This preserves membership behavior without repeated single-token assertions.

- [ ] Step 3: Reduce `test_task_tui_renders_task_view_model_without_old_operation_wording`.

Keep these anchors:

```python
for expected in (
    "[TASK CONTEXT]",
    "Current Anchor: task-0001-clean-runtime-environment",
    "task-0002-next-task",
    "Pending Switch: confirm-0001",
    "Checkout: task.checkout next=continue|finish|block",
    "Switch request.",
):
    with self.subTest(expected=expected):
        self.assertIn(expected, tui)
```

Keep the existing forbidden-token loop.

- [ ] Step 4: Reduce `test_stop_task_tui_renders_checkpoint_for_status_and_next_work`.

Keep these anchors:

```python
for expected in (
    "[TASK CHECKPOINT]",
    "Previous turn completed: turn_123",
    "task-0003-clean-runtime-env - Clean runtime env",
    "Focused test added.",
    "If the task is active, keep working in this turn when there is a clear path forward.",
    "task.checkout continue: pause an unfinished task",
):
    with self.subTest(expected=expected):
        self.assertIn(expected, tui)
```

Keep these negative checks:

```python
for forbidden in (
    "[TASK CHECKOUT]",
    "No capture, select, switch_request, or switch_confirm in checkout.",
    "Stay silent if no checkout update is needed.",
    "task.propose",
    "task.confirm",
    "Task Handling Cue",
):
    with self.subTest(forbidden=forbidden):
        self.assertNotIn(forbidden, tui)
```

- [ ] Step 5: Run the focused test file again.

Run:

```bash
python3 -m pytest tests/test_task_input_context.py -q
```

Expected:

```text
5 passed
```

- [ ] Step 6: Check diff scope.

Run:

```bash
git diff -- tests/test_task_input_context.py
```

Expected: only assertion simplification, no production-code change.

### Task 2: Add local prompt-contract helpers for message prompts

**Files:**

- Modify: `tests/test_message_available_handler.py`
- Do not modify: `scripts/env/domain/messages.py`
- Do not modify: `tools/launcher/message_available_handler.py`

**Intent:** Reduce repeated prompt assertion noise while preserving message prompt contracts.

- [ ] Step 1: Run the current focused test file.

Run:

```bash
python3 -m pytest tests/test_message_available_handler.py -q
```

Expected: all tests pass.

- [ ] Step 2: Add a local helper near the test class, not a shared framework.

Recommended helper:

```python
def assert_contains_all(testcase: unittest.TestCase, text: str, expected: tuple[str, ...]) -> None:
    for token in expected:
        with testcase.subTest(token=token):
            testcase.assertIn(token, text)


def assert_contains_none(testcase: unittest.TestCase, text: str, forbidden: tuple[str, ...]) -> None:
    for token in forbidden:
        with testcase.subTest(token=token):
            testcase.assertNotIn(token, text)
```

Keep it local because this is a cleanup, not a new testing framework.

- [ ] Step 3: Replace repeated positive prompt checks in parent, side-triage, and needs-parent tests with grouped contract anchors.

Parent prompt anchors must include:

```python
(
    "[MESSAGE AVAILABLE]",
    "msg-readable",
    'From: {"actor_id": "act-pm-readable", "role_id": "pm"}',
    'To: {"actor_id": "act-dev-daemon", "role_id": "dev"}',
    "Work-demand guidance:",
    "acknowledgement alone is usually not completion",
    "task.current",
    "task.capture/task.select",
    "message__get",
    "message__send",
    "message__mark",
)
```

Side-triage anchors must include:

```python
(
    "[MESSAGE TRIAGE]",
    "msg-readable",
    "Side triage should not silently convert parent-level work into a lightweight acknowledgement.",
    "Outcome B: Parent must process it.",
    "The message assigns concrete work to this actor",
    "message__get",
    "message__send",
    "message__mark",
)
```

Needs-parent anchors must include:

```python
(
    "[MESSAGE NEEDS PARENT]",
    "Reason from side triage:",
    "Requires parent context.",
    "task.current",
    "task.capture/task.select",
    "message__get",
    "message__send",
    "message__mark",
)
```

- [ ] Step 4: Preserve negative checks.

Keep these forbidden-token checks:

```python
(
    "message__list",
    "Fallback CLI",
    "python3 scripts/env/client.py",
    "message body",
    "mailbox.local_trigger",
    "message.parent_required",
    "parent_thread_id",
    "side_thread_id",
    "codex-remote",
)
```

When the current test builds a forbidden token through string concatenation to avoid accidental source hits, keep that pattern.

- [ ] Step 5: Run the focused tests.

Run:

```bash
python3 -m pytest tests/test_message_available_handler.py -q
```

Expected: all tests pass.

### Task 3: Add local prompt-contract helpers for Track comment prompts

**Files:**

- Modify: `tests/test_track_comment_added_handler.py`
- Do not modify: `scripts/env/domain/track_comments.py`
- Do not modify: `tools/launcher/track_comment_added_handler.py`

**Intent:** Mirror the message prompt cleanup while preserving Track-specific contracts.

- [ ] Step 1: Run the current focused test file.

Run:

```bash
python3 -m pytest tests/test_track_comment_added_handler.py -q
```

Expected: all tests pass.

- [ ] Step 2: Add local `assert_contains_all` and `assert_contains_none` helpers if they do not already exist in the file after Task 2.

Use the same local helper pattern as Task 2. Do not create a shared test utility yet.

- [ ] Step 3: Replace repeated parent Track prompt checks with grouped anchors.

Parent Track anchors must include:

```python
(
    "[TRACK COMMENT ATTENTION]",
    str(comment["id"]),
    str(comment["track_id"]),
    "Track tools remain the source of truth",
    "Task tools are only for this actor's private work tracking",
    "Work-demand guidance:",
    "acknowledgement alone is usually not completion",
    "task.current",
    "task.capture/task.select",
    "track.open",
    "track.list_comments",
    "track.add_comment",
    "track.resolve_comment_thread",
)
```

- [ ] Step 4: Replace repeated side-triage Track prompt checks with grouped anchors.

Side Track anchors must include:

```python
(
    "[TRACK COMMENT TRIAGE]",
    "Side triage is for quick Track-thread handling only.",
    "Work-demand guidance:",
    "do not present it as done",
    "Leave substantive work for the parent/main path",
    "track.open",
    "track.list_comments",
    "track.add_comment",
    "track.resolve_comment_thread",
    "Use only Track tools for this comment.",
)
```

- [ ] Step 5: Preserve forbidden-token checks.

Keep forbidden checks for:

```python
(
    "notification.",
    "nc.notification",
    "daemon",
    "mailbox",
    "message.available",
    "absorbed",
    "replied",
    "needs_parent",
    "parent_thread_id",
    "side_thread_id",
    "message__mark",
)
```

- [ ] Step 6: Run the focused tests.

Run:

```bash
python3 -m pytest tests/test_track_comment_added_handler.py -q
```

Expected: all tests pass.

### Task 4: Re-check launcher output tests without broad cleanup

**Files:**

- Inspect only: `tests/test_buddyswitch_launcher.py`

**Intent:** Avoid mixing prompt cleanup with large CLI integration cleanup.

- [ ] Step 1: Count stdout/stderr containment assertions in the file.

Run:

```bash
rg -n "assert(In|NotIn)\([^\\n]+, .*stdout|assert(In|NotIn)\([^\\n]+, .*stderr" tests/test_buddyswitch_launcher.py | wc -l
```

Expected current scale: about 184 matching lines.

- [ ] Step 2: Do not edit this file in the first cleanup batch except for already-covered prompt title assertions.

Reason: most of this file validates integration output and fake Codex service behavior. It should get its own focused cleanup plan if it remains a bottleneck.

- [ ] Step 3: Record a follow-up note in the implementation summary.

Required summary sentence:

```text
Launcher stdout/stderr containment assertions were audited but intentionally left unchanged because they protect integration-facing output and need a separate pass.
```

### Task 5: Verify combined prompt cleanup

**Files:**

- Test: `tests/test_task_input_context.py`
- Test: `tests/test_message_available_handler.py`
- Test: `tests/test_track_comment_added_handler.py`
- Test: `tests/test_message_env_tool.py`
- Test: `tests/test_task_checkout_handler.py`
- Test: `tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_fake_codex_real_completed_event_triggers_one_stop_task_tui_prompt`

- [ ] Step 1: Run focused prompt-related tests.

Run:

```bash
python3 -m pytest \
  tests/test_task_input_context.py \
  tests/test_message_available_handler.py \
  tests/test_track_comment_added_handler.py \
  tests/test_message_env_tool.py \
  tests/test_task_checkout_handler.py \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_fake_codex_real_completed_event_triggers_one_stop_task_tui_prompt \
  -q
```

Expected: all selected tests pass.

- [ ] Step 2: Run whitespace check.

Run:

```bash
git diff --check
```

Expected: no output and exit code 0.

- [ ] Step 3: Compare containment counts before and after.

Run:

```bash
rg -n "assertIn\(|assertNotIn\(" tests/test_task_input_context.py tests/test_message_available_handler.py tests/test_track_comment_added_handler.py | wc -l
```

Expected: lower than the current combined count of 146 for these three files, while all focused tests still pass.

- [ ] Step 4: Review the diff for scope.

Run:

```bash
git diff -- tests/test_task_input_context.py tests/test_message_available_handler.py tests/test_track_comment_added_handler.py
```

Expected: test assertion cleanup only. No renderer, handler, runtime, launcher, or env-tool behavior changes.

## Stop Conditions

Stop implementation and ask for review if any of these happen:

- A prompt renderer or production runtime file appears to require changes.
- A simplified test no longer fails when a known critical token is removed locally during a manual sanity check.
- A helper starts spreading across unrelated files as a generic test framework.
- A test becomes less clear than the original direct assertions.
- Any focused prompt test fails for a reason other than expected assertion refactoring.

## Definition of Done

This cleanup is done when:

- `tests/test_task_input_context.py` has fewer prompt wording locks and still protects checkpoint behavior.
- Message and Track prompt tests use grouped local contract anchors instead of long repeated assertion blocks.
- Negative safety checks remain present.
- No production code changes are included.
- Focused prompt-related tests pass.
- `git diff --check` passes.
- The implementation summary states which assertion categories were reduced and which were intentionally left unchanged.
