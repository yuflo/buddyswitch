# Cockpit Browser Session Forward Upgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `chrome-devtools-cockpit` / browser-session the single BuddySwitch browser-use foundation, and delete the standalone browser implementation inside `search.open_browser`.

**Architecture:** Browser lifecycle and page ownership move into one browser-session core. `chrome-devtools-cockpit` becomes the primary actor-facing browser projection over that core. `search.open_browser` remains only a search-specific query-to-URL wrapper and must call the shared browser-session primitive instead of owning browser ensure, page open, reuse, TTL, or cleanup.

**Tech Stack:** Python runtime helpers under `scripts/env/`, launcher proxy and daemon handlers under `tools/launcher/`, BuddySwitch env tool definitions under `scripts/env/tools/search/`, role and skill Markdown live surfaces, Python unit/integration tests, scoped residue scans.

---

## Task Goal Restatement

The target state is not "make search.open_browser safer." The target state is:

```text
actor browser work
  -> chrome-devtools-cockpit
  -> browser-session core
  -> Chrome DevTools browser/runtime lifecycle
```

Search is allowed only here:

```text
query + engine
  -> search URL
  -> browser-session open_or_reuse_page
  -> search-specific ToolResult wording
```

The final system must have no long-lived dual path where cockpit and search each implement browser opening, page reuse, page limit, idle TTL, or cleanup.

## Six Upgrade Goals

1. **Harden cockpit ensure / release root handling**
   - `chrome-devtools-cockpit` must derive browser runtime from the real instance root, not actor `HOME`.
   - `BrowserReleaseHandler` must use the same root propagation rule.
   - Actor `HOME=<instance>/home` with missing `BUDDYSWITCH_SHARED_ROOT` must not produce nested `.codex-buddyswitch` paths.

2. **Extract one browser-session page primitive**
   - Add one shared `open_or_reuse_page` flow for target read, exact reuse, page limit, new page creation, idle refresh, current page mark, and failure cleanup.
   - `chrome-devtools-cockpit.new_page` and `search.open_browser` must both use it.

3. **Make browser state actor-visible through cockpit**
   - Actors must be able to see current pages, page identifiers, target identifiers, titles, URLs, selected/current state, reused/opened state, and TTL/idle hints from cockpit responses.
   - Tool descriptions must teach cockpit as the browser-session entrypoint, not only a non-activation patch.

4. **Unify resource management**
   - Page limit, reuse, TTL refresh, current-page state, close cleanup, and release scheduling must be owned by browser-session.
   - Blank `new_page` must be explicitly rejected or handled by the same page limit and TTL path.

5. **Delete the standalone search.open_browser browser implementation**
   - Remove search-owned browser ensure, endpoint lookup, instance payload reload, page target reads, page gate, direct CDP `Target.createTarget`, idle registration, and failure cleanup.
   - Do not keep a fallback independent open path inside search.

6. **Move roles, skills, and tests to cockpit-first**
   - Role AGENTS, market contract, market skills, and consistency tests must stop teaching search-first browser discovery.
   - Search may remain documented only as an optional search URL wrapper on top of cockpit/browser-session.

## Bitter Principles Applied

Read sources:

- `docs/bitter/2026-05-18-tool-skill-layering-principles.md`
- `docs/bitter/2026-05-26-test-resource-lifecycle-principles.md`
- `docs/bitter/2026-05-28-parallel-change-boundary-principles.md`
- `docs/bitter/2026-06-02-residue-cleanup-principles.md`
- `docs/bitter/2026-06-02-wrong-boundary-narrowness-principles.md`
- `docs/bitter/2026-06-25-built-in-product-interface-principles.md`
- `docs/bitter/2026-06-25-end-to-end-contract-slice-principles.md`

Hard rules for this upgrade:

- Fix the owning runtime contract. Do not compensate with larger prompts, role instructions, or skill prose.
- No semantic replacement is complete while live surfaces still teach the old search-first semantics.
- No broad suite claim is valid unless browser/app-server/process resources return to baseline.
- A narrow search-side patch is still wrong if it preserves the wrong boundary.
- Browser-use is a built-in product capability: product core first, interface projections second.
- Sliced implementation must still prove the end-to-end actor loop:

```text
actor asks to browse
  -> cockpit opens or reuses a page through browser-session
  -> actor lists/selects/inspects the page
  -> idle/release lifecycle is registered and cleaned
```

