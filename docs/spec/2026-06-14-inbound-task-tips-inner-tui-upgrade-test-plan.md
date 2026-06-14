# Inbound Task Tips InnerTUI Upgrade Test Plan

Date: 2026-06-14
Source: `docs/memo/2026-06-14-inbound-task-tips-inner-tui-upgrade.md`
Status: Phase 1 reviewed plan, ready for Phase 3 execution

## Goal

Prove inbound message and Track comment InnerTUI prompts clearly distinguish lightweight communication from concrete work demands without changing task, message, or Track tool semantics.

This is a prompt rendering task. Tests should prove reviewed prompt content and handler submission surfaces, not new tool behavior.

## Resource Safety

Follow `docs/bitter/2026-05-26-test-resource-lifecycle-principles.md`.

Default validation uses renderer and handler tests with fake runtimes:

```bash
python -m pytest tests/test_message_available_handler.py tests/test_track_comment_added_handler.py -q
python -m pytest tests/test_message_env_tool.py -q
```

`tests/test_message_available_handler.py` and `tests/test_track_comment_added_handler.py` do not start real daemons, app servers, brokers, browsers, ports, or detached processes. `tests/test_message_env_tool.py` uses in-process env-tool dispatch and patched parent message handling; it should not start persistent services.

If a verification path starts a service unexpectedly, stop broad verification, inspect the start boundary, add lifecycle cleanup, and rerun only the focused failing scope first.

## Functional Requirements To Prove

1. `[MESSAGE AVAILABLE]` includes runtime context, conditional work-demand guidance, `task.current`, `task.capture/task.select`, and the reviewed message tool steps.
2. `[MESSAGE TRIAGE]` includes runtime context, warns that side triage must not turn parent-level work into lightweight acknowledgement, and adds concrete assigned work as a `needs_parent` condition.
3. `[MESSAGE NEEDS PARENT]` includes the side-triage reason, runtime context, conditional durable task capture guidance, and `task.current` plus `task.capture/task.select`.
4. `[TRACK COMMENT ATTENTION]` includes Track source-truth guidance, conditional work-demand guidance, task capture tips, and Track-thread reply/closure steps.
5. `[TRACK COMMENT TRIAGE]` includes lightweight side-triage guidance, concrete-work caution, and stays inside Track tools.
6. Track comment prompts do not introduce message dispositions such as `absorbed`, `replied`, or `needs_parent`.
7. Prompt construction is split into small private helpers inside `scripts/env/domain/messages.py` and `scripts/env/domain/track_comments.py`.
8. Existing handler routing remains unchanged: idle parent submits the parent prompt, running parent submits the side prompt, and unavailable parent activity fails.
9. Existing `message.mark(disposition="needs_parent")` handoff still submits a parent-required prompt before saving the disposition.

## Focused Test Matrix

### Message Prompt Renderer And Handler Tests

Target file: `tests/test_message_available_handler.py`.

Add or update assertions in `test_message_available_handler_routes_idle_parent_to_parent_prompt`:

- Prompt contains `[MESSAGE AVAILABLE]`.
- Prompt contains `Required action:`.
- Prompt contains `Runtime context:`.
- Prompt contains `Work-demand guidance:`.
- Prompt contains `concrete work demand for this actor`.
- Prompt contains `acknowledgement alone is usually not completion`.
- Prompt contains `task.current`.
- Prompt contains `task.capture/task.select`.
- Prompt contains `smallest substantive work`.
- Prompt still contains `message__get`, `message__conversation`, `message__send`, and `message__mark`.
- Prompt still excludes `message__list`, `Fallback CLI`, `python3 scripts/env/client.py`, and raw message body wording.

Add or update assertions in `test_message_available_handler_routes_running_parent_to_side_triage`:

- Prompt contains `[MESSAGE TRIAGE]`.
- Prompt contains `Runtime context:`.
- Prompt contains `Side triage should not silently convert parent-level work into a lightweight acknowledgement.`
- Prompt contains `Outcome B: Parent must process it.`
- Prompt contains `The message assigns concrete work to this actor`.
- Prompt contains `should not be completed as a side-triage acknowledgement`.
- Prompt contains `the reason must cite the specific condition`.
- Prompt still contains message tool names and still excludes mailbox/daemon/internal terms.

Add or update assertions in `test_parent_required_prompt_renderer_is_message_owned`:

- Prompt contains `[MESSAGE NEEDS PARENT]`.
- Prompt contains `Reason from side triage:`.
- Prompt contains the reason text.
- Prompt contains `Runtime context:`.
- Prompt contains `task.current`.
- Prompt contains `task.capture/task.select`.
- Prompt contains `smallest substantive work`.
- Prompt still contains message tool names and excludes handler/internal trigger terms.

