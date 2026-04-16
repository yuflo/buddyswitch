# Market Chrome MCP Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `switch market: ...` runs default to Chrome MCP browser-native research, forbid silent search API downgrade, and keep Phase 1 focused on smooth webpage browsing plus multi-source text capture.

**Architecture:** Tighten the active market contract at four layers that already exist in BuddySwitch: skill metadata, active skill/docs contract, selected-skill runtime execution steps, and market output schema/test boundaries. Do not build a new audit engine or generalized tool-permission system; instead, reuse `selected_skill_packet.execution_constraints` and `execution_steps` as the hard host-facing contract, while relaxing screenshot/interaction evidence requirements so the browsing loop is the only new behavior being forced in Phase 1.

**Tech Stack:** Python runtime (`scripts/env_manifest.py`, `scripts/switch_runtime.py`), TOML skill packages, Markdown skill/docs contracts, JSON schemas, `pytest`-based repo/runtime boundary tests, Chrome DevTools MCP (`chrome-devtools-market`).

---

## File Structure

- Modify `buddyswitch/skills/market/research-scan/skill.toml`
  - Add the explicit Chrome MCP execution metadata and stop leaving `required_tools` empty.
- Modify `buddyswitch/skills/market/pmf-recon/skill.toml`
  - Keep metadata aligned with the shared market cockpit contract.
- Modify `buddyswitch/skills/market/customer-discovery/skill.toml`
  - Keep metadata aligned with the shared market cockpit contract.
- Modify `buddyswitch/skills/market/positioning-copy/skill.toml`
  - Keep metadata aligned with the shared market cockpit contract.
- Modify `buddyswitch/skills/market/channel-discovery/skill.toml`
  - Keep metadata aligned with the shared market cockpit contract.
- Modify `buddyswitch/skills/market/launch-prep/skill.toml`
  - Keep metadata aligned with the shared market cockpit contract.
- Modify `scripts/env_manifest.py`
  - Extend the enforced market `host_execution` metadata surface with the minimal new Phase 1 fields.
- Modify `scripts/switch_runtime.py`
  - Make `selected_skill_packet.execution_steps` explicitly require Chrome MCP browser-native discovery and explicit approval for one-off downgrade.
- Modify `framework/docs/market-research-cockpit.md`
  - Rewrite the cockpit contract around Chrome MCP browser-native discovery instead of generic browser-first wording.
- Modify `framework/contracts/market.md`
  - Align the market buddy contract with browser-native discovery, no silent degrade, and user-approved one-off exception handling.
- Modify `framework/docs/switch-spec.md`
  - Clarify that `required_tools` stays advisory while `execution_constraints` and `execution_steps` carry the enforceable host contract for market runs.
- Modify `framework/templates/research-report.md`
  - Remove `search-assist` guidance from the shared template.
- Modify `buddyswitch/skills/market/research-scan/SKILL.md`
  - Remove `search-assist` wording and describe browser-native search/result/detail/comment browsing.
- Modify `buddyswitch/skills/market/pmf-recon/SKILL.md`
  - Remove `search-assist` wording and align runtime contract text.
- Modify `buddyswitch/skills/market/customer-discovery/SKILL.md`
  - Align runtime contract text with browser-native research behavior.
- Modify `buddyswitch/skills/market/positioning-copy/SKILL.md`
  - Align runtime contract text with browser-native research behavior.
- Modify `buddyswitch/skills/market/channel-discovery/SKILL.md`
  - Align runtime contract text with browser-native research behavior.
- Modify `buddyswitch/skills/market/launch-prep/SKILL.md`
  - Align runtime contract text with browser-native research behavior.
- Modify `framework/schemas/market/research-scan.json`
  - Keep useful text evidence fields required while making screenshot/interaction fields optional for Phase 1.
- Modify `framework/schemas/market/pmf-recon.json`
  - Keep useful text evidence fields required while making screenshot/interaction fields optional for Phase 1.
- Modify `framework/schemas/market/customer-discovery.json`
  - Keep useful text evidence fields required while making screenshot/interaction fields optional for Phase 1.
