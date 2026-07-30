# S4 Search Capability Cutover Implementation Plan

> Use `superpowers:executing-plans`, root `AGENTS.md` and
> `$buddyswitch-testing`.
> Plan state: `READY`
> Packet: `BS-MM-S4-SEARCH-20260730-01`

## 1. Goal

Physically aggregate Search and its owned tests, select it explicitly through
the existing application Tool contribution, delete the old dynamic package
and Search-shaped host placeholder, preserve all current Search behavior, and
prove the installed one-path result.

## 2. Protected contracts

- Tool ID `search`;
- actions `status` and `request`;
- exact input/action semantics and active-Task gate;
- profile-backed status/capability fields;
- explicit backend/query/engine validation;
- target URL results and `page_opened=false`;
- removed `open_browser` rejection and cockpit guidance;
- `search_api` permission/provider boundary;
- all other Tool IDs and existing Demand/Task module behavior;
- exact Daemon order;
- no state mutation or Browser page opening.

## 3. Execution sequence

### S4.SEARCH.0 — Handoff identity

- Verify the preparation commit supplied by the hub.
- Verify its delta from base `e4fe342...` is coordinating documents only.
- Verify clean tracked/index/untracked product state.
- Verify the source/test manifests in `S4-SEARCH-SOURCE-SNAPSHOT.md`.
- Verify zero active instances, inactive Browser and no attributable process.
- Verify the installed runtime before any RED.
- Stop without mutation on any mismatch.

### S4.SEARCH.1 — Exact RED

- Create only the architecture proof named in the boundary design.
- Run:

```bash
./buddyswitch-test focused \
  tests/unit/architecture/test_search_component_boundaries.py::test_search_is_one_explicit_component_and_old_tool_package_is_absent
```

- Record the exact expected failure.
- If no test is collected or the failure is not the final-owner/retired-path
  distinction, stop.

### S4.SEARCH.2 — Atomic owner cutover

- Move the Search Tool files into the final private adapter root.
- Add the minimal `SEARCH` assembly in `module.py`.
- Add Search exactly once to application composition.
- Delete the entire retired Search Tool package.
- Delete only `BrowserAccess.request(...)` from generic Tool context.
- Do not add `public.py`, a Browser adapter, compatibility import, discovery
  exception or new host contract.
- Run `git diff --check`.

Because package source changed, immediately build, non-editably install,
activate and verify the candidate before invoking the public test runner.

### S4.SEARCH.3 — Owner-local tests and consumer proof

- Move the two Search-owned integration tests under the Search module.
- Update their imports and final source-path assertion.
- Remove stale unused Search-private imports and dead browser-client fixture
  setup from the classified root tests.
- Make Demand and Task architecture proofs local rather than complete-list
  owners.
- Make explicit Tool proof derive from application composition.
- Add/complete Search architecture proof.
- Update README and the five current architecture documents.

If this block changes `src/buddyswitch/**` after activation, reprovision again
before the next public test. Test/doc-only changes do not require reprovision.

### S4.SEARCH.4 — Focused GREEN

Run:

```bash
./buddyswitch-test focused \
  tests/unit/architecture/test_search_component_boundaries.py \
  tests/unit/architecture/test_demand_sys_boundaries.py \
  tests/unit/architecture/test_task_sys_boundaries.py \
  tests/unit/architecture/test_tool_runtime_contract.py \
  tests/unit/architecture/test_package_contract.py \
  src/buddyswitch/modules/search/tests \
  tests/integration/env_tool/test_response_registry.py \
  tests/integration/env_tool/test_response_artifact.py
```

Then run the complete affected preservation group:

```bash
./buddyswitch-test focused \
  src/buddyswitch/modules/search/tests \
  tests/integration/env_tool/test_response_registry.py \
  tests/integration/env_tool/test_layer_end_to_end.py \
  tests/integration/env_tool/test_host_decision_surface.py \
  tests/integration/env_tool/test_context_binding.py \
  tests/unit/env_tool/test_semantic_contract.py \
  tests/unit/env_tool/test_active_task_gate.py \
  tests/integration/runtime/test_runless_contract.py \
  tests/process/cli/test_search_cli.py \
  tests/process/cli/test_env_tool_package_independence.py \
  tests/process/cli/test_env_tool_router.py \
  tests/process/cli/test_black_box_tool_runtime.py \
  tests/process/cli/test_env_native_mcp_projection.py \
  tests/process/cli/test_buddy_env_profiles.py \
  tests/process/package/test_distribution_install.py
```

Also prove:

- old source and installed package paths absent;
- Search implementation imports only allowed surfaces;
- generic hosts import no Search private module;
- one Search Tool registration and one component selection;
- Daemon order unchanged;
- module-local tests excluded from the runtime wheel;
- no current guidance teaches the retired path.

Every failure, timeout, flake, no-test or residue signal remains evidence. A
later pass does not erase it.

### S4.SEARCH.5 — Freeze and FINAL

- Freeze tracked/index/untracked and activation identities.
- Confirm every focused result is source-equivalent.
- Confirm `git diff --check`.
- Run `./buddyswitch-test full` exactly once.
- Never rerun FINAL after failure.
- Prove no test root, process, socket, lock, instance, Browser, deleted-open
  file or hidden dependency remains.
- Return the complete packet and stop.

## 4. Stop conditions

Return `REPLANNING REQUIRED` once when:

- identity or manifest differs;
- a required write is unclassified;
- exact RED is not the expected boundary failure;
- `ModuleAssembly`, registry, Browser or profile contract must change;
- Search needs a Public service or state/data migration;
- another S4 lane must change;
- compatibility, fallback or generic framework appears necessary;
- a public test would run after source mutation but before reprovision;
- a failure is outside classified scope or unexplained;
- FINAL fails or cleanup is not attributable and clean.

Do not loop, wait, retry FINAL, edit the packet or mark a stopped execution
complete.

## 5. Return format

```text
Packet ID and lane:
Starting preparation commit and product manifests:
Final tracked/index/untracked identities:
Final activation/source/distribution identity:
Completed checkpoints:
Changed/created/deleted files by manifest class:
Exact RED command, run ID and expected failure:
Focused GREEN commands, run IDs, results and durations:
Affected command, run ID, result and duration:
Single FINAL command, run ID, result and duration:
Every failure/timeout/flake/no-test/residue signal and disposition:
Consumer-observed Search contract:
Composition/registry/package/dependency replacement proof:
Current docs changed:
Cleanup/residual state:
Omitted checks and residual risk:
New findings or stop/replan discoveries:
Proposed ACCEPTED / REJECTED:
```
