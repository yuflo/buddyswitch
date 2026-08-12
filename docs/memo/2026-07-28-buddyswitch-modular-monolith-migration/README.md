# BuddySwitch Modular Monolith Migration Pack

> Current state: S0–S5 ACCEPTED; S6 source refresh and READY preparation unblocked
> Runtime authorization: none; all S5 packets are consumed
> The prior Demand-first pack was replaced after the readiness audit.

Read:

1. root `AGENTS.md`;
2. `../2026-07-28-buddyswitch-modular-monolith-readiness-audit.md`;
3. `../2026-07-28-buddyswitch-explicit-modular-monolith-design.md`;
4. `../2026-07-28-buddyswitch-modular-monolith-migration-roadmap.md`;
5. `00-coordination-hub.md`;
6. `00-execution-governance.md`;
7. only the current stage Goal Packet, charter and named return review. Historical
   implementation plans provide context, not execution authority.

## Stage charters

| Stage | Charter | State |
|---|---|---|
| S0 | `00-program-readiness.md` | ACCEPTED |
| S1 | `01-single-package-runtime-cutover.md` | ACCEPTED |
| S2 | `02-demand-component-pilot.md` | ACCEPTED |
| S3 | `03-task-goal-boundary-cutover.md` | ACCEPTED |
| S4 | `04-independent-component-waves.md` | ACCEPTED |
| S5 | `05-foundation-convergence.md` | ACCEPTED |
| S6 | `06-role-host-cutover.md` | SOURCE REFRESH / READY PREPARATION UNBLOCKED |
| S7 | `07-final-acceptance.md` | BLOCKED |

## Control surfaces

- `migration-ledger.md`: live state and next gate;
- `00-coordination-hub.md`: sole program-control and asynchronous session protocol;
- `decision-log.md`: accepted target/execution decisions;
- `residue-register.md`: old live surfaces and removal owner;
- `executor-handoff-card.md`: one executor payload;
- `stage-implementation-plan-template.md`: required READY plan;
- `stage-goal-packet-template.md`: exact independent-session handoff;
- `stage-acceptance-template.md`: required acceptance record.

S1 has an audit-reviewed structured blueprint at
`01-single-package-runtime-cutover-plan/README.md`. R4 and the first
entry-baseline repair are accepted. Formal packet `BS-MM-S1-20260728-01` and
bounded packet `BS-MM-S1-E1-20260728-01` both stopped correctly before C2.
The hub accepted only E1's Demand-proof repair and expanded the still-open C1
runtime-provenance finding in
`01-single-package-runtime-cutover-plan/S1-E1-RETURN-REVIEW.md`. D-037 now
forbids another patch-on-patch packet, and
`01-single-package-runtime-cutover-plan/S1-E2-PREFLIGHT.md` proves the selected
replacement mechanism is feasible across eleven scenarios. The source snapshot,
exact plan and Goal Packet passed
`01-single-package-runtime-cutover-plan/S1-E2-READY-REVIEW.md`. The returned
implementation is accepted in
`01-single-package-runtime-cutover-plan/S1-E2-ACCEPTANCE.md`; F-034 and
R-PKG-019 are closed and C1 is accepted. E2 is no longer executable. C2
READY preflight then found F-035: moving/deleting source before process and
Actor consumers cut over would create an unusable intermediate product path.
No standalone C2 packet may be issued. The maintainer accepted D-038, and the
hub froze exact source/consumer manifests, complete preservation evidence and
final-topology preflight in the atomic C2–C5 plan. Packet
`BS-MM-S1-C2C5-20260728-01` returned against the frozen source and is accepted
at the C5 gate in
`01-single-package-runtime-cutover-plan/S1-C2-C5-ACCEPTANCE.md`. C2–C5 now
form the sole live runtime path and that packet is consumed. The next action
was C6 current-guidance replacement and frozen FINAL. Packet
`BS-MM-S1-C6-20260729-01` completed that gate and is accepted in
`01-single-package-runtime-cutover-plan/S1-ACCEPTANCE.md`. S1 is closed.
That acceptance unlocked the S2 source refresh and READY preparation.

