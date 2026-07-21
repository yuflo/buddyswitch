# Demand Sys Phase 4 Track Comment Forward Cutover Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` only when the user explicitly
> authorizes delegation; otherwise use `superpowers:executing-plans` and execute
> this plan task-by-task in the current session. Steps use checkbox (`- [ ]`)
> syntax for tracking.

**Goal:** Make Demand the only need-intake owner for Track comments and remove
the last external/non-Demand Task creation path completely.

**Architecture:** The Track handler keeps source validation and maps one exact
comment into the existing Demand-owned `capture_inbound` operation. The actor
remains the only semantic bridge from Demand to the one `task_sys.create`
contract. Task Sys is rebuilt forward to Demand-backed creation only; no
ingress wrapper, compatibility schema, fallback, event bus, or cross-domain
callback remains.

**Tech Stack:** Python 3, file-backed Demand and Task domain owners, generic
instance daemon handlers, native `env.tool` contracts, pytest/unittest through
`./buddyswitch-test`, BuddySwitch CLI, installed real Codex App Server runtime.

**Design source:**
`docs/memo/2026-07-20-demand-sys-phase-4-track-comment-forward-cutover-design.md`

**Protected live-data decision:**
`docs/memo/2026-07-21-demand-sys-phase-4-live-data-cutover-decision.md`

**Frozen planning baseline:**
`213d980c29cc1f6a247375ede06d7f74de676ea3`

**Current execution state (2026-07-21):** Implementation and focused source
acceptance are complete. The real product loop passed, and the user-side actor
environment cleanup removed the live-data gate. Task 7's original snapshot and
role-cleanup procedure nevertheless failed its scoped-data claim; that incident
remains recorded rather than being reclassified as success. No compatibility or
Phase 4 migration path was added. The coherent change set is ready for a commit
when explicitly authorized.

---

## 0. Execution contract

### Acceptance sentence

> A valid Track comment addressed to an active BuddySwitch actor durably creates
> or replays exactly one actor-owned Demand and requests Demand attention even
> while another Task is active; only the actor may subsequently create one
> Demand-backed Task through `task_sys.create`, while Track and Task code have no
> direct creation path, Demand Sys and Task Sys do not import or mutate each
> other, and the generic daemon remains product-neutral.

### Scope guard

In scope:

- Track comment handler cutover to Demand capture;
- exact Track-comment Demand materialization and replay;
- actor source-context guidance where Track reads are necessary;
- deletion of external Task ingress and generic Task ingest;
- Demand-only Task source enforcement across domain, runtime, read models, and
  test fixtures;
- architecture/residue enforcement;
- focused automated proof and real CLI actor acceptance.

Out of scope:

- automatic matching, absorption, relation inference, selection, or completion;
- Track thread resolution from Demand/Task completion;
- offline capture/recovery, workers, queues, priorities, or multiple active
  Tasks;
- generic inbound mapper/registry/event bus;
- public mutation CLI or Web UI;
- direct TUI input as inbound intake.

### Commit policy

Do not create plan-only or task-fragment commits. Verify each coherent block and
create one intentional commit only after automated and real-actor acceptance.
Do not push until the user requests it.

### Runtime data gate

At plan time the current workspace has zero Demand, Task, Track, and Track
comment rows. Before implementation, record the counts again:

```bash
find buddyswitch/objects/demand-sys -type f -name '*.json' -print 2>/dev/null | wc -l
find buddyswitch/objects/task-sys -type f -name '*.json' -print 2>/dev/null | wc -l
find buddyswitch/objects/tracks -type f -name '*.json' -print 2>/dev/null | wc -l
find buddyswitch/objects/track-comments -type f -name '*.json' -print 2>/dev/null | wc -l
```

Expected at implementation start: all four counts are `0`, unless new user
runtime work exists. If nonzero Task data exists, stop for an explicit data
decision. Do not add an old/new Task reader or non-Demand fallback.

Execution correction: these commands inspected the repository mount, not the
public CLI's live state root. The real CLI later exposed 20 retired
`task-im-message-created-*` records under
`/Users/chen/.codex-buddyswitch/state`. The stop condition therefore applies
now, before commit/acceptance.

## 1. File map

### Production files

| Path | Planned responsibility/change |
| --- | --- |
| `tools/launcher/track_comment_added_handler.py` | Keep Track/source validation; map exact comment to Demand; call Demand adapter; remove every Task dependency |
| `tools/launcher/task_sys_ingress.py` | Delete; no valid consumer remains |
| `tools/launcher/demand_sys_daemon_adapter.py` | Preserve one capture/check/actor-input owner; change only if an exact failure proves a source-neutral gap |
| `scripts/env/domain/task_sys.py` | Delete generic ingest/arbitrary source handling; preserve one Demand-backed create owner/lifecycle |
| `scripts/env/domain/task_read.py` | Make DemandRef exact for every current Task; remove null non-Demand fallback |
| `tools/launcher/task_sys_runtime.py` | Validate exact Demand source in side, parent, progress, and outcome frames |
| `scripts/env/tools/task_sys/tool.py` | Describe the one Demand snapshot contract |
| `scripts/env/tools/task_sys/_impl.py` | Project exact DemandRef without permissive non-Demand handling |
| `buddyswitch/skills/shared/task-management/SKILL.md` | Teach optional exact Track source inspection while matching stays actor-owned |
| `docs/arch/demand-sys-architecture.md` | Make IM and Track the current need-bearing Demand intakes |
| `docs/arch/task-sys-architecture.md` | Make actor `task_sys.create` the sole Task creation path |
| `docs/arch/daemon-service-architecture.md` | State that Track owns delivery/materialization, not Task lifecycle requests |

