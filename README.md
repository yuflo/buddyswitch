# BuddySwitch Workspace

BuddySwitch is an env-centric control layer that runs inside the host Codex session. The host session does the actual work; BuddySwitch parses `switch ...` directives, resolves allowed skills, validates structured output, and persists canonical task, artifact, track, and run state.

## 30-Second Quick Start

Two modes exist:

1. **Develop BuddySwitch:** run `codex` from the repo root.
2. **Run BuddySwitch product mode:** run `./buddyswitch-codex start`.

The launcher-managed product mode uses:

- `${BUDDYSWITCH_SHARED_ROOT}` for runtime environment isolation
- `${BUDDYSWITCH_SHARED_ROOT}/workspace` for the execution worktree
- `tools/launcher/assets/runtime-AGENTS.md` for the runtime workspace contract

If you are developing BuddySwitch itself, start here:

1. Read `AGENTS.md` first. It describes the repo-root development workspace.
2. Validate the parser and router:

```bash
python3 scripts/parse_switch.py "switch pm: create track"
python3 scripts/codex_router.py "switch pm: create track"
```

3. Resolve a real directive into BuddySwitch runtime context:

```bash
python3 scripts/switch_runtime.py resolve \
  "switch market: quick market research for AI scheduler landing page" \
  > /tmp/buddyswitch-resolved.json
```

4. Choose one `skill_id` from `eligible_skills`, then materialize the selected skill packet:

```bash
python3 scripts/switch_runtime.py prepare-execution \
  --resolved /tmp/buddyswitch-resolved.json \
  --skill-id research-scan \
  > /tmp/buddyswitch-selected-skill.json
```

5. In the current Codex session:
   - inject `selected_skill_packet.skill_instructions` verbatim
   - treat `selected_skill_packet.execution_steps` as ordered requirements
   - execute the run in-session
   - produce a structured result matching the reported schema

6. Persist the result when the run should become BuddySwitch state:

```bash
python3 scripts/switch_runtime.py persist \
  --resolved /tmp/buddyswitch-resolved.json \
  --skill-id research-scan \
  --result /tmp/buddyswitch-result.json
```

7. Start the read-only Context Panel:

```bash
python3 scripts/serve_context_panel.py
```

Then open `http://127.0.0.1:8765/`.

If you need a launcher-managed product-mode session instead of repo-root development mode, run:

```bash
./buddyswitch-codex start
```

## Daily Use

### Parse or route a switch directive

```bash
python3 scripts/parse_switch.py "switch dev(task-dev-onboarding) -> track-demo: continue the implementation"
python3 scripts/codex_router.py "switch pm: create ai-scheduler-lp track"
```

### Resolve a run

```bash
python3 scripts/switch_runtime.py resolve "switch market: quick market research for AI scheduler landing page"
python3 scripts/switch_runtime.py resolve "switch pm: create ai-scheduler-lp track"
```

### Prepare execution after selecting a skill

```bash
python3 scripts/switch_runtime.py prepare-execution \
  --resolved /tmp/buddyswitch-resolved.json \
  --skill-id write-prd
```

### Persist a structured result

Run `persist` only from the launcher-owned runtime workspace. The repo-root development checkout blocks BuddySwitch runtime writes; start it with `./buddyswitch-codex start` first.

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

### Clean local state

```bash
scripts/cleanup_buddyswitch.sh --agent market
scripts/cleanup_buddyswitch.sh --all-agents
scripts/cleanup_buddyswitch.sh --project app
scripts/cleanup_buddyswitch.sh --all-storage
```

Defaults are dry-run. Add `--execute` to apply deletion. Cleanup targets the launcher runtime workspace under `~/.codex-buddyswitch/workspace`; it does not clean the repo-root development checkout.

## What BuddySwitch Is

BuddySwitch is not a standalone agent and it does not run host tools for you.

BuddySwitch is responsible for:

- parsing `switch ...` commands
- loading buddy and skill metadata from the env manifest
- returning allowed skill candidates and runtime packets
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
2. `resolve`
3. `prepare-execution`
4. host run
5. `persist`

Important runtime rules:

- `resolve` does not write BuddySwitch state.
- `prepare-execution` is the required bridge between `resolve` and host execution.
- `persist` is the canonical write boundary.
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

The text after `:` is a demand, not a task object. If no task id is supplied, `persist` creates a new task for the run. Minor spacing variation around `:` and `->` can be normalized as long as buddy, optional task id, optional track id, and demand remain clear.

## Core Runtime Flow

### 1. Parse

`scripts/parse_switch.py` validates the `switch` directive and extracts:

- `buddy`
- optional `task_id`
- optional `track_id`
- `demand`

### 2. Resolve

`scripts/switch_runtime.py resolve` loads:

- buddy definition from `buddyswitch/manifest.toml`
- allowed skills for that buddy
- task context
- optional track context
- output schema paths
- host next actions

It returns fields such as:

- `eligible_skills`
- `skill_cards`
- `task_resolution`
- `required_output_schema_by_skill`
- `run_instructions`

This step writes nothing.

### 3. Prepare Execution

`scripts/switch_runtime.py prepare-execution` takes the resolved payload plus a chosen `skill_id` and materializes `selected_skill_packet`.

That packet contains:

- `skill_instructions`
- `execution_steps`
- `selected_inputs`
- `output_schema_path`
- execution constraints from the skill metadata

The host session should use the packet directly instead of reconstructing the skill manually.

### 4. Host Run

The host Codex session:

1. chooses one `skill_id`
2. injects the selected skill instructions
3. executes the workflow
4. produces a structured result matching the selected schema

BuddySwitch never performs browser, shell, editor, or MCP tool actions on behalf of the host.

### 5. Persist

`scripts/switch_runtime.py persist` validates:

- selected skill identity
- schema shape
- safe task and track references

Then it writes canonical state to the object store:

- task objects
- artifact objects when the skill produces an artifact
- track objects when track mutation is part of the request
- run audit JSON

Successful persistence also returns concise host-facing follow-up data such as:

- `task_title`
- optional `track_title`
- `reference_switches`
- `related_run_ids`
- `recommended_switch`

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
  Main app code. Runtime-only temporary data belongs in `projects/app/.runtime/` inside the launcher runtime workspace, not in the source checkout.

## Core Storage and Object Authority

Canonical storage lives under the launcher runtime workspace using these relative paths:

- Env manifest: `buddyswitch/manifest.toml`
- Track objects: `buddyswitch/objects/tracks/*.json`
- Task objects: `buddyswitch/objects/tasks/*.json`
- Artifact objects: `buddyswitch/objects/artifacts/*.json`
- Run audit content: `buddyswitch/content/runs/*.json`
- Legacy/raw dumps: `runs/raw/`

Authority model:

- `pm` owns track lifecycle: `create`, `read`, `list`, `update`, `advance`, `archive`
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
  Host-facing execution guidance that gets injected through `selected_skill_packet.skill_instructions`.
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
  Main BuddySwitch runtime with `resolve`, `prepare-execution`, and `persist`.
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
- `scripts/cleanup_buddyswitch.sh`
  Storage-aware cleanup helper.

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

BuddySwitch launcher sessions now bootstrap both browser capabilities automatically when you run:

```bash
./buddyswitch-codex start
```

Use the browser subcommands only for diagnostics or manual repair:

```bash
./buddyswitch-codex browser status
./buddyswitch-codex browser ensure
```

Default shared browser profile path:

```text
~/.codex-buddyswitch/chrome/shared-browser
```

Override the profile path with `BUDDYSWITCH_BROWSER_PROFILE_DIR=/your/path` when needed.

## Cleanup

Manual cleanup helper:

```bash
scripts/cleanup_buddyswitch.sh
```

Defaults to dry-run. Add `--execute` to apply deletion.

Useful modes:

- `--agent <buddy>`
  Cleans that buddy's raw logs, task objects, artifact objects, and run content where `switch.buddy == <buddy>`.
- `--all-agents`
  Clears BuddySwitch env state for all buddies, including run audit content.
- `--project app`
  Only clears `projects/app/.runtime/` inside the launcher runtime workspace.
- `--all-storage`
  Clears the full launcher-managed BuddySwitch storage surface.

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
