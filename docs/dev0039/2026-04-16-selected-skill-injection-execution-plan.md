# Selected Skill Injection And Execution Strengthening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace BuddySwitch's weak "host reads `SKILL.md` and improvises" step with an explicit selected-skill injection packet and stronger execution constraints, without turning BuddySwitch into a tool-executing workflow engine.

**Architecture:** Keep BuddySwitch's main chain unchanged: `switch -> parse -> resolve -> host choose skill -> persist`. Add one explicit runtime step between skill selection and execution: `prepare-execution`. That step materializes a small `selected_skill_packet` that mirrors Codex's explicit skill injection pattern: full `skill_instructions`, selected inputs, output schema, and machine-readable execution constraints. The host remains the only executor. Execution strengthening happens by making the injected packet clearer, more ordered, and fail-closed at the result-contract level; BuddySwitch never opens browsers or calls tools on the host's behalf.

**Tech Stack:** Python runtime (`scripts/switch_runtime.py`), BuddySwitch skill packages (`buddyswitch/skills/**`), top-level host instruction surfaces (`AGENTS.md`, `.codex/agents/router.toml`, `README.md`, `framework/docs/switch-spec.md`), `unittest`, existing market schemas, Codex reference implementation reviewed from the main-branch source tree at `/Users/chen/Dev/buddyswitch/tmp/codex`.

---

## Technical Review Summary

- Codex explicit skill execution is not a separate tool orchestrator. The important part is explicit `SkillInstructions` injection after selection. This was re-checked against the main-branch source tree at `/Users/chen/Dev/buddyswitch/tmp/codex`, specifically `codex-rs/core-skills/src/injection.rs`, `codex-rs/instructions/src/user_instructions.rs`, and `codex-rs/core/src/codex.rs`.
- Codex also renders an available-skills section for implicit use, but that is ancillary to explicit selected-skill execution. This was re-checked against `/Users/chen/Dev/buddyswitch/tmp/codex/codex-rs/core/src/codex.rs` and `/Users/chen/Dev/buddyswitch/tmp/codex/codex-rs/core-skills/src/render.rs`.
- Therefore BuddySwitch does not need to copy Codex's native discovery or reload machinery to strengthen `#5`.
- The correct BuddySwitch upgrade is narrower: standardize how the selected skill is injected into the host, and standardize how execution constraints are expressed so the host is less likely to drift.
- Constitution review tightens the implementation boundary further: do not add reference or script manifests in this first pass. They are not required to solve the current bottleneck and would be speculative abstraction before a second validated use case.
- Do **not** add BuddySwitch-side browser/tool orchestration in this iteration. That would make BuddySwitch a workflow engine and violate the desired control-layer boundary.

## Scope And Non-Goals

This plan only covers:

- explicit selected-skill injection
- stronger execution constraints for the injected skill
- host-facing documentation updates so the new step is actually used
- `market` skill tightening where browser-first behavior must be clearer

This plan does **not** cover:

- Codex native skill discovery integration
- repo/session skill projection tricks
- BuddySwitch calling Playwright or other tools directly
- new persistence objects or a second source of truth
- semantic business-quality review beyond schema validation

## File Map

- `scripts/switch_runtime.py`
  - Add a `prepare-execution` command and the helper that materializes a minimal `selected_skill_packet`.
  - Update `run_instructions_by_skill` so the host is told to call `prepare-execution`, not manually reconstruct the skill.
- `tests/test_switch_runtime.py`
  - Add direct tests for `prepare_execution_payload(...)`.
  - Add CLI-facing tests for the `prepare-execution` command.
- `AGENTS.md`
  - Replace the weak "read SKILL.md" wording with the explicit `prepare-execution -> inject packet -> execute` flow.
- `README.md`
  - Update runtime notes to describe `selected_skill_packet` and the no-tool-orchestration boundary.
- `.codex/agents/router.toml`
  - Update host instructions so router sessions use `prepare-execution` after choosing `skill_id`.
- `framework/docs/switch-spec.md`
  - Make `prepare-execution` a first-class runtime step between `resolve` and `persist`.
- `framework/docs/market-research-cockpit.md`
  - Rewrite the execution story to use selected-skill injection instead of host-execution bridge language.
