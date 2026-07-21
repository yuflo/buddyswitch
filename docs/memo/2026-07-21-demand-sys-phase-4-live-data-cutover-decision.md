# Demand Sys Phase 4 Live-Data Cutover Decision

**Date:** 2026-07-21

**Status:** superseded without a Phase 4 mutation; user-side environment
cleanup removed the live-data gate

**Code baseline:** `213d980c29cc1f6a247375ede06d7f74de676ea3`
plus the uncommitted Phase 4 change set

## 1. Decision statement

Phase 4 code now has one live model:

```text
need-bearing inbound -> Demand -> actor judgment -> task_sys.create(DemandRef)
```

The real actor product loop and focused automated proof passed. The first
public-CLI state probe found retired Task data, so Phase 4 correctly paused
before any irreversible mutation. No runtime fallback, dual read,
compatibility adapter, or implicit deletion was added.

The user subsequently cleaned the actor environment outside this Phase 4
operation. Read-only verification now observes no live instances, no Task
records, empty Demand/Task lists for the named actors, and no acceptance Track.
The protected exact-id operation proposed below is therefore no longer needed
and must not be executed.

## 2. Authoritative live root

The public CLI and real actors use:

```text
/Users/chen/.codex-buddyswitch/state
```

The earlier zero-object check inspected the repository mount and was not valid
evidence for this root. Future acceptance must bind every snapshot command to
the runtime state root reported by `instance status.runtime_broker`.

## 3. Retired Task inventory

There are exactly 20 records whose `source_type` is
`im.message.created`. All are terminal and belong to the two currently active
market actors:

| Actor | Role | Completed | Canceled | Total | Runtime state |
| --- | --- | ---: | ---: | ---: | --- |
| `act-market-645c3ea1fe37` | market | 12 | 2 | 14 | active/healthy |
| `act-market-8164b055c113` | market | 6 | 0 | 6 | active/healthy |
| **Total** |  | **18** | **2** | **20** |  |

Exact ids:

```text
act-market-645c3ea1fe37
  task-im-message-created-6eb1874cd687
  task-im-message-created-f8f7fbbd3ad0
  task-im-message-created-d91e0bf7f24f
  task-im-message-created-db66abdcdb50
  task-im-message-created-0f0764f329a5
  task-im-message-created-fce221f40b3b
  task-im-message-created-7f1d209fa6f9
  task-im-message-created-e52d7e06ceb4
  task-im-message-created-ad12f8f9acff
  task-im-message-created-c7e5ce20c5f3
  task-im-message-created-0c2dfd3fca1d
  task-im-message-created-946ee345cddb
  task-im-message-created-3f67543a2831
  task-im-message-created-8f514baa885f

act-market-8164b055c113
  task-im-message-created-1e27ff8474f3
  task-im-message-created-2ec19b7983fe
  task-im-message-created-b2f2cdf40697
  task-im-message-created-506656cf907e
  task-im-message-created-011e74063121
  task-im-message-created-4b34d77d8c64
```

A public read probe already demonstrates the cutover effect:

```text
./buddyswitch-codex task get task-im-message-created-b2f2cdf40697
-> INVALID_ARGUMENT: task.source_type must be demand
```

This rejection is correct for the new contract. It also proves that the live
data decision cannot be deferred behind a compatibility reader.

Both market threads were idle and both daemons healthy at the inventory point,
but `task list --actor` failed with the same error for each actor because their
Task history contains the retired shape. The sorted SHA-256 manifest of the 20
current files hashes to:

```text
5394a0bf7d0fb126d6ec83851dc036b2b3d6d2cba61053a943e857a95fa69a51
```

This checksum is evidence for the inventory only. It must be regenerated after
the actors stop and before any authorized mutation; a mismatch aborts the
cutover.

## 4. Current records that must not be touched

The same live root contains 35 Demand-backed Tasks distributed across `design`,
`dev`, `pm`, and `test`. Three unrelated Tasks are currently active:

```text
task-demand-2bbb3cc18778  act-test-86d101ccfaf9  side_processing
task-demand-3c7c150c8af9  act-test-4fb7ec2ce707  side_processing
task-demand-8992676772c2  act-pm-323507901965    side_processing
```

No Phase 4 cutover operation may select by role, status family, directory, or
glob. It must match only the exact 20 retired Task ids above and must fail closed
if any selected record changes owner, source type, or terminal state before the
operation begins.

