# Browser Cockpit Ready Gate Development Plan

> **For agentic workers:** implement this plan from `/Users/chen/Dev/buddyswitch/.worktrees/dev0210`. Use `superpowers:test-driven-development` before code changes and `superpowers:verification-before-completion` before claiming completion. Track progress with the checklist below.

**Goal:** Ensure launcher-managed buddy instances expose Codex only after the instance browser cockpit is an MCP-usable browser window, so codex-cli can call runtime and browser tools without judging Chrome first-run or DevTools target state.

**Current bottleneck:** Browser readiness currently means `/json/version` is reachable. That lets a fresh Chrome profile stop at `chrome://intro/`, which `chrome-devtools-mcp` filters out and then reports `Error: No page selected`.

**Architecture:** Move the browser usability guarantee into the launcher/runtime readiness gate. Keep codex-cli host behavior unchanged: it calls `prepare`, `browser_evidence`, `chrome-devtools-cockpit`, and `persist`. Do not add business-specific prompt guidance to `AGENTS.md` or market skills.

---

## Working Directory

Run every command from:

```bash
cd /Users/chen/Dev/buddyswitch/.worktrees/dev0210
```

Do not edit the main checkout at `/Users/chen/Dev/buddyswitch`.

Existing unrelated worktree state must be preserved. At plan creation time, these files already had unrelated changes and must not be reverted as part of this work:

```text
.codex/config.toml
framework/contracts/prepare-turn-context.json
framework/docs/turn-runtime-spec.md
scripts/turn_runtime.py
tests/test_buddy_env_sandbox.py
tests/test_parallel_contracts.py
tests/test_prepare_runtime_context.py
tests/test_repo_consistency.py
tests/test_runtime_tool_feedback.py
docs/memo/2026-05-08-buddy-host-desc-feedback-consensus-memo.md
docs/spec/2026-05-09-buddy-host-desc-feedback-development-plan.md
docs/spec/2026-05-09-buddy-host-desc-feedback-test-plan.md
```

## Source Decision

This plan implements the converged browser-cockpit decision:

- `instance start` and `instance open` must prepare browser readiness before launching codex-cli.
- codex-cli must not learn how to detect or repair Chrome first-run, `/json/new` verbs, selected page state, or MCP target filtering.
- All existing instances will be deleted before retest. Do not add old-instance migration, compatibility markers, or transition logic.
- Old endpoint-only readiness wording and tests should be replaced, not preserved as a parallel path.

## Confirmed Facts

- `buddyswitch-codex::start_locked_bootstrap()` calls `buddyswitch_browser_bootstrap` before `buddyswitch_run_codex`.
- `buddyswitch-codex::instance_open_locked_bootstrap()` also calls `buddyswitch_browser_bootstrap` before `buddyswitch_run_codex`.
- `tools/launcher/browser_cockpit.sh::buddyswitch_browser_ensure_cockpit_endpoint()` currently launches Chrome with only `--remote-debugging-port` and `--user-data-dir`.
- `tools/launcher/browser_cockpit.sh::buddyswitch_browser_check_endpoint()` currently checks only `/json/version`.
- `scripts/runtime_kernel/broker.py::_require_browser_endpoint()` currently checks only `/json/version` before issuing `browser-cockpit-preflight` evidence.
- `chrome-devtools-mcp` filters out most `chrome://` targets. A browser whose only page is `chrome://intro/` can therefore have a reachable endpoint but no MCP-selected page.

## Target Runtime Contract

The new contract is:

```text
instance start/open
-> launcher prepares workspace, codex-home, runtime broker, MCP config
-> launcher ensures browser cockpit ready page
-> launcher starts codex-cli
-> user enters task
-> codex-cli calls prepare, browser_evidence, chrome-devtools-cockpit, persist
```

`browser cockpit ready page` means all of the following are true:

1. `http://127.0.0.1:<port>/json/version` returns HTTP 2xx.
2. `http://127.0.0.1:<port>/json/list` returns at least one usable page target.
3. A usable page target has `type == "page"` and a URL that `chrome-devtools-mcp` can select. `about:blank` is the canonical ready page.
4. A page list containing only `chrome://intro/`, `chrome://signin`, `chrome://welcome`, `chrome-untrusted://blocked`, or `devtools://devtools/bundled/inspector.html` is not ready.
5. If no usable page exists, the launcher/runtime creates `about:blank` with `PUT /json/new?about:blank` and verifies it appears in `/json/list`.

For browser-required buddies, a failed ready page gate blocks codex-cli launch. For browser-available buddies, the launcher may continue with a warning only if the browser cannot be made ready; however, any browser reported as ready must satisfy the same ready page definition.

## Non-Goals

- Do not change codex-cli host behavior or require new host-side browser decision logic.
- Do not add market-specific, landing-page-specific, or browser-debug-specific prompt text to runtime `AGENTS.md` or market `SKILL.md`.
- Do not preserve endpoint-only readiness as a supported public mode.
- Do not add a generic browser orchestration framework.
- Do not migrate existing browser profiles or instance records.
- Do not add silent fallback to ordinary web search when market browser-native work is required.

## Files And Responsibilities

Modify these files:

- `tools/launcher/browser_cockpit.sh`
  - Owns Chrome launch flags, CDP endpoint probing, page creation, and launcher-side ready gate.
  - Public `env browser status|ensure` behavior should reflect browser ready page, not only endpoint reachability.
- `scripts/runtime_kernel/broker.py`
  - Owns broker-issued `browser-cockpit-preflight` evidence readiness.
  - Must not issue a browser token unless the active browser has a usable page.
- `framework/docs/browser-cockpit.md`
  - Update the contract from endpoint availability to ready page availability.
- `tests/test_browser_cockpit_launcher.py`
  - Add direct CLI tests for `env browser ensure/status`.
- `tests/test_buddyswitch_launcher.py`
  - Add start/open tests proving codex-cli is gated on browser readiness.
- `tests/test_market_browser_evidence.py`
  - Add market evidence tests proving browser token issuance requires usable page readiness.
- `tests/test_runtime_tool_feedback.py`
  - Add structured feedback tests for browser preflight failure.
- `tests/test_turn_integration.py`
  - Add one integration-style broker flow to prevent endpoint-only regressions.
- `tests/test_repo_consistency.py`
  - Add drift guard that public docs do not describe browser success as endpoint-only readiness.

Do not modify these files for this fix unless a test proves they must change:

- `tools/launcher/assets/buddies/*/AGENTS.md`
- `buddyswitch/skills/market/*/SKILL.md`
- `buddyswitch/env-profiles/*.json`
- `buddyswitch/manifest.toml`

## Implementation Tasks

### Task 1: Write Launcher-Ready Tests First

**Files:**

- Modify: `tests/test_browser_cockpit_launcher.py`
- Modify: `tests/test_buddyswitch_launcher.py`

**Steps:**

- [ ] Add a reusable browser CDP test double that can return:
  - `/json/version` success.
  - `/json/list` with no pages.
  - `/json/list` with only a `chrome://intro/` page.
  - `/json/list` with an `about:blank` page.
  - `PUT /json/new?about:blank` success.
  - `GET /json/new?about:blank` failure.
- [ ] Add a fake Chrome binary that records argv and then marks the CDP test double as reachable.
- [ ] Add a test proving `env browser ensure --instance <id>` launches Chrome with:
  - `--remote-debugging-port=<port>`
  - `--user-data-dir=<instance>/browser/profile`
  - `--no-first-run`
  - `--no-default-browser-check`
  - `about:blank`
- [ ] Add a test proving endpoint-only readiness is rejected:
  - `/json/version` succeeds.
  - `/json/list` is empty or has only `chrome://intro/`.
  - If page creation is disabled, `env browser ensure` fails and does not configure MCP as ready.