- Modify `framework/schemas/market/positioning-copy.json`
  - Keep useful text evidence fields required while making screenshot/interaction fields optional for Phase 1.
- Modify `framework/schemas/market/channel-discovery.json`
  - Keep useful text evidence fields required while making screenshot/interaction fields optional for Phase 1.
- Modify `framework/schemas/market/launch-prep.json`
  - Keep useful text evidence fields required while making screenshot/interaction fields optional for Phase 1.
- Modify `buddyswitch/skills/market/research-scan/assets/research-report-template.md`
  - Remove screenshot/interaction evidence requirements from the Phase 1 template.
- Modify `buddyswitch/skills/market/pmf-recon/assets/pmf-report-template.md`
  - Remove screenshot/interaction evidence requirements from the Phase 1 template.
- Modify `buddyswitch/skills/market/customer-discovery/assets/interview-brief-template.md`
  - Remove screenshot/interaction evidence requirements from the Phase 1 template.
- Modify `buddyswitch/skills/market/positioning-copy/assets/positioning-brief-template.md`
  - Remove screenshot/interaction evidence requirements from the Phase 1 template.
- Modify `buddyswitch/skills/market/channel-discovery/assets/channel-plan-template.md`
  - Remove screenshot/interaction evidence requirements from the Phase 1 template.
- Modify `buddyswitch/skills/market/launch-prep/assets/launch-prep-template.md`
  - Remove screenshot/interaction evidence requirements from the Phase 1 template.
- Modify `tests/test_env_manifest_v2.py`
  - Enforce the new market cockpit metadata shape.
- Modify `tests/test_repo_consistency.py`
  - Lock the new shared metadata, required evidence fields, and active-doc wording boundaries.
- Modify `tests/test_switch_runtime.py`
  - Lock the new `host_execution` payload and the new market execution step order.
- Modify `tests/test_output_schema_boundaries.py`
  - Update the evidence-boundary tests to match the lighter Phase 1 schema.
- Create `docs/dev0220/market-chrome-mcp-phase1-manual-checklist.md`
  - Give the user a tight manual test checklist for post-implementation body-feel validation.

## Task 1: Lock Market Metadata To Chrome MCP

**Files:**
- Modify: `buddyswitch/skills/market/research-scan/skill.toml`
- Modify: `buddyswitch/skills/market/pmf-recon/skill.toml`
- Modify: `buddyswitch/skills/market/customer-discovery/skill.toml`
- Modify: `buddyswitch/skills/market/positioning-copy/skill.toml`
- Modify: `buddyswitch/skills/market/channel-discovery/skill.toml`
- Modify: `buddyswitch/skills/market/launch-prep/skill.toml`
- Modify: `scripts/env_manifest.py`
- Test: `tests/test_env_manifest_v2.py`
- Test: `tests/test_repo_consistency.py`

- [ ] **Step 1: Write the failing metadata tests**

```python
# tests/test_env_manifest_v2.py
self.assertEqual(
    runtime["host_execution"],
    {
        "execution_mode": "market-browser-native",
        "browser_mode": "headed-only",
        "browser_profile": "shared-market",
        "browser_executor": "chrome-devtools-market",
        "discovery_mode": "browser-native",
        "login_policy": "mandatory-takeover",
        "fallback_policy": "no-silent-degrade",
        "session_continuity": "shared-cockpit",
        "evidence_capture_level": "medium",
    },
)

# tests/test_repo_consistency.py
MARKET_COCKPIT_METADATA = {
    "execution_mode": "market-browser-native",
    "browser_mode": "headed-only",
    "browser_profile": "shared-market",
    "browser_executor": "chrome-devtools-market",
    "discovery_mode": "browser-native",
    "login_policy": "mandatory-takeover",
    "fallback_policy": "no-silent-degrade",
    "session_continuity": "shared-cockpit",
    "evidence_capture_level": "medium",
}

def test_market_skill_tomls_require_chrome_devtools_market(self) -> None:
    for path in SKILL_TOMLS[:6]:
        parsed = env_manifest._load_toml(path)
        self.assertEqual(parsed["required_tools"], ["chrome-devtools-market"])
```

