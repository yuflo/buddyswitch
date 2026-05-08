# Buddy Instance Context Tool Feedback Test Plan

**Goal:** Verify from product requirements that buddy instances receive enough executable context and structured tool feedback to stay on the existing main path without source/schema/profile inference.

**Testing Principle:** Tests must start from functional requirements and observable buddy-instance behavior. Prefer public CLI, broker dispatch, launcher-managed state artifacts, prepared JSON, persisted receipts, and state snapshots. Do not write tests that merely call a private helper or match a private branch so an implementation can pass without improving the product path.

---

## Functional Requirements Under Test

FR1. `prepare` exposes an executable `runtime_context` for every manifest buddy.

FR2. `runtime_context.active_buddy` identifies the locked buddy from launcher/product session metadata, not user text.

FR3. `runtime_context.active_skill_ids` lists only the active buddy's native skills from `buddyswitch/manifest.toml`.

FR4. `runtime_context.capability_boundary.allowed_artifact_kinds` lists only the active buddy's artifact kinds.

FR5. `runtime_context.capability_boundary.allowed_state_effects.task` lists only `status` and `summary`.

FR6. `runtime_context.capability_boundary.allowed_state_effects.track` lists `create/update/advance/archive` only for PM and an empty list for all other buddies.

FR7. `runtime_context.capability_boundary.handoff_targets` lists current manifest buddy ids.

FR8. `runtime_context.capability_boundary.project`, `scratch`, and `raw_state` describe executable read/write boundaries: non-Dev project read-only, Dev project writable, scratch writable, raw state broker-only.

FR9. `runtime_context.tool_requirements` exposes Market browser cockpit and evidence requirements, and exposes non-Market browser availability without requiring evidence.

FR10. `runtime_context.persist_payload_hint` shows required fields, optional fields, durable signal rule, and where to find allowed artifacts, state effects, handoff targets, and Market evidence fields.

FR11. `runtime_context.current_context_summary` summarizes current task, track, artifacts, and recent handoffs without dumping full raw state.

FR12. Product-mode broker unavailable errors tell the buddy to stop and report, not bypass the broker or write raw state.

FR13. Broker identity, active buddy, inactive instance, malformed payload, and unsupported method rejections include a structured permission boundary or allowed next action.

FR14. Persist rejections for unauthorized artifact kinds include structured feedback that identifies the allowed artifact kinds for the active buddy.

FR15. Persist rejections for unauthorized track effects include structured feedback that identifies `env-profile.state_capability.track_effects` and the allowed next action.

FR16. Persist rejections for unsupported task effects include structured feedback that identifies `state_effects.task` allowed fields.

FR17. Persist rejections for invalid handoff targets include structured feedback that identifies manifest buddy targets.

FR18. Persist rejections for stale context, replayed run id, or product-mode context/instance/buddy mismatch include structured feedback that tells the buddy to rerun `prepare`.

FR19. Market artifact-producing persist without broker-issued evidence rejects before writes and tells the buddy how to issue evidence.

FR20. Market artifact-producing persist with handwritten, wrong-run, wrong-context, wrong-instance, or wrong-mode evidence token rejects before writes.

FR21. Market browser evidence issuance success returns token mode, browser URL when relevant, persist field name, token scope, and next action.

FR22. Approved downgrade evidence requires a non-empty reason and returns token scope plus next action.

FR23. PM, Design, Dev, and Test can persist valid product-shaped commits without `tool_evidence`.

FR24. Runtime AGENTS templates remain framework-level and point buddies to `prepare.runtime_context` and structured tool feedback instead of duplicating payload recipes or task-specific examples.

FR25. The implementation does not add a new continuation UX or widen peripheral systems; tests should not require context panel, cleanup tools, debug object APIs, or skill importer changes.

## Coverage Matrix