## Current Code Audit

### Browser root and ensure risk

- `tools/launcher/env.sh:20-23` derives `BUDDYSWITCH_SHARED_ROOT` from `BUDDYSWITCH_SOURCE_HOME` or `HOME`.
- `tools/launcher/env.sh:342-357` then binds actor-local `HOME` under the instance root.
- `tools/launcher/chrome_devtools_cockpit_proxy.py:189-216` runs `buddyswitch-codex env browser ensure --instance <actor_id>` without explicitly passing the real shared root derived from the known `--instance-root`.
- `tools/launcher/browser_release_handler.py:105-108` only defaults `BUDDYSWITCH_REPO_ROOT`; release has the same missing shared-root propagation risk.
- Live actor evidence showed cockpit failing with a nested path:

```text
.../instances/act-market-b31b9180fc69/home/.codex-buddyswitch/instances/act-market-b31b9180fc69/instance.json
```

### Existing cockpit/browser-session capability

- `tools/launcher/chrome_devtools_cockpit_proxy.py:293-365` owns `new_page`, `select_page`, and page-scoped metadata.
- `tools/launcher/chrome_devtools_cockpit_proxy.py:403-442` patches only non-activation descriptions for `new_page` and `select_page`.
- `tools/launcher/chrome_devtools_cockpit_proxy.py:522-635` patches responses to refresh idle/current page metadata.
- `scripts/env/cdp_browser_session.py:73-115` owns page limit and exact URL reuse gate.
- `scripts/env/cdp_browser_lifecycle.py:56-87` duplicates page target reads and created-target resolution.
- `scripts/env/cdp_browser_lifecycle.py:373-482` owns idle refresh, current page marking, release scheduling, and target forget cleanup.

### Standalone search browser implementation to delete

- `scripts/env/tools/search/_impl.py:70-78` has search-private endpoint lookup.
- `scripts/env/tools/search/_impl.py:81-88` has search-private instance payload reload.
- `scripts/env/tools/search/_impl.py:91-120` has search-private browser ensure with `BUDDYSWITCH_SEARCH_BROWSER_ENSURE_COMMAND`.
- `scripts/env/tools/search/_impl.py:198-233` shells to `scripts/env/cdp_background_page.py` for direct CDP `Target.createTarget`.
- `scripts/env/tools/search/_impl.py:875-1016` owns the open/reuse/register/cleanup flow.
- `tests/test_search_env_tool.py:517-620` currently protects direct `Target.createTarget`, search-owned idle registration, and search-owned close-on-registration-failure behavior.
- `tests/test_search_env_tool.py:843-950` currently protects search-owned ensure and the `cdp_background_page.py` dependency.

### Live surface residue

- `tools/launcher/assets/roles/{design,dev,market,pm,test}/AGENTS.md` list `search__open_browser` as a preferred native env MCP tool.
- `framework/contracts/market.md:9` says discovery starts from `search__open_browser`.
- 15 market P0 skills under `buddyswitch/skills/market/*/SKILL.md` say to use native `search__open_browser` first, then continue in cockpit.
- `tests/test_runtime_skills.py:244-254` requires market skills to contain `search__open_browser`.
- `tests/test_buddyswitch_launcher.py:1946-1950` requires native web_search rejection copy to mention `search__open_browser`.
- `scripts/env/tools/search/tool.py:159-225` defines `search.open_browser` as an open/browser action rather than a search wrapper projection.

## Non-Negotiable Deletion Target

The following search-owned browser items must be removed or moved to browser-session. They must not remain in search as fallback, compatibility, or alternate behavior:

- `_ensure_browser_runtime`
- `_browser_endpoint`
- `_reload_instance_payload`
- `_open_browser_page`
- `BUDDYSWITCH_SEARCH_BROWSER_ENSURE_COMMAND`
- direct `cdp_background_page.py` invocation
- direct `Target.createTarget` handling
- direct page target list / gate calls from search
- direct `refresh_page_idle` / `close_page_target` lifecycle handling from search
- search-specific open/reuse/register/cleanup branching

Allowed in search after migration:

- query validation
- engine validation
- query-to-search-URL construction
- call into browser-session
- search-specific `ToolResult` wording and error mapping

## Target File Structure

### Browser-session core

