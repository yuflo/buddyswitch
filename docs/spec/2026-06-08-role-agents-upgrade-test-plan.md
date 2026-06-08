# Role AGENTS Bootstrap Upgrade Test Plan

## Source

- Direction memo: `docs/memo/2026-06-08-role-agents-upgrade-direction.html`
- Authoritative implementation inputs:
  - `buddyswitch/manifest.toml`
  - `buddyswitch/env-profiles/{pm,design,dev,market,test}.json`
  - `framework/contracts/{pm,design,dev,market,test}.md`
  - `tools/launcher/assets/roles/{pm,design,dev,market,test}/AGENTS.md`

## Goal

Upgrade the five role `AGENTS.md` files from generic runtime guidance into short role bootstrap files. The files must keep shared runtime safety rules, add a concise role-specific entry section, and remain explicit that runtime permissions come from profiles, contracts, broker policy, and tools rather than `AGENTS.md`.

## Functional Requirements

1. Every role bootstrap uses the same section structure:
   - `# BuddySwitch Runtime Workspace`
   - `## Bootstrap Rules`
   - `## Role Entry`
   - `## Output Rule`
2. Every role bootstrap states that `AGENTS.md` is bootstrap guidance only and is not the permission source.
3. Shared bootstrap rules preserve current runtime safety:
   - active role lock
   - context summary first when runtime context is needed
   - durable runtime state through native BuddySwitch env MCP tools
   - tool catalog or `python3 scripts/turn_runtime.py status` only for exact schema or diagnostics
   - Buddybox/private files stay actor-private and product-readable content must be artifact-backed
   - projected runtime storage paths must not be edited directly
   - full artifact body must be read before claiming artifact content
   - search/browser routing must respect BuddySwitch search tools and browser cockpit
   - broker/tool rejection feedback must not be bypassed
4. Role-specific entry rules must be concise and traceable:
   - `design`: durable design outputs, explicit task/track context, shared design material via artifacts/track, private prototypes vs artifact handoff, existing design systems over invented visual systems.
   - `dev`: approved source scope, source authority from runtime profile/context, full upstream artifact reads, existing UI components/tokens/design artifacts, final evidence with changed files and verification.
   - `pm`: product direction/scope/requirements/acceptance/decisions/proof iteration, read shared track state before mutations, PM-only comment resolution only when authorized, next owner/action in final output.
   - `market`: discovery through BuddySwitch search/browser tools, target-scoped non-fabricated evidence, draft artifacts before track publication, evidence/blocker output.
   - `test`: explicit verification scope, read shared track/artifact bodies before judging, no source edits under read-only profile, pass/fail/blocked evidence and remaining risk.
5. Negative constraints:
   - no tool catalog dump
   - no payload schema or JSON examples
   - no raw runtime storage paths that invite direct edits
   - no copied skill workflow steps or role methodology manuals
   - no permission claim sourced from `AGENTS.md`
   - no hardcoded source-root path in role bootstraps
   - no old env client CLI examples or retired flags
6. Launcher workspace copies must continue to copy the exact role asset into runtime `AGENTS.md`.

## Automated Tests

### Focused role bootstrap tests

Add or extend `tests/test_repo_consistency.py` with a behavior-level regression test that:

- iterates the manifest role ids `market`, `pm`, `design`, `dev`, and `test`;
- reads each corresponding role `AGENTS.md`;
- asserts the common section structure;
- asserts the bootstrap-permission-source sentence;
- asserts the shared runtime safety fragments;
- asserts role-specific required fragments for each role;
- asserts forbidden fragments are absent.

Expected RED before implementation:

```text
FAIL: role bootstraps do not contain ## Bootstrap Rules / ## Role Entry and role-specific required fragments.
```

Expected GREEN after implementation:

```text
python3 -m pytest tests/test_repo_consistency.py::RepoConsistencyTests::test_runtime_role_agents_are_short_role_bootstraps -q
1 passed
```

### Existing guidance regression tests

Run the existing tests that already protect role guidance from retired runtime wording:

```bash
python3 -m pytest tests/test_repo_consistency.py::RepoConsistencyTests::test_runtime_role_agents_use_native_first_env_tool_guidance tests/test_runtime_skills.py::RuntimeSkillsTests::test_pm_contract_and_agents_align_with_generic_skill_surface -q
```

Expected result: all pass.

### Launcher copy regression

Run the focused launcher test that verifies runtime workspaces receive the role `AGENTS.md` asset. This test uses fake executables and temp homes; do not run the whole launcher suite unless the focused checks pass and residual process checks are clean.

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_execution_worktree_uses_runtime_workspace_agents_header -q
```

Expected result: pass and no residual long-lived fake browser/app-server processes.

### Source audits

Run targeted audits:

```bash
rg -n "## Runtime Boundary|AGENTS.md is guidance only and not the permission source|projects/app|payload schema|payload_fields|tool catalog dump|JSON example|python3 scripts/env/client.py|search open-browser --payload|context summarize --payload" tools/launcher/assets/roles
```

Expected result:

- no `## Runtime Boundary`
- no old `AGENTS.md is guidance only and not the permission source`
- no hardcoded source-root path
- no payload/schema/example residue
- no retired env client examples

Run formatting check:

```bash
git diff --check
```

Expected result: exit 0.

## Resource Lifecycle Guard

This task should not require broad service-starting verification. Follow `docs/bitter/2026-05-26-test-resource-lifecycle-principles.md`:

1. Run focused pure consistency tests first.
2. Run the single launcher-copy test only after focused tests pass.
3. Avoid broad launcher or full-suite runs unless a lifecycle reason is proven.
4. If any service-starting test is run, inspect residual processes before declaring completion.

## Review Checklist

- Every requirement above maps to at least one focused test or audit.
- Tests validate desired bootstrap behavior, not incidental line placement.
- No test encodes private implementation paths beyond the documented role asset location.
- Verification scope is proportional to the content-only change.
