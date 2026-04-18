# Market Declarative Tool Scoping Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce `switch market: ...` execution drift by making the allowed information-acquisition channel explicit and machine-readable per run, without hardcoding market skill semantics into runtime control flow.

**Architecture:** Keep SKILL content as the semantic source of truth, and add one declarative `tool_scope_profile` metadata surface for market execution. Normalize that profile into a reusable `tool_scope` object in runtime metadata, materialize it into `selected_skill_packet`, and tighten docs/tests around host consumption of that policy. Do not touch `buddyswitch-codex`, do not build a generalized permission engine, and do not add persist-time compliance auditing in this batch.

**Tech Stack:** Python runtime (`scripts/env_manifest.py`, `scripts/switch_runtime.py`), TOML skill packages, Markdown contracts, JSON packet payloads, `pytest` repo/runtime tests.

---

## File Structure

- Modify: `buddyswitch/skills/market/research-scan/skill.toml`
  - Add the shared declarative tool scope profile reference.
- Modify: `buddyswitch/skills/market/pmf-recon/skill.toml`
  - Add the shared declarative tool scope profile reference.
- Modify: `buddyswitch/skills/market/customer-discovery/skill.toml`
  - Add the shared declarative tool scope profile reference.
- Modify: `buddyswitch/skills/market/positioning-copy/skill.toml`
  - Add the shared declarative tool scope profile reference.
- Modify: `buddyswitch/skills/market/channel-discovery/skill.toml`
  - Add the shared declarative tool scope profile reference.
- Modify: `buddyswitch/skills/market/launch-prep/skill.toml`
  - Add the shared declarative tool scope profile reference.
- Modify: `scripts/env_manifest.py`
  - Normalize `tool_scope_profile` into a reusable `tool_scope` object during skill package loading.
- Modify: `scripts/switch_runtime.py`
  - Expose `tool_scope` in skill cards and `selected_skill_packet`.
- Modify: `framework/docs/browser-cockpit.md`
  - State that host execution must apply packet-level tool scope before market research starts.
- Modify: `framework/docs/switch-spec.md`
  - Document the new declarative tool scope surface and keep it distinct from `required_tools`.
- Modify: `framework/contracts/market.md`
  - Align the market contract with packet-level declarative tool scoping.
- Modify: `tests/test_env_manifest_v2.py`
  - Lock manifest parsing for `tool_scope_profile` and normalized `tool_scope`.
- Modify: `tests/test_repo_consistency.py`
  - Lock the shared market profile declaration across all six market skill packages.
- Modify: `tests/test_switch_runtime.py`
  - Lock skill-card and `selected_skill_packet` exposure of `tool_scope`.
- Create: `docs/dev1626/2026-04-18-market-declarative-tool-scoping-manual-checklist.md`
  - Add a small manual checklist for representative market runs.

## Non-Goals

- No launcher changes in `buddyswitch-codex`.
- No generalized cross-buddy tool permission system.
- No per-skill hardcoded branching such as `if skill_id == "research-scan"`.
- No persist-time compliance audit gate in this batch.
- No changes to non-market buddies.

### Task 1: Lock the Declarative Market Tool Scope Contract in Tests

**Files:**
- Modify: `tests/test_env_manifest_v2.py`
- Modify: `tests/test_repo_consistency.py`
- Modify: `tests/test_switch_runtime.py`

- [ ] **Step 1: Add the failing manifest test for `tool_scope_profile` normalization**

```python
# tests/test_env_manifest_v2.py
def test_load_manifest_reads_market_tool_scope_profile(self) -> None:
    manifest = self._load_demo_market_manifest(
        """\
        id = "demo-skill"
        buddy = "market"
        description = "Use when demo market work is requested."
        objects = ["task", "artifact"]
        produces_artifact = true
        output_slot = "market-scan"
        input_slots = ["research-question"]
        output_schema = "framework/schemas/market/research-scan.json"
        produces = ["market-scan"]
        consumes = ["research-question"]
        side_effect_level = "medium"
        required_tools = ["chrome-devtools-cockpit"]
        required_env = []
        execution_mode = "browser-cockpit-native"
        browser_mode = "headed-only"
        browser_profile = "shared-browser"
        browser_executor = "chrome-devtools-cockpit"
        discovery_mode = "browser-native"
        login_policy = "mandatory-takeover"
        fallback_policy = "no-silent-degrade"
        session_continuity = "shared-cockpit"
        evidence_capture_level = "medium"
        tool_scope_profile = "market-browser-native"
        allowed_task_kinds = ["research"]
        """
    )

    runtime = manifest["skills"][0]["runtime"]
    self.assertEqual(runtime["tool_scope_profile"], "market-browser-native")
    self.assertEqual(
        runtime["tool_scope"],
        {
            "profile": "market-browser-native",
            "mode": "allowlist",
            "allowed_tool_servers": ["chrome-devtools-cockpit"],
            "downgrade_policy": "user-approved-one-off",
            "temporary_allowed_tool_servers": ["web"],
            "downgrade_reason": "browser-native-blocked",
        },
    )
```

