# S1.4 Actor Workspace Projection

## Outcome

> Actor publication stages and atomically publishes only selected
> Role/Skill/config/private/project content; BuddySwitch implementation,
> tests/docs, all Roles and unselected Skills are impossible in the workspace.

## Builder inputs

Replace checkout `repo_root`/`RUNTIME_COPY_PATHS` with:

- explicit shared/instance/project locator values;
- installed package resource access;
- Actor ID and Role ID;
- source Codex home/auth input;
- current catalog/Role selection service;
- installed runtime identity.

## Final S1 Actor allowlist

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

Role contracts, result schemas, central manifest and profiles remain installed
package resources used by the owning runtime. They are not copied into the
Actor workspace. The Actor sees only its generated `AGENTS.md`, selected Skill
artifacts and generated MCP configuration.

## Forbidden

```text
workspace/scripts
workspace/tools
workspace/framework
workspace/src
workspace/tests
workspace/docs
workspace/buddyswitch/manifest.toml
workspace/all roles
workspace/unselected skills
```

## Shared project

Preserve:

- source `projects/app` seed;
- shared project workspace created once;
- existing shared project not overwritten;
- Actor symlink/projection to shared project;
- Actor delete does not delete shared project.

## Config

Env MCP and diagnostics use installed package module entrypoints:

```text
<runtime-python> -m buddyswitch.application.entrypoints.env_mcp
<runtime-python> -m buddyswitch.runtime_support.turn_runtime status
```

Role/Skill guidance is updated in the same checkpoint.

## Proof

- preflight failure publishes no Actor root;
- post-publication failure retains attributable inactive Actor root;
- exact workspace allowlist;
- selected Role/Skill equivalence for every current Role;
- no Git/symlink/path escape regression;
- source auth handling remains safe;
- shared project semantics;
- delete safety and cleanup.