- `buddyswitch/skills/market/research-scan/SKILL.md`
- `buddyswitch/skills/market/pmf-recon/SKILL.md`
- `buddyswitch/skills/market/customer-discovery/SKILL.md`
- `buddyswitch/skills/market/positioning-copy/SKILL.md`
- `buddyswitch/skills/market/channel-discovery/SKILL.md`
- `buddyswitch/skills/market/launch-prep/SKILL.md`
  - Add an explicit `Execution Order` section at the top so the injected skill body itself is clearer and more imperative.
- `tests/test_repo_consistency.py`
  - Enforce the new injection flow wording and market execution-order wording.

## Data Shape To Introduce

`prepare-execution` should return this canonical shape:

```json
{
  "ok": true,
  "selected_skill_packet": {
    "skill_id": "research-scan",
    "buddy": "market",
    "instruction_path": "buddyswitch/skills/market/research-scan/SKILL.md",
    "skill_instructions": {
      "name": "research-scan",
      "path": "buddyswitch/skills/market/research-scan/SKILL.md",
      "contents": "full SKILL.md text"
    },
    "selected_inputs": [],
    "output_schema_path": "framework/schemas/market/research-scan.json",
    "execution_constraints": {
      "execution_mode": "market-browser-native",
      "browser_mode": "headed-only",
      "browser_profile": "shared-market",
      "login_policy": "mandatory-takeover",
      "fallback_policy": "no-silent-degrade",
      "session_continuity": "shared-cockpit",
      "evidence_capture_level": "medium"
    },
    "execution_steps": [
      "Read selected inputs by slot before other work.",
      "Open a visible browser before any market research.",
      "Pause for takeover if a critical source requires login.",
      "Do not continue with snippet-only or text-only research."
    ]
  },
  "host_next_actions": [
    "Inject selected_skill_packet.skill_instructions verbatim into the current host turn.",
    "Treat selected_skill_packet.execution_steps as ordered requirements.",
    "Do not reconstruct the skill manually from disk after packet generation."
  ]
}
```

Notes:

- `skill_instructions` intentionally mirrors Codex's own explicit skill injection structure.
- `execution_constraints` stay descriptive and machine-readable.
- `execution_steps` are ordered human-readable constraints for the host/model.
- The packet is still BuddySwitch-owned runtime data, not persisted canonical state.
- `reference_manifest`, `scripts_manifest`, and similar package indexes are intentionally deferred until they become necessary in a second real implementation loop.

### Task 1: Add `prepare-execution` And `selected_skill_packet`

**Files:**
- Modify: `scripts/switch_runtime.py`
- Test: `tests/test_switch_runtime.py`

- [ ] **Step 1: Write the failing test for selected-skill packet generation**

```python
# tests/test_switch_runtime.py
class ExecutionPreparationTests(unittest.TestCase):
    def test_prepare_execution_returns_selected_skill_packet(self) -> None:
        resolved = switch_runtime.resolve_switch(
            "switch market: Validate whether indie developers need a lightweight demand-validation workflow before building"
        )

        prepared = switch_runtime.prepare_execution_payload(
            resolved,
            skill_id="research-scan",
        )

        self.assertTrue(prepared["ok"])
        packet = prepared["selected_skill_packet"]
        self.assertEqual(packet["skill_id"], "research-scan")
        self.assertEqual(packet["buddy"], "market")
        self.assertEqual(packet["skill_instructions"]["name"], "research-scan")
        self.assertTrue(packet["skill_instructions"]["contents"].startswith("# "))
        self.assertEqual(
            packet["execution_constraints"]["browser_mode"],
            "headed-only",
        )
        self.assertIn(
            "Open a visible browser before any market research.",
            packet["execution_steps"],
        )
        self.assertIn(
            "Inject selected_skill_packet.skill_instructions verbatim into the current host turn.",
            prepared["host_next_actions"],
        )
```

- [ ] **Step 2: Run the targeted test to verify it fails**

Run:

```bash
python3 -m unittest tests.test_switch_runtime.ExecutionPreparationTests.test_prepare_execution_returns_selected_skill_packet -v
```

Expected:

```text
ERROR or FAIL because prepare_execution_payload does not exist yet
```

- [ ] **Step 3: Implement packet materialization and the new CLI command**

