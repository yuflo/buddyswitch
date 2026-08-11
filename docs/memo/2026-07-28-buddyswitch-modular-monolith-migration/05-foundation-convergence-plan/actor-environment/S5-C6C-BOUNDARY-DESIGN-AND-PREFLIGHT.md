# S5 C6C Boundary Design and Preflight

## Selected boundary

```text
current application Role/Skill resolver
  -> resolved Actor bootstrap projection
  -> foundation/actor_runtime Actor Environment publisher
  -> atomic code-free Actor workspace
```

The resolved projection is data, not a Role plugin framework. It contains only
the already-selected guidance/Skill sources and the configuration facts needed
by the publication owner. Foundation validates and materializes those explicit
inputs; it does not discover Roles, read the central manifest, select Skills,
or know Launcher Role asset paths.

Application composition is the only current glue between assembled module
Skill exports, the current central Role selector and the Foundation publisher.
S6 later replaces that current selector with RoleHost without changing the
publication owner or adding a second path.

The stable process boundary remains
`buddyswitch.application.entrypoints.actor_build`; Host Control shell callers
do not learn a Foundation module path.

## Alternatives rejected

1. **Move the current file unchanged into Foundation — rejected.** It would
   make Foundation import central Role manifest/Skill policy and Launcher Role
   assets, violating the S5 acceptance sentence.
2. **Implement RoleHost now — rejected.** S6 owns package discovery, Role
   descriptors/profiles/assets and deletion of the central catalog.
3. **Move Web or CLI first — rejected.** Current Web imports Host Control and
   CLI contracts; that creates a reverse edge or forces a larger unrelated
   cutover.
4. **Move only a type or helper — rejected.** It closes no runtime owner and
   leaves publication mechanics in Launcher.
5. **Move Host Control with the environment — rejected for this checkpoint.**
   Host Control has a separate lifecycle/lock/shell/error proof boundary and
   remains runnable through the stable build entrypoint after C6C.

## Topology preflight

`S5C6CP-20260811-01` parsed 243 current production Python modules and simulated
the owner replacement plus application-side Role/Skill resolution.

- current non-trivial SCCs: 10;
- candidate non-trivial SCCs: the same 10;
- new SCCs: zero;
- the candidate Environment owner depends only on Process Runtime;
- new Foundation-to-Launcher/application/module/runtime-support edges: zero;
- the application entrypoint is the only new current glue and depends toward
  the Foundation owner plus current S6-owned Role/Skill sources.

Five pre-existing Foundation reverse edges remain outside C6C and are already
owned by later C6/S6 convergence. C6C adds none and cannot preserve one as a
new convenience dependency.

## Ownership constraints

- Foundation owns publication validation, filesystem effects, atomicity,
  result/error semantics and failed-stage cleanup once inputs are resolved.
- Current application/Role support owns which Role/Skills/config facts are
  selected until S6.
- There is one publication call and one write path; no callback registry,
  service locator, fallback resolver, compatibility facade or dual builder.
- The Foundation package root remains inert and consumers import the concrete
  owner directly.
- Internal Python import paths are not protected; the stable application
  entrypoint and observable shell/JSON behavior are protected.

## C6C / later cut line

C6C does not move or redesign:

- central Role/Skill catalog, profiles, authorization or Role assets;
- Host Control lifecycle and shell orchestration;
- runtime lock;
- Codex config patch owner;
- Web/CLI hosts or assets;
- generic cleanup or final Launcher-root deletion.

Necessary current application glue and mechanical test/package/doc updates are
in scope. S6 must be able to replace the current Role resolver directly; it
must not need to repair C6C or remove an S5 compatibility layer.
