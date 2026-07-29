# S3 Boundary Design and Preflight

> Decision: READY
> Source: `8db3a07c4cca6423a1e2c789281a813800bfa2a9`

## 1. Selected architecture

```text
application/composition
  ├─ selects Demand assembly
  ├─ constructs Task assembly with Demand's resolver capability
  ├─ declares exact component daemon order
  └─ supplies Task's active probe to Tool runtime

Demand private ──imports──> Task Public
Task private ──depends on──> Task-owned DemandSelectionResolver port
Task private ──does not import──> Demand
```

This is dependency inversion, not a service locator. There is one concrete
wire at the composition root, one Task-owned callable contract, and no
container, discovery, requires/provides negotiation, event bus, or fallback.

The runtime call during Task creation still reaches Demand's public resolver.
The source/ownership graph remains acyclic because Task depends only on its
own stable input port. Demand already depends on Task Public for exact
attention and evidence reads.

## 2. Daemon ordering and commands

Current correct product order is:

```text
built-ins
  -> demand_triage
  -> task_goal
  -> demand_orchestration
```

Task reconciliation must precede Demand orchestration on the same Goal
notification. Contiguous module flattening cannot preserve this because the
two Demand handlers surround Task.

The product composition root therefore declares the exact three registration
names in order. Generic application build proves the order is a one-to-one
permutation of contributed handler names. Missing, duplicate, unknown, or
unlisted handlers fail before the daemon starts.

The Task Goal registration carries its optional application command factory.
The daemon host extracts factories from registrations; it never imports Task
or names `task_goal.reconcile_task`.

## 3. Narrow Web seam

S2 correctly refused a speculative Web field. S3 has a real current
consumer: Actor Console's `task_sys` section. The earned contract is therefore
only:

```python
@dataclass(frozen=True)
class ActorConsoleSectionRegistration:
    name: str
    project: Callable[[ActorIdentityProfile], Mapping[str, object]]
```

`ModuleAssembly.actor_console_sections` is the sixth and only new field.
Application build rejects invalid or duplicate names. Web owns the surrounding
Actor Console DTO and invokes each projector. Task owns only the `task_sys`
section. No module receives HTTP method, route, body, server, or Web host
objects.

## 4. Tool-host Task probe

The existing generic action metadata already expresses
`active_task_required`. S3 does not create a guard engine. Application
activation injects exactly one Task Public predicate into the existing
registry. A required check with no configured predicate fails closed.

Context Tool becomes a direct Task Public consumer. Task Tool creates its own
private Goal client from generic `instance_json`. `ToolContext` loses both the
private Task domain and `task_goal_runtime` objects.

## 5. State, packaging and tests

- Task continues to write the same files and schema through one moved owner;
- cleanup only adds discovery/attribution; host still deletes;
- existing setuptools include/exclude patterns package Task code and exclude
  Task local tests;
- the existing runner already discovers every
  `modules/*/tests/{unit,contract,integration}` root;
- Task has no Skill, so `pyproject.toml`, manifest Skill rows and Role
  projection do not change.

## 6. Pre-READY evidence

| Claim | Evidence | Result |
|---|---|---|
| current affected behavior | `4f91dbd4a7d540f2b4b0853d7e69d4b7` | 101 passed, 18 subtests |
| remaining direct consumers/fixtures | `ee6bf076007c400588c7aaccab9c5a12` | 228 passed, 287 subtests |
| clear/resume daemon preservation | `1361ebd113804bf8826674b519ec352c` | 1 passed |
| wrong-node history retained | `d5c442f630834ac59a908ec3a82abf1a` | exit 4, no tests; not evidence |
| explicit Demand capability injection | `S3P-b6123b04` | PASS |
| acyclic compile-time product graph | `S3P-b6123b04` | PASS |
| exact interleaved daemon order | `S3P-b6123b04` | PASS |
| Task command factory co-owned by registration | `S3P-b6123b04` | PASS |
| unique Actor Console section | `S3P-b6123b04` | PASS; duplicate rejected |
| Tool/CLI/cleanup contribution uniqueness | `S3P-b6123b04` | PASS |
| Task package included, local tests excluded | `S3P-b6123b04` | PASS |
| old sources present and final root absent | `S3P-b6123b04` | PASS |

The preflight used only in-memory contract objects and current read-only
source/path checks. It created no repository file, runtime, process, socket,
lock, or test root.

## 7. Rejected alternatives

1. Direct Task Public -> Demand Public plus Demand Public -> Task Public
   imports: rejected as a component cycle.
2. Hidden `importlib`, ToolContext service lookup, universal DI, event bus, or
   capability registry: rejected as concealed coupling and speculative
   infrastructure.
3. Removing current Demand validation from Task create: rejected as a behavior
   change.
4. Making Demand complete Task or Task complete Demand: rejected as ownership
   collapse.
5. Numeric daemon priority or generic before/after graph: rejected because
   one explicit current product order is simpler and more legible.
6. A general Web route plugin: rejected because only one Actor Console section
   is currently earned.
7. Leaving central Task CLI/Web/Daemon switches until S5: rejected because S3
   would not deliver private Task change locality.
8. Adding Task checkpoint or Skill surfaces: rejected because neither is a
   current product contract.

## 8. Residual implementation risk

Only execution risk remains:

- exact import and path movement;
- routing root cross-component setup through one test-only Task fixture
  adapter instead of spreading private imports;
- application build validation and registration wiring;
- preserving handler identity/order and mailbox command behavior;
- removing Task objects from generic ToolContext without changing envelopes;
- keeping external CLI/Web DTOs byte-for-shape compatible;
- installed runtime reprovision before the first post-mutation test;
- complete old-path and process cleanup.

Every item has a direct proof in the implementation plan. No architecture
choice is delegated to the executor.