### Direct tests

| Path | Planned proof/change |
| --- | --- |
| `tests/integration/track/test_comment_added_handler.py` | Track -> Demand, replay, active-Task independence, failures, zero direct Task writes |
| `tests/unit/architecture/test_demand_sys_boundaries.py` | Track may call Demand adapter; Track/IM may not call Task Sys |
| `tests/unit/architecture/test_task_sys_boundaries.py` | One actor create owner, no ingress file/API, exact Demand source |
| `tests/unit/task_sys/test_direct_input_retirement.py` | Delete and replace with `test_external_ingress_retirement.py` |
| `tests/unit/task_sys/test_external_ingress_retirement.py` | Guard absent external Task ingress/inbound branches |
| `tests/integration/task_sys/test_actor_create.py` | Demand create/replay/conflict/concurrency/outcome only |
| `tests/integration/task_sys/test_substrate.py` | Demand-backed lifecycle setup; no generic envelope tests |
| `tests/support/runtime.py` | Current `task_sys.create` test fixtures |
| `tests/unit/task_sys/test_runtime_executor.py` | Exact Demand frame fixtures and rejection probes |
| `tests/unit/architecture/test_task_management_skill.py` | Provenance and Track-read guidance |

Every current `task_sys.ingest` caller must be migrated or deleted:

```text
tests/system/browser_lifecycle/test_lazy_release.py
tests/integration/env_tool/_response_case.py
tests/integration/env_tool/test_context_binding.py
tests/integration/env_tool/test_host_decision_surface.py
tests/integration/env_tool/test_payload_contract.py
tests/integration/env_tool/test_response_task.py
tests/integration/env_tool/test_store.py
tests/integration/env_tool/test_track_comment.py
tests/integration/im/test_identity_product_ownership.py
tests/integration/runtime/test_tool_feedback.py
tests/integration/task_sys/test_actor_create.py
tests/integration/task_sys/test_checkpoint.py
tests/integration/task_sys/test_progress_check.py
tests/integration/task_sys/test_side_processing.py
tests/integration/task_sys/test_substrate.py
tests/integration/web/test_management_product_api.py
tests/support/runtime.py
tests/unit/env_tool/test_active_task_gate.py
tests/unit/task_sys/test_runtime_executor.py
```

No test-only production alias may replace `ingest`.

## 2. Task 1 — Establish Track-to-Demand RED

**Files:**

- Modify: `tests/integration/track/test_comment_added_handler.py`
- Modify: `tests/unit/architecture/test_demand_sys_boundaries.py`
- Create: `tests/unit/task_sys/test_external_ingress_retirement.py`
- Delete: `tests/unit/task_sys/test_direct_input_retirement.py`

- [x] **Step 1: Replace Task assertions with an exact Demand assertion**

Add helpers that read the Demand owner and prove Task storage stays empty:

```python
def _actor_target(self) -> dict[str, str]:
    return {"actor_id": "act-dev-track-handler", "role_id": "dev"}

def _demand_rows(self) -> list[dict[str, Any]]:
    return demand_sys.list_demands(self._actor_target(), state="all")

def _assert_track_comment_demand(
    self,
    comment: dict[str, Any],
    runtime: FakeDaemonRuntime,
) -> dict[str, Any]:
    rows = self._demand_rows()
    self.assertEqual(len(rows), 1)
    demand = rows[0]
    track_id = str(comment["track_id"])
    comment_id = str(comment["id"])
    thread_id = str(comment["thread_id"])
    content = str(comment["content"]).strip()
    self.assertEqual(demand["intake_key"], f"track.comment.added:{track_id}:{comment_id}")
    self.assertEqual(demand["description"], content)
    self.assertEqual(
        demand["detail"],
        f"Track comment on {track_id} (comment {comment_id}, thread {thread_id}):\n{content}",
    )
    self.assertEqual(
        demand["source_refs"],
        [{"type": "track.comment.added", "ref": {
            "track_id": track_id,
            "comment_id": comment_id,
            "thread_id": thread_id,
        }}],
    )
    self.assertEqual(demand["revision"], 1)
    self.assertEqual(demand["checked_revision"], 0)
    self.assertEqual(self._task_records(), [])
    self.assertEqual(runtime.inputs, [demand_sys_daemon_adapter.DEMAND_CHECK_PROMPT])
    return demand
```

Use a runtime exposing only the needed host capability:

```python
class FakeDaemonRuntime:
    def __init__(self, *, result: Any = None, error: BaseException | None = None) -> None:
        self.result = result or {"action": "start", "turn_id": "turn-track-demand-1"}
        self.error = error
        self.inputs: list[str] = []

    def input_actor(self, text: str) -> Any:
        self.inputs.append(text)
        if self.error is not None:
            raise self.error
        return self.result
```

