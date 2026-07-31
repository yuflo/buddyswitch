# S4 Evidence R1 Return and Root-Cause Review

> Review state: `ACCEPTED AS REJECTED`
> Consumed packet: `BS-MM-S4-EVIDENCE-R1-20260731-01`
> Preserved candidate: structural Evidence cutover on
> `4184211435778e2168bd198215ea4ad730d31cf4`

## 1. Disposition

The executor stopped correctly and FINAL remained unrun. R1 is permanently
consumed. Its structural candidate is preserved; its READY claim and protected
stable-command preservation claim are rejected.

The candidate already proves the intended physical owner, explicit
composition, Artifact Public dependency, old-path deletion, host-placeholder
removal and installed-package correspondence. No Evidence source migration is
replayed in R2.

## 2. Coordinator defect

R1 classified the stable command as protected and claimed that direct run
`244e12758d9f41bebe4bd3754ab1f163` covered “stable CLI behavior.” The reviewed
process test actually asserted only:

- `issue --help` returns zero and lists Artifact;
- argparse rejects `--target-type memory`.

It did not start Runtime Broker, invoke either successful action, observe a
Tool rejection, or prove JSON/exit mapping. The READY review then incorrectly
stated that the production write set was complete and every private risk was
detected.

This was not an executor implementation failure. The coordinating hub used a
test filename, scope label and pass count as a proxy for assertion-level
consumer proof, then froze scope before auditing the terminal loop.

## 3. Hub preflight and latent product defect

Source identity for both probes:

```text
HEAD: 4184211435778e2168bd198215ea4ad730d31cf4
candidate tracked patch:
  2fc9cb4e249da3d8affc4c81ae7241253be2e82ebdb23b6cda757ffb209a6d5e
candidate untracked content manifest:
  26262898c0263407ead137c9b1e1c740240217f1f6f12777e7f6ee3a10409ccd
installed candidate source digest:
  1f9765b7f4bbf1b9236ec7340279eaf84cf693f4aeebee78b6cc875064b13010
```

Preflight `EVIDENCE-CLI-PREFLIGHT-20260731-01` used an isolated runtime
workspace, an active Market Task, an active-actor-authored Artifact, the real
installed Runtime Broker process and the stable installed command.

Observed canonical Broker success:

```text
ok=true
action=evidence.issue_browser
durability=transient
state_changed=true
mutates_product_state=false
tool_evidence=<object>
feedback=<absent>
```

Observed stable command success attempt:

```text
exit=1
error.code=E_RUNTIME_BROKER_UNAVAILABLE
error.message="runtime broker evidence payload is invalid."
```

The command adapter requires `response["feedback"]`, but canonical
`tool_results.success` has no `feedback` field. The same mismatch affects
`issue` and `approve-downgrade`. The pre-migration command contained the same
defect, which the old process test never detected.

Negative preflight `EVIDENCE-CLI-PREFLIGHT-20260731-02` proved:

```text
missing Artifact:
  exit=1
  error.code=E_EVIDENCE_PAYLOAD
  state_changed=false
  tool_evidence absent

stopped/missing Broker:
  exit=1
  error.code=E_RUNTIME_BROKER_UNAVAILABLE
  state_changed=false

cleanup:
  broker socket absent
  broker pid identity absent
  temporary workspace absent
```

The probes changed no repository file and left no attributable process or
socket.

## 4. Owner-correct design

Rejected alternative:

```text
Evidence Tool or Broker invents a second `feedback` object only for this CLI.
```

This would duplicate canonical ToolResult meaning and make the product owner
depend on an obsolete adapter expectation.

Selected Forward repair:

```text
Evidence Tool canonical ToolResult
  -> Runtime Broker unchanged
    -> Evidence command validates `ok` and `tool_evidence`
      -> prints the canonical result without inventing another response schema
```

The command keeps its name, arguments, target restriction, Runtime Broker
transport and exit convention. Success becomes executable; business rejection
and Broker-unavailable behavior remain exact.

No external consumer of the broken success shape was found. No compatibility,
dual response or fallback is authorized.

## 5. Ratchet

The current migration governance and packet/plan templates now require:

- assertion-level proof for every protected consumer interface;
- real entrypoint/transport success plus material rejection/error proof;
- behavior-test classification before the final scope ledger;
- no use of test filenames, suite labels or pass counts as a substitute.

R2 may exist because this is the first substantive Evidence boundary
invalidation, its root cause is closed, and the selected mechanism has been
preflighted. Another contradictory Evidence successor would trigger the
existing no-third-patch loop breaker.
