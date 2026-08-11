# S5 C6B Actor Runtime Implementation Plan

## Goal

Move the complete current parent-session and side-thread runtime cluster into
one direct Foundation Actor Runtime package, cut over every live consumer and
delete every retired Launcher representation while preserving all behavior.

This is a behavior-preserving refactor. Reuse the GREEN entry evidence; do not
manufacture RED from an expected path move.

## Coherent implementation blocks

### 1. Reproduce and classify current source

Confirm exact clean handoff identity, runtime correspondence and zero
attributable resources. Rediscover Python imports, shell-embedded imports,
dynamic module names, source-path literals, package expectations, tests,
support and current docs. Correct stale path examples inside the authorized
classes without requesting a new packet.

### 2. Build one direct owner

Create an inert `foundation/actor_runtime` package and relocate the six current
semantic owners into it. Update their internal imports directly. Preserve
capability persistence, Codex runtime records, parent input/attach behavior,
side-thread lease/turn transitions and lifecycle cleanup exactly.

### 3. Cut over consumers and replace history

Update application, Demand, Host Control, CLI, shell, test and support
consumers to direct modules. Update installed-distribution proof and current
architecture guidance. Delete all six Launcher owners and every live old
import/path projection. Do not leave a Launcher shim or package-root export.

### 4. Provision before public-runner proof

After coherent `src/buddyswitch/**` mutation, perform one clean non-editable
build/install/activate/verify cycle before the next public-runner command.
This ordering is mandatory under D-044.

### 5. Prove the claim at current boundaries

Use `$buddyswitch-testing` to rediscover valid exact and affected targets from
the final candidate. Prove direct Actor behavior first, then real Host
Control/CLI/Daemon/Demand consumers, package correspondence, architecture and
replacement. Batch compatible targets; do not copy remembered directory
placeholders or rerun unchanged evidence for actor identity.

### 6. Review, freeze and run FINAL once

Review the final diff for behavior preservation, one-owner topology, complete
representation removal, proof simplicity and resource cleanup. Run one
`./buddyswitch-test full` only after every review-driven executable change is
complete. An attributable in-scope defect may enter bounded
`FIX_AFTER_FINAL`; otherwise stop and return.

## Authority boundary

The executor owns the shortest owner-correct implementation, equivalent
private file organization, complete mechanical consumer set, valid target
selection and bounded attributable repair. It does not own product/Role
semantics, Host Control/Web/CLI redesign, migration master truth, commits,
pushes or later checkpoints.

## Stop conditions

Stop only if completion requires a protected semantic/state change, RoleHost
authority, moving a genuine later-C6 owner, compatibility/generalized
framework, an unexplained boundary failure, or a candidate that cannot run
without later work. An omitted mechanical consumer or stale path hypothesis
is executor-owned and is not a stop condition.
