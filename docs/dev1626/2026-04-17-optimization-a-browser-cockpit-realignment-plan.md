# BuddySwitch Browser Cockpit Realignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the market-branded launcher/browser infrastructure with infra-centric browser cockpit naming, and make `./buddyswitch-codex start` the single happy-path bootstrap for the full BuddySwitch Codex environment.

**Architecture:** Keep `buddyswitch-codex` as the only user-facing entrypoint. Split launcher internals under `tools/launcher/`, rename the shared headed browser stack from `market` to `browser`/`cockpit` terminology everywhere that affects current behavior, and make `start` idempotently prepare both browser capabilities before launching Codex: the general `chrome-devtools` MCP and the shared-profile cockpit MCP. Keep manual browser commands only for diagnostics and repair.

**Tech Stack:** Bash, existing `codex` CLI, Chrome remote debugging, `npx chrome-devtools-mcp@latest`, Python runtime metadata validation, `pytest`.

---

## Problem Statement

The first-round launcher migration moved Chrome setup into `buddyswitch-codex`, but it still has two product problems:

1. The happy path is fragmented. Users still have to remember `market ensure` and `market install-mcp` before `start`.
2. The browser infrastructure is named after the `market` buddy even though the capability is generic: one normal browser MCP plus one shared-profile cockpit browser MCP. This leaks historical baggage into CLI, docs, tests, and runtime metadata.

The next iteration should fix both at once. Mixing public rename now and internal rename later will leave stale search hits, stale docs, and easy-to-repeat mistakes.

## Decision Summary

### Recommended approach

Adopt one infra-centric naming system and apply it across launcher UX, runtime metadata, tests, and active docs in the same change.

- Product CLI namespace becomes `browser`, not `market`.
- `start` becomes the full bootstrap path.
- The shared-profile headed browser MCP is renamed from `chrome-devtools-market` to `chrome-devtools-cockpit`.
- The shared profile is renamed from `shared-market` to `shared-browser`.
- Market remains a buddy/domain concept, but browser cockpit stops being market-branded infrastructure.

### Rejected approaches

1. Rename only the launcher CLI and keep internal `market` runtime names.
   Reject because it keeps stale grep hits and mental overhead.

2. Keep separate manual MCP install commands in the main workflow.
   Reject because launcher startup should prepare the full working environment.

3. Collapse the normal browser and shared cockpit browser into one MCP identity.
   Reject for now because BuddySwitch still needs both modes:
   - a normal `chrome-devtools` MCP
   - a dedicated shared-profile headed cockpit MCP

## Canonical Naming After This Change

### Product-facing launcher surface

- `buddyswitch-codex start`
- `buddyswitch-codex reset --yes`
- `buddyswitch-codex browser status`
- `buddyswitch-codex browser ensure`
- `buddyswitch-codex help`

`browser ensure` is a manual repair/bootstrap command. `browser status` is read-only. There is no separate `install-mcp` command in the happy path after this redesign.

### Runtime/browser terminology

- General browser MCP: `chrome-devtools`
- Shared cockpit MCP: `chrome-devtools-cockpit`
- Shared cockpit profile: `shared-browser`
- Shared cockpit execution mode: `browser-cockpit-native`
- Session continuity token: `shared-cockpit`

### Environment variable naming

- `BUDDYSWITCH_BROWSER_PORT`
- `BUDDYSWITCH_BROWSER_PROFILE_DIR`
- `BUDDYSWITCH_BROWSER_LOG_FILE`
- `BUDDYSWITCH_BROWSER_COCKPIT_MCP_NAME`
- `BUDDYSWITCH_BROWSER_CHROME_BIN`

The existing `BUDDYSWITCH_SHARED_ROOT`, `BUDDYSWITCH_HOME`, and `BUDDYSWITCH_CODEX_HOME` remain valid because they are launcher-scoped rather than browser-mode-scoped.

## File Structure

**Create**
- `tools/launcher/browser_cockpit.sh`
- `tests/test_browser_cockpit_launcher.py`

**Modify**
- `buddyswitch-codex`
- `tools/launcher/env.sh`
- `scripts/env_manifest.py`
- `scripts/switch_runtime.py`
- `framework/contracts/market.md`
- `framework/docs/switch-spec.md`
- `framework/templates/research-report.md`
- `README.md`
- `tests/test_buddyswitch_launcher.py`
- `tests/test_repo_consistency.py`
- `tests/test_switch_runtime.py`
- `tests/test_env_manifest_v2.py`
- `tests/test_output_schema_boundaries.py`
- all six `buddyswitch/skills/market/*/skill.toml`
- all six `buddyswitch/skills/market/*/SKILL.md`
- `docs/dev0220/market-chrome-mcp-phase1-manual-checklist.md`
- `docs/dev0220/2026-04-17-market-chrome-mcp-phase1-implementation-plan.md`
- `docs/dev1626/2026-04-17-launcher-market-cockpit-migration-plan.md`

