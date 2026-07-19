# Demand Sys Phase 1 Standalone Forward-Rebuild Design

**Date:** 2026-07-19
**Status:** design approved; implementation not started
**Implementation scope:** Phase 1 only
**Business-flow visual:** `docs/spec/2026-07-19-demand-sys-proactive-prototype-flow.html`

## 1. Acceptance sentence

A fresh BuddySwitch actor can use one independent `demand_sys` action surface to create, inspect, organize, acknowledge, and terminalize actor-owned Demands; the D-supplements-C flow is atomically observable through the public BuddySwitch CLI, while Task Sys, inbound handlers, and daemon registration remain unchanged and no Demand code imports or calls them.

## 2. Current repository facts

The design is grounded in `fea-daemon` at `3c0abe1`.

- `scripts/env/domain/task_sys.py` is the current Task lifecycle owner. It persists Task records below `buddyswitch/objects/task-sys/tasks` and advances one canonical status.
- `tools/launcher/task_sys_ingress.py` still converts controlled IM and Track inbound events directly into Tasks.
- `tools/launcher/im_wake_handler.py:66` and `tools/launcher/track_comment_added_handler.py:122` call that Task ingress and immediately execute Task runtime instructions.
- Direct actor input was deliberately removed from Task ingress by `3c0abe1`; `tests/unit/task_sys/test_direct_input_retirement.py` protects that boundary.
- `tools/launcher/instance_daemon.py` is the sole composition root for generic daemon infrastructure and product adapters.
- `docs/arch/daemon-service-architecture.md` already establishes the correct daemon rule: the daemon hosts product modules but does not know product semantics.
- `scripts/env/tool_runtime/registry.py` discovers actor tools from `scripts/env/tools/*`; a new Demand tool does not require a registry switch or second registration system.
- `scripts/env/tool_runtime/role_auth.py` is the single role-action permission owner.
- `scripts/env/tool_runtime/native_mcp.py` projects registered env actions into Codex-native MCP tools.
- `tools/launcher/cli.py` already provides the public `instance start/input/status/stop/delete` actor lifecycle and read-only Task/Track projections.
- `tests/system/instance_lifecycle/test_main_flow.py` exercises the real public launcher path with a deterministic fake Codex runtime. A separate real-Codex actor acceptance can therefore supplement, rather than replace, repeatable tests.

Baseline evidence gathered before planning:

```text
./buddyswitch-test focused \
  tests/unit/architecture/test_repo_contracts.py \
  tests/unit/actor/test_role_action_auth.py \
  tests/process/cli/test_env_native_mcp_projection.py

result: 20 passed, 94 subtests passed
run: 3f14facb61374e06aebe5c44bb3384bc
cleanup: runner-owned temporary root removed

./buddyswitch-test focused tests/system/instance_lifecycle/test_main_flow.py

result: 1 passed
run: 0ad1bb84563d4a26b995a475e0f7b51c
cleanup: runner-owned actor processes and temporary root removed
```

One unrelated worktree fact remains outside this change: `.superpowers/` is non-ignored and untracked. It must not be staged, edited, or used as implementation evidence.

## 3. Phase boundary

### In Phase 1

- canonical Demand state and lifecycle;
- constrained-hybrid organization: parent tree, explicit dependencies, terminal lineage;
- two-pass-check support, not matching intelligence;
- one actor-facing `demand_sys` tool package;
- one external-safe read projection and read-only `buddyswitch-codex demand` CLI;
- focused owner, contract, architecture, process, and public-instance regression proof;
- one fresh real actor acceptance using the public CLI and installed real Codex runtime.

### Not in Phase 1

- no IM or Track inbound cutover;
- no daemon handler, subscription, schedule, trigger, or application command;
- no `request_check` actor wake;
- no Demand-to-Task reference, import, call, callback, subscription, or shared transaction;
- no Task creation or Task completion reconciliation;
- no embedding, vector search, matching service, rule engine, event bus, workflow engine, or background worker;
- no Web UI, migration reader, fallback read, dual write, compatibility alias, shadow state, or alternate schema.

Direct CLI input is only the control surface used to start a real actor turn. It never becomes a Demand automatically. A Demand exists only after the actor explicitly calls `demand_sys.create`.

## 4. Phase architecture

```text
                          Phase 1 production path

  real actor / native MCP                             local admin
            |                                             |
            v                                             v
  scripts/env/tools/demand_sys/                 buddyswitch-codex demand
      tool.py + _impl.py                           list / get
            |                                             |
            +-------------------+-------------------------+
                                v
                  scripts/env/domain/demand_sys.py
                   one semantic and transition owner
                                |
                                v
                    scripts/env/repos/demands.py
                  lock + load + one atomic replace
                                |
                                v
  $BUDDYSWITCH_STATE_ROOT/buddyswitch/objects/demand-sys/actors/<actor>-<role>.json

  Explicitly absent:
  Demand Sys --X--> Task Sys
  Demand Sys --X--> generic daemon
  inbound    --X--> Demand Sys       (until Phase 4)
```

