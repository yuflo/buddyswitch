# S4 Search Capability Lane Acceptance

> Decision: `ACCEPTED`
> Execution packet: `BS-MM-S4-SEARCH-R2-20260730-01`
> Consumed predecessors:
> `BS-MM-S4-SEARCH-20260730-01`,
> `BS-MM-S4-SEARCH-R1-20260730-01`
> Authority: coordinating hub
> Acceptance date: 2026-07-30
> Next boundary: remaining S4 lane source refresh only

## 1. Accepted outcome

The Search acceptance sentence is true:

> Search is physically aggregated under one capability root, selected exactly
> once by application composition through the existing Tool contribution,
> preserves its non-opening URL-planning behavior, and leaves no Search
> implementation or Search-specific placeholder in the generic Tool host.

The accepted consumer path is:

```text
Actor env.tool request
  -> generic Tool registry
    -> explicitly composed Search Tool registration
      -> Search-private validation/profile projection/URL planning
        -> status, rejection, or page_opened=false target URL result
```

No Search Public surface, Browser action, state owner, compatibility path,
plugin, service locator, DI container, event bus or lifecycle framework was
introduced.

## 2. Frozen candidate identity

The hub reproduced the executor's identity before this non-executable
acceptance record:

```text
worktree:
  /Users/chen/Dev/buddyswitch/.worktrees/fea-tool
branch:
  fea-tool
HEAD and origin/fea-tool:
  2b3d297e7c461f0876a0558b8722ca22dc9335a9
tracked binary patch SHA-256:
  144a55b06bf89be3b2850baca89976dbeb61bf6ba3154a9467f5f87bbefbe059
index patch SHA-256:
  e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
untracked path/content manifest:
  2f76f0d1c69a1289d87e8172859a6808344e935ae45b431c0877be30cd0641b1
untracked files:
  13
git diff --check:
  clean
```

R2 changed no candidate file. The direct, affected and FINAL evidence all
refer to this same source and runtime identity.

## 3. Product and contract proof

| Material claim | Consumer path | Evidence | Result |
|---|---|---|---|
| `search.status` preserves profile-backed backend and readiness reporting | Actor Tool -> generic registry -> Search private owner | direct `6701c80ce5444a80bfd91b448d082d2b`; FINAL `7ecfb65c5e0643c6b112cc8af3c7e98b` | PASS |
| `search.request` preserves explicit backend/query/engine validation and URL projection | active Task Tool call -> Search owner -> `target_url` result | direct and affected evidence; FINAL | PASS |
| Search never opens a Browser page | Search owner -> non-opening result | module-local behavior proof; `page_opened=false`; FINAL | PASS |
| removed `open_browser` remains rejected with `E_ENV_TOOL` | Actor Tool rejection -> generic result envelope | module-local and CLI proof; FINAL | PASS |
| Demand, Task, other Tools and Daemon order remain unchanged | shared application/host paths | affected `d1d75714466b4bf390812aaeb60ff526`; FINAL | PASS |

Both actions are read-only. They write no product object, runtime file, Browser
page, evidence token or fetched result. Failure and success envelopes remain
the generic Tool runtime contract; no persisted or restart state exists for
Search.

## 4. Architecture proof

The accepted candidate has:

- one physical owner at `src/buddyswitch/modules/search/**`;
- one passive `SEARCH` `ModuleAssembly`;
- one application selection and one `search` Tool registration;
- no dynamic Search package or registration duplicate;
- no Search Public surface because no current cross-component consumer needs
  one;
- no Search contribution to Daemon, CLI, Web, Skill, cleanup, state or
  lifecycle;
- no Search-private import from generic hosts;
- no Search-specific method on `BrowserAccess`;
- module-local owning tests under
  `src/buddyswitch/modules/search/tests/integration`;
- root-owned cross-component and architecture proof through the one public
  runner.

Application composition remains the sole complete component-selection owner.
The exact Daemon order remains:

```text
demand_triage -> task_goal -> demand_orchestration
```

Search production logic is byte-equivalent to the retired implementation
except for owner-correct module documentation.

## 5. Replacement and residue proof

`R-SEARCH-001` is closed completely. The Search portions of
`R-FND-002`, `R-FND-003`, `R-FND-011`, `R-FND-012` and `R-DOC-002` are closed.

Absent live paths:

```text
src/buddyswitch/env/tools/search/**
tests/integration/env_tool/test_search.py
tests/integration/env_tool/test_response_search.py
BrowserAccess.request
```

The old checkout and installed-distribution Search paths are absent.
Module-local tests are excluded from the runtime wheel. Current guidance
names only the component owner; historical memos and negative absence guards
may retain retired terms.

## 6. Verification evidence

Direct GREEN:

```text
command:
  ./buddyswitch-test focused \
    src/buddyswitch/modules/search/tests/integration \
    tests/unit/architecture/test_search_component_boundaries.py \
    tests/unit/architecture/test_demand_sys_boundaries.py \
    tests/unit/architecture/test_task_sys_boundaries.py \
    tests/unit/architecture/test_tool_runtime_contract.py \
    tests/unit/architecture/test_package_contract.py \
    tests/unit/architecture/test_repo_contracts.py \
    tests/process/cli/test_env_layer_boundaries.py \
    tests/integration/env_tool/test_response_registry.py \
    tests/integration/env_tool/test_response_artifact.py
run:
  6701c80ce5444a80bfd91b448d082d2b
result:
  89 passed, 26 subtests; exit 0
cleanup:
  run root absent
```

Affected GREEN/IMPACT:

```text
command:
  ./buddyswitch-test focused \
    tests/integration/env_tool/test_layer_end_to_end.py \
    tests/integration/env_tool/test_response_demand.py \
    tests/integration/env_tool/test_response_task.py \
    tests/integration/env_tool/test_host_decision_surface.py \
    tests/integration/env_tool/test_context_binding.py \
    tests/integration/runtime/test_runless_contract.py \
    tests/integration/runtime/test_tool_feedback.py \
    tests/unit/env_tool/test_semantic_contract.py \
    tests/unit/env_tool/test_schema_contract.py \
    tests/unit/env_tool/test_active_task_gate.py \
    tests/unit/daemon/test_decoupling.py \
    tests/process/cli/test_search_cli.py \
    tests/process/cli/test_env_tool_package_independence.py \
    tests/process/cli/test_env_tool_router.py \
    tests/process/cli/test_black_box_tool_runtime.py \
    tests/process/cli/test_env_native_mcp_projection.py \
    tests/process/cli/test_buddy_env_profiles.py \
    tests/process/package/test_distribution_install.py
run:
  d1d75714466b4bf390812aaeb60ff526
result:
  150 passed, 565 subtests; exit 0
cleanup:
  run root absent
```

Frozen FINAL:

```text
command:
  ./buddyswitch-test full
run:
  7ecfb65c5e0643c6b112cc8af3c7e98b
result:
  Unit Python 440 passed, 1,122 subtests
  Unit JavaScript 147 passed
  Integration 761 passed, 442 subtests
  Process 262 passed, 377 subtests
  System 22 passed
  shell syntax PASS
  diff check PASS
  exit 0
cleanup:
  run root absent
```

FINAL ran once. The hub performed read-only identity, code, runtime and cleanup
review and reused the source-equivalent evidence rather than rerunning the
repository-wide suite.

## 7. Contrary evidence disposition

| Signal | Owning diagnosis | Disposition | Resolved |
|---|---|---|---|
| R1 `69e82249c86343c19bf4bf792b2bb151` collected no tests | immutable packet target named the module test parent, not one runner tier | D-051; R2 used runner-valid `tests/integration` tier with unchanged proof breadth | YES |
| R1 activation implementation-module no-op | wrong diagnostic entrypoint | not treated as evidence; installed runtime entrypoint verified | YES |
| R1 rejected provisioning shell | destructive cleanup trap rejected before execution | no mutation; later declared provisioning and runtime identity passed | YES |
| R2 manifest diagnostic shell error | zsh reserved variable shadowed command lookup | read-only diagnostic corrected with a non-reserved variable; identity matched | YES |
| 23 global mailbox socket files | pre-existing ownerless files outside this lane | inventory unchanged before/after FINAL, no open handles, not attributable | YES |

No R2 test failure, timeout, flake, no-test result, undeclared dependency or
attributable cleanup residue occurred.

## 8. Runtime and operations

```text
activated_at:
  2026-07-30T05:15:04.307720Z
source_digest:
  1ac19eb878ec0ff8989836280710d9c2b6ea9d00972295430f57548cb74742a9
distribution_digest:
  81f301201e85a5e3d7008dc4ca853804d93dbf863b6b6987a1b468f5c851d4fa
package:
  buddyswitch 0.1.0
runtime.verify:
  ok=true
instances:
  0
Browser:
  inactive
```

No attributable process, socket, lock, deleted-open file, test root or hidden
environment mutation remains.

## 9. Current documents

Executable truth is reflected in:

```text
README.md
docs/arch/search-capability-architecture.md
docs/arch/daemon-service-architecture.md
docs/arch/demand-sys-architecture.md
docs/arch/task-sys-architecture.md
```

No current guidance teaches `src/buddyswitch/env/tools/search`.

## 10. Acceptance and next boundary

Product, Contract, Architecture, Replacement and Operations proof all pass.
No material proof is omitted and no unresolved contrary signal remains.

Search is therefore `ACCEPTED`. Every Search execution packet is consumed and
must not resume. This record authorizes only:

```text
checkpoint accepted Search
  -> refresh remaining S4 lane source and shared-boundary facts
    -> select one next lane
      -> prepare and READY-review a new lane-sized packet
```

It does not authorize another S4 lane implementation.