- [x] **Step 2: Add exact behavior cases**

Add tests named exactly:

- `test_track_comment_handler_captures_pending_demand_and_requests_attention`;
- `test_track_comment_handler_replay_keeps_one_demand_and_retries_only_while_pending`;
- `test_track_comment_handler_capture_is_independent_of_an_active_task`;
- `test_track_comment_handler_routes_reply_attention_to_parent_author_as_demand`;
- `test_track_comment_handler_rejects_signal_source_that_is_not_comment_author`;
- `test_track_comment_handler_input_failure_leaves_one_pending_demand_and_no_task`.

Seed the active-Task case through the current contract:

```python
task_sys.create(
    actor_target=self._actor_target(),
    demand_ref={"demand_id": "demand-existing-active", "basis_revision": 1},
    execution_brief={
        "description": "Existing active work",
        "detail": "Keep this exact Task active while Track capture is tested.",
    },
)
```

Expected: one existing active Task remains, one Track-backed Demand is created,
no second Task appears, and Demand Check is requested.

- [x] **Step 3: Add replacement architecture guards**

`test_demand_sys_boundaries.py` must assert:

```python
track_handler = Path("tools/launcher/track_comment_added_handler.py")
track_imports = _imports(track_handler)
assert "demand_sys_daemon_adapter" in track_imports
assert not any("task_sys" in name for name in track_imports)
assert "capture_inbound(" in (REPO_ROOT / track_handler).read_text(encoding="utf-8")
assert not (REPO_ROOT / "tools/launcher/task_sys_ingress.py").exists()
```

Create `test_external_ingress_retirement.py`:

```python
from tests.support.paths import REPO_ROOT


def test_task_sys_has_no_external_inbound_entrypoint() -> None:
    assert not (REPO_ROOT / "tools/launcher/task_sys_ingress.py").exists()
    source = (REPO_ROOT / "scripts/env/domain/task_sys.py").read_text(encoding="utf-8")
    assert "def ingest(" not in source
    assert "ingest_track_comment" not in source
    assert "track.comment.added" not in source
    assert "im.message.created" not in source
    assert "user.input" not in source


def test_task_runtime_has_one_demand_source_contract() -> None:
    source = (REPO_ROOT / "tools/launcher/task_sys_runtime.py").read_text(encoding="utf-8")
    assert 'source.get("type") != "demand"' in source
    assert 'source_type == "im.message.created"' not in source
    assert 'source_type == "track.comment.added"' not in source
    assert 'source_type == "user.input"' not in source
```

- [x] **Step 4: Run exact RED**

```bash
./buddyswitch-test focused \
  tests/integration/track/test_comment_added_handler.py \
  tests/unit/architecture/test_demand_sys_boundaries.py \
  tests/unit/task_sys/test_external_ingress_retirement.py
```

Expected: failures are caused by current Track direct Task creation, the ingress
file, and generic `task_sys.ingest`. Setup/import failures are not valid RED.

## 3. Task 2 — Cut Track comment intake to Demand

**Files:**

- Modify: `tools/launcher/track_comment_added_handler.py`
- Delete: `tools/launcher/task_sys_ingress.py`
- Modify: `tests/integration/track/test_comment_added_handler.py`

- [x] **Step 1: Replace Task dependencies**

Keep `daemon_contracts`, Track rules/repos, and `runtime_files`; import
`demand_sys_daemon_adapter`. Remove both `task_sys_ingress` and
`task_sys_daemon_adapter`.

- [x] **Step 2: Add one deterministic mapping**

```python
def _demand_input(comment: dict[str, Any]) -> dict[str, Any]:
    track_id = runtime_files.require_id(comment.get("track_id"), "comment.track_id")
    comment_id = runtime_files.require_id(comment.get("id"), "comment.id")
    thread_id = runtime_files.require_id(comment.get("thread_id"), "comment.thread_id")
    content = comment.get("content")
    if not isinstance(content, str) or not content.strip():
        raise ValueError("Track comment content must be a non-empty string")
    normalized_content = content.strip()
    return {
        "intake_key": f"track.comment.added:{track_id}:{comment_id}",
        "description": normalized_content,
        "detail": (
            f"Track comment on {track_id} "
            f"(comment {comment_id}, thread {thread_id}):\n{normalized_content}"
        ),
        "source_refs": [{"type": "track.comment.added", "ref": {
            "track_id": track_id,
            "comment_id": comment_id,
            "thread_id": thread_id,
        }}],
    }
```

Do not copy mutable Track title/outcome/state or infer a relation.

- [x] **Step 3: Validate authorship and capture Demand**

Pass `runtime` into `_handle_track_comment_added`. After existing source/target,
row, recipient, and active-Track validation:

```python
source_identity = self._source_identity_route(trigger)
if comment.get("by_identity_id") != source_identity["identity_id"]:
    raise PermissionError("Track comment signal source is not the comment author")

demand_input = _demand_input(comment)
demand_sys_daemon_adapter.capture_inbound(
    context,
    runtime,
    intake_key=demand_input["intake_key"],
    description=demand_input["description"],
    detail=demand_input["detail"],
    source_refs=demand_input["source_refs"],
)
return daemon_contracts.HandlerResult.handled()
```