Dependency direction is fixed:

```text
consumer -> adapter/projection -> Demand domain -> Demand repository -> runtime_files
```

The repository knows persistence only. The domain owns every Demand invariant. Tool and CLI adapters project the domain contract and never duplicate its rules.

## 5. Canonical persistence

### 5.1 One actor aggregate

Phase 1 stores all Demands for one `{actor_id, role_id}` in one aggregate document:

```json
{
  "schema_version": 1,
  "actor_target": {
    "actor_id": "act-pm-example",
    "role_id": "pm"
  },
  "demands": {
    "demand-aaaaaaaaaaaa": {
      "id": "demand-aaaaaaaaaaaa",
      "actor_target": {
        "actor_id": "act-pm-example",
        "role_id": "pm"
      },
      "intake_key": "actor-self:csv-export-base",
      "description": "Support user data CSV export.",
      "detail": "Users can export their data as CSV.",
      "source_refs": [
        {
          "type": "actor.self_requested",
          "ref": {"key": "csv-export-base"}
        }
      ],
      "parent_id": null,
      "depends_on": [],
      "revision": 5,
      "checked_revision": 5,
      "terminal": null,
      "created_at": "2026-07-19T00:00:00+08:00",
      "updated_at": "2026-07-19T00:05:00+08:00"
    }
  }
}
```

The aggregate is deliberate, not a generic database abstraction. It makes multi-Demand actions such as `absorb_into` and `split` one local atomic replacement. Current actor-scale data does not justify a database or transaction coordinator.

### 5.2 Lock and write owner

`scripts/env/repos/demands.py` owns:

- actor-target validation and canonical file/lock paths;
- an exclusive `fcntl.flock` around read-modify-write transactions;
- strict aggregate loading with `schema_version == 1`;
- a fresh empty aggregate when the file is absent;
- one `runtime_files.write_json_object` atomic replacement after the domain mutation succeeds;
- no write when validation or domain mutation raises.

The lock lives below `buddyswitch/local/locks/demand-sys`; it is runtime coordination state, not a Demand object or alternate truth.

There is no one-file-per-Demand dual state, journal, cache, or fallback reader.

## 6. Demand semantics

### 6.1 Live and terminal

A Demand is live when `terminal` is `null`. It is terminal when `terminal.type` is one of:

```text
completed | canceled | absorbed | duplicate | superseded
```

Terminal metadata has this closed shape:

```json
{
  "type": "absorbed",
  "at": "2026-07-19T00:05:00+08:00",
  "ref": "demand-target-id",
  "summary": "Merged the timezone requirement into the CSV export demand.",
  "evidence_refs": []
}
```

`ref` is required for `absorbed`, `duplicate`, and `superseded`; it is absent for `completed` and `canceled`. `evidence_refs` is meaningful for completion and may be empty. No top-level status duplicates `terminal`.

### 6.2 Revision and check state

- A semantic mutation increments `revision` exactly once for every changed Demand.
- `description` and `detail` always change in the same revision.
- A new Demand starts at `revision=1`, `checked_revision=0`.
- `check` returns every record where `revision > checked_revision`, including terminal records that still require acknowledgement.
- `complete_check` accepts observed `{demand_id, revision}` pairs and advances only `checked_revision`.
- `complete_check` never increments `revision` and therefore cannot request another check.
- If the current revision is newer than the observed revision, the older revision is acknowledged but the current revision remains pending.

### 6.3 Idempotent intake

`intake_key` is required and unique within one actor aggregate.

- Repeating `create` with the same intake key and the same canonical input returns the existing Demand with `state_changed=false`.
- Reusing an intake key with different canonical input is a conflict and writes nothing.
- The key is source-owned. Future IM/Track adapters will derive it from their stable event identity; actor self-requested Demands provide an explicit key.

There is no content-similarity deduplication in storage.

### 6.4 Organization

`parent_id` means “this is a distinct component Demand of that larger Demand.” It does not mean “more text for the same Demand.”

`depends_on[]` means execution or satisfaction of this Demand relies on other Demands. Parent and dependency cycles are rejected.

`absorb_into(source, target)` means source and target describe one canonical Demand. In one transaction it:

1. verifies both expected revisions;
2. requires both Demands to be live and actor-owned;
3. rejects a source with live children so no live subtree becomes implicitly orphaned;
4. atomically replaces the target description/detail/source refs with actor-supplied merged canonical content;
5. increments the target revision;
6. terminalizes the source as `absorbed` with `ref=target_id`;
7. increments the source revision.

`mark_duplicate(source, target)` and `supersede(old, replacement)` terminalize only the source/old Demand with explicit lineage. They do not copy content or mutate the target/replacement.

`split(parent, children)` keeps the original Demand live as the explicit parent container, revises its description/detail, and creates two or more child Demands with `parent_id=parent.id` in one transaction. Split is therefore a live structural action, not a terminal lineage type.

No action silently rewires parent or dependency edges. The actor uses explicit relation actions when reorganization is required.

