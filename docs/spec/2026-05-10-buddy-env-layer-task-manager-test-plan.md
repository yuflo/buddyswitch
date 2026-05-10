# Buddy Env Layer Task Manager Test Plan

**Goal:** Verify from product requirements that BuddySwitch buddies can manage their own tasks through a shared `task-manager` skill and runtime-owned env tool path, while cross-buddy task access is rejected by code and current task binding remains consistent.

**Testing principle:** Tests must start from observable product requirements: active buddy identity, task ownership, task lifecycle operations, binding behavior, structured feedback, and runtime materialization. Do not write tests that merely match a private helper branch, an exact incidental string, or a fixture chosen only to make the current code pass.

---

## Functional Requirements

FR1. `task-manager` is a normal shared skill available to every buddy through the existing runtime skill materialization path.

FR2. A buddy can create a task for the active buddy without authoring `buddy` in the payload.

FR3. A buddy can list only tasks owned by the active buddy.

FR4. A buddy can read details only for an active-buddy-owned task.

FR5. A buddy can update only minimal task fields: `title`, `summary`, and `status`.

FR6. A buddy can archive its own task as a clear `task.archive` action without deleting the task.

FR7. A buddy can read the current launcher instance task binding and task summary.

FR8. A buddy can set the current launcher instance task only to an active-buddy-owned task.

FR9. Setting current task synchronizes instance `current_task_id` and `current_track_id` from the selected task.

FR10. Cross-buddy task reads and mutations are rejected by service/tool code, not by prompt text.

FR11. Tool success and rejection responses are machine-readable and include enough next-action feedback for Codex CLI to proceed or stop.

FR12. Active buddy and instance identity come from launcher/runtime context, not LLM-authored payload fields.

FR13. `prepare.runtime_context` exposes compact task tool capability, command hints, and payload guidance.

FR14. `AGENTS.md` and `task-manager/SKILL.md` stay concise and do not duplicate permission enforcement recipes.

FR15. The old manual/debug task script does not define the product task env behavior.

FR16. Existing prepare/persist behavior, project write boundaries, browser evidence feedback, and switch-era text handling do not regress.

## Coverage Matrix

| Requirement | Test Group | Observable Proof |
|---|---|---|
| FR1, FR14 | TG-01 Shared Skill Materialization | Every buddy installs `task-manager` as a normal skill package |
| FR2, FR3 | TG-02 Own-Buddy Create And List | Active buddy creates a task and list excludes foreign tasks |
| FR4, FR5, FR6 | TG-03 Own-Buddy Get Update Archive | Owned task can be read, updated, and archived without deletion |
| FR7, FR8, FR9 | TG-04 Current Binding | Current task binding reads and writes instance JSON consistently |
| FR10, FR12 | TG-05 Cross-Buddy Rejection | Foreign task access fails with ownership feedback and no mutation |
| FR11, FR13 | TG-06 Structured Feedback And Runtime Context | Tool responses and prepare context expose actionable machine-readable surfaces |
| FR15 | TG-07 Manual Debug Path Containment | Product tests and docs use the env tool path, not `env_tasks.py` |
| FR16 | TG-08 Existing Runtime Regression | Prepare, persist, project boundaries, evidence feedback, and text handling stay stable |
| FR1, FR11, FR13 | TG-09 Launcher Product Instance Probe | Materialized instances contain the shared skill and executable env client |

## TG-01 Shared Skill Materialization

**Purpose:** Prove `task-manager` is a normal skill, not a special prompt or broker-only command.

**Test cases:**

1. Manifest contains one skill row with `id = "task-manager"` and path `buddyswitch/skills/shared/task-manager`.
2. Every buddy row lists `task-manager` exactly once.
3. Runtime skill installation for `pm`, `dev`, and one read-only non-PM buddy copies `.agents/skills/task-manager/SKILL.md`.
4. Installing runtime skills for one buddy does not install unrelated buddy-specific skills.
5. `task-manager/SKILL.md` contains command guidance for the env client and points to runtime feedback/context.

**Assertions:**

- Skill installation uses `scripts/runtime_skills.py` and manifest membership.
- The shared skill package is copied like any other skill package.
- The skill does not include long cross-buddy permission matrices or raw state write instructions.

**Anti-cheat guard:**

- Do not satisfy this group by checking only a manifest string. At least one test must materialize a runtime workspace and inspect `.agents/skills/task-manager`.

## TG-02 Own-Buddy Create And List

**Purpose:** Prove active buddies can create and discover their own tasks through the env tool path.

**Setup:**

- Use a temporary launcher-style runtime workspace.
- Create an active Dev instance record with `current_task_id = null`.
- Seed a PM-owned task and a Dev-owned task in the runtime task object directory.
- Route operations through broker `env.task` or the public env client CLI.

**Test cases:**

