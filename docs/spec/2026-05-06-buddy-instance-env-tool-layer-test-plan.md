# Buddy Instance Env Tool Layer Test Plan

**Goal:** Verify that BuddySwitch buddy instances receive executed environment boundaries from env profiles: profile-derived filesystem writes, controlled runtime state commits, browser evidence gates, active-buddy skills, and runtime AGENTS context projection.

**Testing Principle:** Tests must start from functional requirements and observable product behavior. Do not construct tests around private helper names, permissive fallback branches, or synthetic shortcuts whose only purpose is to make implementation pass. Private helpers may be tested only for narrow validation units; product behavior must be tested through launcher commands, public runtime CLI, broker protocol, or generated config/state artifacts.

---

## Functional Requirements Under Test

FR1. Every manifest buddy has exactly one env profile, and every profile validates against the compact profile contract.

FR2. Env profiles are the machine-readable capability source; runtime `AGENTS.md` explains the environment but is not the permission source.

FR3. `instance start --buddy market` and `instance open inst-pm-example` validate manifest buddy, env profile, and runtime AGENTS projection before launching Codex.

FR4. Product-mode Codex config writable roots are compiled from the active buddy profile.

FR5. Market, PM, Design, and Test see live `projects/app` but cannot write it through either the runtime symlink or the resolved shared project workspace target.

FR6. Dev sees live `projects/app` and can write project source, while raw BuddySwitch state remains broker-only.

FR7. No buddy host process receives raw write access to `${BUDDYSWITCH_SHARED_ROOT}/state`, `buddyswitch/objects/**`, or `buddyswitch/content/runs/**`.

FR8. Product-mode `prepare` and `persist` keep their public CLI shape but route through the launcher-managed runtime broker.

FR9. Product-mode `prepare`/`persist` fail explicitly when the runtime broker is unavailable; they must not fall back to direct host state writes.

FR10. Runtime broker enforces active instance identity and active buddy identity for every product-mode runtime request.

FR11. Runtime broker enforces prepared context and run-envelope integrity before state writes.

FR12. Persist validates artifact kinds from the active buddy manifest/profile boundary and rejects unauthorized kinds before writes.

FR13. Persist allows track lifecycle mutations only for PM profile authority.

FR14. Persist task effects are limited to `status` and `summary` on the current prepared task.

FR15. Persist handoff targets must be manifest buddies.

FR16. Market profile requires browser cockpit and browser-native evidence for artifact-producing research commits.

FR17. Market research persist without broker-issued browser evidence or broker-issued approved downgrade is rejected before writes.

FR18. Market research persist with broker-issued browser evidence succeeds and records evidence details in run audit.

FR19. Market research persist with broker-issued approved downgrade succeeds and records downgrade details in run audit.

FR20. PM, Design, Dev, and Test profiles do not require Market browser evidence.

FR21. Non-Market browser cockpit is available but not launch-blocking when Chrome is unavailable.

FR22. Runtime AGENTS projection for each buddy describes source access, scratch root, broker-only state, active skills, prepare/persist loop, rejection handling, and buddy-specific handoff boundaries.

FR23. Active buddy skills are materialized under `.agents/skills`; inactive buddy skills are absent.

FR24. Test buddy can run checks and write scratch/test-report state through persist, but cannot edit source, tests, fixtures, snapshots, or generated source under `projects/app`.

FR25. The implementation removes the product-mode direct state write path instead of preserving it as a convenience fallback.

## Coverage Matrix