- Modify `scripts/env/cdp_browser_session.py`
  - Own deterministic browser URL ensure for an instance.
  - Own target list normalization.
  - Own `open_or_reuse_page`.
  - Own typed result objects for opened, reused, blocked, verification failed, ensure failed, open failed, registration failed.

- Modify `scripts/env/cdp_browser_lifecycle.py`
  - Expose a public `create_background_page_target(browser_url, target_url)` helper using `_send_browser_command`.
  - Keep idle, current page, close target, forget target, and release scheduling here.

### Cockpit projection

- Modify `tools/launcher/chrome_devtools_cockpit_proxy.py`
  - Use browser-session ensure instead of local ensure command construction.
  - Use browser-session `open_or_reuse_page` for `new_page`.
  - Reject blank `new_page.url`.
  - Patch `list_pages`, `new_page`, `select_page`, and page-scoped responses with actor-visible browser-session state.
  - Update tool descriptions to say cockpit is the managed browser-session entrypoint.

- Modify `tools/launcher/browser_release_handler.py`
  - Use the same deterministic instance-root/shared-root env rule as browser-session ensure.

### Search wrapper

- Modify `scripts/env/tools/search/_impl.py`
  - Keep query and engine handling.
  - Call browser-session `ensure_browser_url_for_instance` and `open_or_reuse_page`.
  - Delete search-private browser lifecycle helpers and branches.

- Modify `scripts/env/tools/search/tool.py`
  - Reword `search.open_browser` as a search URL wrapper over browser-session.
  - Fix `reads`, `writes`, `does_not_write`, `use_when`, and `do_not_use_when` so it no longer claims ownership of browser fundamentals.

### Live surfaces

- Modify `tools/launcher/assets/roles/{design,dev,market,pm,test}/AGENTS.md`
- Modify `framework/contracts/market.md`
- Modify `buddyswitch/skills/market/*/SKILL.md`
- Modify native web_search rejection copy in launcher shell/runtime surface if it currently points users to search-first browsing.

### Tests

- Modify `tests/test_browser_cockpit_proxy.py`
- Modify `tests/test_browser_cockpit_launcher.py`
- Modify `tests/test_browser_lazy_release_integration.py`
- Modify `tests/test_browser_page_expired_handler.py`
- Modify `tests/test_cdp_browser_session.py`
- Modify `tests/test_search_env_tool.py`
- Modify `tests/test_env_tool_response_contract.py`
- Modify `tests/test_env_tool_semantic_contract.py`
- Modify `tests/test_runtime_skills.py`
- Modify `tests/test_buddyswitch_launcher.py`
- Modify `tests/test_repo_consistency.py`

## Implementation Plan

### Task 1: Lock cockpit root determinism before changing behavior

**Files:**

- Modify: `tests/test_browser_cockpit_proxy.py`
- Modify: `tests/test_browser_page_expired_handler.py`
- Modify: `tools/launcher/chrome_devtools_cockpit_proxy.py`
- Modify: `tools/launcher/browser_release_handler.py`
- Modify: `scripts/env/cdp_browser_session.py`

- [ ] **Step 1: Add failing proxy regression for actor HOME root drift**

Add a focused test in `tests/test_browser_cockpit_proxy.py` that starts the proxy with:

```python
env.pop("BUDDYSWITCH_SHARED_ROOT", None)
env.pop("BUDDYSWITCH_SOURCE_HOME", None)
env["HOME"] = str(instance_root / "home")
env["CODEX_HOME"] = str(instance_root / "codex-home")
```

The fake ensure command must record:

```python
{
    "BUDDYSWITCH_SHARED_ROOT": os.environ.get("BUDDYSWITCH_SHARED_ROOT"),
    "BUDDYSWITCH_REPO_ROOT": os.environ.get("BUDDYSWITCH_REPO_ROOT"),
    "argv": sys.argv,
}
```

Expected before implementation: FAIL because ensure has no real shared-root env and would derive it from actor `HOME`.

- [ ] **Step 2: Add failing release-handler regression for the same root rule**

Add a test in `tests/test_browser_page_expired_handler.py` under `BrowserReleaseHandlerTests` that:

- creates an instance root shaped as `<shared_root>/instances/<actor_id>`;
- sets process `HOME` to `<instance_root>/home`;
- clears `BUDDYSWITCH_SHARED_ROOT` and `BUDDYSWITCH_SOURCE_HOME`;
- monkeypatches `subprocess.run` to capture `env`;
- asserts `env["BUDDYSWITCH_SHARED_ROOT"] == str(shared_root)`.