```python
# scripts/switch_runtime.py
def _load_skill_instruction_text(instruction_path: str) -> str:
    return (ROOT / instruction_path).read_text(encoding="utf-8")

def _build_execution_steps(
    *,
    host_execution: dict[str, Any],
    selected_inputs: list[dict[str, Any]],
) -> list[str]:
    steps: list[str] = []
    if host_execution.get("execution_mode") == "market-browser-native":
        steps.append("Open a visible browser before any market research.")
        if selected_inputs:
            steps.append("Read selected inputs by slot before other work.")
        steps.extend(
            [
                "Pause for takeover if a critical source requires login.",
                "Do not continue with snippet-only or text-only research.",
                "Only after the steps above should you synthesize findings into the structured result.",
            ]
        )
        return steps
    if selected_inputs:
        steps.append("Read selected inputs by slot before other work.")
    return steps

def prepare_execution_payload(
    resolved: dict[str, Any],
    *,
    skill_id: str,
    manifest_path: Path = DEFAULT_MANIFEST,
) -> dict[str, Any]:
    switch_payload = resolved.get("switch") or {}
    buddy_id = switch_payload.get("buddy")
    if not isinstance(buddy_id, str) or not buddy_id:
        raise ValueError("resolved.switch.buddy is required")

    _resolve_persist_skill(
        resolved=resolved,
        requested_skill_id=skill_id,
    )
    selected_skill = _resolve_execution_skill(
        buddy_id=buddy_id,
        skill_id=skill_id,
        manifest_path=manifest_path,
    )
    instruction_path = _normalize_instruction_path(
        selected_skill["runtime"].get("instruction_path", selected_skill["path"])
    )
    output_schema_path = selected_skill["runtime"].get("output_schema")
    if not isinstance(output_schema_path, str) or not output_schema_path.strip():
        raise ValueError(f"Skill '{skill_id}' must define output_schema in the manifest")

    host_execution = dict(selected_skill["runtime"].get("host_execution", {}))
    selected_inputs = _rebuild_selected_inputs_for_execution(
        resolved=resolved,
        selected_skill=selected_skill,
    )
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
        "execution_steps": _build_execution_steps(
            host_execution=host_execution,
            selected_inputs=selected_inputs,
        ),
    }
    return {
        "ok": True,
        "selected_skill_packet": packet,
        "host_next_actions": [
            "Inject selected_skill_packet.skill_instructions verbatim into the current host turn.",
            "Treat selected_skill_packet.execution_steps as ordered requirements.",
            "Do not reconstruct the skill manually from disk after packet generation.",
        ],
    }

def _cmd_prepare_execution(args: argparse.Namespace) -> int:
    try:
        resolved = _read_json_input(args.resolved)
        payload = prepare_execution_payload(resolved, skill_id=args.skill_id)
    except (ManifestError, OutputSchemaError, ValueError, FileNotFoundError) as exc:
        json.dump(runtime_error("E_RUNTIME_PREPARE_EXECUTION", str(exc)), sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return 1
    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0
```

Also add the parser entry:

```python
prepare_cmd = subparsers.add_parser(
    "prepare-execution",
    help="Materialize an explicit selected-skill packet after resolve and skill selection.",
)
prepare_cmd.add_argument("--resolved", required=True, help="Resolved JSON payload file")
prepare_cmd.add_argument("--skill-id", required=True, help="Chosen skill id")
prepare_cmd.set_defaults(func=_cmd_prepare_execution)
```

- [ ] **Step 4: Run the targeted test to verify it passes**

Run:

```bash
python3 -m unittest tests.test_switch_runtime.ExecutionPreparationTests.test_prepare_execution_returns_selected_skill_packet -v
```

Expected:

```text
OK
```

- [ ] **Step 5: Commit**

```bash
git add scripts/switch_runtime.py tests/test_switch_runtime.py
git commit -m "feat: add selected skill packet preparation"
```

### Task 2: Route The Host Through Explicit Injection Instead Of Manual Skill Reconstruction

**Files:**
- Modify: `scripts/switch_runtime.py`
- Modify: `AGENTS.md`
- Modify: `README.md`
- Modify: `.codex/agents/router.toml`
- Modify: `framework/docs/switch-spec.md`
- Test: `tests/test_switch_runtime.py`
- Test: `tests/test_repo_consistency.py`

- [ ] **Step 1: Write the failing tests for the new host flow wording**

