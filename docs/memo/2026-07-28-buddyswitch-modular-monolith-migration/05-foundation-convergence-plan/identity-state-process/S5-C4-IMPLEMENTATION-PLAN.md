# S5 C4 Identity / State / Process Primitives Implementation Plan

> **For agentic workers:** use the repository's `$buddyswitch-testing` skill
> and execute this plan as one independent C4 Goal Packet. Repository facts
> outrank path examples; D-051/D-059 preserve local implementation freedom.

**Goal:** Converge the live product-neutral identity, state and process
primitives into direct Foundation owners, replace every current consumer and
delete retired technical paths without changing observable behavior.

**Architecture:** Three small direct Foundation owners are implemented inside
one runnable candidate. Identity profiles may depend on state primitives;
consumers depend directly on the owning module. Broker/Daemon and host
ownership remain for C5/C6.

**Tech stack:** Python 3.13, installed non-editable BuddySwitch package, current
JSON/file/process contracts, and the single `buddyswitch-test` runner.

## 1. Frame and trace

- Confirm the clean preparation HEAD supplied by the hub, empty index/worktree,
  verified installed runtime, zero active instances and no test resources.
- Re-discover direct imports, literal paths, package assertions, patches and
  support references for all C4 owner fragments.
- Partition newly found representations by OWNER, CONSUMER, PROOF or CURRENT
  DOC. Do not stop for an omitted mechanical representation in those classes.
- Establish or reuse the source-valid behavior-preserving entry evidence. Do
  not run `full` before implementation.

## 2. Identity block

- Create one physical `foundation/identity/**` owner for the live identity
  model and profile persistence.
- Preserve all payloads, validation, ID patterns, profile locations and write
  guards exactly.
- Update every direct Foundation, module, host, test and support consumer.
- Keep Role catalog/selection/authorization out of Identity.
- Do not introduce package-root re-exports or retain old imports.

## 3. State block

- Create one physical `foundation/state/**` owner for current canonical root
  derivation, write guards, refresh behavior, IDs/timestamps and atomic JSON.
- Retain only the live Actor-private safety used by cleanup and the direct
  Actor-private root locator consumed by ToolContext/product code.
- Do not migrate zero-production-consumer descriptor/file-service helpers or
  test-only conveniences.
- Update module repositories and current hosts mechanically; do not move their
  semantic ownership.
- Preserve all paths, environment variables, schemas, error effects and one
  write path.

## 4. Process block

- Place exact process-start identity under `foundation/process_runtime/**`
  beside the already-final activation/invocation owner.
- Update Browser, App Server, Daemon, Broker and test/support imports without
  changing their lifecycle code or protocol semantics.
- Preserve PID/sidecar shape, match/liveness/reap/remove behavior and stale PID
  refusal.
- Leave all C5 Broker/Daemon modules in place.

## 5. Replace and document

- Delete `src/buddyswitch/env/**` after every live consumer has moved.
- Delete the old Runtime Kernel process-identity module and every live old
  import/literal/patch target.
- Remove dead helpers instead of copying or aliasing them.
- Update package topology assertions and add the smallest durable architecture
  proof for the new owners and retired-path absence.
- Add current `docs/arch` guidance for the implemented primitive boundary and
  update only current docs whose path/boundary statements become false.
- Keep architecture proof simple; no mini static analyzer or style micromanagement.

## 6. Verify the candidate

- After the coherent `src/buddyswitch/**` mutation, rebuild/install/activate
  and verify the non-editable runtime before any public runner command.
- Discover current exact tests from changed behavior/contract owners and run
  focused GREEN.
- Add direct affected proof for identity persistence, state/write guards,
  Actor-private cleanup, runtime activation/package correspondence, stale PID
  safety and the host/module consumer paths actually changed.
- Prove retired source/import/literal/package representations absent from source
  and installed distribution.
- Review the complete diff for semantic drift, broadened public surface,
  speculative layers and proof complexity.
- Freeze the candidate and run one `./buddyswitch-test full`.
- If executable/test state changes after FINAL, follow only the
  `$buddyswitch-testing` FIX_AFTER_FINAL sequence: exact regression, affected
  focused proof, reprovision when source changed, then one new frozen FINAL.

## 7. Return boundary

Return the required result packet and stop. Do not update master migration
truth, commit, push, begin C5 or reopen C1–C3.
