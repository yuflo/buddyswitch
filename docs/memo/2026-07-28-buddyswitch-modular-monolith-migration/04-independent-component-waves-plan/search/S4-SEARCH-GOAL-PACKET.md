# S4 Search Capability Cutover Goal Packet

> Packet state: `CONSUMED — REJECTED BEFORE COLLECTION`
> Packet ID: `BS-MM-S4-SEARCH-R1-20260730-01`
> Predecessor: `BS-MM-S4-SEARCH-20260730-01` rejected and consumed
> Successor: `BS-MM-S4-SEARCH-R2-20260730-01`

## 0. Copy-paste independent-task request

```text
Create and pursue this goal:

Execute BuddySwitch packet BS-MM-S4-SEARCH-R1-20260730-01 from the exact
preparation checkpoint supplied by the coordinating hub.

Read root AGENTS.md, the complete $buddyswitch-testing skill and routed
references, then
docs/memo/2026-07-28-buddyswitch-modular-monolith-migration/
04-independent-component-waves-plan/README.md in its exact order.

First verify the preparation commit, clean product state, current Search
source/test manifests, installed runtime and resource state. Reuse the four
identity-valid behavior-preserving GREEN baselines; do not manufacture RED.
Then perform one coherent no-test Search cutover:
physically aggregate Search and its owned tests, contribute its Tool through
the existing ModuleAssembly, select it exactly once in application
composition, delete the old dynamic Search package and unused
BrowserAccess.request placeholder, update only the classified consumers and
current docs, including the generic env-layer and repository-composition
consumers found by pre-handoff review. Reprovision once after the last
package-source mutation, prove the complete affected path, and run FINAL once
on the frozen candidate. If that FINAL finds a failure with one clearly
diagnosed owning cause whose every required write is already classified, one
bounded FIX_AFTER_FINAL cycle is authorized: retain the failed result, make
the owner-correct repair, rerun exact and affected focused proof, reprovision
first if package source changed, freeze, and run one replacement FINAL.
Otherwise return the exact result packet and stop.

Do not start another S4 lane, edit migration master truth, commit, push,
change branches, alter ModuleAssembly/registry/Browser/profile contracts, add
Search Public without a current consumer, add compatibility, or create a
plugin, DI, bus, route or lifecycle framework. Stop once on any unclassified
write, invalid refactor baseline, architecture/public-contract change, data
migration, unexplained failure, environment mutation, cleanup residue or
replacement FINAL failure. Never blind-rerun, exceed two total FINAL commands,
or enter repeated blocked turns.
```

## 1. Identity

```text
Packet: BS-MM-S4-SEARCH-R1-20260730-01
Stage/lane: S4 / Search
Prepared date: 2026-07-30
Product base HEAD: e4fe342144febc023d1d635012e7e8a5e645138d
Product base tree: 5eec6f43e578456b5e75ba4eee7eec3f56437a08
Preparation checkpoint: supplied by hub after this packet is committed
Owner source manifest:
  53f8f4b63a0b2c4517f594a43cf226d8fd573b213f44e80dfe699bed58b77aee
Owner test manifest:
  46fd312220d24f2193a3b8ba15f76ab76532a1b6cbea262797bdb45b3ce79ecf
Tracked/index/untracked product state: clean
Execution branch/worktree: current fea-tool worktree only
```

The preparation commit may change coordinating documents only. Any product
source/test delta from the frozen base is a mismatch.

## 2. Authority

Allowed writes are exactly the OWNER, COMPOSITION, HOST, PROOF and CURRENT DOC
entries in `S4-SEARCH-OWNER-CONSUMER-MANIFEST.md`.

Forbidden:

- every unclassified path;
- Track, Artifact, Communication, Evidence and Context implementation;
- foundation/application host contract changes beyond the two exact Search
  edits;
- migration packet/master truth;
- compatibility or speculative framework;
- Git commit/push/rebase/branch operations.

## 3. Action-time rules

- Verify activation and source equivalence before reusing or rerunning
  baseline proof.
- Reuse identity-valid refactor baselines; do not manufacture RED.
- Search owner move, explicit contribution and old dynamic package deletion
  are one atomic replacement.
- After any `src/buddyswitch/**` mutation, reprovision and verify before the
  next public test.
- Generic proof derives from application composition; never add a Search
  exception.
- Source-structure proof maps dotted invoke modules back to checkout `src/`;
  installed `__file__` is not a source-path authority.
- An ordinary defect is fixable only inside classified scope.
- A new required path or contract stops execution.
- No public test may run inside the coherent source/test edit block.
- One FINAL is authorized per frozen candidate.
- At most one FIX_AFTER_FINAL cycle and one replacement FINAL are authorized,
  only for a clearly diagnosed defect entirely inside classified write scope.
- A failed FINAL remains evidence; it is never hidden by the replacement.
- Return once on stop; do not enter repeated blocked turns.

## 4. Verification authority

Use only:

```bash
./buddyswitch-test focused <file-or-nodeid>...
./buddyswitch-test full
```

Run the exact sequence in `S4-SEARCH-IMPLEMENTATION-PLAN.md`. Additional
focused tests are allowed only to diagnose or own an in-scope failure and
must be included in the return.

## 5. Closure proposal

The executor may propose but not record:

- `R-SEARCH-001` closed;
- Search portions of `R-FND-002/003/011/012` closed;
- Search portion of `R-DOC-002` closed.

The hub alone accepts the lane and updates master truth.
