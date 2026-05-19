# Tool Independence Repair Scope

Date: 2026-05-19

Source memo: `docs/memo/2026-05-19-worktree-independence-review-memo.md`

## Goal

Complete the env.tool independence repair so one tool's implementation failure, payload drift, or local development change does not break unrelated tools or create hidden runtime contracts.

The repair must follow the SHARP Forward rule: replace the broken path directly, keep one current contract, remove ignored/stale fields, and verify through tests. Do not add a compatibility layer, shim, dual registry, fallback registry, generic plugin loader, workflow engine, event bus, or long-lived transitional path.

## Key Questions This Task Answers

1. Can the runtime import env.tool catalog/router/dispatch under the checkout's default `python3`?
2. Can unsupported envelope requests and healthy tool requests run without importing every service module?
3. If one selected tool cannot load, is the failure localized to that selected tool and returned as structured tool feedback?
4. Do registry payload fields, runtime catalog payload fields, CLI affordances, and service accepted fields describe one current contract?
5. Are stale accepted-but-ignored fields removed instead of silently tolerated?
6. Does each existing tool main path continue to work after dispatch and payload-contract cleanup?

## Current Confirmed Problems

### P1: Default `python3` Runtime Import Failure

Current default `python3` is Python 3.9.6.

This focused command fails today:

```bash
python3 -m pytest tests/test_env_tool_router.py::EnvToolRouterTests::test_dispatch_handler_coverage_matches_registry_actions -q
```

Observed failure:

```text
TypeError: unsupported operand type(s) for |: 'types.GenericAlias' and 'NoneType'
```

Root cause:

```python
GetMessage = Callable[[str], dict[str, Any] | None]
```

in `scripts/env/domain/messages.py` is evaluated as a type alias under Python 3.9. The same test passes under `python` pointing to Python 3.13.5, but runtime docs and CLI commands use `python3`, so Python 3.9 compatibility is part of the current contract.

### P2: Eager Dispatch Imports Couple All Tools

`scripts/env/tools/dispatch.py` imports every service module at module load time:

- `env.services.artifacts`
- `env.services.buddybox`
- `env.services.comments`
- `env.services.context`
- `env.services.evidence`
- `env.services.messages`
- `env.services.search`
- `env.services.tasks`
- `env.services.tracks`

Because router imports dispatch, one unrelated service import failure can block routing for every tool.

Target behavior:

- importing `env.tools.contracts` must not import services;
- importing `env.tools.router` must not import services;
- importing `env.tools.dispatch` must not import services;
- dispatching `task.list` must not import `env.services.messages`;
- dispatching `message.list` may import `env.services.messages`;
- a selected-tool import failure must return structured feedback for that selected tool instead of crashing unrelated routing.

### P3: Tool Payload Contract Drift

Observed contract/service drift:

```text
task.create:
  contract fields = status, summary, task_id, title, track_id
  service fields  = active_buddy, buddy, status, summary, task_id, title, track_id

track.update_now:
  service additionally allows owner_buddy

track.add_update:
  service additionally allows owner_buddy

comment.add:
  service additionally allows anchor, artifact_revision_id, mentions

comment.list:
  service additionally allows status
```

Target behavior:

- `task.create` rejects `buddy` and `active_buddy`; task owner is always the runtime active buddy.
- `track.update_now` and `track.add_update` reject `owner_buddy`; track owner is immutable and not a payload field for these actions.
- `comment.add` exposes its real fields in the registry because `anchor`, `artifact_revision_id`, and `mentions` have real product semantics.
- `comment.list` exposes `status` in the registry and CLI because status filtering has real product semantics.
- services validate accepted fields from the same authoritative registry payload fields, not from duplicated per-service allowlists.

### P4: Shared Tool Development Touchpoints Remain

It is acceptable that this small monolith has central files. It is not acceptable for those files to drift.

The following remain shared authoritative files:

- `scripts/env/tools/contracts.py`
- `scripts/env/tools/semantics.py`
- `scripts/env/tools/dispatch.py`
- `scripts/env/tools/router.py`
- `scripts/env/client.py`
- `scripts/turn_runtime.py`

Target behavior:

- central registry is authoritative;
- dispatch maps only registered tool/action pairs;
- runtime status and `context.get.tool_catalog` are projections of the registry;
- CLI operations and arguments align with the registry;
- tests catch drift immediately.

## Non-Goals

- Do not redesign track/artifact/comment product coupling.
- Do not split the monolith into external service processes.
- Do not add a plugin system or dynamic discovery framework.
- Do not preserve ignored `task.create` fields for compatibility.
- Do not keep old and new dispatch paths side by side.
- Do not edit runtime state under `buddyswitch/objects/**` or `buddyswitch/local/buddybox/**` directly.
- Do not change docs as a substitute for runtime tests.

## Definition Of Done

The task is complete only when all of these are true:

1. Default `python3` can import and test env.tool router/dispatch paths.
2. `env.tools.router` and `env.tools.dispatch` import without loading service modules.
3. A broken unrelated service import does not prevent a healthy selected tool from running.
4. A broken selected service import returns structured, no-state-change feedback for that selected tool.
5. Registry payload fields, runtime tool catalog payload fields, CLI affordances, and service accepted fields align.
6. `task.create` rejects `buddy` and `active_buddy` without creating a task.
7. `track.update_now` and `track.add_update` reject `owner_buddy` without mutating the track.
8. `comment.add` and `comment.list` registry fields describe the real supported comment payload.
9. Focused tool suites pass under `python3`.
10. Broader runtime boundary, skill, and consistency suites pass under `python3`.
11. `git diff --check` passes.

