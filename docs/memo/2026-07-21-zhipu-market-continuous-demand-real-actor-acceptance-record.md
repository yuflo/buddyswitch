# Zhipu Market Continuous-Demand Real-Actor Acceptance Record

**Run date:** 2026-07-21 (Asia/Shanghai)
**Verdict:** **Partial pass** — the real continuous research loop ran end to end,
but the run exposed two structural failures that prevent an unqualified Phase 4
acceptance claim: Track material has no single current truth after a revision,
and a new Demand cannot be attached beneath an already-terminal parent Demand.

This memo records one isolated runtime acceptance run. It is evidence and
historical context, not a live architecture contract.

## 1. Acceptance claim and frozen identity

Claim under test:

> Two real Codex actors can turn a sequence of evolving PM messages about one
> Zhipu market study into checked Demands, serial Tasks, browser-grounded
> artifact revisions, and a related decision branch without controller-written
> product state.

Frozen source/runtime identity:

| Item | Evidence |
|---|---|
| Repository HEAD | `213d980c29cc1f6a247375ede06d7f74de676ea3` |
| Tracked patch SHA-256 | `d432b6434c745e3964339f998c3e67e8132de0680772d5a0c88d7ba7700e7e24` |
| CLI runtime | `/Users/chen/.npm-global/lib/node_modules/@openai/codex/bin/codex.js` |
| Codex version | `codex-cli 0.144.6` |
| Isolated shared root | `/private/tmp/buddyswitch-zhipu-market-1784566044/.codex-buddyswitch` |
| Pre-run isolated root | Absent |
| Pre-run default instance list | `[]` |

The controller used only isolated-root-prefixed public CLI commands, actor tool
calls, owned app-server thread reads, and owned daemon/runtime projections. It
did not write Demand, Task, Track, IM, artifact, or daemon state directly.

## 2. Real actors and model depth

| Role | Actor / thread | Runtime processes at steady state | Model depth |
|---|---|---|---|
| PM | `act-pm-677a02b6e4d4` / `019f806f-b075-7c90-8413-819a91b0e35c` | app server `28732`, daemon `28800`, broker `28672` | parent + side `fast` |
| Market | `act-market-4b1f75215cd0` / `019f806f-c34f-70a1-b7c0-033032201079` | app server `28944`, daemon `29046`, broker `28914` | parent + side `balanced` |

Both app servers, runtime brokers, and daemons were healthy. The lower-depth
configuration was intentional: PM dispatch/read work used `fast`; browser-heavy
research used `balanced`. No fake Codex executable was used.

## 3. Shared research Track

PM created Track `zhipu-market-competitiveness-research`, titled
“智谱公司市场竞争力持续调研”, with these acceptance criteria:

- maintain a decision-grade, evidence-backed, versioned Zhipu analysis;
- publish Market research as Track material;
- preserve source dates, URLs, uncertainty, and explicit revisions.

### Setup behavior that contradicted the plan assumption

The setup prompt was direct actor input. It was not automatically captured as
inbound Demand, but the PM actor attempted `track.create` before it had a Task
frame and was rejected by the Task gate. The actor then deliberately created
self-Demand `demand-2cdf00420ed0` (`source_ref.type=actor_input`), consumed it via
Task `task-demand-27d143d4ca33`, created the Track and a requirements-only
artifact, and completed/acknowledged the Demand at revision 2.

Therefore the plan statement “control-plane setup must create no PM Demand” was
wrong for the current actor/task contract. The observed behavior preserves the
important boundary: direct input was not treated as uncontrolled inbound info;
the actor explicitly raised its own Demand to obtain an authorized Task frame.

## 4. Message → Demand → Task chronology

| Stage | IM / Demand | Organization result | Task / result |
|---|---|---|---|
| Initial C | `msg-0ec9eacb46cd` → `demand-18f588aebfaa` | Root Demand; revision 1 checked before execution; later revised to include D | `task-demand-8257597caba3`, basis revision 1, `00:54:48–01:01:43` |
| In-flight supplement D | `msg-00216a360988` → `demand-5ad257eee833` | Absorbed into C at `00:55:35`; D terminal revision 2; C became revision 2 | No parallel Task; C's original Task remained the only active Task |
| Artifact audit E | `msg-a9abce3c0240` → `demand-67fd72d7fea2` | Independent root because C was already terminal; completed/checked revision 2 | `task-demand-c6d4c6081528`, basis revision 1, `01:06:48–01:09:00` |
| Decision branch F | `msg-e9a1e58019cc` → `demand-5933f6f97196` | Semantically a child of the main study, but persisted as another root (`parent_id=null`); completed/checked revision 2 | `task-demand-8fbba0b60e10`, basis revision 1, `01:11:29–01:16:42` |

