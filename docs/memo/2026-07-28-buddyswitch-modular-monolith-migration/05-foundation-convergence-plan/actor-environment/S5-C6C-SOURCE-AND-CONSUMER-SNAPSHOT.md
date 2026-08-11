# S5 C6C Source and Consumer Snapshot

> Source HEAD: `5499aab2341d0aee83e7cbc696fd7b5e3adead79`
> Worktree/index/untracked state: clean
> Snapshot manifest: `df1c9cda8b7bf9fe8c90302adbd9735afe8878d5b402191ba3cb07c4e515d923`

## Current owner

`src/buddyswitch/launcher/actor_environment.py` currently combines two change
reasons:

1. product-neutral publication mechanics: runtime identity validation, shared
   Git-free project seed, atomic Actor staging/publication, auth projection,
   directory and symlink guards, exact workspace allowlist, validation and
   failed-stage cleanup;
2. current Role-bound input resolution: central manifest lookup, Launcher Role
   `AGENTS.md` path selection, selected Skill source resolution and default
   Skill enablement.

The first reason is C6C Foundation ownership. The second is current S6 input
and must stay outside Foundation until RoleHost replaces it. Moving the file
unchanged would create a forbidden Foundation dependency on concrete Role and
`runtime_support` policy.

## Consumer path

```text
Host Control shell start
  -> stable application.entrypoints.actor_build
  -> current application activation + current Role/Skill resolution
  -> Actor Environment publication owner
  -> one code-free Actor workspace or exact failure with no published residue
```

The stable application entrypoint is the only production invocation. Public
CLI and Web do not call the environment builder directly. The shell start path
uses it before launching runtime services and already has one cleanup owner
for failed publication phases.

## Representation classes

The refreshed scan classified:

- direct Python owner/imports and application entrypoint;
- shell-embedded stable entrypoint calls in `env.sh` and `host_control.sh`;
- Role `AGENTS.md` and Skill source resolution used as current inputs;
- unit, Process and System Actor environment/build/config assertions;
- package/distribution resource and removed-path expectations;
- architecture and current-guidance references;
- test support assertions over the published workspace and selected Skills.

Paths in those classes are hypotheses within the semantic authority boundary.
The executor owns newly discovered mechanical consumers and correct current
test targets.

## Preserved behavior

- Actor ID, Role ID and activated-runtime validation;
- shared project seed and Git-free copy semantics;
- atomic no-overwrite publication and concurrent-appearance failure;
- exact Actor directory layout and private/project projections;
- selected `AGENTS.md` and Skill materialization only;
- base Codex config and disabled-Skill behavior;
- shared auth projection;
- path, symlink, boundary and forbidden-entry rejection;
- result JSON/error/exit behavior at the stable application entrypoint;
- failed-stage cleanup and code-free runtime attribution.

## Baseline evidence

| Claim | Run | Result |
|---|---|---|
| direct Actor build/config/process behavior | `7e3800b10a9e4dbaa69c019ad52eb9c0` | 24 passed, 7 subtests |
| private Host Control build boundary | `f70f9357f31c4507863974942352895b` | 1 passed, 4 subtests |
| consumer-observed code-free attributed Actor | `d743845fca5847a7822f10c293cb5961` | 1 System test passed |
| source-equivalent broad baseline | C6B FINAL `7678be695ad14ba1b3cfdf2780a9670a` | all tiers passed |

One attempted System node used a guessed class name and collected no tests
(`2ce33489466e4fb5bc33160914373e39`). It changed no source or product state;
the class was read from current source and the valid target then passed. This
is recorded as target-discovery evidence, not a product failure.

Runtime verification is `ok=true`: source digest `4b93731c...`, distribution
digest `55fce04f...`, package version `0.1.0`.
