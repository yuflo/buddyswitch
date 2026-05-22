# PM Skill Rebuild Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:test-driven-development` before
> implementation, and use `superpowers:writing-skills` when writing or revising PM `SKILL.md`
> packages. Do not execute this plan until the user explicitly approves it.

**Goal:** Replace the PM buddy's single `write-prd` skill with a generic product-management skill
set that supports context intake, synthesis, direction, scope, requirements, acceptance criteria,
decisions, proof iteration, track triage, and sequencing.

**Architecture:** This is a skill-layer rebuild. The implementation edits PM skill packages, manifest
registration, PM role guidance, and tests. It does not change runtime tool implementations unless a
failing test proves a lower-layer contract defect.

**Tech Stack:** Markdown Agent Skills, BuddySwitch TOML manifest, Python `unittest`/`pytest`, launcher
runtime skill projection tests.

---

## Approval Gate

Stop after this plan and the test plan are updated. Do not write tests, edit skills, edit manifest,
delete `write-prd`, or run implementation-phase changes until the user explicitly approves.

## Scope And Constraints

- Work only in `/Users/chen/Dev/buddyswitch/.worktrees/clean-runtime-env`.
- Do not modify the main worktree.
- Follow SHARP: solve the current bottleneck, replace directly, verify, and avoid speculative
  abstraction.
- Remove `write-prd` directly; do not leave a compatibility alias, wrapper, dual registration, or
  migrated copy.
- Do not add page-type PM skills, including landing page, pricing page, launch page, marketing
  surface, or Wukong-specific skills.
- Do not solve sub-agent loop stability, supervisor restarts, scheduling, or long-running
  coordination in this task.
- Do not change runtime tools unless tests prove a real lower-layer contract defect.
- Do not copy payload/action/return schema tables into PM skills.
- Do not turn PM AGENTS or PM contract into a long SOP.
- Use skill descriptions as trigger metadata, not workflow summaries.

## Files

Create:

- `buddyswitch/skills/pm/read-product-context/SKILL.md`
- `buddyswitch/skills/pm/synthesize-cross-functional-inputs/SKILL.md`
- `buddyswitch/skills/pm/frame-product-direction/SKILL.md`
- `buddyswitch/skills/pm/define-scope/SKILL.md`
- `buddyswitch/skills/pm/write-requirements/SKILL.md`
- `buddyswitch/skills/pm/write-acceptance-criteria/SKILL.md`
- `buddyswitch/skills/pm/make-product-decision/SKILL.md`
- `buddyswitch/skills/pm/decide-from-proof/SKILL.md`
- `buddyswitch/skills/pm/triage-track/SKILL.md`
- `buddyswitch/skills/pm/sequence-product-work/SKILL.md`

Modify:

- `buddyswitch/manifest.toml`
- `framework/contracts/pm.md`
- `tests/test_runtime_skills.py`
- `tests/test_buddyswitch_launcher.py`

Delete:

- `buddyswitch/skills/pm/write-prd/SKILL.md`
- `buddyswitch/skills/pm/write-prd/assets/prd-template.md`
- `buddyswitch/skills/pm/write-prd/`

Do not modify:

- `buddyswitch/objects/**`
- `buddyswitch/local/buddybox/**`
- runtime tool implementation files under `scripts/env/tools/**`
- sub-agent loop or supervisor code

## Implementation Order

1. Write focused failing tests for PM skill surface, package quality, docs/bitter boundaries, and
   launcher projection.
2. Run focused tests and confirm RED for the expected missing skills/stale `write-prd` assertions.
3. Replace manifest PM registrations.
4. Create the new PM skill packages.
5. Delete the old `write-prd` package.
6. Update PM contract and PM AGENTS only where they reference old behavior or omit generic PM
   responsibility boundaries.
7. Run focused verification, pressure scenario validation, and full regression.

## Target PM Skill Set

The PM buddy should register exactly these product-work skills in addition to shared runtime tool
skills:

```python
PM_PRODUCT_SKILLS = (
    "read-product-context",
    "synthesize-cross-functional-inputs",
    "frame-product-direction",
    "define-scope",
    "write-requirements",
    "write-acceptance-criteria",
    "make-product-decision",
    "decide-from-proof",
    "triage-track",
    "sequence-product-work",
)
```

Shared runtime tool skills remain:

```python
SHARED_RUNTIME_TOOL_SKILLS = {
    "track-tool",
    "artifact-tool",
    "task-tool",
    "buddybox-tool",
    "message-tool",
    "comment-tool",
    "request-tool",
}
```