S2 then completed the direct Demand module cutover and the final
activation-first Browser lifecycle prerequisite. The coordinating hub accepted
the frozen candidate in
`02-demand-component-pilot-plan/S2-ACCEPTANCE.md`; every S2 implementation and
repair packet is consumed. S3 source refresh and READY preparation are now
unlocked. The hub adopted the S2 quality ratchet, refreshed the current
Task/Goal source and consumers, passed the affected preservation baseline,
selected and preflighted the acyclic Task–Demand boundary, and issued the
structured plan at `03-task-goal-boundary-cutover-plan/README.md`.
The initial S3 executor produced a coherent partial candidate and stopped
correctly when a generated package-discovery consumer was outside the exact
manifest. Hub review found the missing representation class, a neighboring
generated router expectation and three candidate proof-quality drifts. The
initial packet is consumed. D-049 and the reviewed R1 audit replace
Task-specific test exceptions with owner/composition-derived generic proof.
R1 was the sole successor execution authority.

S3 R1 then completed the preserved Task/Goal candidate, corrected the generic
package/router proof owners, passed the complete affected path and one frozen
FINAL, and returned with clean runtime and resource state. The coordinating
hub reproduced its complete source, untracked and activation identities,
reviewed the one-owner/Public/contribution boundaries and accepted S3 in
`03-task-goal-boundary-cutover-plan/S3-ACCEPTANCE.md`. Both S3 packets are
consumed.

The S4 source refresh then separated the six lanes by real host and dependency
boundaries. Search is stateless and needs only the existing Tool contribution.
The affected Search
preservation group passed as `b96f488146524dbc97eb14463aea7780`, and
representative final-topology probe `S4SEARCHP-20260730-02` proved explicit
dispatch, atomic old/new registration failure, duplicate-module rejection and
unchanged Daemon order. The structured Search plan is at
`04-independent-component-waves-plan/README.md`. The initial Search packet was
rejected before execution after pre-handoff review found a manufactured
refactor RED, two omitted generated/enumerated consumers and an avoidable
second reprovision boundary. R1 then completed the coherent Search candidate
and runtime activation, but stopped before collection because its frozen
command named `modules/search/tests` instead of a runner-recognized tier.
R1 was consumed and its candidate preserved. D-051 keeps outcomes and
boundaries hub-owned while assigning target discovery and bounded execution
judgment to the executor. R2 then passed direct, affected and one frozen FINAL
on the preserved identity. Search is accepted in
`04-independent-component-waves-plan/search/S4-SEARCH-ACCEPTANCE.md`; all
Search packets are consumed.

The next source refresh proved Track and Artifact must cut over atomically
while remaining separate modules. R1 completed and proved the product
candidate. Hub review then found a false test-ownership boundary: ten
cross-component tests had moved under one module and the architecture proof
excluded module test roots. R2 changed no product source; it returned those
tests to root tiers, retained three true module-local tests, enforced the
cross-Private rule and passed exact, affected and one new frozen FINAL.
Track–Artifact is accepted in
`04-independent-component-waves-plan/track-artifact/S4-TRACK-ARTIFACT-ACCEPTANCE.md`.
Both packets are consumed. The committed-source refresh then selected
Evidence as the shortest complete next lane: it reuses the existing Tool
contribution and accepted Artifact Public, needs no Browser or Host contract,
and persists no state. Direct and affected refactor baselines plus a
representative explicit-registration preflight passed. Packet
`BS-MM-S4-EVIDENCE-R1-20260731-01` produced the structural cutover and stopped
when the stable command lacked real-Broker terminal-loop proof. R2 repaired the
pre-existing nonexistent-`feedback` mismatch at the Evidence command adapter,
added product-boundary process proof, and passed exact, direct, affected and one
frozen FINAL. Evidence is accepted in
`04-independent-component-waves-plan/evidence/S4-EVIDENCE-ACCEPTANCE.md`; both
Evidence packets are consumed. The committed Communication refresh froze its
owner/consumer map, the two earned passive WebHost contributions, the acyclic
Demand input edge and generic multi-owner cleanup projection. Direct,
affected and process/package preservation baselines plus topology preflight
`S4COMMP-20260803-01` passed. R1 produced the complete Communication cutover;
R2 corrected recursive Message cleanup; R3 corrected effect-time cleanup
authority and truthful deletion projection. The final candidate passed exact,
affected and one frozen replacement FINAL and is accepted in
`04-independent-component-waves-plan/communication/S4-COMMUNICATION-ACCEPTANCE.md`.
All Communication packets are consumed. The committed Context refresh proved
that the projection already consumes Track, Task, Artifact and Communication
Public, while three unused/Context-only access surfaces remain on shared
`ToolContext`. The second pre-handoff audit rejected the unexecuted first
packet, removed its manufactured structural RED and opaque evidence
identities, and recorded assertion-level reusable proof. Direct baseline
`ec4ae6b40a3d4fcaa8494049c609d35c`, affected baseline
`58658371b1244b428ea3cccfb24eb393` and reproducible topology probe
`S4CONTEXTP-20260804-02` passed. D-056 selects one final passive Context Tool
module with no Public/state/test subtree and exact host-residue removal. The
returned candidate passed structure, direct, affected and frozen FINAL proof
and is accepted in
`04-independent-component-waves-plan/context/S4-CONTEXT-ACCEPTANCE.md`.
Every S4 packet is consumed. S5 source refresh is unblocked, but no S5
implementation is authorized before a fresh READY review.

