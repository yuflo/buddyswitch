# Tool Layer CLI Guidance Drift Plan

Goal: make every active skill and buddy AGENTS example agree with the current env client contract:

```bash
python3 scripts/env/client.py <tool> <action> --payload '<JSON_OBJECT>'
```

Current bottleneck: active guidance still teaches old per-field flags that `scripts/env/client.py` does not accept. When a host follows those examples, argparse fails before the call can reach structured `env.tool` feedback. This is guidance drift, not a reason to restore compatibility flags.

Runtime conclusion:

- Do not add or restore `--query`, `--engine`, `--track-id`, `--task-id`, `--artifact-id`, `--target-type`, or `--target-id`.
- Do not mark old examples deprecated and keep them.
- Do not support dual path CLI examples.
- Do not support hyphenated `env.tool` broker action ids as aliases for underscore registry action ids.
- Do not use skills or AGENTS to compensate for unclear runtime contracts.
- Browser workflow remains correct: call `search.open_browser` through payload JSON, then continue in `chrome-devtools-cockpit`.

## Old CLI Flag Inventory

Required scan used:

```bash
rg -n -u -e 'search open-browser --query' -e 'search open_browser --query' -e '--engine' -e '--track-id' -e '--task-id' -e '--artifact-id' -e '--target-type' -e '--target-id' -e 'scripts/env/client.py' tmp/buddyswitch-real-startup-skill-inventory.html buddyswitch/skills tools/launcher/assets/buddies tests scripts/env/client.py
```

Active AGENTS drift:

| File | Current old text | Replacement |
| --- | --- | --- |
| `tools/launcher/assets/buddies/market/AGENTS.md:16` | `python3 scripts/env/client.py track open --track-id <track-id>` | `python3 scripts/env/client.py track open --payload '{"track_id":"<track-id>"}'` |
| `tools/launcher/assets/buddies/pm/AGENTS.md:16` | `python3 scripts/env/client.py track open --track-id <track-id>` | `python3 scripts/env/client.py track open --payload '{"track_id":"<track-id>"}'` |
| `tools/launcher/assets/buddies/design/AGENTS.md:16` | `python3 scripts/env/client.py track open --track-id <track-id>` | `python3 scripts/env/client.py track open --payload '{"track_id":"<track-id>"}'` |
| `tools/launcher/assets/buddies/dev/AGENTS.md:16` | `python3 scripts/env/client.py track open --track-id <track-id>` | `python3 scripts/env/client.py track open --payload '{"track_id":"<track-id>"}'` |
| `tools/launcher/assets/buddies/test/AGENTS.md:16` | `python3 scripts/env/client.py track open --track-id <track-id>` | `python3 scripts/env/client.py track open --payload '{"track_id":"<track-id>"}'` |
| `tools/launcher/assets/buddies/market/AGENTS.md:17` | `python3 scripts/env/client.py task get --task-id <task-id>` | `python3 scripts/env/client.py task get --payload '{"task_id":"<task-id>"}'` |
| `tools/launcher/assets/buddies/pm/AGENTS.md:17` | `python3 scripts/env/client.py task get --task-id <task-id>` | `python3 scripts/env/client.py task get --payload '{"task_id":"<task-id>"}'` |
| `tools/launcher/assets/buddies/design/AGENTS.md:17` | `python3 scripts/env/client.py task get --task-id <task-id>` | `python3 scripts/env/client.py task get --payload '{"task_id":"<task-id>"}'` |
| `tools/launcher/assets/buddies/dev/AGENTS.md:17` | `python3 scripts/env/client.py task get --task-id <task-id>` | `python3 scripts/env/client.py task get --payload '{"task_id":"<task-id>"}'` |
| `tools/launcher/assets/buddies/test/AGENTS.md:17` | `python3 scripts/env/client.py task get --task-id <task-id>` | `python3 scripts/env/client.py task get --payload '{"task_id":"<task-id>"}'` |
| `tools/launcher/assets/buddies/market/AGENTS.md:18` | `python3 scripts/env/client.py artifact get --artifact-id <artifact-id>` | `python3 scripts/env/client.py artifact get --payload '{"artifact_id":"<artifact-id>"}'` |
| `tools/launcher/assets/buddies/pm/AGENTS.md:18` | `python3 scripts/env/client.py artifact get --artifact-id <artifact-id>` | `python3 scripts/env/client.py artifact get --payload '{"artifact_id":"<artifact-id>"}'` |
| `tools/launcher/assets/buddies/design/AGENTS.md:18` | `python3 scripts/env/client.py artifact get --artifact-id <artifact-id>` | `python3 scripts/env/client.py artifact get --payload '{"artifact_id":"<artifact-id>"}'` |
| `tools/launcher/assets/buddies/dev/AGENTS.md:18` | `python3 scripts/env/client.py artifact get --artifact-id <artifact-id>` | `python3 scripts/env/client.py artifact get --payload '{"artifact_id":"<artifact-id>"}'` |
| `tools/launcher/assets/buddies/test/AGENTS.md:18` | `python3 scripts/env/client.py artifact get --artifact-id <artifact-id>` | `python3 scripts/env/client.py artifact get --payload '{"artifact_id":"<artifact-id>"}'` |
| `tools/launcher/assets/buddies/market/AGENTS.md:20` | `python3 scripts/env/client.py search open-browser --query "<query>" --engine google` | `python3 scripts/env/client.py search open-browser --payload '{"query":"<query>","engine":"google"}'` |
| `tools/launcher/assets/buddies/pm/AGENTS.md:20` | `python3 scripts/env/client.py search open-browser --query "<query>" --engine google` | `python3 scripts/env/client.py search open-browser --payload '{"query":"<query>","engine":"google"}'` |
| `tools/launcher/assets/buddies/design/AGENTS.md:20` | `python3 scripts/env/client.py search open-browser --query "<query>" --engine google` | `python3 scripts/env/client.py search open-browser --payload '{"query":"<query>","engine":"google"}'` |
| `tools/launcher/assets/buddies/dev/AGENTS.md:20` | `python3 scripts/env/client.py search open-browser --query "<query>" --engine google` | `python3 scripts/env/client.py search open-browser --payload '{"query":"<query>","engine":"google"}'` |
| `tools/launcher/assets/buddies/test/AGENTS.md:20` | `python3 scripts/env/client.py search open-browser --query "<query>" --engine google` | `python3 scripts/env/client.py search open-browser --payload '{"query":"<query>","engine":"google"}'` |

