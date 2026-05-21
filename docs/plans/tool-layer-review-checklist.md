# Tool Layer Review Checklist

Use this checklist after implementation and before declaring the tool-layer cleanup complete. Every row must be marked pass or fail with evidence.

## Docs/Bitter Compliance

| Check | Pass condition | Evidence command or file |
| --- | --- | --- |
| Runtime-visible semantics own action choice | Every action's `use_when` and `do_not_use_when` comes from `ActionDefinition` / tool definitions and is projected through `registry.env_tools_description()` | `scripts/env/tool_runtime/definition.py`, `scripts/env/tool_runtime/registry.py`, `scripts/env/tools/*/tool.py` |
| Skills do not compensate for weak tool contracts | Skills point to runtime discovery and response fields instead of explaining missing action semantics | `python3 -m unittest tests.test_runtime_skills.RuntimeSkillsTests` |
| AGENTS stays short and operational | Buddy AGENTS only include startup/discovery/runtime boundary guidance and no payload schema tables | `python3 -m unittest tests.test_repo_consistency.RepoConsistencyTests` |
| Tool response remains effect-bearing | Search/evidence/comment/track responses still report state change, durability, read scope, next actions, and field errors where relevant | `python3 -m unittest tests.test_search_env_tool tests.test_evidence_env_tool tests.test_env_tool_response_contract` |
| No prose mirrors of runtime schema | Active Markdown contains no `payload_fields`, `action_semantics`, `operation_semantics`, operations tables, payload tables, or returns tables | `rg -n -u --glob '*.md' 'payload_fields|action_semantics|operation_semantics|\\*\\*payload:\\*\\*|\\*\\*returns:\\*\\*|##\\s*operations' buddyswitch/skills tools/launcher/assets/buddies framework/contracts` returns no active hits |

## SHARP Compliance

| Check | Pass condition | Evidence |
| --- | --- | --- |
| Current bottleneck is solved | Registry no longer emits template action semantics; stale CLI flag guidance is gone | Runtime introspection check and old flag rg check pass |
| Shortest validated path | Implementation only extends existing definition/registry/tool/test files and active guidance files | `git diff --name-only` matches planned write sets |
| No speculative abstraction | No workflow engine, plugin system, event bus, rule engine, generic DSL, compatibility adapter, or migration layer was added | `rg -n -u 'workflow engine|plugin system|event bus|rule engine|generic DSL|compatibility adapter|migration layer' scripts tests buddyswitch tools` has no new implementation hits |
| Replace instead of layer | Placeholder registry semantics are removed, not wrapped or special-cased | `rg -n 'is the intended action|closer semantic match' scripts/env` returns no hits |
| Verification before done | All focused tests, regression tests, rg checks, CLI help checks, and invalid old flag checks have been run | Verification log attached to final implementation report |

## No Compatibility Residue

| Check | Pass condition | Evidence |
| --- | --- | --- |
| No old flag alias design | `scripts/env/client.py` does not define old per-field flags or aliases for `--query`, `--engine`, `--track-id`, `--task-id`, `--artifact-id`, `--target-type`, or `--target-id` | `python3 scripts/env/client.py search open-browser --query x --engine google` exits non-zero |
| No deprecated old examples | Active skills and AGENTS contain no old flag examples even with "deprecated" labels | Old flag rg check returns no active guidance hits |
| No dual-path CLI guidance | Active guidance shows only payload-form env client action calls; no old flag alternatives | `tests.test_runtime_skills` and `tests.test_repo_consistency` pass |
| One CLI action spelling | Hyphenated argparse action names are the only user-facing CLI subcommands; underscore dot action ids remain runtime catalog ids only | `python3 scripts/env/client.py search open_browser --payload '{"query":"x"}'` exits non-zero if alias cleanup is implemented |
| Strict broker action ids | Direct `env.tool` payloads accept only underscore registry action ids and do not normalize hyphen aliases | Focused dispatch test rejects `{"action":"open-browser"}` and accepts only `"open_browser"` |
| No old tests protecting stale guidance | No test asserts `track open --track-id`, `task get --task-id`, `artifact get --artifact-id`, or `search open-browser --query` as desired output | `rg -n 'assertIn\\(\".*--track-id|assertIn\\(\".*--task-id|assertIn\\(\".*--artifact-id|assertIn\\(\".*--query' tests` has no stale positive assertions |
| Old flag failures are accepted as correct | Invalid old flag commands fail and are not treated as reason to restore aliases | Invalid old flag behavior checks pass |

## No Prose Mirror / No Schema Duplication

| Check | Pass condition | Evidence |
| --- | --- | --- |
| Skills do not copy complete runtime schemas | Active skills contain no operation/action/payload/return schema tables | Markdown schema mirror rg check returns no active hits |
| AGENTS does not copy complete runtime schemas | Buddy AGENTS contain no payload field lists or response schema details | `python3 -m unittest tests.test_repo_consistency.RepoConsistencyTests` |
| Buddybox private paths are not exposed | Active skills/AGENTS do not mention `buddyswitch/local/buddybox`, object store paths, or private filesystem paths | `rg -n -u 'buddyswitch/local/buddybox|buddyswitch/objects|private.*filesystem path' buddyswitch/skills tools/launcher/assets/buddies` returns no active guidance hits |
| Runtime discovery is referenced instead | Shared tool skills retain `context.get.tool_catalog[...]` or `python3 scripts/turn_runtime.py status` references for exact contracts | `python3 -m unittest tests.test_runtime_skills.RuntimeSkillsTests` |

