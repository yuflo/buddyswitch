# S2 Boundary Design and Preflight

> Decision: READY
> Source: `28ca25d93b84c0165fa4cd6f92744744c1df5d67`

## 1. Selected architecture

```text
modules.demand.module.DEMAND
  -> passive ModuleAssembly
    -> application current component set (DEMAND,)
      -> typed Daemon / Tool / CLI / Skill / cleanup contributions
        -> generic hosts
```

The application knows the Demand module once. It never names a Demand
handler, Tool, command, Skill or cleanup planner. Generic hosts know only their
own registration type. `module.py` is passive: no scan, import hook, lifecycle,
service locator, bus, dependency negotiation or runtime side effect.

## 2. Frozen contracts

### Module and application

`foundation/composition` owns:

```python
@dataclass(frozen=True)
class ModuleAssembly:
    name: str
    daemon_handlers: tuple[DaemonHandlerRegistration, ...] = ()
    tools: tuple[ToolRegistration, ...] = ()
    cli_commands: tuple[CliCommandRegistration, ...] = ()
    skills: tuple[SkillExport, ...] = ()
    cleanup: tuple[CleanupContribution, ...] = ()
```

`application/composition.py` imports only `DEMAND` and defines the one current
component tuple. `application/build.py` validates and flattens it. Duplicate
module, Tool, daemon handler, CLI command, Skill or cleanup category fails
before a host starts.

No Web field is added because Demand has no current Web contribution.

### Daemon

`launcher/daemon_contracts.py` owns:

```python
@dataclass(frozen=True)
class DaemonHandlerRegistration:
    name: str
    factory: Callable[[], DaemonHandler]
```

The instance host merges current unmigrated handlers with injected
registrations. It validates names and factories without importing Demand.

### Tool

`env/tool_runtime/definition.py` owns:

```python
@dataclass(frozen=True)
class ToolRegistration:
    definition: ToolDefinition
    invoke: ToolInvoke
```

The application configures exact registered component Tools before dispatch.
The current scanner remains only for unmigrated Tools until S5. The old
`env/tools/demand_sys` directory is deleted, so Demand has one registration.
Duplicate explicit/discovered IDs and invalid explicit registrations fail;
they are never silently omitted.

The existing one-use Side capability becomes the generic invocation fact
`bound_capability`. Its environment source is declared by the registered
action metadata. Native MCP, registry and `ToolContext` contain no Demand
branch or Demand application class. The Demand adapter calls Demand private
domain/runtime directly using generic Actor, instance, thread and capability
facts.

### CLI

`launcher/cli_contract.py` owns a named command registration with exact help
rows and a handler returning the existing machine-result shape. The generic
CLI validates duplicates, renders contributed help, dispatches by command
name, and contains no Demand read import or Demand branch.

### Skill

`runtime_support/skill_contracts.py` owns:

```python
@dataclass(frozen=True)
class SkillExport:
    id: str
    package_path: str
    enabled_by_default: bool = True
```

The application supplies component exports to the current manifest/Actor
projection. The two central Demand Skill path rows are removed; Role rows keep
selecting the same IDs until S6. Actor config derives the disabled triage
default from the export. Side-specific enable/disable overrides remain Demand
private behavior.

### Cleanup

The cleanup host owns:

```python
@dataclass(frozen=True)
class OwnedStatePath:
    relative_path: str
    owner_role: str | None

@dataclass(frozen=True)
class CleanupContribution:
    category: str
    discover: Callable[[Path], tuple[OwnedStatePath, ...]]
```

Demand discovers only its canonical actor aggregate files. Role cleanup
selects exact attributed role paths and warns for unattributed malformed
state. All-data selects every Demand candidate, including malformed JSON.
The host rejects absolute, escaping or symlink-bound targets and performs
deletion. Demand does not delete paths itself.

## 3. Pre-READY evidence

| Claim | Evidence | Result |
|---|---|---|
| current positive Demand product behavior | `1ae2966bf66f4616afad03e4e955066a` | 92 passed, 65 subtests |
| current cleanup/CLI behavior | `298084964b1f463ab94c15f71171dffd` | 7 passed |
| current negative local-test boundary | `c6fae094fda84117abf9ba27a69916b5` | exact exit 2: outside root tests |
| proposed local-test runner mechanism | `S2R-etz5nsrl`, run `6b4a815bb9cf46fd8dc84d315efce9e8` | 1 passed through copied public wrapper; clean |
| final topology/package/activation | `S2P-uyunx4fg` | 12 runtime/Skill paths mapped; wheel/install/activation/import PASS |
| duplicate/invalid application assembly | `S2P-uyunx4fg` | both rejected before host use |
| module Skill/test distribution | `S2P-uyunx4fg` | Skill present; module tests and old Tool path absent |
| cleanup attribution/path safety | `S2C-m_jup0nj` | PM 1, malformed warning 1, all-data 3, escape rejected |

The first two topology attempts are not acceptance evidence. They exposed
macOS `/var` versus `/private/var` and symlink-resolved venv interpreter
identity mismatches; the unchanged fail-closed activation contract rejected
both. The accepted probe fixed only fixture identity by using canonical
`/private/tmp` and the literal `venv/bin/python`.

Every accepted fixture root and public test root was removed.

## 4. Correspondence

The isolated final topology maps ten Demand Python owner paths plus two Skill
directories, deletes the old locations before build, includes the module Skill
in the wheel, excludes module tests, installs non-editably, activates with
exact source/distribution correspondence, imports the assembly, and rejects
duplicate/invalid modules.

Executor implementation must additionally preserve exact behavior through
the frozen source tests. The preflight does not permit stub contributions in
production.

## 5. Rejected alternatives

1. Product directory discovery: rejected by D-010/D-011.
2. A universal plugin/DI/event framework: rejected by D-018.
3. Keeping central Demand handler/Tool/Skill lists: rejected because private
   change locality would remain false.
4. Keeping old and new Demand registrations together: rejected by Sharp
   Forward and the S2 charter.
5. Moving only files and deferring Host cleanup to S5: rejected because S2
   would not satisfy its acceptance sentence.
6. Creating speculative Web or broad Public facades: rejected because no real
   consumer exists.

## 6. Residual implementation risk

Remaining risk is private execution work:

- exact import rewrites;
- keeping generic Tool catalog behavior while one Tool becomes explicit;
- building manifest Skill rows from application exports;
- preserving CLI help/error ordering;
- integrating cleanup paths into the existing plan result;
- installed-runtime reprovision after package inputs change.

These are detectable by the frozen proof map. No semantic owner, data
identity, host contract, packaging mechanism or composition decision remains
for the executor.
