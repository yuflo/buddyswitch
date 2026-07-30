# S4 Search Boundary Design and Preflight

> Design state: `FROZEN FOR SEARCH LANE`
> Preflight: `S4SEARCHP-20260730-02 — PASS`

## 1. Selected design

Search becomes one passive capability module:

```python
SEARCH = ModuleAssembly(
    name="search",
    tools=(
        ToolRegistration(
            definition=DEFINITION,
            invoke=invoke,
        ),
    ),
)
```

Application composition imports and selects `SEARCH`. Generic application
activation continues to configure the registry. No product component is
filesystem-discovered.

## 2. Dependency boundary

Allowed Search private dependencies:

- Search-local Tool definition/implementation;
- `buddyswitch.env.tool_runtime` public Tool contracts/results;
- generic `ToolContext` invocation facts;
- `buddyswitch.runtime_support.env_profiles`;
- standard library.

Forbidden:

- another module's `private/**`;
- Browser launcher/manager/cockpit implementation;
- repository/domain state owners;
- application composition from inside Search;
- Search implementation imported by a generic host.

Search has no Public surface because it has no current application consumer.
The Tool registration is its external runtime contract.

## 3. Positive and negative matrix

| Claim | Positive proof | Negative/correspondence proof |
|---|---|---|
| one owner | final module-local behavior passes | retired `env/tools/search` absent |
| one selection | application contains one Search assembly | duplicate module fails |
| one Tool route | explicit registry dispatch returns current contract | Search absent from dynamic discovery |
| preserved semantics | status/request/rejection tests pass | no Browser page/write/fetch occurs |
| host cleanliness | `BrowserAccess.status/evidence` preserved | `BrowserAccess.request` absent |
| dependency isolation | Search imports allowed public/foundation surfaces | no cross-module private/launcher owner import |
| package projection | installed distribution contains Search owner | old package and module-local tests absent from wheel |
| current truth | README/current architecture name final owner | no current doc teaches old Search path |

Mutation and cleanup are inapplicable because Search is read-only and owns no
resource. Process cleanup remains required for the test runner itself.

## 4. Atomicity

The preflight proved old and new registration together fail:

```text
tool 'search' is both explicitly registered and package-discovered
```

Therefore source movement, explicit assembly selection and retired package
deletion form one coherent BUILD/REPLACE block. The executor writes the final
architecture proof within that block, but may not run or publish an
intermediate dual-registration topology.

## 5. No host-contract upgrade

The preflight preserved:

```text
demand_triage -> task_goal -> demand_orchestration
```

and dispatched Search through the existing Tool contract. Therefore changing
`ModuleAssembly`, registry discovery semantics or a Browser contract is a
replan condition, not ordinary implementation.

## 6. Refactor proof entry

This is a behavior-preserving refactor. Do not manufacture RED.

Reuse the four identity-valid current GREEN baselines in the source snapshot.
During the coherent cutover, create:

```text
tests/unit/architecture/test_search_component_boundaries.py
```

with final-topology tests that prove:

- Search physical owner and explicit composition;
- one Tool registration;
- allowed dependencies;
- absence of old paths;
- absence of `BrowserAccess.request`;
- no Search private import in generic hosts.

Run these tests only after the final source topology has been reprovisioned and
activation verifies. A collection/import/setup failure is not architectural
evidence.
