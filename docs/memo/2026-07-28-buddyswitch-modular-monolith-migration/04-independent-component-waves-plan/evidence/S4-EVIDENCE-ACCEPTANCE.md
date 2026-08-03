# S4 Evidence Capability Lane Acceptance

> Decision: `ACCEPTED`
> Structural packet: `BS-MM-S4-EVIDENCE-R1-20260731-01`
> Terminal-loop repair: `BS-MM-S4-EVIDENCE-R2-20260731-01`
> Authority: coordinating hub
> Acceptance date: 2026-08-03
> Next boundary: Communication source refresh only

## 1. Accepted outcome

The Evidence acceptance sentence is true:

> Evidence is physically aggregated under one stateless capability root,
> selected exactly once by application composition, consumes only Artifact
> Public for target scope, preserves its Tool and stable broker-backed command
> results, and leaves no Evidence implementation or placeholder in shared
> technical hosts.

The accepted path is:

```text
Actor or stable command
  -> Runtime Broker / generic Tool registry
    -> explicitly composed Evidence Tool
      -> Artifact Public target and active-author validation
        -> canonical transient ToolResult
```

Evidence owns no durable state, Public package, Browser lifecycle, daemon
handler, Web route, CLI contribution, cleanup contribution, compatibility
surface, fallback or alternate response schema.

## 2. Frozen candidate identity

Before writing this non-executable acceptance record, the coordinating hub
reproduced the executor's frozen candidate identity:

```text
worktree:
  /Users/chen/Dev/buddyswitch/.worktrees/fea-tool
branch:
  fea-tool
HEAD:
  2961725f65424756ffde7a8c4758177fb18cd1fc
tracked binary patch SHA-256:
  b19a15948ea5fe95d3229fa15dc2bd8834f7ec8f9fa5bf11b4a193bc38ec2e54
index patch SHA-256:
  e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
untracked files:
  11
untracked sorted path-list SHA-256:
  a357d1fef183de927c4cd468c91260092591d889d0b687ae589ab8011bcaf703
untracked content-manifest SHA-256:
  4411a34c9d734cf9a2226f9e92c90c87255ec4eecf71208de75b142475044b91
git diff --check:
  clean
```

The R2 result packet, frozen FINAL, post-FINAL audit and hub review refer to
this same executable/test/runtime identity. This acceptance record and its
ledger projections do not alter that candidate.

## 3. Product and contract proof

| Material claim | Consumer path | Evidence | Result |
|---|---|---|---|
| `evidence.issue_browser` returns the canonical transient result | stable command -> real Broker -> Evidence Tool | exact `2635192605a349a5af7b8c538af5daa6`; direct `24583e9ddefe441e94482b5d5e962993`; FINAL | PASS |
| `evidence.approve_downgrade` returns the canonical transient result | stable command -> real Broker -> Evidence Tool | exact, direct and FINAL | PASS |
| Missing Artifact is a business rejection with no effect | Artifact Public validation -> `E_EVIDENCE_PAYLOAD`, exit 1 | process proof and FINAL | PASS |
| Unavailable Broker is an operational failure with no effect | stable command -> Broker transport error -> `E_RUNTIME_BROKER_UNAVAILABLE`, exit 1 | process proof and FINAL | PASS |
| Invalid target type remains an argparse rejection | stable command parser -> exit 2 | process proof and FINAL | PASS |
| Existing Evidence Tool, market-evidence and shared host behavior remain exact | generic registry/Context/Native MCP/Broker consumers | affected `12643e9d7351457c9b2485eaecbe3228`; FINAL | PASS |

Successful `issue` and `approve-downgrade` results preserve the canonical
Broker `ToolResult` unchanged. They contain `tool_evidence`, do not synthesize
the nonexistent `feedback` field, declare transient durability and leave the
durable state snapshot unchanged. Rejections expose the existing failure
envelope and create no undeclared effect.

## 4. Architecture proof

The accepted candidate has:

- one physical owner at `src/buddyswitch/modules/evidence/**`;
- one passive `EVIDENCE` `ModuleAssembly` selected once by application
  composition;
- one Tool contribution and no dynamic duplicate registration;
- a dependency on Artifact Public and generic runtime contracts only;
- no Evidence Public package because there is no current cross-component
  Evidence-operation consumer;
- no Browser lifecycle or Artifact Private dependency;
- no Evidence-specific field or behavior in generic ToolContext/BrowserAccess;
- one stable application entrypoint delegating to the Evidence-owned command
  adapter;
- root-owned cross-component, process and architecture proof through the one
  public test runner.

Composition order remains:

```text
demand -> task -> search -> artifact -> track -> evidence
```

Daemon order and all non-Evidence component contributions remain unchanged.

## 5. Replacement and residue proof

`R-EVIDENCE-001` is closed completely. The Evidence portions of
`R-FND-002`, `R-FND-003`, `R-FND-011`, `R-FND-012` and `R-DOC-002` are closed.

Retired live implementation paths are absent from the checkout, installed
package and wheel record:

```text
src/buddyswitch/env/tools/evidence/**
src/buddyswitch/runtime_support/browser_evidence.py
```

