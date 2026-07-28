# S1 E1 Baseline and Package-Boundary Repair Goal Packet

> Packet ID: `BS-MM-S1-E1-20260728-01`
> Stage: S1 bounded prerequisite
> State: STOPPED / SUPERSEDED
> Acceptance owner: coordinating hub

> Current disposition: E1 closed F-033, then correctly stopped on expanded
> F-034. This packet authorizes no further work. See
> `S1-E1-RETURN-REVIEW.md`.

## 1. Goal

Repair F-033 and F-034 only so C1 has the intended runtime-artifact boundary
and C2 has a trustworthy green pre-move preservation baseline.

Acceptance sentence:

> A real installed BuddySwitch wheel excludes arbitrarily nested co-located
> `tests/docs/projects` subtrees, activation identity ignores those non-runtime
> files while detecting runtime-source drift, the exact current Demand Tool
> contract is proved without changing production behavior, and both frozen C2
> pre-move groups pass before any source or asset movement.

## 2. Read order

1. root `AGENTS.md`;
2. `.agents/skills/buddyswitch-testing/SKILL.md` and its required references;
3. `S1-REPLAN-REVIEW.md`;
4. `S1-E1-REPAIR-PLAN.md`;
5. `01-package-contract.md`;
6. `S1-VERIFICATION-MATRIX.md`;
7. current files named in allowed scope.

Use `superpowers:executing-plans` for the repair plan. Repository facts and the
current Demand owner outrank old test tables.

## 3. Starting identity

The coordinating hub preserves the exact executable identity below in the
READY review. Coordinating memo files are untracked, excluded from executable
content identity, and forbidden to the executor.

```text
HEAD: 9e527141ef9c6ca705015fcecfa0b2a6fe1c3fc3
tracked patch: 748505207476ea72dc494164b9bd4cc65a95ba44e660faf583f1041f1ce22ff8
index: empty
non-memo untracked paths: 12
non-memo path-set SHA-256: 4fc3101e7c5dc95d8a621ceeb42ded5c1c2d065fbb41d5a7a418d3256e5012e0
non-memo path/content manifest SHA-256: ce1d4b35f3861ca6988fb51938d7e70996d2aec5652cf957efce279edf5babeb
```

If HEAD, tracked patch, index state, or non-memo implementation identity
differs, stop and return the difference.

## 4. Allowed write scope

```text
pyproject.toml
src/buddyswitch/foundation/process_runtime/activation.py
tests/support/package_runtime.py
tests/unit/architecture/test_package_contract.py
tests/process/package/test_distribution_install.py
tests/process/package/test_runtime_activation.py
tests/unit/architecture/test_tool_runtime_contract.py
tests/unit/env_tool/test_semantic_contract.py
.buddyswitch-runtime/activation.json          ignored runtime output only
.buddyswitch-runtime/venv/**                  ignored runtime installation only
```

The executor may create only temporary process-test and wheel/build state
owned by the tests/setup commands, and must clean it.

## 5. Frozen behavior

Demand's exact global Tool actions are:

```text
list
get
resolve_inbound
complete
```

`resolve_inbound` is the isolated side's only ingress mutation action;
`create/revise/cancel` are decision values inside it, not global Tool actions.
Parent/Main sees `list/get/complete`. No production Demand file may change.

Package/build remains one setuptools declaration. Runtime installation remains
non-editable and fail-closed. Tests remain physically co-locatable under
modules but never ship or affect runtime activation.

## 6. Forbidden scope

- any production Demand, Tool registry, role-auth, MCP, daemon, domain, state,
  Skill, Web, CLI, launcher, or current architecture document;
- any C2 source/asset move or old-root deletion;
- a compatibility alias, fallback, second build owner, recursive catch-all
  package data, editable install, or source `PYTHONPATH`;
- master ledger, decision log, finding register, residue register, READY
  reviews, original `S1-EXECUTION-STATE.md`, or another stage;
- commit, stage, branch change, `./buddyswitch-test full`, or S1 continuation.

## 7. Execution

Execute `S1-E1-REPAIR-PLAN.md` in order:

1. F-033 exact stale-proof repair and focused GREEN;
2. F-034 process-owned RED for nested forbidden subtrees and activation;
3. minimal package/activation GREEN;
4. explicit runtime rebuild/reinstall/reactivation;
5. complete affected C1 matrix;
6. both frozen C2 pre-move groups;
7. cleanup, diff and identity audit;
8. return and stop.

All tests use only:

```text
./buddyswitch-test focused ...
```

Reuse hub RED `c6e52cb80ffd4f33ba0b19caa83e5249` for F-033 when source-equivalent.
Create a new source-bound RED for F-034 before changing `pyproject.toml` or
activation production code.

## 8. Stop/replan

Stop immediately if:

- current Demand production behavior must change to make the tests pass;
- exclusion cannot be expressed by the single package owner;
- activation requires a second packaging/config parser or source loader;
- any source/asset move is needed;
- a new failure family appears in the C1 or pre-move C2 groups;
- the starting identity or allowed scope is violated.

Do not solve a stop condition by widening scope.

## 9. Exact return

```text
Packet ID:
Goal status:
Starting HEAD / tracked patch / index / non-memo identity:
Exact final diff and changed files:
F-033 reused RED and GREEN run IDs/results:
F-034 new RED and GREEN run IDs/results:
Affected C1 milestone run ID/result:
C2 unit pre-move run ID/result:
C2 integration pre-move run ID/result:
Installed runtime source/distribution identity:
Consumer-observed contract:
F-033/F-034 and R-PKG-019 closure proposal:
Cleanup/residual state:
Omitted checks and residual risk:
Stop/replan discoveries:
Proposed prerequisite ACCEPTED / REJECTED:
```

The coordinating hub alone closes findings/residue, accepts E1, or issues a
fresh S1 resume packet.