## Skill Authoring Standard

Every PM `SKILL.md` must follow this structure:

```markdown
---
name: <skill-id>
description: Use when <triggering condition only, no workflow summary>.
---

# <Readable Skill Name>

## Purpose
- <one or two product-work outcomes>

## Use when
- <task symptoms that should trigger this skill>

## Do not use when
- <nearby work owned by another skill or another buddy>

## Inputs
- <product/runtime artifacts to inspect>
- Runtime contract references: `context.get.tool_catalog`, `python3 scripts/turn_runtime.py status`,
  and runtime response fields.

## Steps
1. <PM judgment step, not a tool schema>
2. <PM judgment step>
3. <PM output/publication step at business level>

## Outputs
- <durable or working output shape>

## Quality Bar
- <what makes this PM work usable by the next owner>

## Runtime Boundary
- Use env tools for durable state.
- Read exact payload and response fields from runtime discovery, not this skill.
- Do not edit projected runtime storage directly.

## Examples
- <one concrete but generic product-work example>

## Counterexamples
- <one failure mode this skill should prevent>
```

Descriptions must be concise and trigger-only. The body may mention high-level runtime actions such
as `track.open`, `artifact.get`, `artifact.create_revision`, `track.add_material`, and
`track.add_proof`, but must not reproduce payload schemas or action catalogs.

## Skill Content Blueprints

### `read-product-context`

Frontmatter:

```markdown
---
name: read-product-context
description: Use when PM work depends on track, task, artifact, request, message, comment, or proof context that must be read before deciding.
---
```

Required body content:
- Purpose: turn durable collaboration state into a PM-readable context summary.
- Inputs: user request, track id, task id, artifact ids, request/comment/message ids, proof ids,
  full artifact bodies when ids are available.
- Steps: collect explicit ids, open track, read artifact bodies, separate facts/assumptions/decisions/
  blockers/missing inputs, state next PM-owned move.
- Outputs: context summary with facts, assumptions, decisions, blockers, missing inputs, and next
  action.
- Quality bar: no claim that artifact content was read unless `artifact.get` returned the full body.
- Counterexample: deciding from chat summary while an artifact id is present.

### `synthesize-cross-functional-inputs`

Frontmatter:

```markdown
---
name: synthesize-cross-functional-inputs
description: Use when PM must combine market, design, dev, test, or stakeholder signals into product implications.
---
```

Required body content:
- Purpose: map signals to decision, scope, requirements, acceptance criteria, owner questions, or
  risk.
- Inputs: market evidence, design artifacts, dev reports, test proof, stakeholder constraints.
- Steps: classify each signal by owner/source, assess evidence strength, map to product impact,
  resolve contradictions or name the blocker, identify next owner.
- Outputs: synthesis table or brief summary with signal, implication, PM action, owner, and open
  question.
- Quality bar: conflicting inputs are not flattened into generic consensus.
- Counterexample: forwarding all inputs downstream without deciding what they mean.

### `frame-product-direction`

Frontmatter:

```markdown
---
name: frame-product-direction
description: Use when PM must define audience, problem, value, evidence, constraints, and non-goals for a product bet.
---
```

Required body content:
- Purpose: create a product direction that design/dev/test can use without re-deciding product
  intent.
- Inputs: user goal, market evidence, current product constraints, previous decisions, risks.
- Steps: state target user/context, problem, value, evidence strength, constraints, non-goals, and
  open product questions.
- Outputs: product direction brief or section.
- Quality bar: unsupported claims are labeled as assumptions.
- Counterexample: writing positioning copy or page modules before product direction is clear.

### `define-scope`

Frontmatter:

```markdown
---
name: define-scope
description: Use when PM must cut product work to the smallest valuable iteration with explicit non-goals.
---
```

Required body content:
- Purpose: make the scope small enough to design, build, and test in the current appetite.
- Inputs: product direction, constraints, risks, design/dev/test signals, appetite.
- Steps: choose smallest valuable outcome, list in-scope behavior, list non-goals, record cut-line
  rationale, name downstream impact.
- Outputs: scope section with in, out, rationale, owner impact, and unresolved scope questions.
- Quality bar: scope cuts preserve user value and reduce verification ambiguity.
- Counterexample: expanding scope to satisfy every stakeholder note.

### `write-requirements`

Frontmatter:

```markdown
---
name: write-requirements
description: Use when PM must turn product goals and scope into observable requirements for design, dev, or test.
---
```

