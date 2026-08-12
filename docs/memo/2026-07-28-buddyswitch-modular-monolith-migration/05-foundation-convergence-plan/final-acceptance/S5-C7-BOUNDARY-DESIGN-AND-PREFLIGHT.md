# S5 C7 Boundary Design and Preflight

> Decision: one atomic final Foundation seam extraction and S5 acceptance
> Preflight: `S5C7P-20260812-01`

## Selected topology

```text
product modules
  -> passive Foundation composition contracts
       SkillExport + cleanup contribution values

Application composition
  -> selected module Skill/cleanup values
  -> current S6 Role source/resolution capabilities
  -> Foundation cleanup / diagnostics / Runtime Broker

Foundation state/lifecycle cleanup
  -> explicit cleanup contributions + injected valid-Role projection
  -X-> Role manifest implementation

Foundation CLI/runtime diagnostics
  -> ToolHost catalog + injected current manifest/status fact

Foundation Runtime Broker
  -> ToolHost/Browser/State + injected manifest loader
  -X-> runtime_support or concrete Role implementation
```

Application owns the current concrete Role facts. Foundation owns generic
execution and validates required injected inputs fail-closed. S6 can replace
the Application-side Role truth without editing Foundation hosts.

## Why C7 is one execution unit

The three generic runtime-support files and Broker edge form one final S5
acceptance claim. Moving only contribution contracts leaves the cleanup host
and Broker upward edges. Moving only cleanup leaves generic diagnostics and
composition under the historical root. Accepting docs first would assert a
boundary the executable graph does not yet have.

One coherent source cutover followed by one reprovision and one frozen FINAL is
shorter and safer than multiple packet/checkpoint cycles. It does not combine
independent product behavior; all edits are mechanical dependency inversion
and physical ownership for the same Foundation boundary.

## Alternatives rejected

1. **Documentation-only C7.** Rejected because executable generic owners and a
   direct Role-policy import remain.
2. **Defer all remaining files to S6.** Rejected because RoleHost would inherit
   generic cleanup, diagnostics and composition responsibilities.
3. **Create a generalized Foundation provider/container.** Rejected because the
   current hosts need only small explicit inputs and no dynamic selection.

## Projected dependency preflight

The candidate owner graph was projected with passive contracts under
Foundation composition, cleanup under Foundation state/lifecycle, diagnostics
under Foundation CLI/runtime, and the Broker Role edge replaced by an
Application input:

```text
planned nodes:                              8
planned edges:                              7
new cycles:                                 0
projected Foundation runtime-support edges: 0
projected generic runtime-support files:    0
projected S6 runtime-support files:          5 including inert __init__.py
```

This is a bounded topology check, not a new dependency engine. Final proof
must inspect imports and executable representations under the changed owners,
plus installed package contents.

## Preservation evidence

| Claim | Evidence | Result |
|---|---|---|
| cleanup, Broker and diagnostics behavior | focused `84becba089ea4b60b715cc257098fee5` | 57 passed, 59 subtests |
| direct architecture and package boundaries | focused `d0afd8e28dbd47beb80cdc8b6a58d7fa` | 26 passed |
| source-equivalent repository acceptance | C6F FINAL `f9dea78e158e473db2a89081e60cb595` | all tiers passed; clean residue |
| installed runtime correspondence | runtime verify at source `f94b873f…`, distribution `1ee40273…` | `ok=true` |

No baseline command failed or left attributable resources.

## Final invariants

- Foundation imports no product module, Launcher, historical generic
  runtime-support or concrete Role implementation;
- generic cleanup, diagnostics and passive contribution contracts have direct
  Foundation owners and no old-path alias;
- every current Role-dependent Foundation operation receives an explicit
  required Application input;
- remaining `runtime_support` and Launcher content is exactly current S6 Role
  input, not generic execution;
- accepted Application process entrypoints remain current explicit interfaces;
- product semantics, Role semantics, protocols, commands, state and resource
  effects remain unchanged;
- current architecture guidance describes only this executable truth.
