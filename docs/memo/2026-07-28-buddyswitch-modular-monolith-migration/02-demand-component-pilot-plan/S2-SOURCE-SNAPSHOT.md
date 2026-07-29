# S2 Formal Source Snapshot

## Identity

```text
HEAD: 28ca25d93b84c0165fa4cd6f92744744c1df5d67
tree: b52905b1a2a87e2220a9e75875e55bee9978d05b
branch: fea-tool
origin/fea-tool: 28ca25d93b84c0165fa4cd6f92744744c1df5d67
ahead/behind: 0/0
tracked patch SHA-256: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
index patch SHA-256: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
non-ignored untracked SHA-256: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
S2 affected path-set SHA-256: a0b2fe93a640734981bd4da0396109fca7ed61938d1aadbc196404f8d29da69b
S2 affected path/content SHA-256: 3bd06b548b3cb2475099d5315f483cfabcbefaa7ab1db984158c64832eb17524
S2 affected path count: 61
```

The worktree was clean before preparation. Preparation changes only this
migration pack and the master coordination documents named by the Goal
Packet. No executable S2 change exists at READY.

## Runtime identity

```text
package version: 0.1.0
source digest: 0240a6d6897a96fc2538f8b883eee4a48f5830c2deb9928e4d9ccaf44809445f
distribution digest: 02344c6d8e7edd0489cf02f69a28c991fc7364d833f1c1c72f04348a2505f0d7
Python: .buddyswitch-runtime/venv/bin/python
package root: .buddyswitch-runtime/venv/lib/python3.13/site-packages/buddyswitch
```

`./buddyswitch-codex env status` returned zero instances and inactive Browser.
No persistent BuddySwitch socket, lock, test root or attributable process
remained after the preparation runs.

## Current behavior preservation

The complete affected D2/M2/G1 automated group ran against this exact source:

```bash
./buddyswitch-test focused \
  tests/integration/daemon/test_core_runtime.py \
  tests/integration/task_sys/test_goal_binding.py \
  tests/integration/demand_sys/test_side_triage_flow.py \
  tests/integration/goal_mode/test_task_goal_reconciliation.py \
  tests/integration/env_tool/test_response_demand.py \
  tests/process/cli/test_env_native_mcp_projection.py \
  tests/unit/architecture/test_demand_sys_boundaries.py \
  tests/unit/architecture/test_task_management_skill.py \
  tests/system/goal_mode/test_product_flow.py
```

Result:

```text
run: 1ae2966bf66f4616afad03e4e955066a
result: 92 passed, 65 subtests passed
duration: 203.35s
cleanup: /private/tmp/bs-test-1ae2966b-vpw5kk0k absent
```

The cleanup owner and public CLI preservation group also passed:

```text
run: 298084964b1f463ab94c15f71171dffd
result: 7 passed
duration: 0.37s
cleanup: /private/tmp/bs-test-29808496-yygkn6rp absent
```

An initial node-id typo produced no tests and exit 4 in run
`7f299b6a6308469ca93c1ae23b32a424`; its root was removed and it is not
evidence.

## Semantic correspondence to accepted Demand behavior

The S1 movement from `9e527141ef9c6ca705015fcecfa0b2a6fe1c3fc3` to the
current package changed Demand implementation content only for package import
paths and removal of old `sys.path` bootstraps. Repository bytes and both
Skill artifacts are identical. The current 92-test preservation group proves
the package-path edits did not change the accepted D2/M2/G1 behavior.

The historical real-Actor acceptance remains:

```text
docs/memo/2026-07-27-demand-forward-cutover-real-actor-acceptance-implementation-plan.md
final run: 41b10edb9ab44db9a265299db03910f8
result: 92 tests, 65 subtests; D2 recovery plus M2/G1 semantic breadth
```

S2 must preserve that contract. A new qualitative real-Actor conversation is
not required for a pure structural move unless an executor changes observable
Demand semantics; the frozen system flow and complete affected group remain
mandatory.

## Exact runner RED

The coordinator temporarily created the final-shaped target
`src/buddyswitch/modules/demand/tests/unit/test_runner_ready_probe.py`, ran the
public runner, and removed it.

```text
run: c6fae094fda84117abf9ba27a69916b5
exit: 2
reason: focused target must be under tests/
cleanup: /private/tmp/bs-test-c6fae094-ap_9a7yw absent
worktree after removal: clean
```

This is the direct RED for D-019. The executor must add approved module-local
roots to the existing runner; it must not add a second runner.

## Invalidation

Any executable, build, current architecture, affected test or activation
change after this source identity invalidates the corresponding preservation
or topology evidence. The executor must stop rather than silently refresh the
packet.
