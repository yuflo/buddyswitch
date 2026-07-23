# Demand Intake REBUILD — Stage 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace capture-first parent Demand checking with one durable `inbound → pending intake → isolated side TriageProposal → private atomic apply` path, expose exactly six high-level Demand tools, and remove every Stage 1 retired path in the same cutover.

**Architecture:** Demand Sys remains the single semantic and write owner for pending intakes and canonical Demands. Existing daemon-service primitives remain product-neutral: source handlers and one Demand-owned handler use generic schedules, App Server notifications, side-thread lifecycle, and parent activity without adding Demand branches to daemon core. Current Task frames remain the only Task executor during Stage 1; selection and terminal reconciliation rules move to `demand-orchestration`, and Goal execution is not introduced until Stage 2.

**Tech Stack:** Python 3, JSON actor aggregate, BuddySwitch env native MCP projection, Codex App Server v2 `turn/start.outputSchema`, BuddySwitch daemon handlers/schedules, installed Markdown skills, `./buddyswitch-test focused`.

---

## Acceptance sentence

From a fresh actor instance, multiple IM or Track inbound facts can be triaged in isolated side threads without steering the parent; each produces exactly one validated result (`no_action_needed`, verified `handled`, `create`, `merge_intake`, `revise`, or `cancel`), canonical Demand changes use one transaction path, an idle actor receives at most one orchestration turn, and no live schema, tool, permission, prompt, skill, test, or current architecture document preserves `[DEMAND CHECK]`, check cursors, absorption, Actor-managed intake keys, or raw numeric revision payloads.

## Scope and explicit non-goals

In scope:

- pending intake persistence and idempotent replay;
- isolated side start and structured final-output consumption;
- TriageProposal validation, conflict retry, source provenance, and atomic apply;
- exact six-tool Actor surface;
- host-derived Actor `create` identity;
- opaque Demand references across Demand and the current Task create/outcome boundary;
- `demand-triage` and `demand-orchestration` skills;
- direct replacement of current inbound, selection, and outcome guidance;
- fresh-instance cutover and Stage 1 residue enforcement.

Not in scope:

- Codex Goal creation, Goal status mapping, or Goal recovery;
- multiple active Tasks, multiple main-like threads, or a scheduler framework;
- a new event bus, workflow engine, registry, daemon business branch, or generic coordinator;
- legacy Demand aggregate migration, fallback readers, aliases, dual writes, or feature flags;
- automatic user-visible delivery evidence beyond the verified IM `handled` reply branch.

## Frozen contracts

### Canonical Demand record

The active schema has one live model:

```python
{
    "id": "demand-...",
    "description": "...",
    "detail": "...",
    "source_refs": [{"type": "...", "ref": {...}}],
    "revision": 1,               # internal only
    "terminal": None | {
        "type": "completed",
        "at": "...",
        "summary": "...",
        "evidence_refs": [...],
    } | {
        "type": "canceled",
        "at": "...",
        "summary": "...",
    },
    "created_at": "...",
    "updated_at": "...",
}
```

There is no `intake_key`, `checked_revision`, `absorbed`, or `target_demand_id` in a Demand record.

### Pending intake record

```python
{
    "id": "intake-...",
    "source_key": "im.message.created:msg-...",
    "description": "...",
    "detail": "...",
    "source_refs": [{"type": "...", "ref": {...}}],
    "status": "pending" | "triaging" | "applied",
    "attempt_id": None | "attempt-...",
    "proposal": None | {...},
    "result": None | {...},
    "created_at": "...",
    "updated_at": "...",
}
```

The aggregate contains `demands`, `intakes`, and `actor_creation_receipts`. It is schema v3 and reads no earlier schema.

### TriageProposal

```python
TRIAGE_DECISIONS = (
    "no_action_needed",
    "handled",
    "create",
    "merge_intake",
    "revise",
    "cancel",
)
```

Exact decision payloads:

```python
{"decision": "no_action_needed", "reason": "..."}

{
    "decision": "handled",
    "reason": "...",
    "handled_receipt": {
        "type": "im.message.reply",
        "message_id": "msg-...",
    },
}

{
    "decision": "create",
    "reason": "...",
    "description": "...",
    "detail": "...",
}

{
    "decision": "merge_intake" | "revise",
    "reason": "...",
    "demand_ref": "dref-...",
    "description": "...",
    "detail": "...",
}

{
    "decision": "cancel",
    "reason": "...",
    "demand_ref": "dref-...",
}
```

`handled` is allowed only for an IM inbound when the referenced stored message is authored by the actor and replies to the exact source message. Track intake has no Stage 1 handled action; it must use `no_action_needed` or a Demand-changing decision.

### Actor Demand tools

The complete public action set is:

```python
("list", "get", "create", "revise", "complete", "cancel")
```

Inputs:

```python
list(state="live")
get(demand_id="demand-...")
create(description="...", detail="...")
revise(demand_ref="dref-...", description="...", detail="...", reason="...")
complete(demand_ref="dref-...", summary="...", evidence_refs=[...])
cancel(demand_ref="dref-...", reason="...")
```

`get` returns the current opaque `demand_ref`. `list` returns summaries without the token so callers reread before a mutation. No Actor action accepts `intake_key`, `source_refs`, `expected_revision`, or an internal proposal.

### Host invocation identity

The env MCP adapter reads:

```python
{
    "thread_id": params["_meta"]["threadId"],
    "turn_id": params["_meta"]["x-codex-turn-metadata"]["turn_id"],
    "request_id": json_rpc_request_id,
}
```

The Actor `create` idempotency key is the SHA-256 digest of actor id, role id, thread id, turn id, action, normalized description, and normalized detail. An identical replay in one turn returns the same Demand; a later turn may create a separate Demand. Missing thread/turn identity rejects `create` without a write.

### Daemon boundary

No Demand token or import is added to:

```text
tools/launcher/daemon_contracts.py
tools/launcher/daemon_state.py
tools/launcher/daemon_runtime.py
tools/launcher/daemon_core.py
tools/launcher/daemon_mailbox.py
scripts/env/tool_runtime/daemon_client.py
```

The existing schedule row is used only as a durable delivery/retry lease. Demand decisions remain in `demand_sys.py`, `demand_sys_daemon_adapter.py`, and the two Demand skills.

## File map

Create:

- `tools/launcher/demand_triage_handler.py` — the only Demand product handler for scheduled intake delivery and side final-output notifications.
- `buddyswitch/skills/shared/demand-triage/SKILL.md` — the only intake judgment rules.
- `buddyswitch/skills/shared/demand-orchestration/SKILL.md` — the only Demand reconciliation and current Task selection rules.
- `tests/unit/demand_sys/test_intake_triage.py` — pending intake and proposal-apply contract.
- `tests/integration/demand_sys/test_side_triage_flow.py` — schedule → side → proposal → apply consumer path.

Replace or modify:

- `scripts/env/repos/demands.py` — schema v3 aggregate only.
- `scripts/env/domain/demand_sys.py` — canonical Demand, pending intake, opaque refs, private apply.
- `scripts/env/domain/demand_read.py` — current external projection without retired fields.
- `scripts/env/tools/demand_sys/tool.py` — exact six actions.
- `scripts/env/tools/demand_sys/_impl.py` — high-level intent mapping and host-derived create.
- `tools/launcher/env_tool_mcp_server.py` — preserve host invocation metadata.
- `scripts/runtime_kernel/dispatcher.py` — pass invocation metadata into env tool dispatch.
- `scripts/env/tool_runtime/registry.py` — bind invocation metadata to ToolContext.
- `scripts/env/tool_runtime/context.py` — typed invocation fact and current Demand sources.
- `scripts/env/tool_runtime/role_auth.py` — exact six Demand permissions.
- `tools/launcher/app_server.py` — optional `output_schema` on `turn_start`.
- `tools/launcher/side_thread_lifecycle.py` — transparent `output_schema` pass-through.
- `tools/launcher/actor_side_thread.py` — transparent `output_schema` pass-through.
- `tools/launcher/demand_sys_daemon_adapter.py` — schedule/capture/render/apply operations; no parent Demand Check.
- `tools/launcher/im_wake_handler.py` — submit exact IM intake through the new adapter.
- `tools/launcher/track_comment_added_handler.py` — submit exact Track intake through the new adapter.
- `tools/launcher/instance_daemon.py` — register the Demand product handler in the composition root.
- `scripts/env/domain/task_sys.py` — retain internal basis revision but carry/redact the opaque Demand token.
- `scripts/env/tools/task_sys/tool.py` and `_impl.py` — Actor passes one opaque string from Demand `get`.
- `tools/launcher/task_sys_runtime.py` — outcome prompt invokes `demand-orchestration` and contains no check-cursor instruction.
- `buddyswitch/skills/shared/task-management/SKILL.md` — Task frame/progress only.
- `buddyswitch/manifest.toml` — install both Demand skills for all roles.
- `docs/arch/demand-sys-architecture.md` and `docs/arch/daemon-service-architecture.md` — current Stage 1 truth.
- existing Demand, native MCP, Task, skill, inbound, daemon, and architecture tests — replace old assertions; do not preserve old behavior.

Delete:

- `tests/unit/demand_sys/test_capture_and_check.py`
- `tests/unit/demand_sys/test_canonicalization.py`

Their replacement tests prove the current model; they are not retained as compatibility fixtures.

---

### Task 1: Freeze schema v3, opaque refs, and private intake apply

**Files:**

