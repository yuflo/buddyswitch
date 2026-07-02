# Browser Cockpit Control-Plane Forward Rebuild Plan

Date: 2026-07-02  
Status: architecture rebuild plan, no framework code changed in this review  
Visual companion: `docs/memo/2026-07-02-browser-cockpit-control-plane-rebuild.html`

## 0. Task Target Restatement

这次升级改造的目标不是修一个 `search__open_browser` case，也不是把 `__file__` 推导 source root 改成另一个路径来源。

目标是把 browser acquisition 从 actor runtime 中彻底移走，让 browser cockpit 成为 launcher/control-plane 拥有的内建 runtime capability：

```text
actor runtime
  -> broker/browser capability request
  -> launcher/control-plane browser runtime manager
  -> Chrome CDP endpoint and page data-plane
  -> structured open/reuse/blocked result
```

硬底线：

- actor runtime 不感知 source root。
- actor runtime 不执行、不定位、不 shell 回 `buddyswitch-codex`。
- `search__open_browser` 不是 browser lifecycle owner，只能表达 search URL open intent。
- `chrome-devtools-cockpit` 可以消费 browser capability，但不能用 subprocess 回调 launcher CLI 来获得 capability。
- 不保留双轨兼容：旧 runtime ensure 路径必须删除或降级为非 live-surface 历史证据。
- 改造完成必须有行为测试、live-surface residue scan、端到端 contract slice、资源生命周期残留检查。

## 1. Current Root Cause

根因不是 Chrome DevTools 缺少打开 URL 的基础能力。`Target.createTarget`、page reuse、page limit、idle TTL 已经存在于 browser session / lifecycle 数据面。

根因是 browser acquisition 的 ownership 放错层了：

```text
runtime-visible tool call
  -> runtime helper sees no browser_port
  -> runtime helper performs browser ensure
  -> runtime helper derives or receives source root
  -> runtime helper shells to buddyswitch-codex env browser ensure
```

这个链路在 sparse actor workspace 中暴露为：

```text
E_SEARCH_BROWSER_ENSURE_FAILED
No such file or directory: .../workspace/buddyswitch-codex
```

这不是路径 bug 的本质。路径错误只是错误边界的可见症状。

## 2. Bitter Principles Applied

已复读并用于本计划的原则文件：

- `docs/bitter/2026-05-18-tool-skill-layering-principles.md`
- `docs/bitter/2026-05-26-test-resource-lifecycle-principles.md`
- `docs/bitter/2026-05-28-parallel-change-boundary-principles.md`
- `docs/bitter/2026-06-02-residue-cleanup-principles.md`
- `docs/bitter/2026-06-02-wrong-boundary-narrowness-principles.md`
- `docs/bitter/2026-06-25-built-in-product-interface-principles.md`
- `docs/bitter/2026-06-25-end-to-end-contract-slice-principles.md`

映射到本次改造的硬规则：

| Principle | 本次要求 |
|---|---|
| Tool/skill layering | 不用 prompt、role prose、retry guidance 掩盖 browser capability contract 不完整。 |
| Test resource lifecycle | 任何启动 broker/browser/upstream/fake Chrome 的测试必须证明 pid、socket、marker、tmp state 清干净。 |
| Parallel boundary | 不在 `search`、`cockpit_proxy`、release handler 各自复制 ensure 逻辑；browser acquisition 归一个 owner。 |
| Residue cleanup | 定义旧语义/新语义，对 live surfaces 做 scoped no-hit scan；历史 memo 不算残留。 |
| Wrong-boundary narrowness | 不接受“只把 `ROOT` 改成 `BUDDYSWITCH_REPO_ROOT`”这种窄但边界错误的补丁。 |
| Built-in product interface | browser runtime 是产品内建 capability；CLI、broker、cockpit、search 都是 projection。 |
| End-to-end slice | 必须证明 `actor asks to open browser URL -> system opens/reuses page -> actor receives observable result`。 |

## 3. Current Code Findings

