# S4 Evidence R2 Continuation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use
> `superpowers:executing-plans` and the complete `$buddyswitch-testing` skill.
>
> Plan state: `READY — R2 ONLY`

**Goal:** Complete the preserved Evidence cutover by repairing and proving the
stable Runtime-Broker-backed command terminal loop.

**Architecture:** R2 keeps the R1 module/composition/replacement candidate
intact. Evidence ToolResult remains the sole response owner; the module-owned
command adapter validates and prints that canonical result. A root process
test crosses the installed stable entrypoint and a real Runtime Broker.

**Tech Stack:** Python 3.13, BuddySwitch installed runtime, Unix Runtime
Broker, the public `./buddyswitch-test` runner.

---

## 1. Fixed outcome

Acceptance is:

> An Actor can successfully issue and approve transient Artifact-scoped
> Evidence metadata through the installed stable command and real Runtime
> Broker, receives canonical ToolResult JSON with exact exit mapping, and the
> preserved Evidence module remains the sole physical and composed owner.

```text
installed stable command
  -> real Runtime Broker
    -> explicitly composed Evidence Tool
      -> Artifact Public scope decision
        -> canonical ToolResult JSON + exact process exit
```

## 2. Preserved candidate and scope

R2 consumes the exact R1 candidate. It does not roll back, replay, recopy or
reformat the structural cutover.

Allowed executable writes are exactly:

| Path | Class | Allowed result |
|---|---|---|
| `src/buddyswitch/modules/evidence/entrypoints/browser_evidence.py` | OWNER/ADAPTER | remove the nonexistent `feedback` requirement; validate `ok` and successful `tool_evidence`; return the canonical Broker ToolResult without a second schema |
| `tests/process/browser/test_browser_evidence_cli.py` | PROOF | add real-Broker success, business-rejection, unavailable-Broker, exit/JSON and cleanup proof |

The already-dirty R1 candidate files may remain dirty but may change only if
an exact focused failure proves an owner defect and the hub first classifies
that write. No such additional write is currently known or authorized.

Forbidden: Evidence Tool semantics/schema, Artifact Public/private/state,
Runtime Broker/client/protocol/lifecycle, Browser, composition order, generic
host contracts, another test helper/framework, Communication, Context, S5,
compatibility, fallback, master acceptance, commit or push.

## 3. Protected behavior

Preserve:

- stable module command and `issue` / `approve-downgrade` argument names;
- Artifact-only target type and non-empty downgrade reason;
- real Runtime Broker transport;
- canonical Evidence ToolResult fields and Tool rejection meaning;
- `durability=transient`, `mutates_product_state=false`;
- exit `0` only when `ok=true`, otherwise exit `1`; argparse remains exit `2`;
- no durable Evidence object or product-state mutation on rejection/error.

There is no protected successful `feedback` field: the current canonical
ToolResult owner never emits one, and the command's requirement made success
unreachable.

## 4. Pre-READY assertion inventory

| Observable result | Hub evidence | Can detect broken terminal loop? | R2 proof write |
|---|---|---:|---|
| successful `issue` | real Broker returns canonical success; stable command currently exits 1 | YES | classified |
| successful `approve-downgrade` | same shared adapter defect and canonical Tool result | YES | classified |
| missing Artifact rejection | real Broker command exits 1 with `E_EVIDENCE_PAYLOAD` | YES | classified |
| Broker unavailable | stopped Broker command exits 1 with `E_RUNTIME_BROKER_UNAVAILABLE` | YES | classified |
| cleanup | socket and pid identity absent after stop | YES | classified |

The two hub probes and exact outputs are recorded in
`S4-EVIDENCE-R1-RETURN-AND-ROOT-CAUSE-REVIEW.md`.

## 5. Execution tasks

### Task R2.0 — Consume identity without replay

- [ ] Verify R1 is consumed and no FINAL exists.
- [ ] Verify the supplied preparation commit changes coordinating documents
      only relative to the R1 return.