| Requirement | Test Group | Observable Proof |
| --- | --- | --- |
| FR1 | TG-01 | profile files match manifest buddies, contract order, enums, paths, and buddy matrix |
| FR2 | TG-07, TG-10 | docs/templates say AGENTS is context projection; permission behavior is proven by config/broker tests |
| FR3 | TG-03 | start/open invalid profile cases fail before shared state mutation; valid cases launch from profile |
| FR4 | TG-02 | generated `config.toml` writable roots match profile matrix |
| FR5 | TG-02, TG-08 | non-dev config excludes project workspace; real sandbox write probes deny symlink and target writes |
| FR6 | TG-02, TG-08 | Dev config includes project workspace; Dev source write probe succeeds; state write probe fails |
| FR7 | TG-02, TG-04, TG-08 | config excludes state roots; broker writes state; host raw write probes fail |
| FR8 | TG-04 | product CLI calls broker and returns prepare/persist payloads |
| FR9 | TG-04 | missing broker returns `ok=false` without state writes |
| FR10 | TG-04 | broker rejects mismatched instance id and active buddy |
| FR11 | TG-05 | stale context, replayed run id, and mismatched envelope reject before writes |
| FR12 | TG-05 | unauthorized artifact kinds reject atomically |
| FR13 | TG-05 | PM lifecycle succeeds; Market/Design/Dev/Test lifecycle rejects |
| FR14 | TG-05 | arbitrary task id or unsupported task field rejects |
| FR15 | TG-05 | unknown handoff buddy rejects before writes |
| FR16 | TG-06 | Market profile requires browser cockpit and evidence; launch treats Market browser as required |
| FR17 | TG-06 | Market artifact persist without evidence rejects and state snapshot is unchanged |
| FR18 | TG-06 | broker-issued browser token allows Market persist and appears in run audit |
| FR19 | TG-06 | broker-issued downgrade token allows Market persist and records reason |
| FR20 | TG-05, TG-06 | PM/Design/Dev/Test persist without `tool_evidence` succeeds when otherwise valid |
| FR21 | TG-03, TG-06 | non-Market launch continues with warning when browser unavailable |
| FR22 | TG-07 | runtime AGENTS validator and template content checks pass for all buddies |
| FR23 | TG-03, TG-07 | active `.agents/skills` contains only active buddy skills |
| FR24 | TG-02, TG-08 | Test source write probes fail; scratch write and persist report succeed |
| FR25 | TG-04, TG-10 | product CLI without broker fails; repo search/doc checks show no direct product state fallback |

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

Negative data must be product-meaningful:

- missing profile;
- profile buddy mismatch;
- non-dev source write;
- raw state write;
- wrong active buddy;
- wrong instance id;
- stale context;
- replayed run id;
- unauthorized track action;
- unauthorized artifact kind;
- unknown handoff buddy;
- missing Market evidence;
- Market evidence token for another run.

Do not use fake values whose only purpose is to trigger a private branch.

## Canonical Commit Fixtures

### PM Valid Commit

```json
{
  "execution_summary": "PM wrote the AI schedule tool landing page PRD and created the delivery track.",
  "working_notes": [
    "The user requested PRD creation and track binding in one PM run."
  ],
  "artifacts": [
    {
      "kind": "prd",
      "title": "AI Schedule Tool Landing Page PRD",
      "summary": "Defines landing page scope, sections, MVP requirements, and acceptance criteria.",
      "content": {
        "problem": "Busy professionals need an AI-assisted way to reduce scheduling overhead.",
        "target_users": ["calendar-heavy professionals", "small team operators"],
        "landing_page_sections": ["hero", "pain points", "AI scheduling value", "use cases", "CTA"],
        "requirements": ["Explain the core promise in the hero", "Show concrete scheduling workflows"],
        "acceptance_criteria": ["A downstream design buddy can derive a page flow from this PRD"]
      }
    }
  ],
  "state_effects": {
    "track": {
      "action": "create",
      "track_id": "track-ai-schedule-landing-page",
      "title": "AI Schedule Tool Landing Page",
      "status": "active",
      "current_buddy": "pm",
      "next_buddy": "market",
      "summary": "Cross-buddy landing page iteration for an AI schedule tool."
    },
    "task": {
      "status": "done",
      "summary": "PM PRD is ready for market positioning research."
    }
  },
  "handoff": {
    "next_buddy": "market",
    "reason": "Market should validate competitor landing page positioning before design.",
    "context": "Use the PRD artifact and track summary as source context."
  },
  "contributors": {
    "skills": ["write-prd", "track-manager"],
    "agents": []
  }
}
```

### Market Valid Commit With Browser Evidence

```json
{
  "execution_summary": "Market analyzed AI scheduling landing page competitors and recommended positioning angles.",
  "working_notes": [
    "The request referenced the existing PM-created track."
  ],
  "artifacts": [
    {
      "kind": "market-scan",
      "title": "AI Schedule Tool Landing Page Market Brief",
      "summary": "Summarizes competitor messaging patterns and recommended landing page expression.",
      "content": {
        "research_question": "How should an AI schedule tool express and present itself on a landing page?",
        "evidence": [
          {
            "source": "browser-cockpit-preflight",
            "claim": "Browser cockpit was available for the current Market run."
          }
        ],
        "insights": ["Calendar automation messaging needs concrete workflow moments."],
        "assumptions": ["Competitor pages are representative of current category language."],
        "risks": ["Evidence depth is limited to the first browser proof loop."],
        "conclusion": "Lead with recovered focus time and reduced scheduling back-and-forth.",
        "recommended_next_step": "Design should shape a hero flow around concrete before/after scheduling moments."
      }
    }
  ],
  "handoff": {
    "next_buddy": "design",
    "reason": "Design can combine PRD scope with market positioning.",
    "context": "Use the PRD artifact and market scan artifact on this track."
  },
  "contributors": {
    "skills": ["research-scan", "positioning-copy"],
    "agents": []
  }
}
```