Expected before implementation: FAIL because `_launcher_env()` does not set shared root.

- [ ] **Step 3: Implement shared deterministic launcher env**

In `scripts/env/cdp_browser_session.py`, add:

```python
def shared_root_for_instance_root(instance_root: Path) -> Path:
    root = Path(instance_root)
    if root.name.startswith("act-") and root.parent.name == "instances":
        return root.parent.parent
    raise BrowserSessionError(f"cannot derive shared root from instance root: {root}")


def launcher_env_for_instance_root(instance_root: Path, base_env: dict[str, str] | None = None) -> dict[str, str]:
    env = dict(base_env or os.environ)
    shared_root = shared_root_for_instance_root(Path(instance_root))
    env["BUDDYSWITCH_SHARED_ROOT"] = str(shared_root)
    env.setdefault("BUDDYSWITCH_SOURCE_HOME", str(shared_root.parent))
    env.setdefault("BUDDYSWITCH_REPO_ROOT", str(ROOT))
    return env
```

Use a concrete `BrowserSessionError` class in the same file. Import `os` and `Path` there.

- [ ] **Step 4: Use shared env in cockpit ensure**

Replace the default `subprocess.run(..., env=...)` omission in `tools/launcher/chrome_devtools_cockpit_proxy.py` with:

```python
env=cdp_browser_session.launcher_env_for_instance_root(root)
```

Keep `BUDDYSWITCH_BROWSER_COCKPIT_ENSURE_COMMAND` only as a test override, but still pass the deterministic env.

- [ ] **Step 5: Use shared env in release handler**

Replace `_launcher_env()` in `tools/launcher/browser_release_handler.py` with an instance-root aware helper:

```python
def _launcher_env(instance_root: Path) -> dict[str, str]:
    return browser_session.launcher_env_for_instance_root(instance_root)
```

Then pass `_launcher_env(root)` into `subprocess.run`.

- [ ] **Step 6: Run focused root tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider \
  tests/test_browser_cockpit_proxy.py::BrowserCockpitProxyTests::test_first_tools_call_ensures_browser_and_starts_upstream \
  tests/test_browser_cockpit_proxy.py::<new-root-drift-test> \
  tests/test_browser_page_expired_handler.py::<new-release-root-test>
```

Expected: PASS.

### Task 2: Build the browser-session open_or_reuse_page primitive

**Files:**

- Modify: `scripts/env/cdp_browser_session.py`
- Modify: `scripts/env/cdp_browser_lifecycle.py`
- Modify: `tests/test_cdp_browser_session.py`

- [ ] **Step 1: Add failing unit tests for the primitive**

In `tests/test_cdp_browser_session.py`, add tests for:

- exact URL reuse refreshes current page idle and does not create a target;
- new URL below limit creates one background target and refreshes current page idle;
- hard limit blocks without creating a target;
- target-list verification failure returns typed failure without creating a target;
- idle registration failure closes the newly created target;
- blank URL is rejected before target-list read.

Each test must assert the result kind explicitly:

```python
self.assertEqual(result.kind, "opened")
self.assertEqual(result.target_url, "https://example.com/new")
self.assertEqual(result.target_id, "target-new")
self.assertTrue(result.idle_refreshed)
```

Expected before implementation: FAIL because the primitive does not exist.

- [ ] **Step 2: Add public CDP create helper**

In `scripts/env/cdp_browser_lifecycle.py`, add:

```python
def create_background_page_target(browser_url: str, target_url: str, timeout_seconds: float = 5.0) -> str:
    result = _send_browser_command(
        browser_url,
        "Target.createTarget",
        {"url": target_url, "background": True},
        timeout_seconds,
    )
    target_id = result.get("targetId")
    if not isinstance(target_id, str) or not target_id.strip():
        raise BrowserLifecycleError("Target.createTarget response missing targetId")
    return target_id.strip()
```

- [ ] **Step 3: Add typed browser-session result classes**

In `scripts/env/cdp_browser_session.py`, add result dataclasses:

```python
@dataclass(frozen=True)
class BrowserSessionOpenResult:
    kind: Literal["opened", "reused", "blocked", "verification_failed", "open_failed", "registration_failed", "invalid_request"]
    target_url: str
    page_count: int | None
    projected_page_count: int | None = None
    target_id: str | None = None
    page_opened: bool = False
    page_reused: bool = False
    idle_refreshed: bool = False
    idle_seconds: int | None = None
    idle_expires_at: str | None = None
    message: str | None = None
