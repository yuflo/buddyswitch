# Demand Sys Phase 1 Standalone Forward-Rebuild Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build one independently runnable, actor-owned Demand Sys that atomically supports capture, two-pass check, constrained-hybrid organization, acknowledgement, and terminalization without touching Task Sys, inbound handlers, or daemon registration.

**Architecture:** One Demand domain owner operates on one locked aggregate per actor. The actor-facing native MCP tool and read-only public CLI are projections of that owner; they do not own rules or persistence. Phase 1 deliberately has no proactive wake and no Demand/Task integration.

**Tech Stack:** Python 3, JSON runtime objects, `fcntl.flock`, existing `runtime_files.write_json_object`, existing env.tool/native-MCP registry, BuddySwitch public CLI, `unittest`/`pytest` through `./buddyswitch-test` only.

**Design:** `docs/memo/2026-07-19-demand-sys-phase-1-standalone-forward-rebuild-design.md`

---

## 1. Frozen implementation scope

This plan implements Phase 1 only. It must not create or modify a Demand daemon adapter, inbound source adapter, Task action, Task schema, attention wake, Web UI, feature flag, legacy reader, compatibility alias, or migration path.

The implementation acceptance claim is:

```text
real actor -> demand_sys native actions -> Demand domain -> one atomic actor aggregate
public CLI -> Demand read projection --------------------^

Task records: 0
Demand daemon registrations: 0
Demand inbound registrations: 0
alternate Demand write paths: 0
```

## 2. File map

### New product files

| File | Sole responsibility |
| --- | --- |
| `scripts/env/repos/demands.py` | Demand aggregate path, lock, strict load, and one atomic transaction write |
| `scripts/env/domain/demand_sys.py` | Canonical Demand validation, lifecycle, revision, check, relation, and receipt semantics |
| `scripts/env/domain/demand_read.py` | External-safe read projections only |
| `scripts/env/tools/demand_sys/__init__.py` | Demand tool package marker |
| `scripts/env/tools/demand_sys/tool.py` | Actor-visible action definitions and JSON input schemas |
| `scripts/env/tools/demand_sys/_impl.py` | ToolContext-to-domain adapter and stable tool result mapping |
| `docs/arch/demand-sys-architecture.md` | Current implemented Demand ownership and boundary contract |

### Existing product files modified

| File | Exact change |
| --- | --- |
| `scripts/env/tool_runtime/context.py` | Inject the Demand semantic owner in `DomainAccess`; list the Demand read source |
| `scripts/env/tool_runtime/role_auth.py` | Add the exact `demand_sys.*` permissions to the one common permission owner |
| `tools/launcher/cli.py` | Add read-only `demand list/get`; no Demand mutation command |
| `README.md` | Publish the two public Demand read commands and no alternate runtime invocation |

### New tests

| File | Proof |
| --- | --- |
| `tests/unit/demand_sys/test_capture_and_check.py` | create/revise/idempotency/check/ack |
| `tests/unit/demand_sys/test_organization.py` | parent/dependency/split/absorb/duplicate/supersede/terminal rules |
| `tests/integration/demand_sys/test_repository_atomicity.py` | process-level serialization and no partial aggregate |
| `tests/integration/env_tool/test_response_demand.py` | actor tool contract, scope, errors, and no Task effects |
| `tests/process/launcher/test_demand_commands.py` | public CLI read projection and failure contract |
| `tests/unit/architecture/test_demand_sys_boundaries.py` | one owner, forbidden dependencies, no Phase 2-4 registration |

### Existing tests modified

| File | Exact change |
| --- | --- |
| `tests/unit/actor/test_role_action_auth.py` | Demand permissions are available to every manifest actor role |
| `tests/integration/env_tool/test_context_binding.py` | `demand_sys` appears in the discovered actor tool catalog and context sources |
| `tests/process/cli/test_env_native_mcp_projection.py` | Native MCP lists and dispatches a Demand action through the current projection |
| `tests/process/launcher/test_public_cli.py` | Help text publishes only read-only Demand commands |
| `tests/unit/architecture/test_repo_contracts.py` | Demand repository follows current repository ownership constraints |

Do not create `scripts/env/domain/demand.py`, `scripts/env/repos/demand.py`, a second CLI, a Demand-specific test runner, or any `tools/launcher/demand_*` file in Phase 1.

## 3. Public domain contract

Implement these names exactly in `scripts/env/domain/demand_sys.py`; later tasks and tests must not invent aliases:

```python
TERMINAL_TYPES = ("completed", "canceled", "absorbed", "duplicate", "superseded")

class DemandError(ValueError):
    code: str

class DemandNotFound(DemandError):
    code = "E_DEMAND_NOT_FOUND"

class DemandRevisionConflict(DemandError):
    code = "E_DEMAND_REVISION_CONFLICT"

class DemandIntakeConflict(DemandError):
    code = "E_DEMAND_INTAKE_CONFLICT"

class DemandTerminalConflict(DemandError):
    code = "E_DEMAND_TERMINAL"

class DemandRelationConflict(DemandError):
    code = "E_DEMAND_RELATION"

class DemandPayloadError(DemandError):
    code = "E_DEMAND_PAYLOAD"

create(actor_target, intake_key, description, detail, source_refs) -> dict[str, Any]
revise(actor_target, demand_id, expected_revision, description, detail, source_refs=None) -> dict[str, Any]
list_demands(actor_target, state="live") -> list[dict[str, Any]]
get(actor_target, demand_id) -> dict[str, Any]
get_many(actor_target, demand_ids) -> list[dict[str, Any]]
check(actor_target) -> dict[str, Any]
complete_check(actor_target, observed) -> dict[str, Any]
set_parent(actor_target, demand_id, expected_revision, parent_id) -> dict[str, Any]
add_dependency(actor_target, demand_id, expected_revision, dependency_id) -> dict[str, Any]
remove_dependency(actor_target, demand_id, expected_revision, dependency_id) -> dict[str, Any]
split(actor_target, demand_id, expected_revision, description, detail, children) -> dict[str, Any]
absorb_into(actor_target, source_id, source_revision, target_id, target_revision, merged_target, summary) -> dict[str, Any]
mark_duplicate(actor_target, source_id, source_revision, target_id, summary) -> dict[str, Any]
supersede(actor_target, old_id, old_revision, replacement_id, summary) -> dict[str, Any]
complete(actor_target, demand_id, expected_revision, summary, evidence_refs) -> dict[str, Any]
cancel(actor_target, demand_id, expected_revision, summary) -> dict[str, Any]
```