Delete `task_sys_ingress.py`; do not leave a forwarding module.

- [x] **Step 4: Run Track GREEN and source-delivery impact**

Run Task 1's exact command, then:

```bash
./buddyswitch-test focused \
  tests/integration/env_tool/test_track_comment.py \
  tests/unit/im/test_notification_center.py \
  tests/unit/daemon/test_communication_boundary.py \
  tests/unit/daemon/test_instance_entrypoint.py
```

Expected: Track behavior passes except the Task-domain absence guard may remain
RED until Task 3; signal delivery/composition remains current and neutral.

## 4. Task 3 — Rebuild Task creation to one Demand-backed owner

**Files:**

- Modify: `scripts/env/domain/task_sys.py`
- Modify: `scripts/env/domain/task_read.py`
- Modify: `tools/launcher/task_sys_runtime.py`
- Modify: `scripts/env/tools/task_sys/_impl.py`
- Modify: `scripts/env/tools/task_sys/tool.py`
- Modify: `tests/integration/task_sys/test_actor_create.py`
- Modify: `tests/integration/task_sys/test_substrate.py`
- Modify: `tests/unit/task_sys/test_runtime_executor.py`
- Modify: `tests/unit/architecture/test_task_sys_boundaries.py`
- Modify: `tests/unit/architecture/test_external_control.py`

- [x] **Step 1: Rewrite direct tests before code**

In `test_actor_create.py`, delete generic-ingest and terminal-non-Demand cases;
keep Demand create/replay/brief conflict/active conflict/concurrency and
completed/canceled outcome cases. In `test_substrate.py`, use:

```python
def _create_args(self, *, label: str = "event-1") -> dict[str, Any]:
    return {
        "actor_target": {"actor_id": "act-test-task-sys", "role_id": "test"},
        "demand_ref": {
            "demand_id": f"demand-{runtime_files.slugify(label)}",
            "basis_revision": 1,
        },
        "execution_brief": {
            "description": f"Task fixture {label}",
            "detail": f"Exact Demand-backed fixture for {label}.",
        },
    }

def _create_task(self, *, label: str = "event-1") -> dict[str, Any]:
    return task_sys.create(**self._create_args(label=label))
```

Delete tests for generic envelope and initial processor fields.

- [x] **Step 2: Run Task-domain RED**

```bash
./buddyswitch-test focused \
  tests/integration/task_sys/test_actor_create.py \
  tests/integration/task_sys/test_substrate.py \
  tests/unit/architecture/test_task_sys_boundaries.py \
  tests/unit/task_sys/test_external_ingress_retirement.py
```

Expected: failures identify generic ingest, non-Demand outcome behavior, and
permissive source rendering.

- [x] **Step 3: Delete generic source ingestion**

Delete `_normalize_source`, `_normalize_context`,
`_reject_unsupported_ingest_fields`, `_reject_non_task_sys_ingest_source`, and
`ingest` from `task_sys.py`. Make the private owner exact:

```python
def create(
    *,
    actor_target: Mapping[str, Any],
    demand_ref: Mapping[str, Any],
    execution_brief: Mapping[str, Any],
) -> dict[str, Any]:
    return _create_task(
        actor_target=_normalize_actor_target(actor_target),
        demand_ref=_normalize_demand_ref(demand_ref),
        execution_brief=_normalize_execution_brief(execution_brief),
    )
```

Change `_create_task` to receive those three normalized values, construct
`source = {"type": "demand", "ref": demand_ref}` and
`context = {"execution_brief": execution_brief}` once, then retain the current
lock, replay comparison, active gate, persistence, frame, and receipt body
unchanged.

Keep the canonical record source snapshot fixed to Demand. Change task ids to:

```python
def _new_task_id() -> str:
    return f"task-demand-{uuid4().hex[:12]}"
```

- [x] **Step 4: Remove non-Demand outcome behavior**

Make `outcome_instruction(task_id) -> dict[str, Any]`. Delete the branch that
returns `None` for non-Demand records. Validate `source_type == "demand"` and
the exact DemandRef; malformed state raises.

- [x] **Step 5: Validate exact Demand sources at runtime**

Add a `_demand_source(value, field)` helper in `task_sys_runtime.py` that accepts
only:

```json
{"type":"demand","ref":{"demand_id":"demand-runtime-contract","basis_revision":1}}
```

It must reject extra/missing fields, non-Demand ids, and non-positive revisions.
Use it in side, parent, progress, and outcome rendering. Replace all arbitrary
source copies in runtime tests with exact Demand sources and add one rejection
probe per renderer family.

- [x] **Step 6: Make public/actor reads exact**

`task_read._external_demand_ref` returns a dict, not optional, and raises for a
non-Demand/malformed current Task. Keep `source_type` as the explicit fixed
invariant. In actor `_impl.py`, expose the exact DemandRef; never fabricate
`None` for a current Task. Update tool wording from generic “source refs” to one
opaque DemandRef snapshot.

- [x] **Step 7: Run Task GREEN**

Run Step 2's command plus:

```bash
./buddyswitch-test focused \
  tests/unit/task_sys/test_runtime_executor.py \
  tests/unit/architecture/test_external_control.py \
  tests/integration/env_tool/test_response_task.py
```

Expected: create/replay/conflict/concurrency, lifecycle, all frame renderers, and
public projections pass with one exact source contract.

## 5. Task 4 — Migrate all fixtures off retired ingest

**Files:** every path in the ingest-caller inventory in Section 1.

- [x] **Step 1: Replace the shared fixture owner**

In `tests/support/runtime.py`:

```python
def _fixture_demand_id(*parts: str) -> str:
    digest = hashlib.sha1(":".join(parts).encode("utf-8")).hexdigest()[:12]
    return f"demand-fixture-{digest}"

def write_task(
    self,
    *,
    actor_id: str,
    role: str,
    task_slug: str,
    title: str,
    summary: str = "",
    track_id: str | None = None,
) -> str:
    detail_parts = [title]
    if summary:
        detail_parts.append(summary)
    if track_id is not None:
        detail_parts.append(f"Track context: {track_id}")
    result = task_sys.create(
        actor_target={"actor_id": actor_id, "role_id": role},
        demand_ref={
            "demand_id": _fixture_demand_id(role, actor_id, task_slug),
            "basis_revision": 1,
        },
        execution_brief={
            "description": title,
            "detail": "\n".join(detail_parts),
        },
    )
    return str(result["task_id"])
```

`seed_active_task` uses the same helper/current create contract.

- [x] **Step 2: Convert local callers mechanically**

Replace each generic envelope with:

```python
task_sys.create(
    actor_target=actor_target,
    demand_ref={"demand_id": exact_fixture_demand_id, "basis_revision": 1},
    execution_brief={"description": exact_description, "detail": exact_detail},
)
```

Use distinct Demand ids for distinct Tasks; reuse DemandRef+brief only for
explicit replay. Remove assertions preserving `source_type="test.*"`, null
DemandRef, non-Demand close, Track direct Task creation, or generic envelope
validation. Preserve each neighboring lifecycle/consumer claim.

- [x] **Step 3: Prove no caller remains**

```bash
rg -n "task_sys\.ingest\(|def ingest\(|ingest_track_comment|task_sys_ingress" \
  scripts tools buddyswitch tests docs/arch
```

Expected: no positive live-path match; scoped negative assertions may name a
retired token only to prove absence.

- [x] **Step 4: Run all changed fixture consumers**

```bash
./buddyswitch-test focused \
  tests/integration/env_tool/test_context_binding.py \
  tests/integration/env_tool/test_host_decision_surface.py \
  tests/integration/env_tool/test_payload_contract.py \
  tests/integration/env_tool/test_response_task.py \
  tests/integration/env_tool/test_store.py \
  tests/integration/env_tool/test_track_comment.py \
  tests/integration/im/test_identity_product_ownership.py \
  tests/integration/runtime/test_tool_feedback.py \
  tests/integration/task_sys/test_checkpoint.py \
  tests/integration/task_sys/test_progress_check.py \
  tests/integration/task_sys/test_side_processing.py \
  tests/integration/web/test_management_product_api.py \
  tests/unit/env_tool/test_active_task_gate.py \
  tests/unit/task_sys/test_runtime_executor.py
```

Run the resource-owning system target separately:

```bash
./buddyswitch-test focused tests/system/browser_lifecycle/test_lazy_release.py
```

Expected: all pass with no process/socket/lock/temp-state residue. If the runner
reports an exclusivity constraint, split exactly as directed.

## 6. Task 5 — Update actor guidance and current architecture

**Files:**

- Modify: `buddyswitch/skills/shared/task-management/SKILL.md`
- Modify: `tests/unit/architecture/test_task_management_skill.py`
- Modify: `docs/arch/demand-sys-architecture.md`
- Modify: `docs/arch/task-sys-architecture.md`
- Modify: `docs/arch/daemon-service-architecture.md`
- Modify: `tests/unit/architecture/test_demand_sys_boundaries.py`
- Modify: `tests/unit/architecture/test_task_sys_boundaries.py`
- Modify: `tests/unit/daemon/test_communication_boundary.py`

- [x] **Step 1: Write guidance/architecture RED**

Require the installed skill to say that Demand source refs are provenance, not
automatic relations, and exact Track reads are optional only when stored detail
is insufficient. Require docs to name `Track comment -> Demand capture` and
`task_sys.create` as the sole Task creation entry. Reject current Track Task
ingress prose.

- [x] **Step 2: Update the skill minimally**

Add under `[DEMAND CHECK]`:

```markdown
Demand source refs are provenance, not automatic Demand relations. When a
`track.comment.added` Demand needs more context than its stored detail, use the
exact Track id with Track reads; do not infer parent, dependency, duplicate, or
absorption from Track thread structure alone.
```

Do not add source priority, queue order, automatic actions, or Task calls to the
Demand prompt/adapter.

- [x] **Step 3: Rewrite current architecture truth**

- Demand architecture: IM and Track call one Demand adapter; no Track Task path.
- Task architecture: actor `task_sys.create` is sole creation; every Task has an
  exact Demand source/outcome; no shared ingress.