- [ ] **Step 2: Add the failing repo consistency test for all six market skill packages**

```python
# tests/test_repo_consistency.py
def test_market_skills_share_market_tool_scope_profile(self) -> None:
    for path in SKILL_TOMLS[:6]:
        with self.subTest(skill_toml=str(path.relative_to(ROOT))):
            parsed = env_manifest._load_toml(path)  # type: ignore[attr-defined]
            self.assertEqual(parsed["tool_scope_profile"], "market-browser-native")
```

- [ ] **Step 3: Add the failing runtime packet tests**

```python
# tests/test_switch_runtime.py
EXPECTED_MARKET_TOOL_SCOPE = {
    "profile": "market-browser-native",
    "mode": "allowlist",
    "allowed_tool_servers": ["chrome-devtools-cockpit"],
    "downgrade_policy": "user-approved-one-off",
    "temporary_allowed_tool_servers": ["web"],
    "downgrade_reason": "browser-native-blocked",
}

def test_market_skill_cards_expose_tool_scope(self) -> None:
    payload = switch_runtime.resolve_switch("switch market: Research demand for AI companion live spaces")
    research_scan = next(card for card in payload["skill_cards"] if card["id"] == "research-scan")
    self.assertEqual(research_scan["tool_scope"], EXPECTED_MARKET_TOOL_SCOPE)

def test_prepare_execution_includes_market_tool_scope(self) -> None:
    resolved = switch_runtime.resolve_switch("switch market: Research demand for AI companion live spaces")
    packet = switch_runtime.prepare_execution_payload(resolved, skill_id="research-scan")
    self.assertEqual(packet["selected_skill_packet"]["tool_scope"], EXPECTED_MARKET_TOOL_SCOPE)
```

- [ ] **Step 4: Run the focused tests and confirm they fail for the missing contract**

Run:

```bash
python3 -m pytest tests/test_env_manifest_v2.py -k tool_scope -v
python3 -m pytest tests/test_repo_consistency.py -k tool_scope -v
python3 -m pytest tests/test_switch_runtime.py -k tool_scope -v
```

Expected: FAIL because `tool_scope_profile` and packet-level `tool_scope` do not exist yet.

- [ ] **Step 5: Commit the failing tests**

```bash
git add tests/test_env_manifest_v2.py tests/test_repo_consistency.py tests/test_switch_runtime.py
git commit -m "test: lock declarative market tool scope contract"
```

### Task 2: Add Shared Declarative Tool Scope Metadata for Market Skills

**Files:**
- Modify: `scripts/env_manifest.py`
- Modify: `buddyswitch/skills/market/research-scan/skill.toml`
- Modify: `buddyswitch/skills/market/pmf-recon/skill.toml`
- Modify: `buddyswitch/skills/market/customer-discovery/skill.toml`
- Modify: `buddyswitch/skills/market/positioning-copy/skill.toml`
- Modify: `buddyswitch/skills/market/channel-discovery/skill.toml`
- Modify: `buddyswitch/skills/market/launch-prep/skill.toml`

- [ ] **Step 1: Add a reusable tool scope profile registry in `env_manifest.py`**

```python
# scripts/env_manifest.py
TOOL_SCOPE_PROFILES = {
    "market-browser-native": {
        "profile": "market-browser-native",
        "mode": "allowlist",
        "allowed_tool_servers": ["chrome-devtools-cockpit"],
        "downgrade_policy": "user-approved-one-off",
        "temporary_allowed_tool_servers": ["web"],
        "downgrade_reason": "browser-native-blocked",
    }
}
```

- [ ] **Step 2: Parse and validate `tool_scope_profile` during skill package loading**

```python
# scripts/env_manifest.py
tool_scope_profile = _optional_string(metadata, "tool_scope_profile", metadata_label)
tool_scope = None
if tool_scope_profile is not None:
    if tool_scope_profile not in TOOL_SCOPE_PROFILES:
        raise ManifestError(
            f"{metadata_path.relative_to(ROOT)}:tool_scope_profile '{tool_scope_profile}' is unknown"
        )
    tool_scope = dict(TOOL_SCOPE_PROFILES[tool_scope_profile])
```