- [ ] **Step 2: Run the metadata tests and confirm they fail**

Run:

```bash
python3 -m pytest tests/test_env_manifest_v2.py tests/test_repo_consistency.py -q
```

Expected: FAIL because the market `host_execution` payload does not yet include `browser_executor` / `discovery_mode`, and the market `skill.toml` files still declare `required_tools = []`.

- [ ] **Step 3: Add the minimal new market metadata surface**

```python
# scripts/env_manifest.py
HOST_EXECUTION_FIELDS = (
    "execution_mode",
    "browser_mode",
    "browser_profile",
    "browser_executor",
    "discovery_mode",
    "login_policy",
    "fallback_policy",
    "session_continuity",
    "evidence_capture_level",
)

MARKET_COCKPIT_HOST_EXECUTION = {
    "execution_mode": "market-browser-native",
    "browser_mode": "headed-only",
    "browser_profile": "shared-market",
    "browser_executor": "chrome-devtools-market",
    "discovery_mode": "browser-native",
    "login_policy": "mandatory-takeover",
    "fallback_policy": "no-silent-degrade",
    "session_continuity": "shared-cockpit",
    "evidence_capture_level": "medium",
}
```

```toml
# buddyswitch/skills/market/*/skill.toml
required_tools = ["chrome-devtools-market"]
required_env = []
execution_mode = "market-browser-native"
browser_mode = "headed-only"
browser_profile = "shared-market"
browser_executor = "chrome-devtools-market"
discovery_mode = "browser-native"
login_policy = "mandatory-takeover"
fallback_policy = "no-silent-degrade"
session_continuity = "shared-cockpit"
evidence_capture_level = "medium"
```

- [ ] **Step 4: Re-run the metadata tests and confirm they pass**

Run:

```bash
python3 -m pytest tests/test_env_manifest_v2.py tests/test_repo_consistency.py -q
```

Expected: PASS for the new market metadata contract checks.

- [ ] **Step 5: Commit the metadata lock-in**

```bash
git add \
  buddyswitch/skills/market/*/skill.toml \
  scripts/env_manifest.py \
  tests/test_env_manifest_v2.py \
  tests/test_repo_consistency.py
git commit -m "feat: lock market metadata to chrome mcp"
```

## Task 2: Rewrite The Active Market Contract Around Browser-Native Discovery

**Files:**
- Modify: `framework/docs/market-research-cockpit.md`
- Modify: `framework/contracts/market.md`
- Modify: `framework/docs/switch-spec.md`
- Modify: `framework/templates/research-report.md`
- Modify: `buddyswitch/skills/market/research-scan/SKILL.md`
- Modify: `buddyswitch/skills/market/pmf-recon/SKILL.md`
- Modify: `buddyswitch/skills/market/customer-discovery/SKILL.md`
- Modify: `buddyswitch/skills/market/positioning-copy/SKILL.md`
- Modify: `buddyswitch/skills/market/channel-discovery/SKILL.md`
- Modify: `buddyswitch/skills/market/launch-prep/SKILL.md`
- Test: `tests/test_repo_consistency.py`

- [ ] **Step 1: Add failing active-doc wording tests**

```python
# tests/test_repo_consistency.py
def test_market_active_docs_require_chrome_mcp_and_remove_search_assist(self) -> None:
    targets = (
        ROOT / "framework" / "docs" / "market-research-cockpit.md",
        ROOT / "framework" / "contracts" / "market.md",
        ROOT / "framework" / "templates" / "research-report.md",
        *(path for path in ARTIFACT_SKILL_DOCS[:6]),
    )
    for path in targets:
        text = path.read_text(encoding="utf-8").lower()
        self.assertIn("chrome-devtools-market", text)
        self.assertIn("browser-native", text)
        self.assertIn("user-approved", text)
        self.assertNotIn("search-assist", text)
```

- [ ] **Step 2: Run the active-doc test and confirm it fails**

Run:

```bash
python3 -m pytest tests/test_repo_consistency.py -q
```

Expected: FAIL because the active docs still contain `search-assist` and do not consistently mention `chrome-devtools-market` or the explicit user-approved downgrade boundary.