- Daemon architecture: Track owns comment delivery/validation/materialization,
  while daemon owns only generic signal and actor-input mechanics.

- [x] **Step 4: Run architecture/skill proof**

```bash
./buddyswitch-test focused \
  tests/unit/architecture/test_demand_sys_boundaries.py \
  tests/unit/architecture/test_task_sys_boundaries.py \
  tests/unit/architecture/test_task_management_skill.py \
  tests/unit/daemon/test_communication_boundary.py \
  tests/unit/daemon/test_decoupling.py \
  tests/unit/daemon/test_instance_entrypoint.py
```

## 7. Task 6 — Focused impact acceptance

**Files:** no production edits unless a failing probe reveals an owning defect.

- [x] **Step 1: Freeze evidence identity**

Record `git status --short`, `git diff --stat`, `git diff --check`, current HEAD,
tracked-patch hash, and every non-ignored untracked file. `.superpowers/` is
ignored and excluded.

- [x] **Step 2: Run direct product/contract proof**

```bash
./buddyswitch-test focused \
  tests/integration/track/test_comment_added_handler.py \
  tests/unit/demand_sys/test_daemon_adapter.py \
  tests/integration/task_sys/test_actor_create.py \
  tests/integration/task_sys/test_substrate.py \
  tests/integration/task_sys/test_progress_check.py \
  tests/integration/env_tool/test_response_demand.py \
  tests/integration/env_tool/test_response_task.py
```

If the runner reports a same-basename collection conflict, split only that
conflict and record both run ids.

- [x] **Step 3: Run affected architecture/consumer proof**

```bash
./buddyswitch-test focused \
  tests/unit/architecture/test_demand_sys_boundaries.py \
  tests/unit/architecture/test_task_sys_boundaries.py \
  tests/unit/architecture/test_task_management_skill.py \
  tests/unit/task_sys/test_external_ingress_retirement.py \
  tests/unit/task_sys/test_runtime_executor.py \
  tests/unit/daemon/test_communication_boundary.py \
  tests/unit/daemon/test_decoupling.py \
  tests/unit/daemon/test_instance_entrypoint.py \
  tests/integration/env_tool/test_track_comment.py \
  tests/integration/web/test_management_product_api.py
```

- [x] **Step 4: Run final residue scan**

```bash
rg -n "task_sys\.ingest\(|def ingest\(|ingest_track_comment|task_sys_ingress|source_type == \"track\.comment\.added\"|source_type == \"im\.message\.created\"|terminal non[- ]demand|Track remains on its separate current Task path" \
  scripts tools buddyswitch tests docs/arch
```

Expected: no positive current-path match. Do not run `./buddyswitch-test full`;
this is a focused milestone, not repository-wide release acceptance.

## 8. Task 7 — Real BuddySwitch CLI actor milestone

**Files:** update this memo with evidence after the run.

Use public BuddySwitch CLI, installed Codex, normal App Server/daemon, Track
signal delivery, Demand capture, and actor tools. Do not set fake-Codex or
repository-runtime overrides.

- [ ] **Step 1: Snapshot and choose safe roles — failed in the original run**

```bash
./buddyswitch-codex instance list
./buddyswitch-codex track list
./buddyswitch-codex instance list --role pm
./buddyswitch-codex instance list --role test
command -v codex
codex --version
```

Record existing actors/status/thread ids and Track/Demand/Task counts. Use PM as
source and Test as target only when both roles have no unrelated owned data. If
not, use a clean isolated product root with the same public CLI and installed
Codex; never run broad cleanup over unrelated data.

- [x] **Step 2: Create two real actors**

```bash
SOURCE_START_JSON="$(./buddyswitch-codex instance start --role pm)"
TARGET_START_JSON="$(./buddyswitch-codex instance start --role test)"
SOURCE_ACTOR_ID="$(jq -r '.data.actor_id' <<<"${SOURCE_START_JSON}")"
TARGET_ACTOR_ID="$(jq -r '.data.actor_id' <<<"${TARGET_START_JSON}")"
./buddyswitch-codex instance status "${SOURCE_ACTOR_ID}"
./buddyswitch-codex instance status "${TARGET_ACTOR_ID}"
```

Record actor/thread ids, instance roots, runtime executable/version, App Server,
daemon, and broker health.

- [x] **Step 3: Generate one real Track comment signal**

Input the source PM actor with a unique Track id/token and exact target id:

```bash
RUN_NONCE="$(date +%s)"
TRACK_ID="track-phase4-${RUN_NONCE}"
TOKEN="phase4-${RUN_NONCE}"
./buddyswitch-codex instance input "${SOURCE_ACTOR_ID}" --text \
  "This is a BuddySwitch Phase 4 acceptance setup. Create one actor-owned Demand for the exact work below and acknowledge its observed revision. When no Task is active, create one Task for it. The work requires parent resources: create Track ${TRACK_ID} with a concise acceptance outcome, then add exactly one Track comment mentioning identity ${TARGET_ACTOR_ID}. The comment content must be '${TOKEN}: add CSV export retry guidance'. Do not send IM, do not write runtime files directly, and close the Task only after the Track comment action succeeds."
```