- [ ] Verify candidate tracked/index/untracked identity against the R2 Goal
      Packet.
- [ ] Verify installed candidate source digest and clean resource state.
- [ ] Record the R1 direct/affected GREEN and the missing consumer proof; do
      not rerun R1 or recreate its structural RED.

An unexplained identity difference or unclassified executable path stops.

### Task R2.1 — Add the terminal-loop RED

- [ ] Extend only
      `tests/process/browser/test_browser_evidence_cli.py`.
- [ ] Use the installed `PYTHON`, an isolated `RuntimeWorkspaceTestCase`
      workspace, active Market Task, active-actor-authored Artifact and a real
      Runtime Broker process.
- [ ] Register/capture the Broker process and owned socket/pid/identity/marker
      before relying on cleanup; stop it in `finally`.
- [ ] Assert both successful commands, business rejection, Broker
      unavailability, JSON fields, exit codes and absence of durable Evidence
      state.
- [ ] Run the exact new process node(s) through
      `./buddyswitch-test focused`.

Expected RED on the preserved candidate:

```text
successful issue/approve exits 1
E_RUNTIME_BROKER_UNAVAILABLE
"runtime broker ... payload is invalid"
```

The RED is invalid if it fails before the real Broker/command boundary or
leaves a resource.

### Task R2.2 — Repair the owning adapter

- [ ] Modify only the module-owned command adapter.
- [ ] Keep Broker and Tool owner responses unchanged.
- [ ] Require a response object with boolean `ok`.
- [ ] On success require `tool_evidence` and return the canonical response
      object; do not synthesize `feedback`, compatibility fields or fallback.
- [ ] Keep existing structured RuntimeBrokerError mapping and exit behavior.
- [ ] Rebuild/install/activate/verify because package source changed.
- [ ] Run the exact RED node(s) to GREEN.

### Task R2.3 — Reprove the preserved candidate

- [ ] Dynamically select direct Evidence Tool, Market, stable command and
      Evidence architecture targets.
- [ ] Dynamically select affected Runtime Broker, Tool schema/semantic,
      Native MCP, composition, package correspondence and root architecture
      targets invalidated by the adapter/test change.
- [ ] Run focused direct and affected proof through the public runner.
- [ ] Prove retired Evidence paths remain absent from checkout and installed
      distribution.
- [ ] Prove `git diff --check` and global process/socket/test-root cleanup.

The executor owns runner-valid target construction. It does not own proof
reduction or a new semantic decision.

### Task R2.4 — Frozen FINAL

- [ ] Freeze source/diff/runtime identities only after focused proof and
      cleanup are clean.
- [ ] Run `./buddyswitch-test full` exactly once.
- [ ] Make no executable/test/package mutation after FINAL.
- [ ] Return the complete R2 result whether FINAL passes or fails.

## 6. Stop conditions

Stop and return once if:

- canonical ToolResult, Runtime Broker or Artifact semantics must change;
- another executable/test path is required;
- a real external consumer requires a different success response;
- the real-Broker RED cannot be made deterministic with existing process
  ownership and cleanup infrastructure;
- source/runtime correspondence or cleanup is invalid;
- focused proof has an unexplained failure;
- FINAL fails.

Do not issue or execute another Evidence repair packet locally.

## 7. Required return

Return:

```text
Packet and preparation identity
Preserved R1 candidate identity
Exact new RED command/run/result
Exact adapter repair
Runtime reprovision/verification identity
Direct and affected focused commands/run IDs/results
Every failure/timeout/flake/residue signal and owning disposition
Successful issue and approve JSON/exit observations
Business rejection and Broker error JSON/exit observations
Architecture/replacement proof
Process/socket/pid/test-root cleanup
Frozen FINAL command/run/result
Changed files after R1
Omitted checks and residual risk
Proposed ACCEPTED / REJECTED
```