```

- [ ] **Step 4: Implement `open_or_reuse_page`**

In `scripts/env/cdp_browser_session.py`, implement:

```python
def open_or_reuse_page(*, instance_root: Path, browser_url: str, target_url: str) -> BrowserSessionOpenResult:
    ...
```

Required behavior:

- reject blank `target_url` as `invalid_request`;
- call `evaluate_page_open_gate`;
- on `reuse`, call `browser_lifecycle.refresh_current_page_idle`;
- on `block`, return `blocked`;
- on `verification_failed`, return `verification_failed`;
- on `allow`, call `browser_lifecycle.create_background_page_target`;
- after create, call `browser_lifecycle.refresh_current_page_idle`;
- if idle registration fails after create, call `browser_lifecycle.close_page_target` and return `registration_failed`;
- never expose raw `browser_url` in the result.

- [ ] **Step 5: Run primitive tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider tests/test_cdp_browser_session.py
```

Expected: PASS.

### Task 3: Route cockpit new_page and actor-visible state through browser-session

**Files:**

- Modify: `tools/launcher/chrome_devtools_cockpit_proxy.py`
- Modify: `tools/launcher/assets/chrome-devtools-mcp-1.1.1-tools.json` only if the static upstream description itself must change; prefer proxy patching.
- Modify: `tests/test_browser_cockpit_proxy.py`

- [ ] **Step 1: Add failing cockpit tests for local browser-session new_page**

Replace or add tests in `tests/test_browser_cockpit_proxy.py` proving:

- `new_page` does not forward to upstream when browser-session opens a page successfully;
- `new_page` exact URL reuse does not forward to upstream;
- blank `new_page` is rejected locally;
- response text includes target URL, target id, opened/reused state, and idle TTL hint;
- `list_pages` response includes a BuddySwitch browser-session summary with target id, URL, title, current marker, and idle state.

Expected before implementation: FAIL because current `new_page` forwards upstream and blank URL can bypass gate/registration.

- [ ] **Step 2: Import browser-session module directly**

In `tools/launcher/chrome_devtools_cockpit_proxy.py`, replace the narrow import:

```python
from env.cdp_browser_session import BROWSER_PAGE_LIMIT_BLOCK_TEXT, evaluate_page_open_gate
```

with:

```python
from env import cdp_browser_session as browser_session
from env.cdp_browser_session import BROWSER_PAGE_LIMIT_BLOCK_TEXT
```

- [ ] **Step 3: Rewrite `new_page` handling**

Change `mutate_tool_call` for `new_page` so it:

- still rejects `isolatedContext`;
- still requires `--instance-root`;
- rejects missing or blank `url`;
- calls `browser_session.open_or_reuse_page`;
- returns a local tool success/error response instead of forwarding upstream for open/reuse/block/failure outcomes.

Do not leave the old before/after upstream target tracking path active.

- [ ] **Step 4: Patch actor-visible descriptions**

In `patch_tool_list_message`, add descriptions for these tools:

- `new_page`: cockpit/browser-session opens or reuses a managed page, registers TTL, and does not activate the foreground browser.
- `list_pages`: use this to inspect current managed browser pages before opening more.
- `select_page`: selects an existing page without foreground activation and refreshes browser-session current page state.
- `take_snapshot` and `take_screenshot`: use after `list_pages` / `select_page` to see page content.
- `navigate_page`, `click`, `type_text`, `evaluate_script`, `wait_for`, `fill`, `press_key`: page-scoped browser-session actions that refresh idle state.

- [ ] **Step 5: Patch `list_pages` response with browser-session state**

Add metadata for `list_pages` in `mutate_tool_call`, then in response patching append a concise BuddySwitch state block based on CDP `/json/list` and `page_idle.json`:

```text
BuddySwitch browser-session state:
- current_target_id: target-123
- pages:
  - target_id: target-123
    title: Example
    url: https://example.com
    idle_expires_at: 2026-07-01T...
```

Keep the upstream `list_pages` content intact so upstream page ids remain visible.

