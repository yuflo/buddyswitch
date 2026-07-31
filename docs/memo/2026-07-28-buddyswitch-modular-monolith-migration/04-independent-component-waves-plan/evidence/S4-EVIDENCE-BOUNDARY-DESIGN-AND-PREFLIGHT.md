# S4 Evidence Boundary Design and Preflight

## 1. Final owner

The final live root is:

```text
src/buddyswitch/modules/evidence/
  __init__.py
  module.py
  private/
    __init__.py
    adapters/
      __init__.py
      tool/
        __init__.py
        tool.py
        _impl.py
  entrypoints/
    __init__.py
    browser_evidence.py
```

Evidence is a stateless capability component. It contributes one Tool through
the existing typed `tools` field and is selected once by application
composition after Artifact and Track.

Evidence has no Public package because no current component consumes an
Evidence-owned operation. Adding one without a current consumer is forbidden.

## 2. Dependency direction

```text
consumer -> Runtime Broker -> explicit Evidence Tool registration
Evidence Private -> Artifact Public -> Artifact Private
stable application entrypoint -> Evidence-owned command adapter
application composition -> Evidence passive assembly
```

Forbidden edges:

```text
Evidence -> Artifact Private
Evidence -> Browser lifecycle/private code
Artifact -> Evidence
generic host -> Evidence Private
registry discovery -> old Evidence package
```

The word `browser` in the action and command names is protected external
vocabulary, not an architectural dependency. Browser foundation is unchanged.

## 3. Exact cutover

The replacement is atomic:

1. create the physical Evidence owner and passive Tool assembly;
2. select it once in `application/composition.py`;
3. redirect the stable application command to the module entrypoint;
4. delete `src/buddyswitch/env/tools/evidence`;
5. delete `src/buddyswitch/runtime_support/browser_evidence.py`;
6. delete only the two unused Evidence-shaped `BrowserAccess` methods;
7. retain `BrowserAccess.status`;
8. add current architecture and absence/dependency proof.

No alias, compatibility import, dynamic fallback, dual registration, plugin
loader, DI container, bus, new ModuleAssembly field, token repository, or
Browser port is permitted.

## 4. Test ownership

No current Evidence test is a true single-module test:

- Tool behavior crosses Artifact Public, Tool runtime, Role authority, and
  Runtime Broker;
- Market evidence crosses Artifact persistence and Evidence;
- the CLI test crosses the installed entrypoint and Runtime Broker;
- topology proof crosses module, composition, host, and package boundaries.

They therefore remain under root `tests/**`. This follows D-019/D-020 and does
not create an empty module-local test tier.

## 5. Representative topology preflight

Preflight `EVIDENCEP-20260731-01` ran against the verified installed runtime.
It constructed a passive Evidence `ModuleAssembly` from the current
`DEFINITION` and `invoke`, appended it to the accepted component list, and
proved:

| Claim | Result |
|---|---|
| existing `tools` contribution accepts Evidence | PASS |
| final order `demand, task, search, artifact, track, evidence` builds | PASS |
| Evidence appears once as module and Tool | PASS |
| no Daemon/CLI/Skill/cleanup/Web/inbound contribution is required | PASS |
| old discovered Evidence plus explicit Evidence fails closed | PASS |
| simulated old-package removal makes explicit definition/actions available | PASS |
| Daemon ordering remains unchanged | PASS |

Observed marker:

```text
EVIDENCE_TOPOLOGY_PREFLIGHT_OK
module_order=demand,task,search,artifact,track,evidence
tool_count=6
```

The duplicate-old/new rejection was exact:

```text
tool 'evidence' is both explicitly registered and package-discovered
```

This proves the selected mechanism and atomicity. It does not replace the
executor's source-bound architecture RED/GREEN or consumer proof.

## 6. Acceptance matrix

| Proof class | Required outcome |
|---|---|
| Product | both Evidence actions and stable command preserve observable results |
| Contract | schemas, authority, errors, Native MCP, affordances, transient metadata exact |
| Architecture | one physical owner, one explicit assembly, Artifact Public only, no Browser dependency |
| Replacement | old Tool/runtime-support paths and host placeholders absent and undiscoverable |
| Operations | installed distribution current; no token persistence; no process/socket/temp residue |

Correspondence is covered by the existing complete source/wheel equality
proof. Mutation/cleanup is inapplicable to Evidence state because the
capability persists none; tests must still prove no product mutation on
success or rejection and clean Runtime Broker/CLI resources.
