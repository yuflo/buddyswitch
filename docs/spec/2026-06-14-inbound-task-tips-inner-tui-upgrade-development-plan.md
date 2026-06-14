# Inbound Task Tips InnerTUI Upgrade Development Plan

Date: 2026-06-14
Source: `docs/memo/2026-06-14-inbound-task-tips-inner-tui-upgrade.md`
Status: Phase 1 reviewed plan, ready for Phase 3 execution

## Goal

Replace under-specified inbound message and Track comment prompt text with reviewed sectioned InnerTUI prompts that make concrete work demands visible without changing tool semantics.

## Architecture

Prompt ownership stays in the existing source-owned domain modules. `scripts/env/domain/messages.py` owns direct-message prompt sections, and `scripts/env/domain/track_comments.py` owns Track comment prompt sections. Handlers and env tools keep calling the same public render functions, so the runtime routing and tool contracts do not change.

## Files

Modify:

- `scripts/env/domain/messages.py`: replace large public prompt literals with private section helpers and reviewed message prompt content.
- `scripts/env/domain/track_comments.py`: replace large public prompt literals with private section helpers and reviewed Track comment prompt content.
- `tests/test_message_available_handler.py`: assert reviewed message prompt content and helper structure.
- `tests/test_track_comment_added_handler.py`: assert reviewed Track comment prompt content and helper structure.
- `tests/test_message_env_tool.py`: assert `message.mark(needs_parent)` parent prompt includes durable work guidance.

Do not modify:

- `tools/launcher/message_available_handler.py`: handler routing should stay unchanged.
- `tools/launcher/track_comment_added_handler.py`: handler routing and validation should stay unchanged.
- `scripts/env/tools/message/_impl.py`: `needs_parent` semantics and save ordering should stay unchanged.
- task tool schemas, role policy, resource locks, `message.send`, `message.mark`, `track.add_comment`, `track.list_comments`, or `track.resolve_comment_thread`.

## Implementation Tasks

### Task 1: Add red tests for message prompt work-demand content and helper shape

Edit `tests/test_message_available_handler.py`.

Add:

```python
MESSAGE_DOMAIN_PATH = ROOT / "scripts" / "env" / "domain" / "messages.py"
```

Update `test_message_available_handler_routes_idle_parent_to_parent_prompt` with:

```python
            self.assertIn("Required action:", prompt)
            self.assertIn("Runtime context:", prompt)
            self.assertIn("Work-demand guidance:", prompt)
            self.assertIn("concrete work demand for this actor", prompt)
            self.assertIn("acknowledgement alone is usually not completion", prompt)
            self.assertIn("task.current", prompt)
            self.assertIn("task.capture/task.select", prompt)
            self.assertIn("smallest substantive work", prompt)
```

Update `test_message_available_handler_routes_running_parent_to_side_triage` with:

```python
            self.assertIn("Runtime context:", prompt)
            self.assertIn("Side triage should not silently convert parent-level work into a lightweight acknowledgement.", prompt)
            self.assertIn("Outcome B: Parent must process it.", prompt)
            self.assertIn("The message assigns concrete work to this actor", prompt)
            self.assertIn("should not be completed as a side-triage acknowledgement", prompt)
            self.assertIn("the reason must cite the specific condition", prompt)
```

Update `test_parent_required_prompt_renderer_is_message_owned` with:

```python
        self.assertIn("Reason from side triage:", prompt)
        self.assertIn("Runtime context:", prompt)
        self.assertIn("task.current", prompt)
        self.assertIn("task.capture/task.select", prompt)
        self.assertIn("smallest substantive work", prompt)
```

Add:

```python
    def test_message_prompt_renderers_are_sectioned_domain_helpers(self) -> None:
        source = MESSAGE_DOMAIN_PATH.read_text(encoding="utf-8")

        for helper in (
            "_message_header",
            "_message_runtime_context",
            "_message_parent_steps",
            "_message_side_triage_steps",
            "_message_parent_work_demand_tips",
            "_message_side_work_demand_tips",
            "_message_finish",
        ):
            with self.subTest(helper=helper):
                self.assertIn(f"def {helper}(", source)
        self.assertIn("def render_parent_message_prompt(", source)
        self.assertIn("def render_side_triage_prompt(", source)
        self.assertIn("def render_parent_required_prompt(", source)
```