- Create: `tests/unit/demand_sys/test_intake_triage.py`
- Modify: `tests/unit/demand_sys/test_lifecycle.py`
- Modify: `tests/integration/demand_sys/test_repository_atomicity.py`
- Modify: `scripts/env/repos/demands.py`
- Modify: `scripts/env/domain/demand_sys.py`
- Modify: `scripts/env/domain/demand_read.py`
- Delete: `tests/unit/demand_sys/test_capture_and_check.py`
- Delete: `tests/unit/demand_sys/test_canonicalization.py`

- [ ] **Step 1: Write the schema and intake RED tests**

Add focused tests with these observable assertions:

```python
def test_capture_intake_is_idempotent_without_creating_a_demand():
    first = demand_sys.capture_intake(TARGET, "im.message.created:msg-1", "Need export", "Need export", REFS)
    replay = demand_sys.capture_intake(TARGET, "im.message.created:msg-1", "Need export", "Need export", REFS)
    assert first["intake_id"] == replay["intake_id"]
    assert replay["state_changed"] is False
    assert demand_sys.list_demands(TARGET, state="all") == []


def test_apply_create_atomically_terminalizes_intake_and_creates_one_demand():
    intake_id = capture()
    attempt_id = demand_sys.begin_triage(TARGET, intake_id)["attempt_id"]
    demand_sys.record_triage_proposal(
        TARGET,
        intake_id,
        attempt_id,
        {"decision": "create", "reason": "New obligation", "description": "Export CSV", "detail": "Add CSV export"},
    )
    receipt = demand_sys.apply_triage_proposal(TARGET, intake_id, attempt_id, handled_verified=False)
    assert receipt["decision"] == "create"
    assert receipt["state_changed"] is True
    assert len(demand_sys.list_demands(TARGET, state="live")) == 1
    assert demand_sys.get_intake(TARGET, intake_id)["status"] == "applied"


def test_merge_intake_updates_one_target_and_never_creates_an_absorbed_source():
    target = create_actor_demand()
    intake_id, attempt_id = proposed(
        {
            "decision": "merge_intake",
            "reason": "Same underlying obligation",
            "demand_ref": target["demand_ref"],
            "description": "Export CSV with timezone",
            "detail": "Export CSV and include timezone",
        }
    )
    demand_sys.apply_triage_proposal(TARGET, intake_id, attempt_id, handled_verified=False)
    rows = demand_sys.list_demands(TARGET, state="all")
    assert len(rows) == 1
    assert rows[0]["description"] == "Export CSV with timezone"
    assert rows[0]["terminal"] is None


def test_stale_proposal_ref_resets_intake_for_side_retry_without_partial_write():
    target = create_actor_demand()
    intake_id, attempt_id = proposed(revise_proposal(target["demand_ref"]))
    demand_sys.revise(TARGET, target["demand_ref"], "Changed elsewhere", "Changed elsewhere", "Concurrent update")
    before = demands.actor_state_path(TARGET).read_bytes()
    receipt = demand_sys.apply_triage_proposal(TARGET, intake_id, attempt_id, handled_verified=False)
    assert receipt == {"state_changed": True, "retry_required": True, "reason": "stale_demand_ref"}
    assert demand_sys.get_intake(TARGET, intake_id)["status"] == "pending"
    assert demand_sys.get(TARGET, target["id"])["description"] == "Changed elsewhere"
    assert b'"status": "pending"' in demands.actor_state_path(TARGET).read_bytes()
    assert before != demands.actor_state_path(TARGET).read_bytes()  # only intake retry state changed
```

Also assert the v3 aggregate and Demand records contain no `intake_key`, `checked_revision`, `absorbed`, or `target_demand_id`.

- [ ] **Step 2: Run the exact RED target**

Run:

```bash
./buddyswitch-test focused \
  tests/unit/demand_sys/test_intake_triage.py \
  tests/unit/demand_sys/test_lifecycle.py \
  tests/integration/demand_sys/test_repository_atomicity.py
```

Expected: FAIL because schema v3 and the intake operations do not exist.

- [ ] **Step 3: Replace the repository schema**

Set `SCHEMA_VERSION = 3` and make the only empty aggregate:

```python
{
    "schema_version": 3,
    "actor_target": normalized_target,
    "demands": {},
    "intakes": {},
    "actor_creation_receipts": {},
}
```

Validation must require this exact shape. Do not add a v2 reader or translator.

- [ ] **Step 4: Replace the Demand domain**

Implement:

```python
capture_intake(actor_target, source_key, description, detail, source_refs)
get_intake(actor_target, intake_id)
begin_triage(actor_target, intake_id)
record_triage_proposal(actor_target, intake_id, attempt_id, proposal)
retry_triage(actor_target, intake_id, attempt_id, reason)
apply_triage_proposal(actor_target, intake_id, attempt_id, handled_verified)
create(actor_target, creation_key, description, detail, source_refs)
list_demands(actor_target, state="live")
get(actor_target, demand_id)
resolve_demand_ref(actor_target, demand_ref)
revise(actor_target, demand_ref, description, detail, reason)
complete(actor_target, demand_ref, summary, evidence_refs)
cancel(actor_target, demand_ref, reason)
```