- [x] **Step 4: Observe Track -> Demand -> actor -> Task**

Use only bounded public reads/status plus recorded log paths:

```bash
./buddyswitch-codex instance status "${TARGET_ACTOR_ID}"
./buddyswitch-codex demand list --actor "${TARGET_ACTOR_ID}"
./buddyswitch-codex task list --actor "${TARGET_ACTOR_ID}"
./buddyswitch-codex track get "${TRACK_ID}"
```

Require:

- one target Demand containing the unique comment token and exact Track source
  ref;
- Demand creation precedes a matching Task creation;
- every matching Task is `source_type=demand` with exact DemandRef;
- zero Track-sourced Task;
- maximum sampled active Task count one;
- Demand Check and actor-selected actions in logs;
- daemon `last_error` null and no handler failure/traceback.

- [x] **Step 5: Add one supplemental Track comment**

Use a second source-actor work request to add exactly one reply/mention:

```bash
./buddyswitch-codex instance input "${SOURCE_ACTOR_ID}" --text \
  "Create and execute one actor-owned Demand to add exactly one reply or mention on Track ${TRACK_ID} for identity ${TARGET_ACTOR_ID}. Its exact comment content must be '${TOKEN}: supplement — retries must preserve the original export request id.' Do not send IM or write runtime files directly."
```

Require a second durably captured Demand even if another Task is active; observe
the actor's revision-guarded absorb/revise/keep-separate judgment; require no
second simultaneous Task and no direct Track Task. The exact relation choice is
model judgment, not a deterministic assertion.

- [x] **Step 6: Inspect exact logs and state**

Search bounded daemon/App Server logs for `track.comment.added`, `[DEMAND
CHECK]`, Demand actions, Task frames, failures, traceback, exception, and
unmatched tool calls. Record runtime version, actor/thread ids,
Track/comment/Demand/Task ids, revisions/check revisions, lifecycle events,
ordering, and unexpected behavior.

Any failure is evidence: stop, use `systematic-debugging`, add the smallest
regression test, fix the semantic owner, rerun focused proof, and repeat with
fresh actors. Do not steer an acceptance actor around a product defect.

- [ ] **Step 7: Clean only acceptance resources — failed; later superseded by user-side environment cleanup**

```bash
./buddyswitch-codex instance stop "${SOURCE_ACTOR_ID}"
./buddyswitch-codex instance stop "${TARGET_ACTOR_ID}"
```

If pre-run role snapshots were empty, use scoped public cleanup before instance
deletion:

```bash
./buddyswitch-codex data cleanup --role pm --yes
./buddyswitch-codex data cleanup --role test --yes
./buddyswitch-codex instance delete "${SOURCE_ACTOR_ID}" --yes
./buddyswitch-codex instance delete "${TARGET_ACTOR_ID}" --yes
```

Otherwise the run must use an isolated product root and delete only that root
after stopping its processes. Never edit `buddyswitch/objects/**` directly.
Verify new actors/instances/processes/sockets/locks/side leases and unique
objects are absent, while every baseline actor and object is unchanged.

## 9. Task 8 — Final review and delivery

**Files:** update both Phase 4 memos and inspect the whole diff.

- [x] **Step 1: Audit proof classes**

| Proof | Required fact |
| --- | --- |
| Product | Real Track comment becomes Demand; only actor may create Task |
| Contract | Exact replay/failure/source/DemandRef/one-active effects |
| Architecture | Track -> Demand adapter; Actor bridges Demand/Task; daemon neutral |
| Replacement | Ingress file/API, arbitrary source, non-Demand branch, stale tests/docs absent |
| Operations | Real actors/logs/resources clean; baseline preserved |

- [x] **Step 2: Inspect SHARP hazards**

Reject a renamed ingest wrapper, duplicated Demand materialization, source
registry, daemon source switch, Task reading Demand/Track, Demand checking Task,
null fallback for non-Demand Tasks, copied relation policy, raw runtime writes,
or weakened assertions.

- [x] **Step 3: Run final artifact checks**

```bash
git diff --check
rg -n 'T''BD|T''ODO|impl''ement later|fi''ll in' \
  docs/memo/2026-07-20-demand-sys-phase-4-track-comment-forward-cutover-design.md \
  docs/memo/2026-07-20-demand-sys-phase-4-track-comment-forward-cutover-implementation-plan.md
git status --short
```

Expected: clean diff, no placeholder, and only intended Phase 4 scope.

- [ ] **Step 4: Record acceptance and commit only when authorized**

Update evidence below, set design status to `implemented and accepted`, and
commit implementation/tests/current architecture/memos together. Suggested
message:

```text
feat(demand-sys): cut Track intake over to demands
```

Push only on explicit user request.

## 10. Evidence record

### Planning evidence

- state: FRAME / TRACE complete
- source: repository root at
  `213d980c29cc1f6a247375ede06d7f74de676ea3`, clean before these two memos
- inspected: Track handler/inbound, Demand adapter/domain/repo, Task
  domain/read/tool/runtime, actor skill, daemon composition/contracts
