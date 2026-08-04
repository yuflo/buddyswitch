# S4 Context Pre-Handoff Audit

> Audit result: `CORRECTED BEFORE EXECUTION`
> Rejected preparation packet: `BS-MM-S4-CONTEXT-R1-20260804-01`
> Executable successor: `BS-MM-S4-CONTEXT-R1-20260804-02`
> Product source changed by audit: no

## 1. Why the first preparation packet was rejected

The maintainer requested a second review because S3 and S4 had already shown
that READY defects discovered by an executor are coordinating-side escaped
defects. The review found five such defects before Context implementation
began.

### F-S4-CONTEXT-P1 — manufactured structural RED

The first plan required a new future-topology architecture test to fail
against the current topology. Context is a behavior-preserving owner refactor;
the current contract is intentionally green. This repeated the Search
pre-handoff defect and contradicted `$buddyswitch-testing`.

Correction: current behavior GREEN is the entry proof. The final architecture
proof is written as part of the coherent cutover and first run only after the
runtime matches the final topology.

### F-S4-CONTEXT-P2 — cross-session evidence was not reusable

The snapshot recorded two run IDs and pass counts but omitted their canonical
commands and explicit targets. A second session could not independently prove
source/command/environment equivalence and would either trust the hub or spend
time reconstructing it.

Correction: the exact two commands, targets, runtime identity, results and
cleanup are recorded in the source snapshot. The review re-ran them unchanged:

```text
direct:   ec4ae6b40a3d4fcaa8494049c609d35c
          34 passed, 23 subtests
affected: 58658371b1244b428ea3cccfb24eb393
          68 passed, 41 subtests
```

### F-S4-CONTEXT-P3 — opaque auxiliary manifests

The first packet supplied two hashes without defining their path set,
exclusions, ordering or byte framing. They were not reproducible identities.
The exact clean product commit/tree already identifies every source and test
byte; explicit owner/proof inventories identify scope.

Correction: remove the opaque hashes. The executor verifies the product
commit/tree, docs-only preparation delta, explicit inventories and clean
starting state directly.

### F-S4-CONTEXT-P4 — assertion coverage was compressed into labels

The READY table named “direct behavior” and “affected architecture/package”
but did not show which assertions could detect each protected Context action,
rejection, runless effect and explicit-registration failure. That repeated the
proof-shape error exposed by Evidence R1.

Correction: the source snapshot now contains an assertion-level observable
matrix. It separates Context action/results from generic registry, package and
activation proof and records exact inapplicability for Context-owned state,
transport and cleanup.

### F-S4-CONTEXT-P5 — declared lifecycle contradicted the stop rule

The first copy-paste request required the declared checkout-local
reprovision/activate/verify flow after package-source edits, but then told the
executor to stop on the unqualified phrase “environment mutation.” Its
starting-identity sentence also failed to say that the no-product-delta gate
applied only before implementation. Read literally, either phrase could stop
the authorized cutover itself.

Correction: only undeclared environment mutation outside the required
reprovision flow is a stop condition. Product/test cleanliness is explicitly a
pre-mutation gate, and cleanup stops execution only when residue cannot be
attributed and restored to clean state.

## 2. Reproducible topology preflight

The hub re-ran the proposed assembly against the current installed runtime.
The probe used the old Context `DEFINITION` and `invoke` as behavior-equivalent
inputs, appended one passive Context assembly to the real component tuple,
proved duplicate fail-closed behavior with the old package present, then used
an empty temporary `env.tools` path to simulate atomic old-package removal and
dispatch the real `context.list_sources` action.

Canonical command shape:

```bash
BUDDYSWITCH_RUNTIME_DIR="$PWD/.buddyswitch-runtime" \
  .buddyswitch-runtime/venv/bin/python - <<'PY'
from __future__ import annotations
import importlib
import tempfile
from pathlib import Path

import buddyswitch.env.tools as env_tools
from buddyswitch.application.build import build_application
from buddyswitch.application.composition import COMPONENTS, DAEMON_HANDLER_ORDER
from buddyswitch.env.tool_runtime import registry
from buddyswitch.env.tool_runtime.definition import ToolRegistration
from buddyswitch.env.tools.context.tool import DEFINITION, invoke
from buddyswitch.foundation.composition import ModuleAssembly
from buddyswitch.runtime_support import env_manifest

context = ModuleAssembly(
    name="context",
    tools=(ToolRegistration(definition=DEFINITION, invoke=invoke),),
)
application = build_application(
    COMPONENTS + (context,),
    daemon_handler_order=DAEMON_HANDLER_ORDER,
)
try:
    registry.configure_tool_registrations(application.tools)
except ValueError as exc:
    assert str(exc) == (
        "tool 'context' is both explicitly registered and package-discovered"
    )
else:
    raise AssertionError("old package plus explicit Context must fail closed")

with tempfile.TemporaryDirectory() as temp_dir:
    env_tools.__path__[:] = [temp_dir]
    importlib.invalidate_caches()
    registry.configure_tool_registrations(application.tools)
    env_manifest.configure_skill_exports(application.skills)
    manifest_path = Path("src/buddyswitch/catalog/manifest.toml").resolve()
    response = registry.dispatch_env_tool_request(
        payload={"tool": "context", "action": "list_sources", "args": {}},
        active_role="dev",
        actor_id="act-dev-context-preflight",
        instance_json=Path(temp_dir) / "instance.json",
        instance_payload={
            "actor_id": "act-dev-context-preflight",
            "role": "dev",
            "workspace_dir": temp_dir,
        },
        manifest=env_manifest.load_manifest(manifest_path),
        manifest_path=manifest_path,
    )
assert [module.name for module in application.modules][-1] == "context"
assert [handler.name for handler in application.daemon_handlers] == [
    "demand_triage",
    "task_goal",
    "demand_orchestration",
]
assert [tool.definition.id for tool in application.tools].count("context") == 1
assert response.get("ok") is True
assert response.get("action") == "context.list_sources"
PY
```

Result: exit `0`; no repository, runtime record, process or persistent state
changed. This is mechanism evidence, not a substitute for the executor's
final source-bound architecture and behavior proof.

## 3. Durable ratchet

The escaped defects were moved to existing action-time owners rather than
left only in this memo:

- execution governance now distinguishes refactor GREEN from behavior RED;
- the handoff card exposes the same rule;
- Goal Packet and implementation templates require cross-session evidence to
  include explicit targets/environment and require reproducible digest framing;
- the implementation template no longer teaches every task to manufacture
  RED;
- the Context packet distinguishes declared reprovision from hidden
  environment mutation and distinguishes the starting identity gate from the
  authorized implementation delta.

No validator, evidence service, new runner or policy owner was added.

## 4. Determination

The Context architecture remains unchanged: one last-selected, read-only
module; no Public/state/tests; four accepted Public reads; three exact
Context-only host residues removed atomically. The defect was preparation
quality, not product design.

`BS-MM-S4-CONTEXT-R1-20260804-01` is rejected before execution and must never
run. Only `BS-MM-S4-CONTEXT-R1-20260804-02` may execute after the coordinating
hub supplies its docs-only preparation checkpoint.