All writes call only `demands.transact_actor_state`. `apply_triage_proposal` validates and changes intake plus canonical Demand in one transaction. A stale target ref resets only the intake to `pending` and returns `retry_required`.

Opaque refs use one current implementation:

```python
def _demand_ref(record):
    body = json.dumps(
        {"demand_id": record["id"], "revision": record["revision"]},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    token = base64.urlsafe_b64encode(body).decode("ascii").rstrip("=")
    checksum = hashlib.sha256(body).hexdigest()[:16]
    return f"dref-{token}.{checksum}"
```

The decoder verifies the checksum and returns internal id/revision. No other layer parses it.

- [ ] **Step 5: Replace lifecycle and read projections**

Keep only `completed` and `canceled` terminal types. `demand_read` exposes current Demand content and lifecycle but not internal revision, intake state, or creation receipts.

- [ ] **Step 6: Run the same target GREEN**

Run the Task 1 command again.

Expected: PASS.

- [ ] **Step 7: Commit the coherent domain replacement**

```bash
git add scripts/env/repos/demands.py scripts/env/domain/demand_sys.py scripts/env/domain/demand_read.py \
  tests/unit/demand_sys/test_intake_triage.py tests/unit/demand_sys/test_lifecycle.py \
  tests/integration/demand_sys/test_repository_atomicity.py \
  tests/unit/demand_sys/test_capture_and_check.py tests/unit/demand_sys/test_canonicalization.py
git commit -m "rebuild: replace demand capture with intake triage"
```

---

### Task 2: Cut the Actor surface to six tools and hide concurrency identity

**Files:**

- Modify: `tests/unit/env_tool/test_schema_contract.py`
- Modify: `tests/unit/env_tool/test_semantic_contract.py`
- Modify: `tests/integration/env_tool/test_response_demand.py`
- Modify: `tests/process/cli/test_env_native_mcp_projection.py`
- Modify: `tests/unit/actor/test_role_action_auth.py`
- Modify: `tools/launcher/env_tool_mcp_server.py`
- Modify: `scripts/runtime_kernel/dispatcher.py`
- Modify: `scripts/env/tool_runtime/registry.py`
- Modify: `scripts/env/tool_runtime/context.py`
- Modify: `scripts/env/tools/demand_sys/tool.py`
- Modify: `scripts/env/tools/demand_sys/_impl.py`
- Modify: `scripts/env/tool_runtime/role_auth.py`

- [ ] **Step 1: Write the exact six-tool and invocation RED tests**

Assert:

```python
assert catalog.supported_actions("demand_sys") == (
    "list", "get", "create", "revise", "complete", "cancel"
)
assert demand_native_names == {
    "demand_sys__list",
    "demand_sys__get",
    "demand_sys__create",
    "demand_sys__revise",
    "demand_sys__complete",
    "demand_sys__cancel",
}
assert set(create_schema["properties"]) == {"description", "detail"}
assert set(revise_schema["properties"]) == {"demand_ref", "description", "detail", "reason"}
assert "expected_revision" not in serialized_catalog
```

Add an MCP adapter test that sends:

```python
{
    "id": 41,
    "method": "tools/call",
    "params": {
        "name": "demand_sys__create",
        "arguments": {"description": "Export CSV", "detail": "Add CSV export"},
        "_meta": {
            "threadId": "thr-main",
            "x-codex-turn-metadata": {"turn_id": "turn-9"},
        },
    },
}
```

and asserts the dispatcher receives `invocation={"thread_id":"thr-main","turn_id":"turn-9","request_id":"41"}`.

Add an integration test proving same-turn identical `create` replays and a different turn creates a second Demand.

- [ ] **Step 2: Run the exact RED target**

```bash
./buddyswitch-test focused \
  tests/unit/env_tool/test_schema_contract.py \
  tests/unit/env_tool/test_semantic_contract.py \
  tests/integration/env_tool/test_response_demand.py \
  tests/process/cli/test_env_native_mcp_projection.py \
  tests/unit/actor/test_role_action_auth.py
```

Expected: FAIL on the old ten actions and leaked fields.

- [ ] **Step 3: Preserve host invocation metadata**

Pass the normalized `invocation` object through:

```text
env_tool_mcp_server._handle_tools_call
  → default_dispatcher
  → runtime broker params
  → dispatcher._env_tool_dispatch
  → registry.dispatch_env_tool_request
  → ToolContext.invocation
```

Reject non-string thread/turn fields; do not accept an Agent argument as a fallback.

- [ ] **Step 4: Replace the Demand ToolDefinition and adapter**

Define exactly six actions and map them to the domain. Public reads use a projection that adds `demand_ref` only on `get`. Public writes accept tokens and never return numeric revision fields.

Actor `create` uses:

```python
creation_key = demand_sys.actor_creation_key(
    actor_target,
    thread_id=context.invocation.thread_id,
    turn_id=context.invocation.turn_id,
    description=args["description"],
    detail=args["detail"],
)
source_refs = [{
    "type": "actor.self_requested",
    "ref": {
        "thread_id": context.invocation.thread_id,
        "turn_id": context.invocation.turn_id,
    },
}]
```

- [ ] **Step 5: Replace role permissions and current runtime source text**

Grant exactly:

```python
demand_sys.list
demand_sys.get
demand_sys.create
demand_sys.revise
demand_sys.complete
demand_sys.cancel
```

Remove all four retired permissions; do not keep aliases.

- [ ] **Step 6: Run the same target GREEN**

Expected: PASS.

- [ ] **Step 7: Commit the public contract cutover**

```bash
git add tools/launcher/env_tool_mcp_server.py scripts/runtime_kernel/dispatcher.py \
  scripts/env/tool_runtime/registry.py scripts/env/tool_runtime/context.py \
  scripts/env/tools/demand_sys scripts/env/tool_runtime/role_auth.py \
  tests/unit/env_tool/test_schema_contract.py tests/unit/env_tool/test_semantic_contract.py \
  tests/integration/env_tool/test_response_demand.py \
  tests/process/cli/test_env_native_mcp_projection.py tests/unit/actor/test_role_action_auth.py
git commit -m "rebuild: expose six demand intents"
```

---

### Task 3: Pass Codex outputSchema and consume one side final result

**Files:**

- Modify: `tests/integration/app_server/test_client.py`
- Modify: `tests/integration/actor/test_side_thread_lifecycle.py`
- Modify: `tests/unit/actor/test_side_thread_registry.py`
- Modify: `tools/launcher/app_server.py`
- Modify: `tools/launcher/side_thread_lifecycle.py`
- Modify: `tools/launcher/actor_side_thread.py`
- Create: `tests/integration/demand_sys/test_side_triage_flow.py`
- Create: `tools/launcher/demand_triage_handler.py`
- Replace: `tools/launcher/demand_sys_daemon_adapter.py`
- Modify: `tools/launcher/im_wake_handler.py`
- Modify: `tools/launcher/track_comment_added_handler.py`
- Modify: `tools/launcher/instance_daemon.py`

- [ ] **Step 1: Write outputSchema pass-through RED tests**

Assert `app_server.turn_start(..., output_schema=schema)` sends:

```python
{
    "threadId": "thr-side",
    "input": [...],
    "permissions": "buddyswitch-runtime",
    "outputSchema": schema,
}
```

Assert `actor_side_thread.start_actor_side_thread` passes the identical object and registers purpose:

```text
demand-triage:intake-...:attempt-...
```

- [ ] **Step 2: Run the outputSchema RED target**

```bash
./buddyswitch-test focused \
  tests/integration/app_server/test_client.py \
  tests/integration/actor/test_side_thread_lifecycle.py \
  tests/unit/actor/test_side_thread_registry.py
```

Expected: FAIL because the wrappers do not accept `output_schema`.

- [ ] **Step 3: Add transparent optional pass-through**

Add `output_schema: Mapping[str, Any] | None = None` to the three wrappers. Only `app_server.turn_start` serializes it as `outputSchema`; no daemon or Demand semantics enter these files.

- [ ] **Step 4: Run the same outputSchema target GREEN**

Expected: PASS.

- [ ] **Step 5: Write the end-to-end side triage RED test**

The test uses fake App Server/runtime boundaries and real Demand storage to prove:

```python
source_handler.handle(inbound_trigger)
assert no_parent_inputs()

scheduled_handler.handle(demand_intake_trigger)
assert one_ephemeral_side_started(output_schema=TRIAGE_OUTPUT_SCHEMA)
assert demand_sys.list_demands(TARGET, "all") == []

triage_handler.handle(item_completed(agent_message_json))
triage_handler.handle(turn_completed("completed"))

assert one_canonical_demand()
assert side_lease_removed()
assert one_orchestration_request_when_parent_idle_and_no_active_task()
```

Add variants for `no_action_needed`, verified IM `handled`, `merge_intake`, invalid output retry, and stale ref retry. Assert Track `handled` is rejected.

- [ ] **Step 6: Run the exact side triage RED target**

```bash
./buddyswitch-test focused \
  tests/integration/demand_sys/test_side_triage_flow.py \
  tests/unit/demand_sys/test_daemon_adapter.py \
  tests/unit/im/test_wake_handler.py \
  tests/integration/track/test_comment_added_handler.py
```

Expected: FAIL because the old adapter creates a Demand and inputs `[DEMAND CHECK]`.

- [ ] **Step 7: Replace the Demand daemon adapter and add one product handler**

Use one stable schedule key per source intake:

```text
demand-intake:<source_key>
```