1. Dev calls `task.create` with title and summary.
2. Dev `task.create` payload tries to include `"buddy": "pm"`.
3. Dev calls `task.list` after creating the task.
4. PM calls `task.list` in a PM instance with the same shared state.

**Assertions:**

- Created task has `buddy == "dev"` even if payload attempted another buddy.
- Created task has valid `id`, `title`, `status`, `summary`, timestamps, empty run ids, and no artifact slots beyond store defaults.
- Dev list includes Dev tasks and excludes PM tasks.
- PM list includes PM tasks and excludes Dev tasks.
- No test depends on a fixed generated task id except optional explicit test ids used as setup data.

**Anti-cheat guard:**

- Do not assert only the service return value. Read the stored task object or call `task.get` afterward to prove persisted state matches the response.

## TG-03 Own-Buddy Get Update Archive

**Purpose:** Prove normal task lifecycle operations work for active-buddy-owned tasks.

**Test cases:**

1. Dev gets a Dev-owned task by id.
2. Dev updates title only.
3. Dev updates summary only.
4. Dev updates status to `blocked`.
5. Dev attempts to update unsupported fields such as `buddy`, `track_id`, `artifact_ids`, or `run_ids`.
6. Dev archives a Dev-owned task.
7. Dev gets the archived task.

**Assertions:**

- Get returns task summary fields, not raw internal-only state.
- Title, summary, and status updates persist.
- Unsupported fields reject with `ok=false`, `permission_boundary=request-payload`, and no partial mutation.
- Archive sets `status` to `archived`.
- Archived task still exists and can be read by the owning buddy.

**Anti-cheat guard:**

- Do not make archive pass by deleting the object or hiding it from every list. The test must prove the task remains readable by owner after archive.

## TG-04 Current Binding

**Purpose:** Prove current task binding is instance-owned and consistent with task track binding.

**Setup:**

- Create one active Dev instance.
- Seed one Dev task without a track.
- Seed one Dev task bound to `track-dev-example`.
- Seed the track object with the bound task id.

**Test cases:**

1. `task.get_current` on an instance with no current task returns a structured response with no task and allowed next actions.
2. `task.set_current` to the untracked Dev task writes `current_task_id` and `current_track_id = null`.
3. `task.get_current` returns the untracked Dev task summary.
4. `task.set_current` to the tracked Dev task writes `current_task_id` and `current_track_id = "track-dev-example"`.
5. `task.get_current` returns binding and task summary after the switch.
6. `task.set_current` with a missing task id rejects and leaves the previous binding unchanged.

**Assertions:**

- Instance JSON is the source of current binding truth.
- Binding changes are atomic from the caller's perspective: rejected calls leave the previous binding unchanged.
- `current_track_id` mirrors the selected task's `track_id`.
- The selected task must belong to the active buddy.

**Anti-cheat guard:**

- Do not only inspect response JSON. Re-read the instance record from disk after each set-current call.

## TG-05 Cross-Buddy Rejection

**Purpose:** Prove the active-buddy boundary is enforced by code for every task operation that names a task id.

**Setup:**

- Use shared runtime state containing a PM task and Dev task.
- Use an active Dev instance for foreign access attempts.

**Test cases:**

1. Dev `task.get` PM task.
2. Dev `task.update` PM task.
3. Dev `task.archive` PM task.
4. Dev `task.set_current` PM task.
5. Dev `task.list` when only PM tasks exist.
6. Payload attempts to override `active_buddy` or `buddy` to PM during a Dev request.

**Assertions:**

- Named foreign task operations return `ok=false`.
- Error code is `E_TASK_BUDDY_SCOPE`.
- `permission_boundary` is `task.buddy_scope`.
- Response includes `active_buddy`, attempted `task_id`, and non-empty `allowed_next_actions`.
- Foreign task object is unchanged after each rejected mutation.
- Dev list does not reveal PM task summaries or titles.
- Payload-authored buddy fields are ignored or rejected and never change active buddy identity.

**Anti-cheat guard:**

- Do not make this pass by globally hiding task ids before ownership checks. The rejection should identify the attempted task id and boundary without leaking full foreign task details.

## TG-06 Structured Feedback And Runtime Context

**Purpose:** Prove Codex CLI receives enough structured information to choose the next action without prompt-only rules.

**Test cases:**

1. Successful `task.create` response includes `ok`, `action`, `active_buddy`, `task_id`, `task`, and `allowed_next_actions`.
2. Rejected foreign `task.set_current` response includes `ok=false`, `error`, `permission_boundary`, `active_buddy`, `task_id`, and `allowed_next_actions`.
3. Missing payload response includes `permission_boundary=request-payload`.
4. Broker unavailable env client execution prints structured `ok=false` feedback using `runtime_kernel.client` details.
5. `prepare.runtime_context` contains compact task tool command and operation hints.
6. `prepare.runtime_context` names runtime/tool feedback as the source of permission and next-action decisions.

**Assertions:**

