# fea-tool, fea-webui, and fea-im Main Merge Plan

> **For agentic workers:** Implement this plan task-by-task. Preserve the latest branch behavior, remove replaced legacy paths directly, and do not add compatibility tracks or dual runtime modes.

**Goal:** Merge current `fea-tool`, `fea-webui`, and `fea-im` into `main` with browser lazy release, smoother Web Management interactions, and clearer actor IM handoff guidance verified together.

**Architecture:** Keep each feature boundary direct. `fea-tool` owns browser cockpit lazy startup/release and search browser on-demand ensure. `fea-webui` owns browser-side Web Management interaction state and rendering. `fea-im` owns message tool guidance/schema text for actionable actor-to-actor IM handoffs. The integrated tree should have one lazy browser lifecycle path, one WebUI action-state/render path, and one Central IM actor handoff guidance path.

**Tech Stack:** Shell launcher code, Python launcher/env tool code, plain browser JavaScript, Node UI tests, `unittest`, `pytest`, `py_compile`, `bash -n`, scoped `rg` residue scans, and `git merge-tree`.

---

## Current Baseline

- `main` is clean at `c45fdd573a2ee25b4c357a12135248b3eb04263b` and matches `origin/main`.
- `fea-tool` is clean at `bfcff306f516dcb45b0571974eb5790082ffc5f1` and matches `origin/fea-tool`.
- `fea-webui` is clean at `bbcb19364559521ca0428197ab34b37b4586165d` and matches `origin/fea-webui`.
- `fea-im` is clean at `27b2470470ca749f0d01186bc5339843b86cd771` and matches `origin/fea-im`.
- All three merge bases with `main` resolve to current `main` (`c45fdd573a2ee25b4c357a12135248b3eb04263b`).
- Each branch has one commit over `main`:
  - `fea-tool`: `bfcff30 feat: implement lazy browser cockpit release`
  - `fea-webui`: `bbcb193 Smooth web management interactions`
  - `fea-im`: `27b2470 Clarify IM handoff guidance`

## Conflict, Dependency, And Association Assessment

### Conflict Assessment

- `git merge-tree --write-tree main fea-tool` produced tree `33ec6b74330043fd012ed4db355db9c08d6427f1` with no conflict records.
- `git merge-tree --write-tree main fea-webui` produced tree `a37eeaa1b715ffdfb2814a51e957578b8b3a94a3` with no conflict records.
- `git merge-tree --write-tree main fea-im` produced tree `9ce095796727fad95a812b974a2c7a45731355a3` with no conflict records.
- Pairwise changed-file intersections among the three branches are empty.
- Result: no textual conflicts are expected, and merge order should not affect overlapping file content.

### Dependency Assessment

- None of the three branches changes dependency manifests or lockfiles such as `package.json`, lockfiles, `pyproject.toml`, requirements files, `Cargo.toml`, `go.mod`, or `buddyswitch/manifest.toml`.
- `git diff --check main..fea-tool`, `git diff --check main..fea-webui`, and `git diff --check main..fea-im` all produced no output.
- Result: no dependency installation, dependency update, or lockfile reconciliation is required.

### Association Assessment

- `fea-tool` changes:
  - `buddyswitch-codex`
  - `scripts/env/cdp_browser_lifecycle.py`
  - `scripts/env/tools/search/_impl.py`
  - browser cockpit launcher/proxy/handler files under `tools/launcher`
  - browser lifecycle tests and `docs/spec/browser-cockpit-lazy-release/**`
- `fea-tool` behavior to preserve:
  - actor start/resume registers browser capability without starting Chrome or upstream `chrome-devtools-mcp`;
  - first cockpit/search browser use ensures the actor-owned browser runtime on demand;
  - final page TTL expiry schedules keyed browser release;
  - release stops owned browser/upstream processes and clears browser lifecycle state;
  - internal browser endpoints are not leaked in ordinary actor-facing search/browser outputs.
- `fea-webui` changes:
  - `tools/launcher/assets/web-management/app.js`
  - `tools/launcher/assets/web-management/index.html`
  - `tools/launcher/assets/web-management/styles.css`
  - Web Management UI Node tests and `docs/spec/webui-interaction-smoothness-forward/**`
- `fea-webui` behavior to preserve:
  - action-scoped pending state, so Send, Refresh, Open TUI, and lifecycle actions do not unnecessarily disable each other;
  - focused render functions, so typing in the composer does not rewrite actor/track/runtime/conversation sections;
  - row event delegation instead of render-time row listener installation;
  - send clears the draft before network completion and refreshes the selected actor console instead of full `refreshAll()`;
  - mobile layout keeps actions before runtime detail with fitting button text.
