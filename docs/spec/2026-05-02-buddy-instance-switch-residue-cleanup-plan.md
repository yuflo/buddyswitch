# Buddy Instance Switch Residue Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove historical `switch` wire syntax and parser residue from active buddy instance product sessions so ordinary product turns are the only supported user-facing workflow.

**Architecture:** Replace the product runtime entrypoint wording and code boundary with a turn-oriented contract: `prepare-turn-context -> host executes exactly one skill -> persist-skill-result`. Delete historical routing/parser code from product runtime instead of hiding it behind compatibility shims. If legacy internal wire material must remain for archaeology, it must be outside active launcher/runtime/prompt/manifest paths and excluded from product tests.

**Tech Stack:** Python runtime scripts and pytest/unittest suites, Bash launcher assets, Markdown prompt/docs assets, static Context Panel contract checks.

---

## Target Outcome

In a launcher-managed buddy instance:

```bash
./buddyswitch-codex instance start --buddy pm
```

The user enters only ordinary product requests:

```text
Draft the MVP PRD for onboarding rewrite
```

The session must not display, require, route, recommend, or internally construct historical `switch <buddy>...:` text. A command-shaped legacy input must fail closed before state mutation with guidance to use a plain request. Natural language containing the word "switch" remains valid when it is not the legacy structural form.

## Current Confirmed Residue

- `tools/launcher/assets/buddies/*/AGENTS.md` still tells the host that structural `switch <buddy>...:` commands exist as internal/debug wire input.
- `tools/launcher/assets/runtime-AGENTS.md` still includes canonical `switch <buddy>(<task-id>) -> <track-id>: <demand>` syntax and `Switch Rules`.
- `scripts/switch_runtime.py` still defines `WIRE_SYNTAX`, `_STRUCTURAL_SWITCH_PATTERN`, and `_parse_wire_switch()`.
- `buddyswitch/manifest.toml` still registers `scripts/debug/codex_router.py` as a debug adapter for `switch <buddy>...: <demand>`.
- `framework/docs/switch-spec.md`, `framework/contracts/switch-grammar.json`, `scripts/debug/parse_switch.py`, and `scripts/debug/codex_router.py` still preserve the historical wire contract.

## Cleanup Boundary

### In Scope

- Active buddy instance prompts.
- Runtime entrypoint used by buddy instances.
- Manifest entries loaded by active runtime.
- Product docs and active framework docs.
- Context Panel and projection guardrails.
- Tests that define product behavior and prevent reintroduction.

### Out Of Scope

- Renaming the product name `BuddySwitch`.
- Editing old dated execution plans only to remove historical references.
- Building compatibility shims for old wire syntax.
- Adding workflow engines, routers, DAGs, or multi-skill orchestration.

## File Responsibility Map

- Create: `scripts/turn_runtime.py`
  - Canonical product runtime CLI for `prepare` and `persist`.
  - Contains product turn context preparation and persistence only.
  - Must not define structural wire syntax, parser regexes, or legacy routing helpers.

- Delete: `scripts/switch_runtime.py`
  - Remove after all active imports, tests, docs, prompts, and launcher calls use `scripts/turn_runtime.py`.
  - Do not leave a compatibility shim unless a test proves an external active product caller still needs it; default is delete.

- Delete: `scripts/debug/parse_switch.py`
  - Historical parser is not part of active product runtime.

- Delete: `scripts/debug/codex_router.py`
  - Historical router is not part of active product runtime.

- Modify: `buddyswitch/manifest.toml`
  - Remove `[[adapters]]` entry for `scripts/debug/codex_router.py`.
  - Keep buddies and skills as the active capability source.

- Modify: `tools/launcher/assets/buddies/{pm,dev,market,design,test}/AGENTS.md`
  - Remove every structural wire reference.
  - Keep only ordinary request, locked buddy, one skill, persist, and summary guidance.

- Modify: `tools/launcher/assets/runtime-AGENTS.md`
  - Remove canonical wire examples and `Switch Rules`.
  - Describe product runtime workspace behavior using turn context vocabulary only.

- Modify: `tools/launcher/workspace.sh`, `buddyswitch-codex`, and launcher tests as needed
  - Ensure generated instance `AGENTS.md` comes from the cleaned buddy template.
  - Ensure runtime examples and prompt-input tests use ordinary product requests.

- Modify: `scripts/runtime_kernel/resolve.py`, `scripts/runtime_kernel/persist.py`
  - Point runtime-kernel callers to turn-oriented APIs.
  - Remove references to switch routing semantics.