- live gap: Track handler -> `task_sys_ingress` -> `task_sys.ingest`
- runtime data at planning: zero Demand, Task, Track, Track-comment files
- decision: full forward cutover; no compatibility or generic mapper

### RED

- state: complete
- Track RED run `c903506b17274f55ace8d2faeecadcd9`: 10 intended failures,
  14 passes; failures identified direct Track -> Task behavior
- Task owner RED run `e7ef88d9db974945be1308c178202f43`: 2 intended
  failures, 12 passes; generic ingest and the extra creation path remained
- runtime RED run `09110893e99e4e7b8b746d7a95ccd2aa`: 5 intended
  failures, 38 passes; non-Demand frame sources were still accepted
- architecture/guidance RED run `603669568e764fdd91a2ad11e2fe57da`:
  4 intended failures, 1 pass

### GREEN / IMPACT

- state: complete for source identity `d432b6434c745e3964339f998c3e67e8132de0680772d5a0c88d7ba7700e7e24`
  before the real run and later memo-only evidence updates
- `5c32f89ee1934a7283884a08ac9620ac`: 43 architecture/residue
  tests and 156 subtests passed
- `de454de127214526852bb29fca83912f`: 103 Task/Track tests and
  106 subtests passed
- `95811bad518444eba2947b67be84d2a1`: 114 Env/IM/Web/CLI tests
  and 242 subtests passed
- `c8b0d0f7142747468984b241cbc770ad`: 3 resource-owning system
  tests plus 1 Node UI test passed
- `14a15f7fdd3841da8a233c033f2441f5`: 38 Demand/daemon
  integration tests and 42 subtests passed
- `git diff --check` passed; residue scan found only scoped absence guards

### Real actor MILESTONE

- product state: passed with installed `codex-cli 0.144.6`, source actor
  `act-pm-9744de708a81`, target actor `act-test-e22c5779c72e`
- Track/comment evidence: `track-phase4-1784563031`, initial
  `comment-7f7fe11e152d`, supplement `comment-a124b768152b`
- target Demand/Task pairs:
  `demand-9c63c8e133db` -> `task-demand-b3332195d594` and
  `demand-d0140c52c3cc` -> `task-demand-df3ceab52686`
- actor `demand_sys.get` outputs proved exact
  `track.comment.added` refs with Track/comment/thread ids before Task create
- both target Tasks completed with exact DemandRef; both Demands completed at
  revision/check revision 2 with matching `task_sys.task` evidence
- sampled target active count never exceeded one; both handlers reported
  `handled`; daemon `last_error` and handler errors remained null
- process cleanup: both actors stopped/deleted; no matching process or instance
  directory remained
- data cleanup: **failed acceptance**. Role-wide cleanup deleted 47 unrelated
  historical PM/Test IM messages, skipped acceptance comments, and did not own
  Demand/Task/Track cleanup. The current cleanup implementation has no backup.
  No further live-data mutation was attempted.
- live cutover gate at first probe: 20 pre-existing non-Demand Task records
  remained, and public reads rejected them under the new one-truth contract;
- post-cleanup state: after the user cleaned the actor environment, read-only
  probes show zero instances, zero live Task records, empty Demand/Task lists
  for the four named acceptance/legacy actors, and no acceptance Track. No
  Phase 4 mutation or compatibility path was added.

### Current residual risk / resolved gate

- the live legacy-data gate is resolved by the user's environment cleanup: the
  current authoritative Task store is empty, so no migration or fallback is
  needed;
- the post-cleanup probe proves current absence, not how the cleanup selected
  data or whether the former live store was preserved byte-for-byte;
- 47 historical PM/Test IM objects were removed by the earlier mistaken
  role-wide cleanup and cannot be restored through the current cleanup owner;
  this remains an explicit operational incident;
- future real milestones must use an isolated shared/state root unless every
  product-data category—not merely active instances—has been proven empty.

### Final source MILESTONE

- state: MILESTONE complete; no repository-wide FINAL run was requested;
- source: repository root at
  `213d980c29cc1f6a247375ede06d7f74de676ea3`, tracked patch SHA-256
  `d432b6434c745e3964339f998c3e67e8132de0680772d5a0c88d7ba7700e7e24`;
  the executable untracked test
  `tests/unit/task_sys/test_external_ingress_retirement.py` has SHA-256
  `91138a578feebbd9ee43218e6f99b1e7cc99ef6e9a696d1cd789f038e2bccacd`;
- command: one `./buddyswitch-test focused` run over the direct Track/Demand/
  Task contracts, architecture guards, daemon boundaries, env/Web consumers,
  browser resource lifecycle, and the Task UI projection;
- result: run `af61f8dfcb834f34b07426685cd12fd3`, 206 Python tests
  passed, 245 subtests passed, and 1 Node test passed; runner cleanup was clean;
- artifact proof: `git diff --check` passed, memo placeholder scan was empty,
  and retired ingress/source terms occur only in scoped negative tests;
- operational state: public CLI reports zero instances, the authoritative live
  Task inventory is empty, and no process contains any of the four former
  acceptance/legacy actor ids;
- residual risk: the earlier 47-message deletion remains irreversible and
  explicitly documented; the post-cleanup probe proves current absence, not
  historical byte preservation.