The source handler writes a generic due-now schedule containing the exact inbound fact. The Demand handler:

1. captures/replays the pending intake;
2. begins one attempt;
3. starts one isolated side with `TRIAGE_OUTPUT_SCHEMA`;
4. records the final `agentMessage` proposal;
5. on completed turn, verifies an IM handled receipt when present and atomically applies;
6. unregisters the side lease;
7. schedules immediate orchestration only when a canonical Demand changed;
8. on malformed output, failed turn, or stale ref, reschedules the same intake with bounded backoff.

The handler may call generic `state.upsert_schedule`, `runtime.parent_activity`, and `runtime.input_actor`. It must not modify daemon core or duplicate Demand validation.

- [ ] **Step 8: Register only at the composition root**

`instance_daemon.default_daemon_handlers()` adds `DemandTriageHandler()` next to source and Task product handlers. No generic daemon module imports it.

- [ ] **Step 9: Run the same side triage target GREEN**

Expected: PASS with no parent input during triage.

- [ ] **Step 10: Commit the product vertical slice**

```bash
git add tools/launcher/app_server.py tools/launcher/side_thread_lifecycle.py \
  tools/launcher/actor_side_thread.py tools/launcher/demand_sys_daemon_adapter.py \
  tools/launcher/demand_triage_handler.py tools/launcher/im_wake_handler.py \
  tools/launcher/track_comment_added_handler.py tools/launcher/instance_daemon.py \
  tests/integration/app_server/test_client.py tests/integration/actor/test_side_thread_lifecycle.py \
  tests/unit/actor/test_side_thread_registry.py tests/integration/demand_sys/test_side_triage_flow.py \
  tests/unit/demand_sys/test_daemon_adapter.py tests/unit/im/test_wake_handler.py \
  tests/integration/track/test_comment_added_handler.py
git commit -m "rebuild: triage inbound demands on isolated sides"
```

---

### Task 4: Move selection/reconciliation ownership and preserve only current Task execution

**Files:**

- Create: `buddyswitch/skills/shared/demand-triage/SKILL.md`
- Create: `buddyswitch/skills/shared/demand-orchestration/SKILL.md`
- Modify: `buddyswitch/skills/shared/task-management/SKILL.md`
- Modify: `buddyswitch/manifest.toml`
- Modify: `scripts/env/domain/task_sys.py`
- Modify: `scripts/env/tools/task_sys/tool.py`
- Modify: `scripts/env/tools/task_sys/_impl.py`
- Modify: `tools/launcher/task_sys_runtime.py`
- Modify: `tests/unit/architecture/test_task_management_skill.py`
- Modify: `tests/unit/actor/test_runtime_skills.py`
- Modify: `tests/unit/task_sys/test_runtime_executor.py`
- Modify: `tests/integration/env_tool/test_response_task.py`

- [ ] **Step 1: Write Skill ownership and opaque Task boundary RED tests**

Assert:

```python
assert "Task Selection Rule" not in task_management
assert "Task Outcome Check" not in task_management
assert "[DEMAND CHECK]" not in task_management
assert "task_sys.side_frame" in task_management
assert "[TASK PROGRESS CHECK]" in task_management

assert "TriageProposal" in demand_triage
assert "needs_parent_judgment" not in demand_triage
assert "choose at most one" in demand_orchestration
assert "task_sys.outcome_frame" in demand_orchestration
```

Task create schema must accept:

```python
{"demand_ref": {"type": "string"}, "execution_brief": {...}}
```

and Task actor-visible outputs/outcome frames must contain no `basis_revision`.

- [ ] **Step 2: Run the exact RED target**

```bash
./buddyswitch-test focused \
  tests/unit/architecture/test_task_management_skill.py \
  tests/unit/actor/test_runtime_skills.py \
  tests/unit/task_sys/test_runtime_executor.py \
  tests/integration/env_tool/test_response_task.py
```

Expected: FAIL because one old Skill owns all three concerns and Task exposes raw revision.

- [ ] **Step 3: Write the two final Demand skills**

`demand-triage` owns only side judgment and exact proposal output. It tells the side to use `list/get`, return one allowed decision, never call a Demand mutation, never ask parent, and use only verified `message.send(reply_to=...)` for IM `handled`.

`demand-orchestration` owns:

1. reconcile a terminal Task outcome against the latest Demand;
2. list active Tasks;
3. if none is active, list all live Demands;
4. compare urgency, user commitment, blocked downstream work, continuity, evidence readiness, and staleness;
5. choose at most one or explicitly choose none;
6. reread it, record the selection reason in the execution brief, and create one Task using the opaque Demand ref.

It does not teach Goal continuation.

- [ ] **Step 4: Narrow task-management**

Keep only side frame, parent frame, Progress Check, close/cancel/need_parent behavior. Remove every Demand mutation, selection, and outcome rule.

- [ ] **Step 5: Adapt the current Task edge to opaque refs**