All four Market IM notifications were handled by the generic daemon's
`im_message_created` handler with `result=handled` and no handler error. The
daemon remained a delivery/wakeup substrate; Demand and Task decisions were made
by the actor through their owning tools.

### In-flight supplement and snapshot reconciliation

D arrived while C's Task was in `in_progress.parent_processing`. The Market
actor compared the live descriptions, judged that D requested no independent
deliverable, absorbed it into C, and continued the existing Task. Repeated
sampling observed an active count of one; persisted Task intervals also do not
overlap.

C ultimately completed at revision 3 even though its Task basis was revision 1.
This was not automatic old-snapshot completion: after publishing v1.0, the actor
read C at revision 2, verified the deliverable contained D's added scope, called
`demand_sys.complete(expected_revision=2)` with the Task receipt, then
acknowledged revision 3. The run therefore passed the stale-snapshot safety
claim through explicit latest-revision reconciliation, not through a second
Task.

## 5. Research and adaptive correction

### v1.0

Market published `art-3acd23d22b`, “智谱 AI 市场竞争力研究 — v1.0”. It covered
the requested product/API, technical, developer, enterprise, financing/listing,
regulatory, moat, competitor, and 12-month scenario areas. The source ledger
contained 12+ official records and 6 Reuters records, with claim labels and
explicit evidence gaps.

The deterministic artifact audit selected the first qualifying weakness:

> “搜索与报道上下文提到阿里云合作”

Reuters I4 did not establish an Alibaba Cloud partnership, date, scope, terms,
customer contribution, or revenue contribution. PM sent one concrete correction
message E based on that exact artifact claim.

### v1.1 correction

Market used a direct Alibaba Cloud Model Studio GLM page and found that it proves
only GLM model availability, supported interfaces, and token billing. It then
published revision `art-532a274187`, “v1.1（审计更正）”, which:

- removes the Alibaba Cloud partnership assertion;
- records the Model Studio fact at its narrower evidence boundary;
- blocks partnership contract, joint sales, revenue, partner-quality, and moat
  inferences;
- preserves `supersedes_artifact_id=art-3acd23d22b` lineage.

This is a material correction, not an appended disclaimer.

### Decision branch

F produced separate artifact `art-zhipu-enterprise-winloss-v1`, “智谱 AI：中国
企业大模型 12 个月 Win/Loss Segment Map — v1.0”. It references v1.1 as its
baseline without rewriting the main report and includes:

- narrow win/loss segments;
- positioning against Qwen/Model Studio, Baidu Qianfan, Doubao/Ark, DeepSeek,
  Kimi, and MiniMax;
- three 12-month scenarios;
- observable confirmation and falsification signals;
- current browser reads for GLM-5.2, Alibaba Model Studio, Qianfan, Ark, and
  DeepSeek;
- explicit boundaries against treating product pages as adoption, retention,
  revenue, TCO, or market-share proof.

The branch also caught a real freshness change: GLM-4.5 documentation now warns
of retirement while the current GLM-5.2 page carries the newer long-task,
coding, 1M-context, and tool-integration positioning.

## 6. Final PM content review

The PM performed a read-only final review (`track.open` plus two
`artifact.get` calls) and created no new object. Its verdict was **partial pass**:

| Requirement | Result | Evidence / limitation |
|---|---|---|
| Main competitiveness brief | Pass | v1.1 retains the requested strategic coverage and corrected evidence boundary |
| Adaptive correction | Pass | Unsupported partnership inference was materially removed |
| Win/loss segment map | Pass | A–E narrow scenarios, competitor positioning, three scenarios, and falsifiers are present |
| URLs, dates, uncertainty | Partial | Branch S1–S5 are explicit; v1.1 refers back to v1.0 for some P7–P13 URLs and many pages expose no usable publication date |
| One current version truth | **Fail** | Track marks requirements material, v1.0, v1.1, and the decision branch all `current=true` |
| Fully current model/economic baseline | Partial | Main v1.1 still emphasizes GLM-4.5 while the later branch identifies GLM-5.2 and GLM-4.5 retirement |
| Decision-grade commercial proof | Incomplete by evidence availability | No audited enterprise revenue, renewals, win rate, deployment scale, or actual TCO |
| Capital-market chronology | Partial | Shanghai application and Hong Kong offering/placement reports are not reconciled into one current state chain |

## 7. Runtime and contract findings

### Failure A — Track revision does not establish one current truth

