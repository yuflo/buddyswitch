# S4 Communication R3 Cleanup Execution-Boundary Repair Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use
> `superpowers:executing-plans` and the complete `$buddyswitch-testing` skill.
> This is one bounded `FIX_AFTER_FINAL` boundary correction.

**Goal:** Make the generic cleanup executor the single owner of destructive
path safety and truthful deletion results while preserving the accepted R2
Communication behavior.

**Architecture:** Component Private contributors continue to discover and
attribute state. The generic cleanup planner remains a preview and selection
projection. The generic executor revalidates roots and paths immediately before
effects, delegates regular actor-private deletion to its owner, safely unlinks
leaf links, and reports only attributable effects. No new public contract,
cleanup framework or component-specific host branch is introduced.

**Tech stack:** Python 3.13, pathlib/os/shutil, immutable cleanup contributions,
BuddySwitch public test runner and non-editable installed runtime.

---

## 1. Frozen behavior

### 1.1 Root authority

- A state-relative target is executable only beneath the current non-symlink
  `repo_root`.
- An external target is executable only when the plan has a current non-symlink
  `shared_root`, the display path is a safe relative path beneath it, the stored
  absolute target agrees with that derivation, and the category is the existing
  `actor_private_files` category.
- If a root itself becomes a symlink or otherwise loses its declared boundary
  before execution, fail before destructive effects. Do not recreate skeletons
  through that root.

### 1.2 Per-path execution

- Recheck every parent segment immediately before deletion. A parent symlink or
  resolved escape skips the entry and emits an effect-accurate warning.
- A final leaf symlink may be unlinked; its target is never opened, resolved for
  deletion or mutated.
- Delete nested selected paths deepest-first so a parent operation does not turn
  later child operations into falsely reported no-ops.
- A selected path that is missing at execution is skipped, warned and not
  reported as deleted.
- Unexpected I/O failure remains failure; do not suppress it or convert it into
  an `ok=true` result.

### 1.3 Actor-private owner

- A regular instance-private file continues through
  `actor_private_files.delete_private_file` after the generic executor has
  re-established the current boundary.
- A boundary rejection, missing file or other non-deletion outcome never falls
  back to raw absolute `unlink`/`rmtree`.
- An instance-private leaf symlink is removed as a link entry by the generic
  guarded deletion path without touching its target.

### 1.4 Terminal result truth

- `deleted_paths` contains only paths whose removal is attributable to this
  execution; `deleted_count == len(deleted_paths)`.
- Object ID projections contain only records whose `object_path` was actually
  deleted by this execution.
- Planner counts and candidate paths remain preview facts. Execution warnings
  explain stale, missing or newly unsafe entries without rewriting the plan.
- Existing result keys and CLI envelope remain unchanged.

## 2. Authorized files

Primary production owner:

```text
src/buddyswitch/runtime_support/env_cleanup.py
```

Required regression owner:

```text
tests/integration/env_tool/test_cleanup.py
```

Conditionally authorized only if direct consumer proof requires it:

```text
tests/process/cli/test_cleanup_cli.py
```

Communication discovery, actor-private repository code, module contributors,
Public/Web/Daemon/Tool surfaces, schemas, commands, architecture guidance,
migration master truth and every other S4 lane are read-only. If the frozen
behavior cannot be implemented inside this envelope, stop once and return the
specific architectural reason.

## 3. Required RED proof matrix

Before production mutation, add exact regressions that distinguish planning
from execution. The tests must build a valid plan first and then perform the
phase change before calling the real executor.

| Case | Phase change after plan | Required terminal proof |
|---|---|---|
| relative parent swap | replace a selected file's parent with an external symlink | target preserved; path not reported; warning names rejection |
| state-root swap | replace the planned state root with a symlink | no external effect or skeleton creation; execution fails before mutation |
| instance-private parent swap | replace a selected private parent with an external symlink | target preserved; no raw fallback; path not reported |
| shared-root swap | replace the shared root with a symlink before external deletion | no external effect; execution fails before mutation |
| missing after plan | remove a selected file before execution | no phantom deletion or ID; warning names stale/missing path |
| nested parent and child | select both existing paths | both effects are real and reported once; retired root remains absent |
| stable leaf links | keep relative and instance-private leaf links stable | link entries removed; targets byte-identical |

At least one stale relative record must use a cleanup index projection so the
test proves that actual deletion state, object IDs and consumer-visible result
cannot disagree.

Run the smallest changed exact nodes and observe attributable REDs from the
current installed R2 candidate. Collection, setup or runtime mismatch is not
valid RED.

## 4. Implementation and verification sequence

1. Reproduce the R3 continuation identity and preserve the dirty candidate
   directly; do not reset, stash, reconstruct, cherry-pick or create a detached
   repair patch.
2. Add and run the exact phase-change regressions to RED.
3. Correct only the generic execution owner and result projection described in
   sections 1 and 2.
4. Rebuild/install/activate the non-editable runtime after the final source
   mutation and run no-argument runtime verification.
5. Run the same exact regressions to GREEN, then dynamically discover direct
   cleanup, package, architecture and CLI proof from current repository facts.
6. Freeze the complete candidate and run `./buddyswitch-test full` exactly once.
7. Make no executable/test/package/runtime mutation after FINAL. Return the
   complete packet and stop without commit, push or Context work.

## 5. Stop conditions

Stop once and return `REPLANNING REQUIRED` for an unreconciled candidate or
runtime identity, a required production write outside section 2, a new public
schema/command decision, need for a second cleanup abstraction, unexplained
environment/resource failure or FINAL failure.

An expected exact RED or an in-scope implementation/test failure before FINAL
is not a packet contradiction. Diagnose it, correct it within the authorized
boundary and continue. Do not rerun a failed FINAL or loop through repeated
blocked turns.
