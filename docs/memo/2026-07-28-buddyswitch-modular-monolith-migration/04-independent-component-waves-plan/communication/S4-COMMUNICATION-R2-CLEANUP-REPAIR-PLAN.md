# S4 Communication Cleanup Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use
> `superpowers:executing-plans` and the complete `$buddyswitch-testing` skill.
> This is one bounded `FIX_AFTER_FINAL` continuation, not a new component
> migration and not an invitation to reconstruct R1.

**Goal:** Close the uncovered Message cleanup behavior gap without changing
the accepted Communication, Web, Daemon, Tool, Public or composition design.

**Architecture:** Communication Private continues to own Message path/schema
discovery and warnings. The generic cleanup host continues to own scope
selection, guarded path handling, deletion and result projection; it may be
changed only to restore safe leaf-symlink deletion without following a
symlinked parent. No scope-aware discovery framework or second cleanup shape
is introduced.

**Tech stack:** Python 3.13, immutable cleanup contribution dataclasses,
BuddySwitch public test runner and non-editable installed runtime.

---

## 1. Why R2 exists

R1's frozen candidate passed direct, affected and repository FINAL evidence.
The hub then ran a finding-specific probe against that same installed runtime.
With these owned files:

```text
im/messages/orphan.bin
im/messages/nested/broken.json
buddyswitch/objects/messages/orphan.bin
```

`build_cleanup_plan(scope="all-data", ...)` returned:

```text
delete_paths: []
warnings: []
```

The cause is top-level `glob("*.json")` discovery in Communication Private.
The retired central Message implementation traversed current Message state
recursively for all-data cleanup. The new owner must retain that effect while
keeping Message semantics out of the generic host.

R1 FINAL `22395255f8cf4ba6a8e40da39d651d7c` is valid evidence for the
unchanged remainder of the candidate, but this contrary signal prevents R1
acceptance. Any R2 executable or test change invalidates that FINAL and
requires exact proof, affected proof and one new frozen FINAL.

## 2. Frozen behavior decisions

### 2.1 Current Message root

For `im/messages/**`:

- discovery is recursive and does not depend on file extension;
- a regular file containing a valid current Message is role-attributed using
  both sender and recipient roles and is selected exactly once;
- malformed, non-JSON, unattributable and leaf-symlink entries are not selected
  by role cleanup and produce an actionable warning;
- all-data cleanup selects every safely owned regular file and leaf symlink
  exactly once, including nested and non-JSON residue;
- no symlink target is read, followed or deleted.

### 2.2 Retired Message root

For `buddyswitch/objects/messages/**`:

- role cleanup never deletes retired state and reports why it was skipped;
- explicit all-data cleanup deletes every safely owned regular file and leaf
  symlink exactly once;
- the retired root is not recreated after cleanup;
- retired entries never populate `message_object_ids` or `message_records`.

This is the Forward behavior for the explicit destructive all-data command.
It does not restore a retired read path, schema or compatibility surface.

### 2.3 Warnings and projection

- A warning names the affected path, the reason and the two true effects:
  role-scoped cleanup skips it; all-data cleanup deletes it.
- The wording may be one scope-neutral sentence. Do not add discovery context,
  per-scope callbacks, warning registries or a second `OwnedStatePath` shape
  merely to reproduce historical prose byte-for-byte.
- Only valid current Messages populate `message_object_ids` and
  `message_records`.
- Existing plan/result keys, category counts, sender/recipient selection and
  required recreation of `im/messages` remain unchanged.

### 2.4 Symlink safety

The generic cleanup boundary may unlink a leaf symlink contributed from an
owned directory, because deletion removes the link entry itself. It must reject
an absolute path, `..`, a symlink in any parent segment, or any regular path
whose resolved target escapes the state root. Discovery must never open a
symlink to classify its target as a Message.

## 3. Authorized change envelope

Primary production owner:

```text
src/buddyswitch/modules/communication/private/adapters/cleanup.py
```