Execution rule: this static fixture intentionally omits `tool_evidence`. Test harnesses must inject a real `tool_evidence.browser_cockpit_token` issued by `scripts/browser_evidence.py issue` for the current run envelope.

### Market Valid Commit With Approved Downgrade

```json
{
  "execution_summary": "Market recorded a user-approved downgrade for AI scheduling landing page research and summarized limited public evidence.",
  "working_notes": [
    "The browser cockpit path was blocked and the user explicitly approved a one-off downgrade."
  ],
  "artifacts": [
    {
      "kind": "market-scan",
      "title": "AI Schedule Tool Landing Page Market Brief With Downgrade",
      "summary": "Records limited evidence gathered under an explicit user-approved downgrade.",
      "content": {
        "research_question": "How should an AI schedule tool express and present itself on a landing page?",
        "evidence": [
          {
            "source": "approved-downgrade",
            "claim": "User approved one-off fallback because browser-native access was blocked."
          }
        ],
        "insights": ["Limited evidence should not be treated as a complete market scan."],
        "assumptions": ["Downgrade evidence is lower confidence than browser-native discovery."],
        "risks": ["Market conclusion may miss page-level details."],
        "conclusion": "Use only as a temporary positioning input until browser-native research is available.",
        "recommended_next_step": "Repeat browser-native research when cockpit access is restored."
      }
    }
  ],
  "handoff": {
    "next_buddy": "pm",
    "reason": "PM should decide whether limited evidence is enough for the next iteration.",
    "context": "Treat this artifact as downgraded evidence."
  },
  "contributors": {
    "skills": ["research-scan"],
    "agents": []
  }
}
```

Execution rule: this static fixture intentionally omits `tool_evidence`. Test harnesses must inject a real `tool_evidence.approved_downgrade_token` issued by `scripts/browser_evidence.py approve-downgrade` for the current run envelope.

### Test Buddy Valid Commit

```json
{
  "execution_summary": "Test ran landing page smoke checks and reported readiness without editing source.",
  "working_notes": [
    "Test buddy inspected behavior and wrote report state only."
  ],
  "artifacts": [
    {
      "kind": "test-report",
      "title": "Landing Page Smoke Test Report",
      "summary": "Reports pass/fail results for landing page hero and CTA behavior.",
      "content": {
        "test_scope": ["landing page hero", "CTA click behavior"],
        "checks_run": ["manual DOM smoke", "static asset load check"],
        "passed_items": ["hero renders"],
        "failed_items": [],
        "blocked_items": [],
        "reproduction_notes": [],
        "readiness": "ready-for-pm-review"
      }
    }
  ],
  "state_effects": {
    "task": {
      "status": "done",
      "summary": "Landing page smoke checks passed."
    }
  },
  "handoff": {
    "next_buddy": "pm",
    "reason": "PM can review readiness.",
    "context": "Use the smoke test report artifact."
  },
  "contributors": {
    "skills": ["smoke-test"],
    "agents": []
  }
}
```

## Anti-Cheat Rules

- Do not assert permission behavior only by reading `AGENTS.md`; prove it with generated config, broker rejection, or sandbox write probes.
- Do not make tests pass by allowing both direct product-mode state writes and broker writes.
- Do not add a fallback that writes raw state when broker routing fails.
- Do not use broad writable roots in tests and then mask them from assertions.
- Do not treat fake Codex launch tests as proof of real sandbox denial; real sandbox write probes are required for final verification.
- Do not accept raw hand-written Market downgrade records as evidence; evidence and downgrade records must be broker-issued.
- Do not call private persist helpers for product-mode behavior tests when the public CLI or broker protocol is the behavior under test.
- Do not skip non-dev resolved symlink target tests; writing through `projects/app` and writing the resolved target are separate risks.
- Do not construct negative tests around helper names or exception wording only; every negative must correspond to a product boundary.
- Do not leave tests that preserve legacy prompt-only or direct host-state-write assumptions.

## Test Groups

### TG-01: Env Profile Contract And Buddy Matrix

Requirements: FR1, FR2.

Cases:

1. Manifest buddies and profile files match exactly.
   - Flow: load `buddyswitch/manifest.toml`; list `buddyswitch/env-profiles/*.json`.
   - Expected: profile names are exactly `market`, `pm`, `design`, `dev`, `test`.

2. Every profile validates against the compact contract.
   - Flow: run `python3 scripts/env_profiles.py validate-all`.
   - Expected: output contains `market: ok`, `pm: ok`, `design: ok`, `dev: ok`, and `test: ok`.