| Priority | Finding | Evidence | Why It Matters |
|---|---|---|---|
| P0 | `search__open_browser` 在缺少 `browser_port` 时触发 browser ensure。 | `scripts/env/tools/search/_impl.py:800-817` | search wrapper 变成 acquisition owner，破坏 runtime/control-plane 边界。 |
| P0 | runtime-projected `cdp_browser_session.py` 通过 `__file__` 推导 source root，并 shell 到 `buddyswitch-codex env browser ensure`。 | `scripts/env/cdp_browser_session.py:17-19`, `:94-100`, `:128-160` | actor runtime 能间接感知 source root 和 launcher CLI。 |
| P0 | `chrome_devtools_cockpit_proxy.py` 在 first tools/call 时也 shell 到 `buddyswitch-codex env browser ensure`。 | `tools/launcher/chrome_devtools_cockpit_proxy.py:204-232`, `:994-1014` | cockpit projection 同样绕过 broker/control-plane service boundary。 |
| P0 | runtime broker 当前只支持 `env.tool`、`ping`、`status`，没有 browser capability API。 | `scripts/runtime_kernel/dispatcher.py:217-292` | runtime 没有正确入口，只能借助 helper/CLI 绕路。 |
| P1 | `browser_cockpit.sh` 把 endpoint ensure 和 cockpit MCP 注册耦合在 bootstrap。 | `tools/launcher/browser_cockpit.sh:404-430`, `:830-870`, `:1008-1066` | browser acquisition 和 MCP projection 不是同一责任，会导致 ensure 顺手修 MCP。 |
| P1 | `browser_release_handler.py` release 也 shell 到 launcher CLI。 | `tools/launcher/browser_release_handler.py:152-155` | release 与 acquire 一样缺少直接 control-plane owner API。 |
| P1 | 测试在保护旧边界。 | `tests/test_browser_cockpit_proxy.py:642-694`, `tests/test_search_env_tool.py:501-535`, `:1004-1015` | mock 掉 ensure 并断言 repo root 传递，会让错误设计继续绿。 |
| P1 | live evidence 已复现 sparse workspace launcher path failure。 | `docs/spec/2026-07-02-browser-cockpit-resource-stress-matrix/logs/stress-summary.json` | 证明问题穿过真实 MCP path，不是单元测试臆测。 |

## 4. Target Architecture

目标模块边界：

```text
Actor runtime surfaces
  search__open_browser
  chrome-devtools-cockpit tool calls
        |
        | broker RPC only; no source root, no launcher CLI
        v
Runtime broker
  validates actor_id, role, instance status, permission boundary
        |
        | in-process/control-plane call
        v
Browser runtime manager
  owns acquire/status/release/stop
  owns port/profile/log/pid markers
  starts Chrome and records browser_port
        |
        v
Browser session data-plane
  owns list/reuse/open/page limit/idle TTL
        |
        v
Chrome CDP endpoint
```

Projection ownership:

| Module | Target Responsibility | Explicitly Not Responsible For |
|---|---|---|
| `buddyswitch-codex env browser *` | Human/debug/admin CLI projection over browser runtime manager. | Not a service endpoint called by actor runtime. |
| runtime broker | Single IPC boundary for runtime browser capability requests. | Not browser implementation details scattered in env tools. |
| browser runtime manager | Acquire/status/release/stop, port allocation, Chrome startup, marker cleanup, instance `browser_port`. | Not search semantics or cockpit tool wording. |
| browser session data-plane | CDP page list, reuse, create, page limit, idle TTL, close-on-failure cleanup. | Not source root, launcher CLI, process acquisition. |
| `search__open_browser` | Validate query/engine, build search URL, request `browser.open_url`, map response to search ToolResult. | Not ensure, release, port allocation, direct CDP, launcher path. |
| `chrome-devtools-cockpit` proxy | MCP projection and page interaction; acquire via broker/control-plane API before upstream calls. | Not subprocess ensure, not MCP registration repair. |
| instance start/bootstrap | Register cockpit MCP projection. | Not lazy browser endpoint acquisition. |

## 5. Broker Contract Target

Add browser capability methods under runtime broker. This is the stable boundary; implementation can remain monolith-first behind it.