## 7. Public action surface

Phase 1 exposes exactly these actor actions:

```text
create
revise
list
get
get_many
check
complete_check
set_parent
add_dependency
remove_dependency
split
absorb_into
mark_duplicate
supersede
complete
cancel
```

Every write action that targets an existing Demand requires `expected_revision`. Multi-Demand actions require an expected revision for every Demand whose semantic state changes.

Every mutation returns a `DemandCommitReceipt` projection:

```json
{
  "state_changed": true,
  "changes": [
    {"demand_id": "demand-c", "revision": 6, "kind": "revised"},
    {"demand_id": "demand-d", "revision": 2, "kind": "absorbed"}
  ],
  "check_required": true
}
```

The receipt is not a persisted event stream. Durable pending attention is derived from `revision > checked_revision`, so a lost receipt cannot erase unfinished review.

### 7.1 Two-pass actor check

```text
check()
  -> attention_items[]    full changed Demand records
  -> live_index[]         only id + description

actor coarse match over live_index

get_many([attention_id] + candidate_ids)
  -> full candidate records

actor chooses one explicit organization action or no relation

complete_check(observed_revision_rows)
```

Demand Sys supplies information and atomic actions. The actor owns every similarity, relation, priority, and consumption decision.

## 8. Error contract

The domain exposes typed failures that the tool adapter maps to stable tool responses:

| Code | Meaning | State guarantee |
| --- | --- | --- |
| `E_DEMAND_NOT_FOUND` | referenced Demand does not exist for the actor | unchanged |
| `E_DEMAND_REVISION_CONFLICT` | expected revision is stale | unchanged |
| `E_DEMAND_INTAKE_CONFLICT` | intake key exists with different content | unchanged |
| `E_DEMAND_TERMINAL` | action requires a live Demand | unchanged |
| `E_DEMAND_RELATION` | self-edge, cycle, cross-actor edge, or live-child terminalization | unchanged |
| `E_DEMAND_PAYLOAD` | schema or field validation failed | unchanged |

Unexpected persistence or runtime failures remain explicit `E_ENV_TOOL` failures. They are not converted to success and do not trigger fallback reads or writes.

## 9. External observation

`scripts/env/domain/demand_read.py` projects actor target, description, revision/check state, live/terminal state, terminal lineage, parent/dependency ids, and timestamps. It does not own mutations.

The public CLI adds only:

```text
buddyswitch-codex demand list --actor <actor-id>
buddyswitch-codex demand get <demand-id> --actor <actor-id>
```

Actor scope is required for both reads, so the projection never scans or infers ownership across actor aggregates. This read surface is required for black-box acceptance and operator inspection. It does not expose a second write path.

## 10. Forward-only rules

Phase 1 has no predecessor Demand implementation to preserve. Therefore:

- the only live name is `demand_sys`; there is no `demand`, `demand_v2`, or legacy alias tool;
- the only canonical schema is aggregate schema version 1;
- the only mutation path is the Demand domain transaction;
- CLI is read-only and calls the read projection;
- tool code calls the same Demand domain owner;
- no Task field, Task reference, daemon token, inbound branch, adapter stub, feature flag, fallback, or shadow write is introduced;
- current IM/Track-to-Task paths remain exactly current in Phase 1; they are replaced only in the later cutover phase, source by source, with the retired same-source path deleted in that change.

## 11. Verification design

The shortest sufficient evidence stack is:

1. **RED/GREEN owner proof:** canonical model, idempotency, revision conflicts, check/ack, relations, terminalization, and atomic D-to-C absorption.
2. **Repository/process proof:** concurrent writers serialize; failed mutations preserve the previous aggregate; no temporary or lock-owned process residue remains.
3. **Tool contract proof:** native actions, actor scope, success/rejection fields, and no Task side effects.
4. **Architecture proof:** dependency direction and forbidden Task/daemon/inbound imports.
5. **CLI proof:** list/get are read-only and actor filters are exact.
6. **Existing-system proof:** current public instance main flow still passes without Demand daemon/inbound registration.
7. **Real actor milestone:** public CLI creates a fresh real Codex actor; direct input causes no automatic Demand; an explicit prompt makes the actor call Demand actions to absorb D into C and acknowledge both revisions; CLI observation shows one live C, terminal D→C, no pending check, and zero Task records; actor and processes are then stopped and deleted.

The real actor run supplements deterministic tests because model action selection is intentionally not a stable automated assertion. It is nevertheless required before delivery acceptance.

`./buddyswitch-test full` is not planned for ordinary Phase 1 completion. It is reserved for an explicit repository-wide acceptance or frozen release candidate.

## 12. Later phases, not implementation scope

```text
Phase 2  Demand-owned attention policy -> generic Actor Input capability -> actor check
Phase 3  actor independently coordinates Demand actions and single-active Task actions
Phase 4  each inbound source cuts directly to Demand and deletes its old Task ingress path
```

No Phase 2-4 stub is created during Phase 1.