3. Filename and `buddy_id` match.
   - Flow: load each profile.
   - Expected: `market.json` has `"buddy_id": "market"` and so on.

4. Contract path exists for every profile.
   - Expected: profile contract paths are exactly `framework/contracts/market.md`, `framework/contracts/pm.md`, `framework/contracts/design.md`, `framework/contracts/dev.md`, and `framework/contracts/test.md`.

5. Project access matrix is correct.
   - Expected: Market/PM/Design/Test are `read-only`; Dev is `write`.

6. Scratch roots are buddy-specific.
   - Expected: `runs/raw/market`, `runs/raw/pm`, `runs/raw/design`, `runs/raw/dev`, `runs/raw/test`.

7. State authority matrix is correct.
   - Expected: PM has `create/update/advance/archive`; other buddies have no track effects.

8. Tool capability matrix is correct.
   - Expected: Market has browser required, evidence required, ordinary fallback user-approved only.
   - Expected: PM/Design/Dev/Test have browser available and evidence not required.

9. Temporary invalid profile fixture fails.
   - Input: copy Market profile to temp root and change `buddy_id` to `pm`.
   - Expected: validator raises or CLI exits non-zero before any launcher mutation.

Commands:

```bash
python3 -m unittest tests.test_buddy_env_profiles -v
python3 scripts/env_profiles.py validate-all
```

### TG-02: Profile-Derived Codex Sandbox Roots

Requirements: FR4, FR5, FR6, FR7, FR24.

Cases:

1. Non-dev writable roots exclude forbidden boundaries.
   - Buddies: Market, PM, Design, Test.
   - Expected excluded roots: shared root, instance root, execution workspace root, shared project root, project workspace, shared state root, runtime state projection paths.

2. Dev writable roots include project workspace only as source write authority.
   - Expected: Dev includes `${BUDDYSWITCH_SHARED_ROOT}/project/workspace`.
   - Expected: Dev excludes shared root, shared project root, shared state root, instance root, execution workspace root.

3. Every buddy includes common safe roots.
   - Expected: instance home, instance codex-home, instance xdg-config, the active buddy scratch root, `/tmp`, and safe `$TMPDIR`.

4. Unsafe temp roots are skipped.
   - Input: `--temp-root` equal to source checkout, source Codex home, state root, or project root.
   - Expected: root not rendered in config.

5. Config patch is idempotent.
   - Flow: run config patch twice.
   - Expected: one managed sandbox block and one `[sandbox_workspace_write]` block.

6. MCP approvals are preserved.
   - Input: existing `[mcp_servers.chrome-devtools-cockpit]`.
   - Expected: section has `default_tools_approval_mode = "approve"`.

7. Missing profile leaves config unchanged.
   - Input: invoke patch with unknown buddy or missing profile path in temp fixture.
   - Expected: non-zero exit and original config text unchanged.

8. Test buddy source path classes are not writable.
   - Expected generated roots do not include `projects/app`, `projects/app/tests`, fixture paths, snapshot paths, or generated source paths.

Commands:

```bash
python3 -m unittest tests.test_buddy_env_sandbox -v
```

### TG-03: Launcher Assembly And Open Revalidation

Requirements: FR3, FR21, FR22, FR23.

Cases:

1. Unknown buddy fails before shared root mutation.
   - Flow: `./buddyswitch-codex instance start --buddy unknown`.
   - Expected: non-zero exit, no shared root created.

2. Missing profile fails before instance mutation.
   - Setup: temporary repo fixture without `buddyswitch/env-profiles/pm.json`.
   - Flow: locked start bootstrap for PM.
   - Expected: no instance record, no state root, no project worktree, no config write.

3. Profile buddy mismatch fails before mutation.
   - Setup: temp profile file has filename `pm.json` and `buddy_id="market"`.
   - Expected: start fails before shared root mutation.

4. Valid Market start validates profile and active skills.
   - Expected: instance record buddy is `market`.
   - Expected: `.agents/skills/research-scan` exists.
   - Expected: `.agents/skills/write-prd` does not exist.
   - Expected: `AGENTS.md` contains Market browser evidence wording.

5. Valid Dev start validates source write authority.
   - Expected: runtime AGENTS says Dev can write `projects/app`.
   - Expected: config includes project workspace.

6. Valid Test start validates no source edit authority.
   - Expected: runtime AGENTS says Test must hand source fixes to Dev.
   - Expected: config excludes project workspace.

7. `instance open` revalidates profile and AGENTS.
   - Setup: valid inactive instance.
   - Flow: corrupt active buddy AGENTS template.
   - Expected: open fails before Codex launch and leaves instance inactive.