- Modify/Rename: `tests/test_switch_runtime.py` -> `tests/test_turn_runtime.py`
  - Product runtime tests should not carry historical names.

- Modify/Rename: `tests/test_switch_integration.py` -> `tests/test_turn_integration.py`
  - Integration tests should describe product turn behavior.

- Modify: `tests/test_parallel_contracts.py`
  - Update contract references to turn context and persist result.

- Modify: `tests/test_buddyswitch_launcher.py`
  - Replace prompt-input fixtures using legacy wire text with ordinary request text.

- Modify: `tests/test_repo_consistency.py`
  - Add active-path guardrails that reject standalone `switch` wire references in product runtime, launcher assets, product docs, manifest adapters, and Context Panel code.

- Delete/Replace: `framework/docs/switch-spec.md`
  - Replace with `framework/docs/turn-runtime-spec.md` if a runtime spec is still needed.

- Delete: `framework/contracts/switch-grammar.json`
  - Historical grammar is not an active product contract.

- Modify: `README.md`, `framework/docs/architecture-overview.md`, `framework/docs/skill-architecture-best-practices.md`, `framework/agent-registry.md`
  - Remove active guidance that teaches, documents, or registers historical wire syntax.

## Execution Tasks

### Task 1: Define Product Cleanliness Guardrails First

**Files:**
- Modify: `tests/test_repo_consistency.py`
- Test: `tests/test_repo_consistency.py`

- [ ] **Step 1: Add active-path forbidden token test**

Add a test that scans only active product paths, not historical dated plans:

```python
def test_active_product_paths_do_not_contain_legacy_switch_wire(self) -> None:
    active_paths = [
        ROOT / "tools" / "launcher" / "assets",
        ROOT / "scripts",
        ROOT / "buddyswitch" / "manifest.toml",
        ROOT / "README.md",
        ROOT / "framework" / "docs",
        ROOT / "framework" / "contracts",
        ROOT / "framework" / "console",
    ]
    allowed_files = {
        ROOT / "tests" / "test_repo_consistency.py",
    }
    forbidden_patterns = (
        r"switch\s+<buddy>",
        r"switch\s+[a-z][a-z0-9-]*\s*:",
        r"_parse_wire_switch",
        r"_STRUCTURAL_SWITCH_PATTERN",
        r"WIRE_SYNTAX",
        r"switch-grammar",
        r"codex_router\.py",
        r"parse_switch\.py",
    )
```

Use `re.search(pattern, text, re.IGNORECASE)` and fail with the exact path plus matching pattern. Exclude generated caches and this guardrail test itself.

- [ ] **Step 2: Run the guardrail and verify it fails on current residue**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_repo_consistency.py::RepoConsistencyTests::test_active_product_paths_do_not_contain_legacy_switch_wire -q
```

Expected: FAIL listing current active residue in launcher assets, runtime script, manifest, and framework docs/contracts.

- [ ] **Step 3: Do not weaken the guardrail**

Keep the allowlist narrow. Do not allow active prompt files, runtime files, manifest, or product docs to bypass the test.

### Task 2: Move Product Runtime To Turn Runtime And Remove Wire Parser

**Files:**
- Create: `scripts/turn_runtime.py`
- Delete: `scripts/switch_runtime.py`
- Modify: `scripts/runtime_kernel/resolve.py`
- Modify: `scripts/runtime_kernel/persist.py`
- Rename/Modify: `tests/test_switch_runtime.py` -> `tests/test_turn_runtime.py`
- Rename/Modify: `tests/test_switch_integration.py` -> `tests/test_turn_integration.py`

- [ ] **Step 1: Rename tests before implementation**

Rename product runtime tests so new work is not expressed through the old concept:

```bash
git mv tests/test_switch_runtime.py tests/test_turn_runtime.py
git mv tests/test_switch_integration.py tests/test_turn_integration.py
```

Then update imports from `switch_runtime` to `turn_runtime`.

- [ ] **Step 2: Create `scripts/turn_runtime.py` from the current product path**

Move the existing product-mode context preparation and persist logic into `scripts/turn_runtime.py`. Keep only:

- product session loading from `BUDDYSWITCH_ACTIVE_BUDDY`, `BUDDYSWITCH_INSTANCE_ID`, `BUDDYSWITCH_INSTANCE_JSON`
- task/track/artifact/run state helpers
- `prepare` command for turn context
- `persist` command for skill result persistence
- structured receipt and refreshed context behavior

Delete from the new file:

- `WIRE_SYNTAX`
- `WIRE_EXAMPLE`
- `_STRUCTURAL_SWITCH_PATTERN`
- `_parse_wire_switch`
- non-product fallback that requires historical wire syntax

- [ ] **Step 3: Add command-shaped legacy input rejection without routing**

In product mode, reject exact legacy command-shaped input before creating tasks or reservations. The check is a fail-closed input guard, not a router. It must not extract buddy/task/track for execution.

Behavior:

- `"switch pm: Draft PRD"` -> error, no writes
- `"switch dev(task-a) -> track-b: Implement"` -> error, no writes
- `"Help users switch plans without losing data"` -> accepted

Error message must say the buddy instance accepts ordinary requests, not structural commands.

- [ ] **Step 4: Delete `scripts/switch_runtime.py`**

After active references are migrated, delete the old file:

```bash
git rm scripts/switch_runtime.py
```

Do not leave a shim. Any failing active test must be updated to the turn runtime contract instead of reintroducing the old name.

- [ ] **Step 5: Run focused runtime tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_turn_runtime.py -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_turn_integration.py -q
```