Required body content:
- Purpose: express product behavior without owning UI craft or implementation details.
- Inputs: product direction, scope, decisions, design constraints, technical constraints, user flows.
- Steps: convert goals to observable behavior, split requirement from acceptance criterion, mark
  owner boundaries, record assumptions.
- Outputs: numbered requirements with actor, trigger, behavior, constraint, and rationale.
- Quality bar: test can understand what behavior exists without PM interpretation.
- Counterexample: "make it better" or "use React component X" as a PM requirement.

### `write-acceptance-criteria`

Frontmatter:

```markdown
---
name: write-acceptance-criteria
description: Use when PM must define verifiable pass/fail criteria for scoped product behavior.
---
```

Required body content:
- Purpose: give test and dev observable proof targets.
- Inputs: requirements, scope, known risks, affected flows, proof expectations.
- Steps: map each critical behavior to pass/fail checks, include negative/edge states where relevant,
  name unverified areas separately, avoid subjective visual-only criteria.
- Outputs: acceptance criteria grouped by behavior or flow.
- Quality bar: a tester can produce pass/fail/blocked proof from the criteria.
- Counterexample: "looks premium" as an acceptance criterion without observable evidence.

### `make-product-decision`

Frontmatter:

```markdown
---
name: make-product-decision
description: Use when PM must record a durable product decision, tradeoff, rejected alternative, or next owner action.
---
```

Required body content:
- Purpose: make decisions inspectable and durable.
- Inputs: competing options, evidence, constraints, owner feedback, track state.
- Steps: state decision, evidence, tradeoff, rejected alternatives, residual risk, next owner/action,
  and publication target.
- Outputs: decision artifact or decision section.
- Quality bar: downstream buddies know what changed and what not to relitigate.
- Counterexample: burying a decision in chat or a vague track update.

### `decide-from-proof`

Frontmatter:

```markdown
---
name: decide-from-proof
description: Use when PM must decide continue, revise, send back, stop, or blocked after test proof or validation evidence.
---
```

Required body content:
- Purpose: close the post-proof loop.
- Inputs: test proof, validation evidence, acceptance criteria, dev report, current track state.
- Steps: read proof body, map result to acceptance criteria, choose continue/revise/send back/stop/
  blocked, record evidence and residual risk, create/update owner follow-up if needed.
- Outputs: iteration decision, track update, proof publication, or owner-specific task/request.
- Quality bar: decision follows evidence rather than optimism or process momentum.
- Counterexample: treating a partial pass with unverified mobile behavior as full readiness.

### `triage-track`

Frontmatter:

```markdown
---
name: triage-track
description: Use when a PM-owned track is stale, cluttered, blocked, missing proof, or unclear about the latest product truth.
---
```

Required body content:
- Purpose: recover track clarity without rewriting product artifacts unnecessarily.
- Inputs: track state, shared materials, close proof, updates, tasks, requests, comments.
- Steps: identify current truth, obsolete or superseded material, missing proof, blockers, next PM
  action, and owner requests.
- Outputs: triage note, track `now` update, or task/request changes.
- Quality bar: track becomes easier to act on with the fewest durable mutations.
- Counterexample: creating a new PRD to hide stale state.

### `sequence-product-work`

Frontmatter:

```markdown
---
name: sequence-product-work
description: Use when PM must order product, market, design, dev, and test work for a scoped track.
---
```

Required body content:
- Purpose: turn a product direction into an ordered collaboration path.
- Inputs: scope, requirements, known dependencies, owner constraints, risks, proof needs.
- Steps: identify blocking dependency, order owners, define expected output per owner, set stop
  conditions, avoid creating a generic process system.
- Outputs: short sequence with owner, output, dependency, stop condition, and current next action.
- Quality bar: every next owner can start without re-deciding PM scope.
- Counterexample: broad project plan detached from current track outcome.

## Task 1: Add Failing PM Skill Contract Tests

**Files:**
- Modify: `tests/test_runtime_skills.py`

- [ ] **Step 1: Add PM skill constants**

Add near `DEV_PRODUCT_SKILLS`:

```python
    PM_PRODUCT_SKILLS = (
        "read-product-context",
        "synthesize-cross-functional-inputs",
        "frame-product-direction",
        "define-scope",
        "write-requirements",
        "write-acceptance-criteria",
        "make-product-decision",
        "decide-from-proof",
        "triage-track",
        "sequence-product-work",
    )
    SHARED_RUNTIME_TOOL_SKILLS = {
        "track-tool",
        "artifact-tool",
        "task-tool",
        "buddybox-tool",
        "message-tool",
        "comment-tool",
        "request-tool",
    }
    PM_SCENARIO_TERMS = (
        "wukong",
        "landing page",
        "pricing page",
        "launch page",
        "marketing surface",
        "marketing-surface",
    )
```

- [ ] **Step 2: Add PM helpers**

Add near `_dev_skill_file`:

```python
    def _pm_skill_file(self, skill_id: str) -> Path:
        return ROOT / "buddyswitch" / "skills" / "pm" / skill_id / "SKILL.md"

    def _pm_buddy(self) -> dict:
        return next(
            row
            for row in self.manifest.get("buddies", [])
            if isinstance(row, dict) and row.get("id") == "pm"
        )
```

- [ ] **Step 3: Replace role skill handoff test reference**

In `test_role_skills_remove_optional_handoff_guidance`, replace the hardcoded
`buddyswitch/skills/pm/write-prd/SKILL.md` entry with all PM product skills:

```python
            *(self._pm_skill_file(skill_id) for skill_id in self.PM_PRODUCT_SKILLS),
```

- [ ] **Step 4: Add manifest skill set test**

Add this test:

```python
    def test_pm_product_skill_chain_is_registered(self) -> None:
        skills_by_id = {row["id"]: row for row in self.manifest.get("skills", []) if isinstance(row, dict)}
        pm_skills = set(self._pm_buddy().get("skills", []))
        expected_product = set(self.PM_PRODUCT_SKILLS)

        self.assertTrue(expected_product.issubset(pm_skills))
        self.assertTrue(self.SHARED_RUNTIME_TOOL_SKILLS.issubset(pm_skills))
        self.assertNotIn("write-prd", pm_skills)

        for skill_id in expected_product:
            self.assertIn(skill_id, skills_by_id, msg=skill_id)
            self.assertTrue((ROOT / skills_by_id[skill_id]["path"] / "SKILL.md").exists(), msg=skill_id)

        for skill_id in pm_skills:
            lowered = skill_id.lower()
            for term in self.PM_SCENARIO_TERMS:
                self.assertNotIn(term, lowered, msg=skill_id)
```

- [ ] **Step 5: Add old package removal test**

Add this test:

```python
    def test_pm_write_prd_skill_package_is_removed(self) -> None:
        self.assertFalse((ROOT / "buddyswitch/skills/pm/write-prd/SKILL.md").exists())
        self.assertFalse((ROOT / "buddyswitch/skills/pm/write-prd/assets/prd-template.md").exists())
        skill_ids = [row.get("id") for row in self.manifest.get("skills", []) if isinstance(row, dict)]
        self.assertNotIn("write-prd", skill_ids)
```

- [ ] **Step 6: Add package validity and description tests**

Add this test:

```python
    def test_pm_skills_have_valid_frontmatter_and_trigger_descriptions(self) -> None:
        forbidden_description_tokens = (
            "1.",
            "2.",
            "python3 scripts/env/client.py",
            "track.open",
            "artifact.get",
            "artifact.create_revision",
            "track.add_material",
            "track.add_proof",
            "## ",
        )
        for skill_id in self.PM_PRODUCT_SKILLS:
            path = self._pm_skill_file(skill_id)
            text = path.read_text(encoding="utf-8")
            lines = text.splitlines()
            with self.subTest(skill=skill_id):
                self.assertEqual(lines[0], "---")
                self.assertIn(f"name: {skill_id}", lines[:6])
                description_lines = [line for line in lines[:8] if line.startswith("description: ")]
                self.assertEqual(len(description_lines), 1)
                description = description_lines[0].split("description: ", 1)[1]
                self.assertTrue(description.startswith("Use when "), msg=description)
                self.assertLessEqual(len(description), 1024)
                for token in forbidden_description_tokens:
                    self.assertNotIn(token, description)
```

- [ ] **Step 7: Add PM skill body quality test**

Add this test:

```python
    def test_pm_skills_include_product_work_sections_and_quality_bars(self) -> None:
        required_headings = (
            "## purpose",
            "## use when",
            "## do not use when",
            "## inputs",
            "## steps",
            "## outputs",
            "## quality bar",
            "## runtime boundary",
            "## examples",
            "## counterexamples",
        )
        required_by_skill = {
            "read-product-context": ("facts", "assumptions", "decisions", "blockers", "missing inputs"),
            "synthesize-cross-functional-inputs": ("market", "design", "dev", "test", "product impact"),
            "frame-product-direction": ("audience", "problem", "value", "constraints", "non-goals"),
            "define-scope": ("smallest valuable", "in-scope", "non-goals", "cut", "downstream"),
            "write-requirements": ("observable", "actor", "trigger", "behavior", "owner boundary"),
            "write-acceptance-criteria": ("pass", "fail", "blocked", "criteria", "proof"),
            "make-product-decision": ("decision", "evidence", "tradeoff", "rejected", "next owner"),
            "decide-from-proof": ("continue", "revise", "send back", "stop", "blocked"),
            "triage-track": ("stale", "current truth", "obsolete", "missing proof", "next action"),
            "sequence-product-work": ("owner", "output", "dependency", "stop condition", "sequence"),
        }
        for skill_id in self.PM_PRODUCT_SKILLS:
            lowered = self._pm_skill_file(skill_id).read_text(encoding="utf-8").lower()
            with self.subTest(skill=skill_id):
                for heading in required_headings:
                    self.assertIn(heading, lowered)
                for token in required_by_skill[skill_id]:
                    self.assertIn(token, lowered)
```

- [ ] **Step 8: Add docs/bitter boundary test for PM skills**

Add this test:

```python
    def test_pm_skills_do_not_copy_runtime_schema_or_action_catalogs(self) -> None:
        forbidden = (
            "payload_fields",
            "operation_semantics",
            "**payload:**",
            "**returns:**",
            "## operations",
            "scripts/env/tools/",
            "action_semantics",
            "tool_spec",
            "published_to_track",
            "content.prd",
            "kind=prd",
        )
        required_refs = (
            "context.get.tool_catalog",
            "python3 scripts/turn_runtime.py status",
            "runtime response fields",
        )
        for skill_id in self.PM_PRODUCT_SKILLS:
            lowered = self._pm_skill_file(skill_id).read_text(encoding="utf-8").lower()
            with self.subTest(skill=skill_id):
                for token in forbidden:
                    self.assertNotIn(token, lowered)
                for token in required_refs:
                    self.assertIn(token, lowered)
```

- [ ] **Step 9: Add scenario drift test**

Add this test:

```python
    def test_pm_skills_are_not_page_or_case_specific(self) -> None:
        for skill_id in self.PM_PRODUCT_SKILLS:
            text = self._pm_skill_file(skill_id).read_text(encoding="utf-8").lower()
            with self.subTest(skill=skill_id):
                self.assertNotIn("wukong", text)
                self.assertNotIn("landing page", text)
                self.assertNotIn("landing-page", text)
                self.assertNotIn("pricing page", text)
                self.assertNotIn("pricing-page", text)
                self.assertNotIn("launch page", text)
                self.assertNotIn("launch-page", text)
                self.assertNotIn("marketing surface", text)
                self.assertNotIn("marketing-surface", text)
```

- [ ] **Step 10: Replace PM publication path test**

Replace `test_pm_and_shared_tool_skills_describe_single_publication_path` so it scans all PM product
skills instead of opening `write-prd`:

```python
    def test_pm_and_shared_tool_skills_describe_single_publication_path(self) -> None:
        pm_text = "\n".join(
            self._pm_skill_file(skill_id).read_text(encoding="utf-8").lower()
            for skill_id in self.PM_PRODUCT_SKILLS
        )
        artifact_skill = (ROOT / "buddyswitch/skills/shared/artifact-tool/SKILL.md").read_text(encoding="utf-8").lower()
        track_skill = (ROOT / "buddyswitch/skills/shared/track-tool/SKILL.md").read_text(encoding="utf-8").lower()

        self.assertIn("artifact.create_revision", pm_text)
        self.assertIn("track.add_material", pm_text)
        self.assertIn("track.add_proof", pm_text)
        self.assertIn("track.open", pm_text)
        self.assertIn("artifact.get", pm_text)
        self.assertNotIn("published_to_track", pm_text)
        self.assertNotIn("content.prd", pm_text)
        self.assertNotIn("kind=prd", pm_text)

        self.assertIn("create-revision", artifact_skill)
        self.assertIn("private draft", artifact_skill)
        self.assertIn("track.add-material", artifact_skill)
        self.assertIn("track.add-proof", artifact_skill)
        self.assertNotIn("published_to_track", artifact_skill)
        self.assertNotIn("content.prd", artifact_skill)
        self.assertNotIn("kind=prd", artifact_skill)

        self.assertIn("add-material", track_skill)
        self.assertIn("add-proof", track_skill)
        self.assertIn("artifact.get", track_skill)
        self.assertNotIn("content.prd", track_skill)
        self.assertNotIn("kind=prd", track_skill)
        self.assertNotIn("published_to_track", track_skill)
```