| Requirement | Test Group | Observable Proof |
| --- | --- | --- |
| FR1-FR3 | TG-01 | prepare output for each buddy contains active buddy and active skill ids derived from product session + manifest |
| FR4-FR7 | TG-02 | capability boundary matches manifest/profile permissions for artifacts, task effects, track effects, handoff targets |
| FR8 | TG-03 | prepare output describes non-Dev read-only project, Dev writable project, scratch root, and broker-only raw state |
| FR9-FR10 | TG-04 | Market and non-Market prepare outputs show browser/evidence requirements and persist payload hints |
| FR11 | TG-05 | prepared context after PM persist contains compact task/track/artifact/handoff summaries |
| FR12 | TG-06 | CLI prepare/persist/evidence missing broker returns stop condition and no raw state writes |
| FR13 | TG-07 | broker dispatch rejections return structured boundary feedback |
| FR14-FR18 | TG-08 | persist negative cases reject atomically with structured next actions |
| FR19-FR22 | TG-09 | Market evidence gate and issuance success/failure behavior are observable through broker/evidence CLI |
| FR23 | TG-10 | non-Market valid commits persist without evidence |
| FR24 | TG-11 | runtime AGENTS validator and repo consistency guards prevent prompt bloat |
| FR25 | TG-12 | repo search and test selection show scope stayed on main path |

## Test Data Rules

Use product-shaped data:

- PM request: `给一款AI日程工具做一个简单的landing page，写一份PRD，然后创建绑定一个track`
- Market request: `调研 AI 日程工具 landing page 竞品表达和定位方式`
- Design request: `基于现有 PRD 和市场简报，整理 landing page 原型方向`
- Dev request: `实现 landing page hero 文案和 CTA 调整`
- Test request: `验证 landing page hero 和 CTA 行为`
- Track id: `track-ai-schedule-landing-page`
- PRD artifact kind: `prd`
- Market artifact kind: `market-scan`
- Design artifact kind: `design-handoff`
- Dev artifact kind: `implementation-report`
- Test artifact kind: `test-report`

Negative data must remain product-meaningful:

- Market tries to create a track;
- Dev tries to persist a PRD;
- PM hands off to an unknown buddy;
- PM updates unsupported task field;
- Market omits browser evidence;
- Market uses handwritten or wrong-run evidence token;
- product-mode CLI loses broker socket;
- broker request sends wrong instance id or active buddy;
- persist uses stale prepared context.

Do not use fake values whose only purpose is to hit a private helper branch.

## TG-01 Prepare Runtime Context Exists For Every Buddy

**Purpose:** Prove every buddy receives executable runtime context in the public prepare payload.

**Setup:**

- Use the existing runtime test helper to isolate BuddySwitch state.
- Patch product-mode session only as an equivalent of launcher metadata, or dispatch through broker where practical.
- Prepare once for each buddy with the product-shaped request for that buddy.

**Assertions:**

- `payload["ok"] is True`.
- `payload["runtime_context"]` exists.
- `runtime_context` contains `active_buddy`, `active_skill_ids`, `capability_boundary`, `tool_requirements`, `persist_payload_hint`, and `current_context_summary`.
- `active_buddy.id` equals the locked session buddy even if request text contains `switch market:`.
- No router-era fields such as `recommended_switch`, `selected_skill`, or `selected_skill_packet` appear.

**Command:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_prepare_runtime_context.py::PrepareRuntimeContextTests::test_prepare_returns_runtime_context_for_each_buddy -q
```

## TG-02 Capability Boundary Matches Product Permissions

**Purpose:** Prove `runtime_context` exposes capability boundaries that let a buddy decide what it can persist.

**Assertions:**

- Market artifact kinds equal `market-scan`, `pmf-report`, `customer-discovery`, `positioning-brief`, `channel-plan`, and `launch-prep`.
- PM artifact kinds equal `prd`, `pm-decision`, and `track-note`.
- Design artifact kinds equal `design-handoff` and `prototype-brief`.
- Dev artifact kinds equal `implementation-report` and `skill-import-report`.
- Test artifact kinds equal `smoke-test` and `test-report`.
- PM track effects are `create`, `update`, `advance`, `archive`.
- Market, Design, Dev, and Test track effects are empty.
- Handoff targets equal manifest buddies: `market`, `pm`, `design`, `dev`, `test`.

**Anti-cheat check:** Do not assert values by reading `scripts/turn_runtime.py`. Compare prepare output to manifest/profile public data or explicit product expectations.

## TG-03 Filesystem And State Boundaries Are Visible

**Purpose:** Prove `prepare` tells buddies where they may act before they try to write.

**Assertions:**

- Market, PM, Design, and Test `project.access` is `read-only`.
- Dev `project.access` is `write`.
- Non-Dev write rule says to hand source changes to Dev or equivalent.
- Dev write rule says direct project write is allowed.
- Scratch root equals `runs/raw/<buddy>`.
- Raw state access is `broker-only`.
- Raw state paths mention tracks, tasks, artifacts, and run audits as broker-owned, not host-writable.

**Command:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_prepare_runtime_context.py::PrepareRuntimeContextTests::test_prepare_exposes_filesystem_and_state_boundaries -q
```

