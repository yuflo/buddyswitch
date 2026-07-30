# S4 Search Capability Cutover Implementation Plan

> Use `superpowers:executing-plans`, root `AGENTS.md` and
> `$buddyswitch-testing`.
> Plan state: `READY`
> Packet: `BS-MM-S4-SEARCH-R1-20260730-01`

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
- Verify its delta from base
  `e4fe342144febc023d1d635012e7e8a5e645138d` is coordinating documents only.
- Verify clean tracked/index/untracked product state.
- Verify the source/test manifests in `S4-SEARCH-SOURCE-SNAPSHOT.md`.
- Verify zero active instances, inactive Browser and no attributable process.
- Verify the installed runtime before reusing or rerunning baseline proof.
- Stop without mutation on any mismatch.

### S4.SEARCH.1 — Reuse the refactor baseline

- Verify that runs `b96f488146524dbc97eb14463aea7780`,
  `978b8137549e47bf9542e69b2045e2d6` and
  `c50a7fce15e94e0b902f7478abccf6ca` and
  `d0414c37f2a64ca7a1aa0c1c5de1866c` correspond to the unchanged product
  source, test inputs and material runtime.
- Record them as behavior-preserving GREEN/IMPACT entry evidence.
- Do not rerun them merely because executor identity changed.
- Do not create or run a manufactured RED. If identity equivalence cannot be
  established, rerun only the missing focused baseline before mutation.

### S4.SEARCH.2 — One coherent owner/consumer cutover

- Move the Search Tool files into the final private adapter root.
- Add the minimal `SEARCH` assembly in `module.py`.
- Add Search exactly once to application composition.
- Delete the entire retired Search Tool package.
- Delete only `BrowserAccess.request(...)` from generic Tool context.
- Move the two Search-owned integration tests under the Search module.
- Update their imports and final source-path assertion; remove their unused
  Browser/CDP imports and local/shared handler/server fixture code.
- Remove stale unused Search-private imports and dead browser-client fixture
  infrastructure from the classified root tests.
- Make Demand and Task architecture proofs local rather than complete-list
  owners.
- Make explicit Tool proof derive from application composition.
- Make the env-layer Tool-root proof derive both dynamic packages and explicit
  component Tool roots from application composition. Translate
  `registration.invoke.__module__` into `REPO_ROOT / "src" / <module parent>`;
  do not use installed `__file__`.
- Make the repository composition proof validate selected module surfaces and
  forbid private imports without hard-coding a complete component list.
- Add/complete Search architecture proof.
- Update README and the four current architecture documents.
- Do not add `public.py`, a Browser adapter, compatibility import, discovery
  exception or new host contract.
- Run a static Python parse over every changed/untracked Python file.
- Run `git diff --check`.

Do not invoke `./buddyswitch-test` anywhere inside this edit block.

The generic env-layer source projection must use this shape:

```python
application = build_application()
explicit_tool_roots = {
    registration.definition.id: (
        ROOT
        / "src"
        / Path(*registration.invoke.__module__.split(".")).parent
    )
    for registration in application.tools
}
dynamic_tool_roots = {
    path.name: path
    for path in (ROOT / "src/buddyswitch/env/tools").iterdir()
    if path.is_dir()
    and not path.name.startswith("_")
    and (path / "__init__.py").is_file()
}
assert not (explicit_tool_roots.keys() & dynamic_tool_roots.keys())
tool_roots = {**dynamic_tool_roots, **explicit_tool_roots}
```

The env-layer cross-import proof iterates `tool_roots.items()` and uses
`set(tool_roots)` as the current Tool-ID set. It must not retain a manually
enumerated `_SHIPPED_TOOLS`.

The repository composition proof must derive selected names from
`COMPONENTS`, require every selected module to have a composition import, and
reject every `buddyswitch.modules.<name>.private` import. It must not assert an
exact complete import set.

The new Search architecture proof must directly assert:

- final Search owner files and module-local tests exist;
- all three retired `env/tools/search` files and the old root tests are absent;
- `SEARCH` is a passive `ModuleAssembly` named `search` with exactly one
  `search` Tool registration;
- application composition selects `search` exactly once;
- dynamic discovery does not contain `search`, while the built application
  contains exactly one `search` Tool;
- Search source imports only its local private adapter, public Tool runtime
  contracts, `runtime_support.env_profiles` and the standard library;
- generic hosts import no Search private module;
- `BrowserAccess.request` is absent while its current status/evidence methods
  remain.

README must distinguish the two current Tool ownership forms without teaching
a universal old path:

```text
component-owned Tool:
  src/buddyswitch/modules/<component>/private/adapters/tool/{tool.py,_impl.py}
not-yet-migrated dynamically discovered Tool:
  src/buddyswitch/env/tools/<tool>/{tool.py,_impl.py}
```

`test_package_contract.py` must require those current guidance forms and the
new Search architecture document/owner paths. It must not keep the claim that
every Tool is owned under `env/tools/<tool>`.

### S4.SEARCH.3 — One activation boundary

