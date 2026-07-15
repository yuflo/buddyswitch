# Browser Target TTL Forward Rebuild Plan

**Date:** 2026-07-15
**Implementation and acceptance worktree:** `fea-daemon`
**Status:** implemented and focused acceptance complete

## 1. Target outcome

Repair the browser TTL failure that left Chrome tabs alive after their schedules fired, without a URL/page-number fallback or a compatibility track. The accepted result must:

1. keep ordinary `new_page`, `select_page`, navigation, snapshot, click, typing, explicit close, and lazy browser acquire behavior working;
2. track an opened tab for TTL by Chrome's stable target ID, never by MCP `pageId`, URL, title, or list position;
3. close and verify that exact target when its TTL expires;
4. preserve the existing resource strategy: lazy acquire, actor-owned browser/profile, parent-turn protection, failed-open cleanup, delayed release, real-page release guard, and verified process cleanup;
5. load TTL values from one host-global file at `$BUDDYSWITCH_SHARED_ROOT/config/browser.toml`;
6. prove the path with focused tests, including one public CLI-created actor instance, and leave no old identity path or test residue.

This is a direct replacement. Existing `pages`, `page_id`, `current_page_id`, `selected_page_id`, URL-resolution expiry, and temporary expiry MCP session logic are removed, not read in parallel.

## 2. Confirmed root cause and historical decision

The original lifecycle implementation used a CDP target ID. The CLI/browser refactor correctly unified normal page operations through `chrome-devtools-mcp`, but also persisted MCP `pageId` as if it were a durable tab identity. A later repair observed that `pageId` changes between MCP processes and resolved it in a new session by recorded URL/title.

That repair is the direct failure mechanism:

- `pageId` is scoped to one MCP process and can be renumbered;
- URL and title are mutable metadata, not identity;
- navigation changes the URL after the TTL record is written;
- expiry starts a fresh MCP process, finds no matching URL, treats that as an already-absent page, deletes the TTL record, and schedules release;
- the release guard still sees a real Chrome page and correctly refuses to kill the browser.

The lifecycle scheduler did fire. The expiry handler discarded ownership of a tab it had not closed.

## 3. Final ownership model

There are three deliberately separate concepts:

| Concern | Identity | Owner |
| --- | --- | --- |
| Normal browser operation and selection | MCP `pageId`, valid only in the active upstream generation | `chrome_devtools_cockpit_proxy.py` |
| Durable tab resource lifecycle | Chrome `TargetID` returned by hidden upstream `get_tab_id` | `cdp_browser_lifecycle.py` |
| Raw browser target transport | `Target.getTargets`, `Target.closeTarget`, ready-target creation | `cdp_target.py` |

URL and title may be persisted for diagnostics only. They never participate in lookup, close, absence, retry, or verification decisions.

### 3.1 Persisted state

`<instance>/runtime/browser/page_idle.json` is replaced with this shape:

```json
{
  "active_tab_target_id": "TAB-123",
  "targets": {
    "TAB-123": {
      "tab_target_id": "TAB-123",
      "last_used_at": "2026-07-15T00:00:00Z",
      "idle_seconds": 40,
      "url": "https://example.com/diagnostic-only"
    }
  }
}
```

There is no pageId-to-target map. The in-memory proxy may remember the selected target for its current upstream generation, but that map is never durable.

### 3.2 Schedule contract

```json
{
  "tab_target_id": "TAB-123",
  "idle_seconds": 40
}
```

The schedule key is `browser.page.idle:TAB-123`. The effective `idle_seconds` is stored in both the target record and the trigger payload so a later config edit affects only the next schedule/refresh and cannot reinterpret an already-issued due time.

### 3.3 Exact expiry sequence