## 5. Phase 4 acceptance evidence still in live state

The stopped and deleted acceptance instances were:

```text
act-pm-9744de708a81
act-test-e22c5779c72e
```

Their durable evidence is bounded to:

- one Track: `track-phase4-1784563031`;
- four comments under that Track;
- PM aggregate: four Demands and two Tasks;
- Test aggregate: two Demands and two Tasks;
- the two actor identity records.

Both instances are absent and no matching process or instance directory
remains. These product records are not part of the 20-record legacy cutover and
must not be mixed into that operation.

## 6. Cleanup incident

The acceptance plan treated an empty PM/Test instance list as an empty role-data
set and executed:

```text
data cleanup --role pm --yes
data cleanup --role test --yes
```

The current cleanup owner defines role scope as every message whose `from_role`
or `to_role` matches. It therefore deleted 31 PM-linked and 16 Test-linked
historical IM objects. It did not select Demand or Task records, did not own the
acceptance Track, and skipped Track comments whose stored author shape lacks
`by_actor.role_id`.

`execute_cleanup_plan` deletes directly and creates no transaction backup. No
local recovery copy was found, and no unsupported reconstruction has been
attempted. Fifty-four other-role message objects remain. This incident must stay
in the acceptance record even if an external backup later restores the deleted
objects.

## 7. Options

### A. Archive and remove the exact 20 retired Tasks — recommended

This is the shortest forward-only cutover because every selected Task is
already terminal. It does not invent Demand semantics for historical work.

Protected execution requirements:

1. obtain explicit user authorization for the exact 20 ids;
2. wait for a maintenance window and stop only the two market actors;
3. verify both actors are stopped and every selected Task still has the recorded
   owner, `im.message.created` source, and terminal status;
4. export the exact 20 records to a user-approved immutable archive outside the
   live state root and record its checksum;
5. remove only those exact records through a bounded, reviewed one-time cutover
   operation;
6. prove every Demand-backed Task and all unrelated state are byte-identical;
7. restart the two market actors and prove `task_sys.list`, context reads, daemon
   health, and new Demand-backed work;
8. remove the one-time mutation surface from the live repository if one had to
   be introduced.

This is deletion from the canonical live product state, even with an archive,
and therefore cannot run without explicit authority.

### B. Semantically migrate each retired Task to a new Demand — not recommended

This would need to reconstruct a Demand from historical IM, invent a basis
revision, rename Task ids to remove the retired source identity, and rewrite
every evidence reference. It introduces more irreversible semantic guesses and
touches more records than the current bottleneck requires.

### C. Keep the records and add a compatibility read — rejected

This preserves two source models in current code and directly violates the
approved forward-only replacement.

### D. Delete by role, glob, or all-data cleanup — rejected

The live inventory proves these scopes overlap unrelated active work and user
history. The previous cleanup incident already demonstrates the failure mode.

## 8. Acceptance-evidence cleanup decision

Keep the Phase 4 acceptance records until the code and protected legacy cutover
are accepted. They are exact, bounded evidence and do not block the new model.

If their later removal is required, handle it as a separate actor-scoped cleanup
capability or a separately authorized exact-id operation. Do not reuse role
cleanup and do not broaden the 20-record legacy cutover to include them.

Future real-actor acceptance runs must use an isolated
`BUDDYSWITCH_SHARED_ROOT`/state root from the first command through teardown.
Deleting that isolated root after all owned processes stop is then both exact and
observable; production role cleanup is no longer part of the test protocol.

## 9. Resolution

The user reported the related actor instances cleaned. The following read-only
checks were then made against the authoritative public-CLI state:

```text
instance list                         -> []
instance list --role market/pm/test   -> []
live Task JSON inventory              -> 0 total / 0 non-Demand
task list for both former Market actors -> []
demand/task list for both acceptance actors -> []
track get track-phase4-1784563031     -> NOT_FOUND
```

This removes the live legacy-data blocker. It does not prove which external
cleanup operation was used, does not retroactively satisfy the rejected
role-wide cleanup procedure, and does not establish byte preservation for the
former store. The 47-message incident in section 6 remains unchanged.

The exact-id archive/removal option in section 7 is now historical contingency
only. Running it against the current empty store would be both unnecessary and
incorrect. Phase 4 may proceed to final source verification with one Demand-only
Task model and no migration or compatibility code.
