# BuddySwitch Workspace

BuddySwitch is an env-centric control layer that runs inside the host Codex session. The host session does the actual work; BuddySwitch parses `switch ...` directives, resolves allowed skills, validates structured output, and persists canonical task, artifact, track, and run state.

## 30-Second Quick Start

Two modes exist:

1. **Develop BuddySwitch:** run `codex` from the repo root.
2. **Run BuddySwitch product mode:** run `./buddyswitch-codex instance start --buddy <buddy>`.

The launcher-managed product mode layout is:

- `${BUDDYSWITCH_SHARED_ROOT}` as the shared launcher root
- `${BUDDYSWITCH_SHARED_ROOT}/state` for canonical BuddySwitch task, track, artifact, and run state
- `${BUDDYSWITCH_SHARED_ROOT}/instances/<instance-id>/workspace` for each buddy-locked execution worktree
- `${BUDDYSWITCH_SHARED_ROOT}/project/workspace` as the shared project workspace for durable product source edits
- `tools/launcher/assets/buddies/<buddy>/AGENTS.md` for the instance root prompt contract

Product mode has two work surfaces:

- Runtime workspace: `${BUDDYSWITCH_SHARED_ROOT}/instances/<instance-id>/workspace`
  BuddySwitch control flow, projected state, raw dumps, browser scratch, and relative `projects/app` access.
- Shared project workspace: `${BUDDYSWITCH_SHARED_ROOT}/project/workspace`
  Shared product source for `projects/app`; `${BUDDYSWITCH_PROJECT_WORKSPACE_DIR}` is launcher/debug context.

If you are developing BuddySwitch itself, start here:

1. Read `AGENTS.md` first. It describes the repo-root development workspace.
2. Validate the parser and router:

```bash
python3 scripts/parse_switch.py "switch pm: create track"
python3 scripts/codex_router.py "switch pm: create track"
```

3. If you want to exercise the runtime loop manually, switch into a launcher-managed runtime workspace first. `resolve` may materialize a zero-run task and reserve the next run envelope, so it is blocked in the repo-root development checkout.

Resolve a real directive into BuddySwitch `resolve_context` there:

```bash
python3 scripts/switch_runtime.py resolve \
  "switch market: quick market research for AI scheduler landing page" \
  > /tmp/buddyswitch-resolved.json
```

4. Choose one `skill_id` from `resolve_context.skills`, then execute that skill in the current Codex session:
   - read the selected skill's `instruction_path`
   - treat `resolve_context.inputs` as the current selected input bundle only when the selected skill surface is already resolved
   - for multi-skill buddies, choose from `resolve_context.skills` using the skill metadata plus `task_context` / `track_context`
   - for market runs, apply `resolve_context.skills[*].host_execution` and `resolve_context.skills[*].tool_scope`
   - execute the run in-session and produce a structured result matching the reported schema

5. Persist the result when the run should become BuddySwitch state. The current CLI command is `persist`, which implements the `persist-skill-result` step:

```bash
python3 scripts/switch_runtime.py persist \
  --resolved /tmp/buddyswitch-resolved.json \
  --skill-id research-scan \
  --result /tmp/buddyswitch-result.json
```

6. `persist` is end-of-turn. Successful `persist` does not reserve a follow-up run. If another turn is needed, run `resolve` with `receipt.recommended_switch`, then start the read-only Context Panel:

```bash
python3 scripts/serve_context_panel.py
```

Then open `http://127.0.0.1:8765/`.

If you need a launcher-managed product-mode session instead of repo-root development mode, run:

```bash
./buddyswitch-codex instance buddies
./buddyswitch-codex instance start --buddy pm
```

`instance start --buddy <buddy>` creates a fresh buddy-locked instance. To re-enter a stored instance, use:

```bash
./buddyswitch-codex instance list
./buddyswitch-codex instance open <instance-id>
```

To remove one stored instance without deleting shared BuddySwitch state:

```bash
./buddyswitch-codex instance delete <instance-id>
```

`instance open <instance-id>` re-enters the existing instance workspace and runtime profile; it does not restore the previous Codex transcript.
`instance delete <instance-id>` previews deletion. Add `--yes` to remove only that instance's launcher-owned local tree; shared BuddySwitch state is kept.

## Daily Use

### Parse or route a switch directive

```bash
python3 scripts/parse_switch.py "switch dev(task-dev-onboarding) -> track-demo: continue the implementation"
python3 scripts/codex_router.py "switch pm: create ai-scheduler-lp track"
```

### Resolve a run

Run `resolve` only from the launcher-owned instance runtime workspace. In create mode it may materialize a zero-run task and reserve the next run id, so the repo-root development checkout blocks it; start the runtime workspace with `./buddyswitch-codex instance start --buddy <buddy>` first. Product mode runs from `${BUDDYSWITCH_SHARED_ROOT}/instances/<instance-id>/workspace`, projects canonical state from `${BUDDYSWITCH_SHARED_ROOT}/state`, and maps relative `projects/app` to the shared project workspace.

```bash
python3 scripts/switch_runtime.py resolve "switch market: quick market research for AI scheduler landing page"
python3 scripts/switch_runtime.py resolve "switch pm: create ai-scheduler-lp track"
```

### Persist a structured result

Run `persist` only from the launcher-owned instance runtime workspace. The repo-root development checkout blocks BuddySwitch runtime writes; start it with `./buddyswitch-codex instance start --buddy <buddy>` first. Product mode writes canonical state under `${BUDDYSWITCH_SHARED_ROOT}/state`, keeps instance-local scratch under `${BUDDYSWITCH_SHARED_ROOT}/instances/<instance-id>/workspace`, and keeps durable product source in the shared project workspace. This command is the current CLI wrapper for the `persist-skill-result` step.

```bash
python3 scripts/switch_runtime.py persist \
  --resolved /tmp/buddyswitch-resolved.json \
  --skill-id write-prd \
  --result /tmp/buddyswitch-result.json

python3 scripts/switch_runtime.py persist \
  --resolved /tmp/buddyswitch-resolved.json \
  --skill-id track-manager \
  --result /tmp/buddyswitch-result.json
```

### Open the workspace viewer

```bash
python3 scripts/serve_context_panel.py
```

### Manage product-mode instances

```bash
./buddyswitch-codex instance buddies
./buddyswitch-codex instance start --buddy <buddy>
./buddyswitch-codex instance list
./buddyswitch-codex instance open <instance-id>
./buddyswitch-codex instance delete <instance-id>
```

`instance start --buddy <buddy>` creates a fresh buddy-locked instance.
`instance open <instance-id>` re-enters the existing instance workspace and runtime profile; it does not restore the previous Codex transcript.
`instance delete <instance-id>` previews deletion. Add `--yes` to remove only that instance's launcher-owned local tree; shared BuddySwitch state is kept.

### Clean local state

```bash
./buddyswitch-codex data cleanup --buddy market
./buddyswitch-codex data cleanup --all-data
```

Defaults are preview mode. Add `--yes` to apply deletion. Data cleanup targets shared BuddySwitch data and instance-local scratch; it never deletes instance roots or the shared launcher root.

## What BuddySwitch Is

BuddySwitch is not a standalone agent and it does not run host tools for you.

BuddySwitch is responsible for:

- parsing `switch ...` commands
- loading buddy and skill metadata from the env manifest
- returning `resolve_context`, allowed skill metadata, and the current input bundle when one skill surface is already resolved
- validating structured output against schemas
- persisting canonical task, artifact, track, and run state

The host Codex session is responsible for:

- understanding the user request
- choosing one `skill_id` from the allowed candidates
- executing the selected skill workflow
- browsing, coding, testing, and writing outputs
- returning a schema-valid structured result

## Mental Model

If you remember only four things, remember these:

- `switch` is the canonical entry point.
- The host session does the real work.
- BuddySwitch is the control layer and recorder.
- State lives in task, artifact, track, and run objects.

The default flow is:

1. `parse`
2. `resolve_context`
3. host run
4. `persist-skill-result`
5. if another turn is needed, run `resolve` with `receipt.recommended_switch`

Important runtime rules:

- `resolve_context` reserves the next run envelope and may materialize a zero-run task in create mode before any persist happens.
- the host chooses one `skill_id` from `resolve_context.skills` and executes it locally.
- `persist-skill-result` is the canonical write boundary; `scripts/switch_runtime.py persist` is its current CLI wrapper.
- BuddySwitch-managed outputs do not go into `artifacts/*.md` or `runs/summaries/**`.

## Canonical Switch Syntax

BuddySwitch uses this canonical directive:

```text
switch <buddy>(<task-id>) -> <track-id>: <demand>
```

Supported forms:

- `switch <buddy>: <demand>`
- `switch <buddy> -> <track-id>: <demand>`
- `switch <buddy>(<task-id>): <demand>`
- `switch <buddy>(<task-id>) -> <track-id>: <demand>`

Examples:

- `switch market: Research demand for AI companion live spaces`
- `switch pm -> track-ai-companion: Define MVP scope`
- `switch pm(task-pm-ai-companion): Continue scope refinement`
- `switch dev(task-dev-ai-companion) -> track-ai-companion: Implement the approved P0 scope in projects/app`
- `switch test: Run smoke checks for the latest implementation`

The text after `:` is a demand, not a task object. If no task id is supplied, `resolve_context` may materialize a zero-run task immediately and reserve the next run id before `persist-skill-result` records the run. Minor spacing variation around `:` and `->` can be normalized as long as buddy, optional task id, optional track id, and demand remain clear.

## Core Runtime Flow

### 1. Parse

`scripts/parse_switch.py` validates the `switch` directive and extracts:

- `buddy`
- optional `task_id`
- optional `track_id`
- `demand`

### 2. Resolve

`scripts/switch_runtime.py resolve` returns `resolve_context` by loading:

- buddy definition from `buddyswitch/manifest.toml`
- allowed skills for that buddy
- task context
- optional track context
- the current input bundle when one skill surface is already resolved
- reserved run envelope
- host execution metadata when the selected skill family needs it

The stable handoff includes:

- `skills`
- `task_resolution`
- `run_envelope`
- `task_context`
- `track_context`
- `inputs`
- `warnings`

This step reserves the next run envelope and may materialize a zero-run task in create mode, but it does not write the final run audit or artifact result. Run it from the launcher-owned runtime workspace rather than the repo-root development checkout.

### 3. Host Run

The host Codex session:

1. chooses one `skill_id`
2. reads the selected skill's `instruction_path`
3. treats `resolve_context.inputs` as the current selected input bundle only when the selected skill surface is already resolved
4. for market runs, applies `resolve_context.skills[*].host_execution` and `resolve_context.skills[*].tool_scope`
5. executes the workflow
6. produces a structured result matching the selected schema

BuddySwitch never performs browser, shell, editor, or MCP tool actions on behalf of the host.

### 4. Persist

`scripts/switch_runtime.py persist` is the current CLI wrapper for the `persist-skill-result` step. It validates:

- selected skill identity
- schema shape
- safe task and track references

Then it writes canonical state to the object store:

- task objects
- artifact objects when the skill produces an artifact
- track objects when track mutation is part of the request
- run audit JSON

Successful persistence returns `{ok, receipt, refreshed_context}`. The host-facing follow-up data lives inside `receipt`, including:

- `task_title`
- optional `track_title`
- `reference_switches`
- `related_run_ids`
- `recommended_switch`

`persist` is the end-of-turn commit boundary. Successful `persist` does not reserve a follow-up run.

