# Zhipu Market Continuous-Demand Real-Actor Acceptance Design

**Date:** 2026-07-21

**Status:** approved for execution

**Repository baseline:** `fea-daemon` at
`213d980c29cc1f6a247375ede06d7f74de676ea3` plus the uncommitted Phase 4
forward-cutover change set

## 1. Goal

Run one real Market actor through a genuinely evolving research engagement on
Zhipu AI's market competitiveness. The run must not collapse several prompts
into one up-front brief. A real PM actor sends an initial inbound request and
later supplements; later messages are chosen partly from actual intermediate
research findings.

The acceptance sentence is:

> In an isolated real-Codex environment, sequential PM messages about one Zhipu
> market study become durable Market-owned Demands before Task selection; the
> Market actor distinguishes same-need supplements from a related child need,
> never runs more than one active Task, carries newer Demand revisions into
> later serial work, and produces an evidence-backed final research artifact
> that materially responds to the intermediate feedback.

## 2. Scope and non-goals

In scope:

- installed real Codex runtime, one PM actor, and one Market actor;
- real `message.send` from PM to Market and the normal IM daemon path;
- at least one supplement arriving while a Market Task is active;
- adaptive feedback after reading an actual intermediate artifact;
- Demand absorption, a related child Demand, serial Task lifecycle, browser
  evidence, artifact revision/publication, logs, and exact isolated cleanup.

Out of scope:

- fake Codex, direct Demand writes, or direct Market input as inbound
  simulation;
- changing Demand or Task rules to make the sample pass;
- a scheduler, queue, automatic relation engine, or multiple active Tasks;
- treating the research report as authoritative financial advice;
- touching the default `/Users/chen/.codex-buddyswitch` live state.

Direct input is test control only. It may tell the PM actor to send a message or
ask an actor to expose current supported-product evidence. It does not count as
a Market inbound need and must not create a Market Demand.

## 3. Chosen architecture

```text
root test controller
  -> public CLI input to real PM actor
  -> PM message.send(target_identity_id=Market)
  -> Central IM fact/event
  -> generic daemon delivery
  -> Market IM handler -> Demand capture -> Demand Check
  -> actor organization judgment
  -> at most one task_sys.create(DemandRef)
  -> Market browser research -> artifact revision -> Track publication
  -> PM artifact.get review -> next adaptive message
```

Two alternatives are rejected:

- A single Market actor creating self-Demands would not prove inbound capture.
- Track comments would prove the Phase 4 source path but would introduce Track
  thread semantics into a run whose main target is Demand organization and
  serial Task consumption.

The PM is a real requester and reviewer, not a second research engine. The
Market actor owns research judgments and evidence collection.

## 4. Isolation and source identity

Create one run directory outside both the repository runtime projection and the
default live root:

```text
/private/tmp/buddyswitch-zhipu-market-1784566044/.codex-buddyswitch
```

Every CLI command in the run receives that exact `BUDDYSWITCH_SHARED_ROOT`.
Record:

- repository HEAD and dirty patch identity;
- real Codex executable and version;
- run root;
- PM/Market actor, thread, and turn ids;
- baseline instance/object/process/socket counts.

Do not run role-wide cleanup. Teardown stops and deletes the two exact actors,
uses the isolated environment reset only after their processes stop, and proves
the isolated root and owned processes/sockets are absent.

## 5. Research contract

The Market actor must investigate the current company rather than rely on model
memory. “Zhipu” means Zhipu AI / Beijing Zhipu Huazhang and its current public
commercial identity, which the actor must verify.

The final analysis must cover:

1. model and product portfolio, including API, enterprise, consumer, agent, and
   open-source positioning where current evidence supports them;
2. technical differentiation and limits without equating benchmarks with
   sustainable advantage;
3. pricing/model economics and developer ecosystem;
4. enterprise adoption, partnerships, commercialization, financing/listing or
   other business-quality signals that are publicly supportable;
5. comparison with at least DeepSeek, Alibaba Qwen, ByteDance Doubao, Baidu
   ERNIE, Moonshot/Kimi, and MiniMax, plus global vendors only where relevant;
6. defensibility, regulatory/geopolitical exposure, commoditization risk, and
   a 12-month scenario view;
7. a clear conclusion separating verified facts, inference, uncertainty, and
   recommended follow-up.

Primary/company/regulatory sources anchor factual claims. Independent reputable
sources test company claims. Every material current claim needs a retrievable
URL, source date, and access date. Source count is a diagnostic, not a quality
substitute; the initial brief asks for at least 12 primary and 6 independent
sources to make shallow completion unlikely.

## 6. Staged challenge

### Stage A — initial Demand C

The PM sends a fresh direct message requesting a decision-grade Zhipu market
competitiveness study under the research contract above. It asks the Market
actor to publish a versioned `brief` artifact to a dedicated Track.

Expected observations:

- one IM-derived Demand C with exact message provenance;
- C is checked and selected through the actor path;
- exactly one Demand-backed Task starts;
- no Task is created directly by IM or daemon code.

### Stage B — in-flight same-need supplement D

As soon as C's Task is observably active, the PM sends a second message adding:

- financing/listing and commercial traction signals;
- model/API economics and evidence-quality grading;
- explicit separation of company claims from independent corroboration.

D is intentionally part of the same deliverable. The expected organization is
`D absorbed_into C`, with C revised atomically and D terminalized with lineage.
The existing Task remains the only active Task. Because it carries an older C
basis revision, its completion must not silently complete the newer C revision;
later work must consume the latest revision serially.

If the actor makes a different relation decision, capture the exact reasoning
and state. Do not repair state by hand merely to satisfy the expectation.

### Stage C — adaptive correction E

After the first readable artifact exists, the controller and PM inspect the full
artifact body, cited sources, Demand state, and Task outcome. Select one material
weakness actually present, such as:

- a strong claim supported only by company material;
- an outdated product/pricing comparison;
- benchmark evidence used as a proxy for commercial moat;
- a competitor or customer segment treated too generically;
- contradictory evidence not reconciled.

The PM sends a concrete correction request naming the observed claim and the
evidence gap. E is another same-deliverable supplement and should normally be
absorbed into C. The revised artifact must change the affected analysis rather
than merely append a disclaimer.

The exact correction is deliberately not frozen before Stage A; prewriting it
would defeat the adaptive-feedback requirement.

### Stage D — related child Demand F

After the corrected artifact, the PM sends a distinct decision question:

> Given the evidence already assembled, where can Zhipu most plausibly win or
> lose in China's enterprise-model market over the next 12 months, and what
> observable signals would falsify the view?

This is related to C but has its own outcome: a win/loss segment map and scenario
watchlist. Expected organization is `F.parent_id = C.id`, not absorption into
C. No speculative dependency is required. F remains queued while another Task
is active and receives its own serial Task only when the single-active gate is
clear.

### Stage E — final synthesis

The Market actor publishes the final current artifact revision(s). The PM reads
the full body with `artifact.get` and provides one final acceptance response
covering resolved feedback, remaining uncertainty, and the next decision.

## 7. Acceptance evidence

| Proof | Required evidence |
| --- | --- |
| Product | PM message ids; Market Demand ids; real research artifacts; PM final review |
| Demand | C/D/E/F projections, revisions, checked revisions, live structure, and lineage |
| Task | exact DemandRefs, lifecycle events, terminal results, and sampled active count <= 1 |
| Pro-active | IM delivery, daemon handling, Demand Check turn starts/steers, no direct Task creation |
| Research | full artifact bodies, source ledger, claim changes after E, child decision output after F |
| Architecture | current one-path code identity; no test-only or compatibility route used |
| Operations | real Codex identity, actor/log health, browser evidence, exact teardown and zero residue |

Supported observation surfaces are the public instance/Demand/Task/Track CLI,
the actors' native `track.open`/`artifact.get` actions, IM delivery responses,
and owned daemon/app-server logs and thread records. Raw runtime JSON is not a
mutation or orchestration interface.

The exact ids and timestamps go into a separate execution record so this design
does not become a diary.

## 8. Failure rules

- A capture or wake failure is evidence. Diagnose before retrying; never replay
  until a pass hides the first signal.
- An actor that creates a second active Task, loses a supplement, acknowledges a
  revision it did not inspect, or completes newer Demand work from an older Task
  snapshot fails the corresponding contract.
- A shallow or poorly sourced report fails research acceptance even if lifecycle
  mechanics pass.
- A defensible actor relation decision that differs from the expected relation
  is recorded and evaluated semantically; relations are actor judgment, not a
  hard-coded classifier.
- Product defects are diagnosed and preserved as evidence. No hidden state edit,
  fake tool, compatibility branch, or prompt that dictates exact tool calls is
  introduced to force success.
- If a transient external website is unavailable, record it and use another
  authoritative source. If real Codex, browser, broker, or daemon health blocks
  the run, stop with exact diagnostics rather than substituting a fake runtime.

## 9. Completion criteria

The acceptance is complete only when:

1. the PM and Market actors are real and their runtime identity is recorded;
2. the initial request and at least three later PM messages traverse real IM;
3. at least one supplement is captured while a Task is active;
4. same-need supplement organization and one related child need are observed;
5. every final Demand revision is checked and no more than one Task is active at
   every recorded sample;
6. the final artifact responds materially to adaptive feedback and meets the
   research contract;
7. logs connect messages, Demand attention, actor turns, Tasks, and artifacts;
8. the isolated actors, processes, sockets, leases, browser resources, and state
   root are removed;
9. any defect or evidence gap is reported without weakening the claim.

This is a real-actor MILESTONE, not a repository-wide FINAL test run. It
supplements the repeatable focused Phase 4 evidence and does not replace it.