The Task tool resolves the token through Demand domain at the application boundary, then passes the internal id/revision snapshot to Task domain. Task storage may retain the internal basis revision for current frame idempotency, but all Actor projections and frame payloads carry only:

```python
{"demand_id": "demand-...", "demand_ref": "dref-..."}
```

No Task domain code imports Demand domain.

- [ ] **Step 6: Replace the outcome prompt**

`render_outcome_frame` starts with:

```text
task_sys.outcome_frame
Use $demand-orchestration to reconcile this terminal Task against the latest Demand and then select at most one next live Demand.
```

Remove `complete_check`, exact returned revision acknowledgement, and all old selection wording.

- [ ] **Step 7: Install both skills for every role**

Add both shared skills and role references. Keep `task-management` only because current Task frames remain the sole Stage 1 executor.

- [ ] **Step 8: Run the same target GREEN**

Expected: PASS.

- [ ] **Step 9: Commit the owner migration**

```bash
git add buddyswitch/skills/shared/demand-triage buddyswitch/skills/shared/demand-orchestration \
  buddyswitch/skills/shared/task-management/SKILL.md buddyswitch/manifest.toml \
  scripts/env/domain/task_sys.py scripts/env/tools/task_sys tools/launcher/task_sys_runtime.py \
  tests/unit/architecture/test_task_management_skill.py tests/unit/actor/test_runtime_skills.py \
  tests/unit/task_sys/test_runtime_executor.py tests/integration/env_tool/test_response_task.py
git commit -m "rebuild: assign demand triage and orchestration owners"
```

---

### Task 5: Delete retired live surfaces and update current architecture

**Files:**

- Modify: `tests/unit/architecture/test_demand_sys_boundaries.py`
- Modify: `tests/unit/architecture/test_tool_runtime_contract.py`
- Modify: `tests/process/launcher/test_demand_commands.py`
- Modify: `tests/integration/im/test_external_reply_loop.py`
- Modify: `tests/integration/track/test_comment_added_handler.py`
- Modify: `tests/integration/env_tool/test_payload_contract.py`
- Modify: `docs/arch/demand-sys-architecture.md`
- Modify: `docs/arch/daemon-service-architecture.md`
- Modify: `docs/arch/task-sys-architecture.md`
- Modify: `tools/launcher/assets/roles/market/AGENTS.md`
- Modify: `tools/launcher/assets/roles/pm/AGENTS.md`
- Modify: `tools/launcher/assets/roles/design/AGENTS.md`
- Modify: `tools/launcher/assets/roles/dev/AGENTS.md`
- Modify: `tools/launcher/assets/roles/test/AGENTS.md`

- [ ] **Step 1: Write residue RED assertions**

The architecture test scans active code, `docs/arch`, manifest, role bootstrap, and installed skills while excluding `docs/memo` and negative-test token construction. Assert:

```python
RETIRED = (
    "[DEMAND " + "CHECK]",
    "demand_sys." + "check",
    "demand_sys." + "get_many",
    "demand_sys." + "complete_check",
    "demand_sys." + "absorb_into",
    "checked_" + "revision",
    '"absorbed"',
    "expected_" + "revision",
)
```

Also assert:

- native Demand actions and permissions equal the six-action set;
- schema v3 record fields exclude retired fields;
- generic daemon modules contain no Demand import/token;
- no `demand_v2`, `legacy_demand`, `fallback_demand`, feature flag, or compatibility adapter exists.

- [ ] **Step 2: Run residue assertions RED**

```bash
./buddyswitch-test focused \
  tests/unit/architecture/test_demand_sys_boundaries.py \
  tests/unit/architecture/test_tool_runtime_contract.py \
  tests/process/launcher/test_demand_commands.py \
  tests/integration/env_tool/test_payload_contract.py
```

Expected: FAIL and enumerate remaining live residue.

- [ ] **Step 3: Replace every current consumer and document**

Update tests to assert the new consumer path, not the retired behavior. Rewrite current architecture docs around:

```text
source fact
  → generic daemon schedule/handler dispatch
  → Demand-owned pending intake
  → isolated side TriageProposal
  → Demand-owned atomic apply
  → parent demand-orchestration when eligible
  → current Task frame executor
```

State explicitly that daemon-service is product-neutral and Stage 1 contains no Goal execution path.

- [ ] **Step 4: Remove retired files/assertions rather than skipping them**

Delete or rewrite every old test fixture that constructs v2 fields or treats retired actions as supported. Do not mark them skipped and do not add compatibility setup.

- [ ] **Step 5: Run the same residue target GREEN**

Expected: PASS with zero unexplained matches.

- [ ] **Step 6: Commit replacement cleanup**

```bash
git add tests docs/arch tools/launcher/assets/roles
git commit -m "rebuild: remove demand check and absorb residue"
```

---

### Task 6: Stage 1 focused acceptance

**Files:**