- `fea-im` changes:
  - `buddyswitch/skills/shared/message-tool/SKILL.md`
  - `scripts/env/tools/message/tool.py`
- `fea-im` behavior to preserve:
  - actor-to-actor IM handoff instructions tell senders to include source intent, concrete inputs, constraints, and requested output in the message body;
  - private message/conversation ids may be audit references but must not be the only actionable context;
  - Central IM remains the single messaging tool path; no retired handoff tool, next-role flow, or alternate message path is restored.
- Cross-branch association:
  - `fea-tool` and `fea-webui` meet at actor-facing browser/Web Management usability but have no source overlap.
  - `fea-webui` and `fea-im` meet at actor communication quality: the WebUI keeps the current `/api/im` frontend path while `fea-im` improves the env tool guidance behind Central IM.
  - Existing skill tests contain a historical guard that only allowed the word `handoff` in shared tool skills under `Do Not`. The new `fea-im` guidance intentionally uses actor handoff as quality guidance for Central IM, so the integrated tree should update that guard to reject only retired tool/next-role handoff guidance, not actionable IM handoff wording.

## Merge Plan

### Task 1: Record This Current Plan

- [x] Add this merge and test plan under `docs/spec`.
- [x] Commit the plan before feature merges if the worktree is otherwise clean.

Verification:

```bash
git status --short --branch
git diff --check
```

Expected: only this plan file is modified before the planning commit, and whitespace check has no output.

### Task 2: Merge `fea-tool`

- [x] Run `git merge --no-ff --no-commit fea-tool`.
- [x] Keep lazy browser startup/release as the only browser cockpit lifecycle path.
- [x] Reject fixes that preserve eager startup through flags, wrappers, or alternate compatibility branches.
- [x] Run focused browser lifecycle verification.
- [x] Commit the merge.

Focused verification:

```bash
bash -n buddyswitch-codex tools/launcher/browser_cockpit.sh tools/launcher/env.sh
python3 -m py_compile scripts/env/cdp_browser_lifecycle.py scripts/env/tools/search/_impl.py tools/launcher/browser_page_expired_handler.py tools/launcher/browser_release_handler.py tools/launcher/browser_inbound.py tools/launcher/chrome_devtools_cockpit_proxy.py
python3 -m unittest tests.test_browser_cockpit_launcher
python3 -m unittest tests.test_browser_cockpit_proxy
python3 -m unittest tests.test_browser_page_expired_handler
python3 -m unittest tests.test_cdp_browser_session
python3 -m unittest tests.test_search_env_tool
python3 -m unittest tests.test_env_tool_response_contract
python3 -m unittest tests.test_buddyswitch_launcher
python3 -m unittest tests.test_instance_daemon_entrypoint
python3 -m unittest tests.test_browser_lazy_release_integration
git diff --check
```

Expected: shell syntax and Python compile pass, focused browser/search/launcher tests pass, and whitespace check has no output.

### Task 3: Merge `fea-webui`

- [x] Run `git merge --no-ff --no-commit fea-webui`.
- [x] Keep action-scoped pending state, focused render functions, event delegation, selected-console send refresh, and mobile priority CSS.
- [x] Remove or adjust any stale global mutation/full-render path directly; do not keep old and new UI paths side by side.
- [x] Run focused WebUI verification.
- [x] Commit the merge.

Focused verification:

```bash
node --check tools/launcher/assets/web-management/app.js
node tests/web_management_ui_state.test.js
node tests/web_management_ui_contract.test.js
git diff --check
```

Residue scans:

```bash
rg -n "mutationKey|isMutating|Action running\.|runMutation\(" tools/launcher/assets/web-management/app.js tests/web_management_ui_state.test.js tests/web_management_ui_contract.test.js -S
rg -n "querySelectorAll\('\[data-actor-id\]'\)|querySelectorAll\('\[data-track-id\]'\)" tools/launcher/assets/web-management/app.js -S
rg -n "POST /api/web/im|/api/web/im|buildWebImConversationUrl|ensureWebImSession|connection_key|participant_token|event_cursor|cursor=" tools/launcher/assets/web-management/app.js tests/web_management_ui_state.test.js tests/web_management_ui_contract.test.js -S
```

