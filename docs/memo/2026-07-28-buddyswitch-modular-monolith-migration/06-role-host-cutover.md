# S6 RoleHost Cutover Charter

> Current state: READY — S6 R1 ONLY
> Packet: `BS-MM-S6-ROLE-HOST-R1-20260813-01`
> Merge unit: one complete Role/Skill truth cutover

## Acceptance sentence

> A reviewed Role package is available by adding one valid packaged directory;
> invalid/duplicate Roles fail before Actor publication; only selected
> Role/Skill content reaches the Actor; no central Role/Skill/profile/contract
> catalog remains.

## Contract

A Role package owns:

- explicit Role ID and label;
- descriptor/capability inputs;
- `AGENTS.md`;
- Role-private Skills/code;
- assets/templates;
- Role-local tests;
- selection of assembled module Skill IDs.

Directory name is not implicit durable identity.

## Host policy

RoleHost:

- discovers only reviewed `buddyswitch.roles` packages;
- validates descriptor, duplicates, paths and assets fail-closed;
- validates selected IDs against application Skill exports;
- materializes only selected Role and Skills;
- cannot activate product components or mutate application composition.

## Scope

- current Role descriptors/AGENTS/profiles/Skills/contracts;
- Role list/start/authority/config consumers;
- Actor projection;
- Role-related cleanup validation;
- deletion of central manifest/catalog and prior Role/Skill paths;
- secondary-market-investor Role boundary proof.

## Proof

- every current Role bootstrap/Skills/authority;
- new valid Role requires no central host edit;
- duplicate/invalid/missing/path-escape failure before publication;
- Actor allowlist excludes other Roles/unselected Skills;
- no product discovery or generic PluginHost;
- old catalog/profile/contract/Skill paths absent;
- lifecycle and cleanup clean.

The source-bound implementation pack is at
`06-role-host-cutover-plan/README.md`. S6 remains one atomic cutover; its
internal coherent blocks are not separately acceptable architectures.