- Modify if evidence exposes a defect: only the nearest owning file and its exact regression test.
- Record final evidence in this memo’s execution log below.

- [ ] **Step 1: Run contract and architecture evidence**

```bash
./buddyswitch-test focused \
  tests/unit/demand_sys \
  tests/integration/demand_sys \
  tests/unit/env_tool/test_schema_contract.py \
  tests/unit/env_tool/test_semantic_contract.py \
  tests/integration/env_tool/test_response_demand.py \
  tests/process/cli/test_env_native_mcp_projection.py \
  tests/unit/architecture/test_demand_sys_boundaries.py \
  tests/unit/architecture/test_tool_runtime_contract.py \
  tests/unit/architecture/test_task_management_skill.py
```

Expected: PASS.

- [ ] **Step 2: Run product consumer evidence**

```bash
./buddyswitch-test focused \
  tests/integration/im/test_external_reply_loop.py \
  tests/integration/track/test_comment_added_handler.py \
  tests/integration/demand_sys/test_side_triage_flow.py \
  tests/integration/actor/test_side_thread_lifecycle.py \
  tests/unit/daemon/test_decoupling.py
```

Expected: PASS; resource-owning tests leave no side lease, socket, lock, or temporary runtime state.

- [ ] **Step 3: Run Task preservation evidence**

```bash
./buddyswitch-test focused \
  tests/unit/task_sys/test_runtime_executor.py \
  tests/integration/task_sys/test_actor_create.py \
  tests/integration/task_sys/test_progress_check.py \
  tests/integration/env_tool/test_response_task.py
```

Expected: PASS; Task frames remain the only executor and outcome uses `demand-orchestration`.

- [ ] **Step 4: Run source-bound residue scan**

```bash
rg -n \
  '\\[DEMAND CHECK\\]|demand_sys\\.(check|get_many|complete_check|absorb_into)|checked_revision|\"absorbed\"|expected_revision' \
  scripts tools/launcher buddyswitch/skills tools/launcher/assets docs/arch tests \
  -g '*.py' -g '*.md' -g '*.toml'
```

Expected: only deliberate negative assertions assembled so the active retired token is not taught as a current string; no runtime, schema, fixture, or guidance hit.

- [ ] **Step 5: Audit the diff against all proof classes**

Record:

- Product — real inbound consumer reaches side proposal and canonical result.
- Contract — six tools, exact proposal, no partial write.
- Architecture — one Demand write owner; daemon remains neutral.
- Replacement — retired path unreachable and absent.
- Operations — replay/retry is idempotent and side leases clean up.

- [ ] **Step 6: Do not run repository-wide full suite unless separately authorized**

Stage 1 acceptance uses the focused affected boundaries above. `./buddyswitch-test full` is reserved for a frozen merge/release candidate or an explicit user request.

## REBUILD gate

Stage 1 is rejected if any statement below is false:

- inbound can still create a Demand before side judgment;
- parent can still receive `[DEMAND CHECK]`;
- any native MCP or role permission exposes `get_many`, `check`, `complete_check`, or `absorb_into`;
- any Actor mutation accepts numeric revision;
- any active schema reads or writes `checked_revision` or `absorbed`;
- `task-management` still teaches triage, selection, or Demand reconciliation;
- daemon core/state/contracts/runtime/mailbox contain a Demand-specific import or branch;
- a v2 aggregate loads through a fallback or translator;
- Goal and Task frames can both execute a Task in Stage 1;
- a retired fixture remains only to make old behavior pass.

## Execution log

Update this section during implementation:

```text
State: implemented and focused-accepted
Source identity: branch fea-daemon @ 2256f77
RED evidence:
  - schema/runtime seam: run fdc6f0565a97448db041b70424ac996a
  - side-start recovery: run 249f2bd8279b454db10fa4fcee28e1c8
GREEN evidence:
  - final affected-scope verification: run e7b9aed708e94618adacc7dbd7374188
  - 749 passed, 1567 subtests passed
  - focused command only; repository-wide full suite intentionally not run
Residue evidence:
  - source scan found no retired Demand Check/check/get_many/complete_check/
    absorb_into/check-cursor/expected-revision token in active code, skills,
    role guidance, or docs/arch
  - generic daemon contracts/state/runtime/core/mailbox/client scan found no
    Demand token or import
  - git diff --check and changed Python compilation passed
Operational cleanup:
  - side completion tests prove lease removal
  - side-start failure resets the intake claim and schedules the same intake
  - invalid/stale proposals retry without partial Demand writes
Residual risk:
  - daemon-service has no generic handler activation/reconciliation hook and
    App Server notification delivery is not replayed after a daemon outage.
    Therefore a triage side turn that becomes terminal entirely while the
    daemon is offline may remain triaging until a future product-neutral
    recovery capability is added. Do not solve this by adding Demand meaning
    to daemon core.
Commit status:
  - no commit created; the user did not request commit or publication
```