Conditionally authorized only if required for the frozen leaf-symlink rule:

```text
src/buddyswitch/runtime_support/env_cleanup.py
```

Required regression owner:

```text
tests/integration/env_tool/test_cleanup.py
```

Conditionally authorized proof/current guidance:

```text
tests/unit/architecture/test_communication_component_boundaries.py
docs/arch/communication-capability-architecture.md
```

Do not modify other cleanup contributors. If the current generic contract
cannot satisfy the frozen outcome without doing so, stop once and return the
exact architectural reason; do not mechanically expand all module contracts.

Forbidden changes include Communication Public, Message domain/state, Tool,
Demand, Context, Application composition, WebHost, DaemonHost, other S4 lanes,
schemas, commands and migration master truth.

## 4. Execution tasks

### Task 0: Consume R1 and verify the current candidate

- [ ] Treat R1 as historical evidence and R2 as the sole authority.
- [ ] Reproduce branch, HEAD, non-memo tracked patch, empty index, non-memo
  untracked set, installed runtime identity and clean process/test-root state.
- [ ] Confirm no executable/test mutation occurred after the returned R1
  identity. Stop once if identity cannot be reconciled.
- [ ] Do not reset, stash, reapply, regenerate or cherry-pick the R1 candidate.

### Task 1: Add the missing exact regression and prove RED

- [ ] Extend the current cleanup integration owner with focused cases for:
  recursive current non-JSON/nested residue, valid dual-owner Message
  selection, retired residue, and a leaf symlink whose external target remains
  untouched.
- [ ] Assert both plan and execution outcomes: selected paths, warnings,
  Message indices, deleted entries, preserved external target, recreated
  current root and absent retired-root recreation.
- [ ] Dynamically validate the exact test node or file with the current runner.
- [ ] Run the smallest public focused target against the still-matching R1
  installed runtime and record an attributable RED caused by the known
  discovery gap—not collection, environment or setup failure.

### Task 2: Repair the semantic owner

- [ ] Implement the smallest Communication-private recursive discovery that
  satisfies section 2.
- [ ] If leaf-symlink unlinking is blocked by the generic guard, change only
  that guard: permit the final symlink entry while continuing to reject every
  symlinked parent and resolved regular path escape.
- [ ] Keep the existing `OwnedStatePath`, multi-owner and index-projection
  architecture. Do not add a discovery framework, product branch in the host,
  compatibility path or alternate cleanup contract.
- [ ] Inspect the complete diff for accidental changes outside section 3.

### Task 3: Reprovision and prove the repaired candidate

- [ ] After the last source mutation, rebuild/install/activate the
  non-editable runtime and run the current no-argument runtime verification.
- [ ] Run the same exact regression target to GREEN.
- [ ] Discover and run only the directly affected cleanup, architecture,
  process/package and consumer targets required by current repository facts.
- [ ] Prove no test root, process, socket, symlink target or temporary state is
  left behind.
- [ ] Freeze HEAD, tracked/index/untracked identities and runtime identity.

### Task 4: Run one replacement FINAL and stop

- [ ] On the frozen candidate, run `./buddyswitch-test full` exactly once.
- [ ] After FINAL, make no executable, test, package or runtime-asset mutation.
- [ ] Return the complete R2 packet on pass or failure; do not commit, push,
  edit migration master truth or begin Context.

## 5. Stop conditions

Stop once and return `REPLANNING REQUIRED` only for:

- unreconciled candidate/runtime identity;
- a required production write outside section 3;
- a new product, schema, authority or cleanup-scope decision;
- need for compatibility, a second cleanup contract or product branching in
  the generic host;
- an unexplained test/environment/resource failure;
- FINAL failure.

A correctable in-scope RED or affected failure is not a reason to loop in a
blocked state. Diagnose it once, repair it before FINAL, and continue. Do not
rerun a failed FINAL or wait through repeated blocked turns.
