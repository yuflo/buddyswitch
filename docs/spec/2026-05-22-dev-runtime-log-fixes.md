# Dev Runtime Log Fixes Implementation Plan

**Goal:** Fix framework behavior exposed by the Dev runtime log without repairing any already-started buddy instance workspace. The main product failure is `context summarize --payload '{}'` returning `ok:false` when the normal launcher topology projects `workspace/projects/app` as a symlink to the shared project workspace source root.

**Core boundary:** This is a framework/runtime interpretation fix. Do not mutate launcher-created instance workspaces, do not add workspace repair steps, and do not require launcher to persist new fields in `instance.json`.

---

## Current Bottleneck

The blocking failure is `context.source_workspace` rejecting the standard launcher-managed source projection:

```text
<shared-root>/instances/<instance-id>/workspace/projects/app
  -> <shared-root>/project/workspace/projects/app
```

`context` is read-only and should report source facts from existing runtime topology. It should accept the standard launcher projection and reject symlinks that escape that project source root.

Expected non-bugs from the same log:

- `message.list` does not accept `box`; it is inbox-only and should be called with `{}` or supported filters such as `buddy`, `q`, and `limit`.
- `buddybox.logical_name` must not start with a buddy id such as `dev/`.
- `E_RUNTIME_BROKER_BUSY` is expected when broker workers are saturated; broker capacity behavior should remain unchanged unless a focused test proves a defect.

---

## Framework Work

### 1. Context Source Workspace Topology

Modify:

- `tests/test_context_binding_env_tool.py`
- `scripts/env/tools/context/_impl.py`

Add tests that build a temporary launcher-style shared root outside the repository:

- Accept `workspace/projects/app` when it resolves exactly to `<shared-root>/project/workspace/projects/app`.
- Reject `workspace/projects/app` when it resolves anywhere else.
- Use `tempfile.TemporaryDirectory()` so tests do not create `project-workspace-*` or `outside-source-*` directories in the checkout.
- Do not add or depend on `project_workspace_dir` in `instance.json`.

Implementation direction:

- Keep `context` read-only.
- Validate the raw env profile path stays lexically under `workspace_dir`.
- If the resolved source root leaves `workspace_dir`, derive `<shared-root>/project/workspace` from standard launcher topology:
  - primary: `instance_json.parent.parent.parent` when `instance_json` is under `<shared-root>/instances/<instance-id>/instance.json`;
  - fallback: `workspace_dir` shaped as `<shared-root>/instances/<instance-id>/workspace`.
- Accept only the exact derived project source root.
- Raise `E_CONTEXT_SOURCE_WORKSPACE` with project workspace wording for escapes.

Do not:

- Add a source-write tool.
- Read source path authority from AGENTS.
- Require launcher `instance.json` to include `project_workspace_dir`.
- Repair or rewrite any existing buddy instance workspace.

### 2. Skill Misuse Guardrails

Modify:

- `tests/test_runtime_skills.py`
- `buddyswitch/skills/shared/message-tool/SKILL.md`
- `buddyswitch/skills/shared/buddybox-tool/SKILL.md`

Add skill quality tests and guidance:

- `message.list` does not accept `box`; use `request.list` for inbox/outbox request filtering.
- Keep the valid `message list --payload '{}'` example.
- Buddybox `logical_name` must not use absolute paths, traversal, or buddy id prefixes.
- Add concrete buddybox examples:
  - Good: `logical_name="heartbeats/b.md"`.
  - Bad: `logical_name="dev/b-heartbeat.md"` because `dev/` is a buddy id prefix.

Do not:

- Add compatibility to `message.list`.
- Weaken buddybox prefix rejection.
- Copy full tool schemas into skills.

### 3. Broker Busy Semantics

Modify no production code unless a focused test fails.

Run the existing broker capacity test to confirm `E_RUNTIME_BROKER_BUSY` remains retryable and does not kill the server. Use the actual test class name present in the repository.

---

## Workspace-Local Work That Is Not In Scope

Do not treat these as implementation goals:

- Fixing a specific launched buddy instance workspace.
- Rewriting `workspace/projects/app` inside an existing runtime instance.
- Persisting `project_workspace_dir` into launcher-created `instance.json`.
- Adding launcher tests for new instance record fields.
- Editing runtime object JSON or buddybox local files directly.

If a specific instance workspace is corrupted, that is an operational cleanup issue outside this framework fix.

---

## Verification Plan

Run focused red/green checks where practical:

```bash
python3 -m pytest -q \
  tests/test_context_binding_env_tool.py::ContextBindingEnvToolTests::test_context_summarize_accepts_launcher_project_symlink_source_workspace \
  tests/test_context_binding_env_tool.py::ContextBindingEnvToolTests::test_context_summarize_rejects_source_symlink_outside_project_workspace
```

```bash
python3 -m pytest -q tests/test_context_binding_env_tool.py
```

```bash
python3 -m pytest -q tests/test_runtime_skills.py::RuntimeSkillsTests::test_shared_message_and_buddybox_skills_prevent_observed_invalid_calls
```

```bash
python3 -m pytest -q tests/test_runtime_skills.py
```

```bash
python3 -m pytest -q tests/test_runtime_broker.py::RuntimeBrokerServerIsolationTests::test_capacity_limit_returns_busy_without_killing_server
```

Run focused integration guardrails:

```bash
python3 -m pytest -q \
  tests/test_context_binding_env_tool.py \
  tests/test_runtime_skills.py \
  tests/test_runtime_broker.py::RuntimeBrokerServerIsolationTests::test_capacity_limit_returns_busy_without_killing_server
```

Run sandbox boundary tests:

```bash
python3 -m pytest -q \
  tests/test_buddy_env_sandbox.py \
  tests/test_env_layer_boundaries.py
```

Then run full verification:

```bash
python3 -m pytest -q
```

If any command fails, has unexpected skips, or is blocked by environment capability, stop and report the blocker.

---

## Review Checklist

- `context` reports read-only source facts only.
- Standard launcher source symlink is accepted.
- Symlink escape outside `<shared-root>/project/workspace/projects/app` is rejected.
- No launcher `instance.json` field is added.
- No launched buddy instance workspace is edited or repaired.
- No source path/access facts are added back to AGENTS.
- `message.list` remains forward-only; no `box` compatibility is added.
- Buddybox prefix rejection remains enforced.
- Skill guidance describes guardrails, not full runtime schemas.
- Diff is limited to framework context code, context tests, runtime skill tests, and shared skill docs.