- [ ] **Step 3: Rewrite the active docs and skill docs with the new Phase 1 contract**

```markdown
# framework/docs/market-research-cockpit.md
- `browser_executor = "chrome-devtools-market"`
- `discovery_mode = "browser-native"`

3. Browser-native discovery first
- Use `chrome-devtools-market` as the shared market browser executor.
- Discovery happens inside the browser: search result pages, destination pages, detail pages, and comment threads.
- Do not silently fall back to search APIs, snippets, or crawler excerpts.

4. Explicit one-off exception only
- If browser access is blocked after normal attempts, stop and ask for explicit user approval before any one-time downgrade.
- The approved exception is narrow and per blocked need; it is not a mode switch for the rest of the run.
```

```markdown
# buddyswitch/skills/market/research-scan/SKILL.md
## Research Defaults
- Collection mode: `browser-native`
- Use `chrome-devtools-market` for search result browsing, destination-page reading, and deeper detail/comment exploration.
- Do not treat search APIs, snippets, or crawler excerpts as the default discovery path.
- If browser access stays blocked, ask for explicit user approval before any one-time exception downgrade.
```

```markdown
# framework/docs/switch-spec.md
- `required_tools` and `required_env` remain advisory.
- Market-specific browser enforcement belongs in `selected_skill_packet.execution_constraints` and `selected_skill_packet.execution_steps`.
```

- [ ] **Step 4: Re-run the repo consistency tests and confirm they pass**

Run:

```bash
python3 -m pytest tests/test_repo_consistency.py -q
```

Expected: PASS, with no active `search-assist` wording left in the tested documents.

- [ ] **Step 5: Commit the active-contract rewrite**

```bash
git add \
  framework/docs/market-research-cockpit.md \
  framework/contracts/market.md \
  framework/docs/switch-spec.md \
  framework/templates/research-report.md \
  buddyswitch/skills/market/*/SKILL.md \
  tests/test_repo_consistency.py
git commit -m "docs: rewrite market contract for browser-native discovery"
```

## Task 3: Make Selected Skill Packets Fail Closed To Chrome MCP

**Files:**
- Modify: `scripts/switch_runtime.py`
- Test: `tests/test_switch_runtime.py`

- [ ] **Step 1: Update the runtime tests to match the new packet contract**

```python
# tests/test_switch_runtime.py
self.assertEqual(
    pmf_card.get("host_execution"),
    {
        "execution_mode": "market-browser-native",
        "browser_mode": "headed-only",
        "browser_profile": "shared-market",
        "browser_executor": "chrome-devtools-market",
        "discovery_mode": "browser-native",
        "login_policy": "mandatory-takeover",
        "fallback_policy": "no-silent-degrade",
        "session_continuity": "shared-cockpit",
        "evidence_capture_level": "medium",
    },
)

self.assertEqual(
    prepared["selected_skill_packet"]["execution_steps"],
    [
        "Use the chrome-devtools-market browser before any market research.",
        "Read selected inputs by slot before other work.",
        "Perform discovery inside the browser: browse search results, destination pages, detail pages, and comment threads before synthesizing.",
        "Pause for takeover if a critical source requires login.",
        "If browser access remains blocked, ask for explicit user approval before any one-time downgrade.",
        "Do not continue with snippet-only or text-only research.",
        "Only after the steps above should you synthesize findings into the structured result.",
    ],
)
```

- [ ] **Step 2: Run the runtime tests and confirm they fail**

Run:

```bash
python3 -m pytest tests/test_switch_runtime.py -q
```

Expected: FAIL because the current runtime packet still says only `Open a visible browser...` and does not mention Chrome MCP, browser-native discovery, or explicit one-time downgrade approval.

- [ ] **Step 3: Tighten the packet execution contract**

