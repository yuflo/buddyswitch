# IM Message Frame Capability Forward Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** For `source.type == "im.message.created"` Task Sys frames, allow both side and parent frames to use the full Central IM message tool surface while preserving Task Sys task scope and removing the old source-bound-only frame contract.

**Architecture:** Message capability semantics stay owned by the message tool contract and IM product core. Task Sys owns frame lifecycle and task closure, not a narrower duplicate message authorization model. The frame renderer should provide source-specific guidance for IM inbound tasks, then defer concrete message reads/writes to `message.contacts`, `message.list`, `message.get`, `message.conversation`, `message.send`, and `message.mark`.

**Tech Stack:** Python 3, Task Sys launcher runtime, BuddySwitch env tool schemas, Central IM services, unittest/pytest, scoped live-surface residue scans.

---

## Read-In Summary

`docs/bitter` was reviewed before this plan. The principles applied here are:

- A semantic change is unfinished while any live surface still teaches old semantics.
- Fix the layer that owns the wrong contract; do not compensate with larger prompts.
- Do not add one narrow special case at the wrong shared boundary.
- Product semantics belong in the product core and tool contracts; runtime frames are projections of the active task boundary.
- Keep the end-to-end promise alive with acceptance coverage, not only local component tests.
- Do not run broad service-starting verification without lifecycle proof. This plan uses focused non-daemon tests and scans.

## Restated Task Objective

Current IM Task Sys frames teach this old behavior:

```text
im.message.created side/parent frame
  -> only source-bound reply with message.send(reply_to=source_message_id, ...)
  -> or source-bound absorb with message.mark(message_id=source_message_id, disposition=absorbed)
  -> no target_identity_id send from side
  -> parent frame remains source-bound even after task_sys.need_parent
```

Target behavior:

```text
im.message.created side/parent frame
  -> may use the full message tool surface to complete the current IM-source task
  -> read with message.contacts / message.list / message.get / message.conversation
  -> send with message.send(reply_to=...) or message.send(target_identity_id=...)
  -> absorb with message.mark(..., disposition=absorbed) where the message tool contract allows it
  -> close the Task Sys task after required message work succeeds
```

The change is forward-only. Do not preserve the old source-bound-only frame contract behind a feature flag, relation check, compatibility branch, or alternate wording.

## Scope

In scope:

- `source.type == "im.message.created"` side frame guidance.
- `source.type == "im.message.created"` parent frame guidance.
- Live shared skill guidance that teaches Task Sys frame behavior.
- Task Sys tool response/schema wording that still says `source-bound work`.
- Focused runtime-rendering and live-surface tests.
- Scoped residue scans over live surfaces.

Out of scope:

- Refactoring `reply_to` into a separate source-completion workflow.
- Changing `message.send`, `message.mark`, `message.list`, `message.conversation`, or resolver behavior.
- Changing external IM API contracts.
- Changing `user.input` semantics beyond removing stale IM-only wording from generic side-frame text.
- Editing runtime state under `buddyswitch/objects/**` or shared-root state.

## Key Problems Found

- `tools/launcher/task_sys_runtime.py` side-frame text says new outbound communication requires `task_sys.need_parent`, which contradicts opening `message.send(target_identity_id=...)` for IM tasks.
- `tools/launcher/task_sys_runtime.py` side-frame text contains IM-specific source-bound closure rules even when the source is `user.input`.
- `tools/launcher/task_sys_runtime.py` parent-frame `im.message.created` branch only allows source reply, source absorb, and close.
- `buddyswitch/skills/shared/task-management/SKILL.md` still teaches parent frames to complete source-bound work and IM sources to reply/mark before close.
- `scripts/env/tools/task_sys/tool.py` and `scripts/env/tools/task_sys/_impl.py` still expose `source-bound work/task` wording through live tool surfaces.
- `tests/test_task_sys_runtime_executor.py` asserts the old parent-frame IM closure order and explicitly rejects `message.send(target_identity_id=..., content=...)`.
- `tests/test_task_management_skill_architecture.py` asserts old IM-only skill wording.