Check `refreshed_context.ok` before using it for the next turn. On `E_RUNTIME_REFRESH_CONTEXT`, the persist already committed successfully; if another turn is needed, run `resolve` with `receipt.recommended_switch`.

## Project Layout

These paths matter most when you are orienting yourself in the repo:

- `buddyswitch/manifest.toml`
  Buddy definitions, skill wiring, and object-authority metadata.
- `buddyswitch/skills/**`
  Skill packages used by BuddySwitch runtime.
- `buddyswitch/objects/tracks/*.json`
  Canonical track objects.
- `buddyswitch/objects/tasks/*.json`
  Canonical task objects.
- `buddyswitch/objects/artifacts/*.json`
  Canonical artifact objects with structured content.
- `buddyswitch/content/runs/*.json`
  Canonical run audit content.
- `scripts/`
  Runtime, manifest, store, object CRUD, parser, router, cleanup, and panel server scripts.
- `framework/console/`
  Read-only Context Panel frontend.
- `framework/schemas/`
  Output schemas per skill family.
- `framework/contracts/`
  Buddy-level contracts and expectations.
- `framework/docs/`
  Architecture and framework specifications.
- `projects/app/`
  Main app code. In product mode, keep working with relative `projects/app` from the instance runtime workspace; launcher projects it to shared product source.

## Core Storage and Object Authority

Canonical storage lives under the launcher runtime workspace using these relative paths:

- Env manifest: `buddyswitch/manifest.toml`
- Track objects: `buddyswitch/objects/tracks/*.json`
- Task objects: `buddyswitch/objects/tasks/*.json`
- Artifact objects: `buddyswitch/objects/artifacts/*.json`
- Run audit content: `buddyswitch/content/runs/*.json`
- Legacy/raw dumps: `runs/raw/`

Authority model:

- `pm` owns track lifecycle mutations: `create`, `update`, `advance`, `archive`
- other buddies read tracks and persist artifacts through their resolved task
- every persisted run belongs to a task
- `buddy -> skills` in the manifest is the main runtime routing authority
- `permissions` in the manifest are object-authority metadata for manual and debug APIs

## Skills, Schemas, and Contracts

BuddySwitch skills are packaged under `buddyswitch/skills/**/` and are not using Codex native `.agents/skills` semantics.

Each skill package is made of:

- `skill.toml`
  Runtime metadata such as `id`, `buddy`, `objects`, `output_schema`, `input_slots`, `output_slot`, and artifact behavior.
- `SKILL.md`
  Host-facing execution guidance the host reads from the selected skill's `instruction_path`.
- optional `assets/`
  Templates or report scaffolds used by the skill.
- optional `references/`
  Domain guidance used by the host during execution.

Schemas and contracts live separately:

- `framework/schemas/*`
  Structured output shape required by each skill family.
- `framework/contracts/*`
  Buddy-level operating contracts, boundaries, and output expectations.

This separation matters:

- the manifest decides which skills are available for a buddy
- `skill.toml` describes runtime behavior
- `SKILL.md` tells the host how to execute
- schemas validate outputs
- contracts define buddy-level expectations and boundaries

## Key Scripts

These are the main operational entry points:

- `scripts/switch_runtime.py`
  Main BuddySwitch runtime with `resolve` and `persist` as the current CLI wrapper for `persist-skill-result`.
- `scripts/parse_switch.py`
  Syntax parser for canonical `switch` directives.
- `scripts/codex_router.py`
  Single Codex adapter for env-backed routing.
- `scripts/env_manifest.py`
  Manifest inspection utilities.
- `scripts/env_tracks.py`
  Manual and debug track CRUD and lifecycle operations.
- `scripts/env_tasks.py`
  Manual and debug task read, update, and archive operations.
- `scripts/env_artifacts.py`
  Manual and debug artifact CRUD and registration operations.
- `scripts/output_schema.py`
  Output schema loading and validation.
- `scripts/workspace_data.py`
  Aggregates canonical state into the `/api/workspace` payload.