The lines above are the complete public API inventory, expressed as contract signatures rather than executable Python. No additional public mutation entrypoint is allowed.

## Task 1: Atomic Demand repository

**Completed 2026-07-19 in `1f1ad07`.** RED was observed with run
`12b6180ccb1545a9b1591949db2ecebd` because `env.repos.demands` did not exist;
the architecture owner probe independently failed before implementation. Final
GREEN/IMPACT run `9532b692f3424837b328ba53825a4cd3` passed 17 tests and 5
subtests with no retained run root or writer process. Scope audit found one
aggregate path owner, one atomic write call, zero forbidden Task/daemon/inbound
dependencies, and only the three Task 1 implementation files in the code commit.

**Files:**

- Create: `scripts/env/repos/demands.py`
- Create: `tests/integration/demand_sys/test_repository_atomicity.py`
- Modify: `tests/unit/architecture/test_repo_contracts.py`

- [x] **Step 1: Write the repository RED tests**

Add cases with these exact names: `test_absent_actor_state_loads_one_empty_schema_v1_aggregate`, `test_successful_transaction_persists_one_actor_aggregate`, `test_failed_mutator_keeps_previous_aggregate_byte_identical`, `test_two_process_writers_serialize_without_losing_either_change`, and `test_wrong_schema_or_actor_target_is_rejected_without_rewrite`.

Use `RuntimeWorkspaceTestCase` for isolated `BUDDYSWITCH_STATE_ROOT`. The process case launches two short Python children through the existing integration-test process support; each calls the same repository transaction and writes a different Demand id. Assert that the final aggregate contains both ids and that no temporary file remains beside the aggregate.

- [x] **Step 2: Run RED**

```bash
./buddyswitch-test focused tests/integration/demand_sys/test_repository_atomicity.py
```

Expected: collection/import failure because `env.repos.demands` does not exist. This is the intended RED.

- [x] **Step 3: Implement the repository**

The repository contract is:

```python
SCHEMA_VERSION = 1

def actor_state_path(actor_target: Mapping[str, Any]) -> Path:
    actor_id, role_id = normalize_actor_target(actor_target)
    return runtime_files.OBJECTS_ROOT / "demand-sys" / "actors" / f"{actor_id}-{role_id}.json"

def actor_lock_path(actor_target: Mapping[str, Any]) -> Path:
    actor_id, role_id = normalize_actor_target(actor_target)
    return runtime_files.LOCAL_ROOT / "locks" / "demand-sys" / f"{actor_id}-{role_id}.lock"

def load_actor_state(actor_target: Mapping[str, Any]) -> dict[str, Any]:
    """Return a validated deep copy or a fresh empty aggregate."""

def transact_actor_state(
    actor_target: Mapping[str, Any],
    mutator: Callable[[dict[str, Any]], tuple[bool, Any]],
) -> Any:
    """Lock, load, mutate, and atomically replace only when changed is true."""
```

`transact_actor_state` must acquire `fcntl.LOCK_EX`, call the mutator once, require a `(bool, result)` tuple, validate the complete aggregate before writing, call `runtime_files.write_json_object` once when changed, and release the lock in `finally`. Exceptions write nothing.

- [x] **Step 4: Run GREEN and repository architecture proof**

```bash
./buddyswitch-test focused \
  tests/integration/demand_sys/test_repository_atomicity.py \
  tests/unit/architecture/test_repo_contracts.py
```

Expected: all selected tests pass and runner cleanup reports no residual process or temporary root.

- [x] **Step 5: Commit Task 1**

```bash
git add scripts/env/repos/demands.py tests/integration/demand_sys/test_repository_atomicity.py tests/unit/architecture/test_repo_contracts.py
git commit -m "feat(demand-sys): add atomic actor aggregate repository"
```

## Task 2: Capture, revision, and two-pass check owner

**Files:**

- Create: `scripts/env/domain/demand_sys.py`
- Create: `tests/unit/demand_sys/test_capture_and_check.py`

- [x] **Step 1: Write exact lifecycle RED cases**

Cover:

```text
create -> revision 1 / checked 0 / live
same intake_key + same canonical input -> state_changed false
same intake_key + different input -> E_DEMAND_INTAKE_CONFLICT and identical state
revise -> description and detail change together at revision +1
stale revise -> E_DEMAND_REVISION_CONFLICT and identical state
check -> full pending records + all live {id, description}
get_many -> requested actor-owned records in requested order, duplicate ids rejected
complete_check observed current revision -> checked_revision catches up without revision increment
complete_check observed old revision -> newer current revision remains pending
terminal pending record appears in attention_items but not live_index
cross-actor get/list/check never exposes another actor aggregate
```