The S5 refresh found several independent Foundation lifecycle owners rather
than one safe repository-wide merge unit. The ordered cutover blueprint is at
`05-foundation-convergence-plan/README.md`. C1 converges only the explicit
ToolHost, narrow ToolContext and generic Daemon client; source/consumer
snapshot, representation-complete manifest, affected baselines, topology
preflight, implementation plan and READY review admitted R1. R1 returned a
runnable candidate, but hub review rejected its unused-surface residue and the
coordinator's path-prescriptive handoff model. R2 removed the unearned
ToolContext/error/Broker surfaces, preserved all eight Tool contracts, passed
affected proof and one replacement frozen FINAL after an owner-correct Search
repair, and is accepted in
`05-foundation-convergence-plan/tool-host/S5-TOOL-HOST-ACCEPTANCE.md`. Both C1
packets are consumed. C2 refresh then traced the remaining concrete Track
import in WebHost and the product-enumerated cleanup projection fields. D-060
selects passive exact/prefix route matchers and contribution-derived cleanup
plan/result fields without changing current Web, cleanup or CLI effects.
Preflight `S5C2P-20260804-02`, exact/affected proof and frozen FINAL
`c1a3466da1b6455ead00dfcdca86bf46` passed. C2 is accepted in
`05-foundation-convergence-plan/web-cleanup/S5-C2-ACCEPTANCE.md`; its packet
and evidence-only continuation are consumed. The committed C2 source refresh
then traced all eight Browser implementation fragments, the cockpit proxy
asset, Broker/Daemon/application consumers, literal test paths and package
projection. D-061 selects one `foundation/browser_runtime/**` owner without a
facade or compatibility path. Preflight `S5C3P-20260806-01` proves the mapped
owner graph is acyclic and the complete C3 plan is READY at
`05-foundation-convergence-plan/browser-runtime/README.md`. R1 completed the
atomic owner move and behavior preservation. A bounded R2/hub review replaced
an exact private topology assertion with invariant-based proof and removed an
unearned lexical-analysis helper. Exact, affected and frozen FINAL
`c6a7f1ad14c44df48dea1a96e0a4f5db` passed. C3 is accepted in
`05-foundation-convergence-plan/browser-runtime/S5-C3-ACCEPTANCE.md`; both
packets are consumed. C4 then refreshed the live identity/state/process
owners, 68 direct import representations and 63 direct test/support files.
Focused preservation `64a171bd1ff847e1b4e25136c8c46eb3` and topology
preflight `S5C4P-20260806-01` passed; D-062 freezes three direct Foundation
primitive owners, no migration of zero-consumer helpers, and the C4/C5/C6 cut
line. R1 then completed the direct-owner cutover, removed the retired
`env/**` and old process-identity path, passed exact/affected proof and frozen
FINAL `e306abb4f43d42ce8b9517f08e3a5450`, and is accepted in
`05-foundation-convergence-plan/identity-state-process/S5-C4-ACCEPTANCE.md`.
The packet is consumed. C5 source refresh found two independent service owners,
so D-063 refines the former combined unit into C5A Runtime Broker followed by
C5B Daemon. Broker baseline `fed0d4f4...`, independent Daemon baseline
`35589e1b...` and topology `S5C5AP-20260807-02` passed. C5A packet
`BS-MM-S5-RUNTIME-BROKER-R1-20260807-01` then completed the direct Broker and
shared-framing cutover. Hub review removed Broker terminology from the shared
primitive, passed exact/affected proof and new frozen FINAL
`0edb068adf19462a863ce3445e8aab0c`. C5A is accepted in
`05-foundation-convergence-plan/runtime-broker/S5-C5A-ACCEPTANCE.md`; its
packet is consumed. C5B source refresh then classified 76 current
source/test/current-doc representations and proved that App/Actor behavior
must cross one narrow application-supplied capability, Browser registrations
must enter through application composition, and the shared runtime-event log
belongs to Process Runtime. Focused baseline `433a2e2766d34929b10b6aa2e4111213`,
source-equivalent full `7643bdc832c648729ab87c0eef6e0c39` and topology
`S5C5BP-20260807-01` passed. C5B R1 then completed the one-owner cutover;
focused repair evidence and frozen FINAL
`e91948e42eb0498bbc473714cd48e09d` passed. C5B is accepted in
`05-foundation-convergence-plan/daemon/S5-C5B-ACCEPTANCE.md`; its packet is
consumed. C6 source refresh then proved App Server is an independently runnable
owner with its live shell adapter, while Actor/Web/CLI can remain current.
D-065 admits this shortest C6A cutover; direct baselines `c81992a7...` and
`97b26774...`, source-equivalent FINAL `e91948e...` and topology
`S5C6AP-20260811-01` passed. R1 then completed the direct Foundation owner,
consumer/package cutover and retired Launcher deletion. Focused runs
`622998aa...`, `28c9b731...`, review closure `d4d529b1...` and frozen FINAL
`2136e109...` passed. C6A is accepted in
`05-foundation-convergence-plan/app-server/S5-C6A-ACCEPTANCE.md`; its packet is
consumed. Only remaining C6 source refresh and READY preparation are unlocked;
C7 and S6 remain unauthorized.