- [ ] **Step 11: Add PM guidance alignment test**

Add this test:

```python
    def test_pm_contract_and_agents_align_with_generic_skill_surface(self) -> None:
        contract = (ROOT / "framework/contracts/pm.md").read_text(encoding="utf-8").lower()
        agents = (ROOT / "tools/launcher/assets/buddies/pm/AGENTS.md").read_text(encoding="utf-8").lower()
        combined = contract + "\n" + agents

        self.assertNotIn("write-prd", combined)
        for token in (
            "context intake",
            "product direction",
            "scope",
            "requirements",
            "acceptance criteria",
            "decision",
            "proof",
            "track triage",
            "sequencing",
        ):
            self.assertIn(token, contract)
        self.assertLess(contract.count("python3 scripts/env/client.py"), 8)
```

- [ ] **Step 12: Run focused tests and confirm RED**

Run:

```bash
python3 -m pytest tests/test_runtime_skills.py -q
```

Expected:
- Fails because target PM skills are not registered and package files do not exist.
- Failure must be missing target skill/package assertions, not syntax errors.

## Task 2: Add Failing Launcher Projection Tests

**Files:**
- Modify: `tests/test_buddyswitch_launcher.py`

- [ ] **Step 1: Add PM product skill constant near test class constants**

Add:

```python
    _PM_PRODUCT_SKILLS = (
        "read-product-context",
        "synthesize-cross-functional-inputs",
        "frame-product-direction",
        "define-scope",
        "write-requirements",
        "write-acceptance-criteria",
        "make-product-decision",
        "decide-from-proof",
        "triage-track",
        "sequence-product-work",
    )
```

- [ ] **Step 2: Replace direct PM runtime assertions**

Replace every assertion that expects PM runtime `.agents/skills/write-prd/SKILL.md` with a loop over
`self._PM_PRODUCT_SKILLS`.

Use this pattern:

```python
            runtime_skills = workspace_dir / ".agents" / "skills"
            for skill_id in self._PM_PRODUCT_SKILLS:
                self.assertTrue((runtime_skills / skill_id / "SKILL.md").exists(), msg=skill_id)
            self.assertFalse((runtime_skills / "write-prd").exists())
            self.assertFalse((runtime_skills / "write-prd" / "assets" / "prd-template.md").exists())
```

Apply this to launcher tests currently found by:

```bash
rg -n 'write-prd|\\.agents/skills/write-prd|runtime_skills / "write-prd"' tests/test_buddyswitch_launcher.py
```

Known assertion clusters include PM instance start, PM sparse runtime copy, PM open/refresh, and
permission/runtime AGENTS copy tests.

- [ ] **Step 3: Preserve generic manifest projection test**

Keep `test_instance_start_materializes_runtime_skills_from_manifest_for_each_buddy` as the broad
truth source. It should pass once manifest is replaced because it compares runtime installed skills
to buddy manifest skills.

- [ ] **Step 4: Run focused launcher tests and confirm RED**

Run:

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py -q
```

Expected:
- Fails on missing new PM skills or stale `write-prd` expectations until manifest and packages are
  replaced.

## Task 3: Replace PM Manifest Registration

**Files:**
- Modify: `buddyswitch/manifest.toml`

- [ ] **Step 1: Remove old skill entry**

Delete:

```toml
[[skills]]
id = "write-prd"
path = "buddyswitch/skills/pm/write-prd"
```

- [ ] **Step 2: Add target PM skill entries**

Add one `[[skills]]` entry for each PM product-work skill:

```toml
[[skills]]
id = "read-product-context"
path = "buddyswitch/skills/pm/read-product-context"

[[skills]]
id = "synthesize-cross-functional-inputs"
path = "buddyswitch/skills/pm/synthesize-cross-functional-inputs"

[[skills]]
id = "frame-product-direction"
path = "buddyswitch/skills/pm/frame-product-direction"

[[skills]]
id = "define-scope"
path = "buddyswitch/skills/pm/define-scope"

[[skills]]
id = "write-requirements"
path = "buddyswitch/skills/pm/write-requirements"