The D/C fixture must use descriptions from the design memo so the later organization test reuses the same scenario vocabulary.

- [x] **Step 2: Run RED**

```bash
./buddyswitch-test focused tests/unit/demand_sys/test_capture_and_check.py
```

Expected: missing domain functions fail for the intended reason.

- [x] **Step 3: Implement canonical normalization and receipts**

Every mutation result must use this shape:

```python
def _receipt(*, state_changed: bool, changes: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "state_changed": state_changed,
        "changes": changes,
        "check_required": bool(changes),
    }
```

`create` stores exactly the schema in the design memo. `check_required` is false for an idempotent replay and for `complete_check`; pending attention remains independently discoverable through `check`.

Normalize `source_refs` as a list of objects with exactly `type` and object-valued `ref`. Reject unknown top-level Demand fields by constructing records inside the owner rather than copying caller payloads.

- [x] **Step 4: Implement read/check semantics**

Return this exact projection from `check`:

```python
{
    "attention_items": [full_pending_demand_rows],
    "live_index": [
        {"id": demand["id"], "description": demand["description"]}
        for demand in live_demands
    ],
    "pending_count": len(full_pending_demand_rows),
}
```

Sort both collections by `(created_at, id)` for deterministic actor input. `complete_check` returns `acknowledged`, `still_pending`, `state_changed`, and `check_required=False`.

- [x] **Step 5: Run GREEN**

```bash
./buddyswitch-test focused tests/unit/demand_sys/test_capture_and_check.py
```

Expected: all capture/check tests pass.

- [x] **Step 6: Commit Task 2**

```bash
git add scripts/env/domain/demand_sys.py tests/unit/demand_sys/test_capture_and_check.py
git commit -m "feat(demand-sys): own capture revision and check lifecycle"
```

## Task 3: Constrained-hybrid organization and terminal lifecycle

**Files:**

- Modify: `scripts/env/domain/demand_sys.py`
- Create: `tests/unit/demand_sys/test_organization.py`

- [x] **Step 1: Write organization RED cases**

Use exact cases:

```text
set_parent creates one live parent edge
set_parent rejects self, terminal target, missing target, and parent cycle
add_dependency is idempotent for an existing edge
add_dependency rejects self and a dependency cycle
remove_dependency changes only the source Demand
split revises original parent and atomically creates at least two child Demands
absorb D@1 into C@5 -> C@6 live and D@2 terminal absorbed ref C
absorb stale source or target revision -> neither record changes
absorb source with live child -> E_DEMAND_RELATION
mark_duplicate terminalizes source only
supersede terminalizes old only
complete stores summary and evidence refs
cancel stores summary without evidence refs
exact terminal action replay -> state_changed false
different action against terminal Demand -> E_DEMAND_TERMINAL
```

- [x] **Step 2: Run RED**

```bash
./buddyswitch-test focused tests/unit/demand_sys/test_organization.py
```

Expected: missing organization actions fail.

- [x] **Step 3: Implement cycle and terminal invariants**

Parent traversal follows `parent_id` through live records. Dependency traversal follows `depends_on` through live records. A proposed edge is rejected when the target can already reach the source.

All target Demand lookup, revision validation, record construction, and multi-record mutation occurs inside one `transact_actor_state` callback. Do not pre-read then write in a later transaction.

- [x] **Step 4: Implement split and lineage actions**

`split` requires two or more children. Its input child shape is:

```json
{
  "intake_key": "actor-self:csv-export-ui",
  "description": "Expose CSV export controls.",
  "detail": "Add the export control and progress feedback.",
  "source_refs": []
}
```

`absorb_into.merged_target` accepts exactly `description`, `detail`, and `source_refs`. No caller may patch `revision`, `checked_revision`, relations, terminal state, actor target, or timestamps.

- [x] **Step 5: Run GREEN with capture regression**

```bash
./buddyswitch-test focused \
  tests/unit/demand_sys/test_capture_and_check.py \
  tests/unit/demand_sys/test_organization.py
```

Expected: all Demand domain tests pass.

- [x] **Step 6: Commit Task 3**

```bash
git add scripts/env/domain/demand_sys.py tests/unit/demand_sys/test_organization.py
git commit -m "feat(demand-sys): add atomic demand organization"
```

## Task 4: Actor-facing `demand_sys` tool

**Files:**

- Create: `scripts/env/tools/demand_sys/__init__.py`
- Create: `scripts/env/tools/demand_sys/tool.py`
- Create: `scripts/env/tools/demand_sys/_impl.py`
- Modify: `scripts/env/tool_runtime/context.py`
- Modify: `scripts/env/tool_runtime/role_auth.py`
- Create: `tests/integration/env_tool/test_response_demand.py`
- Modify: `tests/unit/actor/test_role_action_auth.py`
- Modify: `tests/integration/env_tool/test_context_binding.py`
- Modify: `tests/process/cli/test_env_native_mcp_projection.py`

- [x] **Step 1: Write actor contract RED tests**

Prove:

```text
registry discovers only demand_sys, never a demand alias
native MCP exposes demand_sys__create/check/get_many/absorb_into/complete_check
all manifest roles are authorized through demand_sys.* common permissions
actor A cannot read or mutate actor B Demand
unknown payload fields return E_DEMAND_PAYLOAD and no state change
stale revision returns E_DEMAND_REVISION_CONFLICT with retry guidance
D->C action response lists both changed ids/revisions
complete_check response exposes acknowledged/still_pending
Task record set is byte-for-byte unchanged across every Demand action
```