```python
# tests/test_switch_runtime.py
def test_market_run_instructions_require_prepare_execution(self) -> None:
    resolved = switch_runtime.resolve_switch(
        "switch market: research whether solo founders need faster validation loops"
    )
    instructions = resolved["run_instructions_by_skill"]["research-scan"]
    self.assertIn(
        "After choosing skill_id, call prepare-execution to materialize selected_skill_packet.",
        instructions["next_actions"],
    )
    self.assertIn(
        "Inject selected_skill_packet.skill_instructions verbatim into the current host turn.",
        instructions["next_actions"],
    )
```

```python
# tests/test_repo_consistency.py
def test_top_level_docs_define_selected_skill_packet_flow(self) -> None:
    combined = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (
            ROOT / "AGENTS.md",
            ROOT / "README.md",
            ROOT / ".codex" / "agents" / "router.toml",
            ROOT / "framework" / "docs" / "switch-spec.md",
        )
    ).lower()

    self.assertIn("prepare-execution", combined)
    self.assertIn("selected_skill_packet", combined)
    self.assertIn("inject selected_skill_packet.skill_instructions verbatim", combined)
    self.assertIn("buddyswitch does not execute host tools", combined)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
python3 -m unittest tests.test_switch_runtime.ExecutionPreparationTests.test_market_run_instructions_require_prepare_execution -v
python3 -m unittest tests.test_repo_consistency.RepoConsistencyTests.test_top_level_docs_define_selected_skill_packet_flow -v
```

Expected:

```text
FAIL because current wording still says "Read the selected ... SKILL.md"
```

- [ ] **Step 3: Patch runtime wording and host docs**

```python
# scripts/switch_runtime.py
next_actions.extend(
    [
        "After choosing skill_id, call prepare-execution to materialize selected_skill_packet.",
        "Inject selected_skill_packet.skill_instructions verbatim into the current host turn.",
        "Treat selected_skill_packet.execution_steps as ordered requirements for this run.",
    ]
)
```

```markdown
# AGENTS.md
7. Let the host Codex session choose one `skill_id` from `eligible_skills`.
8. Immediately call `scripts/switch_runtime.py prepare-execution --resolved <file> --skill-id <skill_id>`.
9. Inject `selected_skill_packet.skill_instructions` verbatim into the host turn, then execute the run in-session.
10. BuddySwitch does not execute host tools; it supplies the selected skill packet and persists the result.
```

```markdown
# README.md
- `resolve` identifies candidates and context.
- `prepare-execution` materializes the selected skill as `selected_skill_packet`.
- The host injects `selected_skill_packet.skill_instructions` verbatim and remains the only tool executor.
- BuddySwitch does not open browsers, run shell commands, or call MCP tools on the host's behalf.
```

```toml
# .codex/agents/router.toml
Execution flow:
1. resolve
2. choose exactly one `skill_id`
3. call `prepare-execution`
4. inject `selected_skill_packet.skill_instructions` verbatim
5. execute the run in the current host session

Boundary:
- BuddySwitch supplies the selected-skill packet.
- The host remains the only executor of browser, shell, and MCP tool actions.
```