8. Non-Market browser unavailable is warning-only.
   - Setup: PM instance with Chrome binary unavailable.
   - Expected: launch/open continues with warning and no evidence-required mode.

9. Market browser unavailable is launch-blocking.
   - Setup: Market instance with Chrome binary unavailable.
   - Expected: launch/open fails and explains browser cockpit is required.

Commands:

```bash
python3 -m unittest tests.test_buddyswitch_launcher -v
python3 -m unittest tests.test_browser_cockpit_launcher -v
```

### TG-04: Product Runtime Broker Routing

Requirements: FR8, FR9, FR10, FR25.

Cases:

1. Broker prepare succeeds with matching identity.
   - Setup: runtime broker serving an instance JSON with buddy `pm`.
   - Flow: send broker `prepare` request for PM ordinary request.
   - Expected: response payload has `ok=true`, active buddy `pm`, instance id, task id, and reserved run id.

2. Broker persist succeeds with matching identity.
   - Setup: use context from broker prepare.
   - Flow: send broker `persist` with PM valid commit.
   - Expected: response payload has `ok=true`; run audit exists in projected state.

3. Wrong instance id is rejected.
   - Flow: send request with `instance_id` not matching instance JSON.
   - Expected: `ok=false`; no state writes.

4. Wrong active buddy is rejected.
   - Flow: instance JSON buddy is `pm`, request active buddy is `market`.
   - Expected: `ok=false`; no state writes.

5. Product CLI prepare routes through broker.
   - Flow: run `python3 scripts/turn_runtime.py prepare "给一款AI日程工具做一个简单的landing page，写一份PRD，然后创建绑定一个track"` with product env and broker socket.
   - Expected: output is broker payload, not direct host write.

6. Product CLI persist routes through broker.
   - Flow: run `persist --context --result` with product env and broker socket.
   - Expected: broker writes state and output matches broker response.

7. Product CLI without broker fails explicitly.
   - Flow: product env is set, `BUDDYSWITCH_RUNTIME_BROKER_SOCKET` missing or socket unreachable.
   - Expected: `ok=false`, error code `E_RUNTIME_BROKER_UNAVAILABLE`, state snapshot unchanged.

8. Non-product unit path remains available for tests/debug.
   - Flow: no product env; call public Python function in isolated runtime workspace.
   - Expected: direct function behavior works only outside product mode.

Commands:

```bash
python3 -m unittest tests.test_runtime_broker -v
python3 -m unittest tests.test_turn_runtime -v
```

### TG-05: State Capability Enforcement

Requirements: FR11, FR12, FR13, FR14, FR15, FR20.

Cases:

1. PM track create succeeds.
   - Flow: PM prepare, persist PM valid commit.
   - Expected: track object created, task bound, run audit records `track_action=create`.

2. PM track update/advance/archive succeed when valid.
   - Setup: existing track bound to PM prepared task.
   - Expected: each action applies expected track mutation and records run audit.

3. Market track lifecycle is rejected before writes.
   - Input: Market valid artifact commit plus `state_effects.track.action=create`.
   - Expected: rejection and state snapshot unchanged.

4. Design track lifecycle is rejected before writes.
   - Input: Design commit with `state_effects.track.action=advance`.
   - Expected: rejection and state snapshot unchanged.

5. Dev track lifecycle is rejected before writes.
   - Input: Dev commit with `state_effects.track.action=archive`.
   - Expected: rejection and state snapshot unchanged.

6. Test track lifecycle is rejected before writes.
   - Input: Test commit with `state_effects.track.action=update`.
   - Expected: rejection and state snapshot unchanged.

7. Unauthorized artifact kind is rejected before writes.
   - Input: PM commit with artifact kind `market-scan`.
   - Expected: rejection and no artifact/run/task/track mutation.

8. Duplicate artifact kind is rejected before writes.
   - Input: two `prd` artifacts in one PM commit.
   - Expected: rejection and state snapshot unchanged.

9. Unsupported task effect field is rejected.
   - Input: `state_effects.task` contains `task_id`.
   - Expected: rejection because task effects are current-task-only.

10. Unknown handoff target is rejected.
    - Input: handoff next buddy `ops`.
    - Expected: rejection and state snapshot unchanged.

11. Stale context is rejected.
    - Setup: prepare context, mutate task by another valid persist, reuse old context.
    - Expected: rejection before writes.

12. Replayed run envelope is rejected.
    - Flow: persist once with a context, then persist again with same context.
    - Expected: second attempt rejects before writes.

13. Non-Market buddies do not require `tool_evidence`.
    - Flow: PM/Design/Dev/Test valid artifact commits without `tool_evidence`.
    - Expected: each succeeds when other capability rules are satisfied.

