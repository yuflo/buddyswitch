# Skill Tool Boundary Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the remaining stale skill/tool boundary prose so skills and docs consume env.tool contracts through runtime discovery only.

**Architecture:** Keep the existing thin runtime chain: `SKILL -> Tool Contract -> Service -> Domain Ops -> Object Repo`. This change does not alter runtime behavior; it tightens documentation and guardrail tests so payload schemas stay in per-tool packages and runtime catalog projections, not skill assets or README prose.

**Tech Stack:** Markdown docs, Python 3 `unittest`/`pytest`, `rg`, existing BuddySwitch runtime catalog and boundary tests.

---

## Current Bottleneck

Two prose surfaces still weaken the otherwise clear skill/tool split:

- `buddyswitch/skills/shared/track-tool/assets/track-operation-template.md` embeds track payload examples inside a skill package asset.
- `README.md` still names deleted central runtime sources: `scripts/env/tools/contracts.py` and `scripts/env/tools/semantics.py`.

The runtime code path is already aligned. The cleanup should only touch docs/tests and the stale skill asset.

## Scope

Do:

- Delete or neutralize the stale track payload asset.
- Add tests that catch payload-schema mirrors in skill assets, not only `SKILL.md` files.
- Update README canonical runtime sources to the per-tool package layout and `env.tools.catalog`.
- Run focused boundary verification.

Do not:

- Change env.tool runtime behavior.
- Add compatibility aliases for old central contract modules.
- Rewrite unrelated specs, memos, role contracts, or skills.
- Expand this into a new architecture pass.

## File Structure

- Modify `tests/test_repo_consistency.py`
  - Owns broad prose consistency checks.
  - Add a guard for payload-heading mirrors such as:

```markdown
## `track.create` payload
```

  - Add a README source-of-truth test for current per-tool runtime files.

- Modify `tests/test_env_layer_boundaries.py`
  - Owns runtime layer and boundary checks.
  - Mirror the payload-heading guard so boundary tests catch future skill asset drift.

- Delete `buddyswitch/skills/shared/track-tool/assets/track-operation-template.md`
  - This file is a stale prompt-side payload mirror.
  - Runtime payload examples must come from `context.get.tool_catalog`, `python3 scripts/turn_runtime.py status`, or minimal inline command examples in `SKILL.md`.

- Modify `README.md`
  - Replace central `contracts.py` / `semantics.py` references with per-tool package files plus `scripts/env/tools/catalog.py`.

## Execution Prep

- [ ] **Step 1: Inspect current worktree changes**

Run:

```bash
git status --short
git diff -- README.md tests/test_repo_consistency.py tests/test_env_layer_boundaries.py buddyswitch/skills/shared/track-tool/assets/track-operation-template.md
```

Expected:

- You understand whether the touched files already contain user or previous-agent changes.
- Preserve unrelated changes. Do not revert files outside this plan.

- [ ] **Step 2: Confirm the stale asset is currently unreferenced or only stale-doc referenced**

Run:

```bash
rg -n 'track-operation-template|track\.create` payload|track\.update_now` payload|track\.add_update` payload' .
```

Expected before cleanup:

- At minimum, hits inside `buddyswitch/skills/shared/track-tool/assets/track-operation-template.md`.
- If active code or manifest references this asset, replace that reference with runtime discovery guidance before deleting the asset.

## Task 1: Add Guardrails For Payload Mirrors In Skill Assets

**Files:**
- Modify: `tests/test_repo_consistency.py`
- Modify: `tests/test_env_layer_boundaries.py`

- [ ] **Step 1: Extend the broad prose schema-copy regex**

In `tests/test_repo_consistency.py`, update `test_skill_and_contract_texts_do_not_copy_payload_field_or_schema_tables` so the regex expression also rejects code-formatted payload headings.

Add this pattern to the existing regex string:

```python
+ "|##\\s*`[^`]+`\\s+payload"
```

The final regex expression in that test must include these relevant fragments:

```python
(
    "payload_fields"
    + "|action_semantics"
    + "|operation_semantics"
    + "|TOOL_SPEC"
    + "|ACTION_SEMANTICS"
    + "|HANDLER_SPECS"
    + "|scripts/env/tools/.*/contract\\.py"
    + "|scripts/env/tools/.*/semantics\\.py"
    + "|scripts/env/tools/.*/handlers\\.py"
    + "|scripts/env/tools/.*/service\\.py"
    + "|\\|\\s*tool\\s*\\|\\s*action\\s*\\|\\s*payload"
    + "|\\|\\s*action\\s*\\|\\s*payload"
    + "|\\*\\*payload:\\*\\*"
    + "|\\*\\*returns:\\*\\*"
    + "|##\\s*payload\\s+examples"
    + "|##\\s*operations"
    + "|##\\s*`[^`]+`\\s+payload"
)
```

- [ ] **Step 2: Extend the env layer boundary regex**

In `tests/test_env_layer_boundaries.py`, update `test_skills_and_boundary_guides_do_not_copy_payload_or_schema_tables` with the same payload-heading guard:

```python
(
    "payload_fields"
    + "|action_semantics"
    + "|operation_semantics"
    + "|\\|\\s*tool\\s*\\|\\s*action\\s*\\|\\s*payload"
    + "|\\|\\s*action\\s*\\|\\s*payload"
    + "|##\\s*`[^`]+`\\s+payload"
)
```

- [ ] **Step 3: Run the new guardrails and confirm they fail on the existing stale asset**

Run:

```bash
python3 -m pytest tests/test_repo_consistency.py::RepoConsistencyTests::test_skill_and_contract_texts_do_not_copy_payload_field_or_schema_tables tests/test_env_layer_boundaries.py::EnvLayerBoundaryTests::test_skills_and_boundary_guides_do_not_copy_payload_or_schema_tables -q
```

Expected before cleanup:

- FAIL.
- Failure output names `buddyswitch/skills/shared/track-tool/assets/track-operation-template.md`.

## Task 2: Remove The Stale Track Payload Asset

**Files:**
- Delete: `buddyswitch/skills/shared/track-tool/assets/track-operation-template.md`

- [ ] **Step 1: Delete the stale asset**

Delete:

```text
buddyswitch/skills/shared/track-tool/assets/track-operation-template.md
```

Reason:

- The file duplicates runtime payload shape in skill-package prose.
- The active `track-tool` skill already points users to `context.get.tool_catalog['track']` and `python3 scripts/turn_runtime.py status`.

- [ ] **Step 2: Verify no active reference remains**

Run:

```bash
rg -n 'track-operation-template|track\.create` payload|track\.update_now` payload|track\.add_update` payload' buddyswitch/skills tests framework tools README.md
```

Expected:

- No hits in active skill, framework, launcher, or README surfaces.

- [ ] **Step 3: Re-run the guardrail tests**

Run:

```bash
python3 -m pytest tests/test_repo_consistency.py::RepoConsistencyTests::test_skill_and_contract_texts_do_not_copy_payload_field_or_schema_tables tests/test_env_layer_boundaries.py::EnvLayerBoundaryTests::test_skills_and_boundary_guides_do_not_copy_payload_or_schema_tables -q
```

Expected:

- PASS.

## Task 3: Update README Runtime Source Guidance

**Files:**
- Modify: `README.md`
- Modify: `tests/test_repo_consistency.py`

- [ ] **Step 1: Add a README source-of-truth regression test**

Add this test method to `tests/test_repo_consistency.py`, near the other prose/runtime consistency tests:

```python
    def test_readme_runtime_sources_match_per_tool_runtime(self) -> None:
        text = (ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("scripts/env/tools/catalog.py", text)
        self.assertIn("scripts/env/tools/<tool>/contract.py", text)
        self.assertIn("scripts/env/tools/<tool>/semantics.py", text)
        self.assertIn("scripts/env/tools/<tool>/cli.py", text)
        self.assertIn("scripts/env/tools/<tool>/handlers.py", text)
        self.assertIn("scripts/env/tools/<tool>/service.py", text)

        self.assertNotIn("scripts/env/tools/contracts.py", text)
        self.assertNotIn("scripts/env/tools/semantics.py` for machine-readable operation semantics", text)
```

- [ ] **Step 2: Run the README test and confirm it fails**

Run:

```bash
python3 -m pytest tests/test_repo_consistency.py::RepoConsistencyTests::test_readme_runtime_sources_match_per_tool_runtime -q
```

Expected before README cleanup:

- FAIL because `README.md` still names `scripts/env/tools/contracts.py` and central `scripts/env/tools/semantics.py`.

- [ ] **Step 3: Replace the README canonical runtime source bullets**

In `README.md`, replace the current bullets under `## Canonical Runtime Sources` that name central tool files with:

```markdown
- `scripts/env/tools/<tool>/contract.py` for per-tool action names, payload fields, permissions, and return metadata.
- `scripts/env/tools/<tool>/semantics.py` for per-tool machine-readable capability and action semantics.
- `scripts/env/tools/<tool>/cli.py`, `handlers.py`, and `service.py` for per-tool CLI registration, selected dispatch mapping, and service execution.
- `scripts/env/tools/catalog.py` for service-light env tool discovery, status/catalog projection, and operation semantics projection.
```

Keep the existing runtime kernel, context payload, workspace projection, role contract, and test bullets unless they are directly adjacent wording that now reads incorrectly.

- [ ] **Step 4: Run the README test again**

Run:

```bash
python3 -m pytest tests/test_repo_consistency.py::RepoConsistencyTests::test_readme_runtime_sources_match_per_tool_runtime -q
```

Expected:

- PASS.

## Task 4: Focused Verification

**Files:**
- Verify only.

- [ ] **Step 1: Run the skill/tool boundary suite**

Run:

```bash
python3 -m pytest tests/test_runtime_skills.py tests/test_repo_consistency.py tests/test_env_layer_boundaries.py tests/test_env_tool_package_independence.py -q
```

Expected:

- PASS.

- [ ] **Step 2: Confirm runtime status still exposes the catalog projection**

Run:

```bash
python3 -c 'import json, subprocess; payload=json.loads(subprocess.check_output(["python3","scripts/turn_runtime.py","status"], text=True)); print(payload["ok"]); print(",".join(sorted(payload["env_tools"]))); print(",".join(payload["env_tools"]["track"]["operations"]))'
```

Expected output:

```text
True
artifact,buddybox,comment,context,evidence,message,search,task,track
create,list,open,update_now,add_material,add_update,add_proof,archive
```

- [ ] **Step 3: Run the prose drift scan**

Run:

```bash
rg -n '## `.*payload|payload_fields|action_semantics|operation_semantics|TOOL_SPEC|ACTION_SEMANTICS|HANDLER_SPECS|contract\.py|semantics\.py|handlers\.py|service\.py|\|\s*action\s*\|\s*payload' buddyswitch/skills framework/contracts tools/launcher/assets/buddies -S --glob '*.md'
```

Expected:

- No output.

- [ ] **Step 4: Run whitespace diff check**

Run:

```bash
git diff --check
```

Expected:

- No output.

## Completion Criteria

The cleanup is complete only when:

- The stale track payload asset is gone or no longer contains payload/action schema prose.
- README points to per-tool package files and `scripts/env/tools/catalog.py`, not deleted central registry modules.
- Guardrail tests fail before cleanup and pass after cleanup.
- Focused verification passes.
- No runtime behavior or object-layer code changed.

## Expected Final Summary

Report:

- Deleted stale `track-tool` payload asset.
- Updated README canonical runtime source bullets.
- Added guardrail tests for skill package payload mirrors and README source drift.
- Verification commands and pass/fail results.
- Remaining risk: low; this is prose/test cleanup only, with no runtime behavior change.