```python
# scripts/switch_runtime.py
def _build_execution_steps(
    *,
    host_execution: dict[str, Any],
    selected_inputs: list[dict[str, Any]],
) -> list[str]:
    steps: list[str] = []
    if host_execution.get("execution_mode") == "market-browser-native":
        browser_executor = host_execution.get("browser_executor", "chrome-devtools-market")
        steps.append(f"Use the {browser_executor} browser before any market research.")
        if selected_inputs:
            steps.append("Read selected inputs by slot before other work.")
        steps.extend(
            [
                "Perform discovery inside the browser: browse search results, destination pages, detail pages, and comment threads before synthesizing.",
                "Pause for takeover if a critical source requires login.",
                "If browser access remains blocked, ask for explicit user approval before any one-time downgrade.",
                "Do not continue with snippet-only or text-only research.",
                "Only after the steps above should you synthesize findings into the structured result.",
            ]
        )
        return steps
```

- [ ] **Step 4: Re-run the runtime tests and confirm they pass**

Run:

```bash
python3 -m pytest tests/test_switch_runtime.py -q
```

Expected: PASS for the new packet constraints and market execution-step ordering.

- [ ] **Step 5: Commit the runtime fail-closed change**

```bash
git add scripts/switch_runtime.py tests/test_switch_runtime.py
git commit -m "feat: make market execution packets chrome-mcp first"
```

## Task 4: Relax Market Evidence Schemas To A Phase 1 Text-First Baseline

**Files:**
- Modify: `framework/schemas/market/research-scan.json`
- Modify: `framework/schemas/market/pmf-recon.json`
- Modify: `framework/schemas/market/customer-discovery.json`
- Modify: `framework/schemas/market/positioning-copy.json`
- Modify: `framework/schemas/market/channel-discovery.json`
- Modify: `framework/schemas/market/launch-prep.json`
- Modify: `buddyswitch/skills/market/research-scan/assets/research-report-template.md`
- Modify: `buddyswitch/skills/market/pmf-recon/assets/pmf-report-template.md`
- Modify: `buddyswitch/skills/market/customer-discovery/assets/interview-brief-template.md`
- Modify: `buddyswitch/skills/market/positioning-copy/assets/positioning-brief-template.md`
- Modify: `buddyswitch/skills/market/channel-discovery/assets/channel-plan-template.md`
- Modify: `buddyswitch/skills/market/launch-prep/assets/launch-prep-template.md`
- Test: `tests/test_output_schema_boundaries.py`
- Test: `tests/test_repo_consistency.py`

- [ ] **Step 1: Write the failing schema-boundary tests**

```python
# tests/test_output_schema_boundaries.py
errors = output_schema.validate_output_payload(payload, schema)

self.assertIn(
    "$.artifact_content.evidence[0]: missing required property 'page_title'",
    errors,
)
self.assertIn(
    "$.artifact_content.evidence[0]: missing required property 'auth_state'",
    errors,
)
self.assertIn(
    "$.artifact_content.evidence[0]: missing required property 'query_or_filter_used'",
    errors,
)
self.assertNotIn(
    "$.artifact_content.evidence[0]: missing required property 'interaction_steps_summary'",
    errors,
)
self.assertNotIn(
    "$.artifact_content.evidence[0]: missing required property 'screenshot_ref_or_snapshot_ref'",
    errors,
)
```

```python
# tests/test_repo_consistency.py
MARKET_EVIDENCE_FIELDS = (
    "source_id",
    "url",
    "source_type",
    "accessed_at",
    "claim_excerpt",
    "page_title",
    "auth_state",
    "query_or_filter_used",
)
```

- [ ] **Step 2: Run the schema tests and confirm they fail**

Run:

```bash
python3 -m pytest tests/test_output_schema_boundaries.py tests/test_repo_consistency.py -q
```

Expected: FAIL because the current schemas still require `interaction_steps_summary` and `screenshot_ref_or_snapshot_ref`.

- [ ] **Step 3: Make screenshot and interaction fields optional across all market schemas and templates**

```json
// framework/schemas/market/research-scan.json
"required": [
  "source_id",
  "url",
  "source_type",
  "accessed_at",
  "claim_excerpt",
  "page_title",
  "auth_state",
  "query_or_filter_used"
],
"properties": {
  "source_id": { "type": "string" },
  "url": { "type": "string" },
  "source_type": { "type": "string" },
  "accessed_at": { "type": "string" },
  "claim_excerpt": { "type": "string" },
  "page_title": { "type": "string" },
  "auth_state": { "type": "string", "enum": ["public", "logged_in", "paywalled", "unknown"] },
  "query_or_filter_used": { "type": "string" },
  "interaction_steps_summary": { "type": "string" },
  "screenshot_ref_or_snapshot_ref": { "type": "string" }
}
```