- [ ] **Step 6: Run cockpit proxy tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider tests/test_browser_cockpit_proxy.py
```

Expected: PASS.

### Task 4: Delete search.open_browser standalone browser stack

**Files:**

- Modify: `scripts/env/tools/search/_impl.py`
- Modify: `scripts/env/tools/search/tool.py`
- Modify: `tests/test_search_env_tool.py`
- Modify: `tests/test_env_tool_response_contract.py`
- Modify: `tests/test_env_tool_semantic_contract.py`
- Modify: `tests/test_browser_lazy_release_integration.py`
- Modify: `tests/test_buddyswitch_launcher.py`

- [ ] **Step 1: Replace search behavior tests with wrapper tests**

In `tests/test_search_env_tool.py`, delete tests that require direct search-owned CDP behavior:

- `test_search_open_browser_creates_background_cdp_target`
- `test_search_open_browser_refreshes_idle_after_new_target`
- `test_search_open_browser_closes_new_target_when_idle_registration_fails`
- `test_search_open_browser_ensures_browser_when_port_missing`
- direct `cdp_background_page.py` dependency assertions

Replace them with tests that monkeypatch `search_impl.browser_session.open_or_reuse_page` and assert:

- search builds the correct target URL;
- search passes `instance_root`, ensured browser URL, and target URL to browser-session;
- opened result maps to `page_opened=True`;
- reused result maps to `page_reused=True`;
- blocked result maps to `E_SEARCH_BROWSER_PAGE_LIMIT_REACHED`;
- registration failure maps to `E_SEARCH_BROWSER_LIFECYCLE_REGISTRATION_FAILED`;
- no response leaks raw browser endpoint.

- [ ] **Step 2: Add a hard no-residue source scan test**

Add a test in `tests/test_search_env_tool.py`:

```python
def test_search_open_browser_has_no_standalone_browser_stack(self) -> None:
    text = (ROOT / "scripts" / "env" / "tools" / "search" / "_impl.py").read_text(encoding="utf-8")
    forbidden = [
        "_ensure_browser_runtime",
        "_browser_endpoint",
        "_reload_instance_payload",
        "_open_browser_page",
        "BUDDYSWITCH_SEARCH_BROWSER_ENSURE_COMMAND",
        "cdp_background_page.py",
        "Target.createTarget",
        "refresh_page_idle(",
        "close_page_target(",
        "evaluate_page_open_gate(",
    ]
    for pattern in forbidden:
        self.assertNotIn(pattern, text)
```

Expected before implementation: FAIL.

- [ ] **Step 3: Rewrite search implementation**

In `scripts/env/tools/search/_impl.py`:

- import browser-session as `browser_session`;
- keep `_normalize_query`, `_normalize_engine`, `_build_search_url`, and ToolResult mappers;
- delete `_ensure_browser_runtime`, `_browser_endpoint`, `_reload_instance_payload`, and `_open_browser_page`;
- in `open_browser_for_active_instance`, call browser-session ensure/open only;
- map `BrowserSessionOpenResult.kind` to search-specific `ToolResult` fields.

The wrapper must not call CDP or lifecycle helpers directly.

- [ ] **Step 4: Reword search tool contract**

In `scripts/env/tools/search/tool.py`, update `open_browser`:

- `description`: "Build a search URL and ask browser-session to open or reuse it."
- `mutates`: keep `browser_session`, but state that mutation is delegated to browser-session.
- `reads`: query payload, search profile, browser-session result.
- `writes`: no direct browser writes; delegated browser-session may open/reuse a page.
- `use_when`: "You need search-specific query URL construction before browser-session opens/reuses a page."
- `do_not_use_when`: "You need general browsing; use chrome-devtools-cockpit directly."

- [ ] **Step 5: Update lazy release integration**

In `tests/test_browser_lazy_release_integration.py`, stop using `search.open_browser` as the page-opening step for lifecycle smoke. Use `chrome-devtools-cockpit.new_page` as the browser-use path, then prove:

- page idle trigger is scheduled;
- page expiry closes the tracked target;
- release is scheduled after idle state is empty;
- next cockpit browser call restarts ensure/upstream cleanly.

- [ ] **Step 6: Run search and integration tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider \
  tests/test_search_env_tool.py \
  tests/test_env_tool_response_contract.py \
  tests/test_env_tool_semantic_contract.py \
  tests/test_browser_lazy_release_integration.py
```

Expected: PASS.