Expected: PASS. Runtime tests must prove ordinary request success, command-shaped rejection with no writes, natural-language "switch" acceptance, exactly-one-skill persist, and structured receipt.

### Task 3: Remove Debug Wire Adapter From Active Runtime

**Files:**
- Delete: `scripts/debug/parse_switch.py`
- Delete: `scripts/debug/codex_router.py`
- Modify: `buddyswitch/manifest.toml`
- Modify/Delete: `tests/test_switch_routing.py`
- Modify: `tests/test_env_manifest_v2.py`

- [ ] **Step 1: Remove manifest adapter**

Delete the `[[adapters]]` block from `buddyswitch/manifest.toml`:

```toml
[[adapters]]
id = "codex"
path = "scripts/debug/codex_router.py"
description = "Debug-only adapter for internal `switch <buddy>...: <demand>` wire parsing/routing with env-backed buddy scope, skills, and object permissions."
```

The manifest should define environment, skills, buddies, and permissions only.

- [ ] **Step 2: Delete debug parser/router files**

Run:

```bash
git rm scripts/debug/parse_switch.py scripts/debug/codex_router.py
```

- [ ] **Step 3: Remove parser/router tests**

Delete `tests/test_switch_routing.py` if its only purpose is preserving debug parser/router isolation. In `tests/test_env_manifest_v2.py`, replace adapter expectations with manifest tests that prove active runtime uses buddies and skills, not adapters.

- [ ] **Step 4: Run manifest tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_env_manifest_v2.py tests/test_repo_consistency.py -q
```

Expected: PASS. No active manifest adapter references remain.

### Task 4: Clean Active Buddy Instance Prompts

**Files:**
- Modify: `tools/launcher/assets/buddies/pm/AGENTS.md`
- Modify: `tools/launcher/assets/buddies/dev/AGENTS.md`
- Modify: `tools/launcher/assets/buddies/market/AGENTS.md`
- Modify: `tools/launcher/assets/buddies/design/AGENTS.md`
- Modify: `tools/launcher/assets/buddies/test/AGENTS.md`
- Modify: `tools/launcher/assets/runtime-AGENTS.md`
- Modify: `tests/test_repo_consistency.py`

- [ ] **Step 1: Remove structural command wording from buddy templates**

Each buddy template should contain:

- locked buddy identity
- ordinary request ownership
- canonical loop using `scripts/turn_runtime.py prepare`
- exactly one skill execution
- `scripts/turn_runtime.py persist`
- `Receipt -> Summary`

Each buddy template must not contain structural command examples, historical wire vocabulary, parser vocabulary, or debug adapter vocabulary.

- [ ] **Step 2: Remove generic runtime `Switch Rules`**

In `tools/launcher/assets/runtime-AGENTS.md`, delete the canonical wire block and the `Switch Rules` section. Replace `scripts/switch_runtime.py resolve` with `scripts/turn_runtime.py prepare`.

- [ ] **Step 3: Verify an actual generated instance prompt**

Start or open a disposable instance and inspect its generated root `AGENTS.md`:

```bash
./buddyswitch-codex instance start --buddy pm debug prompt-input "Draft the onboarding PRD"
```

Then inspect the instance workspace printed by launcher:

```bash
rg -n "switch\\s+<buddy>|switch\\s+[a-z][a-z0-9-]*\\s*:|parse_switch|codex_router|wire syntax" <instance-workspace>/AGENTS.md -S
```

Expected: no matches.

### Task 5: Replace Product Docs And Contracts

**Files:**
- Delete: `framework/docs/switch-spec.md`
- Delete: `framework/contracts/switch-grammar.json`
- Create: `framework/docs/turn-runtime-spec.md`
- Modify: `README.md`
- Modify: `framework/docs/architecture-overview.md`
- Modify: `framework/docs/skill-architecture-best-practices.md`
- Modify: `framework/agent-registry.md`
- Modify: `tests/test_repo_consistency.py`

- [ ] **Step 1: Delete historical wire spec and grammar**

Run:

```bash
git rm framework/docs/switch-spec.md framework/contracts/switch-grammar.json
```

- [ ] **Step 2: Add `turn-runtime-spec.md`**

Document only:

- product-mode ordinary request contract
- `prepare-turn-context`
- host exactly-one-skill execution
- `persist-skill-result`
- structured receipt
- Context Panel projection source

Do not include historical wire examples.

- [ ] **Step 3: Update README and framework docs**

Replace active usage examples with:

```text
Draft the MVP PRD for onboarding rewrite
```

Do not include command-shaped routing examples.

- [ ] **Step 4: Run docs guardrails**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_repo_consistency.py -q
```