**Rename / Replace**
- `tools/launcher/market_cockpit.sh` -> `tools/launcher/browser_cockpit.sh`
- `tests/test_market_cockpit_launcher.py` -> `tests/test_browser_cockpit_launcher.py`
- `framework/docs/market-research-cockpit.md` -> `framework/docs/browser-cockpit.md`

**Delete**
- market-branded launcher helper/test paths once their browser replacements exist

## Scope Boundaries

### In scope

- Product CLI rename from `market` to `browser`
- Full `start` bootstrap
- Runtime metadata rename from market-branded browser infra to cockpit-branded browser infra
- Market skill contract updates where they reference shared browser infrastructure
- Repo-wide cleanup of active docs/tests so current grep results are consistent

### Out of scope

- Renaming the `market` buddy itself
- Changing BuddySwitch object authority or switch syntax
- Replacing the shared cockpit model with a headless-only model
- Reworking non-browser buddies

## Implementation Tasks

### Task 1: Replace product-facing `market` launcher commands with `browser`

**Files:**
- Modify: `buddyswitch-codex`
- Create: `tools/launcher/browser_cockpit.sh`
- Delete: `tools/launcher/market_cockpit.sh`
- Create: `tests/test_browser_cockpit_launcher.py`
- Delete: `tests/test_market_cockpit_launcher.py`

- [ ] Change launcher help text and command dispatch from `market` to `browser`.
- [ ] Rename browser helper functions and environment variables to the new `BUDDYSWITCH_BROWSER_*` namespace.
- [ ] Rename the shared profile/log defaults from `shared-market` and `chrome-market.log` to `shared-browser` and `chrome-cockpit.log`.
- [ ] Rename the dedicated shared MCP identity from `chrome-devtools-market` to `chrome-devtools-cockpit`.
- [ ] Replace the launcher test module with `tests/test_browser_cockpit_launcher.py` and remove the market-branded test path.
- [ ] Add a regression test that `./buddyswitch-codex browser status` is read-only and does not create `~/.codex-buddyswitch`.

**Verification:**
- `python3 -m pytest tests/test_buddyswitch_launcher.py tests/test_browser_cockpit_launcher.py -v`

### Task 2: Make `start` the full bootstrap happy path

**Files:**
- Modify: `buddyswitch-codex`
- Modify: `tools/launcher/env.sh`
- Modify: `tools/launcher/browser_cockpit.sh`
- Modify: `tests/test_buddyswitch_launcher.py`
- Modify: `tests/test_browser_cockpit_launcher.py`

- [ ] Add one shared bootstrap function that:
  - ensures BuddySwitch shared directories/config exist
  - ensures `chrome-devtools` is registered in BuddySwitch `CODEX_HOME`
  - ensures the shared cockpit Chrome endpoint is reachable
  - ensures `chrome-devtools-cockpit` is registered in BuddySwitch `CODEX_HOME`
- [ ] Call that bootstrap function from `buddyswitch-codex start` before launching `codex`.
- [ ] Make `buddyswitch-codex browser ensure` call the same bootstrap function without launching `codex`.
- [ ] Remove the separate `browser install-mcp` command from the product CLI.
- [ ] Keep `browser status` purely diagnostic.
- [ ] Ensure MCP registration is idempotent and does not rely on the user remembering a separate command after reset.

**Verification:**
- `python3 -m pytest tests/test_buddyswitch_launcher.py tests/test_browser_cockpit_launcher.py -v`
- Manual smoke: `./buddyswitch-codex start` should prepare the browser stack without any prior browser subcommand.

### Task 3: Rename runtime metadata and market cockpit contract together

**Files:**
- Modify: `scripts/env_manifest.py`
- Modify: `scripts/switch_runtime.py`
- Modify: `framework/contracts/market.md`
- Rename: `framework/docs/market-research-cockpit.md` -> `framework/docs/browser-cockpit.md`
- Modify: `tests/test_repo_consistency.py`
- Modify: `tests/test_switch_runtime.py`
- Modify: `tests/test_env_manifest_v2.py`
- Modify: `tests/test_output_schema_boundaries.py`
- Modify: all six `buddyswitch/skills/market/*/skill.toml`
- Modify: all six `buddyswitch/skills/market/*/SKILL.md`