Commands:

```bash
python3 -m unittest tests.test_turn_runtime -v
python3 -m unittest tests.test_turn_integration -v
```

### TG-06: Market Browser Evidence Gate

Requirements: FR16, FR17, FR18, FR19, FR20, FR21.

Cases:

1. Market profile requires browser evidence.
   - Expected: profile has `browser_cockpit=required` and `market_research_evidence=required`.

2. Browser evidence issue requires Market.
   - Flow: run `scripts/browser_evidence.py issue` in PM context.
   - Expected: `ok=false`; no token record.

3. Browser preflight token requires current run envelope.
   - Input: Market context without run envelope.
   - Expected: `ok=false`; no token record.

4. Browser preflight token requires reachable endpoint.
   - Setup: Market instance JSON has browser port with no server.
   - Expected: `ok=false`; no token record.

5. Browser preflight token succeeds.
   - Setup: test HTTP server responds to `/json/version`.
   - Flow: Market prepare, broker evidence issue.
   - Expected: token record under instance runtime evidence directory for same run id.

6. Market persist without evidence rejects.
   - Input: Market valid commit with no `tool_evidence`.
   - Expected: `ok=false`; state snapshot unchanged.

7. Market persist with broker-issued browser token succeeds.
   - Input: Market valid commit with `browser_cockpit_token`.
   - Expected: run audit has `tool_evidence.kind=browser-cockpit-preflight` and token metadata.

8. Market persist with token for another run rejects.
   - Input: token issued for run A, commit uses context for run B.
   - Expected: rejection and state snapshot unchanged.

9. Market persist with hand-written token rejects.
   - Input: token string with no broker record.
   - Expected: rejection and state snapshot unchanged.

10. Approved downgrade token requires reason.
    - Flow: `approve-downgrade` with empty reason.
    - Expected: `ok=false`; no token record.

11. Approved downgrade token succeeds and records reason.
    - Flow: `approve-downgrade --reason "Browser-native cockpit blocked; user approved one-off downgrade."`
    - Expected: token record includes reason.

12. Market persist with approved downgrade token succeeds.
    - Expected: run audit includes downgrade reason under `tool_evidence`.

Commands:

```bash
python3 -m unittest tests.test_market_browser_evidence -v
python3 -m unittest tests.test_browser_cockpit_launcher -v
```

### TG-07: Runtime AGENTS Projection And Active Skills

Requirements: FR2, FR22, FR23, FR24.

Cases:

1. Runtime AGENTS validator passes for all buddies.
   - Flow: `python3 scripts/runtime_agents.py validate-all`.
   - Expected: output contains `market: ok`, `pm: ok`, `design: ok`, `dev: ok`, and `test: ok`.

2. Market AGENTS explains browser evidence gate.
   - Expected: contains `chrome-devtools-cockpit`, browser-native, approved downgrade, and persist rejection wording.

3. PM AGENTS explains track lifecycle authority.
   - Expected: PM owns track lifecycle through `state_effects.track`; source is read-only.

4. Design AGENTS explains source read-only and Dev handoff.
   - Expected: Design cannot edit source and should hand implementation to Dev.

5. Dev AGENTS explains source write authority and broker-only state.
   - Expected: Dev can edit `projects/app`; raw state still persists through broker.

6. Test AGENTS explains no source/test fixture edits.
   - Expected: Test can run checks and write scratch/report state but must hand fixes to Dev.

7. Active buddy skills only.
   - Flow: materialize PM skills in runtime workspace.
   - Expected: `write-prd` and `track-manager` exist; Market skills absent.

8. Test buddy skills only.
   - Flow: materialize Test skills.
   - Expected: `smoke-test` exists; `implement-task` absent.

Commands:

```bash
python3 scripts/runtime_agents.py validate-all
python3 -m unittest tests.test_runtime_skills -v
python3 -m unittest tests.test_buddyswitch_launcher -v
```

### TG-08: Real Sandbox Product Probes

Requirements: FR5, FR6, FR7, FR8, FR16, FR17, FR18, FR24.

These are manual or integration probes because fake Codex tests do not enforce Codex sandbox writes.

1. PM source and raw state writes are denied.
   - Flow: start disposable PM instance and run a Codex exec script that writes `projects/app/pm-probe.txt` and `buddyswitch/objects/tasks/pm-probe.json`.
   - Expected: both writes fail; no probe files exist in shared project or state.

2. PM prepare/persist still works.
   - Flow: in same PM instance, run public prepare/persist CLI with PM valid commit.
   - Expected: persist succeeds through broker and writes canonical state.