```markdown
# framework/docs/switch-spec.md
`prepare-execution` is the canonical step between `resolve` and `persist`.
It converts the chosen skill into `selected_skill_packet`, including explicit `skill_instructions`, execution constraints, ordered execution steps, and selected inputs.
The host must execute the packet; BuddySwitch must not execute host tools itself.
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:

```bash
python3 -m unittest tests.test_switch_runtime.ExecutionPreparationTests.test_market_run_instructions_require_prepare_execution -v
python3 -m unittest tests.test_repo_consistency.RepoConsistencyTests.test_top_level_docs_define_selected_skill_packet_flow -v
```

Expected:

```text
OK
```

- [ ] **Step 5: Commit**

```bash
git add scripts/switch_runtime.py AGENTS.md README.md .codex/agents/router.toml framework/docs/switch-spec.md tests/test_switch_runtime.py tests/test_repo_consistency.py
git commit -m "feat: route host execution through selected skill packets"
```

### Task 3: Strengthen Market Execution Through Clearer Injected Skill Bodies

**Files:**
- Modify: `framework/docs/market-research-cockpit.md`
- Modify: `buddyswitch/skills/market/research-scan/SKILL.md`
- Modify: `buddyswitch/skills/market/pmf-recon/SKILL.md`
- Modify: `buddyswitch/skills/market/customer-discovery/SKILL.md`
- Modify: `buddyswitch/skills/market/positioning-copy/SKILL.md`
- Modify: `buddyswitch/skills/market/channel-discovery/SKILL.md`
- Modify: `buddyswitch/skills/market/launch-prep/SKILL.md`
- Test: `tests/test_repo_consistency.py`

- [ ] **Step 1: Write the failing repo-consistency test for `Execution Order`**

```python
# tests/test_repo_consistency.py
def test_market_skill_docs_start_with_execution_order(self) -> None:
    market_skill_docs = (
        ROOT / "buddyswitch" / "skills" / "market" / "research-scan" / "SKILL.md",
        ROOT / "buddyswitch" / "skills" / "market" / "pmf-recon" / "SKILL.md",
        ROOT / "buddyswitch" / "skills" / "market" / "customer-discovery" / "SKILL.md",
        ROOT / "buddyswitch" / "skills" / "market" / "positioning-copy" / "SKILL.md",
        ROOT / "buddyswitch" / "skills" / "market" / "channel-discovery" / "SKILL.md",
        ROOT / "buddyswitch" / "skills" / "market" / "launch-prep" / "SKILL.md",
    )
    for path in market_skill_docs:
        text = path.read_text(encoding="utf-8").lower()
        self.assertIn("## execution order", text)
        self.assertIn("before any market research", text)
        self.assertIn("do not continue with snippet-only or text-only research", text)
        self.assertIn("pause for mandatory takeover", text)
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
python3 -m unittest tests.test_repo_consistency.RepoConsistencyTests.test_market_skill_docs_start_with_execution_order -v
```

Expected:

```text
FAIL because the market skill docs still describe the cockpit conceptually instead of in ordered execution language
```

- [ ] **Step 3: Rewrite the market skill openings and cockpit doc**

Add an explicit first section like this to each market skill:

```markdown
## Execution Order

1. Before any market research, open a visible browser and work inside that browser-first environment.
2. Read all selected upstream inputs before forming new market claims.
3. If a critical source requires login, pause for mandatory takeover.
4. Do not continue with snippet-only or text-only research when the skill contract requires browser-native work.
5. Only after the steps above should you synthesize findings into the structured result.
```

Update `framework/docs/market-research-cockpit.md` so the execution story becomes:

```markdown
The cockpit no longer assumes BuddySwitch itself opens browser tools.
Instead, `prepare-execution` materializes a selected-skill packet whose injected instructions and execution constraints make browser-first behavior explicit to the host.
This keeps BuddySwitch as a control layer while still strengthening `market` execution.
```

- [ ] **Step 4: Run the test to verify it passes**

Run:

```bash
python3 -m unittest tests.test_repo_consistency.RepoConsistencyTests.test_market_skill_docs_start_with_execution_order -v
```

Expected:

```text
OK
```

- [ ] **Step 5: Commit**

```bash
git add framework/docs/market-research-cockpit.md buddyswitch/skills/market/research-scan/SKILL.md buddyswitch/skills/market/pmf-recon/SKILL.md buddyswitch/skills/market/customer-discovery/SKILL.md buddyswitch/skills/market/positioning-copy/SKILL.md buddyswitch/skills/market/channel-discovery/SKILL.md buddyswitch/skills/market/launch-prep/SKILL.md tests/test_repo_consistency.py
git commit -m "feat: strengthen market execution order in injected skills"
```

### Task 4: Verify The Live Contract Surface And Delete Superseded dev0039 Docs

**Files:**
- Modify: `framework/docs/market-research-cockpit.md`
- Modify: `docs/dev0039/2026-04-16-selected-skill-injection-execution-plan.md`
- Test: `tests/test_repo_consistency.py`
- Delete: `docs/dev0039/2026-04-16-market-cockpit-host-execution-bridge-plan.md`
- Delete: `docs/dev0039/2026-04-16-market-research-cockpit-design.md`
- Delete: `docs/dev0039/2026-04-16-market-research-cockpit-implementation-plan.md`

- [ ] **Step 1: Write the failing consistency checks for the final doc surface**

```python
# tests/test_repo_consistency.py
def test_market_cockpit_doc_defines_selected_skill_execution_boundary(self) -> None:
    cockpit_doc = (ROOT / "framework" / "docs" / "market-research-cockpit.md").read_text(
        encoding="utf-8"
    ).lower()
    self.assertIn("selected_skill_packet", cockpit_doc)
    self.assertIn("host stays the only executor", cockpit_doc)
    self.assertIn("these six skills stay separate", cockpit_doc)
    self.assertIn("not a second source of truth", cockpit_doc)