[[skills]]
id = "write-acceptance-criteria"
path = "buddyswitch/skills/pm/write-acceptance-criteria"

[[skills]]
id = "make-product-decision"
path = "buddyswitch/skills/pm/make-product-decision"

[[skills]]
id = "decide-from-proof"
path = "buddyswitch/skills/pm/decide-from-proof"

[[skills]]
id = "triage-track"
path = "buddyswitch/skills/pm/triage-track"

[[skills]]
id = "sequence-product-work"
path = "buddyswitch/skills/pm/sequence-product-work"
```

- [ ] **Step 3: Replace PM buddy skill list**

Replace:

```toml
skills = ["write-prd", "track-tool", "artifact-tool", "task-tool", "buddybox-tool", "message-tool", "comment-tool", "request-tool"]
```

with:

```toml
skills = [
  "read-product-context",
  "synthesize-cross-functional-inputs",
  "frame-product-direction",
  "define-scope",
  "write-requirements",
  "write-acceptance-criteria",
  "make-product-decision",
  "decide-from-proof",
  "triage-track",
  "sequence-product-work",
  "track-tool",
  "artifact-tool",
  "task-tool",
  "buddybox-tool",
  "message-tool",
  "comment-tool",
  "request-tool",
]
```

- [ ] **Step 4: Run PM manifest test**

Run:

```bash
python3 -m pytest tests/test_runtime_skills.py::RuntimeSkillsTests::test_pm_product_skill_chain_is_registered -q
```

Expected:
- Still fails until skill package files exist.

## Task 4: Create Generic PM Skill Packages

**Files:**
- Create the ten target `SKILL.md` files under `buddyswitch/skills/pm/`.

- [ ] **Step 1: Create directories**

Create:

```text
buddyswitch/skills/pm/read-product-context/
buddyswitch/skills/pm/synthesize-cross-functional-inputs/
buddyswitch/skills/pm/frame-product-direction/
buddyswitch/skills/pm/define-scope/
buddyswitch/skills/pm/write-requirements/
buddyswitch/skills/pm/write-acceptance-criteria/
buddyswitch/skills/pm/make-product-decision/
buddyswitch/skills/pm/decide-from-proof/
buddyswitch/skills/pm/triage-track/
buddyswitch/skills/pm/sequence-product-work/
```

- [ ] **Step 2: Write `SKILL.md` files from the blueprints**

Use the exact frontmatter from "Skill Content Blueprints". Each body must contain the standard
sections from "Skill Authoring Standard".

- [ ] **Step 3: Keep references and assets absent**

Do not create `references/`, `assets/`, `scripts/`, or `agents/` directories in this rebuild unless
the implementation discovers a concrete need. The current target is concise `SKILL.md` packages.

- [ ] **Step 4: Run focused PM skill tests**

Run:

```bash
python3 -m pytest tests/test_runtime_skills.py::RuntimeSkillsTests::test_pm_skills_have_valid_frontmatter_and_trigger_descriptions -q
python3 -m pytest tests/test_runtime_skills.py::RuntimeSkillsTests::test_pm_skills_include_product_work_sections_and_quality_bars -q
python3 -m pytest tests/test_runtime_skills.py::RuntimeSkillsTests::test_pm_skills_do_not_copy_runtime_schema_or_action_catalogs -q
```

Expected:
- These tests pass after packages are written.

## Task 5: Delete The Old Single PM Skill

**Files:**
- Delete: `buddyswitch/skills/pm/write-prd/`

- [ ] **Step 1: Delete the old package directory**

Remove:

```text
buddyswitch/skills/pm/write-prd/
```

- [ ] **Step 2: Confirm no active source or test expectation remains**

Run:

```bash
rg -n 'write-prd' buddyswitch/manifest.toml buddyswitch/skills/pm framework/contracts/pm.md tools/launcher/assets/buddies/pm/AGENTS.md tests/test_runtime_skills.py tests/test_buddyswitch_launcher.py
```

Expected:
- No active-surface references.
- Allow only explicit negative test names/assertions that verify `write-prd` is absent.

- [ ] **Step 3: Run deletion test**

Run:

```bash
python3 -m pytest tests/test_runtime_skills.py::RuntimeSkillsTests::test_pm_write_prd_skill_package_is_removed -q
```

Expected:
- Pass.

## Task 6: Update PM Contract And AGENTS Without Prompt Bulk

**Files:**
- Modify: `framework/contracts/pm.md`
- Modify if needed: `tools/launcher/assets/buddies/pm/AGENTS.md`

- [ ] **Step 1: Update PM contract purpose and responsibilities**

Keep `framework/contracts/pm.md` short. It must include the generic responsibility terms used by
the test:

```markdown
## Product Responsibilities