## Target Module Boundaries

| Module | Owns | Must Not Own |
|---|---|---|
| `env.services.messages` and message tool definitions | Message read/write semantics, target resolver behavior, disposition behavior, visible conversation/event contracts | Task Sys frame lifecycle |
| `tools/launcher/task_sys_runtime.py` | Rendering source-specific Task Sys frame instructions and lifecycle operations | A narrower duplicate message permission model |
| `scripts/env/tools/task_sys/*` | Task Sys read/close/need_parent tool semantics and response wording | Message-specific source-bound restrictions |
| `buddyswitch/skills/shared/task-management/SKILL.md` | Short workflow guidance for Task Sys frame handling | Full message schema or obsolete source-bound-only rules |
| Tests | Behavior and live-surface contract proof | Historical memo enforcement |

## End-To-End Contract

The acceptance contract for this plan is:

```text
actor receives im.message.created
  -> Task Sys starts side frame
  -> frame teaches all message tool actions as available for the current IM task
  -> side may send by target_identity_id without need_parent when message work is sufficient
  -> if side escalates to parent, parent frame also teaches all message tool actions
  -> agent closes the Task Sys task after required message work
```

This plan verifies the changed contract through rendered frame text, live-surface residue checks, and existing message tool contract tests. The implementation stays focused on frame capability contracts because the underlying message send/read tools already own and test IM delivery semantics.

## Implementation Tasks

### Task 1: Update Runtime Frame Contract Tests First

**Files:**
- Modify: `tests/test_task_sys_runtime_executor.py`

- [ ] **Step 1: Add IM-source side-frame fixture**

Add this helper near `_instruction()`:

```python
    def _im_instruction(self) -> dict[str, Any]:
        instruction = self._instruction()
        instruction["type"] = "start_side"
        instruction["task_id"] = "task-im-message-created-abcdef123456"
        frame = instruction["frame"]
        frame["task_id"] = "task-im-message-created-abcdef123456"
        frame["source"] = {
            "type": "im.message.created",
            "ref": {
                "message_id": "msg-source-1",
                "conversation_id": "conv-source-1",
                "event_id": "imev-source-1",
            },
        }
        frame["context"] = {
            "message_id": "msg-source-1",
            "conversation_id": "conv-source-1",
            "event_id": "imev-source-1",
        }
        return instruction
```

- [ ] **Step 2: Add side-frame full message capability test**

Add this test after `test_render_side_frame_is_task_sys_scoped_and_names_only_two_results`:

```python
    def test_render_side_frame_for_im_source_allows_full_message_tool_surface(self) -> None:
        text = self.module.render_side_frame(self._im_instruction()["frame"])

        self.assertIn("For an IM source message:", text)
        self.assertIn("message.contacts", text)
        self.assertIn("message.list", text)
        self.assertIn("message.get", text)
        self.assertIn("message.conversation", text)
        self.assertIn("message.send(reply_to=source_message_id, content=...)", text)
        self.assertIn("message.send(target_identity_id=..., content=...)", text)
        self.assertIn("message.mark(message_id=..., disposition=absorbed)", text)
        self.assertIn("task_sys.close(task_id=..., summary=...)", text)
        self.assertIn("task_sys.need_parent", text)
        self.assertNotIn("Do not start a new IM conversation", text)
        self.assertNotIn("Do not send to target_identity_id from side", text)
        self.assertNotIn("new outbound communication", text)
        self.assertNotIn("source-bound", text)
```

- [ ] **Step 3: Tighten existing generic side-frame test**

In `test_render_side_frame_is_task_sys_scoped_and_names_only_two_results`, remove these old assertions:

```python
        self.assertIn("message.send(reply_to=source_message_id", text)
        self.assertIn("message.mark(message_id=source_message_id, disposition=absorbed)", text)
        self.assertIn("Do not call task_sys.need_parent merely because a user-facing reply is needed.", text)
```

Replace them with:

```python
        self.assertNotIn("Current-source IM closure", text)
        self.assertNotIn("Do not start a new IM conversation", text)
        self.assertNotIn("Do not send to target_identity_id from side", text)
        self.assertNotIn("source-bound", text)
```

- [ ] **Step 4: Replace parent-frame IM closure test**

Replace `test_render_parent_frame_names_im_closure_order` with:

```python
    def test_render_parent_frame_for_im_source_allows_full_message_tool_surface(self) -> None:
        instruction = self._parent_instruction()
        instruction["frame"]["source"] = {
            "type": "im.message.created",
            "ref": {
                "message_id": "msg-1",
                "conversation_id": "conv-1",
                "event_id": "imev-1",
            },
        }

        text = self.module.render_parent_frame(instruction["frame"])

        self.assertIn("For an IM source message:", text)
        self.assertIn("message.contacts", text)
        self.assertIn("message.list", text)
        self.assertIn("message.get", text)
        self.assertIn("message.conversation", text)
        self.assertIn("message.send(reply_to=source_message_id, content=...)", text)
        self.assertIn("message.send(target_identity_id=..., content=...)", text)
        self.assertIn("message.mark(message_id=..., disposition=absorbed)", text)
        self.assertIn("- task_sys.close(task_id=..., summary=...)", text)
        self.assertNotIn("Only after the source-bound IM action succeeds", text)
        self.assertNotIn("source-bound", text)
```

- [ ] **Step 5: Run the focused failing tests**

Run:

```bash
python3 -m pytest tests/test_task_sys_runtime_executor.py -q
```

Expected before implementation: failures in the new/updated frame contract assertions because the rendered text still teaches old source-bound-only IM behavior.

### Task 2: Implement Source-Specific IM Frame Guidance

**Files:**
- Modify: `tools/launcher/task_sys_runtime.py`

- [ ] **Step 1: Add small rendering helpers**

Add these helpers after `_json_block`:

```python
def _im_message_tool_capability_lines() -> tuple[str, ...]:
    return (
        "- message.contacts(...) to inspect discoverable actor targets when target discovery is needed.",
        "- message.list(...) to inspect active-identity Central IM events when event feed context is needed.",
        "- message.get(message_id=...) to read exact processable inbound messages.",
        "- message.conversation(target_identity_id=..., ...) to inspect visible direct conversation context.",
        "- message.send(reply_to=source_message_id, content=...) to reply to the current source message.",
        "- message.send(target_identity_id=..., content=...) to send required IM communication to an explicit actor or external identity.",
        "- message.mark(message_id=..., disposition=absorbed) when a processable inbound message needs no reply.",
    )


def _render_im_message_task_guidance(*, frame_kind: str) -> tuple[str, str, str]:
    close_line = (
        "- After the required message work succeeds, call task_sys.close(task_id=..., summary=...)."
        if frame_kind == "parent"
        else "- After the task is completed in side, call task_sys.close(task_id=..., summary=...)."
    )
    return (
        "For an IM source message:",
        "\n".join(
            (
                "Use the message tool contract as the authority for message reads, sends, target resolution, and disposition.",
                "Allowed message operations for completing this IM-source task:",
                *_im_message_tool_capability_lines(),
                close_line,
            )
        ),
        "Message task boundary:",
    )
```

- [ ] **Step 2: Rework `render_side_frame` to branch by source type**

At the start of `render_side_frame`, load the source and source type:

```python
    source = _require_mapping(payload.get("source"), "frame.source")
    source_type = source.get("type")
```

Replace the direct `_json_block(_require_mapping(payload.get("source"), "frame.source"))` call with:

```python
            _json_block(source),
```

Build source-specific side guidance before the return:

```python
    if source_type == "im.message.created":
        source_guidance = (
            *_render_im_message_task_guidance(frame_kind="side"),
            "\n".join(
                (
                    "- Keep message work tied to the current IM-source task.",
                    "- Use task_sys.need_parent only when required work needs parent resources outside message tools.",
                )
            ),
        )
    else:
        source_guidance = (
            "Source-specific resources:",
            "No source-specific message capability is added for this source type.",
        )
```