Expected: syntax and Node tests pass; residue scans have no live `app.js` hits except negative assertions in tests if the tests intentionally mention forbidden strings; whitespace check has no output.

### Task 4: Merge `fea-im`

- [x] Run `git merge --no-ff --no-commit fea-im`.
- [x] Keep Central IM actor handoff quality guidance.
- [x] Update tests only where their older guard conflicts with the current product decision: reject retired handoff tool/next-role guidance, while allowing actionable IM handoff wording inside `message-tool`.
- [x] Run focused message-tool verification.
- [x] Commit the merge.

Focused verification:

```bash
python3 -m py_compile scripts/env/tools/message/tool.py
python3 -m pytest -q tests/test_env_tool_schema_contract.py tests/test_env_tool_semantic_contract.py tests/test_runtime_skills.py tests/test_repo_consistency.py
git diff --check
```

Residue scans:

```bash
rg -n "handoff-tool|next_role|track\.advance|message send --payload|target_actor_address|actor_address" buddyswitch/skills/shared/message-tool/SKILL.md scripts/env/tools/message/tool.py tests/test_runtime_skills.py tests/test_env_tool_schema_contract.py -S
```

Expected: compile and focused tests pass; residue scan has no retired handoff tool, next-role, `track.advance`, legacy CLI, or actor-address guidance in live message surfaces.

### Task 5: Final Integration Verification

- [x] Prove all three feature branches are ancestors of `main`.
- [x] Run combined focused verification covering browser lifecycle, WebUI state, and message tool guidance.
- [x] Run scoped residue scans for old browser eager startup, old WebUI global mutation/full-render paths, retired Web IM frontend routes, and retired message/handoff guidance.
- [x] Inspect final status and recent history.

Final verification:

```bash
git merge-base --is-ancestor fea-tool main
git merge-base --is-ancestor fea-webui main
git merge-base --is-ancestor fea-im main
bash -n buddyswitch-codex tools/launcher/browser_cockpit.sh tools/launcher/env.sh
node --check tools/launcher/assets/web-management/app.js
python3 -m py_compile scripts/env/cdp_browser_lifecycle.py scripts/env/tools/search/_impl.py scripts/env/tools/message/tool.py tools/launcher/browser_page_expired_handler.py tools/launcher/browser_release_handler.py tools/launcher/browser_inbound.py tools/launcher/chrome_devtools_cockpit_proxy.py
node tests/web_management_ui_state.test.js
node tests/web_management_ui_contract.test.js
python3 -m unittest tests.test_browser_cockpit_launcher
python3 -m unittest tests.test_browser_cockpit_proxy
python3 -m unittest tests.test_browser_page_expired_handler
python3 -m unittest tests.test_cdp_browser_session
python3 -m unittest tests.test_search_env_tool
python3 -m unittest tests.test_env_tool_response_contract
python3 -m unittest tests.test_buddyswitch_launcher
python3 -m unittest tests.test_instance_daemon_entrypoint
python3 -m unittest tests.test_browser_lazy_release_integration
python3 -m pytest -q tests/test_env_tool_schema_contract.py tests/test_env_tool_semantic_contract.py tests/test_runtime_skills.py tests/test_repo_consistency.py
git diff --check
git status --short --branch
```

Final residue scans:

```bash
rg -n "start.*Chrome|Browser cockpit ready:|--browser-url=http://127\\.0\\.0\\.1|instance browser_port is missing" buddyswitch-codex tools/launcher scripts/env/tools/search tests tools/launcher/assets/roles framework/contracts -S
rg -n "browser_endpoint|browser_url|manual browser|browser startup|Chrome endpoint|remote-debugging" scripts/env/tools/search tests/test_search_env_tool.py tests/test_env_tool_response_contract.py tools/launcher/assets/roles framework/contracts -S
rg -n "mutationKey|isMutating|Action running\.|runMutation\(" tools/launcher/assets/web-management/app.js tests/web_management_ui_state.test.js tests/web_management_ui_contract.test.js -S
rg -n "querySelectorAll\('\[data-actor-id\]'\)|querySelectorAll\('\[data-track-id\]'\)" tools/launcher/assets/web-management/app.js -S
rg -n "POST /api/web/im|/api/web/im|buildWebImConversationUrl|ensureWebImSession|connection_key|participant_token|event_cursor|cursor=" tools/launcher/assets/web-management/app.js tests/web_management_ui_state.test.js tests/web_management_ui_contract.test.js -S
rg -n "handoff-tool|next_role|track\.advance|message send --payload|target_actor_address|actor_address" buddyswitch/skills/shared/message-tool/SKILL.md scripts/env/tools/message/tool.py tests/test_runtime_skills.py tests/test_env_tool_schema_contract.py -S
```

