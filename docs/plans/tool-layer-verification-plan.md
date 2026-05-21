# Tool Layer Verification Plan

Goal: prove the tool layer has complete action-level selection semantics, stale CLI flag guidance is gone, and browser/search/evidence behavior remains aligned with runtime responses.

Verification principle: no code or guidance change is done until the corresponding test or scan proves the old failure mode cannot return.

## Focused Tests

### Action Semantics Coverage

Command:

```bash
python3 -m unittest tests.test_env_tool_semantic_contract.EnvToolSemanticContractTests
```

Required new or updated tests:

- `test_every_action_has_action_owned_selection_semantics`
  - Iterates every `tool.action` from `registry.supported_tools()` and `registry.supported_actions(tool)`.
  - Asserts `action_semantics[action]["use_when"]` and `["do_not_use_when"]` are non-empty lists.
  - Asserts no entry contains:
    - `is the intended action`
    - `closer semantic match`
- `test_all_expected_actions_have_semantic_boundary_text`
  - Asserts exact registry action set still equals:
    - `artifact.get/create_revision/update_metadata`
    - `buddybox.desc/list/read/write/delete`
    - `comment.add/list`
    - `context.get/summarize/list_sources`
    - `evidence.issue_browser/approve_downgrade`
    - `message.send/list`
    - `search.status/request/open_browser`
    - `task.create/list/get/update/archive`
    - `track.create/list/open/update_now/add_material/add_update/add_proof/archive`
- `test_adjacent_action_boundaries_are_explained`
  - Checks selection text for the required pairs:
    - `track.add_material` vs `track.add_update` vs `track.add_proof`
    - `artifact.get` vs `artifact.create_revision` vs `artifact.update_metadata`
    - `task.list` vs `task.get` vs `task.update` vs `task.archive`
    - `comment.add` vs `track.add_update`
    - `search.request` vs `search.open_browser`
    - `evidence.issue_browser` vs `evidence.approve_downgrade`
    - `context.get` vs `context.summarize` vs `context.list_sources`
    - `buddybox.list` vs `buddybox.read` vs `buddybox.write` vs `buddybox.delete`
    - `message.send` vs `message.list` vs `comment.add`

Expected output:

```text
OK
```

### Schema Contract Boundaries

Command:

```bash
python3 -m unittest tests.test_env_tool_schema_contract.EnvToolSchemaContractTests
```

Required assertions:

- `ActionDefinition` validates action-level `use_when` and `do_not_use_when`.
- `artifact.create_revision` continues to reject direct publication fields by schema/behavior.
- `track.add_material` and `track.add_proof` publication payload fields remain `track_id`, `artifact_id`, `label`, `summary`.
- `track.add_update.refs` remains artifact-reference-only.
- `comment.add` target type semantics cover `track`, `artifact`, and `artifact_section`.
- `buddybox.read.encoding` schema and implementation are reconciled:
  - Either both accept `auto`, or implementation rejects `auto`.
  - The chosen contract must be tested.

Expected output:

```text
OK
```

### Search/Browser/Evidence Behavior

Command:

```bash
python3 -m unittest tests.test_search_env_tool tests.test_evidence_env_tool tests.test_market_browser_evidence
```

Required assertions:

- `search.status` reports capability/readiness without opening a page.
- `search.request` with browser backend returns:
  - `page_opened == False`
  - `state_changed == False`
  - `target_url`
  - `required_cockpit_tool == "chrome-devtools-cockpit"`
  - `allowed_next_actions` mentioning `search.open_browser`
- `search.open_browser` returns:
  - `page_opened == True`
  - `target_url`
  - `durability == "browser_session"`
  - `state_changed == True`
  - `mutates_product_state == False`
  - `allowed_next_actions` or command hint for `chrome-devtools-cockpit`
- `evidence.issue_browser` creates transient broker-token metadata only.
- `evidence.approve_downgrade` requires non-empty `reason` and is distinct from browser evidence.

Expected output:

```text
OK
```

## Regression Tests

### Runtime Skills

Command:

```bash
python3 -m unittest tests.test_runtime_skills.RuntimeSkillsTests
```

Required new or updated tests:

- `test_active_skills_do_not_teach_old_env_client_flags`
  - Scans manifest-listed active skills.
  - Forbids:
    - `search open-browser --query`
    - `search open_browser --query`
    - `--query`
    - `--engine`
    - `--track-id`
    - `--task-id`
    - `--artifact-id`
    - `--target-type`
    - `--target-id`
- `test_market_skills_use_payload_browser_entry`
  - Requires `search open-browser --payload`.
  - Requires `chrome-devtools-cockpit`.
  - Forbids old browser flag examples.
- `test_shared_tool_skill_env_client_examples_use_payload`
  - Any active skill command beginning `python3 scripts/env/client.py <tool> <action>` must include `--payload`.
  - Skills may point to `context.get.tool_catalog[...]` and `python3 scripts/turn_runtime.py status` instead of copying schema.

Expected output:

```text
OK
```

### Repo Consistency

Command:

```bash
python3 -m unittest tests.test_repo_consistency.RepoConsistencyTests
```

Required new or updated tests:

- Invert the old `track open --track-id` guard:
  - Remove assertions requiring old flags.
  - Require payload-form AGENTS examples for `track.open`, `task.get`, `artifact.get`, `context.summarize`, `context.get`, `search.status`, and `search.open_browser`.
- Add active guidance old-flag scan over:
  - `buddyswitch/skills`
  - `tools/launcher/assets/buddies`
  - `scripts/env/client.py`
- Allow forbidden strings only inside guardrail test definitions themselves.
- Keep existing no schema mirror checks.

Expected output:

```text
OK
```

### Env Client CLI

Command:

```bash
python3 -m unittest tests.test_env_client_payload_cli.EnvClientPayloadCliTests tests.test_search_env_tool.SearchEnvToolTests.test_search_cli_help_exposes_status_request_and_open_browser
```

Required assertions:

- Help exposes actions and `--payload`, not old per-field flags.
- Every action dispatch test uses the one canonical CLI spelling and `--payload`.
- Missing payload behavior remains current for empty-object actions only if the test intentionally covers it; active guidance should still show `--payload '{}'` for clarity.
- Underscore CLI action aliases are rejected if the implementation removes them:
  - `python3 scripts/env/client.py search open_browser --payload '{"query":"x"}'` must fail.
- Hyphenated CLI action spelling remains the only user-facing CLI spelling:
  - `python3 scripts/env/client.py search open-browser --payload '{"query":"x"}'` is parsed.

Expected output:

```text
OK
```

### Broker Action Alias Rejection

Command:

```bash
python3 -m unittest tests.test_env_tool_semantic_contract.EnvToolSemanticContractTests.test_broker_payload_action_ids_are_strict
```

Required assertion:

- Direct broker/runtime dispatch with `{"tool":"search","action":"open-browser","args":{"query":"x"}}` is rejected as unsupported.
- Direct broker/runtime dispatch with `{"tool":"search","action":"open_browser","args":{"query":"x"}}` remains the canonical action id path.
- This test may live in `tests/test_env_tool_semantic_contract.py` or a new focused file owned by I5.

Expected output:

```text
OK
```

## RG Guardrail Checks

### Old Env Client Flags

Command:

```bash
rg -n -u -e 'search open-browser --query' -e 'search open_browser --query' -e '--engine' -e '--track-id' -e '--task-id' -e '--artifact-id' -e '--target-type' -e '--target-id' buddyswitch/skills tools/launcher/assets/buddies scripts/env/client.py tests/test_runtime_skills.py tests/test_repo_consistency.py
```

Expected output:

- No active guidance hits.
- Test files may contain these strings only as forbidden pattern definitions or invalid-command assertions.

### Placeholder Semantics

Command:

```bash
rg -n -u 'is the intended action|closer semantic match|Operation completed with structured tool feedback' scripts/env tests
```

Expected output:

- No production hits.
- Test files may contain these strings only as forbidden placeholder assertions.

### Schema Mirror Guardrail

Command:

```bash
rg -n -u --glob '*.md' 'payload_fields|action_semantics|operation_semantics|\\|\\s*tool\\s*\\|\\s*action\\s*\\|\\s*payload|\\*\\*payload:\\*\\*|\\*\\*returns:\\*\\*|##\\s*payload\\s+examples|##\\s*operations' buddyswitch/skills tools/launcher/assets/buddies framework/contracts
```