def test_dev0039_docs_keep_only_active_selected_skill_plans(self) -> None:
    docs_dir = ROOT / "docs" / "dev0039"
    names = {path.name for path in docs_dir.glob("*.md")}

    self.assertIn("2026-04-16-selected-skill-injection-execution-plan.md", names)
    self.assertNotIn("2026-04-16-market-research-cockpit-design.md", names)
    self.assertNotIn("2026-04-16-market-cockpit-host-execution-bridge-plan.md", names)
    self.assertNotIn("2026-04-16-market-research-cockpit-implementation-plan.md", names)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
python3 -m unittest tests.test_repo_consistency.RepoConsistencyTests.test_market_cockpit_doc_defines_selected_skill_execution_boundary -v
python3 -m unittest tests.test_repo_consistency.RepoConsistencyTests.test_dev0039_docs_keep_only_active_selected_skill_plans -v
```

Expected:

```text
FAIL because the live cockpit contract is not explicit enough yet and the old dev0039 docs still exist
```

- [ ] **Step 3: Consolidate the live contract and delete superseded docs**

Patch `framework/docs/market-research-cockpit.md` so it says:

```markdown
The host chooses exactly one `market` `skill_id` for the run.
The host calls `prepare-execution` to materialize `selected_skill_packet`.
The host injects that packet and follows `execution_steps` in order.
This contract applies to one selected skill at a time.
```

Then delete the superseded dev0039 bridge/design/implementation docs instead of retaining them as references.

- [ ] **Step 4: Run the final focused regression set**

Run:

```bash
python3 -m unittest tests.test_switch_runtime.ExecutionPreparationTests -v
python3 -m unittest tests.test_repo_consistency.RepoConsistencyTests.test_top_level_docs_define_selected_skill_packet_flow -v
python3 -m unittest tests.test_repo_consistency.RepoConsistencyTests.test_market_cockpit_doc_defines_selected_skill_execution_boundary -v
python3 -m unittest tests.test_repo_consistency.RepoConsistencyTests.test_dev0039_docs_keep_only_active_selected_skill_plans -v
python3 -m unittest tests.test_repo_consistency.RepoConsistencyTests.test_dev0039_active_plans_define_selected_skill_packet_flow -v
```

Expected:

```text
OK
```

- [ ] **Step 5: Commit**

```bash
git add framework/docs/market-research-cockpit.md docs/dev0039/2026-04-16-selected-skill-injection-execution-plan.md tests/test_repo_consistency.py
git rm docs/dev0039/2026-04-16-market-cockpit-host-execution-bridge-plan.md docs/dev0039/2026-04-16-market-research-cockpit-design.md docs/dev0039/2026-04-16-market-research-cockpit-implementation-plan.md
git commit -m "docs: collapse dev0039 to the selected skill injection contract"
```

## Spec Coverage Check

- `#5` injection is covered by Task 1 and Task 2.
- Execution strengthening without BuddySwitch tool orchestration is covered by Task 2 and Task 3.
- `market` browser-native clarity is covered by Task 3.
- Removal of the older host-bridge framing is covered by Task 4.
- No task introduces BuddySwitch-side Playwright execution or native-skill discovery coupling.
- The packet shape stays minimal and avoids speculative manifests, matching the constitution's "solve the current bottleneck first" rule.

## Placeholder Scan

- No `TODO` or `TBD` placeholders remain.
- Each task specifies files, tests, commands, and expected outcomes.
- All new function and command names are declared before later tasks refer to them.

## Type And Naming Consistency

- Runtime command: `prepare-execution`
- Helper: `prepare_execution_payload(...)`
- Packet object: `selected_skill_packet`
- Explicit injection payload: `skill_instructions`
- Constraint object: `execution_constraints`
- Ordered human-facing contract: `execution_steps`

These names should remain stable across runtime, docs, and tests.