The unused Evidence-shaped `BrowserAccess` methods are absent while current
Browser status remains foundation truth. Historical memos and scoped negative
guards may name retired paths only as history or absence proof.

## 6. Verification evidence

Expected defect RED:

```text
command:
  ./buddyswitch-test focused \
    tests/process/browser/test_browser_evidence_cli.py::TestBrowserEvidenceCli::test_stable_command_returns_canonical_success_for_issue_and_approve \
    tests/process/browser/test_browser_evidence_cli.py::TestBrowserEvidenceCli::test_stable_command_maps_rejection_and_unavailable_broker
run:
  cf5c1a0d33894992be3bea5238ee87cf
result:
  2 failed, 2 passed for the nonexistent-feedback mismatch
cleanup:
  run root and attributable Broker resources absent
```

Exact GREEN used the same command:

```text
run:
  2635192605a349a5af7b8c538af5daa6
result:
  2 passed, 2 subtests; exit 0
cleanup:
  run root and attributable Broker resources absent
```

Direct GREEN:

```text
command:
  ./buddyswitch-test focused \
    tests/integration/env_tool/test_evidence.py \
    tests/integration/browser/test_market_evidence.py \
    tests/process/browser/test_browser_evidence_cli.py \
    tests/unit/architecture/test_evidence_component_boundaries.py
run:
  24583e9ddefe441e94482b5d5e962993
result:
  17 passed, 2 subtests; exit 0
cleanup:
  run root and attributable Broker resources absent
```

Affected GREEN/IMPACT:

```text
run:
  12643e9d7351457c9b2485eaecbe3228
result:
  179 passed, 559 subtests; exit 0
cleanup:
  run root and attributable Broker resources absent
```

Frozen FINAL:

```text
command:
  ./buddyswitch-test full
run:
  9ffe775dd313446dad2b17b0aa0aab26
result:
  Unit Python 458 passed, 1,119 subtests
  Unit JavaScript 147 passed
  Integration 761 passed, 442 subtests
  Process 264 passed, 376 subtests
  System 22 passed
  shell syntax PASS
  diff check PASS
  exit 0
cleanup:
  run root, Broker resources and attributable processes absent
```

FINAL ran once. No executable, test, fixture, runner, package or runtime
mutation occurred afterward. The hub reproduced the frozen identity and reused
the valid evidence instead of rerunning the repository-wide suite.

## 7. Contrary evidence disposition

| Signal | Owning diagnosis | Disposition | Resolved |
|---|---|---|---|
| R1 stopped before FINAL | protected stable command had no real Broker terminal-loop proof | R1 consumed; hub preflight and R2 added the missing product-boundary proof | YES |
| Real Broker preflight rejected successful canonical results | command adapter required nonexistent `feedback` | R2 selected canonical ToolResult as sole owner and removed the false requirement | YES |
| Initial R2 GREEN/direct/affected runs became stale | reviewer found Broker cleanup might be skipped during setup failure | test lifecycle owner repaired with exception-safe `finally`; all affected proof rerun | YES |
| First provisioning and process prechecks were rejected/noisy | command/probe construction errors before product execution | bounded commands replaced them; no checkout or runtime pollution occurred | YES |
| Two pre-existing ignored cache directories remain | unrelated state predating R2 | preserved and excluded from Evidence attribution | YES |

There is no unexplained FINAL failure, flake, timeout, no-test result,
undeclared dependency, hidden environment mutation or attributable cleanup
residue.

## 8. Runtime and operations

```text
activated_at:
  2026-07-31T09:22:16.244005Z
source_digest:
  cf8909b292e0a31c0ba0d4819594185d2bb06d9a7c5e20031e69ea3464d0d5ca
distribution_digest:
  682351bc4b12e19067e0c98f8dc0595dee7c23de81d33662d815b2e42dbb6aca
package:
  buddyswitch 0.1.0
runtime.verify:
  ok=true
```

The process proof captures the real Broker identity before cleanup and stops
the owner before removing identity/socket state. Current inspection found no
`bs-test-*` root or attributable Broker process/socket/PID/marker resource.

## 9. Current documents

Executable truth is reflected in:

```text
README.md
docs/arch/evidence-capability-architecture.md
docs/arch/daemon-service-architecture.md
```

No current guidance teaches a retired Evidence implementation root or the
removed `feedback` result requirement.

## 10. Omitted checks and residual risk

No manual duplicate command invocation was run outside the public runner; the
process test already exercises the installed stable command and real Broker.
No second FINAL was run because the accepted candidate identity remained
unchanged. The two pre-existing ignored cache directories were not removed.

Residual implementation risk within this lane: none identified.

## 11. Acceptance and next boundary

Product, Contract, Architecture, Replacement and Operations proof all pass,
and every contrary signal has an owning resolved disposition.

Evidence is therefore `ACCEPTED`. R1 and R2 are consumed permanently and must
not resume. This record authorizes only:

```text
checkpoint accepted Evidence
  -> refresh Communication source, consumers and worker-lifecycle facts
    -> design and preflight the smallest complete Communication boundary
      -> issue a new packet only after READY review
```

It does not authorize Communication implementation, Context, S5, S6 or S7.
