# S5 C6F Source and Consumer Snapshot

> Source/upstream: `01335be4232d9f7d96a099f22920d679b77a03fc`
> Worktree/index/untracked: clean / empty / none
> Runtime: source `f7a7b8d0…`, distribution `b78b994e…`, `ok=true`
> Captured: 2026-08-12

## Bottleneck

After C6E, the remaining executable Launcher cluster is:

```text
launcher/cli.py
launcher/codex_config.py
launcher/shell/env.sh
launcher/shell/cleanup.sh
launcher/shell/browser_cockpit.sh
```

It contains 3,020 lines and changes as one live public path: CLI dispatch
constructs and sources the shell adapters; Host Control start configuration
also sources environment and Browser adapters; Codex config is invoked through
the Application Actor-build entrypoint. Moving only one file would leave a
Foundation-to-Launcher dependency or require a temporary alias/fallback.

The ordered `path + NUL + sha256(content) + LF` owner manifest is:

```text
5064dadaa5a13a517614b2c7f72ac2d4a670ac88c98ff11aa9b0a028befd6fc5
```

## Current responsibility classes

- `cli.py`: public command parsing, help, exact success/failure projection,
  Host Control and Actor Session invocation, Web launch, shell execution and
  error mapping;
- `codex_config.py`: deterministic Codex permission/config projection and
  profile-mode filesystem boundary calculation;
- `env.sh`: shared/Actor environment, config and MCP orchestration plus Codex
  invocation policy;
- `cleanup.sh`: destructive cleanup parsing, active-resource guard and
  Application cleanup invocation;
- `browser_cockpit.sh`: Browser CLI adapter, MCP projection and public shell
  orchestration over the accepted Browser owner.

## Upward executable facts

The current cluster embeds concrete Application or Role-support knowledge in
every representation class:

- CLI launches the concrete Web Application module;
- config imports the current Role-profile implementation;
- shell invokes Actor-build, Browser Runtime, env MCP, Browser proxy, cleanup
  and diagnostics Application modules;
- Browser shell imports Application/Role profile code in an embedded Python
  block;
- environment shell names the current Launcher Role asset tree.

These are real executable dependencies, not harmless strings. C6F may move the
cluster only if Application supplies the exact current facts and Foundation
contains none of those roots afterward.

## Live consumer classes

Twenty-two direct import/path/content representation files were captured with
ordered content manifest:

```text
e0f623a9c61736641746373bdd220b81e1e587ee87cc979f280292c3600f3e91
```

They include Application build/CLI/Actor-build/Host-start assembly, Host
Control startup, package projection, public CLI/config/Browser/environment/
cleanup process tests, runtime integration and owner/architecture proofs.
This is a source-refresh identity, not an executor path ceiling. The executor
must rediscover every current import, path, package and shell representation.

## Zero-production-consumer residue

Current-source call tracing found eight shell helpers with no production
consumer:

```text
buddyswitch_browser_create_blank_page
buddyswitch_browser_instance_endpoint_is_owned_active
buddyswitch_browser_prepare_instance_ensure_port
buddyswitch_browser_validate_env_or_default_port
buddyswitch_cleanup_requests_execute
buddyswitch_cleanup_trim_state_skeleton
buddyswitch_require_env_profile
buddyswitch_require_role_agents_template
```

Tests do not earn these surfaces. They must not migrate unless the executor
finds a current production consumer missed by this snapshot and reports it as
a replan discovery.

## Protected observable path

```text
./buddyswitch-codex
  -> verified Application CLI entrypoint
    -> generic CLI Runtime
      -> injected Host Control + component command registrations
      -> injected Application executable/manifest/Profile facts
      -> generic shell/config adapters
        -> accepted Foundation/Application owners
          -> exact JSON/exit/resource result
```

Protected behavior includes every current public command/help/envelope/exit
contract, destructive confirmation and lock behavior, Browser status/ensure/
release, Web launch and signal behavior, config idempotence and filesystem
safety, Host Control start configuration, MCP registration, shell quoting and
all resource cleanup effects.

## S6 boundary

`launcher/assets/roles/**` remains the current S6-owned Role input. C6F may
pass its current location from Application where a live behavior still needs
it, but may not move, reinterpret or discover Role packages. After C6F,
Launcher may remain only as an inert package root plus those Role assets until
S6 replaces them.