`track.get` returned all of these relations with `current=true`:

- `art-451f136e7f` — requirements-only material;
- `art-3acd23d22b` — v1.0 containing the retired Alibaba Cloud claim;
- `art-532a274187` — corrective v1.1;
- `art-zhipu-enterprise-winloss-v1` — separate decision branch.

Artifact lineage says v1.1 supersedes v1.0, but the Track projection does not
retire the old current relation. A consumer reading “current materials” can
still receive the contradicted statement. Root-cause boundary: Track
material/revision semantics, not Demand or Task execution.

### Failure B — completed Demand cannot own later related branches

F explicitly described itself as a decision branch under the completed main
research, but persisted with `parent_id=null`. E likewise became a new root even
though it revised the same completed research.

Current Demand Sys only permits a live structural parent: the tool contract says
“Live parent Demand id”, and `set_parent` calls `_require_live(parent)`. This
means the graph cannot preserve a continuing need structure after the parent is
terminal. Execution continues correctly through new root Demands, but the
Demand organization loses the engagement lineage. Root-cause boundary: Demand
graph/lifecycle semantics; Task Sys remains independently serial.

### Recoverable tool-use friction

During F's Demand check, Market first called
`demand_sys.get_many(ids=[...])`; the schema requires `demand_ids`. It then made
an unrelated failed `context.get(key=tool_catalog)` attempt before recovering
with `demand_ids`, acknowledging the exact revision, and starting the Task.
Both failures were read-only/no-state-change. This did not block the run, but it
shows that the actor-facing action guidance is not yet sufficiently self-evident.

Browser work also encountered expected external failures (connection closure,
10-second navigation timeouts, and one stale closed-page selection). The actor
retained these limits, used other direct sources, and did not fabricate results.
No daemon `last_error`, failed schedule, leaked active Task, or terminal Demand
with an unacknowledged revision remained.

## 8. Requirement/evidence audit

| Acceptance requirement | Status | Exact evidence |
|---|---|---|
| Real PM and Market actors | Pass | Two isolated actors on installed Codex 0.144.6 with healthy app server/daemon/broker |
| Initial plus D/E/F IM messages | Pass | `msg-0ec9eacb46cd`, `msg-00216a360988`, `msg-a9abce3c0240`, `msg-e9a1e58019cc` |
| Supplement captured during active Task | Pass | D at `00:55:12`; C Task active `00:54:48–01:01:43` |
| Same-need supplement organization | Pass | D terminal `absorbed`, ref C; C revision advanced |
| E same-deliverable correction | Product pass / graph partial | v1.1 material correction succeeded; E persisted as a root after C was terminal |
| F child structure | **Fail** | F remained `parent_id=null`; current live-parent invariant prevents expected child edge |
| Every final Demand revision acknowledged | Pass | C `3/3`, D `2/2`, E `2/2`, F `2/2` |
| Single active Task | Pass | Sampled maximum one; three Market Task intervals are non-overlapping |
| Stale Task snapshot safety | Pass with explicit reconciliation | C Task basis 1; actor reread C revision 2 and completed with `expected_revision=2` |
| Adaptive artifact correction | Pass | v1.1 removes unsupported partnership evidence and moat use |
| Final research coverage | Pass with named evidence gaps | Main brief + decision branch cover requested areas and falsifiers |
| IM/daemon/turn/Task/artifact causality | Pass | Four handled IM origins, actor Demand checks, exact DemandRef Tasks, artifact + Track receipts |
| Single current Track truth | **Fail** | Superseded v1.0 remains current beside v1.1 |
| Clean isolated teardown | Pass | Exact browser/actor/root cleanup and residue checks below |

## 9. Teardown evidence

The browser cockpit had already been released by its idle lifecycle before
explicit teardown (`ownership=inactive`, no recorded browser port or owned PID).
The explicit release was therefore a clean no-op.

Cleanup then used only the two exact actor ids:

1. stopped and deleted Market `act-market-4b1f75215cd0`;
2. stopped and deleted PM `act-pm-677a02b6e4d4`;
3. verified isolated `instance list` returned `[]`;
4. ran isolated-root `env reset --yes`, which returned `removed=true`;
5. removed the now-empty run parent directory.

Final proofs:

- `/private/tmp/buddyswitch-zhipu-market-1784566044` is absent;
- both app-server sockets and both runtime-broker sockets are absent;
- process inspection found no exact actor id, run-root marker, app-server socket
  identity, or runtime-broker socket identity;
- the default-root public `instance list` remains `[]`.

The runtime acceptance left no actor, browser, process, socket, or isolated
state residue.