1. Validate `tab_target_id`, `idle_seconds`, target route, and stale-due state.
2. If the parent turn is running and this is the active target, refresh the target with the current config.
3. Query `Target.getTargets` through the shared CDP transport.
4. If the exact target is already absent, forget it and schedule release when no tracked targets remain.
5. Otherwise call `Target.closeTarget(tab_target_id)`.
6. Query targets again and require exact absence.
7. Only after verified absence, forget the record and schedule release.

Query, close, or verification failure keeps the state and returns failure so daemon retry semantics retain ownership. A missing browser process may forget state because there is no live target to own.

## 4. Normal browser-use behavior

The pinned `chrome-devtools-mcp@1.1.1` process is started with `--experimental-interop-tools` and `--experimental-structured-content`. Its hidden read-only `get_tab_id` returns the selected Puppeteer page's stable Chrome tab target ID.

The proxy keeps this internal:

- `tools/list` remains the static public asset and does not expose `get_tab_id`;
- internal request IDs are generation-scoped and never reach the client;
- upstream `structuredContent` enabled for internal identity is removed from ordinary client responses, preserving the public response shape;
- `new_page` and successful `select_page` resolve `pageId -> tab_target_id` before returning their client response, then persist/refresh the target;
- page-scoped calls refresh the known generation-local selected target at request acceptance, protecting long navigation or interaction calls;
- after an upstream restart, the first page-scoped call internally asks `get_tab_id` for the upstream's actual selected page before forwarding the original call; it does not change MCP selection;
- explicit `close_page` resolves the requested `pageId` before forwarding, then forgets the exact target only after a successful close. Identity lookup failure never blocks the user's close operation; expiry later reconciles an already-absent target.

Thus target tracking adds internal metadata work but does not create, select, focus, navigate, limit, reuse, or reorder pages. The previously removed page hard limit and exact-URL reuse remain removed.

## 5. Host-global TTL configuration

Live configuration is not stored in the source checkout. The only file is:

```text
$BUDDYSWITCH_SHARED_ROOT/config/browser.toml
```

Default content, created atomically during shared-environment/instance bootstrap when absent:

```toml
schema_version = 1

[ttl]
page_idle_seconds = 40
release_delay_seconds = 10
```

Rules:

- no per-repository, per-role, per-actor, or environment-variable value override;
- `schema_version` must equal `1`;
- `page_idle_seconds` must be a positive integer;
- `release_delay_seconds` must be a non-negative integer;
- booleans, missing fields, and unknown keys are rejected with a path-specific error;
- scheduling reloads the file each time, so a valid edit applies to the next refresh without a process restart;
- invalid existing config fails bootstrap or lifecycle scheduling explicitly; it is never silently overwritten;
- implementation constants exist only as the one-time default-file template, never as an alternate runtime truth.

`browser_ttl_config.py` is the sole path, creation, parsing, and validation owner. Callers receive an immutable two-value configuration object.

## 6. Direct replacement changes

### 6.1 Configuration and bootstrap

- Add `scripts/env/browser_ttl_config.py` with path derivation, atomic `ensure`, strict TOML load, and a small `ensure --shared-root` CLI.
- Invoke that CLI from `buddyswitch_ensure_shared_env` so public `instance start` creates/validates the shared config before actor runtime startup.
- Remove fixed page/release defaults from lifecycle function signatures and status rendering.

### 6.2 CDP target transport

- Replace `scripts/env/cdp_background_page.py` with `scripts/env/cdp_target.py`.
- Keep ready-target creation required by browser startup.
- Add `list_page_targets()` using browser-level `Target.getTargets` and keep exact `close_target()`.
- Move every `/json/list`/raw-CDP target read out of lifecycle state code.
- Update launcher variables/imports to the new target transport; retain no old module or environment variable alias.

### 6.3 Lifecycle state and schedules

- Rebuild `cdp_browser_lifecycle.py` around `targets` and `active_tab_target_id`.
- Schedule and forget by `tab_target_id` only.
- Persist the effective TTL used for each schedule.
- Load shared config for each page refresh and browser-release schedule.

### 6.4 Proxy identity bridge