After the final `src/buddyswitch/**` mutation:

- build through the declared PEP 517 path;
- non-editably install into `.buddyswitch-runtime/venv`;
- activate and verify exact source/distribution correspondence;
- record activation, source and distribution identities;
- confirm no ad hoc dependency or environment mutation.

If any later repair changes `src/buddyswitch/**`, repeat this boundary before
the next public-runner command. Test/doc-only repair invalidates affected test
evidence but does not require package reprovision.

### S4.SEARCH.4 — Focused GREEN and affected proof

Run:

```bash
./buddyswitch-test focused \
  tests/unit/architecture/test_search_component_boundaries.py \
  tests/unit/architecture/test_demand_sys_boundaries.py \
  tests/unit/architecture/test_task_sys_boundaries.py \
  tests/unit/architecture/test_tool_runtime_contract.py \
  tests/unit/architecture/test_package_contract.py \
  tests/unit/architecture/test_repo_contracts.py \
  tests/process/cli/test_env_layer_boundaries.py \
  src/buddyswitch/modules/search/tests \
  tests/integration/env_tool/test_response_registry.py \
  tests/integration/env_tool/test_response_artifact.py \
  tests/integration/env_tool/test_response_demand.py \
  tests/integration/env_tool/test_response_task.py
```

Then run the complete affected preservation group:

```bash
./buddyswitch-test focused \
  src/buddyswitch/modules/search/tests \
  tests/integration/env_tool/test_response_artifact.py \
  tests/integration/env_tool/test_response_demand.py \
  tests/integration/env_tool/test_response_registry.py \
  tests/integration/env_tool/test_response_task.py \
  tests/integration/env_tool/test_layer_end_to_end.py \
  tests/integration/env_tool/test_host_decision_surface.py \
  tests/integration/env_tool/test_context_binding.py \
  tests/integration/runtime/test_tool_feedback.py \
  tests/unit/env_tool/test_semantic_contract.py \
  tests/unit/env_tool/test_schema_contract.py \
  tests/unit/env_tool/test_active_task_gate.py \
  tests/unit/daemon/test_decoupling.py \
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

### S4.SEARCH.5 — Freeze, FINAL and bounded FIX_AFTER_FINAL

- Freeze tracked/index/untracked and activation identities.
- Confirm every focused result is source-equivalent.
- Confirm `git diff --check`.
- Run `./buddyswitch-test full` once for this frozen candidate.
- Prove no test root, process, socket, lock, instance, Browser, deleted-open
  file or hidden dependency remains.
- If FINAL passes, return the complete packet and stop.
- If FINAL fails, preserve the complete failed result and classify it once.
- At most one FIX_AFTER_FINAL cycle is authorized, and only when the failure
  has one clear owning cause, every required write is already classified by
  the manifest, no protected contract/boundary changes, and cleanup is
  restored.
- For that bounded repair, run the smallest exact regression plus the complete
  affected group, reprovision before public proof if `src/buddyswitch/**`
  changed, freeze the new candidate, then run one replacement FINAL.
- The replacement FINAL is the second and last `full` command. Return and stop
  whether it passes or fails.
- Any unclassified, unexplained, environment, protected-contract or
  cross-lane FINAL failure returns immediately without repair or rerun.

This is not permission for blind retry or patch-on-patch. The failed FINAL
remains contrary evidence and must appear in the return packet with its owning
diagnosis and disposition.

## 4. Stop conditions

Return `REPLANNING REQUIRED` once when:

- identity or manifest differs;
- a required write is unclassified;
- baseline identity cannot be established or its rerun produces a new signal;
- `ModuleAssembly`, registry, Browser or profile contract must change;
- Search needs a Public service or state/data migration;
- another S4 lane must change;
- compatibility, fallback or generic framework appears necessary;
- a public test would run after source mutation but before reprovision;
- a failure is outside classified scope or unexplained;
- FINAL fails without satisfying every bounded FIX_AFTER_FINAL condition;
- a replacement FINAL fails;
- cleanup is not attributable and clean.

Do not loop, wait, blind-retry FINAL, exceed one bounded repair, edit the
packet or mark a stopped execution complete.

## 5. Return format

```text
Packet ID and lane:
Starting preparation commit and product manifests:
Final tracked/index/untracked identities:
Final activation/source/distribution identity:
Completed checkpoints:
Changed/created/deleted files by manifest class:
Reused/rerun refactor baseline commands, identities and results:
Focused GREEN commands, run IDs, results and durations:
Affected command, run ID, result and duration:
Every FINAL command, frozen identity, run ID, result and duration:
FIX_AFTER_FINAL cause/authority/repair/exact-and-affected evidence, or inapplicable:
Every failure/timeout/flake/no-test/residue signal and disposition:
Consumer-observed Search contract:
Composition/registry/package/dependency replacement proof:
Current docs changed:
Cleanup/residual state:
Omitted checks and residual risk:
New findings or stop/replan discoveries:
Proposed ACCEPTED / REJECTED:
```