- [ ] **Step 3: Return normalized tool scope in runtime metadata**

```python
# scripts/env_manifest.py
return {
    "name": skill_id,
    "buddy": metadata_buddy.strip(),
    "description": description.strip(),
    "objects": objects,
    "produces_artifact": produces_artifact,
    "output_slot": output_slot,
    "input_slots": input_slots,
    "output_schema": normalized_schema,
    "version": None,
    "side_effect_level": side_effect_level.strip() if isinstance(side_effect_level, str) else None,
    "required_tools": required_tools,
    "required_env": required_env,
    "host_execution": host_execution,
    "tool_scope_profile": tool_scope_profile,
    "tool_scope": tool_scope,
    "produces": produces,
    "consumes": consumes,
    "allowed_task_kinds": allowed_task_kinds,
    "instruction_path": instruction_path.relative_to(ROOT).as_posix(),
    "guidance": guidance,
}
```

- [ ] **Step 4: Add the shared profile reference to all six market skill packages**

```toml
# buddyswitch/skills/market/*/skill.toml
tool_scope_profile = "market-browser-native"
```

- [ ] **Step 5: Run the focused tests and confirm they pass**

Run:

```bash
python3 -m pytest tests/test_env_manifest_v2.py -k tool_scope -v
python3 -m pytest tests/test_repo_consistency.py -k tool_scope -v
```

Expected: PASS with `tool_scope_profile` and normalized `tool_scope` available for all six market skills.

- [ ] **Step 6: Commit the metadata change**

```bash
git add scripts/env_manifest.py buddyswitch/skills/market/*/skill.toml tests/test_env_manifest_v2.py tests/test_repo_consistency.py
git commit -m "feat: add declarative market tool scope metadata"
```

### Task 3: Materialize Tool Scope in `selected_skill_packet` and Host-Facing Docs

**Files:**
- Modify: `scripts/switch_runtime.py`
- Modify: `framework/docs/browser-cockpit.md`
- Modify: `framework/docs/switch-spec.md`
- Modify: `framework/contracts/market.md`
- Modify: `tests/test_switch_runtime.py`

- [ ] **Step 1: Expose `tool_scope` in market skill cards**

```python
# scripts/switch_runtime.py
card = {
    "id": skill["id"],
    "path": skill["path"],
    "instruction_path": runtime.get("instruction_path", skill["path"]),
    "description": skill["description"],
    "objects": skill["objects"],
    "produces_artifact": bool(runtime.get("produces_artifact", True)),
    "input_slots": input_slots,
    "output_schema": runtime["output_schema"],
    "version": runtime.get("version"),
    "side_effect_level": runtime.get("side_effect_level"),
    "required_tools": required_tools,
    "required_env": required_env,
    "host_execution": host_execution,
    "tool_scope": dict(runtime.get("tool_scope") or {}),
    ...
}
```

- [ ] **Step 2: Add `tool_scope` to `selected_skill_packet`**

```python
# scripts/switch_runtime.py
packet = {
    "skill_id": skill_id,
    "buddy": buddy_id,
    "instruction_path": instruction_path,
    "skill_instructions": {
        "name": skill_id,
        "path": instruction_path,
        "contents": _load_skill_instruction_text(instruction_path),
    },
    "selected_inputs": selected_inputs,
    "output_schema_path": output_schema_path.strip(),
    "execution_constraints": host_execution,
    "tool_scope": dict(selected_skill["runtime"].get("tool_scope") or {}),
    "execution_steps": _build_execution_steps(
        host_execution=host_execution,
        selected_inputs=selected_inputs,
    ),
}
```

- [ ] **Step 3: Tighten host guidance so packet-level tool scope is applied before research starts**

```markdown
<!-- framework/docs/browser-cockpit.md -->
- `selected_skill_packet.tool_scope` carries the allowed tool-server scope for the run.
- The host applies `tool_scope` before any market research begins.
- For `market-browser-native`, discovery starts with `chrome-devtools-cockpit`.
- Browser-external search is not part of the default scope; it becomes temporarily available only after explicit user-approved downgrade.
```

```markdown
<!-- framework/docs/switch-spec.md -->
- `required_tools` remains advisory metadata.
- `tool_scope` is the declarative host-facing tool boundary for the selected run.
- `execution_constraints` and `execution_steps` describe behavior; `tool_scope` narrows the permitted tool surface.
```