Active market skill drift:

| File | Current old text | Replacement |
| --- | --- | --- |
| `buddyswitch/skills/market/research-scan/SKILL.md:9` | `python3 scripts/env/client.py search open-browser --query "<initial query>" --engine <google|reddit|x|web>` | `python3 scripts/env/client.py search open-browser --payload '{"query":"<initial query>","engine":"google"}'` |
| `buddyswitch/skills/market/pmf-recon/SKILL.md:9` | `python3 scripts/env/client.py search open-browser --query "<initial query>" --engine <google|reddit|x|web>` | `python3 scripts/env/client.py search open-browser --payload '{"query":"<initial query>","engine":"google"}'` |
| `buddyswitch/skills/market/customer-discovery/SKILL.md:9` | `python3 scripts/env/client.py search open-browser --query "<initial query>" --engine <google|reddit|x|web>` | `python3 scripts/env/client.py search open-browser --payload '{"query":"<initial query>","engine":"google"}'` |
| `buddyswitch/skills/market/channel-discovery/SKILL.md:9` | `python3 scripts/env/client.py search open-browser --query "<initial query>" --engine <google|reddit|x|web>` | `python3 scripts/env/client.py search open-browser --payload '{"query":"<initial query>","engine":"google"}'` |
| `buddyswitch/skills/market/positioning-copy/SKILL.md:9` | `python3 scripts/env/client.py search open-browser --query "<initial query>" --engine <google|reddit|x|web>` | `python3 scripts/env/client.py search open-browser --payload '{"query":"<initial query>","engine":"google"}'` |
| `buddyswitch/skills/market/launch-prep/SKILL.md:9` | `python3 scripts/env/client.py search open-browser --query "<initial query>" --engine <google|reddit|x|web>` | `python3 scripts/env/client.py search open-browser --payload '{"query":"<initial query>","engine":"google"}'` |

Active shared skill drift:

| File | Current old text | Replacement |
| --- | --- | --- |
| `buddyswitch/skills/shared/comment-tool/SKILL.md:47` | `python3 scripts/env/client.py comment list --target-type track --target-id <track_id>` | `python3 scripts/env/client.py comment list --payload '{"target_type":"track","target_id":"<track_id>"}'` |

Test drift:

| File | Current old text | Replacement |
| --- | --- | --- |
| `tests/test_repo_consistency.py:153` | `self.assertIn("track open --track-id", text)` | Assert canonical payload form for `track open` and forbid all old per-field flags. |
| `tests/test_repo_consistency.py:154` | `self.assertNotIn("track get --track-id", text)` | Replace narrow old-action check with a full forbidden old flag scan. |

Generated inventory note:

- `tmp/buddyswitch-real-startup-skill-inventory.html` mentions `env search open-browser` as a generated artifact but does not include the old per-field flags in active runtime guidance. It should be referenced as context only and not used as a source for new CLI examples.

CLI alias note:

- `scripts/env/client.py` currently registers underscore action aliases with `aliases = [action] if cli_action != action else []`.
- To satisfy the no alias/no dual path rule, implementation must remove those aliases so active CLI examples and parser behavior converge on one CLI spelling.
- Resolution for notation conflict: runtime `tool.action` ids remain underscore ids such as `search.open_browser`; user-facing CLI subcommands remain the current hyphenated argparse spelling such as `search open-browser`; underscore CLI subcommands such as `search open_browser` are removed.
- This follows the current implementation's user-facing CLI shape while eliminating the extra invocation path.
- This is a single-file serial CLI cleanup owned by the integrator, not by I1-I5.

Broker action alias note:

- `scripts/env/tool_runtime/registry.py` currently normalizes broker payload actions with `raw_action.strip().replace("-", "_")`.
- Remove that normalization so direct `env.tool` payloads must use canonical underscore action ids from the registry, such as `"open_browser"`.
- The CLI may continue translating its single hyphenated subcommand into the canonical underscore action id internally.
- This belongs to the shared serial registry seed, not I4 guidance cleanup.

## Replacement Strategy

Launcher AGENTS:

- Keep AGENTS short.
- Keep `context summarize` and `context get` startup guidance, but use payload form:
  - `python3 scripts/env/client.py context summarize --payload '{}'`
  - `python3 scripts/env/client.py context get --payload '{}'`
- Replace id examples with payload form:
  - `python3 scripts/env/client.py track open --payload '{"track_id":"<track-id>"}'`
  - `python3 scripts/env/client.py task get --payload '{"task_id":"<task-id>"}'`
  - `python3 scripts/env/client.py artifact get --payload '{"artifact_id":"<artifact-id>"}'`
- Replace browser examples with:
  - `python3 scripts/env/client.py search status --payload '{}'`
  - `python3 scripts/env/client.py search open-browser --payload '{"query":"<query>","engine":"google"}'`
- Keep the browser policy: after `search.open_browser`, continue in `chrome-devtools-cockpit`.

Market skills:

- Replace the old line 9 command in all six active market skills with payload form.
- Keep browser-native evidence guidance.
- Do not duplicate the full `engine` enum list in prose; route exact options to runtime discovery.
- Do not add crawler/snippet fallback guidance.

Shared tool skills:

- Keep minimal workflow guidance.
- Keep runtime discovery references such as `context.get.tool_catalog['comment']` and `python3 scripts/turn_runtime.py status`.
- Replace old verification examples with payload-form commands.
- Remove generic `python3 scripts/env/client.py <tool> --help` and no-payload action examples from active skill guidance when they are presented as execution paths.
- Do not copy payload schema tables into the skill.

Tests:

- Change tests from protecting old flags to rejecting them.
- Require payload-form examples in active AGENTS and active skills.
- Keep schema and response details protected by runtime/tool tests, not Markdown prose.

## Launcher AGENTS And Skills Boundary

AGENTS may say:

- Start with compact context:
  - `python3 scripts/env/client.py context summarize --payload '{}'`
- Use full context or status when exact tool selection is unclear:
  - `python3 scripts/env/client.py context get --payload '{}'`
  - `python3 scripts/turn_runtime.py status`
- Use `--payload` JSON for env client action calls.
- Browser discovery starts with `search.open_browser`, then uses `chrome-devtools-cockpit`.

AGENTS must not say:

- Per-action payload schemas or return schemas.
- Private buddybox filesystem paths.
- Old per-field flags or deprecated examples.
- A phrase-to-tool routing table.

Skills may say:

- When a repeated workflow needs browser-native research, artifact publication, comments, or messages.
- Check runtime response fields such as `state_changed`, `durability`, `allowed_next_actions`, `why_blocked`, and `field_errors`.
- Use runtime discovery for exact action, payload, return, and recovery details.