Expected:

- `fea-tool`, `fea-webui`, and `fea-im` are ancestors of `main`.
- Focused shell, syntax, Node, browser lifecycle, launcher/search, message-tool, runtime skill, and repo consistency verification passes.
- Whitespace check has no output.
- Old browser eager-start and endpoint leak scans have only accepted internal/negative-test hits, not actor-facing live guidance.
- WebUI residue scans have no live `app.js` old-path hits.
- Message residue scan has no retired handoff tool, next-role, legacy CLI, or actor-address guidance.
- Final `main` history contains the plan commit and three feature merge commits, plus any direct integration fix commit required by verification.

## Acceptance Criteria

- `main` contains `bfcff306f516dcb45b0571974eb5790082ffc5f1`, `bbcb19364559521ca0428197ab34b37b4586165d`, and `27b2470470ca749f0d01186bc5339843b86cd771`.
- No textual conflicts remain.
- No dependency or lockfile reconciliation is required.
- Browser cockpit uses one lazy first-use runtime path and one release cleanup path.
- WebUI uses one action-scoped pending/render path and does not retain old global mutation/full-render compatibility.
- Central IM message guidance teaches actionable actor handoff content without reintroducing a retired handoff tool, next-role route, or alternate message path.
- Focused verification passes, or any blocker is recorded with exact failing command and root cause before further changes.

## Execution Log

Merge commits:

```text
68ddd18 docs: plan tool webui im merge
0d8db74 Merge branch 'fea-tool'
1c1a07c docs: split browser merge verification commands
fd72260 Merge branch 'fea-webui'
5283c1c Merge branch 'fea-im'
```

Integration fix:

- `tests/test_repo_consistency.py` now classifies `docs/spec/browser-cockpit-lazy-release/**` as execution-spec context. This keeps the stable-guidance guard strict while allowing the new browser execution specs to mention response-structure verification files.

Branch ancestry:

```text
git merge-base --is-ancestor fea-tool main
exit 0

git merge-base --is-ancestor fea-webui main
exit 0

git merge-base --is-ancestor fea-im main
exit 0
```

Focused verification:

```text
bash -n buddyswitch-codex tools/launcher/browser_cockpit.sh tools/launcher/env.sh
exit 0

node --check tools/launcher/assets/web-management/app.js
exit 0

python3 -m py_compile scripts/env/cdp_browser_lifecycle.py scripts/env/tools/search/_impl.py scripts/env/tools/message/tool.py tools/launcher/browser_page_expired_handler.py tools/launcher/browser_release_handler.py tools/launcher/browser_inbound.py tools/launcher/chrome_devtools_cockpit_proxy.py
exit 0

node tests/web_management_ui_state.test.js
40 checks passed

node tests/web_management_ui_contract.test.js
11 checks passed

python3 -m pytest -q tests/test_env_tool_schema_contract.py tests/test_env_tool_semantic_contract.py tests/test_runtime_skills.py tests/test_repo_consistency.py
96 passed, 844 subtests passed in 0.64s
```

Browser unittest verification:

```text
python3 -m unittest tests.test_browser_cockpit_launcher
13 tests passed

python3 -m unittest tests.test_browser_cockpit_proxy
29 tests passed

python3 -m unittest tests.test_browser_page_expired_handler
22 tests passed

python3 -m unittest tests.test_cdp_browser_session
14 tests passed

python3 -m unittest tests.test_search_env_tool
29 tests passed

python3 -m unittest tests.test_env_tool_response_contract
14 tests passed

python3 -m unittest tests.test_buddyswitch_launcher
206 tests passed

python3 -m unittest tests.test_instance_daemon_entrypoint
7 tests passed

python3 -m unittest tests.test_browser_lazy_release_integration
1 test passed
```

Residue and status verification:

```text
git diff --check
no output

WebUI old global mutation/full-render and retired `/api/web/im` scans
no output

Browser eager-start residue scan
accepted hits only: host status output, internal upstream argv construction, stale-config repair fixtures, and negative tests

Search endpoint leak scan
accepted hits only: internal helper names and negative no-leak assertions

Message/handoff residue scan
accepted hits only: negative assertions in tests; no live message skill/tool hits

git status --short --branch
## main...origin/main [ahead 8]
```

Acceptance decision: accepted.