## TG-04 Tool Requirements And Persist Payload Hints

**Purpose:** Prove a buddy can build the right persist payload without reading JSON contracts.

**Assertions:**

- All buddies see `execution_summary` as required.
- All buddies see optional keys `working_notes`, `artifacts`, `state_effects`, `handoff`, `contributors`, and `tool_evidence`.
- All buddies see durable signal rule: at least one of `artifacts`, `state_effects`, or `handoff`.
- Market sees `browser_cockpit=required`, `market_research_evidence=required`, and accepted evidence fields `browser_cockpit_token` and `approved_downgrade_token`.
- PM/Design/Dev/Test see `market_research_evidence=not-required`.
- PM sees enough hints to choose PRD artifact + track create + Market handoff for the PM request.

**Anti-cheat check:** The test should assert field semantics and shape, not a long fixed help string.

## TG-05 Current Context Summaries After A PM Run

**Purpose:** Prove follow-up buddies receive compact current state without reading raw state files.

**Flow:**

1. Prepare as PM for the AI schedule landing page request.
2. Persist a valid PM commit with PRD artifact, track create, task done, and handoff to Market.
3. Open or prepare as Market against the same current track/task binding.

**Assertions:**

- Market prepare includes current track id `track-ai-schedule-landing-page`.
- Current context summary includes PM-created PRD artifact id, kind, title, summary, buddy, and task id.
- Recent handoff summary includes PM run id, next buddy `market`, reason, and context.
- Summary does not include full PRD artifact content unless already present in existing task context.

## TG-06 Broker Unavailable Stop Feedback

**Purpose:** Prove product-mode tools fail safely and instruct the buddy not to bypass.

**Cases:**

- `turn_runtime.py prepare` with product-mode env and missing broker socket.
- `turn_runtime.py persist` with product-mode env and missing broker socket.
- `browser_evidence.py issue` with product-mode env and missing broker socket.

**Assertions:**

- Exit code is non-zero.
- `ok=false`.
- `error.code=E_RUNTIME_BROKER_UNAVAILABLE`.
- `error.permission_boundary=product-mode-runtime-broker`.
- `error.stop_condition=stop_and_report_do_not_bypass_broker`.
- `allowed_next_actions` tells the buddy to report broker unavailability and not write raw state or bypass via debug APIs.
- Runtime state snapshot is unchanged.

## TG-07 Broker Dispatch Structured Rejections

**Purpose:** Prove broker errors are buddy-facing, not generic implementation failures.

**Cases:**

- Wrong `instance_id`.
- Wrong `active_buddy`.
- Inactive instance.
- Unsupported method.
- Malformed payload.

**Assertions:**

- `ok=false`.
- Error identifies the boundary: active instance, active buddy, active instance status, broker protocol, or request payload.
- `allowed_next_actions` is present where a buddy can recover.
- No state writes occur.

## TG-08 Persist Rejection Feedback And Atomicity

**Purpose:** Prove persist feedback lets the buddy fix the payload from the response.

**Cases:**

- Market includes `state_effects.track.create`.
- Dev persists `prd`.
- PM handoff target is `sales`.
- PM task effect includes `owner`.
- Persist uses stale prepared context after another run commits.
- Persist context active buddy does not match instance active buddy.

**Assertions:**

- Each response is `ok=false`.
- Each response includes `permission_boundary` or equivalent structured boundary field.
- Each response includes `allowed_next_actions`.
- Artifact-kind rejection includes active buddy allowed kinds.
- Track-effect rejection includes active buddy allowed track actions.
- Task-effect rejection includes `status` and `summary` only.
- Handoff rejection includes manifest buddy targets.
- Stale context rejection tells the buddy to rerun `prepare`.
- State snapshot before and after rejection is identical.

## TG-09 Market Evidence Feedback

**Purpose:** Prove Market can recover from missing evidence and can use successful evidence issuance without source reading.

**Cases:**

