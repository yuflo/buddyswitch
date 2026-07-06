# fea-tool + fea-im Main Merge Plan

Date: 2026-07-06

## Goal

Merge `fea-tool` and `fea-im` into `main` while preserving the latest forward behavior from both branches. Do not keep old compatibility paths, duplicate runtime truths, or historical residue.

## Current Evidence

Branch topology from current `main` (`b2ddbecc`):

| Branch | Ahead of `main` | Behind `main` | Decision |
| --- | ---: | ---: | --- |
| `fea-tool` | 9 | 0 | Merge |
| `fea-im` | 11 | 0 | Merge |

Individual merge simulations:

```bash
git merge-tree --write-tree main fea-tool
git merge-tree --write-tree main fea-im
```

Both exit 0 and return a tree hash, so each branch can merge cleanly by itself.

Combined merge simulation:

```bash
git merge-tree --write-tree fea-tool fea-im
```

Exits 1 with content conflicts in exactly these files:

- `scripts/env/tools/search/_impl.py`
- `tests/test_browser_page_expired_handler.py`
- `tests/test_repo_consistency.py`

Overlapping non-conflict surfaces that require focused verification:

- `scripts/env/tool_runtime/context.py`
- `tests/test_browser_cockpit_proxy.py`
- `tests/test_browser_lazy_release_integration.py`
- `tests/test_buddyswitch_launcher.py`
- `tests/test_central_daemon_service.py`
- `tests/test_daemon_trigger_router.py`
- `tests/test_env_tool_response_contract.py`
- `tests/test_env_tool_schema_contract.py`
- `tests/test_env_tool_semantic_contract.py`
- `tests/test_runtime_broker.py`
- `tools/launcher/browser_page_expired_handler.py`
- `tools/launcher/browser_release_handler.py`
- `tools/launcher/daemon_core.py`

`git diff --check main...fea-tool` reports trailing-whitespace / EOF issues in files introduced by `fea-tool`; `git diff --check main...fea-im` reports one EOF issue. The merge must fix these instead of preserving them.

## Dependency And Conflict Assessment

`fea-tool` is the browser-control forward path:

- Removes `search.open_browser` as a live browser-opening action.
- Keeps `search.request` / `search.status` as URL-planning and capability metadata surfaces.
- Moves browser page lifecycle from CDP target IDs and `cdp_browser_session.py` toward MCP page IDs and `chrome-devtools-cockpit`.
- Removes the obsolete repo-local user simulation skill and updates market role skill references.

`fea-im` is the identity/IM forward path:

- Replaces actor-address-shaped runtime identity with identity-route / current-identity terminology.
- Rebuilds IM session naming, target resolution, reply wrapper handling, and post-write delivery boundaries.
- Removes `scripts/env/tool_runtime/actor_profile.py` as active runtime coupling.
- Adds identity and IM residue checks to `tests/test_repo_consistency.py`.

Required conflict resolutions:

1. In `scripts/env/tools/search/_impl.py`, keep `fea-tool`'s removal of browser opening, broker browser client, and `open_browser` action. Apply `fea-im`'s `current_identity` result field to every remaining rejection/success result.
2. In `tools/launcher/browser_page_expired_handler.py` and `tests/test_browser_page_expired_handler.py`, keep `fea-tool`'s MCP page-id lifecycle and page-id payload. Apply `fea-im`'s target identity trigger fields and "wrong target identity" permission wording.
3. In `tests/test_repo_consistency.py`, keep both residue sets:
   - browser cockpit / MCP page-id / no `search.open_browser` live guidance checks from `fea-tool`
   - identity/IM no-retired-shape checks from `fea-im`
   Remove the broad docs-spec drift allowlist from the live guidance scan, matching `fea-im`'s stricter cleanup.
4. Do not restore removed files or compatibility shims:
   - `.agents/skills/buddyswitch-user-simulation-testing/**`
   - `scripts/env/cdp_browser_session.py`
   - `scripts/env/tool_runtime/actor_profile.py`
   - `tests/test_buddyswitch_user_simulation_skill_contract.py`

## Implementation Plan

1. Confirm `main` is clean.
2. Merge `fea-tool` with `git merge --no-ff fea-tool`.
3. Merge `fea-im` with `git merge --no-ff fea-im`.
4. Resolve the three predicted conflict files with the forward resolutions above.
5. Fix whitespace / EOF issues reported by `git diff --check`.
6. Run focused verification.
7. Audit branch convergence, residue, and final git status.

## Focused Test Plan

Conflict-surface and shared-contract tests:

```bash
python3 -m unittest \
  tests.test_repo_consistency \
  tests.test_buddyswitch_launcher \
  tests.test_env_tool_response_contract \
  tests.test_env_tool_schema_contract \
  tests.test_env_tool_semantic_contract \
  tests.test_runtime_broker \
  tests.test_central_daemon_service \
  tests.test_daemon_trigger_router
```

Browser-control tests:

```bash
python3 -m unittest \
  tests.test_browser_runtime_manager \
  tests.test_browser_cockpit_launcher \
  tests.test_browser_cockpit_proxy \
  tests.test_browser_lazy_release_integration \
  tests.test_browser_page_expired_handler \
  tests.test_cdp_browser_session \
  tests.test_search_env_tool
```

Identity and IM tests:

```bash
python3 -m unittest \
  tests.test_communication_identity_cutover \
  tests.test_identity_global_convergence \
  tests.test_im_product_core \
  tests.test_im_http_router \
  tests.test_external_im_session \
  tests.test_im_external_reply_loop \
  tests.test_message_tool_im_client \
  tests.test_im_web_management_projection \
  tests.test_imessage_channel \
  tests.test_context_binding_env_tool \
  tests.test_runtime_actor_profile
```

Syntax and merge hygiene:

```bash
python3 -m compileall scripts tools tests
git diff --check
rg -n '(<{7}|={7}|>{7})' .
```

Final audit:

```bash
git rev-list --left-right --count main...fea-tool
git rev-list --left-right --count main...fea-im
test ! -e scripts/env/cdp_browser_session.py
test ! -e scripts/env/tool_runtime/actor_profile.py
test ! -e .agents/skills/buddyswitch-user-simulation-testing
test ! -e tests/test_buddyswitch_user_simulation_skill_contract.py
rg -n 'search\.open_browser|search__open_browser|browser\.open_url|cdp_browser_session|close_page_target|current_target_id|target_actor_address|actor_address' scripts/env/tools/search/_impl.py tools/launcher/browser_page_expired_handler.py tools/launcher/assets/roles tests/test_repo_consistency.py
git status --short --branch
```

Expected branch convergence after merge: right-hand count is `0` for both `main...fea-tool` and `main...fea-im`.