3. Dev source write succeeds and raw state write fails.
   - Flow: start disposable Dev instance and write `projects/app/dev-probe.txt`; then attempt raw state write.
   - Expected: source file exists in shared project workspace; raw state write fails.

4. Test source/test fixture writes are denied.
   - Flow: start disposable Test instance and attempt writes under `projects/app`, `projects/app/tests`, fixture, snapshot, and generated source paths.
   - Expected: every source path write fails.

5. Test scratch write and persist report succeed.
   - Flow: write `runs/raw/test/probe.log`; persist Test valid commit.
   - Expected: scratch write succeeds; persist writes test-report artifact through broker.

6. Market missing evidence persist rejects.
   - Flow: start disposable Market instance, prepare, persist Market valid commit with no `tool_evidence`.
   - Expected: persist returns `ok=false`; no artifact/run writes.

7. Market browser evidence persist succeeds.
   - Flow: issue browser preflight token, persist Market valid commit with token.
   - Expected: persist returns `ok=true`; run audit records evidence.

Concrete probe commands:

```bash
export BUDDYSWITCH_SHARED_ROOT="$(mktemp -d)/.codex-buddyswitch"
./buddyswitch-codex instance start --buddy pm -- exec 'python3 - <<'"'"'PY'"'"'
from pathlib import Path
for target in [Path("projects/app/pm-probe.txt"), Path("buddyswitch/objects/tasks/pm-probe.json")]:
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("probe\n", encoding="utf-8")
        print(f"UNEXPECTED_WRITE:{target}")
    except Exception as exc:
        print(f"DENIED:{target}:{type(exc).__name__}")
PY'
./buddyswitch-codex instance start --buddy dev -- exec 'python3 - <<'"'"'PY'"'"'
from pathlib import Path
source = Path("projects/app/dev-probe.txt")
source.write_text("dev-ok\n", encoding="utf-8")
print(source.read_text(encoding="utf-8").strip())
state = Path("buddyswitch/objects/tasks/dev-probe.json")
try:
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text("{}\n", encoding="utf-8")
    print("UNEXPECTED_STATE_WRITE")
except Exception as exc:
    print(f"STATE_DENIED:{type(exc).__name__}")
PY'
./buddyswitch-codex instance start --buddy test -- exec 'python3 - <<'"'"'PY'"'"'
from pathlib import Path
scratch = Path("runs/raw/test/probe.log")
scratch.parent.mkdir(parents=True, exist_ok=True)
scratch.write_text("scratch-ok\n", encoding="utf-8")
print(scratch.read_text(encoding="utf-8").strip())
for target in [Path("projects/app/test-probe.txt"), Path("projects/app/tests/test-probe.txt"), Path("projects/app/__snapshots__/test-probe.txt")]:
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("probe\n", encoding="utf-8")
        print(f"UNEXPECTED_WRITE:{target}")
    except Exception as exc:
        print(f"DENIED:{target}:{type(exc).__name__}")
PY'
./buddyswitch-codex instance start --buddy market -- exec 'mkdir -p runs/raw/market && python3 scripts/turn_runtime.py prepare "调研 AI 日程工具 landing page 竞品表达和定位方式" > runs/raw/market/context.json && python3 - <<'"'"'PY'"'"'
import json
from pathlib import Path
payload = {
    "execution_summary": "Market attempted AI scheduling landing page research without browser evidence.",
    "working_notes": ["This probe intentionally omits tool_evidence to prove runtime rejection."],
    "artifacts": [
        {
            "kind": "market-scan",
            "title": "Missing Evidence Probe",
            "summary": "This artifact should be rejected because Market evidence is missing.",
            "content": {
                "research_question": "How should an AI schedule tool express itself?",
                "evidence": [],
                "insights": [],
                "assumptions": [],
                "risks": ["No browser-native evidence was provided."],
                "conclusion": "Reject this commit.",
                "recommended_next_step": "Issue browser evidence token first."
            }
        }
    ]
}
Path("runs/raw/market/market-result-without-evidence.json").write_text(json.dumps(payload, ensure_ascii=True), encoding="utf-8")
PY
python3 scripts/turn_runtime.py persist --context runs/raw/market/context.json --result runs/raw/market/market-result-without-evidence.json'
```

Expected proof is command output plus absence/presence of probe files in the shared project/state roots.

### TG-09: Cross-Buddy Flow Smoke

Requirements: FR8, FR12, FR13, FR16, FR18, FR20, FR22, FR23.

Flow:

1. Start PM instance.
   - Prepare PM request.
   - Persist PM valid commit creating `track-ai-schedule-landing-page`.
   - Expected: track exists and next buddy is Market.

