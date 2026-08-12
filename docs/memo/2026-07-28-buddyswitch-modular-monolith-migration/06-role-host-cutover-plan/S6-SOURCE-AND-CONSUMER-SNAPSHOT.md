# S6 Source and Consumer Snapshot

## Identity

```text
Source HEAD:             b5f275dff2f2c52e09744c8fcf2c9002a67e9a84
Branch/upstream:         fea-tool / origin/fea-tool
Tracked/index patch:     empty
Untracked:               none
Installed source:        032dde43ff162285bf34b890652e85713c6dd5776dbdc3813f859b5ee23b27c3
Installed distribution: e3d0515d6e7d12e0223cf61c1df68a673ec4a65638a5454789f12582ad405887
Runtime verify:           ok=true
```

The 74 current Role-source files under `runtime_support`, `catalog`,
`launcher`, central `skills` and Role contracts have framed path/content digest
`d5b64ef51259a48a63fa24eef4ea4f0f472ee3e56f20aff780a2f1cdaa70dd68`.
The sorted 81-file direct/literal/package/test/current-doc consumer set has
framed path/content digest
`ba199fd3944e4de714bfc7a0888c40213aa83dd5f6395fe59a6332aa167f6ad6`.

For both digests, files are sorted by POSIX path. Each entry hashes an unsigned
eight-byte big-endian path length, path bytes, unsigned eight-byte content
length and raw content bytes. Generated caches are excluded.

## Current semantic owners to replace

| Current surface | Current responsibility | S6 disposition |
|---|---|---|
| `catalog/manifest.toml` | central Roles, private Skills, selected component Skills and Artifact templates | delete after Role descriptors are live |
| `catalog/env-profiles/*.json` | Role source access and Search/Browser capability plus duplicated advisory fields | replace with exact Role-owned capability facts; do not copy unused metadata into a new central schema |
| `runtime_support/env_manifest.py` | catalog parsing, mutable component Skill injection, Role/template validation and retired artifact-kind translation | replace; no global mutable Skill catalog or legacy translation |
| `runtime_support/env_profiles.py` | central Role profile loader/validator | replace with RoleHost resolution |
| `runtime_support/role_auth.py` | central permission enumeration and policy preview | replace with Application/RoleHost authorization derived from current Tool registrations and validated Roles |
| `runtime_support/runtime_skills.py` | central selected-Skill path resolution | replace with RoleHost selected projection |
| `launcher/assets/roles/*/AGENTS.md` | Role bootstrap | move byte-equivalent current guidance into each Role package |
| `skills/<role>/**` | Role-private Skills | move into owning Role package |
| Role `.md` contracts and result schemas | Role-specific content/test contract | move to the owning Role package when still live; remove only test-created central fiction |

`contracts/prepare-turn-context.json` is not Role truth. It remains outside the
Role package cutover unless current consumer tracing establishes a different
owner-correct disposition. S6 must not absorb generic Context semantics merely
because that file currently shares a directory with Role contracts.

## Production consumer map

### Application and Actor

- `application/build.py` configures Tool authority and the mutable component
  Skill injection.
- `application/entrypoints/actor_build.py` resolves central Role assets and
  selected Skills into `ResolvedActorBootstrap`.
- `application/host_control.py`, `application/cli_runtime.py` and
  `application/role_source.py` project central Role facts to Foundation.
- cleanup, diagnostics and Runtime Broker entrypoints pass the manifest loader
  or path into Foundation.
- the two test-only manifest/profile application entrypoints have no production
  consumer and do not earn compatibility merely through tests.

### Foundation hosts

- ToolHost authorizer currently receives the full manifest; `ToolContext`
  exposes both manifest content and path.
- Runtime Broker session/server/lifecycle and Host Control shell carry
  `--manifest` and a packaged path.
- CLI Runtime config, environment, cleanup shell and diagnostics carry the same
  path.
- generic cleanup uses a manifest-path loader only to obtain valid Role IDs.

These are implementation leaks, not protected public product inputs. S6 removes
them instead of renaming the manifest.

### Product modules

- Artifact reads active Role template choices from the full manifest.
- Search loads the active Role Search boundary through the central profile.
- Context loads project/source access and central Role-action preview.
- Evidence and several typed test contexts declare unused manifest fields.

The replacement supplies one immutable selected Role runtime projection through
the existing ToolHost boundary. Product modules consume only the Role facts
they actually need and do not import RoleHost private implementation.

### Package, runner, tests and guidance

- `pyproject.toml` packages central catalog/contracts/Role assets/Skills.
- distribution tests require those paths.
- the public runner discovers only `modules/*/tests/<tier>` today; S6 must add
  `roles/*/tests/{unit,contract,integration}` to that same mechanism exactly
  once and keep process/system tests root-owned.
- root behavior, process, architecture and package tests encode central paths,
  loaders, patch targets or a five-Role enumeration.
- root `AGENTS.md`, README and two current architecture documents teach the
  central path.

## Protected observable behavior

- existing Role IDs, labels, scopes, bootstrap bytes, selected Skills,
  Artifact template boundaries and source access remain equivalent;
- `market` keeps required Browser research and user-approved-only fallback;
  other current Roles keep available Browser/Search behavior;
- `dev` alone keeps source write access;
- every registered current Role keeps the current Tool permission outcome,
  while unknown Role and unknown permission fail closed;
- Role list/start, CLI sandbox configuration, Broker v2 dispatch, cleanup Role
  filtering, diagnostics command, Tool catalog and current product operations
  remain runnable;
- Actor publication remains atomic and code-free: selected AGENTS plus selected
  Skills only, with no other Role, unselected Skill, Role descriptor or private
  implementation copied.

## Cross-stage exclusions

No canonical product data moves. No external API or compatibility coexistence
is required. S6 may change internal Application/Foundation call shapes needed
to remove the manifest, but it may not redesign product module Public APIs,
Daemon/Web composition, Actor lifecycle or storage semantics.