- [x] **Step 2: Run RED**

```bash
./buddyswitch-test focused \
  tests/integration/env_tool/test_response_demand.py \
  tests/unit/actor/test_role_action_auth.py \
  tests/process/cli/test_env_native_mcp_projection.py
```

Expected: Demand tool discovery and permissions are absent.

- [x] **Step 3: Define exact actor schemas**

Create one `ToolDefinition(id="demand_sys", actions=DEMAND_ACTIONS)` with the sixteen actions listed in the design. Every schema has `additionalProperties: false`; all existing-Demand mutations require positive integer expected revisions; `state` for list is exactly `live|terminal|all`; `observed` contains unique `{demand_id, revision}` rows.

Use these permissions and add exactly the same strings to `COMMON_ROLE_PERMISSIONS`:

```text
demand_sys.create
demand_sys.revise
demand_sys.list
demand_sys.get
demand_sys.get_many
demand_sys.check
demand_sys.complete_check
demand_sys.set_parent
demand_sys.add_dependency
demand_sys.remove_dependency
demand_sys.split
demand_sys.absorb_into
demand_sys.mark_duplicate
demand_sys.supersede
demand_sys.complete
demand_sys.cancel
```

- [x] **Step 4: Implement the thin tool adapter**

`_impl.py` derives actor target only from `ToolContext.current_actor_identity_profile`; it never accepts actor id or role id from action payloads. It calls `context.rules.demand_sys` and maps `DemandError.code` to a `tool_results.rejection` with `state_changed=False`. Success uses `tool_results.success`, preserving the returned Demand receipt fields.

Add `demand_sys` to `DomainAccess`; do not add Demand to `RepoAccess` because the tool must not bypass the domain owner. Do not add a runtime capability class because Demand Phase 1 has no daemon/runtime capability.

- [x] **Step 5: Run GREEN**

```bash
./buddyswitch-test focused \
  tests/integration/env_tool/test_response_demand.py \
  tests/unit/actor/test_role_action_auth.py \
  tests/integration/env_tool/test_context_binding.py \
  tests/process/cli/test_env_native_mcp_projection.py \
  tests/unit/env_tool/test_schema_contract.py \
  tests/unit/env_tool/test_semantic_contract.py
```

Expected: Demand actions are discoverable and current generic schema/semantic contracts remain green.

- [x] **Step 6: Commit Task 4**

```bash
git add scripts/env/tools/demand_sys scripts/env/tool_runtime/context.py scripts/env/tool_runtime/role_auth.py tests/integration/env_tool/test_response_demand.py tests/unit/actor/test_role_action_auth.py tests/integration/env_tool/test_context_binding.py tests/process/cli/test_env_native_mcp_projection.py
git commit -m "feat(demand-sys): expose actor demand actions"
```

## Task 5: External-safe read projection and public CLI

**Files:**

- Create: `scripts/env/domain/demand_read.py`
- Modify: `tools/launcher/cli.py`
- Modify: `README.md`
- Create: `tests/process/launcher/test_demand_commands.py`
- Modify: `tests/process/launcher/test_public_cli.py`

- [x] **Step 1: Write CLI RED cases**

Prove:

```text
demand list --actor returns that actor's external-safe projections newest first
demand get <id> --actor returns one actor-scoped projection or NOT_FOUND
projection exposes intake_key, description, revision, checked_revision, parent_id, depends_on, terminal, actor, updated_at
CLI exposes no create/update/absorb/complete mutation
help publishes demand list/get only
malformed actor and demand ids fail before state mutation
```

- [x] **Step 2: Run RED**

```bash
./buddyswitch-test focused \
  tests/process/launcher/test_demand_commands.py \
  tests/process/launcher/test_public_cli.py
```

Expected: `demand` is an unknown top-level command.

- [x] **Step 3: Implement the read projection**

The projection shape is exact:

```python
{
    "demand_id": record["id"],
    "intake_key": record["intake_key"],
    "description": record["description"],
    "actor": dict(record["actor_target"]),
    "revision": record["revision"],
    "checked_revision": record["checked_revision"],
    "parent_id": record["parent_id"],
    "depends_on": list(record["depends_on"]),
    "terminal": deepcopy(record["terminal"]),
    "created_at": record["created_at"],
    "updated_at": record["updated_at"],
}
```

Do not expose a CLI mutation or read raw files in `cli.py`.

- [x] **Step 4: Implement CLI routing**

Add:

```text
buddyswitch-codex demand list --actor <actor-id>
buddyswitch-codex demand get <demand-id> --actor <actor-id>
```

`_dispatch_demand` derives the exact `{actor_id, role_id}` target from the required actor id and calls only `demand_read.list_external_demands` and `demand_read.get_external_demand`, following the current Task read adapter pattern without adding aggregate-wide discovery.

- [x] **Step 5: Run GREEN**

```bash
./buddyswitch-test focused \
  tests/process/launcher/test_demand_commands.py \
  tests/process/launcher/test_public_cli.py \
  tests/unit/architecture/test_repo_contracts.py
```

Expected: all selected tests pass; CLI remains a thin adapter.

- [x] **Step 6: Commit Task 5**

```bash
git add scripts/env/domain/demand_read.py tools/launcher/cli.py README.md tests/process/launcher/test_demand_commands.py tests/process/launcher/test_public_cli.py
git commit -m "feat(demand-sys): add public demand read projection"
```

## Task 6: Architecture law and current documentation

**Files:**

- Create: `tests/unit/architecture/test_demand_sys_boundaries.py`
- Create: `docs/arch/demand-sys-architecture.md`

