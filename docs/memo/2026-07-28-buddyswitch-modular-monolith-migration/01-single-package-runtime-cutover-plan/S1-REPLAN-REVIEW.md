# S1 C1/C2 Return and Replan Review

> Current disposition: HISTORICAL first replan. Its E1 repair direction was
> attempted and stopped. Current control is `S1-E1-RETURN-REVIEW.md` plus
> the E2 source/plan/packet/acceptance chain. E2 is accepted and consumed;
> no packet is currently authorized.
> Review authority: coordinating hub
> Returned packet: `BS-MM-S1-20260728-01`
> Decision: S1 `REPLANNING`; C1 reopened; C2 not started

## 1. Outcome

The independent executor followed the packet correctly. It completed the
initial C1 implementation, ran the frozen C2 pre-move baseline, found a
predecessor contract contradiction, moved no source, made no commit, and
returned `STOPPED / REPLANNING REQUIRED`.

The stop report is accepted as accurate. S1 implementation is not accepted and
C2 may not resume from the old packet.

## 2. Repository identity verified

```text
HEAD:
9e527141ef9c6ca705015fcecfa0b2a6fe1c3fc3

tracked patch:
748505207476ea72dc494164b9bd4cc65a95ba44e660faf583f1041f1ce22ff8

index:
empty

commits created:
none
```

The tracked diff contains only the accepted E0 repair and C1 changes. The
executor preserved the coordinating-owned memo files. No C2 source or asset
move occurred.

## 3. F-033 — C2 baseline proof drift

Executor evidence:

```text
run 960b3959f7b64f86b29b95329f1d303a
7 failed, 310 passed, 977 subtests passed
```

Hub reproduction:

```bash
./buddyswitch-test focused \
  tests/unit/architecture/test_tool_runtime_contract.py \
  tests/unit/env_tool/test_semantic_contract.py
```

```text
run c6e52cb80ffd4f33ba0b19caa83e5249
7 failed, 23 passed, 407 subtests passed
```

The failures are one family. The two tests still require direct Demand
`create/revise/cancel` actions. Commit `4b9d297` replaced those public actions
with the exact current surface:

```text
list
get
resolve_inbound
complete
```

Current `scripts/env/tools/demand_sys/tool.py`,
`docs/arch/demand-sys-architecture.md`,
`tests/unit/architecture/test_demand_sys_boundaries.py`,
`tests/unit/env_tool/test_schema_contract.py`, native-MCP proof and Role
authorization all agree. `create/revise/cancel` remain only decisions inside
the private-capability-bound `resolve_inbound` operation.

Decision: the tests are stale. Production Demand code must not change.

## 4. F-034 — C1 runtime artifact boundary

The hub injected this future target topology into an isolated copy:

```text
src/buddyswitch/modules/probe/tests/__init__.py
src/buddyswitch/modules/probe/tests/test_probe.py
```

It built a real wheel with the current C1 `pyproject.toml`. The wheel contained
both test files. The cause is the finder exclusion
`buddyswitch.tests*`, which does not exclude nested
`buddyswitch.modules.<module>.tests`.

The current activation owner also recursively digests every file under
`src/buddyswitch/**` except cache/pyc. It therefore treats test content that
must not ship as runtime source identity.

This contradicts:

- D-019 physical test co-location;
- F-005's filtered runtime artifact;
- S1.1's required `**/tests/**`, `docs/**`, and `projects/**` exclusions;
- S1.1's rule that tests/docs/projects are not activation inputs.

Decision: C1 is reopened. Existing C1 RED/GREEN evidence remains useful for
the contracts it actually covered, but it cannot establish C1 acceptance.

## 5. Cleanup

The hub's test run root and isolated wheel-probe source are absent from `/tmp`.
The probe source was moved to the user's Trash. No BuddySwitch process was
left running. The ignored `.buddyswitch-runtime` remains the intentional
active development runtime.

## 6. Historical E1 replan boundary

The stopped bounded E1 packet owned only:

1. correcting the two stale Demand proof tables without production behavior
   change;
2. adding a real nested forbidden-subtree wheel proof;
3. excluding nested `tests/docs/projects` from package discovery and
   activation source identity;
4. rebuilding/reactivating the installed runtime;
5. proving C1 and the complete pre-move C2 baseline green.

E1 did not move sources, change any Demand production contract, begin C2,
commit, stage, run `full`, or alter another stage. Its package-internal
`docs/projects` exclusion assumption was later disproved and is not a current
rule.

## 7. Next gate

E1 is permanently retired. F-033 is closed; F-034 and R-PKG-019 remain open.
The accepted `S1-E2-PREFLIGHT.md` proves the replacement correspondence design
is feasible but authorizes no product change by itself. The subsequent
`S1-E2-READY-REVIEW.md` authorized only packet
`BS-MM-S1-E2-20260728-01`; `S1-E2-ACCEPTANCE.md` accepted and consumed it.
C2 remains unauthorized.