- Market artifact-producing persist without `tool_evidence`.
- Market artifact-producing persist with handwritten token.
- Market artifact-producing persist with token issued for another run.
- Browser evidence issuance with reachable cockpit.
- Approved downgrade evidence issuance with reason.
- Approved downgrade evidence issuance with blank reason.

**Assertions:**

- Missing/invalid evidence rejects before writes.
- Rejection includes `permission_boundary=market.browser_evidence` or equivalent.
- Rejection includes command hint for `scripts/browser_evidence.py issue --context <prepare-context.json> --mode browser-cockpit-preflight`.
- Successful browser evidence includes `tool_evidence.browser_cockpit_token`.
- Successful browser evidence includes feedback mode, browser URL, persist field, token scope, and next action.
- Successful downgrade evidence includes `tool_evidence.approved_downgrade_token`, reason, token scope, and next action.

## TG-10 Non-Market Valid Persist Does Not Require Evidence

**Purpose:** Prove Market-specific evidence policy does not block other buddies.

**Flow:**

- Prepare and persist valid commits for PM, Design, Dev, and Test.

**Assertions:**

- Each persist succeeds without `tool_evidence`.
- Receipt includes buddy id, task id, run id, artifact ids, receipt paths, and next state.
- No response suggests browser evidence is required for non-Market buddies.

## TG-11 Runtime AGENTS Remain Framework-Level

**Purpose:** Prove prompt bloat was not used to solve the behavior.

**Assertions:**

- Every buddy AGENTS template states active buddy is locked.
- Every buddy AGENTS template states AGENTS is context projection only and not the permission source.
- Every buddy AGENTS template points to `prepare.runtime_context` for allowed actions and persist shape.
- No AGENTS template contains AI calendar landing-page examples.
- No AGENTS template contains long copyable persist payload examples.
- No AGENTS template duplicates full artifact-kind matrices that should come from `prepare`.
- Runtime AGENTS validation passes for all buddies.

**Command:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_runtime_agents.py tests/test_repo_consistency.py -q
```

## TG-12 Scope Guard

**Purpose:** Prove the change stayed on the accepted main path.

**Assertions:**

- No new launcher continuation commands are introduced: `instance continue`, `open-handoff`, or receipt-based continuation UX.
- Context panel server files are unchanged.
- Cleanup/debug object APIs are unchanged unless a focused test proves they were blocking the main path.
- Skill importer is unchanged.
- Tests assert structured runtime output, not long fixed prompt strings.

## Full Verification Command

Run focused suites first:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_prepare_runtime_context.py \
  tests/test_runtime_tool_feedback.py \
  tests/test_turn_runtime.py \
  tests/test_runtime_broker.py \
  tests/test_market_browser_evidence.py \
  tests/test_runtime_agents.py \
  tests/test_buddy_env_profiles.py \
  tests/test_repo_consistency.py \
  -q
```

Then run launcher-adjacent suites:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_buddyswitch_launcher.py \
  tests/test_browser_cockpit_launcher.py \
  -q
```

## Manual Product Acceptance Probe

Run a launcher-managed PM instance and issue:

```text
给一款AI日程工具做一个简单的landing page，写一份PRD，然后创建绑定一个track
```

Acceptance signs:

- The buddy calls `prepare` first.
- The buddy uses `runtime_context` to identify PM can create PRD, create/update/advance/archive track state, and hand off to Market.
- The buddy does not inspect `manifest.toml`, `framework/contracts/*.json`, `buddyswitch/env-profiles/*.json`, or `scripts/turn_runtime.py` to infer allowed actions.
- Persist creates PRD artifact, track state, task update, receipt, and handoff.
- Final response reports receipt and concise summary.

Run a launcher-managed Market instance on the handoff:

Acceptance signs:

- The buddy sees browser evidence requirement in `runtime_context`.
- Missing evidence rejection explains how to issue evidence.
- Evidence issuance response says exactly which `tool_evidence` field to include.
- Market does not bypass browser-native evidence with ordinary web search unless an approved downgrade token exists.

## Non-Cheating Rules

- Do not test private helper names as the primary proof of behavior.
- Do not assert a long fixed prose string when a structured field proves the requirement.
- Do not add tests that pass by hardcoding one AI calendar prompt path.
- Do not consider a rejection test valid unless it also proves no state write occurred.
- Do not consider AGENTS changes valid unless runtime output carries the removed guidance.
