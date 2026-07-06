# Search Open Browser Cockpit Rebuild Plan

Date: 2026-07-04  
Status: implementation and test plan; no runtime code changed by this memo

## 1. Goal

Rebuild the browser-search opening path around `chrome-devtools-cockpit` and remove the old `search.open_browser` live capability with no dual-track compatibility.

The target end state is:

```text
actor
  -> chrome-devtools-cockpit.search_page(query, engine)
  -> cockpit/browser-session open-or-reuse page
  -> list/select/snapshot through chrome-devtools-cockpit
  -> browser TTL/resource lifecycle stays in browser-session/lifecycle code
```

The old live path must be removed:

```text
actor
  -> search__open_browser / search.open_browser
  -> env search implementation
  -> runtime broker browser.open_url
  -> browser-session open-or-reuse page
```

`search.request` and `search.status` may remain only as non-opening metadata/planning actions. They must not teach or delegate browser page opening.

## 2. Why This Stage Is Now Unblocked

The first-stage socket issue has been validated separately: `chrome-devtools-cockpit` can acquire browser capability and `new_page` can open pages.

The `act-market-93892ea2bfe8` session proves the browser-search flow can be built on cockpit:

```text
query
  -> construct search URL
  -> chrome-devtools-cockpit.new_page
  -> list_pages
  -> select_page
  -> take_snapshot
  -> observable search page evidence
```

The session also proves that search page opening, page selection, snapshot evidence, and idle refresh work without calling `search.open_browser`, `search__open_browser`, or any env search tool.

## 3. Principles Applied

Read before this plan:

- `AGENTS.md`
- `docs/bitter/2026-05-18-tool-skill-layering-principles.md`
- `docs/bitter/2026-05-26-test-resource-lifecycle-principles.md`
- `docs/bitter/2026-05-28-parallel-change-boundary-principles.md`
- `docs/bitter/2026-06-02-residue-cleanup-principles.md`
- `docs/bitter/2026-06-02-wrong-boundary-narrowness-principles.md`
- `docs/bitter/2026-06-25-built-in-product-interface-principles.md`
- `docs/bitter/2026-06-25-end-to-end-contract-slice-principles.md`
- `docs/memo/2026-07-03-browser-cockpit-socket-scope-confirmation.md`

Rules for this rebuild:

- No compatibility alias for `search.open_browser`.
- No long-lived dual path where both env search and cockpit can open search pages.
- No prompt-only fix that leaves old tool semantics live.
- No hidden old semantics in role `AGENTS.md`, market skills, framework contracts, or launcher rejection guidance.
- Behavior tests and live-surface residue scans are both required.
- Real actor validation is required because local unit tests alone do not prove the end-to-end browser path.

## 4. Current Code Findings

| Area | Current state | Required change |
|---|---|---|
| `scripts/env/tools/search/tool.py` | Defines `open_browser` as public `search.open_browser`. | Remove `open_browser` action. Keep only `status` and `request` if they remain non-opening. |
| `scripts/env/tools/search/_impl.py` | Defines `_RuntimeBrowserClient`, `browser_client`, `open_browser_for_active_instance`, broker result mapping, and `_ACTION_HANDLERS['open_browser']`. | Delete the open-browser implementation and broker client. Update status/request guidance to point to cockpit `search_page` for opening. |
| `scripts/runtime_kernel/dispatcher.py` | Supports `browser.open_url`; it acquires browser and calls `browser_session.open_or_reuse_page`. | Remove `browser.open_url` because current live source shows no owner beyond old `search.open_browser`. Keep `browser.acquire/status/release`. |
| `tools/launcher/chrome_devtools_cockpit_proxy.py` | Has browser-session ownership for `new_page`, `list_pages`, `select_page`, page-scoped idle refresh, and socket-backed `browser.acquire`. No search-specific tool yet. | Add local `search_page` tool to cockpit. It builds a supported search URL and calls the same browser-session open/reuse path as `new_page`. |
| `tools/launcher/env.sh` | Native web_search rejection still points users to `search__open_browser`. | Point browser-native search opening to `chrome-devtools-cockpit.search_page`; `search__request` only for non-opening URL planning. |
| `tools/launcher/assets/roles/*/AGENTS.md` | Runtime role bootstrap still teaches `search__open_browser`. | Replace old opening guidance with cockpit-first `search_page`. Keep AGENTS short. |
| `framework/contracts/market.md` | Market contract still allows `search__open_browser` as wrapper. | Replace with cockpit `search_page` and non-opening `search__request` guidance. |
| `buddyswitch/skills/market/*/SKILL.md` | Market skills still instruct `search__open_browser`. | Replace old opening guidance in live market skills. |
| Tests | Multiple schema, semantic, runtime broker, response, search, launcher, repo consistency, and skill tests currently protect the old path. | Convert tests to protect the rebuilt path and prevent old live residue. |