Skills must not say:

- Full runtime schema mirrors.
- Object storage paths.
- Old env client flags.
- Compatibility routes or fallback CLI paths.

## Guardrail Changes

`tests/test_repo_consistency.py`:

- Replace `test_runtime_buddy_agents_use_track_open_guidance` with a payload-form AGENTS guidance test:
  - Requires `track open --payload '{"track_id":"<track-id>"}'`.
  - Requires `task get --payload '{"task_id":"<task-id>"}'`.
  - Requires `artifact get --payload '{"artifact_id":"<artifact-id>"}'`.
  - Requires `search open-browser --payload '{"query":"<query>","engine":"google"}'`.
  - Requires `context summarize --payload '{}'`.
  - Requires `context get --payload '{}'`.
- Add `test_active_cli_guidance_has_no_old_env_client_flags` scanning:
  - `buddyswitch/skills`
  - `tools/launcher/assets/buddies`
  - `scripts/env/client.py`
- Forbidden patterns:
  - `search open-browser --query`
  - `search open_browser --query`
  - `--query`
  - `--engine`
  - `--track-id`
  - `--task-id`
  - `--artifact-id`
  - `--target-type`
  - `--target-id`
- Add parser-level tests that these old invocations fail:
  - `python3 scripts/env/client.py search open-browser --query x --engine google`
  - `python3 scripts/env/client.py track open --track-id track-alpha`
  - `python3 scripts/env/client.py task get --task-id task-alpha`
  - `python3 scripts/env/client.py artifact get --artifact-id art-alpha`
  - `python3 scripts/env/client.py comment list --target-type track --target-id track-alpha`
- If underscore action alias removal is included in the same implementation, assert `python3 scripts/env/client.py search open_browser --payload '{"query":"x"}'` fails.

`tests/test_runtime_skills.py`:

- Add `test_active_skills_do_not_teach_old_env_client_flags`.
- Scan manifest-listed active `SKILL.md` files.
- Require market skills to include `search open-browser --payload` and `chrome-devtools-cockpit`.
- Forbid old search flags in all active market skills.
- Strengthen shared tool skill command examples so every `python3 scripts/env/client.py <tool> <action>` command includes `--payload`.

## Runtime Contract Cleanup

Serial CLI cleanup:

- Modify `scripts/env/client.py` to remove underscore action aliases:

Current:

```python
aliases = [action] if cli_action != action else []
action_parser = tool_sub.add_parser(cli_action, aliases=aliases, help=f"{tool}.{action}")
```

Target:

```python
action_parser = tool_sub.add_parser(cli_action, help=f"{tool}.{action}")
```

Expected effect:

- Hyphenated CLI action names remain the one CLI spelling.
- Runtime catalog still exposes canonical action ids with underscores in `tool.action` strings.
- Direct `env.tool` broker payloads accept only underscore action ids and do not normalize hyphen aliases.
- No old alias path remains for guidance to drift back toward.
- Do not rewrite all CLI examples to underscore action names; that would expand the task beyond stale flag drift and contradict the current argparse primary spelling.

## Completion Standards

- `rg -n -u -e 'search open-browser --query' -e 'search open_browser --query' -e '--engine' -e '--track-id' -e '--task-id' -e '--artifact-id' -e '--target-type' -e '--target-id' buddyswitch/skills tools/launcher/assets/buddies tests/test_repo_consistency.py tests/test_runtime_skills.py scripts/env/client.py` returns no active old guidance hits except forbidden-pattern definitions inside guardrail tests.
- Tests no longer assert `track open --track-id`.
- Active skills and AGENTS use payload-form examples or runtime discovery references.
- Market/browser guidance states `search.open_browser --payload ...` then `chrome-devtools-cockpit`.
- Old flag invocation failures are treated as correct parser behavior, not compatibility requirements.

## Disjoint Write Scope For Implementation

Serial seed by integrator:

- `scripts/env/client.py` only, to remove underscore action aliases if this cleanup is executed with the drift fix.

I4:

- `buddyswitch/skills/**/*.md`
- `tools/launcher/assets/buddies/*/AGENTS.md`

I5:

- `tests/test_runtime_skills.py`
- `tests/test_repo_consistency.py`

R2:

- Review only. Check no old flags, no deprecated examples, no dual-path guidance, no schema mirror, and no browser-policy regression.