```markdown
<!-- framework/contracts/market.md -->
- Market runs must honor the packet-level `tool_scope`.
- Default market profile is `market-browser-native`.
- The default scope allows browser-native discovery through `chrome-devtools-cockpit`.
- Browser-external search may be temporarily widened only after explicit user-approved downgrade.
```

- [ ] **Step 4: Run the focused runtime tests and confirm they pass**

Run:

```bash
python3 -m pytest tests/test_switch_runtime.py -k tool_scope -v
python3 -m pytest tests/test_switch_runtime.py -k market_host_execution -v
```

Expected: PASS with `tool_scope` exposed in both skill cards and `selected_skill_packet`, and existing market host execution tests still green.

- [ ] **Step 5: Commit the packet and doc contract changes**

```bash
git add scripts/switch_runtime.py framework/docs/browser-cockpit.md framework/docs/switch-spec.md framework/contracts/market.md tests/test_switch_runtime.py
git commit -m "feat: expose declarative market tool scope in execution packet"
```

### Task 4: Add a Focused Manual Validation Checklist for Representative Market Runs

**Files:**
- Create: `docs/dev1626/2026-04-18-market-declarative-tool-scoping-manual-checklist.md`

- [ ] **Step 1: Write the manual checklist with three representative runs**

```markdown
# Market Declarative Tool Scoping Manual Checklist

## Preconditions
1. Run `./buddyswitch-codex start`
2. Confirm `chrome-devtools-cockpit` is available in the active session

## Case 1: Broad scan
Command: `switch market: Research demand for AI companion live spaces`
Check:
- choose `research-scan`
- `prepare-execution` packet contains `tool_scope.profile = market-browser-native`
- host begins with `chrome-devtools-cockpit`

## Case 2: PMF validation
Command: `switch market: Validate whether an AI note-taking tool for consultants has enough PMF signal to test`
Check:
- choose `pmf-recon`
- packet still contains the same `tool_scope`
- no browser-external search unless explicit user-approved downgrade is requested

## Case 3: Positioning from upstream artifacts
Command: `switch market -> track-ai-note: Turn the PMF findings into founder-facing homepage positioning`
Check:
- choose `positioning-copy`
- packet contains selected inputs plus the same `tool_scope`
- host still starts from the browser-native scope before any downgrade path
```

- [ ] **Step 2: Verify the file exists and reads cleanly**

Run:

```bash
test -f docs/dev1626/2026-04-18-market-declarative-tool-scoping-manual-checklist.md
sed -n '1,220p' docs/dev1626/2026-04-18-market-declarative-tool-scoping-manual-checklist.md
```

Expected: file exists and prints a short, readable checklist with exactly three representative market cases.

- [ ] **Step 3: Commit the manual checklist**

```bash
git add docs/dev1626/2026-04-18-market-declarative-tool-scoping-manual-checklist.md
git commit -m "docs: add market declarative tool scoping checklist"
```

## Final Verification

- [ ] Run the focused suite:

```bash
python3 -m pytest tests/test_env_manifest_v2.py -k tool_scope -v
python3 -m pytest tests/test_repo_consistency.py -k "tool_scope or market_skills_share_market_cockpit_execution_metadata" -v
python3 -m pytest tests/test_switch_runtime.py -k "tool_scope or market_host_execution" -v
```

Expected: PASS.

- [ ] Run a quick contract grep:

```bash
rg -n "tool_scope|market-browser-native|temporary_allowed_tool_servers|user-approved-one-off" \
  buddyswitch/skills/market \
  scripts/env_manifest.py \
  scripts/switch_runtime.py \
  framework/docs/browser-cockpit.md \
  framework/docs/switch-spec.md \
  framework/contracts/market.md \
  tests
```

Expected: the new declarative tool scope contract appears only in the market runtime path and related tests/docs, without launcher changes or generalized permission-engine wording.

## Acceptance Criteria

- All six market skill packages declare the same declarative `tool_scope_profile`.
- Runtime metadata normalizes that profile into a machine-readable `tool_scope`.
- `selected_skill_packet` exposes `tool_scope` alongside `execution_constraints` and `execution_steps`.
- Active docs clearly say market runs are SKILL-driven plus packet-scoped, not hardcoded by runtime branching.
- The batch does not touch `buddyswitch-codex`, does not add a generalized permission engine, and does not introduce persist-time compliance auditing.