### Task 5: Move live surfaces to cockpit-first and remove search-first residue

**Files:**

- Modify: `tools/launcher/assets/roles/design/AGENTS.md`
- Modify: `tools/launcher/assets/roles/dev/AGENTS.md`
- Modify: `tools/launcher/assets/roles/market/AGENTS.md`
- Modify: `tools/launcher/assets/roles/pm/AGENTS.md`
- Modify: `tools/launcher/assets/roles/test/AGENTS.md`
- Modify: `framework/contracts/market.md`
- Modify: `buddyswitch/skills/market/*/SKILL.md`
- Modify: `tests/test_runtime_skills.py`
- Modify: `tests/test_repo_consistency.py`
- Modify: `tests/test_buddyswitch_launcher.py`

- [ ] **Step 1: Add failing residue scans**

Update `tests/test_runtime_skills.py` so market skills must include `chrome-devtools-cockpit` and must not include the exact old phrase:

```python
self.assertNotIn("use native `search__open_browser`", text)
self.assertNotIn("start discovery from native `search__open_browser`", text)
```

Add a scoped live-surface scan in `tests/test_repo_consistency.py` covering:

- `tools/launcher/assets/roles/*.md`
- `framework/contracts/*.md`
- `buddyswitch/skills/market/*/SKILL.md`

Forbidden exact phrases:

- `Start discovery from native \`search__open_browser\``
- `use native \`search__open_browser\` with a focused query, then continue discovery`
- `Use search.open_browser for browser-native discovery`
- `Call search.open_browser to open the target in the instance browser`

Expected before implementation: FAIL.

- [ ] **Step 2: Rewrite role AGENTS guidance**

For all role AGENTS, replace the preferred tool list language with cockpit-first wording:

```text
Use `chrome-devtools-cockpit` for browser pages: open, list, select, inspect, screenshot, navigate, and interact. Use `search__open_browser` only when you specifically need search query-to-URL construction before cockpit/browser-session opens or reuses that URL.
```

- [ ] **Step 3: Rewrite market contract**

In `framework/contracts/market.md`, replace search-first guidance with:

```text
Start browser discovery from `chrome-devtools-cockpit`. When a focused search query needs URL construction, `search__open_browser` may wrap the query, but browser page ownership and follow-up inspection remain in cockpit/browser-session.
```

- [ ] **Step 4: Rewrite all market P0 skills**

For each `buddyswitch/skills/market/*/SKILL.md`, replace the execution-order sentence with:

```text
1. Before forming external market claims, use `chrome-devtools-cockpit` to open, list, select, and inspect browser pages. Use `search__open_browser` only as a query-to-URL wrapper when the task specifically starts from a search query.
```

- [ ] **Step 5: Update native web_search rejection copy**

In the launcher surface tested by `tests/test_buddyswitch_launcher.py:1946-1950`, stop making `search__open_browser` the replacement for native `web_search`. The copy should point to:

```text
Native Codex web_search is disabled in BuddySwitch product sessions.
Use chrome-devtools-cockpit for browser-native discovery.
Use search__status for search capability status.
Use search__open_browser only for search query URL construction.
```

- [ ] **Step 6: Run surface tests and scans**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider \
  tests/test_runtime_skills.py \
  tests/test_repo_consistency.py \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_native_web_search_is_rejected_for_runtime_roles
```

Run exact scans:

```bash
rg -n "Start discovery from native `search__open_browser`|use native `search__open_browser` with a focused query, then continue discovery|Use search\\.open_browser for browser-native discovery|Call search\\.open_browser to open the target in the instance browser" \
  tools/launcher/assets/roles framework/contracts buddyswitch/skills/market scripts/env/tools/search
```

Expected: pytest PASS and `rg` returns no matches.

### Task 6: Prove the end-to-end cockpit-first browser loop

**Files:**

- Modify: `tests/test_browser_lazy_release_integration.py`
- Modify: `tests/test_browser_cockpit_launcher.py`
- Modify: `tests/test_browser_cockpit_proxy.py`
- Optional create: `docs/memo/2026-07-01-cockpit-browser-session-upgrade-acceptance.md` after implementation.

- [ ] **Step 1: Add one contract sentence to test docstring or test name**

The acceptance test must prove:

```text
cockpit new_page opens or reuses a managed page through browser-session
  -> cockpit list_pages exposes the page to the actor
  -> cockpit select/snapshot can operate on the page
  -> page idle expiry closes the page
  -> browser release occurs after idle state is empty
  -> next cockpit call restarts the browser cleanly