Run:

```bash
python -m pytest tests/test_message_available_handler.py -q
```

Expected before implementation:

```text
FAILED ... 'Runtime context:' not found in prompt
```

### Task 2: Replace message prompt literals with section helpers

Edit `scripts/env/domain/messages.py`.

Add these private helpers near `_format_actor_address`:

```python
def _message_header(
    title: str,
    message_id: str,
    source_actor_address: ActorAddress | dict[str, Any],
    target_actor_address: ActorAddress | dict[str, Any],
) -> str:
    return (
        f"[{title}]\n\n"
        f"Message id: {message_id}\n"
        f"From: {_format_actor_address(source_actor_address)}\n"
        f"To: {_format_actor_address(target_actor_address)}\n"
    )


def _message_runtime_context(*, side: bool = False, parent_required: bool = False) -> str:
    if parent_required:
        return (
            "Runtime context:\n"
            "This message already crossed the side-triage threshold.\n"
            "It may require active-work adjustment, a decision, durable task capture, or substantive follow-through before reply.\n"
        )
    if side:
        return (
            "Runtime context:\n"
            "A direct message may be simple communication, status sync, clarification, or a concrete work demand.\n"
            "Side triage should not silently convert parent-level work into a lightweight acknowledgement.\n"
        )
    return (
        "Runtime context:\n"
        "A direct message may be simple communication, status sync, clarification, or a concrete work demand for this actor.\n"
        "After reading the message, decide what kind of attention it needs.\n"
    )


def _message_parent_work_demand_tips(*, parent_required: bool = False) -> str:
    if parent_required:
        return (
            "Work-demand guidance:\n"
            "If the message assigns concrete work to this actor, acknowledgement alone is usually not completion.\n"
            "Consider task.current and task.capture/task.select when the work should become durable actor work.\n"
            "If the requested work is small enough to complete now, do the smallest substantive work and send the result.\n"
            "If only coordination is needed, reply normally.\n"
        )
    return (
        "Work-demand guidance:\n"
        "If the message assigns concrete work to this actor, acknowledgement alone is usually not completion.\n"
        "For durable actor work, consider task.current and task.capture/task.select before finishing.\n"
        "If the requested work is small enough to complete now, do the smallest substantive work and send the result instead of only saying you will do it.\n"
        "If the message is only FYI, status sync, or lightweight clarification, reply or mark absorbed normally.\n"
    )
```

Add `_message_parent_steps`, `_message_side_triage_steps`, `_message_side_work_demand_tips`, and `_message_finish` using the exact reviewed baseline from the memo.

Replace the bodies of:

- `render_parent_message_prompt`
- `render_side_triage_prompt`
- `render_parent_required_prompt`

with joins of the helper sections. Keep their public signatures unchanged.

Run:

```bash
python -m pytest tests/test_message_available_handler.py -q
```

Expected:

```text
all tests pass
```

### Task 3: Add red tests for Track comment prompt work-demand content and helper shape

Edit `tests/test_track_comment_added_handler.py`.

Add:

```python
TRACK_COMMENT_DOMAIN_PATH = ROOT / "scripts" / "env" / "domain" / "track_comments.py"
```

Update `test_track_comment_handler_routes_idle_parent_to_parent_prompt` with:

```python
        self.assertIn("Required action:", prompt)
        self.assertIn("Runtime context:", prompt)
        self.assertIn("Track tools remain the source of truth", prompt)
        self.assertIn("Task tools are only for this actor's private work tracking", prompt)
        self.assertIn("Work-demand guidance:", prompt)
        self.assertIn("acknowledgement alone is usually not completion", prompt)
        self.assertIn("task.current", prompt)
        self.assertIn("task.capture/task.select", prompt)
        self.assertIn("reply with the result in the Track thread", prompt)
```

Update `test_track_comment_handler_routes_running_parent_to_side_triage` with:

```python
        self.assertIn("Runtime context:", prompt)
        self.assertIn("Side triage is for quick Track-thread handling only.", prompt)
        self.assertIn("Work-demand guidance:", prompt)
        self.assertIn("do not present it as done", prompt)
        self.assertIn("Leave substantive work for the parent/main path", prompt)
        self.assertIn("Use only Track tools for this comment.", prompt)
        self.assertNotIn("absorbed", prompt)
        self.assertNotIn("replied", prompt)
        self.assertNotIn("message__mark", prompt)
```