Required methods:

```text
browser.acquire
  params: actor_id, active_role, reason
  returns: ok, browser_url for authorized launcher-owned consumers, browser_port, state_changed, durability

browser.open_url
  params: actor_id, active_role, target_url, source_tool
  returns: ok, target_url, page_opened, page_reused, blocked, page_count, target_id, idle fields
  search runtime should not receive source root or launcher path

browser.status
  params: actor_id, active_role
  returns: recorded browser state, readiness, ownership, page summary

browser.release
  params: actor_id, active_role, reason
  returns: handled/skipped/failure with observable skip reason
```

Contract behavior:

- broker validates actor, role, active instance status before browser work.
- `browser.open_url` is the preferred path for `search__open_browser` because search does not need raw `browser_url`.
- cockpit proxy may use `browser.acquire` because it must start upstream `chrome-devtools-mcp` with a browser endpoint; this is still launcher-owned projection code, not search runtime logic.
- all methods return structured error fields: `permission_boundary`, `state_changed`, `durability`, `why_blocked`, `allowed_next_action_options` when appropriate.

## 6. No-Residual / No-Dual-Track Rules

Old live semantics to delete:

```text
runtime helper ensures browser
runtime code computes source launcher root
runtime code executes buddyswitch-codex env browser ensure
cockpit proxy executes buddyswitch-codex env browser ensure
BUDDYSWITCH_BROWSER_COCKPIT_ENSURE_COMMAND in live runtime tests
search.open_browser retry guidance that implies search owns browser ensure
browser ensure repairs cockpit MCP registration
release handler shells to buddyswitch-codex env browser release
```

New live semantics:

```text
runtime asks broker for browser capability
broker/control-plane owns browser acquisition
browser manager owns lifecycle
browser session owns page data-plane
search is a URL wrapper
cockpit is a browser interaction projection
CLI is human/debug projection only
```

Scoped residue scans must exclude historical docs and old memos, but include runtime source, launcher source, tool definitions, live roles/skills, and tests.

## 7. Rebuild Plan

### Phase 1: Add failing contract tests first

Purpose: force the target boundary before implementation.

Test targets:

- `tests/test_search_env_tool.py`
  - `search__open_browser` with missing `browser_port` must call broker/browser client, not `browser_session.ensure_browser_url_for_instance`.
  - error path must not contain `workspace/buddyswitch-codex`, source root, or launcher CLI path.

- `tests/test_runtime_broker.py`
  - unsupported browser methods fail before implementation.
  - then add expected `browser.acquire`, `browser.open_url`, `browser.status`, `browser.release` request/response contract.
  - actor mismatch, role mismatch, inactive instance, invalid URL, and manager failure must return structured boundary errors.

- `tests/test_browser_cockpit_proxy.py`
  - first browser `tools/call` acquires through broker/client, not subprocess CLI.
  - `initialize`, `notifications/initialized`, and `tools/list` still do not acquire browser.
  - `new_page` keeps local page data-plane behavior after acquisition.

- `tests/test_browser_page_expired_handler.py` and `tests/test_browser_lazy_release_integration.py`
  - release path calls browser manager/control-plane API, not CLI subprocess.
  - skip reasons remain observable.

- `tests/test_repo_consistency.py` or a focused boundary test
  - no runtime-projected browser code contains `ROOT / "buddyswitch-codex"`, `BUDDYSWITCH_BROWSER_COCKPIT_ENSURE_COMMAND`, or `subprocess.run(... env browser ensure ...)`.

### Phase 2: Create browser runtime manager as the product core

Files:

- create `tools/launcher/browser_runtime_manager.py`
- modify `buddyswitch-codex`
- reduce or replace relevant implementation in `tools/launcher/browser_cockpit.sh`

Required shape:

- browser manager exposes `acquire(instance_root, actor_id, options)`, `status(...)`, `release(...)`, `stop(...)`.
- implementation owns port selection, Chrome start, usable ready page, `browser_port` update, marker cleanup, ownership checks.
- CLI calls manager directly as a projection.
- shell implementation must not remain a parallel authority after the phase is complete.