```markdown
# buddyswitch/skills/market/research-scan/assets/research-report-template.md
- query_or_filter_used:

# Remove these two Phase 1 lines from every market asset template
- interaction_steps_summary:
- screenshot_ref_or_snapshot_ref:
```

- [ ] **Step 4: Re-run the schema tests and confirm they pass**

Run:

```bash
python3 -m pytest tests/test_output_schema_boundaries.py tests/test_repo_consistency.py -q
```

Expected: PASS, with market evidence staying text-rich but no longer blocked by screenshot or interaction bookkeeping.

- [ ] **Step 5: Commit the lighter Phase 1 evidence baseline**

```bash
git add \
  framework/schemas/market/*.json \
  buddyswitch/skills/market/*/assets/*.md \
  tests/test_output_schema_boundaries.py \
  tests/test_repo_consistency.py
git commit -m "refactor: relax market evidence schema for phase1 browsing"
```

## Task 5: Add A Manual Body-Feel Checklist Under `docs/dev0220`

**Files:**
- Create: `docs/dev0220/market-chrome-mcp-phase1-manual-checklist.md`

- [ ] **Step 1: Write the manual checklist document**

```markdown
# Market Chrome MCP Phase 1 Manual Checklist

## Setup
1. Run `bash scripts/setup_market_chrome_devtools.sh --status`
2. If not reachable, run `bash scripts/setup_market_chrome_devtools.sh`
3. Confirm `chrome-devtools-market` is available in the active Codex session

## Manual Runs
1. `switch market: Research demand for AI companion live spaces`
   - Expect the run to browse inside Chrome MCP first
   - Expect search and page reading to happen in-browser
   - Expect no silent API-search fallback wording

2. `switch market: Compare creator monetization products and capture evidence`
   - Expect result-page -> destination-page -> detail-page browsing depth
   - Expect multi-source text capture from browsed pages

3. `switch market: Validate whether playlist collaboration is becoming a standard expectation`
   - If a source blocks browser access, expect an explicit request for one-time downgrade approval
   - Expect no automatic downgrade without approval
```

- [ ] **Step 2: Verify the checklist file exists and is readable**

Run:

```bash
test -f docs/dev0220/market-chrome-mcp-phase1-manual-checklist.md
sed -n '1,220p' docs/dev0220/market-chrome-mcp-phase1-manual-checklist.md
```

Expected: file exists and prints the setup plus three concrete `switch market` manual checks.

- [ ] **Step 3: Commit the manual validation guide**

```bash
git add docs/dev0220/market-chrome-mcp-phase1-manual-checklist.md
git commit -m "docs: add market chrome mcp phase1 manual checklist"
```

## Final Verification

- [ ] Run the focused test suite after all five tasks:

```bash
python3 -m pytest \
  tests/test_env_manifest_v2.py \
  tests/test_repo_consistency.py \
  tests/test_switch_runtime.py \
  tests/test_output_schema_boundaries.py -q
```

Expected: PASS.

- [ ] Run one final grep sweep to confirm no active `search-assist` wording remains:

```bash
rg -n "search-assist" \
  framework/docs \
  framework/contracts \
  framework/templates \
  buddyswitch/skills/market \
  tests
```

Expected: no matches in the active implementation paths touched by this plan.

## Self-Review

- Spec coverage: the plan covers the four Phase 1 enforcement layers we already identified in repo context: metadata, active docs/skills contract, runtime packet execution order, and schema/template boundaries. It also adds a manual checklist so the user can immediately test the post-implementation body feel.
- Placeholder scan: no placeholder markers remain. All modified files, commands, and expected failures/passes are explicit.
- Type consistency: the new metadata keys are consistently named `browser_executor` and `discovery_mode`, and the downgrade behavior is described as an explicit user-approved one-time exception without inventing a second policy subsystem.