- `scripts/serve_context_panel.py`
  Serves the read-only Context Panel.

## Context Panel

The Context Panel is a read-only workspace viewer. It is served from `framework/console/` and reads live data from `/api/workspace`.

Start it with:

```bash
python3 scripts/serve_context_panel.py
```

Then open `http://127.0.0.1:8765/`.

The panel shows:

- track objects
- task objects
- artifact objects
- run audits
- copyable switch and cleanup commands

The panel must not:

- invoke buddies
- call LLMs
- execute shell commands
- execute cleanup commands
- write repository files from browser code

Its source of truth is always canonical BuddySwitch state:

- `buddyswitch/manifest.toml`
- `buddyswitch/objects/tracks/*.json`
- `buddyswitch/objects/tasks/*.json`
- `buddyswitch/objects/artifacts/*.json`
- `buddyswitch/content/runs/*.json`

## Browser MCP

Use the default browser MCP for general public browsing:

```bash
codex mcp add chrome-devtools -- npx chrome-devtools-mcp@latest
```

BuddySwitch launcher sessions now bootstrap the execution workspace shell and browser capabilities automatically when you run:

```bash
./buddyswitch-codex instance start --buddy pm
```

`instance start --buddy <buddy>` creates a fresh instance worktree from the current repo code.

Launcher-managed Codex config sets all enabled MCP servers to `default_tools_approval_mode = "approve"` so product-mode research does not stop for per-tool MCP approval prompts. Do not set `supports_parallel_tool_calls = true` for the browser cockpit path; the instance browser is stateful and should execute page navigation, clicks, and DOM reads serially.

Repair and refresh commands are split by responsibility:

```bash
./buddyswitch-codex env browser status --instance <instance-id>
./buddyswitch-codex env browser ensure --instance <instance-id>
./buddyswitch-codex env reset
```

- `env browser ensure --instance <instance-id>` repairs that instance's browser cockpit and browser MCP setup.
- `env browser ensure --instance <instance-id>` and `env browser status --instance <instance-id>` default to that instance profile path:

```text
~/.codex-buddyswitch/instances/<instance-id>/browser/profile
```

Shared browser profile fallback (used when no instance context is bound):

```text
~/.codex-buddyswitch/chrome/shared-browser
```

Override the profile path with `BUDDYSWITCH_BROWSER_PROFILE_DIR=/your/path` when needed.

## Cleanup

Manual cleanup entrypoint:

```bash
./buddyswitch-codex data cleanup --buddy <buddy>
./buddyswitch-codex data cleanup --all-data
```

Defaults to preview mode. Add `--yes` to apply deletion.

Useful modes:

- `--buddy <buddy>`
  Cleans that buddy's raw logs, task objects, artifact objects, and run content where `switch.buddy == <buddy>`.
- `--all-data`
  Clears all-buddy shared data and all-buddy raw scratch while keeping instance roots, shared root, and shared project source.

## Terminal Output Contract

Normal BuddySwitch terminal summaries should use exactly three sections in this order:

1. `Receipt`
2. `Commands`
3. `Summary`

Expected contents:

- `Receipt`
  `Persisted`, `Task`, optional `Track`, `Artifact`, `Run`, optional `Related Runs`
- `Commands`
  exactly one `Template` command and one `Recommended` command
- `Summary`
  1-2 lines of execution summary and up to 4 open questions

Do not lead normal summaries with long object-path dumps. Paths are debug details.

## Further Reading

Start here when you need deeper framework context:

- `framework/docs/architecture-overview.md`
- `framework/docs/switch-spec.md`
- `framework/docs/track-registry.md`
- `framework/docs/interface-spec.md`
- `framework/docs/skill-architecture-best-practices.md`
- `framework/docs/skill-runtime-shared-rules.md`
- `framework/docs/artifacts-runs-git-policy.md`
- `framework/docs/buddyswitch-development-constitution.md`