## Browser Workflow Correctness

| Check | Pass condition | Evidence |
| --- | --- | --- |
| Browser enforcement is not treated as bug | Plan and implementation keep browser-native market path: `search.open_browser` then `chrome-devtools-cockpit` | Market skill tests require both strings |
| Search request does not open browser | `search.request` returns `page_opened=false`, `state_changed=false`, and `target_url` | `python3 -m unittest tests.test_search_env_tool.SearchEnvToolTests.test_search_request_browser_returns_actionable_instruction_without_opening_page` |
| Search open mutates browser session only | `search.open_browser` returns `page_opened=true`, `durability=browser_session`, `target_url`, and cockpit next action, without product object mutation | `python3 -m unittest tests.test_search_env_tool.SearchEnvToolTests.test_search_open_browser_opens_cdp_page_with_encoded_target_url` |
| Market skills use payload browser entry | All active market skills use `search open-browser --payload` and no old `--query/--engine` flags | `python3 -m unittest tests.test_runtime_skills.RuntimeSkillsTests.test_market_skills_use_payload_browser_entry` after added |
| Browser downgrade is explicit | `evidence.approve_downgrade` requires target artifact and reason; it is not silent fallback for browser access failures | `python3 -m unittest tests.test_evidence_env_tool tests.test_market_browser_evidence` |

## Action Semantics Quality

| Check | Pass condition | Evidence |
| --- | --- | --- |
| No generic `use_when` templates | No action selection text contains `is the intended action` | Runtime introspection check |
| No generic `do_not_use_when` templates | No action selection text contains `closer semantic match` | Runtime introspection check |
| No action missing adjacent distinction | Required adjacent pairs are explicitly distinguished in action semantics or semantic tests | `tests.test_env_tool_semantic_contract` |
| All current registry actions covered | The action set in semantic tests equals registry discovery and expected action map | `tests.test_env_tool_semantic_contract` |
| Work-object publication path is clear | `artifact.create_revision`, `track.add_material`, `track.add_proof`, `track.open`, and `artifact.get` semantics match draft -> publish -> read path | `tests.test_env_tool_semantic_contract` |
| Timeline/comment/message boundaries are clear | `track.add_update`, `comment.add`, and `message.send` semantics distinguish timeline, object discussion, and inbox message | `tests.test_env_tool_semantic_contract` |
| Context/buddybox/message boundaries are clear | `context.*`, `buddybox.*`, and `message.*` semantics distinguish transient context, private files, and durable direct messages | `tests.test_env_tool_semantic_contract` |
| Search/evidence boundaries are clear | `search.status`, `search.request`, `search.open_browser`, `evidence.issue_browser`, and `evidence.approve_downgrade` semantics distinguish metadata, planning, browser session, browser evidence token, and downgrade token | `tests.test_env_tool_semantic_contract` |
| State effect terms are not flattened | Browser session, transient token, private file, runtime object, and read-only actions are not all described as generic durable state | `tests.test_env_tool_semantic_contract` plus response tests |

## Known Drift Fixes

| Check | Pass condition | Evidence |
| --- | --- | --- |
| `comment` response no longer points to nonexistent `track.get` | Comment rejection guidance says `track.open` or `artifact.get` as appropriate | `rg -n 'track.get' scripts/env/tools/comment tests` has no stale positive guidance |
| `track.add_material.summary` does not imply timeline update row | Field description and semantics say material summary/publication summary, not timeline row | `scripts/env/tools/track/tool.py` review and semantic test |
| `comment.add` preconditions include supported target scope | Definition covers `track`, `artifact`, and `artifact_section` boundary consistently with schema/implementation | `scripts/env/tools/comment/tool.py` and schema tests |
| `buddybox.read.encoding` contract is reconciled | Schema and implementation both accept or both reject `auto`; tests lock the choice | `tests.test_env_tool_schema_contract` and buddybox behavior tests |
| `comment.list.status` contract is reconciled if implementation accepts `all` | Schema and implementation agree on accepted status values | `tests.test_env_tool_schema_contract` or focused comment tests |

## Final Pass/Fail Gate

The implementation passes only if all of these are true:

- No old flag alias design remains.
- No deprecated old examples remain.
- No dual-path CLI guidance remains.
- No generic action semantics templates remain.
- No registered action is missing semantics.
- Every action with adjacent alternatives has explicit selection boundaries.
- Skills and AGENTS do not copy runtime schema.
- Browser enforcement is preserved as correct behavior.
- Every current registry action is covered.
- All tests and rg guardrails have explicit commands and expected output in `docs/plans/tool-layer-verification-plan.md`.

Any failed item blocks completion. Do not reclassify a failed old-flag command as a compatibility requirement.