C6B source refresh then isolated the product-neutral Actor parent-session and
side-thread runtime from Role-bound Host Control and workspace construction.
Direct baseline `d38fa5b...`, affected baseline `2f61b0e...` and topology
`S5C6BP-20260811-01` passed. D-066 selects one direct
`foundation/actor_runtime/**` owner for capability state, Codex runtime
descriptors, parent Session and side lifecycle/registry. R1 completed the direct
owner, consumer/package cutover and six-path deletion. Direct `60bf5416...`,
affected `aaefa823...`, architecture/package proof, System `c666068c...` and
frozen FINAL `7678be69...` passed. C6B is accepted in
`05-foundation-convergence-plan/actor-runtime/S5-C6B-ACCEPTANCE.md`; its packet
is consumed. Only remaining C6 source refresh and READY preparation are
unlocked; C7 and S6 remain unauthorized.

C6C source refresh then separated product-neutral atomic Actor workspace
publication from central Role/Skill selection. Direct baseline `7e3800b1...`,
private invocation `f70f9357...`, consumer System `d743845f...` and topology
`S5C6CP-20260811-01` passed. D-067 selects one resolved bootstrap projection:
the current application produces it from existing Role/Skill truth, while the
Foundation publisher performs one code-free atomic write path and imports no
Role implementation. R1 completed that owner, consumer, package and retired
Launcher cutover. Direct/affected/package/System proof and frozen FINAL
`c9211e36639740738eca7fe0cbda96ca` passed. C6C is accepted in
`05-foundation-convergence-plan/actor-environment/S5-C6C-ACCEPTANCE.md`; its
packet is consumed. That checkpoint unlocked only remaining C6 source refresh
and READY preparation; it did not authorize later implementation, C7 or S6.