## 5. Target Runtime Contract

### 5.1 `chrome-devtools-cockpit.search_page`

Add a local cockpit MCP tool:

```text
tool: chrome-devtools-cockpit.search_page
input:
  query: non-empty string
  engine: optional enum ["google", "web", "reddit", "x"]
effect:
  build search URL
  open or reuse a managed browser-session page
  refresh/register browser page idle TTL
  return target_url, target_id, page_count transition, and idle state text
```

Engine mapping:

```text
google -> https://www.google.com/search?q=<query>
web    -> https://www.google.com/search?q=<query>
reddit -> https://www.reddit.com/search/?q=<query>
x      -> https://x.com/search?q=<query>&src=typed_query
```

This tool is local to the cockpit proxy. It must not forward to upstream `chrome-devtools-mcp`, because upstream does not own BuddySwitch browser-session lifecycle semantics.

### 5.2 Env `search`

`search` remains only for non-opening search boundary metadata:

```text
search.status  -> read status and capability boundary
search.request -> return target_url planning metadata with page_opened=false
```

`search.open_browser` is removed from:

- tool definition
- MCP registration
- runtime dispatch
- response contract
- semantic contract
- test fixtures
- live role/skill guidance

### 5.3 Runtime Broker Browser Methods

After removal:

```text
supported:
  browser.acquire
  browser.status
  browser.release

unsupported:
  browser.open_url
```

The broker should reject `browser.open_url` at the protocol boundary before target URL validation or browser acquisition.

## 6. Implementation Plan

### Phase A: Add Red Tests For The New Boundary

Modify `tests/test_browser_cockpit_proxy.py`:

- Add `test_tools_list_includes_buddyswitch_search_page`.
- Add `test_search_page_opens_locally_without_forwarding`.
- Add `test_search_page_blank_query_is_rejected_locally`.
- Add `test_search_page_rejects_unsupported_engine`.
- Add `test_search_page_builds_supported_engine_urls`.

Expected initial failures:

- `search_page` missing from `tools/list`.
- `tools/call search_page` currently forwards upstream or is unsupported.
- blank query and unsupported engine do not have local BuddySwitch validation.

Modify `tests/test_search_env_tool.py`:

- Change CLI/help expectation to expose only `status` and `request`.
- Add `test_search_open_browser_action_is_removed`.
- Update `search.status` and `search.request` assertions so browser-opening guidance points to `chrome-devtools-cockpit.search_page`.
- Add source scan assertion that `scripts/env/tools/search/_impl.py` does not contain `request_runtime_broker("browser.open_url"` or `browser_client.open_url`.

Modify `tests/test_runtime_broker.py`:

- Replace successful `browser.open_url` tests with `test_browser_open_url_method_is_removed`.
- Assert response code is `E_RUNTIME_BROKER_PROTOCOL`.
- Assert boundary is `broker-protocol`.
- Assert allowed methods do not include `browser.open_url`.
- Assert invalid URL payloads are rejected as unsupported method, not as `E_BROWSER_INVALID_URL`.

Modify contract tests:

- `tests/test_black_box_tool_runtime.py`: shipped search actions become `{"request", "status"}`.
- `tests/test_env_tool_schema_contract.py`: search supported actions become `{"request", "status"}` and no schema lookup for `open_browser`.
- `tests/test_env_tool_semantic_contract.py`: remove `search.open_browser` from expected actions and active-task requirements; canonical broker payload for `open_browser` must be invalid/unsupported.
- `tests/test_env_tool_response_contract.py`: remove old success/reuse/browser broker response expectations and assert removed action returns the standard unsupported-tool/action response.

Modify live-surface tests:

- `tests/test_repo_consistency.py`: scoped live guidance scan must reject `search__open_browser`, `search.open_browser`, and old CLI-style `search open_browser --query` in role bootstraps, framework contracts, stable guidance, and live docs/spec filters.
- `tests/test_runtime_skills.py`: market skills must require cockpit `search_page` guidance and reject old `search__open_browser` guidance.
- `tests/test_buddyswitch_launcher.py`: native `web_search` rejection must point to cockpit `search_page`, `search__request`, and `search__status`, not `search__open_browser`.