- [x] **Step 1: Write architecture RED assertions**

The test parses imports and asserts:

```text
env.domain.demand_sys -> env.repos.demands allowed
env.repos.demands -> env.repos.runtime_files allowed
env.tools.demand_sys -> env.domain through ToolContext allowed
demand_sys files -> task_sys forbidden
demand_sys files -> tools.launcher / daemon modules forbidden
generic daemon modules -> demand_sys forbidden
tools/launcher/instance_daemon.py -> Demand product adapter absent in Phase 1
IM and Track handler source -> demand_sys absent in Phase 1
only env.domain.demand_sys calls demands.transact_actor_state
no demand/demand_v2 tool package or fallback read path exists
```

- [x] **Step 2: Run the architecture test and fix only real findings**

```bash
./buddyswitch-test focused tests/unit/architecture/test_demand_sys_boundaries.py
```

Expected: pass. A failure means the implementation boundary is wrong; do not weaken the assertion to allow an unnecessary dependency.

- [x] **Step 3: Write current architecture documentation**

`docs/arch/demand-sys-architecture.md` records only the implemented Phase 1 truth: owner, aggregate path, action surface, check semantics, CLI projection, and forbidden dependencies. It must not describe Phase 2-4 as already live and must not copy complete tool payload tables owned by `tool.py`.

- [x] **Step 4: Run documentation and residue checks**

```bash
git diff --check
rg -n "demand_v2|legacy_demand|fallback.*demand|shadow.*demand|dual.*demand" scripts tools tests docs/arch
```

Expected: `git diff --check` exits 0; the residue search returns no live implementation hit.

- [x] **Step 5: Commit Task 6**

```bash
git add tests/unit/architecture/test_demand_sys_boundaries.py docs/arch/demand-sys-architecture.md
git commit -m "docs(demand-sys): lock standalone architecture"
```

## Task 7: Focused IMPACT verification

**Files:** no production changes expected; update only a failing direct contract when the failure proves a real omitted impact.

- [x] **Step 1: Record source identity**

```bash
git status --short
git rev-parse HEAD
git diff --binary | shasum -a 256
git ls-files --others --exclude-standard
```

Record the unrelated `.superpowers/` entries separately and do not stage them.

- [x] **Step 2: Run one compatible owner/contract batch**

```bash
./buddyswitch-test focused \
  tests/unit/demand_sys/test_capture_and_check.py \
  tests/unit/demand_sys/test_organization.py \
  tests/integration/demand_sys/test_repository_atomicity.py \
  tests/integration/env_tool/test_response_demand.py \
  tests/process/launcher/test_demand_commands.py \
  tests/unit/architecture/test_demand_sys_boundaries.py \
  tests/unit/architecture/test_repo_contracts.py \
  tests/unit/actor/test_role_action_auth.py \
  tests/integration/env_tool/test_context_binding.py \
  tests/process/cli/test_env_native_mcp_projection.py \
  tests/unit/env_tool/test_schema_contract.py \
  tests/unit/env_tool/test_semantic_contract.py \
  tests/process/launcher/test_public_cli.py
```

Expected: all targets pass and the runner reports no cleanup residual.

- [x] **Step 3: Run the public-instance regression separately**

```bash
./buddyswitch-test focused tests/system/instance_lifecycle/test_main_flow.py
```

Expected: public start/input/status/stop/resume/delete remains green with clean service cleanup.

- [x] **Step 4: Inspect Task and daemon non-impact**

```bash
BASE="$(git merge-base 3c0abe1 HEAD)"
git diff --name-only "$BASE" HEAD -- tools/launcher/instance_daemon.py tools/launcher/task_sys_ingress.py tools/launcher/im_wake_handler.py tools/launcher/track_comment_added_handler.py scripts/env/domain/task_sys.py scripts/env/tools/task_sys
```

Expected: no output. If a listed file changed, Phase 1 scope has drifted and must be corrected before acceptance.

- [x] **Step 5: Record IMPACT evidence**

Record exact commands, run ids, source identity, Python/runtime environment, pass counts, cleanup state, and residual risk using `.agents/skills/buddyswitch-testing/references/evidence.md`.

## Task 8: Fresh real actor MILESTONE acceptance

**Files:** no source changes during the accepted run.

This is a real installed-Codex acceptance. Do not put fake Codex earlier on `PATH`, do not reuse an existing actor, and do not treat this nondeterministic model run as a replacement for Task 7.

- [x] **Step 1: Create an isolated real actor using the public CLI**

```bash
source tools/launcher/env.sh
buddyswitch_env_init
RUN_ROOT="$(mktemp -d /private/tmp/bs-demand-real-XXXXXX)"
export BUDDYSWITCH_SHARED_ROOT="$RUN_ROOT/.codex-buddyswitch"
ACTOR_ID=""
cleanup_probe() {
  if [[ -n "$ACTOR_ID" ]]; then
    ./buddyswitch-codex instance stop "$ACTOR_ID"
    ./buddyswitch-codex instance delete "$ACTOR_ID" --yes
  fi
  ./buddyswitch-codex env reset --yes
}
trap cleanup_probe EXIT INT TERM
START_JSON="$(./buddyswitch-codex instance start --role pm)"
ACTOR_ID="$(printf '%s' "$START_JSON" | "$BUDDYSWITCH_PYTHON" -c 'import json,sys; print(json.load(sys.stdin)["data"]["actor_id"])')"
./buddyswitch-codex instance status "$ACTOR_ID"
```

Expected: a new `act-pm-*` actor is active; app server, runtime broker, and daemon are healthy.