Expected output:

- No hits in active skills or AGENTS.

## Runtime Catalog Introspection

Command:

```bash
PYTHONPATH=scripts python3 - <<'PY'
from env.tool_runtime import registry

expected = {
    "artifact": {"get", "create_revision", "update_metadata"},
    "buddybox": {"desc", "list", "read", "write", "delete"},
    "comment": {"add", "list"},
    "context": {"get", "summarize", "list_sources"},
    "evidence": {"issue_browser", "approve_downgrade"},
    "message": {"send", "list"},
    "search": {"status", "request", "open_browser"},
    "task": {"create", "list", "get", "update", "archive"},
    "track": {"create", "list", "open", "update_now", "add_material", "add_update", "add_proof", "archive"},
}

desc = registry.env_tools_description()
assert set(desc) == set(expected), set(desc)
missing = []
placeholder = []
for tool, actions in expected.items():
    assert set(desc[tool]["action_semantics"]) == actions
    for action in actions:
        row = desc[tool]["action_semantics"][action]
        use = row.get("use_when") or []
        no = row.get("do_not_use_when") or []
        if not use or not no:
            missing.append(f"{tool}.{action}")
        text = "\n".join(use + no)
        if "is the intended action" in text or "closer semantic match" in text:
            placeholder.append(f"{tool}.{action}")
print("missing_semantics=", missing)
print("placeholder_semantics=", placeholder)
raise SystemExit(1 if missing or placeholder else 0)
PY
```

Expected output:

```text
missing_semantics= []
placeholder_semantics= []
```

## CLI Help Checks

Commands:

```bash
python3 scripts/env/client.py search --help
python3 scripts/env/client.py search open-browser --help
python3 scripts/env/client.py track open --help
python3 scripts/env/client.py comment list --help
```

Expected output:

- Each command exits `0`.
- Action help includes `--payload`.
- Help text does not include `--query`, `--engine`, `--track-id`, `--task-id`, `--artifact-id`, `--target-type`, or `--target-id`.

## Invalid Old Flag Behavior Checks

Commands:

```bash
python3 scripts/env/client.py search open-browser --query x --engine google
python3 scripts/env/client.py track open --track-id track-alpha
python3 scripts/env/client.py task get --task-id task-alpha
python3 scripts/env/client.py artifact get --artifact-id art-alpha
python3 scripts/env/client.py comment list --target-type track --target-id track-alpha
```

Expected output:

- Each exits non-zero.
- Each fails at CLI parsing or env CLI validation before any runtime broker action.
- This failure is correct behavior; it is not a reason to add aliases or compatibility flags.

If underscore CLI action aliases are removed:

```bash
python3 scripts/env/client.py search open_browser --payload '{"query":"x"}'
```

Expected output:

- Exits non-zero.
- `search open-browser --payload '{"query":"x"}'` remains the single CLI spelling.

Direct `env.tool` payload action alias check:

- Dispatching action `"open-browser"` must be rejected.
- Dispatching action `"open_browser"` is the only broker action id path.

## Final Verification Command List

Run after implementation:

```bash
python3 -m unittest tests.test_env_tool_semantic_contract tests.test_env_tool_schema_contract
python3 -m unittest tests.test_runtime_skills tests.test_repo_consistency
python3 -m unittest tests.test_env_client_payload_cli tests.test_search_env_tool tests.test_evidence_env_tool tests.test_market_browser_evidence
rg -n -u -e 'search open-browser --query' -e 'search open_browser --query' -e '--engine' -e '--track-id' -e '--task-id' -e '--artifact-id' -e '--target-type' -e '--target-id' buddyswitch/skills tools/launcher/assets/buddies scripts/env/client.py tests/test_runtime_skills.py tests/test_repo_consistency.py
```

Expected final result:

- All unittest commands pass with `OK`.
- The `rg` command has no active guidance hits and only test guardrail definitions where expected.
- Runtime catalog action semantics no longer include placeholder template text.
- Browser workflow guidance and response semantics both point to `search.open_browser --payload ...` followed by `chrome-devtools-cockpit`.