- Own context intake before product mutations.
- Frame product direction from evidence, constraints, assumptions, and non-goals.
- Define scope, requirements, and acceptance criteria for downstream design/dev/test.
- Capture durable PM decisions with evidence, tradeoffs, rejected alternatives, residual risk, and next owner/action.
- Decide from proof whether to continue, revise, send back, stop, or mark blocked.
- Triage track state and sequence next product work without adding process layers.
```

Keep the existing runtime boundary and runtime discovery sections. Do not add tool payload tables.

- [ ] **Step 2: Update PM AGENTS only if necessary**

`tools/launcher/assets/buddies/pm/AGENTS.md` currently does not name `write-prd`. If no stale PM
skill guidance exists, leave it mostly unchanged. If adding one PM role sentence, keep it short:

```markdown
- PM owns product direction, scope, requirements, acceptance criteria, decisions, proof iteration, track triage, and sequencing.
```

- [ ] **Step 3: Run alignment test**

Run:

```bash
python3 -m pytest tests/test_runtime_skills.py::RuntimeSkillsTests::test_pm_contract_and_agents_align_with_generic_skill_surface -q
```

Expected:
- Pass.

## Task 7: Run Focused Verification

**Files:**
- No additional planned file changes.

- [ ] **Step 1: Runtime skill tests**

Run:

```bash
python3 -m pytest tests/test_runtime_skills.py -q
```

Expected:
- Pass.

- [ ] **Step 2: Launcher projection tests**

Run:

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py -q
```

Expected:
- Pass, including PM runtime `.agents/skills` projection.

- [ ] **Step 3: Existing docs/bitter boundary test**

Run:

```bash
python3 -m pytest tests/test_repo_consistency.py::RepoConsistencyTests::test_skill_and_contract_texts_do_not_copy_payload_field_or_schema_tables -q
```

Expected:
- Pass.

## Task 8: Run PM Pressure Scenario Validation

**Files:**
- Create only if recording evidence is needed: `docs/spec/2026-05-22-pm-skill-rebuild-pressure-validation.md`

- [ ] **Step 1: Run or simulate the pressure scenarios from the test plan**

Use P1-P8 from `docs/spec/2026-05-22-pm-skill-rebuild-test-plan.md`. For each scenario, record:

```markdown
## P<n>: <Scenario Name>

Input summary:
- <scenario input>

Observed PM output:
- <summary or artifact id if run through runtime>

Rubric:
- [ ] Required behavior 1
- [ ] Required behavior 2
- [ ] Required behavior 3

Result: pass | fail | blocked
Evidence:
- <command output, artifact id, or observed text>
```

- [ ] **Step 2: Treat failures correctly**

If a scenario fails because PM lacks skill guidance, update the relevant `SKILL.md` and rerun the
focused skill tests. If a scenario fails because a runtime tool response or catalog is incomplete,
stop and report that lower-layer defect instead of patching skill prose around it.

## Task 9: Run Full Regression

**Files:**
- No additional planned file changes.

- [ ] **Step 1: Run the full suite**

Run:

```bash
python3 -m pytest -q
```

Expected:
- Pass.
- If unrelated pre-existing failures appear, capture exact failing tests and evidence. Do not claim
  done unless focused PM skill and launcher verification passed.

## Self-Review Checklist Before Final Report

- The user approved the plan before implementation began.
- `write-prd` has no active skill package, manifest registration, or runtime projection expectation.
- PM has only generic product-management skills, not Wukong/page-type skills.
- Every PM skill follows Agent Skills frontmatter and progressive disclosure rules.
- Descriptions are trigger metadata only.
- Skill bodies contain PM product-work SOP, not prompt bulk or tool schemas.
- PM contract remains short and does not become an AGENTS-like manual.
- PM AGENTS remains runtime-boundary guidance, not a long SOP.
- Shared runtime tool skills remain atomic.
- Focused skill tests pass.
- Launcher projection tests pass.
- Pressure scenarios P1-P8 pass or failures are clearly attributed.
- Full regression passes or unrelated blockers are reported with evidence.

## Tool Decision

No new runtime tool is planned for this rebuild. If implementation pressure scenarios expose a
missing tool capability, record it as a separate follow-up and stop for user review rather than
expanding this task.
