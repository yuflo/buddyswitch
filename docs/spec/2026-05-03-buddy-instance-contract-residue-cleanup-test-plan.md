# Buddy Instance Contract Residue Cleanup Test Plan

**Goal:** Verify that a launcher-managed buddy instance accepts ordinary product requests, persists canonical state, and renders a complete protocol-compliant final receipt, with no old switch/router/resolve-era product path left active.

**Testing Principle:** Tests must start from user-visible and contract-level requirements, not from implementation quirks. A test is valid only when it proves behavior a user, host agent, or downstream contract consumer depends on.

---

## Functional Requirements Under Test

FR1. A buddy instance is locked to one active buddy and accepts ordinary user request text.

FR2. The host receives one prepared turn context and chooses exactly one skill from that context.

FR3. Persist commits canonical task, artifact, track, and run state and returns a structured receipt with stable IDs.

FR4. Final terminal output instructions must require the complete `Receipt` and `Summary` contract.

FR5. Runtime receipt metadata must not be embedded in business skill output schemas.

FR6. All manifest buddies must have equivalent prompt and contract coverage.

FR7. Product docs, prompts, active tests, launcher config, and runtime code must not teach or rely on old switch/router/resolve product flow.

FR8. Track-manager runs and artifact-producing runs both satisfy receipt requirements.

FR9. The context panel and workspace projection continue to read structured state, not command strings.

FR10. Obsolete historical planning docs must not remain searchable as current product contract guidance.

## Coverage Matrix

| Requirement | Test Type | Primary Files | Observable Proof |
|---|---|---|---|
| FR1 | Runtime integration | `tests/test_turn_runtime.py`, `tests/test_turn_integration.py` | Ordinary request creates/reuses task under locked buddy; structural command input rejects without writes |
| FR2 | Contract and runtime integration | `tests/test_parallel_contracts.py`, `tests/test_turn_runtime.py` | Prepare response shape matches `prepare-turn-context`; `persist` rejects out-of-context skill id |
| FR3 | Runtime integration | `tests/test_turn_runtime.py`, `tests/test_turn_integration.py` | Receipt IDs match persisted task/artifact/run files |
| FR4 | Prompt and launcher integration | `tests/test_repo_consistency.py`, `tests/test_buddyswitch_launcher.py` | Generated workspace `AGENTS.md` contains complete receipt fields for every tested buddy |
| FR5 | Schema boundary | `tests/test_repo_consistency.py`, `tests/test_turn_runtime.py` | Skill schemas reject runtime IDs; persist returns runtime IDs in receipt |
| FR6 | Manifest coverage | `tests/test_repo_consistency.py` | Every manifest buddy has prompt asset and `framework/contracts/<buddy>.md` |
| FR7 | Residue guard | `tests/test_repo_consistency.py` plus `rg` command | No active product paths contain old product-flow terms |
| FR8 | Runtime integration | `tests/test_turn_runtime.py` | Artifact skill and track-manager skill both return valid receipt shape |
| FR9 | Console/projection contract | `tests/test_console_app_contract.py`, `tests/test_parallel_contracts.py` | Projection uses `next_state` and `receipt_paths`; no command strings |
| FR10 | Docs residue guard | `tests/test_repo_consistency.py` plus `rg` command | Only current cleanup plan/test plan mention old terms as historical evidence |

## Test Groups

### TG-01: Product Input And Buddy Lock

**Requirement:** Product users submit ordinary requests inside a locked buddy instance.

Cases:

1. `pm` instance receives `Draft onboarding PRD`.
   - Expected: `prepare` returns `ok=true`, `active_buddy=pm`, non-empty `current_task_id`, and at least one PM skill.
   - Expected: no user-visible command string is required.

2. `dev` instance receives `Implement the approved onboarding improvements in projects/app`.
   - Expected: `prepare` returns `active_buddy=dev`, not `pm`, and includes `implement-task`.

3. `pm` instance receives structural `switch pm: Draft the PRD`.
   - Expected: `prepare` returns `ok=false` or exits non-zero with legacy command input error.
   - Expected: no task object, artifact object, run audit, or reserved run is written.

4. `pm` instance receives natural text containing the word switch, for example `Explain how users can switch billing plans`.
   - Expected: request is treated as ordinary demand if it does not match structural routing syntax.

Anti-cheat rule:

- Do not satisfy this group by checking only error messages. Tests must inspect state writes or absence of writes.

### TG-02: Prepare-Turn Context Contract

**Requirement:** The current context contract is prepare-oriented, not resolve-oriented.

Cases:

1. Contract file exists at `framework/contracts/prepare-turn-context.json`.
   - Expected: `contract_id` is `prepare-turn-context`.
   - Expected: `response_key_order` matches actual `prepare` response key order.

2. Old contract file is absent.
   - Expected: `framework/contracts/resolve-context.json` does not exist.

3. Runtime response shape matches the contract.
   - Expected keys: `ok`, `context_revision`, `instance_id`, `active_buddy`, `request_text`, `current_task_id`, `current_track_id`, `task_context`, `track_context`, `skills`, `inputs_by_skill`, `run_envelope`, `warnings`.

