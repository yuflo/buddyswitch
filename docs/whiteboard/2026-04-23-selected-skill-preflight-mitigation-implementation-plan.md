# Selected-Skill Preflight Mitigation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tighten the product-mode host prompt contract so selected-skill execution metadata is treated as explicit preflight guidance before selected-skill external tool use, reducing `web-first / cockpit-later` drift without adding buddy-specific hardcoding.

**Architecture:** This batch is a prompt-contract mitigation, not runtime enforcement. The implementation keeps BuddySwitch declarative: the selected skill already exports execution metadata through `skill.toml` and `tool_scope`; the host prompt is tightened so the host interprets that metadata before selected-skill external tool invocation and evidence capture. If the same failure repeats after this batch, the next stronger layer is approval/interrupt or real tool-surface narrowing, not more prose.

**Tech Stack:** Markdown prompt surfaces, launcher workspace injection, Python `pytest`, BuddySwitch manifest/runtime metadata

---

## Community Baseline

This plan is intentionally constrained by current community best practice:

- GitHub Copilot custom instructions are non-deterministic and should stay short, specific, and broadly applicable. This batch must not overclaim prompt edits as guarantees.
- LangChain HITL guidance treats approval/interrupt as the correct stronger control for risky tool calls; prompt-only control is mitigation, not hard enforcement.
- Anthropic guidance prefers clear declarative tool contracts and simple composable patterns over bespoke hardcoded branches.

Operational consequence for this plan:

- no `if buddy == market`
- no skill-specific hardcoded branch
- no semantic drift that turns `required_tools` into a new repo-wide hard gate
- no claim that this batch "enforces" or "prevents" tool misuse

## Scope

This plan covers:

- tightening `tools/launcher/assets/runtime-AGENTS.md` as the incident-critical prompt surface
- mirroring the same semantics minimally in `.codex/agents/router.toml` for repo prompt consistency
- adding semantic prompt-contract coverage in `tests/test_repo_consistency.py`
- strengthening launcher propagation coverage in `tests/test_buddyswitch_launcher.py`

This plan does not cover:

- changing `buddyswitch/skills/market/pmf-recon/skill.toml`
- changing `buddyswitch/skills/market/pmf-recon/SKILL.md`
- changing `framework/contracts/market.md` or runtime schema files
- adding code-level tool enforcement
- adding buddy-specific routing or hardcoded market behavior

## Root Cause

The bug is not that market metadata is missing. The bug is that BuddySwitch already exports selected-skill execution contract pieces, but product-mode host prompt does not operationalize them into a clear metadata-to-action preflight before selected-skill external tool invocation.

That leaves the model free to treat:

- `host_execution`
- `tool_scope`
- `login_policy`
- `fallback_policy`

as reference prose instead of first-step decision instructions.

The failing result is `web-first / cockpit-later` drift.

## File Map

**Primary modify**

- `tools/launcher/assets/runtime-AGENTS.md`
- `tests/test_repo_consistency.py`
- `tests/test_buddyswitch_launcher.py`

**Secondary consistency only**

- `.codex/agents/router.toml`

**Read-only context during implementation**

- `buddyswitch/skills/market/pmf-recon/skill.toml`
- `buddyswitch/skills/market/pmf-recon/SKILL.md`
- `scripts/env_manifest.py`
- `framework/docs/switch-spec.md`
- `framework/docs/browser-cockpit.md`

## Semantic Target

After this batch, the runtime host prompt must say the equivalent of:

- after the selected skill is chosen, treat the selected skill's `host_execution` and `tool_scope` as preflight instructions before selected-skill external tool invocation or evidence capture
- `required_tools` and `required_env` remain advisory readiness metadata
- if `discovery_mode = browser-native`, the first discovery/evidence step must begin in the declared `browser_executor`
- if `login_policy = mandatory-takeover`, pause for takeover rather than reinterpreting login as downgrade
- `temporary_allowed_tool_servers` are inactive by default and only become available after explicit user approval

The prompt must also keep three states separate:

1. declared executor missing in session
2. critical source requires takeover
3. browser-native source is genuinely blocked

These are not the same path and must not collapse into "maybe use web".

## Task 1: Freeze Prompt-Contract Semantics In Tests First

**Files:**
- Modify: `tests/test_repo_consistency.py`
- Test: `python3 -m pytest tests/test_repo_consistency.py -q`

- [ ] **Step 1: Add a failing semantic test for the runtime prompt**

Add a new test near the existing host prompt assertions:

```python
    def test_runtime_host_prompt_defines_selected_skill_preflight_mitigation(self) -> None:
        text = (ROOT / "tools" / "launcher" / "assets" / "runtime-AGENTS.md").read_text(
            encoding="utf-8"
        ).lower()

        self.assertIn("selected skill", text)
        self.assertIn("preflight", text)
        self.assertIn("host_execution", text)
        self.assertIn("tool_scope", text)
        self.assertIn("login_policy", text)
        self.assertIn("fallback_policy", text)
        self.assertIn("browser_executor", text)
        self.assertIn("browser-native", text)
        self.assertIn("explicit user approval", text)
        self.assertIn("required_tools", text)
        self.assertIn("advisory", text)
```

- [ ] **Step 2: Extend that test with negative assertions for semantic drift**

Use negative assertions so the test fails if implementation overclaims:

```python
        self.assertNotIn("for market runs", text)
        self.assertNotIn("hard gate", text)
        self.assertNotIn("enforced", text)
        self.assertNotIn("prevented", text)
        self.assertNotIn("before any external action", text)
        self.assertNotIn("required tools must be present before continuing", text)
```

- [ ] **Step 3: Add a reduced parity test for `.codex/agents/router.toml`**

Keep parity expectations smaller than runtime prompt expectations:

```python
    def test_router_prompt_mirrors_selected_skill_preflight_mitigation(self) -> None:
        text = (ROOT / ".codex" / "agents" / "router.toml").read_text(encoding="utf-8").lower()

        self.assertIn("selected skill", text)
        self.assertIn("preflight", text)
        self.assertIn("host_execution", text)
        self.assertIn("tool_scope", text)
        self.assertIn("explicit user approval", text)
        self.assertIn("advisory", text)
        self.assertNotIn("for market runs", text)
```

- [ ] **Step 4: Run the repo consistency test to watch it fail for the right reason**

Run:

```bash
python3 -m pytest tests/test_repo_consistency.py -q -k 'selected_skill_preflight or router_prompt_mirrors_selected_skill_preflight_mitigation'
```

Expected:

- FAIL because the current prompt surfaces do not yet contain the selected-skill preflight semantics

- [ ] **Step 5: Commit the failing-test baseline**

```bash
git add tests/test_repo_consistency.py
git commit -m "test: freeze selected-skill preflight prompt contract"
```

## Task 2: Tighten The Incident-Critical Runtime Prompt Surface

**Files:**
- Modify: `tools/launcher/assets/runtime-AGENTS.md`
- Test: `python3 -m pytest tests/test_repo_consistency.py -q -k 'selected_skill_preflight'`

- [ ] **Step 1: Replace the weak runtime host instruction with a compact preflight block**

Replace the current broad sentence about applying `host_execution` and `tool_scope` before browser work with a tighter block in the host responsibilities section:

```md
8. Read the selected skill's `instruction_path`, then treat the selected skill's `host_execution` and `tool_scope` as preflight instructions before selected-skill external tool invocation or evidence capture.
   - `required_tools` and `required_env` are advisory readiness metadata for the host session.
   - if the selected skill declares `discovery_mode = browser-native`, begin discovery and evidence capture in the declared `browser_executor`
   - if `login_policy = mandatory-takeover`, pause for takeover before continuing
   - if the selected skill's `tool_scope` allows temporary downgrade tools, those tools stay unavailable until explicit user approval
   - do not reinterpret missing executor availability, login takeover, and genuine browser-native blocking as the same path
```

- [ ] **Step 2: Keep the wording short and declarative**

Do not add:

```md
- profile mapping tables copied from env_manifest
- buddy-specific examples
- words like "enforced", "blocked", or "prevented"
```

Do keep:

```md
- selected skill
- preflight
- advisory
- explicit user approval
- browser_executor
- mandatory-takeover
```

- [ ] **Step 3: Run the focused repo consistency test**

Run:

```bash
python3 -m pytest tests/test_repo_consistency.py -q -k 'selected_skill_preflight'
```

Expected:

- PASS for runtime prompt semantics
- parity test may still fail until Task 3 lands

- [ ] **Step 4: Commit the runtime prompt mitigation**

```bash
git add tools/launcher/assets/runtime-AGENTS.md tests/test_repo_consistency.py
git commit -m "docs: add selected-skill preflight mitigation to runtime prompt"
```

## Task 3: Mirror The Mitigation Minimally In Router Prompt

**Files:**
- Modify: `.codex/agents/router.toml`
- Test: `python3 -m pytest tests/test_repo_consistency.py -q -k 'router_prompt_mirrors_selected_skill_preflight_mitigation'`

- [ ] **Step 1: Add a compressed parity rule to the router prompt**

Insert a shorter mirror statement in the host responsibility section:

```toml
- After choosing the selected skill, treat that skill's `host_execution` and `tool_scope` as preflight instructions before selected-skill external tool use.
- `required_tools` and `required_env` remain advisory readiness metadata.
- Browser-native discovery starts in the declared `browser_executor`.
- Temporary downgrade tools remain unavailable until explicit user approval.
- `mandatory-takeover` stays separate from downgrade handling.
```

- [ ] **Step 2: Keep router scope narrower than runtime prompt**

Do not duplicate the full runtime prose block. Router parity is for repo consistency only.

- [ ] **Step 3: Run the reduced router parity test**

Run:

```bash
python3 -m pytest tests/test_repo_consistency.py -q -k 'router_prompt_mirrors_selected_skill_preflight_mitigation'
```

Expected:

- PASS

- [ ] **Step 4: Commit the router parity update**

```bash
git add .codex/agents/router.toml tests/test_repo_consistency.py
git commit -m "docs: mirror selected-skill preflight mitigation in router prompt"
```

## Task 4: Prove Launcher Propagates The Updated Runtime Prompt

**Files:**
- Modify: `tests/test_buddyswitch_launcher.py`
- Test: `python3 -m pytest tests/test_buddyswitch_launcher.py -q -k 'runtime_agents or workspace_sync'`

- [ ] **Step 1: Strengthen the start-path workspace AGENTS test**

Replace the first-line-only assertion with exact content equality:

```python
            template_text = (ROOT / "tools" / "launcher" / "assets" / "runtime-AGENTS.md").read_text(
                encoding="utf-8"
            )
            self.assertEqual(agents_md.read_text(encoding="utf-8"), template_text)
```

- [ ] **Step 2: Strengthen the workspace-sync restore test the same way**

Replace the header assertion in the sync test with:

```python
            template_text = (ROOT / "tools" / "launcher" / "assets" / "runtime-AGENTS.md").read_text(
                encoding="utf-8"
            )
            self.assertEqual((workspace_dir / "AGENTS.md").read_text(encoding="utf-8"), template_text)
```

- [ ] **Step 3: Keep launcher tests focused on propagation, not prompt semantics**

Do not add token-level semantic assertions to launcher tests. Prompt semantics belong in `tests/test_repo_consistency.py`.

- [ ] **Step 4: Run the launcher subset**

Run:

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py -q -k 'runtime_agents or workspace_sync'
```

Expected:

- PASS

- [ ] **Step 5: Commit the launcher propagation proof**

```bash
git add tests/test_buddyswitch_launcher.py
git commit -m "test: verify launcher installs current runtime prompt template"
```

## Task 5: Final Verification And Scope Check

**Files:**
- Verify only touched files from Tasks 1-4

- [ ] **Step 1: Run the combined targeted verification**

Run:

```bash
python3 -m pytest tests/test_repo_consistency.py tests/test_buddyswitch_launcher.py -q
```

Expected:

- PASS

- [ ] **Step 2: Check scope**

Run:

```bash
git diff --name-only
```

Expected:

- only:
  - `tools/launcher/assets/runtime-AGENTS.md`
  - `.codex/agents/router.toml`
  - `tests/test_repo_consistency.py`
  - `tests/test_buddyswitch_launcher.py`

- [ ] **Step 3: Commit the final batch**

```bash
git add tools/launcher/assets/runtime-AGENTS.md .codex/agents/router.toml tests/test_repo_consistency.py tests/test_buddyswitch_launcher.py
git commit -m "docs: tighten selected-skill preflight mitigation for runtime prompts"
```

## Reviewer Rubric For This Plan

Use this rubric before implementation signoff:

- Root cause or symptom:
  - must stay framed as missing metadata-to-action preflight operationalization
- Boundary violation or not:
  - must not add buddy-specific or market-specific hardcoding
- Overclaim risk:
  - must not use `enforced`, `hard gate`, `prevented`, `blocked`, or similar wording
- Verification quality:
  - tests must prove prompt semantics tightened and launcher propagates the runtime template
- Residual risk:
  - must explicitly state this batch is mitigation, not tool enforcement

## Escalation Path If This Mitigation Fails Again

If the same product-mode failure repeats after this batch, do not add more prose first.

Next stronger layer:

1. selected-run approval/interrupt before temporary tool-scope widening
2. launcher-level exposure narrowing so only `allowed_tool_servers` are available by default
3. behavioral eval/trace for:
   - selected skill requires `chrome-devtools-cockpit`
   - `web` is not available until explicit approval

## Execution Handoff

Plan complete and saved to `docs/whiteboard/2026-04-23-selected-skill-preflight-mitigation-implementation-plan.md`.

Two execution options:

1. Subagent-Driven (recommended) - dispatch a fresh subagent per task, review between tasks
2. Inline Execution - execute tasks in this session with checkpoints