Add a source-shape test in the same file:

- `scripts/env/domain/messages.py` contains private helpers named:
  - `_message_header`
  - `_message_runtime_context`
  - `_message_parent_steps`
  - `_message_side_triage_steps`
  - `_message_parent_work_demand_tips`
  - `_message_side_work_demand_tips`
  - `_message_finish`
- Public renderers still exist with the same names and signatures.

Focused command:

```bash
python -m pytest tests/test_message_available_handler.py -q
```

Expected red result before implementation:

```text
FAILED ... 'Runtime context:' not found in prompt
```

### Track Comment Prompt Renderer And Handler Tests

Target file: `tests/test_track_comment_added_handler.py`.

Update `test_track_comment_handler_routes_idle_parent_to_parent_prompt`:

- Prompt contains `[TRACK COMMENT ATTENTION]`.
- Prompt contains `Required action:`.
- Prompt contains `Runtime context:`.
- Prompt contains `Track tools remain the source of truth`.
- Prompt contains `Task tools are only for this actor's private work tracking`.
- Prompt contains `Work-demand guidance:`.
- Prompt contains `acknowledgement alone is usually not completion`.
- Prompt contains `task.current`.
- Prompt contains `task.capture/task.select`.
- Prompt contains `reply with the result in the Track thread`.
- Prompt still contains `track.open`, `track.list_comments`, `track.add_comment`, and `track.resolve_comment_thread`.
- Prompt still excludes message and daemon internals.

Update `test_track_comment_handler_routes_running_parent_to_side_triage`:

- Prompt contains `[TRACK COMMENT TRIAGE]`.
- Prompt contains `Runtime context:`.
- Prompt contains `Side triage is for quick Track-thread handling only.`
- Prompt contains `Work-demand guidance:`.
- Prompt contains `do not present it as done`.
- Prompt contains `Leave substantive work for the parent/main path`.
- Prompt contains `Use only Track tools for this comment.`
- Prompt still contains Track tool names.
- Prompt does not contain `needs_parent`, `absorbed`, `replied`, `message.available`, `message__mark`, `parent_thread_id`, or `side_thread_id`.

Add a source-shape test in the same file:

- `scripts/env/domain/track_comments.py` contains private helpers named:
  - `_track_comment_header`
  - `_track_comment_runtime_context`
  - `_track_comment_parent_steps`
  - `_track_comment_side_steps`
  - `_track_comment_parent_work_demand_tips`
  - `_track_comment_side_work_demand_tips`
  - `_track_comment_finish`
- Public renderers still exist with the same names and signatures.

Focused command:

```bash
python -m pytest tests/test_track_comment_added_handler.py -q
```

Expected red result before implementation:

```text
FAILED ... 'Work-demand guidance:' not found in prompt
```

### Message Needs-Parent Env Tool Regression

Target file: `tests/test_message_env_tool.py`.

Update `test_message_mark_needs_parent_stores_reason_and_requests_parent_prompt`:

- Existing assertions for stored disposition and parent call remain.
- Parent prompt contains `[MESSAGE NEEDS PARENT]`.
- Parent prompt contains the side-triage reason.
- Parent prompt contains `Runtime context:`.
- Parent prompt contains `task.current`.
- Parent prompt contains `task.capture/task.select`.
- Parent prompt contains `If the requested work is small enough to complete now`.

Focused command:

```bash
python -m pytest tests/test_message_env_tool.py::MessageEnvToolTests::test_message_mark_needs_parent_stores_reason_and_requests_parent_prompt -q
```

Expected red result before implementation:

```text
FAILED ... 'task.capture/task.select' not found in prompt
```

## Broader Verification

After the focused renderer and handler tests pass:

```bash
python -m pytest tests/test_message_available_handler.py tests/test_track_comment_added_handler.py -q
python -m pytest tests/test_message_env_tool.py -q
```

No full launcher or browser suite is required for this prompt-only change unless focused verification exposes a broader integration issue.

## Phase 1 Review

Spec coverage:

- The tests cover all five prompt surfaces named in the memo.
- The tests cover the reviewed work-demand content, source-truth guidance, and side-triage boundaries.
- The Track comment tests explicitly prevent message disposition semantics from entering Track comment prompts.
- The env-tool regression covers the existing `message.mark(needs_parent)` parent-handoff prompt path.

Resource lifecycle:

- Focused tests use fake runtimes and in-process dispatch.
- No planned test starts a persistent daemon, broker, browser, app server, port, or detached worker.

Rebuild-forward check:

- The plan replaces the existing prompt literals with sectioned domain-local helpers.
- It does not add prompt frameworks, rule engines, compatibility paths, or alternate prompt modes.