Expected: PASS. Active docs contain turn runtime vocabulary and no historical wire examples.

### Task 6: Keep Projection And Console Structurally Clean

**Files:**
- Modify: `scripts/runtime_store/projections.py`
- Modify: `framework/contracts/workspace-projection.json`
- Modify: `framework/console/app.js`
- Modify: `framework/console/index.html`
- Modify: `tests/test_console_app_contract.py`
- Modify: `tests/test_parallel_contracts.py`

- [ ] **Step 1: Confirm no command-derived next-step fields**

Search:

```bash
rg -n "recommended_switch|reference_switches|switchBuddyId|SWITCH_BUDDY_PATTERN|deriveRecommendedSwitch" scripts/runtime_store framework/console framework/contracts tests -S
```

Expected before cleanup: no active product matches except old tests that will be removed or renamed.

- [ ] **Step 2: Strengthen tests around structured state**

Tests must assert next-step display uses structured fields such as `next_state`, `task_id`, `track_id`, `active_buddy`, `skill_id`, `receipt_paths`, and `run_id`.

- [ ] **Step 3: Run console and contract tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_console_app_contract.py tests/test_parallel_contracts.py -q
```

Expected: PASS. No UI logic parses command text to infer product state.

### Task 7: Full Verification And Manual Product Acceptance

**Files:**
- Modify only if verification exposes missed active residue.

- [ ] **Step 1: Run full targeted suite**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_turn_runtime.py \
  tests/test_turn_integration.py \
  tests/test_buddyswitch_launcher.py \
  tests/test_console_app_contract.py \
  tests/test_parallel_contracts.py \
  tests/test_repo_consistency.py \
  tests/test_env_manifest_v2.py \
  -q
```

Expected: PASS.

- [ ] **Step 2: Run active-path residue scan**

Run:

```bash
rg -n "\\bswitch\\s+<buddy>|\\bswitch\\s+[a-z][a-z0-9-]*\\s*:|_parse_wire_switch|_STRUCTURAL_SWITCH_PATTERN|WIRE_SYNTAX|switch-grammar|parse_switch\\.py|codex_router\\.py" \
  tools/launcher/assets scripts buddyswitch/manifest.toml README.md framework/docs framework/contracts framework/console tests \
  -S
```

Expected: no matches, except this cleanup plan if included by a broader docs search. `BuddySwitch` as the product name is not a violation.

- [ ] **Step 3: Manual product smoke**

Start a fresh buddy instance and enter:

```text
Draft the MVP PRD for onboarding rewrite
```

Expected:

- no product prompt or terminal instruction asks for historical command syntax
- exactly one skill is selected and persisted
- `Receipt -> Summary` is shown
- Context Panel launched from the instance workspace shows the new task/artifact/run audit

- [ ] **Step 4: Manual negative smoke**

In a fresh buddy instance, enter:

```text
switch dev: Draft onboarding PRD
```

Expected:

- fail closed before creating task/artifact/run audit
- message says this buddy instance accepts ordinary requests
- current active buddy is not changed
- no state files are written for that rejected input

## Final Acceptance Criteria

- Active buddy instance prompts contain no structural wire syntax or debug parser guidance.
- Product runtime no longer contains historical parser/regex/wire constants.
- Active manifest no longer registers a historical debug router adapter.
- Product docs and contracts describe turn runtime, not switch wire.
- Command-shaped legacy input cannot route work or mutate state.
- Natural language containing the word "switch" remains valid.
- Full targeted suite and manual product smoke pass.
- `git status --short` shows only intentional cleanup changes.
