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
deletion form one coherent BUILD/REPLACE block. The executor may create a RED
test before that block, but may not publish or verify an intermediate
dual-registration topology.

## 5. No host-contract upgrade

The preflight preserved:

```text
demand_triage -> task_goal -> demand_orchestration
```

and dispatched Search through the existing Tool contract. Therefore changing
`ModuleAssembly`, registry discovery semantics or a Browser contract is a
replan condition, not ordinary implementation.

## 6. Exact architecture RED

Create:

```text
tests/unit/architecture/test_search_component_boundaries.py
```

with an exact test:

```text
test_search_is_one_explicit_component_and_old_tool_package_is_absent
```

Before product mutation it must fail because the Search component/final owner
does not exist and the retired package does. If it passes or fails for another
reason, stop before BUILD.

The same file must ultimately prove physical owner, explicit composition,
allowed dependencies, absence of old paths and absence of
`BrowserAccess.request`.