- [ ] Add a test proving intro-only readiness is repaired:
  - `/json/version` succeeds.
  - `/json/list` initially has only `chrome://intro/`.
  - `PUT /json/new?about:blank` succeeds.
  - `/json/list` then has `about:blank`.
  - `env browser ensure` succeeds.
- [ ] Add a start test proving `instance start --buddy market` does not invoke fake codex until browser ready page has been verified.
- [ ] Add an open test proving `instance open <id>` runs the same ready page gate before invoking fake codex.

Run:

```bash
python3 -m unittest tests.test_browser_cockpit_launcher tests.test_buddyswitch_launcher
```

Expected before implementation: new tests fail because readiness is still endpoint-only and Chrome launch flags are missing.

### Task 2: Implement Launcher Ready Page Gate

**Files:**

- Modify: `tools/launcher/browser_cockpit.sh`

**Steps:**

- [ ] Keep a low-level endpoint probe for `/json/version`, but stop treating it as public readiness.
- [ ] Add a shell function that reads `/json/list` and returns success only when at least one usable page exists.
- [ ] Parse JSON using Python from the shell helper. Do not introduce `jq`.
- [ ] Define usable page as `type == "page"` with a URL that is not `chrome://`, `chrome-untrusted://`, or `devtools://`. Treat `about:blank` as explicitly usable.
- [ ] Add a function that creates a blank page with:

```bash
curl --silent --show-error --fail --request PUT "$(buddyswitch_browser_url)/json/new?about:blank" >/dev/null
```

- [ ] Add a bounded ready loop:
  - Check `/json/version`.
  - Check usable page.
  - If endpoint is up but page is missing, create `about:blank`.
  - Re-check usable page.
  - Retry for a small bounded interval already consistent with the existing 20 second startup wait.
- [ ] Launch new Chrome with `--no-first-run`, `--no-default-browser-check`, and final URL `about:blank`.
- [ ] Update public status/ensure messages from endpoint-only language to ready language.
- [ ] Ensure `buddyswitch_browser_bootstrap` calls MCP setup only after ready page success.

Run:

```bash
python3 -m unittest tests.test_browser_cockpit_launcher tests.test_buddyswitch_launcher
```

Expected after this task: launcher tests pass.

### Task 3: Upgrade Broker Preflight From Endpoint To Ready Page

**Files:**

- Modify: `scripts/runtime_kernel/broker.py`
- Modify: `tests/test_market_browser_evidence.py`
- Modify: `tests/test_runtime_tool_feedback.py`
- Modify: `tests/test_turn_integration.py`

**Steps:**

- [ ] Replace endpoint-only `_require_browser_endpoint` semantics with browser ready page semantics.
- [ ] Probe `/json/version` first. If unreachable, keep an explicit unreachable-browser error.
- [ ] Probe `/json/list`. If it has a usable page, allow token issuance.
- [ ] If `/json/list` has no usable page, attempt one `PUT /json/new?about:blank`, then re-check `/json/list`.
- [ ] If no usable page is available after repair, reject token issuance.
- [ ] Return structured broker feedback for browser-ready failures:
  - `permission_boundary`: `browser-cockpit-ready`
  - `stop_condition`: browser cockpit is not ready for MCP page operations
  - `allowed_next_actions`: restart/open the launcher-managed instance or rerun browser ensure
  - `command_hint`: `./buddyswitch-codex env browser ensure --instance <instance-id>`
- [ ] Preserve token scoping and handwritten-token rejection behavior.

Run:

```bash
python3 -m unittest tests.test_market_browser_evidence tests.test_runtime_tool_feedback tests.test_turn_integration
```

Expected after this task: browser evidence tests pass and endpoint-only token issuance is impossible.

### Task 4: Update Browser Contract Docs