- JSON shapes are stable enough for machine parsing.
- Recoverable feedback uses `allowed_next_actions`.
- Non-recoverable broker feedback uses a stop condition and does not suggest raw state writes.
- Runtime context contains the task tool surface; AGENTS and SKILL text do not need long payload recipes.

**Anti-cheat guard:**

- Do not assert one copied long error string. Validate semantic fields and non-empty next-action arrays.

## TG-07 Manual Debug Path Containment

**Purpose:** Prove old task debug APIs no longer define product behavior.

**Test cases:**

1. Product task-manager tests call broker `env.task`, `scripts/env/client.py`, or task service functions, not `scripts/env_tasks.py`.
2. `scripts/env_tasks.py --help` describes itself as manual/debug if retained.
3. Active runtime docs identify `task-manager` and env tools as the product path.
4. Repo consistency check prevents `task-manager` skill instructions from telling buddies to mutate raw `buddyswitch/objects/tasks/*.json`.

**Assertions:**

- Manual/debug helper remains separate from product active-buddy scoped tools.
- Prompt or skill text does not claim permission authority.
- Product tests exercise the product env tool path.

**Anti-cheat guard:**

- Do not delete all mentions of `env_tasks.py` just to pass a search. If retained, classify it clearly as debug/manual and prove product paths avoid it.

## TG-08 Existing Runtime Regression

**Purpose:** Prove the task-manager env layer does not break current runtime behavior.

**Test cases:**

1. `prepare` still preserves ordinary user request text.
2. Text that resembles retired routing syntax remains ordinary request text and does not change active buddy.
3. `persist` still commits one buddy run with the existing receipt shape.
4. Dev prepare context still reports write access to `projects/app`.
5. PM, Market, Design, and Test prepare contexts remain read-only for project source.
6. Market browser evidence structured feedback remains unchanged except for unrelated context additions.
7. Product-mode broker unavailable feedback still tells the host to stop and report rather than bypass runtime safeguards.
8. Existing runtime context required sections remain present.

**Assertions:**

- Active buddy comes from instance metadata.
- Task-manager additions do not widen filesystem or raw state permissions.
- Existing prepare/persist tests continue to pass.
- Browser evidence tests continue to pass.

**Anti-cheat guard:**

- Use public prepare/persist output and broker responses. Do not validate only private helper functions.

## TG-09 Launcher Product Instance Probe

**Purpose:** Prove a launcher-managed instance receives the executable tool surface and shared skill.

**Flow:**

1. Start or materialize a temporary Dev instance.
2. Inspect the runtime workspace.
3. Confirm `.agents/skills/task-manager/SKILL.md` exists.
4. Confirm `scripts/env/client.py` exists in the runtime workspace.
5. Confirm `AGENTS.md` remains concise and points to runtime context and structured feedback.
6. Run the env client against a broker-backed test instance or confirm broker-unavailable structured feedback when broker is intentionally absent.

**Assertions:**

- Runtime workspace uses launcher-managed instance path, not the main checkout.
- Shared skill and env client are both present.
- Missing broker produces structured stop/report feedback, not raw state fallback instructions.
- Existing `.codex/config.toml` neutralization behavior remains intact.

**Anti-cheat guard:**

- Do not inspect only source templates. At least one test must inspect a materialized runtime workspace.

## Required Verification Commands

Run focused task-manager tests:

```bash
python3 -m pytest -p no:cacheprovider tests/test_task_manager_env_tool.py -q
```

Run runtime integration tests:

```bash
python3 -m pytest -p no:cacheprovider tests/test_runtime_skills.py tests/test_runtime_broker.py -q
python3 -m pytest -p no:cacheprovider tests/test_turn_runtime.py tests/test_runtime_tool_feedback.py -q
```

Run repo consistency and launcher checks:

```bash
python3 -m pytest -p no:cacheprovider tests/test_repo_consistency.py -q
python3 -m pytest -p no:cacheprovider tests/test_buddyswitch_launcher.py -q
```

Run import proof:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile scripts/env/client.py scripts/env/services/tasks.py scripts/env/tools/task_manager.py scripts/runtime_kernel/broker.py scripts/turn_runtime.py
```

Run behavior-oriented inspection:

```bash
rg -n "task-manager|env.task|scripts/env/client.py|scripts/env_tasks.py" buddyswitch scripts tests framework tools/launcher docs/spec
```

Every match should support the product contract, structured feedback, shared skill materialization, or explicit debug/manual containment.

## Completion Standard

The task-manager env layer is verified when:

- every buddy receives the shared skill in a materialized runtime workspace;
- own-buddy create/list/get/update/archive/current binding flows pass;
- cross-buddy task reads and mutations fail with structured feedback and no mutation;
- current task binding and current track binding are synchronized from the selected owned task;
- runtime context exposes compact task env tool hints;
- old debug/manual task paths are not treated as the product permission source;
- focused and regression commands pass from `/Users/chen/Dev/buddyswitch/.worktrees/dev0210`.