2. Start Market instance bound to same track.
   - Prepare Market request with existing track binding.
   - Issue browser evidence token.
   - Persist Market valid commit with evidence and handoff to Design.
   - Expected: Market artifact exists and run audit records evidence.

3. Start Design instance bound to same track.
   - Prepare Design request.
   - Persist Design handoff artifact without track lifecycle mutation.
   - Expected: Design artifact exists; track lifecycle fields unchanged except allowed task/run indexes.

4. Start Dev instance bound to same track.
   - Modify `projects/app` source.
   - Persist Dev implementation report.
   - Expected: source write succeeds; Dev report exists.

5. Start Test instance bound to same track.
   - Run checks without source edits.
   - Persist Test report.
   - Expected: Test report exists; no source modifications by Test.

Observable proof:

- track artifact index shows PRD, Market brief, Design handoff, Dev report, and Test report;
- each run audit has correct buddy id and run id;
- only Dev changed project source;
- Market run audit includes evidence.

### TG-10: Repo Consistency And Legacy Path Removal

Requirements: FR2, FR7, FR25.

Cases:

1. Docs identify profile as capability source.
   - Expected: architecture and runtime docs mention `buddyswitch/env-profiles`.

2. Docs identify AGENTS as context projection only.
   - Expected: no tracked docs state that AGENTS is permission source.

3. Product direct state write fallback is absent.
   - Expected: repo search finds no product-mode fallback text that writes state directly when broker is unavailable.

4. Manual/debug APIs stay marked as manual/debug.
   - Expected: docs or code comments do not present `scripts/env_tracks.py` or `scripts/env_artifacts.py` as product runtime permission path.

5. No repo-root `.agents` tracked.
   - Expected: `git ls-files .agents` returns empty.

6. No runtime state skeleton directories tracked as product source.
   - Expected: tracked runtime state files remain absent except intentional docs/tests fixtures.

Commands:

```bash
python3 -m unittest tests.test_repo_consistency -v
git ls-files .agents
git status --short
```

## Atomicity Checks

Every rejection test must snapshot these locations before and after the rejected operation:

- `buddyswitch/objects/tracks/*.json`
- `buddyswitch/objects/tasks/*.json`
- `buddyswitch/objects/artifacts/*.json`
- `buddyswitch/content/runs/*.json`
- `buddyswitch/content/runs/reserved/*.json`
- active instance `instance.json` current task/track binding
- `$BUDDYSWITCH_INSTANCE_ROOT/runtime/evidence-tokens/**` when evidence issuance is under test

Expected for persist rejection:

- no artifact written;
- no run audit written;
- no task mutation;
- no track mutation;
- reservation remains unchanged unless the operation explicitly failed after a successful commit, which should not happen in validation rejection tests;
- instance binding unchanged.

Expected for evidence issuance rejection:

- no token file written;
- no canonical state write.

## Required Verification Commands

Focused suite:

```bash
python3 -m unittest \
  tests.test_buddy_env_profiles \
  tests.test_buddy_env_sandbox \
  tests.test_runtime_broker \
  tests.test_market_browser_evidence \
  tests.test_turn_runtime \
  tests.test_turn_integration \
  tests.test_buddyswitch_launcher \
  tests.test_browser_cockpit_launcher \
  tests.test_runtime_skills \
  tests.test_repo_consistency \
  -v
```

Full suite:

```bash
python3 -m unittest discover tests -v
```

Manual probes:

Run TG-08 using fresh disposable `BUDDYSWITCH_SHARED_ROOT` values and collect observable proof for all seven TG-08 cases. The concrete commands above are the baseline write-denial probes; final acceptance also requires PM broker-routed prepare/persist in the same PM instance, Dev source-write plus state-denial evidence, Test scratch/write-denial plus broker persist, and both Market missing-evidence rejection and broker-issued browser-evidence success.

Completion requires fresh output from the focused suite, full suite, and the manual probes or a documented blocker explaining why a manual probe could not run.

## Verification Checkpoint (2026-05-07)

Current acceptance focus:
- TG-08 must prove actual Codex sandbox denial for non-dev source/state writes, not only generated config shape.
- PM evidence must combine direct write-denial probes and broker-routed prepare/persist in the same disposable PM instance.
- Test evidence must include denied source/test/fixture/snapshot/generated writes plus scratch and broker persist success.
- Market evidence must include missing-evidence rejection and broker-issued browser-evidence success.

Test acceptance gate before completion:
- Re-run TG-08 probes with fresh `BUDDYSWITCH_SHARED_ROOT` values and no stale browser processes.
- Re-run focused suite.
- Re-run full suite `python3 -m unittest discover tests -v`.
- Re-run independent test-agent and final reviewer-agent acceptance against FR1-FR25.