```

- [ ] **Step 2: Ensure test resource lifecycle is explicit**

The acceptance test must:

- record fake browser pid/pgid;
- register cleanup with `addCleanup`;
- terminate remaining fake browser processes;
- assert no fake browser process remains alive after release;
- avoid broad suite runs before this focused loop is clean.

- [ ] **Step 3: Run focused end-to-end verification**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider \
  tests/test_browser_cockpit_proxy.py \
  tests/test_browser_cockpit_launcher.py \
  tests/test_browser_lazy_release_integration.py
```

Expected: PASS, with no residual fake browser process from the integration helper.

- [ ] **Step 4: Run final residue and source ownership scans**

Run:

```bash
rg -n "_ensure_browser_runtime|_browser_endpoint|_reload_instance_payload|_open_browser_page|BUDDYSWITCH_SEARCH_BROWSER_ENSURE_COMMAND|cdp_background_page\\.py|Target\\.createTarget|refresh_page_idle\\(|close_page_target\\(|evaluate_page_open_gate\\(" scripts/env/tools/search/_impl.py
```

Expected: no matches.

Run:

```bash
rg -n "search__open_browser" tools/launcher/assets/roles framework/contracts buddyswitch/skills/market
```

Expected: matches are allowed only when the sentence says search is an optional query-to-URL wrapper. No match may say start from search, use search before cockpit, or use search for browser-native discovery.

## Final Verification Command Set

After all tasks pass focused tests, run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider \
  tests/test_cdp_browser_session.py \
  tests/test_browser_cockpit_proxy.py \
  tests/test_browser_cockpit_launcher.py \
  tests/test_browser_page_expired_handler.py \
  tests/test_browser_lazy_release_integration.py \
  tests/test_search_env_tool.py \
  tests/test_env_tool_response_contract.py \
  tests/test_env_tool_semantic_contract.py \
  tests/test_runtime_skills.py \
  tests/test_repo_consistency.py
```

Then run:

```bash
git diff --check
```

Then run exact residue scans:

```bash
rg -n "_ensure_browser_runtime|_browser_endpoint|_reload_instance_payload|_open_browser_page|BUDDYSWITCH_SEARCH_BROWSER_ENSURE_COMMAND|cdp_background_page\\.py|Target\\.createTarget|refresh_page_idle\\(|close_page_target\\(|evaluate_page_open_gate\\(" scripts/env/tools/search/_impl.py
```

```bash
rg -n "Start discovery from native `search__open_browser`|use native `search__open_browser` with a focused query, then continue discovery|Use search\\.open_browser for browser-native discovery|Call search\\.open_browser to open the target in the instance browser" \
  tools/launcher/assets/roles framework/contracts buddyswitch/skills/market scripts/env/tools/search
```

Expected:

- pytest exits 0;
- `git diff --check` exits 0;
- source-ownership scan has no matches;
- search-first live-surface scan has no matches.

## Completion Criteria

This upgrade is complete only when all statements below are true in current code and tests:

- `chrome-devtools-cockpit` browser ensure works when actor `HOME` is bound and shared-root env is absent.
- Browser release uses the same deterministic root rule.
- `scripts/env/cdp_browser_session.py` owns the shared page open/reuse primitive.
- `chrome-devtools-cockpit.new_page` uses browser-session and does not preserve the old upstream-forwarded open path as a second owner.
- `search.open_browser` contains no direct browser ensure, endpoint, CDP open, page gate, TTL, or cleanup implementation.
- `search.open_browser` tests prove wrapper behavior, not search-owned browser behavior.
- Role AGENTS, market contract, and market skills teach cockpit-first browser use.
- Tests include both behavior coverage and scoped live-surface residue coverage.
- The final end-to-end browser loop proves actor-visible page open/list/select/inspect and lifecycle release.

## Explicit Non-Goals

- Do not implement broad URL normalization in this upgrade.
- Do not add a Google-search-specific special case.
- Do not add a generic browser plugin framework, workflow engine, or long-lived adapter layer.
- Do not preserve search-owned browser code as a compatibility fallback.
- Do not move browser semantics into role prompts or skills instead of runtime contracts.
- Do not run broad service-starting suites before focused lifecycle cleanup is proven.

