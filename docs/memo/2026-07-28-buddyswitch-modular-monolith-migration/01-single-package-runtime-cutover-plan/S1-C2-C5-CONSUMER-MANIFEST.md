# S1 C2–C5 Atomic Cutover Consumer and Scope Manifest

> Status: FROZEN
> Source: `S1-C2-C5-SOURCE-SNAPSHOT.md`
> Boundary decision: D-038

## 1. One replacement unit

The following four technical work groups are one runtime truth:

```text
223 direct moves + 5 deletes
  -> installed package imports/resources
    -> every public and child process uses verified package modules
      -> Actor workspace contains projections but no implementation
        -> complete lifecycle remains observable and clean
```

There is no accepted state between these arrows. No old-path copy, alias,
fallback, temporary loader or broken public path may be retained.

## 2. Exact source/resource disposition

The 228 tracked inputs and deterministic targets are owned by
`02-source-and-asset-move-map.md` plus these frozen clarifications:

- `tools/__init__.py` is deleted;
- `src/buddyswitch/catalog/__init__.py`,
  `config/__init__.py`, `contracts/__init__.py`,
  `runtime_support/__init__.py` and `skills/__init__.py` are created as the
  package owners for moved code/data;
- `pyproject.toml` adds only `assets/**/LICENSE*` to launcher package data;
- all four current third-party `LICENSE*` resources must ship;
- `scripts/output_schema.py` moves to `tests/support/output_schema.py` and
  never ships.

## 3. Exact package entrypoint allowlist

`runtime_activation` already exists. The cutover creates these additional thin
modules under `src/buddyswitch/application/entrypoints/`:

| Module | Current owner called after verification |
|---|---|
| `cli` | `buddyswitch.launcher.cli.main` |
| `web` | `buddyswitch.launcher.web_management.main` |
| `central_daemon` | `buddyswitch.launcher.central_daemon.main` |
| `instance_daemon` | `buddyswitch.launcher.instance_daemon.main` |
| `runtime_broker` | `buddyswitch.runtime_kernel.broker.main` |
| `env_mcp` | `buddyswitch.launcher.env_tool_mcp_server.main` |
| `app_server` | `buddyswitch.launcher.app_server.main` |
| `actor_build` | `buddyswitch.launcher.actor_environment.main` |
| `browser_runtime` | `buddyswitch.launcher.browser_runtime_manager.main` |
| `browser_cockpit_proxy` | `buddyswitch.launcher.chrome_devtools_cockpit_proxy.main` |
| `cleanup` | `buddyswitch.runtime_support.env_cleanup.main` |
| `diagnostics` | `buddyswitch.runtime_support.turn_runtime.main` |
| `browser_evidence` | `buddyswitch.runtime_support.browser_evidence.main` |
| `artifact_selection` | `buddyswitch.runtime_support.artifact_selection.main` |

One helper below `buddyswitch.foundation.process_runtime` calls the existing
activation `verify()` owner and maps its stable error/exit contract before
invoking an owner. It is not a second runtime manager.

Every production Python child command is:

```text
<verified sys.executable> -m <one allowlisted package entrypoint> ...
```

No production child command executes a checkout `.py`, accepts `--repo-root`
for code loading, imports with `spec_from_file_location`, or receives a source
`PYTHONPATH`.

## 4. Public root interfaces

Only these root interfaces remain:

```text
buddyswitch-codex
buddyswitch-test
```

Both resolve either the absolute `BUDDYSWITCH_RUNTIME_DIR` or the checkout
`.buddyswitch-runtime`, require `activation.json` and
`venv/bin/python`, and never source `tools/launcher/env.sh`.

- `buddyswitch-codex` executes
  `-m buddyswitch.application.entrypoints.cli`.
- `buddyswitch-test` executes root `tests/runner.py` with the same interpreter;
  the runner calls installed activation `verify()` before test discovery and
  clears source `PYTHONPATH`.

Shell does not parse activation JSON or fall back to `PATH` Python.

## 5. Current child-process consumers

The packet owns all launch construction in:

```text
buddyswitch.launcher.cli
buddyswitch.launcher.host_control
buddyswitch.launcher.app_server
buddyswitch.launcher.central_daemon
buddyswitch.launcher.daemon_core
buddyswitch.launcher.web_management
buddyswitch.launcher.browser_runtime_manager
buddyswitch.launcher.chrome_devtools_cockpit_proxy
buddyswitch.runtime_kernel.lifecycle
buddyswitch.runtime_kernel.dispatcher
packaged launcher shell helpers
root test fakes/support
```

The source root recorded by activation may be used only to locate the
external `projects/app` seed and to verify source/distribution identity. It
must not select implementation, manifests, profiles, contracts, Skills or
entrypoints. Production `BUDDYSWITCH_REPO_ROOT` and `--repo-root` code-loading
contracts are removed, not aliased.

## 6. Actor projection contract

Actor build receives explicit shared/instance/project locators, Actor/Role
identity, source auth input and verified runtime identity. Package resources
provide Role/Skill/catalog inputs. The published allowlist is:

```text
instance.json
workspace/AGENTS.md
workspace/.agents/skills/<selected>/**
workspace/private/**
workspace/projects/app -> shared project
home/**
codex-home/config.toml
xdg-config/**
tmp/**
runtime/**
browser/**
```

Forbidden output:

```text
workspace/scripts
workspace/tools
workspace/framework
workspace/src
workspace/tests
workspace/docs
workspace/buddyswitch/manifest.toml
all Roles
unselected Skills
```

`repo_root` and `RUNTIME_COPY_PATHS` disappear. Env MCP, diagnostics, Broker,
Browser and App processes run from the installed distribution, not the Actor
workspace.

## 7. Writable scope

| Class | Exact writable path |
|---|---|
| package/build owner | `pyproject.toml` |
| moved implementation/assets | the exact 228-path source set and deterministic targets in `02-source-and-asset-move-map.md` |
| package/runtime additions | `src/buddyswitch/**` only for the package owners, verification helper and entrypoint allowlist named above |
| public interfaces | `buddyswitch-codex`, `buddyswitch-test` |
| behavior-preserving proof | `tests/runner.py`, `tests/support/**`, `tests/unit/**`, `tests/integration/**`, `tests/process/**`, `tests/system/**` |
| executor state | `S1-C2-C5-EXECUTION-STATE.md` only |
| generated runtime | `.buddyswitch-runtime/**` only for explicit rebuild/install/activate; never stage |

Every test change must be required by namespace, resource, entrypoint,
workspace or runtime-identity replacement. Unrelated test cleanup is
forbidden.

## 8. Preserved dirty work and forbidden scope

Preserve without editing:

```text
.gitignore
requirements-test.txt
all docs/memo/** except S1-C2-C5-EXECUTION-STATE.md
```

Forbidden:

```text
AGENTS.md
README.md
docs/arch/**
docs/bitter/**
docs/team_diary/**
projects/app/**
canonical user/state data
git index, commit, branch or worktree configuration
S2+ product component boundaries
```

Root/current architecture guidance and final residue closure belong to C6.
Packaged Role/Skill guidance is not deferred when it is needed for a runnable
Actor and therefore is changed as part of the moved resource itself.

## 9. Stop-on-discovery rule

Stop and return if:

- any production consumer outside this manifest requires a write;
- a sixteenth product process entrypoint is required;
- a moved source path has no deterministic target or collides;
- Actor behavior requires copied implementation;
- canonical data must move or be dual-written;
- current public command, Tool schema/authority or lifecycle semantics must
  change;
- compatibility or source fallback appears necessary.