- [x] **Step 2: Drive the exact Demand scenario through one actor turn**

```bash
PROBE_ID="real-$(date +%s)"
./buddyswitch-codex instance input "$ACTOR_ID" --text "Demand Sys acceptance probe $PROBE_ID. Do not call task_sys. Explicitly use demand_sys actions only: create C with intake_key actor-self:$PROBE_ID-c, description 'Support user data CSV export.', detail 'Users can export their data as CSV.', and source_refs [{type:'actor.self_requested',ref:{key:'$PROBE_ID-c'}}]; create D with intake_key actor-self:$PROBE_ID-d, description 'CSV export must include the user timezone.', detail 'Add the user timezone to every exported row.', and source_refs [{type:'actor.self_requested',ref:{key:'$PROBE_ID-d'}}]; call demand_sys.check; use get_many for C and D; absorb D into C with both returned revisions and merged description 'Support CSV export with the user timezone.', merged detail 'Users can export their data as CSV and every exported row includes the user timezone.', and both source refs; call complete_check with the returned final revisions for C and D; finally call check and finish only when pending_count is zero."
```

Expected: `instance.input` returns an accepted turn. The prompt is test control; only explicit `demand_sys.create` calls produce Demands.

- [x] **Step 3: Poll the public Demand projection, not raw state**

```bash
"$BUDDYSWITCH_PYTHON" - "$ACTOR_ID" "$PROBE_ID" <<'PY'
import json
import subprocess
import sys
import time

actor_id, probe_id = sys.argv[1:]
deadline = time.monotonic() + 180
while time.monotonic() < deadline:
    completed = subprocess.run(
        ["./buddyswitch-codex", "demand", "list", "--actor", actor_id],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode == 0:
        payload = json.loads(completed.stdout)
        rows = payload["data"]["demands"]
        selected = {row["intake_key"]: row for row in rows if probe_id in row["intake_key"]}
        c = selected.get(f"actor-self:{probe_id}-c")
        d = selected.get(f"actor-self:{probe_id}-d")
        if (
            c
            and d
            and c["terminal"] is None
            and c["checked_revision"] == c["revision"]
            and d["terminal"]["type"] == "absorbed"
            and d["terminal"]["ref"] == c["demand_id"]
            and d["checked_revision"] == d["revision"]
        ):
            print(json.dumps({"c": c, "d": d}, ensure_ascii=False, indent=2))
            raise SystemExit(0)
    time.sleep(2)
raise SystemExit("Demand acceptance state was not observed within 180 seconds")
PY
```

Expected: one live C, one terminal D→C, and both records fully acknowledged.

- [x] **Step 4: Prove Task Sys remained untouched**

```bash
./buddyswitch-codex task list --actor "$ACTOR_ID"
```

Expected: `data.tasks` is an empty list.

- [x] **Step 5: Stop, delete, reset, and verify cleanup**

```bash
./buddyswitch-codex instance stop "$ACTOR_ID"
./buddyswitch-codex instance delete "$ACTOR_ID" --yes
./buddyswitch-codex env reset --yes
test ! -e "$BUDDYSWITCH_SHARED_ROOT"
rmdir "$RUN_ROOT"
ACTOR_ID=""
trap - EXIT INT TERM
```

Expected: actor root, service pid/socket markers, isolated shared root, and `RUN_ROOT` are absent. No accepted actor process remains live.

- [x] **Step 6: Record MILESTONE evidence**

Record installed Codex version, actor id, thread id, exact prompt, observed C/D projections, empty Task projection, process/socket cleanup, source identity, and any model retry. If the actor selects an incorrect action, preserve the failure as evidence, diagnose tool description/schema clarity, fix the owner contract, rerun focused affected proof, then create a new actor for the next milestone attempt.

## Task 9: Final replacement and scope audit

- [x] **Step 1: Scan the final diff by owner**

```bash
BASE="$(git merge-base 3c0abe1 HEAD)"
git diff --stat "$BASE" HEAD
git diff --check
git status --short
```

Expected: only Phase 1 files and the unrelated untouched `.superpowers/` fact are present.

- [x] **Step 2: Prove no forbidden live surface**

```bash
rg -n "demand_v2|legacy_demand|fallback.*demand|shadow.*demand|dual.*demand" scripts tools tests docs/arch
rg -n "demand_sys" tools/launcher/instance_daemon.py tools/launcher/task_sys_ingress.py tools/launcher/im_wake_handler.py tools/launcher/track_comment_added_handler.py scripts/env/domain/task_sys.py scripts/env/tools/task_sys
```

Expected: both commands return no hit. Naming the forbidden terms inside the dedicated residue test is allowed only when the assertion proves absence.

- [x] **Step 3: Audit the acceptance sentence**

Confirm every phrase has evidence:

```text
fresh actor                 -> real CLI MILESTONE
one demand_sys action owner -> registry/tool/domain architecture proof
D supplements C atomically  -> domain + repository + actor observation
CLI observability           -> process test + real projection
Task untouched              -> empty Task projection + no changed Task files
daemon/inbound unchanged    -> architecture test + no changed launcher files
no residue/dual path        -> path/import/token audit
clean resources             -> runner and real actor cleanup evidence
```

- [x] **Step 4: Commit evidence/document updates only if created by execution**

If acceptance adds evidence to the architecture document, commit only that changed document:

```bash
if ! git diff --quiet -- docs/arch/demand-sys-architecture.md; then
  git add docs/arch/demand-sys-architecture.md
  git commit -m "docs(demand-sys): record phase one acceptance"
fi
```

