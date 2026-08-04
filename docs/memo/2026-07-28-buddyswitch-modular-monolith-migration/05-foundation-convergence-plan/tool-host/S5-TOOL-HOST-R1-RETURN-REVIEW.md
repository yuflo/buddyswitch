# S5 C1 ToolHost R1 Return Review

## Disposition

`REPAIR REQUIRED — PRESERVE CANDIDATE`.

Packet `BS-MM-S5-TOOLHOST-R1-20260804-01` is consumed. Its returned candidate
is the sole base for R2: do not roll it back, replay the migration, restore old
paths or begin C2.

The implementation is runnable and most of C1 is correct. Hub review accepts
the returned source/evidence identity, but not the proposed `ACCEPTED`
disposition because the C1 acceptance sentence is not yet true.

## Source and evidence admission

The hub reproduced the returned candidate:

- HEAD `8a6369222c702aea6ec430a41524cdad4a9aaf15`;
- executable tracked patch
  `1874dc3da2dd08a9071b4b8239bd8ef20a7715823920d5fec6c60dc62b4a6172`;
- empty index;
- untracked source path-set
  `c05e13b9ab52100a1b12942bd9a34071d1d5e5a65152727aa36cc2097d45c4c5`;
- untracked source path/content manifest
  `8bafab31299c81432c6719ce8e1441fc74c92324ace56fc8e979d524d3751710`;
- installed source digest
  `a9dac2d4e908c54b3a0c41fe3f32a40f87e189028235e208a8491de442f7a09a`;
- distribution digest
  `13f092514a75414cc7779bc77f1b1672d2ff02c37b6f47ddde896725597a953a`;
- runtime activation time `2026-08-04T08:25:32.080161Z` and verify
  `ok=true`;
- clean `git diff --check`, empty index and no attributable test/runtime
  residue.

R1's exact, affected, real-Broker and single frozen FINAL evidence is valid for
that candidate and supplies the R2 refactor baseline. Do not rerun it merely
because the executor changes. Any R2 executable/test mutation invalidates only
the affected evidence and the frozen FINAL as defined by the testing contract.

## Accepted C1 outcomes

The candidate already establishes:

- application-selected explicit registrations for all eight current Tools;
- Foundation ToolHost with no component or Role implementation import;
- Role authorization supplied by application composition;
- no package scanner, dynamic Tool import or retired ToolHost source path;
- generic Daemon transport at the Foundation boundary;
- Artifact's explicit Actor-private root and Evidence's host time fact;
- preserved native MCP, Broker, authorization, task gate, result and cleanup
  behavior on the returned identity.

R2 must preserve these outcomes rather than reproduce them.

## Acceptance gaps

### 1. ToolContext is not yet minimal

The returned `ToolContext` still exposes `active_actor`, `active_role` and
`new_id()`. Current source has no production consumer for `active_actor` or
`new_id()`. The only attribute consumer of `active_role` is a new process test;
current product Tools use the real `role_id` fact or the still-current Mapping
projection.

A test written to call an otherwise unused alias is not consumer evidence. The
R1 plan's statement that the ID helper was consumed was a coordinator fact
error.

### 2. Discovery-shaped residue remains after discovery removal

`semantic_contract_errors()` now derives an always-empty result and is used
only by a test. Tool dispatch failure guidance still directs the consumer to
inspect catalog load errors even though explicit registration has removed
runtime package loading. Both surfaces teach the retired discovery model.

### 3. The planned Broker facade had no earned contract

`foundation/tool_runtime/broker_client.py` is a zero-consumer re-export while
the current CLI and MCP host call the actual Runtime Kernel client directly.
The R1 source snapshot called this a stable adapter without proving a current
consumer or protected external contract. That classification was a
coordinator error, not an external compatibility obligation.

### 4. The escaped condition had no direct proof

R1 architecture tests prove final location, forbidden imports, explicit
registration and two narrow consumer substitutions, but do not prove the exact
earned ToolContext/ToolHost surface. This allowed tests and a dead facade to
preserve residue while all suites passed.

## Root cause and process correction

The primary failure is the coordinator's handoff model: path-level hypotheses
were transmitted as implementation commands, then reviewed against repository
facts only after execution. The executor also should have challenged the
acceptance contradiction, especially the test-only alias, but R2 must not
repeat the same scripted packet model.

Decision D-059 and root `AGENTS.md` now enforce:

- a packet owns outcome, semantic authority, protected contracts and proof;
- the executor owns implementation inside that authority boundary;
- repository facts override memo path examples;
- tests cannot manufacture a consumer for dead production surface;
- local ambiguity is resolved by the executor; only real boundary expansion or
  protected semantic change stops execution.

## R2 disposition

R2 is a bounded C1 completion, not a new migration and not patch-on-patch
feature development. The preserved candidate remains the base. The executor
audits and closes all residue of the same class within the ToolHost boundary,
adds the nearest enforceable proof and returns one final C1 candidate. C2–C7
and S6 remain blocked.