C6D source refresh then identified the real remaining dependency bottleneck:
private Host Control lifecycle is split across a Launcher facade, the actual
Host Control shell, mixed environment helpers, current Role input and a
Launcher-owned runtime lock. Focused baseline `2a202fd6...` and topology
`S5C6DP-20260812-01` pass. D-068 admits one complete lifecycle cutover with
application-supplied current Role input and one Process Runtime lock owner.
R1 completed the lifecycle/lock cutover but hub review found concrete
Application module invocations in Foundation helper shells. R2 moved those
four exact executable facts into the existing application input, extended the
architecture proof across every helper shell and passed direct, affected and
frozen FINAL `374bde20002b48cfaa40b6585298d66f`. C6D is accepted in
`05-foundation-convergence-plan/host-control/S5-C6D-ACCEPTANCE.md`; both
packets are consumed. Only remaining Web/Cli host source refresh and READY
preparation are unlocked; C7 and S6 remain blocked.

The remaining-host refresh found two real owner boundaries. Web Runtime is
already product-neutral and independently runnable; CliHost still spans env,
Browser, cleanup, Codex configuration and S6 Role-asset dependencies. D-070
therefore admits C6E first: move Web contracts/runtime/assets plus the complete
small machine-envelope contract to direct Foundation owners, then refresh the
remaining CliHost from that clean checkpoint. Web preservation runs
`05e68f98a675479d91013f53abcaa6fe`,
`f74dd3efc6824a2f97a903b1a28aeea2` and real System
`c9c8b863f4b14f22bea5d7b26f92eea3` pass; topology
`S5C6EP-20260812-01` is acyclic. R1 completed the move and passed FINAL, but
hub review found its Open-TUI builder still embedded the concrete Application
CLI module. R2 moved that fact to the Application composition point, extended
the bounded owner proof across embedded executable representations and passed
affected proof plus frozen FINAL `69dd48e9e39e48c5bf232e4a8dd4552d`.
C6E is accepted in
`05-foundation-convergence-plan/web-runtime/S5-C6E-ACCEPTANCE.md`; both packets
are consumed. The committed C6F refresh then classified the remaining
CLI/config/shell cluster, its Application/Role executable facts, live
consumers and eight zero-production-consumer helpers. The atomic cutover moved
the complete host to `foundation/cli_runtime/**`, supplied all concrete facts
through one required Application input, deleted the five Launcher owners and
unused helpers, and passed direct, affected, package, real System and frozen
FINAL `f9dea78e158e473db2a89081e60cb595`. C6F is accepted at
`05-foundation-convergence-plan/cli-runtime/S5-C6F-ACCEPTANCE.md`; its packet
is consumed. C7 source refresh and READY preparation are unblocked; S6 remains
blocked.

C7 source refresh then found that the historical `runtime_support` root still
contains three generic S5 owners beside the four current S6 Role
implementations: cleanup execution, passive Skill/composition contracts and
runless diagnostics. Foundation composition and Runtime Broker also retain
three direct edges into that root. Direct preservation
`84becba089ea4b60b715cc257098fee5`, architecture/package preservation
`d0afd8e28dbd47beb80cdc8b6a58d7fa`, source-equivalent FINAL
`f9dea78e158e473db2a89081e60cb595` and topology
`S5C7P-20260812-01` pass. D-072 selected one atomic final Foundation seam
extraction and S5 acceptance packet. It moved the three generic owners to
Foundation, made all Role facts explicit Application inputs, removed the old
source and installed paths, and passed frozen FINAL
`364f7e924501414a9ca48b3404645307`. C7 and S5 are accepted at
`05-foundation-convergence-plan/final-acceptance/S5-C7-ACCEPTANCE.md`; its
packet is consumed. S6 source refresh and READY preparation are unblocked.

Do not hand the whole program to one executor. The handoff unit is one current
stage or owner-bounded lane with an outcome, semantic authority boundary,
protected contracts and proof obligations. Historical implementation plans are
context, not commands.