Add:

```python
    def test_track_comment_prompt_renderers_are_sectioned_domain_helpers(self) -> None:
        source = TRACK_COMMENT_DOMAIN_PATH.read_text(encoding="utf-8")

        for helper in (
            "_track_comment_header",
            "_track_comment_runtime_context",
            "_track_comment_parent_steps",
            "_track_comment_side_steps",
            "_track_comment_parent_work_demand_tips",
            "_track_comment_side_work_demand_tips",
            "_track_comment_finish",
        ):
            with self.subTest(helper=helper):
                self.assertIn(f"def {helper}(", source)
        self.assertIn("def render_parent_track_comment_prompt(", source)
        self.assertIn("def render_side_track_comment_prompt(", source)
```

Run:

```bash
python -m pytest tests/test_track_comment_added_handler.py -q
```

Expected before implementation:

```text
FAILED ... 'Work-demand guidance:' not found in prompt
```

### Task 4: Replace Track comment prompt literals with section helpers

Edit `scripts/env/domain/track_comments.py`.

Add private helpers:

- `_track_comment_header`
- `_track_comment_runtime_context`
- `_track_comment_parent_steps`
- `_track_comment_side_steps`
- `_track_comment_parent_work_demand_tips`
- `_track_comment_side_work_demand_tips`
- `_track_comment_finish`

Use the reviewed baseline text from the memo exactly apart from line wrapping.

Replace the bodies of:

- `render_parent_track_comment_prompt`
- `render_side_track_comment_prompt`

with joins of the helper sections. Keep their public signatures unchanged.

Run:

```bash
python -m pytest tests/test_track_comment_added_handler.py -q
```

Expected:

```text
all tests pass
```

### Task 5: Add and satisfy `message.mark(needs_parent)` parent prompt regression

Edit `tests/test_message_env_tool.py`.

In `test_message_mark_needs_parent_stores_reason_and_requests_parent_prompt`, add:

```python
        self.assertIn("Runtime context:", prompt)
        self.assertIn("task.current", prompt)
        self.assertIn("task.capture/task.select", prompt)
        self.assertIn("If the requested work is small enough to complete now", prompt)
```

Run:

```bash
python -m pytest tests/test_message_env_tool.py::MessageEnvToolTests::test_message_mark_needs_parent_stores_reason_and_requests_parent_prompt -q
```

Expected after Task 2:

```text
1 passed
```

### Task 6: Focused verification

Run:

```bash
python -m pytest tests/test_message_available_handler.py tests/test_track_comment_added_handler.py -q
```

Expected:

```text
all tests pass
```

### Task 7: Broader relevant verification

Run:

```bash
python -m pytest tests/test_message_env_tool.py -q
```

Expected:

```text
all tests pass
```

### Task 8: Final review for prompt-only scope

Search:

```bash
rg "additionalContext|PromptBuilder|needs_parent|absorbed|replied|task.capture/task.select|Work-demand guidance|Runtime context" scripts/env/domain tools/launcher tests/test_message_available_handler.py tests/test_track_comment_added_handler.py tests/test_message_env_tool.py
```

Review:

- `needs_parent` remains message-only.
- Track comment prompts do not contain `absorbed`, `replied`, or `needs_parent`.
- Handler files have no routing changes.
- No task-tool schemas, policies, locks, or Track comment semantics changed.

Run:

```bash
git diff --check
```

Expected:

```text
no output
```

## Phase 1 Review

Spec coverage:

- The tasks cover all five prompt surfaces named in the memo.
- The implementation stays local to the two domain modules.
- Existing public renderer APIs and handler routing stay unchanged.
- The `message.mark(needs_parent)` parent-required handoff path remains covered.

Execution clarity:

- Each task names exact files, content assertions, implementation points, and verification commands.
- The plan uses red prompt tests before changing prompt renderers.

Rebuild-forward check:

- Large prompt literals are replaced by concrete private helpers in each domain.
- No generic prompt framework, rule engine, DSL, compatibility switch, or alternate prompt mode is introduced.