4. Product docs and prompt assets do not use `resolve_context` as current product terminology.

Anti-cheat rule:

- Do not only rename the JSON file while leaving docs/tests/prompt language on `resolve_context`.

### TG-03: Persist Receipt Contract

**Requirement:** Persist returns stable runtime receipt metadata that can be rendered without parsing paths or command strings.

Artifact skill cases:

1. Persist a valid `write-prd` result.
   - Expected: top-level keys are `ok`, `receipt`, `refreshed_context`.
   - Expected receipt keys include `ok`, `skill_id`, `task_id`, `task_title`, `artifact_id`, `artifact_ids`, `run_id`, `next_state`, `receipt_paths`, `related_run_ids`.
   - Expected: `receipt.artifact_ids` contains `receipt.artifact_id`.
   - Expected: task, run, and artifact paths in `receipt.receipt_paths` exist.
   - Expected: `receipt.run_id` equals `prepare.run_envelope.run_id`.
   - Expected: `receipt.next_state.task_id` equals `receipt.task_id`.

2. Persist a valid `implement-task` result.
   - Expected: same receipt guarantees hold for a non-PM artifact skill.

Track-manager cases:

1. Persist a `track-manager` create operation.
   - Expected: receipt includes `track_id`, `track_title`, and `track_action=create`.
   - Expected: `artifact_ids` is an empty list.
   - Expected: terminal rendering can represent artifact as `none`.

2. Persist a `track-manager` update or advance operation against an existing track.
   - Expected: receipt reflects the track action and updated track state.

Forbidden receipt fields:

- `recommended_switch`
- `reference_switches`

Anti-cheat rule:

- Do not pass by constructing a fake receipt fixture. At least one test must use real `prepare` and real `persist` with actual state files.

### TG-04: Terminal Prompt Contract In Actual Buddy Instances

**Requirement:** The actual generated instance prompt must instruct the host to render a complete receipt.

Cases:

1. For each manifest buddy prompt asset:
   - Expected: contains `Receipt` and `Summary` section contract.
   - Expected: contains `Persisted: ok|failed`.
   - Expected: contains `Task: <task_title> [<task_id>]`.
   - Expected: contains `Artifact: <artifact_id|none>`.
   - Expected: contains `Run: <run_id>`.
   - Expected: contains `Related Runs`.
   - Expected: object paths are described as debug-only.

2. Start a launcher-managed `pm` instance with fake Codex capture.
   - Expected: generated workspace `AGENTS.md` equals `tools/launcher/assets/buddies/pm/AGENTS.md`.
   - Expected: generated `AGENTS.md` includes the complete receipt contract.

3. Start one non-PM instance, preferably `design` because it was missing contract markdown.
   - Expected: generated workspace `AGENTS.md` includes the same receipt contract and is locked to `design`.

Forbidden prompt content:

- `Receipt -> Commands -> Summary`
- `switch <buddy>`
- `switch pm:`
- `recommended_switch`
- `reference_switches`

Anti-cheat rule:

- Do not check only the source prompt asset. At least one launcher integration test must inspect the generated workspace file.

### TG-05: Runtime Prompt Source Simplification

**Requirement:** There is no stale generic runtime prompt competing with buddy prompt assets.

Cases:

1. `tools/launcher/assets/runtime-AGENTS.md` is absent.

2. Launcher product startup requires a buddy-specific template.
   - Expected: `instance start --buddy pm` succeeds.
   - Expected: malformed startup without a buddy fails before workspace mutation.

3. Generic workspace install without `BUDDYSWITCH_RUNTIME_AGENTS_TEMPLATE` fails clearly.

4. Active docs do not say `runtime-AGENTS.md` is the product prompt source.

Anti-cheat rule:

- Do not leave `runtime-AGENTS.md` in place with updated wording. The goal is to remove the competing active source.

### TG-06: Buddy Contract Coverage

**Requirement:** Every manifest buddy has equivalent current contract docs.

Cases:

1. Manifest-driven coverage:
   - Read `buddyswitch/manifest.toml`.
   - For each buddy id, assert `tools/launcher/assets/buddies/<buddy>/AGENTS.md` exists.
   - For each buddy id, assert `framework/contracts/<buddy>.md` exists.

2. `framework/contracts/design.md` exists and describes:
   - `shape-prototype` responsibility.
   - Artifact output boundary.
   - `Receipt -> Summary` terminal output.
   - `persist-skill-result` as runtime commit boundary.

3. Existing `pm`, `dev`, `market`, and `test` contracts remain aligned to current turn runtime naming.

Anti-cheat rule:

- Do not hard-code only the current five buddies in the test. It must derive buddy ids from the manifest.

### TG-07: Skill Schema Boundary

**Requirement:** Business output schema and runtime receipt schema stay separate.

Cases:

1. For every `framework/schemas/**.json`, top-level `properties` must not include runtime receipt keys:
   - `task_id`
   - `task_title`
   - `artifact_id`
   - `artifact_ids`
   - `run_id`
   - `receipt_paths`
   - `next_state`
   - `related_run_ids`

