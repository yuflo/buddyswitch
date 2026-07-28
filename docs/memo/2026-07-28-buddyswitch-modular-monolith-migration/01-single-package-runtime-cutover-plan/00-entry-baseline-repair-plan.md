# S1 Entry Baseline Repair Plan

> Plan state: READY
> Purpose: restore current accepted behavior proofs before S1 migration
> Findings: F-026, F-027, F-028
> Runtime migration: forbidden

## 1. Acceptance sentence

> The accepted current Web/CLI boundary, parent-visible Tool catalog and direct
> Tool dispatch contract are mutually consistent and pass their exact public
> runner proofs, without beginning package/runtime migration or changing
> product semantics.

## 2. Root causes

### E0.1 Current architecture proof drift

`docs/arch/web-interface-call-architecture.md` was forward-rewritten in
`f8c53b2`, while
`test_durable_architecture_names_the_final_single_track_boundaries` still
requires exact phrases from the prior document.

The current document is the semantic owner. Repair the test to prove its
current exact owner/call prohibitions. Do not put retired phrases back into the
document merely to satisfy string assertions.

### E0.2 Parent Context catalog expectation drift

`4b9d297` deliberately introduced `_parent_tool_catalog()` so Parent/Main does
not see the side-only `demand_sys.resolve_inbound` action. The integration test
still compares the returned catalog to the global unfiltered registry.

Repair the proof around the current contract:

- the global registry still owns and exposes `resolve_inbound`;
- Parent/Main `context.get` exposes Demand `list`, `get`, and `complete`;
- `resolve_inbound` is absent from every parent-visible Demand operation,
  payload, input-schema, action-semantics and native-MCP projection;
- unrelated full input schemas, including `track.create.now`, remain intact.

Do not expose the side-only action to make the old equality pass.

### E0.3 Runtime Kernel package initialization cycle

Direct Tool dispatch imports `daemon_client`, which imports
`runtime_kernel.protocol`. Package initialization eagerly re-exports Broker,
which imports Dispatcher, which imports the still-initializing Tool Context.

Repository search finds no consumer of
`from runtime_kernel import dispatch_runtime_request` or
`runtime_kernel.dispatch_runtime_request`. Make `runtime_kernel.__init__`
side-effect free; import concrete submodules at their owner/caller. Do not add
a lazy compatibility alias.

## 3. Files

Allowed production/test/current-doc files:

```text
scripts/runtime_kernel/__init__.py
tests/process/cli/test_black_box_tool_runtime.py
tests/integration/runtime/test_runless_contract.py
tests/unit/architecture/test_external_control.py
docs/arch/web-interface-call-architecture.md
```

The architecture document is allowed only if investigation finds the current
contract itself wrong. The expected repair is proof alignment, not document
reversion.

No other production file is expected. Stop if a semantic production change
outside the Runtime Kernel initialization boundary appears necessary.

## 4. Proof sequence

Reuse the valid isolated RED evidence in `00-source-snapshot.md`; do not rerun
RED merely for freshness.

After each repair run:

```bash
./buddyswitch-test focused tests/unit/architecture/test_external_control.py::ExternalControlArchitectureTests::test_durable_architecture_names_the_final_single_track_boundaries
```

```bash
./buddyswitch-test focused tests/integration/runtime/test_runless_contract.py::RunlessRuntimeContractTests::test_context_get_exposes_full_input_schemas
```

```bash
./buddyswitch-test focused tests/process/cli/test_black_box_tool_runtime.py::ToolRuntimeProcessTests::test_broken_non_selected_private_impl_does_not_block_selected_tool tests/process/cli/test_black_box_tool_runtime.py::ToolRuntimeProcessTests::test_probe_tool_add_and_delete_use_only_tool_py_registration
```

Then rerun the exact 21-file preservation selection recorded by the Goal
Packet. `./buddyswitch-test full` is not authorized for this prerequisite.

## 5. Stop conditions

Stop and return without broadening when:

- the current architecture document is semantically inconsistent rather than
  only proof-stale;
- Parent/Main is supposed to expose `resolve_inbound`;
- a public `runtime_kernel.dispatch_runtime_request` contract is found;
- a production change outside package initialization is required;
- a new baseline failure appears;
- unrelated dirty work overlaps an allowed file;
- any resource cleanup is not clean.

## 6. Completion

Return exact diff, commands/run IDs/results, cleanup, finding closure proposals
and remaining baseline risk. Do not mark F-026–F-028 closed, edit the master
ledger, start S1 migration, commit, stage or begin another goal.