Acceptance:

- `buddyswitch-codex env browser ensure/release/status` still works for human/debug use.
- no actor runtime/cockpit/search code calls the CLI for browser lifecycle.

### Phase 3: Add broker browser methods

Files:

- modify `scripts/runtime_kernel/dispatcher.py`
- modify `scripts/runtime_kernel/client.py`
- modify `scripts/runtime_kernel/protocol.py` only if envelope/schema helpers are needed
- add focused tests in `tests/test_runtime_broker.py`

Required behavior:

- `browser.acquire` invokes browser manager inside control-plane authority.
- `browser.open_url` invokes acquire when needed, then browser session data-plane open/reuse.
- broker response includes actual state effect, not only `ok=true`.
- source root remains inside broker/control-plane process environment and is never projected into actor-facing response.

Acceptance:

```text
consumer action: actor runtime sends browser.open_url
system path: broker validates actor and invokes browser manager/session
observable result: actor receives opened/reused/blocked response with target_url and page state
```

### Phase 4: Split runtime browser session data-plane from acquisition

Files:

- modify `scripts/env/cdp_browser_session.py`
- update tests in `tests/test_cdp_browser_session.py`

Required changes:

- keep pure page data-plane: URL validation, target list read, exact reuse, page limit, `Target.createTarget`, idle TTL registration, close-on-failure cleanup.
- remove `ensure_browser_url_for_instance`.
- remove `launcher_env_for_instance_root`.
- remove module-level `ROOT` usage for launcher CLI.
- if a helper still needs instance payload browser URL read, keep it pure and local.

Acceptance:

- data-plane tests still pass.
- acquisition-related imports and subprocess calls are gone from runtime-projected browser session.

### Phase 5: Rewrite search as broker browser.open_url caller

Files:

- modify `scripts/env/tools/search/_impl.py`
- modify `scripts/env/tools/search/tool.py`
- modify `tests/test_search_env_tool.py`
- modify `tests/test_env_tool_response_contract.py`
- modify `tests/test_env_tool_semantic_contract.py`

Required behavior:

- query/engine validation and search URL construction stay in search.
- browser work is one broker client call to `browser.open_url`.
- response maps broker fields into search-specific ToolResult wording.
- failures use broker structured error fields; no retry guidance that says search should ensure browser.

Acceptance:

- `search__open_browser` succeeds in sparse actor runtime with no workspace `buddyswitch-codex`.
- `search__open_browser` failure path never leaks source root or launcher path.
- search tests no longer mock `browser_session.ensure_browser_url_for_instance`.

### Phase 6: Rewrite cockpit proxy acquisition path

Files:

- modify `tools/launcher/chrome_devtools_cockpit_proxy.py`
- modify `tests/test_browser_cockpit_proxy.py`

Required behavior:

- remove `ensure_browser_url` subprocess logic.
- before browser `tools/call`, call broker/control-plane browser acquire client.
- keep local `new_page` mutation through browser session data-plane after acquired browser URL is available.
- keep upstream initialization lazy: no acquisition on `initialize`, `notifications/initialized`, or `tools/list`.

Acceptance:

- first `list_pages` or `new_page` browser call acquires through broker, starts upstream with acquired browser URL, and returns expected result.
- no test asserts `BUDDYSWITCH_REPO_ROOT` was passed to a fake ensure subprocess.

### Phase 7: Decouple MCP registration from browser acquisition

Files:

- modify `tools/launcher/browser_cockpit.sh`
- modify instance start/bootstrap tests in `tests/test_browser_cockpit_launcher.py` and `tests/test_buddyswitch_launcher.py`

Required behavior:

- instance start registers `chrome-devtools-cockpit` MCP projection when role/profile allows it.
- browser manager `acquire` only ensures browser endpoint/runtime state.
- ensure/release no longer repairs or removes MCP registration as side effect.

Acceptance:

- starting an instance produces correct MCP config for cockpit.
- acquiring browser does not mutate MCP config except through explicitly owned setup path.

### Phase 8: Rewrite release path to manager API

Files:

- modify `tools/launcher/browser_release_handler.py`
- modify `tools/launcher/browser_page_expired_handler.py` only where scheduling/observable results require it
- modify release tests

Required behavior:

- release handler calls browser manager/control-plane API directly.
- it does not shell to `buddyswitch-codex env browser release`.
- skip reasons stay observable: `parent_turn_running`, `page_idle_targets_remain`, `browser_port_missing`, `real_user_page_present`.

Acceptance:

- release tests prove no CLI subprocess.
- resource lifecycle tests prove pid/pgid/socket/marker cleanup.

### Phase 9: Residue cleanup and live surface rewrite

Files/surfaces:

- `scripts/env/**`
- `tools/launcher/**`
- `scripts/runtime_kernel/**`
- `tools/launcher/assets/roles/**/AGENTS.md`
- live skills and contracts that teach browser use
- relevant tests under `tests/`

Required scans:

```bash
rg -n 'ensure_browser_url_for_instance|BUDDYSWITCH_BROWSER_COCKPIT_ENSURE_COMMAND|ROOT / "buddyswitch-codex"|env browser ensure|env browser release' scripts/env tools/launcher tests -S
```

Expected rule:

- allowed hits only in CLI help/projection tests that explicitly validate human/admin CLI behavior.
- no hits in runtime-projected browser code, search, cockpit proxy acquisition path, release handler, or tests that define actor runtime behavior.

Additional live surface scan:

```bash
rg -n 'Retry search\.open_browser after browser ensure succeeds|search.*owns.*browser|search-first browser|workspace/buddyswitch-codex' scripts/env tools/launcher tests tools/launcher/assets -S
```

Expected result:

- no live guidance teaches old browser ensure ownership.

### Phase 10: End-to-end verification

Required contract slice:

```text
actor calls search__open_browser with no browser_port
  -> runtime uses broker browser.open_url
  -> browser manager acquires Chrome
  -> browser session opens or reuses target URL
  -> actor receives ok result with page state
  -> no source root or launcher path is visible to actor runtime
  -> cleanup returns resources to baseline
```

Verification commands should include focused tests first, then broader groups:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider tests/test_runtime_broker.py
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider tests/test_search_env_tool.py
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider tests/test_browser_cockpit_proxy.py
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider tests/test_browser_cockpit_launcher.py
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider tests/test_browser_lazy_release_integration.py
```

Resource checks:

- no leaked fake Chrome process
- no leaked upstream `chrome-devtools-mcp` process owned by test helper
- no stale runtime broker socket
- no stale pid/pgid marker under instance runtime
- no stale page idle locks after release/stop

## 8. Acceptance Criteria

The rebuild is complete only when all items are true:

- `search__open_browser` no longer imports or calls browser acquisition helpers from `cdp_browser_session.py`.
- `scripts/env/cdp_browser_session.py` contains no launcher CLI subprocess path.
- `chrome_devtools_cockpit_proxy.py` contains no browser ensure subprocess path.
- `browser_release_handler.py` contains no `buddyswitch-codex env browser release` subprocess path.
- runtime broker exposes and tests browser capability methods.
- browser runtime manager is the single owner of acquire/status/release/stop.
- CLI remains as human/admin projection and is not called by actor runtime.
- MCP registration is not coupled to browser endpoint acquisition.
- scoped residue scans prove no live surface teaches old semantics.
- end-to-end actor path proves open/reuse result from sparse runtime without source root leakage.
- service-starting tests prove resource cleanup.

## 9. Review Checklist Before Implementation Starts

- Confirm this plan supersedes the older search/session-local plans for browser acquisition ownership.
- Keep the existing HTML visual companion open while reviewing implementation PRs.
- Do not accept a patch that only swaps `__file__` root derivation for `BUDDYSWITCH_REPO_ROOT`.
- Do not accept a patch that leaves both old CLI subprocess ensure and new broker acquire live.
- Do not accept tests that mock away the actor runtime sparse workspace failure without a contract test proving the real boundary.
- Treat every old-path test hit as either an explicit CLI projection test or unfinished cleanup.