Never suppress test, build, lint, runtime, commit, or cleanup failures.

## 4. Verification breadth decision

Phase 1 completion targets `IMPACT` plus one real actor `MILESTONE`.

- RED/GREEN is exact per task.
- The compatible focused batch proves the owner and direct contracts once.
- The system instance test runs separately because it owns live service resources.
- The real actor run is required supplementary evidence.
- `./buddyswitch-test full` is intentionally omitted unless the user explicitly requests repository-wide acceptance or the branch becomes a frozen release/merge candidate.

## 5. Stop conditions

Stop implementation and report the exact evidence instead of adding a workaround when:

- Demand atomicity would require a second canonical store or dual write;
- a proposed action needs Task state to decide Demand semantics;
- generic daemon code would need a Demand token or branch;
- real actor use requires raw state writes or a second test/CLI entry;
- a stale revision can partially mutate the aggregate;
- a failure can only be hidden by fallback, compatibility, retry-until-green, or weakened assertions.

The correct response to any of these is to repair the owner boundary or reduce Phase 1 scope, never to layer around it.

## 6. Execution evidence

### Task 7 IMPACT — 2026-07-19

```text
Verification Evidence
- state: IMPACT
- source: /Users/chen/Dev/buddyswitch/.worktrees/fea-daemon; HEAD a985425e19e6cea043d186e3fccf7ffdd64857d3; tracked patch sha256 e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855; unrelated non-ignored untracked files limited to .superpowers/brainstorm/22131-1784393393/{content/demand-organization-models.html,content/waiting-after-organization.html,state/server-stopped,state/server.pid}
- command: ./buddyswitch-test focused tests/unit/demand_sys/test_capture_and_check.py tests/unit/demand_sys/test_organization.py tests/integration/demand_sys/test_repository_atomicity.py tests/integration/env_tool/test_response_demand.py tests/process/launcher/test_demand_commands.py tests/unit/architecture/test_demand_sys_boundaries.py tests/unit/architecture/test_repo_contracts.py tests/unit/actor/test_role_action_auth.py tests/integration/env_tool/test_context_binding.py tests/process/cli/test_env_native_mcp_projection.py tests/unit/env_tool/test_schema_contract.py tests/unit/env_tool/test_semantic_contract.py tests/process/launcher/test_public_cli.py
- environment: BuddySwitch public test runner; Python 3.13.5
- result: exit 0; run a8a93ca6fcbc477289e3af69662b5596; 130 passed and 806 subtests passed in 5.52s; run root /private/tmp/bs-test-a8a93ca6-vqu69z9q absent after completion
- proves: Demand capture, organization, atomicity, actor tool, public read CLI, authorization, ToolContext, native MCP, schema/semantic, architecture, and public CLI contracts pass together on the frozen source
- valid-for: executable source at a985425e19e6cea043d186e3fccf7ffdd64857d3
- residual-risk: real installed-Codex actor behavior remains for Task 8 MILESTONE
```

```text
Verification Evidence
- state: IMPACT
- source: same frozen executable source and untracked identity as the preceding IMPACT record
- command: ./buddyswitch-test focused tests/system/instance_lifecycle/test_main_flow.py
- environment: BuddySwitch public test runner; Python 3.13.5
- result: exit 0; run f05deca748674db1a9540e90a5f8336e; 1 passed in 5.80s; run root /private/tmp/bs-test-f05deca7-8e9x2byu absent after completion
- proves: public actor start, input, status, stop, resume, and delete lifecycle remains operational with clean test resources
- valid-for: executable source at a985425e19e6cea043d186e3fccf7ffdd64857d3
- residual-risk: nondeterministic real actor Demand action selection is not covered by the system fixture
```

The baseline non-impact audit used `git merge-base 3c0abe1 HEAD` and returned no
changed path among `instance_daemon.py`, `task_sys_ingress.py`, the IM and Track
handlers, the Task Sys domain, or the Task Sys tool package.

### Task 8 MILESTONE — 2026-07-19

```text
Verification Evidence
- state: MILESTONE
- source: /Users/chen/Dev/buddyswitch/.worktrees/fea-daemon; HEAD 1b16d07cd5b6d2d2b77b0eb169550358319496e4; tracked patch sha256 e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855; unrelated .superpowers/ untracked identity unchanged from Task 7
- command: public CLI instance start/status/input, public demand list polling, public task list, instance stop/delete, env reset, followed by direct absence probes for owned pids, sockets, actor process, and isolated root
- environment: installed /Users/chen/.npm-global/bin/codex; codex-cli 0.144.4; BuddySwitch Python /Users/chen/miniconda3/bin/python; fresh role pm actor act-pm-a37f25798f37; thread 019f7a9c-16a5-77f2-9792-497be7fcbece; turn 019f7a9c-2352-7c60-a74d-570e4153c1f9
- exact prompt: Demand Sys acceptance probe real-1784468480. Do not call task_sys. Explicitly use demand_sys actions only: create C with intake_key actor-self:real-1784468480-c, description 'Support user data CSV export.', detail 'Users can export their data as CSV.', and source_refs [{type:'actor.self_requested',ref:{key:'real-1784468480-c'}}]; create D with intake_key actor-self:real-1784468480-d, description 'CSV export must include the user timezone.', detail 'Add the user timezone to every exported row.', and source_refs [{type:'actor.self_requested',ref:{key:'real-1784468480-d'}}]; call demand_sys.check; use get_many for C and D; absorb D into C with both returned revisions and merged description 'Support CSV export with the user timezone.', merged detail 'Users can export their data as CSV and every exported row includes the user timezone.', and both source refs; call complete_check with the returned final revisions for C and D; finally call check and finish only when pending_count is zero.
- result: exit 0; one accepted actor turn; public projection observed on poll 17: C demand-554af2b680d7 live at revision=checked_revision=2 with merged description, D demand-887ff7a64d81 terminal absorbed ref demand-554af2b680d7 at revision=checked_revision=2; public task.list returned []; stop/delete/reset succeeded
- cleanup: app-server pid 21606, daemon pid 21672, and runtime-broker pid 21576 not live; app-server and broker sockets absent; no process matched actor id; /private/tmp/bs-demand-real-8r4j4l and its .codex-buddyswitch root absent
- proves: one fresh installed-Codex actor can discover and use the current native demand_sys action contract to complete the exact C/D consolidation and acknowledgement loop while Task Sys stays untouched
- valid-for: executable source at 1b16d07cd5b6d2d2b77b0eb169550358319496e4
- residual-risk: this is one nondeterministic model sample; proactive wake and Demand/Task integration are intentionally outside Phase 1
```