### Phase B: Implement Cockpit `search_page`

Modify `tools/launcher/chrome_devtools_cockpit_proxy.py`:

- Import `urlencode`.
- Add `SEARCH_ENGINES = ("google", "web", "reddit", "x")`.
- Add a local tool definition for `search_page`.
- Include the local tool in `tools_list_response`.
- Add helpers:
  - `_normalize_search_query`
  - `_normalize_search_engine`
  - `_build_search_url`
  - `_browser_search_open_text`
  - `_browser_search_error_text`
- In `mutate_tool_call`, intercept `name == "search_page"` before upstream forwarding.
- Require `--instance-root`, same as `new_page`.
- Call `browser_session.open_or_reuse_page`.
- Return success/error text with query, engine, target URL, target id, page count transition, and idle TTL.

Do not duplicate browser lifecycle logic. Reuse the same browser-session path used by `new_page`.

### Phase C: Delete Env `search.open_browser`

Modify `scripts/env/tools/search/tool.py`:

- Remove `ActionDefinition(name='open_browser', title='search.open_browser', ...)`.
- Update the tool description/object model so `search` no longer claims browser opening.
- Update `search.request` `do_not_use_when` to point browser opening to `chrome-devtools-cockpit.search_page`.

Modify `scripts/env/tools/search/_impl.py`:

- Remove imports that exist only for `open_browser` broker/result mapping.
- Remove `_RuntimeBrowserClient` and `browser_client`.
- Remove all open-browser-specific rejection/success mapping helpers.
- Remove `open_browser_for_active_instance`.
- Remove `_ACTION_HANDLERS['open_browser']`.
- Update `status_for_active_instance` and `request_for_active_instance` guidance:
  - `search.request` is URL planning only.
  - browser opening belongs to `chrome-devtools-cockpit.search_page`.

Modify `scripts/env/tool_runtime/context.py` only if current context projections expose `BrowserAccess.open_browser` to live hosts. If it is a placeholder not surfaced to active tool catalogs, either delete it or update the plan executor's residue scan to prove it is not live. Do not leave a live helper that teaches old semantics.

### Phase D: Remove Broker `browser.open_url`

Modify `scripts/runtime_kernel/dispatcher.py`:

- Remove `urlsplit` import if only used by `browser.open_url`.
- Remove `from env import cdp_browser_session as browser_session` if only used by `browser.open_url`.
- Remove `_validate_browser_target_url`.
- Remove `_browser_open_result_payload`.
- Remove `_browser_open_url_dispatch`.
- Remove `if method == "browser.open_url"` from `_browser_dispatch`.
- Remove `browser.open_url` from `_browser_allowed_actions`.
- Remove `browser.open_url` from top-level unsupported-method guidance.

This is not a rollback safety tradeoff. Current live source scan shows `browser.open_url` is only owned by old `search.open_browser`, so keeping it would preserve an orphaned dual path.

### Phase E: Clean Live Guidance Surfaces

Modify `tools/launcher/assets/roles/{market,dev,test,design,pm}/AGENTS.md`:

- Replace old `search__open_browser` lines with cockpit-first browser search guidance.
- Keep text short; do not turn AGENTS into a tool schema mirror.

Modify `tools/launcher/env.sh`:

- Replace native `web_search` rejection text with:
  - use `chrome-devtools-cockpit.search_page` for browser-native search page opening
  - use `search__request` for non-opening URL planning
  - use `search__status` for capability status

Modify `framework/contracts/market.md`:

- Replace `search__open_browser` wrapper guidance with cockpit `search_page`.

Modify `buddyswitch/skills/market/*/SKILL.md`:

- Replace old repeated execution-order guidance with:
  - use `chrome-devtools-cockpit.search_page` to open search pages
  - then use cockpit list/select/inspect/snapshot
  - use `search__request` only for URL planning without opening

Do not add payload schemas to skills. Skills own workflow judgment, not tool contract duplication.

## 7. Test Plan

### 7.1 Focused Red/Green Commands

Run after Phase A to confirm failures, then after implementation to confirm green:

```bash
python3 -m pytest \
  tests/test_browser_cockpit_proxy.py::BrowserCockpitProxyTests::test_tools_list_includes_buddyswitch_search_page \
  tests/test_browser_cockpit_proxy.py::BrowserCockpitProxyTests::test_search_page_opens_locally_without_forwarding \
  tests/test_browser_cockpit_proxy.py::BrowserCockpitProxyTests::test_search_page_blank_query_is_rejected_locally \
  tests/test_browser_cockpit_proxy.py::BrowserCockpitProxyTests::test_search_page_rejects_unsupported_engine \
  tests/test_browser_cockpit_proxy.py::BrowserCockpitProxyTests::test_search_page_builds_supported_engine_urls \
  -q
```

```bash
python3 -m pytest \
  tests/test_search_env_tool.py::SearchEnvToolTests::test_search_cli_help_exposes_status_and_request_only \
  tests/test_search_env_tool.py::SearchEnvToolTests::test_search_status_reports_market_profile_backend_and_cockpit_search_boundary \
  tests/test_search_env_tool.py::SearchEnvToolTests::test_search_request_browser_returns_actionable_instruction_without_opening_page \
  tests/test_search_env_tool.py::SearchEnvToolTests::test_search_open_browser_action_is_removed \
  -q
```

```bash
python3 -m pytest \
  tests/test_runtime_broker.py::RuntimeBrokerTests::test_browser_open_url_method_is_removed \
  tests/test_runtime_broker.py::RuntimeBrokerTests::test_browser_method_rejects_actor_mismatch \
  tests/test_runtime_broker.py::RuntimeBrokerTests::test_browser_open_url_is_rejected_before_url_validation \
  -q
```

### 7.2 Contract And Live-Surface Commands

```bash
python3 -m pytest \
  tests/test_black_box_tool_runtime.py::BlackBoxToolRuntimeTests::test_shipped_tools_expose_single_public_entrypoint \
  tests/test_env_tool_schema_contract.py::EnvToolSchemaContractTests::test_high_risk_schema_shapes_match_domain_contracts \
  tests/test_env_tool_semantic_contract.py::EnvToolSemanticContractTests::test_registry_semantics_cover_every_registered_tool_and_action \
  tests/test_env_tool_semantic_contract.py::EnvToolSemanticContractTests::test_broker_payload_action_ids_are_strict \
  tests/test_env_tool_response_contract.py \
  -q
```

```bash
python3 -m pytest \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_runtime_role_agents_use_native_first_env_tool_guidance \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_runtime_role_agents_are_short_role_bootstraps \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_stable_guidance_does_not_point_to_internal_tool_contract_surfaces \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_docs_spec_drift_filter_rejects_unmarked_live_guidance \
  tests/test_runtime_skills.py::RuntimeSkillsTests::test_market_skills_use_native_browser_entry \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_product_mode_run_codex_rejects_native_search_with_native_env_tool_guidance \
  -q
```

### 7.3 Scoped Residue Scans

The old live terms are:

```text
search__open_browser
search.open_browser
browser.open_url
request_runtime_broker("browser.open_url"
browser_client.open_url
search open_browser --query
```

Required live-source scan:

```bash
rg -n "search__open_browser|search\\.open_browser|browser\\.open_url|request_runtime_broker\\(\"browser\\.open_url\"|browser_client\\.open_url|search open_browser --query" \
  scripts tools/launcher/assets framework/contracts buddyswitch/skills/market \
  --glob '!docs/**'
```

Expected result: no output.

Tests may contain old terms only as negative assertions or unsupported-method regression test names. Add targeted consistency tests so this rule is machine-checked instead of relying on manual scan memory.

### 7.4 Broad Relevant Suite

After focused tests and scans are green:

```bash
python3 -m pytest \
  tests/test_browser_cockpit_proxy.py \
  tests/test_search_env_tool.py \
  tests/test_black_box_tool_runtime.py \
  tests/test_env_tool_schema_contract.py \
  tests/test_env_tool_semantic_contract.py \
  tests/test_env_tool_response_contract.py \
  tests/test_runtime_broker.py \
  tests/test_repo_consistency.py \
  tests/test_runtime_skills.py \
  tests/test_buddyswitch_launcher.py \
  -q
```

### 7.5 Formatting Check

```bash
git diff --check
```

## 8. Real Actor Acceptance Test

Start a fresh market actor:

```bash
./buddyswitch-codex instance start --role market --json
```

Capture:

- actor id
- instance root
- initial `browser_port`
- generated `codex-home/config.toml` showing `chrome-devtools-cockpit` registration

Use the instance input interface. The task text should require:

```text
只使用 chrome-devtools-cockpit。
请调用 chrome-devtools-cockpit.search_page 查询 "BuddySwitch browser resource lifecycle"。
然后调用 list_pages/select_page/take_snapshot 获取页面证据。
最后回复是否成功、打开 URL、target_id、页面数量变化/页面状态摘要。
不要调用 search.open_browser、search__open_browser、search__request 或 search__status。
```

Acceptance evidence:

- session log contains `chrome-devtools-cockpit.search_page`
- session log contains `chrome-devtools-cockpit.list_pages`
- session log contains `chrome-devtools-cockpit.take_snapshot`
- session log does not contain an env search invocation
- `search_page` returns `target_url`, `target_id`, and page count transition or reuse state
- instance `browser_port` is active after first browser use
- daemon schedule shows browser page idle tracking when applicable
- actor task completes without blocker

Cleanup:

```bash
./buddyswitch-codex instance stop <actor-id> --json
./buddyswitch-codex instance delete <actor-id> --yes --json
test ! -e /Users/chen/.codex-buddyswitch/instances/<actor-id>
```

Do not run broad service-starting verification until the actor cleanup path is proven, because browser/app-server/broker processes are owned resources.

## 9. Completion Criteria

The rebuild is complete only when all of the following are true:

1. `chrome-devtools-cockpit.search_page` is visible in cockpit `tools/list`.
2. `search_page` opens or reuses a managed browser-session page without forwarding upstream.
3. `search_page` validates blank query and unsupported engine locally.
4. `search.open_browser` is absent from env search action definitions.
5. `search__open_browser` is absent from runtime MCP registration.
6. `scripts/env/tools/search/_impl.py` no longer calls `browser.open_url`.
7. Runtime broker no longer supports `browser.open_url`.
8. `search.status` and `search.request` no longer instruct users to call `search.open_browser`.
9. Role AGENTS, market skills, framework contract, and launcher native-search rejection no longer teach old search browser opening.
10. Focused tests pass.
11. Broad relevant suite passes.
12. Scoped live-surface residue scan returns no hits.
13. Real actor acceptance test proves cockpit search page opening, page evidence retrieval, and idle tracking.
14. Validation actor is stopped/deleted and no instance directory remains.

If any item is missing, do not claim completion.

## 10. Implementation Discipline

Recommended execution order:

1. Commit or stash unrelated work before implementation.
2. Add red tests for cockpit `search_page`.
3. Add red tests for env search action removal.
4. Add red tests for broker `browser.open_url` removal.
5. Add/update live-surface residue tests.
6. Implement cockpit `search_page`.
7. Delete env `search.open_browser`.
8. Delete broker `browser.open_url`.
9. Clean live guidance surfaces.
10. Run focused tests until green.
11. Run scoped residue scan.
12. Run broad relevant suite.
13. Run real actor acceptance test.
14. Clean actor resources.
15. Report changed files, verification evidence, residue scan, actor evidence, and remaining risk.

Do not merge a partial state where both `search__open_browser` and `chrome-devtools-cockpit.search_page` are live opening tools.

## 11. Expected File Set

Implementation files:

- `tools/launcher/chrome_devtools_cockpit_proxy.py`
- `scripts/env/tools/search/tool.py`
- `scripts/env/tools/search/_impl.py`
- `scripts/runtime_kernel/dispatcher.py`
- `scripts/env/tool_runtime/context.py` only if its browser helper is live
- `tools/launcher/env.sh`
- `tools/launcher/assets/roles/design/AGENTS.md`
- `tools/launcher/assets/roles/dev/AGENTS.md`
- `tools/launcher/assets/roles/market/AGENTS.md`
- `tools/launcher/assets/roles/pm/AGENTS.md`
- `tools/launcher/assets/roles/test/AGENTS.md`
- `framework/contracts/market.md`
- `buddyswitch/skills/market/*/SKILL.md`

Test files:

- `tests/test_browser_cockpit_proxy.py`
- `tests/test_search_env_tool.py`
- `tests/test_runtime_broker.py`
- `tests/test_black_box_tool_runtime.py`
- `tests/test_env_tool_schema_contract.py`
- `tests/test_env_tool_semantic_contract.py`
- `tests/test_env_tool_response_contract.py`
- `tests/test_repo_consistency.py`
- `tests/test_runtime_skills.py`
- `tests/test_buddyswitch_launcher.py`

No unrelated refactors, renames, formatting sweeps, or broad launcher restructuring should be mixed into this change.