Insert `*source_guidance` after `"Allowed side resources:"` and before the generic read-only resource section.

- [ ] **Step 3: Remove old side-frame IM restrictions**

Delete the old `Current-source IM closure` block that contains:

```text
For an IM source message, side may only:
Do not start a new IM conversation.
Do not send to target_identity_id from side...
```

Also remove `new outbound communication` from the parent-handoff trigger sentence. Replace the sentence with:

```python
                "If the task requires parent attention, workspace resources, browser/web/research resources, shared "
                "product-state writes outside the message tools, durable deliverables, or multi-step execution outside "
                "the current message task, do not perform it in side. Call task_sys.need_parent."
```

- [ ] **Step 4: Update side-frame close order text**

Replace the old `IM closure order` section with:

```python
            "Frame completion order:",
            "\n".join(
                (
                    "- Perform required message actions before closing the task.",
                    "- If the message action fails, do not close the task. Retry if clearly safe, otherwise call task_sys.need_parent with failure context.",
                    "- If the message action succeeded but task_sys.close fails, retry task_sys.close; do not send a duplicate message.",
                )
            ),
```

- [ ] **Step 5: Rework parent-frame IM branch**

In `render_parent_frame`, replace the `source_type == "im.message.created"` branch with:

```python
    if source_type == "im.message.created":
        source_guidance = (
            *_render_im_message_task_guidance(frame_kind="parent"),
            "\n".join(
                (
                    "- Use message tools only for work required by this parent frame and its parent_handoff_params.",
                    "- Do not rely on parent turn completion to close this Task Sys task.",
                )
            ),
            "Allowed parent frame operations:",
            "\n".join(
                (
                    "- message.contacts(...)",
                    "- message.list(...)",
                    "- message.get(message_id=...)",
                    "- message.conversation(target_identity_id=..., ...)",
                    "- message.send(reply_to=source_message_id, content=...)",
                    "- message.send(target_identity_id=..., content=...)",
                    "- message.mark(message_id=..., disposition=absorbed)",
                    "- task_sys.close(task_id=..., summary=...)",
                )
            ),
        )
```

- [ ] **Step 6: Run focused runtime tests**

Run:

```bash
python3 -m pytest tests/test_task_sys_runtime_executor.py -q
```

Expected after implementation: all tests in the file pass.

### Task 3: Update Shared Task Management Skill And Task Sys Tool Wording

**Files:**
- Modify: `buddyswitch/skills/shared/task-management/SKILL.md`
- Modify: `tests/test_task_management_skill_architecture.py`
- Modify: `scripts/env/tools/task_sys/tool.py`
- Modify: `scripts/env/tools/task_sys/_impl.py`
- Check: `tests/test_env_tool_schema_contract.py`
- Check: `tests/test_env_tool_semantic_contract.py`

- [ ] **Step 1: Update task-management skill tests**

In `tests/test_task_management_skill_architecture.py`, replace old IM-specific assertions:

```python
        self.assertIn("If replying to an IM source, first call `message.send(reply_to=...)`.", skill_text)
        self.assertIn("If no reply is needed for an IM source, first call `message.mark(..., disposition=absorbed)`.", skill_text)
```

With:

```python
        self.assertIn("For IM source frames, use message tools for required message reads, sends, and disposition work.", skill_text)
        self.assertIn("Use `message.send(target_identity_id=...)` when the IM task requires a new explicit actor or external target.", skill_text)
        self.assertIn("Use `message.send(reply_to=...)` when the IM task is a reply to a processable inbound message.", skill_text)
        self.assertIn("Use `message.mark(..., disposition=absorbed)` only when no reply is needed.", skill_text)
        self.assertNotIn("source-bound", skill_text)
```

- [ ] **Step 2: Update the shared skill**

Replace lines 15-16 and 21-24 in `buddyswitch/skills/shared/task-management/SKILL.md` with:

```markdown
- For IM source frames, use message tools for required message reads, sends, and disposition work.
- Use `message.send(target_identity_id=...)` when the IM task requires a new explicit actor or external target.
- Use `message.send(reply_to=...)` when the IM task is a reply to a processable inbound message.
- Use `message.mark(..., disposition=absorbed)` only when no reply is needed.
- Exact payload schemas, effects, rejection meanings, and recovery guidance come from native tool schemas and `context.get.tool_catalog['task_sys']`.
```

And:

```markdown
## Judge The Frame
- If the frame kind is `task_sys.side_frame`, use `task_sys.close` when completed in side or `task_sys.need_parent` when parent resources outside the frame's allowed tools are required.
- If the frame kind is `task_sys.parent_frame`, complete the required frame work, perform required message actions first when this is an IM source frame, then call `task_sys.close`.
- Use `context.get` only when exact schemas or runtime source descriptions are needed.
```

- [ ] **Step 3: Update Task Sys tool contract wording**

In `scripts/env/tools/task_sys/tool.py`, change:

```python
description="Close a Task Sys task after the active side or parent frame has completed the required source-bound work.",
```

To:

```python
description="Close a Task Sys task after the active side or parent frame has completed the required frame work.",
```

Change:

```python
use_when=("The active side or parent frame completed the source-bound work and the task should be closed.",),
```

To:

```python
use_when=("The active side or parent frame completed the required frame work and the task should be closed.",),
```

In `scripts/env/tools/task_sys/_impl.py`, change:

```python
"Use task_sys.close when the active frame completed the source-bound task.",
```

To:

```python
"Use task_sys.close when the active frame completed the required task work.",
```

- [ ] **Step 4: Run skill and tool contract tests**

Run:

```bash
python3 -m pytest tests/test_task_management_skill_architecture.py tests/test_env_tool_schema_contract.py tests/test_env_tool_semantic_contract.py -q
```

Expected: all selected tests pass after updating expected live-surface wording.

### Task 4: Add Live-Surface Residue Guard

**Files:**
- Modify: `tests/test_task_management_skill_architecture.py`

- [ ] **Step 1: Add scoped residue test**

Add this test to `TaskManagementSkillArchitectureTests`:

```python
    def test_im_message_frame_capability_surfaces_do_not_teach_source_bound_only_rules(self) -> None:
        surfaces = [
            ROOT / "tools" / "launcher" / "task_sys_runtime.py",
            ROOT / "buddyswitch" / "skills" / "shared" / "task-management" / "SKILL.md",
            ROOT / "scripts" / "env" / "tools" / "task_sys" / "tool.py",
            ROOT / "scripts" / "env" / "tools" / "task_sys" / "_impl.py",
        ]
        stale_tokens = (
            "Current-source IM closure",
            "Do not start a new IM conversation",
            "Do not send to target_identity_id from side",
            "Only after the source-bound IM action succeeds",
            "source-bound work",
            "source-bound task",
        )
        for path in surfaces:
            text = path.read_text(encoding="utf-8")
            for token in stale_tokens:
                with self.subTest(path=str(path.relative_to(ROOT)), token=token):
                    self.assertNotIn(token, text)
```

- [ ] **Step 2: Run the residue test**

Run:

```bash
python3 -m pytest tests/test_task_management_skill_architecture.py::TaskManagementSkillArchitectureTests::test_im_message_frame_capability_surfaces_do_not_teach_source_bound_only_rules -q
```

Expected after implementation: pass.

### Task 5: Focused Behavioral Acceptance For Rendered IM Frames

**Files:**
- Modify: `tests/test_task_sys_runtime_executor.py`

- [ ] **Step 1: Add acceptance-shaped text test for side and parent**

Add this test near the other render tests:

```python
    def test_im_message_frames_share_the_same_message_capability_contract(self) -> None:
        side_text = self.module.render_side_frame(self._im_instruction()["frame"])
        parent_instruction = self._parent_instruction()
        parent_instruction["frame"]["source"] = self._im_instruction()["frame"]["source"]
        parent_text = self.module.render_parent_frame(parent_instruction["frame"])

        required_tokens = (
            "message.contacts",
            "message.list",
            "message.get",
            "message.conversation",
            "message.send(reply_to=source_message_id, content=...)",
            "message.send(target_identity_id=..., content=...)",
            "message.mark(message_id=..., disposition=absorbed)",
        )
        for token in required_tokens:
            with self.subTest(surface="side", token=token):
                self.assertIn(token, side_text)
            with self.subTest(surface="parent", token=token):
                self.assertIn(token, parent_text)
```

- [ ] **Step 2: Run the complete focused test set**

Run:

```bash
python3 -m pytest tests/test_task_sys_runtime_executor.py tests/test_task_management_skill_architecture.py tests/test_env_tool_schema_contract.py tests/test_env_tool_semantic_contract.py -q
```

Expected: all selected tests pass.

### Task 6: Manual Residue Scan And Final Verification

**Files:**
- Verify only; no file edits unless a scan finds a live-surface residue.

- [ ] **Step 1: Run a scoped old-rule scan**

Run:

```bash
rg -n "Current-source IM closure|Do not start a new IM conversation|Do not send to target_identity_id from side|Only after the source-bound IM action succeeds|source-bound work|source-bound task" tools/launcher scripts/env/tools/task_sys buddyswitch/skills/shared tests/test_task_sys_runtime_executor.py tests/test_task_management_skill_architecture.py
```

Expected: no matches.

- [ ] **Step 2: Run a scoped new-capability scan**

Run:

```bash
rg -n "message.contacts|message.list|message.get|message.conversation|message.send\\(reply_to=source_message_id|message.send\\(target_identity_id=|message.mark\\(message_id=..., disposition=absorbed\\)" tools/launcher/task_sys_runtime.py buddyswitch/skills/shared/task-management/SKILL.md tests/test_task_sys_runtime_executor.py
```

Expected: matches in runtime frame rendering, shared skill guidance, and frame rendering tests.

- [ ] **Step 3: Run focused tests**

Run:

```bash
python3 -m pytest tests/test_task_sys_runtime_executor.py tests/test_task_management_skill_architecture.py tests/test_env_tool_schema_contract.py tests/test_env_tool_semantic_contract.py -q
```

Expected: pass.

- [ ] **Step 4: Inspect git diff for scope**

Run:

```bash
git diff -- tools/launcher/task_sys_runtime.py buddyswitch/skills/shared/task-management/SKILL.md scripts/env/tools/task_sys/tool.py scripts/env/tools/task_sys/_impl.py tests/test_task_sys_runtime_executor.py tests/test_task_management_skill_architecture.py tests/test_env_tool_schema_contract.py tests/test_env_tool_semantic_contract.py
```

Expected: diff only changes IM frame capability guidance, Task Sys close wording, and corresponding tests. It must not change message service behavior, external API behavior, runtime state, or unrelated launcher behavior.

## Acceptance Criteria

- `im.message.created` side frames explicitly allow `message.contacts`, `message.list`, `message.get`, `message.conversation`, `message.send(reply_to=...)`, `message.send(target_identity_id=...)`, and `message.mark(...)`.
- `im.message.created` parent frames expose the same message capability surface as side frames.
- The old rule "new outbound communication requires parent" is no longer taught for IM message tool work.
- The old parent behavior "IM parent frame can only source reply/source absorb" is removed.
- Live shared skill guidance matches runtime frame behavior.
- Task Sys tool descriptions no longer call task closure `source-bound`.
- Scoped residue scan over live surfaces returns no old-rule matches.
- Focused tests pass without starting daemon/app-server/browser services.

## Non-Goals And Guardrails

- Do not refactor `reply_to` into source-completion workflow in this change.
- Do not change `message.send` resolver logic.
- Do not change external session cursor or HTTP projection behavior.
- Do not add frame-aware ACLs or feature flags.
- Do not preserve the old source-bound-only guidance for compatibility.
- Do not edit runtime object state directly.
