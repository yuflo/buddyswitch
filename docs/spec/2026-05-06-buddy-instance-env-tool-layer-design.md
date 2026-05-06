# Buddy Instance Env Tool Layer Design

Status: revised design for review
Date: 2026-05-06
Worktree: dev0210
Supersedes: `docs/spec/2026-05-06-buddy-instance-env-profile-design.md`

## Target

Build BuddySwitch's first real buddy instance environment layer.

This is not a PM/Market prompt fix. The two investigation memos under
`docs/memo/2026-05-06-*` are incident records that exposed the same root
problem: buddy instances currently differ mostly by guidance, while the runtime
environment remains too similar.

A buddy env must be an executed boundary, not just written instructions. The
host LLM / Codex CLI should experience permissions through tool-layer feedback:
write denial, unavailable tools, explicit approval gates, and persist rejection.

## Core Decision

Implement buddy env as profile-compiled runtime capabilities.

```text
buddyswitch/env-profiles/<buddy>.json
-> launcher assembly in tools/launcher/**
-> host-facing runtime tools in scripts/**
-> Codex sandbox, runtime state broker, browser evidence gate
-> runtime AGENTS.md as context projection only
```

`AGENTS.md` explains the environment. It is not the permission source.

## Current Code Facts

- `scripts/turn_runtime.py prepare/persist` is already the product runtime
  boundary documented in `framework/docs/turn-runtime-spec.md`.
- `scripts/runtime_kernel/*` exists, but currently only wraps
  `turn_runtime.py`; it is the natural place to grow runtime tool internals.
- `scripts/runtime_store/*` and `env_store.py` contain state repository access.
- `tools/launcher/codex_config.py` currently patches Codex sandbox
  `writable_roots`.
- `tools/launcher/browser_cockpit.sh` currently starts the headed browser and
  registers `chrome-devtools-cockpit`.
- `tools/launcher/**` are launcher/operator commands. They assemble instances;
  they are not the host runtime tool layer.
- `scripts/env_tracks.py` and `scripts/env_artifacts.py` enforce permissions for
  manual/debug APIs. They should not become the product runtime permission path.

## Directory Responsibility

Use this boundary:

- `scripts/**`: host-facing BuddySwitch runtime tools and runtime tool
  internals.
- `tools/launcher/**`: instance lifecycle, workspace projection, Codex config,
  browser bootstrap, cleanup, reset.
- `framework/contracts/**`: JSON contracts and human role contracts.
- `buddyswitch/env-profiles/**`: machine-readable env profiles.

Do not build a new parallel permission system under `tools/launcher`. Launcher
uses profiles to assemble the environment; runtime permission feedback comes
from `scripts/**` tools and Codex tool execution.

## Env Definition

A buddy instance env has five parts:

1. Identity: active buddy, instance id, current task/track binding.
2. Context: runtime `AGENTS.md`, active buddy skills, prepared state context,
   and live `projects/app` visibility.
3. Filesystem capability: which resolved paths host tools may write.
4. Tool capability: which external execution surfaces are required, available,
   unavailable, or approval-gated.
5. State capability: which BuddySwitch state changes are accepted by the
   controlled runtime commit tool.

The first implementation must cover all five buddies together: `market`, `pm`,
`design`, `dev`, and `test`.

## Profile Source

Create one profile per manifest buddy:

```text
buddyswitch/env-profiles/market.json
buddyswitch/env-profiles/pm.json
buddyswitch/env-profiles/design.json
buddyswitch/env-profiles/dev.json
buddyswitch/env-profiles/test.json
```

Add a compact schema contract:

```text
framework/contracts/buddy-env-profile.json
```

Keep the schema fixed and small. This is not a generic permission DSL.

Required top-level profile keys:

- `buddy_id`
- `contract_path`
- `project`
- `scratch`
- `filesystem_capability`
- `state_capability`
- `tool_capability`
- `context_projection`

Allowed enum values:

- `project.visibility`: `live`
- `project.access`: `read-only | write`
- `tool_capability.browser_cockpit`: `required | available | unavailable`
- `tool_capability.market_research_evidence`: `required | not-required`
- `tool_capability.ordinary_web_fallback`: `available | user-approved-only`
- `state_capability.artifact_kinds`: `from-manifest`
- `context_projection.agents_md`: `from-profile-and-contract`
- `context_projection.skills`: `active-buddy-only`

## Capability Ports

### 1. Filesystem Capability

Implemented by launcher-generated Codex sandbox config.

`tools/launcher/codex_config.py` must stop granting blanket writable roots:

- no `${BUDDYSWITCH_SHARED_ROOT}`;
- no whole instance root;
- no `${BUDDYSWITCH_SHARED_ROOT}/project`;
- no `${BUDDYSWITCH_SHARED_ROOT}/project/workspace` except for Dev;
- no raw shared state root for the host.

Common host writable roots:

- instance `home`;
- instance `codex-home`;
- instance `xdg-config`;
- buddy scratch root under runtime workspace, for example `runs/raw/<buddy>/`;
- safe temp roots such as `/tmp` and `$TMPDIR`;
- git common dir only if tests prove it is required and it does not grant source
  or state writes.

Dev-only host writable root:

- `${BUDDYSWITCH_SHARED_ROOT}/project/workspace`

All buddies see live `projects/app`. Only Dev can write it. Market, PM, Design,
and Test must receive a filesystem tool failure if they try to write through:

- `workspace/projects/app/...`;
- the resolved symlink target under project workspace.

### 2. State Commit Capability

Implemented as a controlled runtime tool in `scripts/**`.

The host must not receive raw write access to:

- `${BUDDYSWITCH_SHARED_ROOT}/state`;
- `buddyswitch/objects/**`;
- `buddyswitch/content/runs/**`.

`prepare` and `persist` both belong to this capability because both may create
or mutate canonical BuddySwitch state.

Product mode must route state mutation through a controlled runtime broker/tool:

```text
host Codex CLI
-> scripts/turn_runtime.py prepare|persist
-> scripts runtime tool client
-> launcher-managed runtime broker
-> scripts/runtime_kernel/**
-> canonical state write
```

The broker has state write capability. The host process does not.

The CLI surface can remain:

```bash
python3 scripts/turn_runtime.py prepare "<ordinary request>"
python3 scripts/turn_runtime.py persist --context <context> --result <result>
```

But in product mode those commands must behave as clients of the controlled
runtime tool, not as arbitrary sandbox-local file writers.

The broker must enforce:

- active instance identity;
- active buddy identity;
- prepared context/run-envelope integrity;
- env profile state capability;
- manifest artifact kinds;
- manifest/profile state-effect permissions;
- handoff target validity.

Tool feedback must be explicit:

- invalid profile: launch or tool failure;
- unauthorized artifact kind: persist rejected;
- unauthorized track lifecycle mutation: persist rejected;
- stale or mismatched context: persist rejected;
- missing required Market evidence: persist rejected.

There must be no second product-mode path that writes state directly.

### 3. Browser Evidence Capability

Implemented through the existing browser cockpit plus runtime evidence checks.

Market research requires a browser-native evidence signal. Prompt wording alone
is not sufficient.

First version enforcement:

- launcher still starts the headed instance browser and registers
  `chrome-devtools-cockpit`;
- Market profile sets `browser_cockpit = required`;
- Market profile sets `market_research_evidence = required`;
- Market profile sets `ordinary_web_fallback = user-approved-only`;
- runtime state commit rejects Market research artifacts unless the result
  includes either:
  - browser-native evidence proof from the runtime tool layer; or
  - an explicit user-approved downgrade record.

The first proof may be minimal: a browser-cockpit preflight or evidence token
issued by a `scripts/**` runtime tool for the current run envelope. It does not
need to be a full browser trace system in this step.

If future acceptance proves preflight tokens are too weak, add cockpit
navigation trace capture. Do not build full trace capture before that evidence
exists.

### 4. Command Execution Capability

Do not create a separate command permission system in the first step.

Dev and Test may run shell commands through the host, but filesystem capability
controls where command outputs can land.

- Dev can write source and report implementation.
- Test can run checks but can write only scratch/temp/test-report state through
  controlled persist.
- Test cannot edit source, test files, fixtures, snapshots, or generated source
  artifacts under `projects/app`.

## Buddy Matrix

| Buddy | `projects/app` | Scratch root | State capability | Tool capability |
|---|---|---|---|---|
| `market` | live read-only | `runs/raw/market/` | market artifact kinds from manifest, current task summary/status, handoff; no track lifecycle | browser cockpit required; browser evidence required; ordinary fallback user-approved only |
| `pm` | live read-only | `runs/raw/pm/` | PM artifact kinds from manifest, current task summary/status, track lifecycle, handoff | browser available, not required |
| `design` | live read-only | `runs/raw/design/` | design artifact kinds from manifest, current task summary/status, handoff; no track lifecycle | browser available, not required |
| `dev` | live write | `runs/raw/dev/` | dev artifact kinds from manifest, current task summary/status, handoff; no track lifecycle | browser available, not required |
| `test` | live read-only | `runs/raw/test/` | test artifact kinds from manifest, current task summary/status, handoff; no track lifecycle | browser available, not required |

PM is the only buddy with track lifecycle authority:

- `track.create`
- `track.update`
- `track.advance`
- `track.archive`

All task state effects are current-task-only:

- `status`
- `summary`

No buddy may mutate arbitrary task ids through runtime persist.

## Runtime Context Projection

Runtime `AGENTS.md` is generated or validated from:

- env profile;
- `framework/contracts/<buddy>.md`;
- active buddy id;
- canonical runtime loop.

It must explain:

- live project visibility and write limits;
- allowed scratch/output locations;
- active skills;
- how to call prepare/persist;
- what to do after tool rejection;
- buddy-specific handoff boundaries.

It must not be the only proof of any permission.

## Launcher Assembly