- [ ] Change the host execution contract from:
  - `execution_mode = "market-browser-native"`
  - `browser_profile = "shared-market"`
  - `browser_executor = "chrome-devtools-market"`
  to:
  - `execution_mode = "browser-cockpit-native"`
  - `browser_profile = "shared-browser"`
  - `browser_executor = "chrome-devtools-cockpit"`
- [ ] Update `switch_runtime` execution steps so they instruct the host to use `chrome-devtools-cockpit` instead of `chrome-devtools-market`.
- [ ] Keep `discovery_mode = "browser-native"` and `session_continuity = "shared-cockpit"` unless implementation work proves a better neutral term is needed.
- [ ] Update market contract docs so they describe market as the consumer of the browser cockpit, not the owner of the infrastructure naming.
- [ ] Add/adjust repo consistency checks so active files no longer regress back to `buddyswitch-codex market ...`, `chrome-devtools-market`, or `shared-market`.

**Verification:**
- `python3 -m pytest tests/test_repo_consistency.py tests/test_switch_runtime.py tests/test_env_manifest_v2.py tests/test_output_schema_boundaries.py -v`
- `rg -n "buddyswitch-codex market|chrome-devtools-market|shared-market|market-browser-native" README.md framework buddyswitch tests tools`

### Task 4: Clean active docs and remove stale mental traps

**Files:**
- Modify: `README.md`
- Modify: `framework/docs/switch-spec.md`
- Modify: `framework/templates/research-report.md`
- Modify: `docs/dev0220/market-chrome-mcp-phase1-manual-checklist.md`
- Modify: `docs/dev0220/2026-04-17-market-chrome-mcp-phase1-implementation-plan.md`
- Modify: `docs/dev1626/2026-04-17-launcher-market-cockpit-migration-plan.md`

- [ ] Rewrite launcher setup docs so `start` is the main path and `browser status` / `browser ensure` are repair tools.
- [ ] Replace active `market` launcher examples with `browser` examples.
- [ ] Update old dev planning docs that still show the earlier launcher flow so repo search no longer suggests the wrong commands.
- [ ] Mark the first-round dev1626 launcher plan as superseded by Optimization A so the repo has one current recommendation.

**Verification:**
- `rg -n "market status|market ensure|market install-mcp" README.md docs framework`
- `python3 -m pytest tests/test_repo_consistency.py -v`

### Task 5: Re-run end-to-end launcher smoke flows

**Files:**
- Modify only if fixes are needed after smoke verification

- [ ] Verify `./buddyswitch-codex browser status` before bootstrap does not create `~/.codex-buddyswitch`.
- [ ] Verify `./buddyswitch-codex start` from a clean state:
  - creates the shared BuddySwitch home
  - ensures both MCP registrations in BuddySwitch `CODEX_HOME`
  - ensures the shared cockpit browser is reachable
  - enters Codex successfully
- [ ] Verify a second `./buddyswitch-codex start` shares the same BuddySwitch home/session store.
- [ ] Verify `reset --yes` still blocks when a launcher session is active.
- [ ] Verify `reset --yes` still blocks when the shared browser cockpit is active.
- [ ] Verify reset succeeds only after launcher sessions and cockpit browser are gone.

**Verification:**
- Manual smoke commands recorded in the implementation PR/notes after execution

## Acceptance Criteria

- Users can launch BuddySwitch through `./buddyswitch-codex start` without any pre-step to install browser MCPs or start the shared cockpit browser.
- Product-facing CLI no longer uses the `market` namespace for browser infrastructure.
- Runtime host execution metadata no longer uses market-branded browser naming.
- Repo-wide active docs/tests no longer teach the old `market` browser commands.
- Reset behavior remains safe with shared launcher state and shared browser cockpit state.

## Risks And Mitigations

- **Risk:** Partial rename leaves mixed terms in tests and docs.
  **Mitigation:** Add repo consistency assertions and a mandatory grep sweep for legacy terms.

- **Risk:** `start` becomes too heavy and hides failures.
  **Mitigation:** Keep `browser status` and `browser ensure` as explicit repair paths with precise error output.

- **Risk:** General browser MCP and cockpit browser MCP bootstrap logic diverge.
  **Mitigation:** Centralize both under one bootstrap function and test both registration states together.

- **Risk:** Historical dev docs reintroduce the wrong commands through search.
  **Mitigation:** Update or supersede them in the same change rather than leaving them untouched.

## Plan Status

This plan supersedes the first-round launcher/browser migration plan in `docs/dev1626/2026-04-17-launcher-market-cockpit-migration-plan.md` for the next implementation batch.