Actor/model retries were zero. One preflight orchestration command was rejected
before runtime creation because the host tool defaulted to zsh while `env.sh`
requires Bash; the accepted run used an explicit Bash shell and created a fresh
isolated actor. No product source changed between source identity capture and
the accepted run.

### Final candidate corrective review — 2026-07-19

Independent code review found no critical issue and two important contract gaps:
an idempotent `create` replay lost the existing Demand identity, and terminal
actions other than `absorb_into` could leave a live child attached to a terminal
parent. Both were repaired at the Demand domain owner without compatibility
paths or duplicated rules.

```text
Verification Evidence
- state: RED -> GREEN
- source: corrective commit a4bd56047bb68aea44c80af123ba0612660370d5
- RED: run ddb6c1a1b923474f81aa56d12dc61669; 7 expected failures proving both missing contracts
- GREEN: run 20c03572738842278348a78d8e2e37fa; 30 passed and 10 subtests passed
- result: create and exact replay return the same demand_id/revision; every first terminalization rejects live children atomically through one domain invariant
- residual-risk: none specific to the two reviewed contracts
```

### Final candidate IMPACT — 2026-07-19

```text
Verification Evidence
- state: IMPACT
- source: /Users/chen/Dev/buddyswitch/.worktrees/fea-daemon; executable HEAD a4bd56047bb68aea44c80af123ba0612660370d5; tracked patch sha256 e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
- command: the Task 7 compatible focused batch across Demand domain/repository/tool/read CLI, authorization, ToolContext, native MCP, architecture, schema/semantic, and public CLI contracts
- environment: BuddySwitch public test runner; Python 3.13.5
- result: exit 0; run 57f5fa1ad5e14afd84396bfe7a06ca69; 131 passed and 810 subtests passed in 5.49s; run root /private/tmp/bs-test-57f5fa1a-wcrawl4c absent
- system regression: exit 0; run 5232c7e00a504aadb211e3bfa48830c5; 1 passed in 5.66s; run root /private/tmp/bs-test-5232c7e0-xtg6mhhn absent
- proves: the corrected executable candidate passes the complete Phase 1 affected contract set and preserves the public instance lifecycle
- residual-risk: repository-wide full was intentionally omitted by the plan; the affected owner and consumer paths are covered directly
```

### Final candidate MILESTONE — 2026-07-19

```text
Verification Evidence
- state: MILESTONE
- source: /Users/chen/Dev/buddyswitch/.worktrees/fea-daemon; executable HEAD a4bd56047bb68aea44c80af123ba0612660370d5; tracked patch sha256 e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
- command: public CLI instance start/status/input, public demand list polling, public task list, instance stop/delete, env reset, then exact pid/socket/process/root absence probes
- environment: installed /Users/chen/.npm-global/bin/codex; codex-cli 0.144.4; BuddySwitch Python /Users/chen/miniconda3/bin/python; fresh role pm actor act-pm-feda35ac4293; thread 019f7aaa-8a8e-76b1-9ea3-8328841081f7; turn 019f7aaa-9bf9-7722-88ed-7e3cede37611
- probe: real-final-1784469429; the exact Task 8 C/D prompt was used; actor/model retries were zero
- result: exit 0; public projection observed on poll 16: C demand-cdc2f3911917 live at revision=checked_revision=2 with merged description, D demand-bcf359aca0fd terminal absorbed ref demand-cdc2f3911917 at revision=checked_revision=2; public task.list returned []
- cleanup: pids 27555, 27585, 27654, and 27658 absent; app-server, runtime-broker, and central-daemon sockets absent; no process contains actor id act-pm-feda35ac4293; /private/tmp/bs-demand-real-final-ZqHuPr absent
- proves: the corrected current executable lets one fresh real actor complete the exact standalone Demand consolidation/check loop while Task Sys stays untouched and all owned runtime resources are released
- residual-risk: this is one nondeterministic model sample; proactive wake, inbound adapters, and Demand/Task coordination remain intentionally outside Phase 1
```

### Task 9 final scope and replacement audit — 2026-07-19

The final audit used base `3c0abe17e3b3a0bb49cad69a3270e5f42529e202`.
All 27 changed files belong to Phase 1 documentation, the Demand owner and its
projections, or direct tests/registrations. `git diff --check` passed. The
forbidden integration scan found no `demand_sys` reference in daemon, inbound,
or Task Sys owners. The residue token scan found only negative assertions in
`test_demand_sys_boundaries.py`; no retired live path exists. The four
pre-existing `.superpowers/` files remain untracked and untouched.