2. Every skill output schema still requires:
   - `execution_summary`
   - `working_notes`
   - `deliverables_or_changed_files`

3. Artifact-producing skill schemas require `artifact_content`.

4. Persisting a result with an extra top-level `task_id` fails schema validation and performs no state writes.

5. Persisting the same result without extra runtime metadata succeeds and returns `receipt.task_id`.

Anti-cheat rule:

- Do not weaken `additionalProperties: false` to make tests pass.

### TG-08: Old Router And Switch-Era Residue

**Requirement:** Old router/switch product paths are not active.

Cases:

1. `.codex/agents/router.toml` does not exist.

2. Active paths do not contain old product-flow terms:
   - `scripts/switch_runtime.py`
   - `switch_runtime`
   - `resolve_context`
   - `resolve-context`
   - `runtime-AGENTS.md`
   - `Receipt -> Commands -> Summary`
   - `recommended_switch`
   - `reference_switches`
   - `codex_router`
   - `parse_switch`
   - `switch <buddy>`
   - `switch pm:`

3. Guard tests may contain the forbidden terms only as forbidden-token strings.

4. Product runtime code does not import parser/router debug modules.

Anti-cheat rule:

- Do not satisfy the test by excluding active paths such as `tools`, `scripts`, `framework`, `README.md`, `AGENTS.md`, `.codex`, or `buddyswitch/manifest.toml`.

### TG-09: Workspace Projection And Console Contract

**Requirement:** UI and projections read structured state, not next-command strings.

Cases:

1. After a real persist, workspace projection includes run audit fields:
   - `run_id`
   - `task_id` or resolved task id equivalent
   - `task_title`
   - `artifact_ids`
   - `next_state`
   - `receipt_paths`
   - `related_run_ids`

2. Projection does not include:
   - `reference_switches`
   - `recommended_switch`

3. Console contract tests render next-step state from `next_state`.

4. Console does not derive buddy or task from command text.

Anti-cheat rule:

- Do not hide command strings in CSS or labels while preserving them in data.

### TG-10: Documentation Cleanup

**Requirement:** Current docs must not preserve old product contract guidance as searchable instructions.

Cases:

1. Obsolete migration plan and memo files listed in the implementation plan are deleted.

2. Active docs describe:
   - Product runtime loop: `prepare-turn-context -> host executes exactly one skill -> persist-skill-result`.
   - Buddy prompt source: `tools/launcher/assets/buddies/<buddy>/AGENTS.md`.
   - Receipt source: `persist` response `receipt`.

3. Active docs do not describe:
   - `runtime-AGENTS.md` as product prompt source.
   - `switch_runtime.py` as product runtime entry.
   - `receipt.recommended_switch` as follow-up mechanism.
   - `Receipt -> Commands -> Summary`.

4. Current cleanup plan and this test plan are allowed to mention old terms as historical evidence.

Anti-cheat rule:

- Do not move obsolete docs to another active searchable docs directory. If the content is no longer true, delete it.

## Required Commands

Targeted behavior and contract tests:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_turn_runtime.py \
  tests/test_turn_integration.py \
  tests/test_parallel_contracts.py \
  tests/test_buddyswitch_launcher.py \
  tests/test_repo_consistency.py \
  -q
```

Projection and console coverage:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_console_app_contract.py \
  tests/test_artifact_selection.py \
  -q
```

Full relevant regression:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_cleanup_system.py \
  tests/test_console_app_contract.py \
  tests/test_artifact_selection.py \
  tests/test_turn_runtime.py \
  tests/test_turn_integration.py \
  tests/test_parallel_contracts.py \
  tests/test_buddyswitch_launcher.py \
  tests/test_repo_consistency.py \
  -q
```

Final residue scan:

```bash
rg -n "scripts/switch_runtime.py|switch_runtime|resolve_context|resolve-context|runtime-AGENTS.md|Receipt -> Commands -> Summary|recommended_switch|reference_switches|codex_router|parse_switch|switch <buddy>|switch pm:" \
  README.md AGENTS.md .codex tools scripts framework tests buddyswitch/manifest.toml docs
```

Expected scan result:

- Only guard-test definitions and the current cleanup plan/test plan may mention old terms.
- Runtime, launcher, prompt assets, active product docs, contracts, and manifest must not contain old product-path guidance.

Syntax and diff hygiene:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile scripts/turn_runtime.py scripts/env_manifest.py scripts/output_schema.py scripts/runtime_store/projections.py
git diff --check
```

## Pass Criteria

- A real buddy instance can complete the prepare/persist path and return a receipt with stable task, artifact, run, and path metadata.
- The generated buddy workspace prompt tells the host to render the full receipt.
- No competing generic runtime prompt remains active.
- No old router/switch/resolve product path remains active.
- All manifest buddies have prompt and contract coverage.
- Skill output schemas remain business-output-only.
- Tests prove behavior through real runtime state where persistence is involved.
