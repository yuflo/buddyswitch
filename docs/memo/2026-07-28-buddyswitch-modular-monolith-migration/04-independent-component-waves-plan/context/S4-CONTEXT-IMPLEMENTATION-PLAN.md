# S4 Context Atomic Cutover Implementation Plan

> Use root `AGENTS.md`, `$buddyswitch-testing` and
> `superpowers:executing-plans`.
> Plan state: `READY`
> Packet: `BS-MM-S4-CONTEXT-R1-20260804-01`

## 1. Acceptance sentence

> Context is one last-selected, read-only application-projection module that
> composes accepted Public reads, contributes exactly one `context` Tool, and
> leaves no Context-private behavior or retired owner path in shared hosts.

## 2. Execution checkpoints

### S4.CONTEXT.0 — Identity and scope

- Verify the hub preparation checkpoint and its product parent
  `84734395f7b9088ad130ae8ace310cb55220865f`.
- Verify the preparation delta is coordinating documents only.
- Verify clean product/index/untracked state, installed runtime identity and
  clean attributable resource state.
- Recompute the source/consumer representations from the current checkout.
- Stop before mutation on a product-source mismatch or unclassified write.

### S4.CONTEXT.1 — Entry evidence

- Reuse the two source-equivalent GREEN baselines in the source snapshot.
- If equivalence cannot be proved, dynamically reconstruct and run only the
  missing pre-mutation focused group.
- Retain the zero-collection run as non-evidence; do not copy its node IDs.
- Do not manufacture a product-behavior RED for this refactor.

### S4.CONTEXT.2 — Structural RED

- Add the Context architecture proof in its classified root-owned file.
- Its first run must detect the old dynamic owner, missing explicit Context
  module/composition, and Context-only shared-host residue.
- Record the exact RED identity and cleanup.

### S4.CONTEXT.3 — One no-test cutover block

- Create the minimal `modules/context` private Tool owner and passive
  `ModuleAssembly`.
- Move the current definition and implementation without changing protected
  payload/output semantics.
- Select Context exactly once and last in application composition.
- Replace the Context-only `runtime_policy_preview` host method with the
  existing generic Role authorization call inside Context Private.
- Delete `RuntimeObjectAccess`, `RegistryCatalogAccess`, their ToolContext
  fields and other imports made dead by that removal.
- Delete the entire old `env/tools/context` package.
- Update only the classified direct path consumers and localize the three
  old complete-list component tests.
- Add current Context architecture guidance and remove the README's active
  not-yet-migrated Tool-owner path.
- Parse all changed Python and run `git diff --check`.

Do not invoke the public test runner inside this source/test edit block.

### S4.CONTEXT.4 — Runtime correspondence

After the last `src/buddyswitch/**` edit, use the declared PEP 517 build,
non-editable checkout-local install, activation and verify flow. Record source,
distribution, activation and package identities. Any later package-source
repair repeats this boundary before another public-runner proof.

### S4.CONTEXT.5 — GREEN and affected proof

The executor owns valid target discovery and grouping through the public
runner. Proof breadth must include:

- the new Context architecture RED turned GREEN;
- the complete Context binding file;
- Context catalog/decision/runless/process observables from the direct
  preservation group;
- component architecture consumers whose full-list/path assumptions change;
- generic Tool/application/package independence and Native MCP projections;
- distribution install and activation correspondence;
- absence of the old source and installed package;
- no Context Private import outside application composition/module owner;
- no `RuntimeObjectAccess`, `RegistryCatalogAccess`, ToolContext
  `objects`/`catalog`, or `runtime_policy_preview` residue;
- no current guidance teaching `env/tools/context` or an active dynamic Tool
  owner.

Known current proof files are listed in the owner/consumer manifest and the
two preserved groups. The packet does not freeze shell transcription or
invalid parent test directories.

### S4.CONTEXT.6 — Frozen FINAL and return

- Freeze tracked/index/untracked and activation identities.
- Confirm direct and affected proof are source-equivalent and cleanup is
  clean.
- Run `./buddyswitch-test full` once on the frozen S4 Context candidate.
- If it passes, return the complete packet and stop.
- If it fails, retain and classify the complete result. One bounded
  FIX_AFTER_FINAL cycle is allowed only when one clear cause and every write
  are already classified, no protected boundary changes, and cleanup is
  restored. Reprove exact plus affected behavior, reprovision first if source
  changed, freeze and run one replacement FINAL.
- Any unclassified, environment, protected-contract, cross-lane or second
  FINAL failure returns immediately as `REPLANNING REQUIRED`.

## 3. Stop conditions

Stop once and return when:

- source/preparation/runtime identity cannot be established;
- Context needs a Public API, state, new host contribution or new component
  Public operation;
- a protected output/schema/authority/visibility behavior must change;
- another component Private or accepted Public contract must change;
- a root cross-component test would need to move into Context;
- registry, ModuleAssembly, Native MCP or package activation contracts must
  change;
- a compatibility path, discovery exception or framework appears necessary;
- any required write is unclassified or evidence is unexplained;
- cleanup is not attributable and clean;
- a replacement FINAL fails.

Do not wait, blind-retry, stack repair packets, edit the Goal Packet, commit or
push.

## 4. Return packet

```text
Packet ID and lane:
Starting preparation/product/activation identities:
Final tracked/index/untracked identities:
Final activation/source/distribution identity:
Completed checkpoints:
Changed/created/deleted files by manifest class:
Structural RED command, run ID and detected claims:
Reused or rerun entry evidence:
Focused GREEN and affected commands, run IDs, results and durations:
Every FINAL identity, command, run ID, result and duration:
FIX_AFTER_FINAL cause/scope/repair/evidence, or inapplicable:
Every failure/timeout/flake/no-test/residue signal and disposition:
Consumer-observed Context contract:
Composition/dependency/host-residue/package proof:
Current docs changed:
Cleanup/residual state:
Omitted checks and residual risk:
New findings or stop/replan discoveries:
Proposed ACCEPTED / REJECTED:
```