On `instance start --buddy <buddy>` and `instance open <instance-id>`:

1. Validate the buddy in `buddyswitch/manifest.toml`.
2. Load and validate `buddyswitch/env-profiles/<buddy>.json`.
3. Fail if profile is missing, invalid, or mismatched.
4. Ensure live `projects/app` projection.
5. Materialize only active buddy skills.
6. Generate or validate runtime `AGENTS.md` from profile and contract.
7. Patch Codex config from profile-derived filesystem capability.
8. Start or reuse the runtime state broker for the instance.
9. Bootstrap browser cockpit according to profile.
10. Launch Codex from the instance workspace.

`tools/launcher/**` owns this assembly. `scripts/**` owns host-facing runtime
tools and state/tool validation logic.

## Replacement Strategy

Replace the current direct product-mode state write path. Do not preserve it as
a parallel product path.

Allowed during implementation:

- pure runtime kernel functions may stay importable for unit tests;
- manual/debug APIs may remain separate and explicitly marked as non-product;
- CLI names may remain stable if their product-mode behavior routes through the
  controlled runtime tool.

Not allowed:

- host writable raw state root as a convenience fallback;
- old selected-skill persistence owner;
- `persist-skill-result`;
- prompt-only role boundaries;
- per-buddy partial rollout.

## Verification Plan

Profile and schema tests:

- every manifest buddy has exactly one env profile;
- every profile validates against `framework/contracts/buddy-env-profile.json`;
- every profile `buddy_id` matches filename and manifest id;
- every `contract_path` exists;
- every non-dev profile declares `project.access = read-only`;
- Dev declares `project.access = write`;
- every profile has a buddy-specific scratch root.

Filesystem capability tests:

- non-dev generated Codex config excludes shared root, project root, project
  workspace, state root, and whole instance root;
- Dev generated Codex config includes project workspace and still excludes raw
  state root;
- non-dev write probe to `workspace/projects/app/...` fails;
- non-dev write probe to resolved project workspace target fails;
- Dev write probe to `projects/app` succeeds;
- Design write probe to `runs/raw/design/` succeeds;
- Test write probe to `runs/raw/test/` succeeds;
- Test write probe to app test files, fixtures, snapshots, and generated source
  paths under `projects/app` fails.

State capability tests:

- product-mode prepare succeeds through the controlled runtime tool without host
  raw state root write access;
- product-mode persist succeeds through the controlled runtime tool without host
  raw state root write access;
- direct host write probe to state root fails;
- PM track lifecycle persist succeeds for valid actions;
- Market/Design/Dev/Test track lifecycle persist attempts are rejected before
  writes;
- unauthorized artifact kinds are rejected before writes;
- task effects can affect only the current prepared task;
- handoff targets must be manifest buddies.

Market tool capability tests:

- Market profile requires browser cockpit and browser evidence;
- launcher config includes `chrome-devtools-cockpit` for Market;
- Market research persist without browser evidence proof and without approved
  downgrade is rejected;
- Market research persist with explicit approved downgrade records the downgrade
  in artifact content or run audit;
- runtime `AGENTS.md` includes browser-native wording, but that wording is not
  the only verification.

Runtime projection tests:

- runtime `AGENTS.md` for each buddy projects profile boundaries;
- PM, Design, and Test explain source read-only behavior;
- Test explains that source or test fixes are Dev handoffs;
- Dev explains project source write authority and verification reporting;
- Market explains browser-native first execution and downgrade rejection.

## Non-Goals

- No generic permission DSL.
- No workflow engine.
- No multi-owner transaction system.
- No full network firewall in this step.
- No full browser navigation trace system in this step.
- No snapshot copy of `projects/app`.
- No history-compatible selected-skill persist path.
- No broad rewrite of all runtime store code before the state broker boundary is
  needed.

## Open Assumptions And Invalidators

- Assumption: Codex sandbox denies writes based on resolved symlink targets. If
  false, use an OS-level read-only project projection or avoid any writable root
  that can reach the symlink target.
- Assumption: product-mode `prepare/persist` can route through a local
  launcher-managed broker while keeping the same host-facing CLI shape. If
  false, expose a different `scripts/**` host-facing runtime tool and remove the
  old CLI from product prompts.
- Assumption: Market browser preflight/evidence token is enough for the first
  validated loop. If product acceptance still shows silent downgrade, add
  browser navigation trace capture.
- Assumption: git common dir write is not required for non-dev host work. If
  required, add only the minimal git path and prove it cannot write source or
  state.

## Stop Condition

This first env step is complete when:

- all five buddies launch from env profiles;
- host filesystem writes are profile-bounded;
- non-dev buddies cannot write project source or raw state;
- Dev remains the only project source writer;
- `prepare` and `persist` succeed through controlled runtime tools;
- state authority is enforced by runtime tool rejection, not raw file access;
- Market research persist requires browser evidence or explicit approved
  downgrade;
- runtime `AGENTS.md` is only a context projection;
- tests prove the properties above.