**Files:**

- Modify: `framework/docs/browser-cockpit.md`
- Modify: `tests/test_repo_consistency.py`

**Steps:**

- [ ] Update the cockpit bootstrap section to say launcher ensures a ready browser page before launching codex-cli.
- [ ] Update the evidence gate section to say preflight verifies browser ready page, not only debug endpoint reachability.
- [ ] Add a short note that `about:blank` is the canonical bootstrap target and `chrome://intro/` is not ready.
- [ ] Add a repo consistency test that rejects public docs or launcher help text that presents `/json/version` reachability as sufficient browser readiness.

Run:

```bash
python3 -m unittest tests.test_repo_consistency
```

Expected after this task: docs and consistency checks match the new contract.

### Task 5: Residue Sweep

**Files:**

- Modify only files already touched by Tasks 1-4 unless a test finds a stale public contract elsewhere.

**Steps:**

- [ ] Search for endpoint-only public wording:

```bash
rg -n "endpoint is reachable|endpoint reachable|Browser cockpit reachable|/json/version.*ready|browser endpoint" tools scripts framework docs tests
```

- [ ] Replace public readiness wording with ready page wording.
- [ ] Keep low-level code comments only when they clearly distinguish endpoint probe from browser readiness.
- [ ] Search for prompt-workaround drift:

```bash
rg -n "chrome://intro|no-first-run|json/new|No page selected|about:blank" tools/launcher/assets/buddies buddyswitch/skills
```

- [ ] Confirm no `AGENTS.md` or market skill now instructs the host to debug browser readiness.
- [ ] Confirm no old-instance migration or compatibility marker was added.

Run:

```bash
python3 -m unittest discover -s tests
```

Expected after this task: full suite passes.

### Task 6: Manual Rebuild Experience Verification

**Files:**

- No source file changes expected.

**Steps:**

- [ ] Close active BuddySwitch Codex and Chrome instance sessions.
- [ ] Delete existing BuddySwitch instances as planned for rebuild testing.
- [ ] Start a fresh market instance:

```bash
./buddyswitch-codex instance start --buddy market
```

- [ ] Before entering any user task, verify Chrome is visible as a normal browser window with `about:blank` or another usable normal page, not Chrome login/intro.
- [ ] In the codex-cli session, run a market research task that requires browsing.
- [ ] Confirm the host can call `browser_evidence` and then `chrome-devtools-cockpit` without `Error: No page selected`.
- [ ] Confirm market persist succeeds with the broker-issued browser evidence token.

Stop condition:

- If codex-cli sees `Error: No page selected`, the fix is not complete.
- If the host must reason about Chrome first-run or CDP repair steps, the fix is not complete.
- If the launcher opens codex-cli before market browser readiness, the fix is not complete.

## Verification Command Set

Run targeted tests during development:

```bash
python3 -m unittest tests.test_browser_cockpit_launcher tests.test_buddyswitch_launcher
python3 -m unittest tests.test_market_browser_evidence tests.test_runtime_tool_feedback tests.test_turn_integration
python3 -m unittest tests.test_repo_consistency
```

Run final automated verification:

```bash
python3 -m unittest discover -s tests
```

Run final manual verification with a fresh market instance after deleting old instances.

## Definition Of Done

This work is done only when:

- `instance start --buddy market` blocks codex-cli launch until browser ready page is true.
- `instance open <id>` runs the same ready page gate before codex-cli launch.
- New Chrome starts with `--no-first-run`, `--no-default-browser-check`, and `about:blank`.
- Endpoint-only `/json/version` success cannot issue browser preflight evidence.
- Intro-only browser state is repaired by launcher/runtime before host browser tool calls.
- Public docs and tests no longer treat endpoint reachability as browser readiness.
- No `AGENTS.md` or market skill prompt becomes responsible for browser diagnosis.
- Automated tests and fresh-instance manual market flow pass.