- Start the pinned upstream with the two required experimental flags.
- Add an internal response state machine in `UpstreamManager`; do not start a second MCP process.
- Capture stable identity after new/select, bootstrap it before the first page-scoped call in a generation, and resolve it before explicit close.
- Keep the normal client response pending only for identity work that must complete after an upstream response.
- Serialize upstream writes because both the client loop and relay can issue messages.
- Preserve new-page failure cleanup by diffing CDP target IDs before/after and closing exact new targets.

### 6.5 Expiry and release

- Delete `McpToolSession`, URL/title candidate resolution, and fresh-session MCP expiry close.
- Expire with exact CDP list/close/list verification.
- Keep state on transient query/close/verify failure.
- Update the release guard to query the shared target transport while keeping its current `real_user_page_present` protection.
- Change inbound payload contract to `tab_target_id` plus `idle_seconds`.

## 7. Test-first execution plan

All commands run from `fea-daemon`. Use only the public runner. No blind `full` run is planned because the changed ownership surface has explicit focused coverage and the user requested an efficient acceptance loop.

### Task A — config RED/GREEN

Add `tests/unit/browser/test_ttl_config.py` first:

- absent config is atomically created at the shared-root path with exact defaults;
- valid edits reload and return new values;
- invalid schema, missing/unknown keys, bools, negative/zero values, and malformed TOML fail explicitly;
- instance-root derivation points to the same shared file for two actor instances.

Run:

```bash
./buddyswitch-test focused tests/unit/browser/test_ttl_config.py
```

Add a process bootstrap assertion to `tests/process/launcher/test_bootstrap_config.py` that the public launcher path creates the file outside the repo and rejects an invalid existing file.

### Task B — stable target lifecycle RED/GREEN

Replace the old pageId tests in `tests/integration/browser/test_cdp_page_lifecycle.py`:

- refresh schedules `tab_target_id` and effective TTL;
- state contains only target identity fields;
- edited config changes the next schedule only;
- stale-due comparison uses the trigger's effective TTL;
- final verified target forget schedules configured release delay;
- scheduling failure writes no ownership record.

Extend the focused CDP transport fixture to prove exact `Target.getTargets`, `Target.closeTarget`, and ready-target creation. Run:

```bash
./buddyswitch-test focused \
  tests/unit/browser/test_ttl_config.py \
  tests/integration/browser/test_cdp_page_lifecycle.py
```

### Task C — proxy identity bridge RED/GREEN

Update the fake upstream to implement internal `get_tab_id` structured results. Replace pageId-state assertions in the proxy integration tests with:

- upstream argv contains the pinned package and both experimental flags;
- public `tools/list` still hides `get_tab_id`;
- new/select record the returned stable target ID;
- navigation keeps the same target after URL change and refreshes at request acceptance;
- first page-scoped call after upstream restart bootstraps actual selected identity without changing basic operation;
- normal response shape does not leak structured content;
- explicit close removes exact tracked target;
- identity lookup failure returns the normal close result with a lifecycle warning;
- high page count and exact URL still forward normally;
- failed-open cleanup still closes only the CDP target created by that failed call.

Run:

```bash
./buddyswitch-test focused \
  tests/integration/browser/test_cockpit_proxy_open_search.py \
  tests/integration/browser/test_cockpit_proxy_page_state.py \
  tests/integration/browser/test_cockpit_proxy_protocol.py \
  tests/integration/browser/test_cockpit_proxy_lifecycle.py
```

### Task D — exact expiry RED/GREEN

Replace URL/session tests in `tests/unit/browser/test_page_expired_handler.py` and the process expiry test:

- navigated target closes by unchanged target ID;
- duplicate URLs do not matter;
- absent target is forgotten;
- query/close/verification failure retains state and does not schedule release;
- only verified absence forgets state;
- active target plus running parent refreshes with current config;
- no MCP process/session is started by expiry;
- failed-open cleanup still retries the exact CDP target.

Run:

```bash
./buddyswitch-test focused \
  tests/unit/browser/test_page_expired_handler.py \
  tests/process/browser/test_page_expired_target_transport.py
```

The process file is renamed if its final purpose is no longer an MCP-session test.

### Task E — public CLI actor-instance acceptance

Use the existing system browser lifecycle and public instance-start ResourceLedger fixtures rather than adding a second full-stack harness. Together they must:

1. invoke public `./buddyswitch-codex instance start` against a temporary shared root;
2. discover the returned actor instance and register all service/browser resources before assertions;
3. assert the shared config was created outside the repo;
4. use the existing dev browser lifecycle system fixture with test-only page `1` / release `0` TTL values;
5. open and navigate a page through the cockpit path while the fake upstream changes URL but keeps target ID;
6. observe exact target expiry and browser release without sleeping production `40 + 10` seconds;
7. signal cleanup and let the ledger prove no processes, sockets, schedules, worktrees, or browser profile escape the run root.

Run the browser lifecycle directory, then run the public CLI supervisor node separately because the nested runner intentionally acquires the system-test lock:

```bash
./buddyswitch-test focused tests/system/browser_lifecycle
./buddyswitch-test focused \
  tests/integration/support/test_run_supervisor.py::test_sigterm_runner_cleans_public_instance_start_detached_services_and_worktrees
```

If a deterministic full-stack expiry cannot be driven through existing fake service seams without duplicating production infrastructure, keep the system test to CLI bootstrap/config plus the real browser acquire boundary, and retain exact expiry proof in process/integration. Do not build a second test framework for one scenario.

## 8. Focused final acceptance set

After all local RED/GREEN loops pass, run one risk-matched non-system aggregate:

```bash
./buddyswitch-test focused \
  tests/unit/browser/test_ttl_config.py \
  tests/unit/browser/test_page_expired_handler.py \
  tests/integration/browser/test_cdp_page_lifecycle.py \
  tests/integration/browser/test_cockpit_proxy_open_search.py \
  tests/integration/browser/test_cockpit_proxy_page_state.py \
  tests/integration/browser/test_cockpit_proxy_protocol.py \
  tests/integration/browser/test_cockpit_proxy_lifecycle.py \
  tests/integration/browser/test_runtime_manager.py \
  tests/process/browser \
  tests/process/launcher/test_bootstrap_config.py \
  tests/process/launcher/test_browser_cockpit.py \
  tests/process/launcher/test_browser_commands.py
```

Run the two system gates from Task E serially after the aggregate. Do not combine the nested CLI supervisor node with another system test: the inner and outer public runners correctly contend on the same system-test lock. Record exact counts, duration, and residue outcome below. A wider run is justified only if these gates expose a cross-owner failure signal.

## 9. Architecture and residue audit

The final review must verify behavior and deletion, not just green tests:

```bash
rg -n 'current_page_id|selected_page_id|page_id_to_target_id|"pages"|page_id' \
  scripts/env/cdp_browser_lifecycle.py \
  tools/launcher/chrome_devtools_cockpit_proxy.py \
  tools/launcher/browser_page_expired_handler.py \
  tools/launcher/browser_inbound.py

rg -n '_resolve_recorded_page|McpToolSession|open_mcp_session|read_page_targets|cdp_background_page' \
  scripts tools/launcher tests

rg -n 'BROWSER_PAGE_IDLE_SECONDS|BROWSER_COCKPIT_RELEASE_DELAY_SECONDS' scripts tools/launcher tests

git diff --check
```

Expected results:

- no durable or expiry `page_id` identity;
- no URL/title identity resolution;
- no expiry-owned MCP process;
- no old CDP transport module/variable;
- no runtime TTL constant path;
- no source-repo `browser.toml`;
- public page-limit/reuse behavior remains absent;
- only intentional files are modified; pre-existing untracked user files remain untouched.

Review the diff by responsibility:

1. **Correctness:** exact target identity survives navigation and is forgotten only after verified absence.
2. **Browser-use safety:** normal page operations still forward once with the same arguments except enforced background/no-focus policy.
3. **Resource safety:** failed-open, parent-running, delayed release, real-page guard, and cleanup verification remain effective.
4. **Configuration:** one obvious global file, one loader, no override precedence, next-schedule semantics.
5. **Simplicity:** one target transport, one lifecycle state owner, one proxy identity bridge; no adapter or compatibility read.
6. **Test quality:** local rules proven low in the pyramid; only the cross-service public actor path is system-level.

## 10. Progress and acceptance record

- [x] Root cause, historical design, and target architecture confirmed.
- [x] Config location and single-layer semantics approved.
- [x] Config tests and implementation complete.
- [x] Stable target lifecycle tests and implementation complete.
- [x] Proxy identity bridge tests and implementation complete.
- [x] Exact expiry/release tests and implementation complete.
- [x] Public CLI actor-instance acceptance complete.
- [x] Residue and architecture audit complete.
- [x] Final focused aggregate green.

### Verification evidence

- Baseline before implementation: `48 passed, 2 subtests passed in 6.68s` for the original lifecycle/proxy/expiry slice.
- Config unit plus launcher bootstrap: `20 passed, 8 subtests passed in 2.19s`.
- Proxy identity/state focused file: `14 passed, 2 subtests passed in 9.08s`, including navigation with stable identity and upstream exit during internal identity lookup.
- Runtime manager, exact target child process, and lock slice: `16 passed, 9 subtests passed in 7.70s`.
- Launcher browser process contracts: `31 passed, 10 subtests passed in 27.71s`.
- Final non-system risk aggregate: `147 passed, 33 subtests passed in 75.11s` (`focused-python` completed in `75.21s`). It includes regressions proving that a failed target query cannot incorrectly release the browser, failed-open cleanup retries when Chrome reports a target still present after `closeTarget`, and an owned browser child is reaped when its process group disappears during the termination wait.
- Browser system gate with test-only `page_idle_seconds = 1` and `release_delay_seconds = 0`: `3 passed in 2.42s`. The main path proves `new_page -> list_pages -> select_page -> navigate_page (URL changes, target ID does not) -> take_snapshot -> exact Target.closeTarget -> release -> restart`, and asserts expiry never calls MCP `close_page`.
- Public `./buddyswitch-codex instance start --role pm` under the existing ResourceLedger supervisor: `1 passed in 3.17s`. It asserts `$BUDDYSWITCH_SHARED_ROOT/config/browser.toml` is created with exact defaults and all detached services/worktrees are cleaned after the runner signal.
- `git diff --check`: clean in `fea-daemon`.
- Residue scans: no old background-target module/env alias, temporary expiry MCP session, URL/title resolution, durable pageId field, runtime TTL constant, source-checkout `config/browser.toml`, page limit, or exact-URL reuse path remains.
- Pre-existing untracked memo/stress-design files in both worktrees were left untouched.

One combined exploratory acceptance run exposed test pollution: unit tests had replaced shared imported module functions without restoring them. Cleanup hooks were added so lower-tier fakes cannot alter later system behavior. A later pre-commit aggregate caught an intermittent production cleanup branch that returned after the process group disappeared without reaping its tracked child; a deterministic regression now covers that branch and the implementation reaps before returning. The same runs also confirmed that the nested CLI supervisor must remain a separate gate because the test runner's system lock is working as designed.

### Remaining risk

The remaining risk is limited to the pinned upstream's experimental `get_tab_id`/structured-content contract changing in a future package upgrade. The package remains pinned at `chrome-devtools-mcp@1.1.1`, argv and response-shape tests cover the current contract, and identity failure is deliberately non-blocking for ordinary browser operations. No broad full-suite run was performed; acceptance stayed on the explicit browser, launcher, daemon-contract, system lifecycle, and public CLI resource boundaries.
