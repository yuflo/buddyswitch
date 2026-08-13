# BuddySwitch Real Web Actor Experience Plan

> **Execution owner:** the current coordinating task executes this plan inline.
> Use the repository `buddyswitch-testing` contract only if a source-bound defect
> needs executable proof. This run is a real consumer-path acceptance exercise,
> not an excuse to add test infrastructure or repair every observation in place.

**Goal:** start the installed BuddySwitch Web UI, create one real
`secondary-market-investor` Actor Instance through the browser, exercise a
representative multi-turn investment-research journey, and leave reproducible
evidence of product, interaction, contract, state, and cleanup behavior.

**Architecture:** exercise the single current product path end to end:
`Browser -> Web -> Host Control -> RoleHost -> Actor/IM -> product modules`.
Use one longitudinal Instance so continuity, state projection, lifecycle, and
cleanup are observable without confounding framework behavior with differences
between Roles. Browser interactions are authoritative for the user journey;
public CLI reads and process/resource inspection corroborate terminal truth but
do not replace the UI.

**Surfaces:** installed BuddySwitch runtime, local Web UI, in-app browser,
`secondary-market-investor` Role, Communication/IM, Demand/Task/Track/Artifact
projections, Host Control lifecycle, Browser runtime, and public read-only CLI.

---

## 1. Acceptance sentence

From an empty launcher baseline, a user can discover and start the reviewed
`secondary-market-investor` Role in the Web UI, send a realistic long-horizon
research request, observe delivery and Actor progress/results, continue the same
research without duplicate state, stop and resume the Instance without losing
durable work, inspect the resulting Task/Track context, and delete the Instance;
the UI, public contracts, canonical projections, runtime status, and resource
cleanup agree at every terminal step.

This run may legitimately discover that part of the sentence is false. In that
case the output is an evidence-backed finding with exact reproduction and owner,
not a diluted completion claim.

## 2. Why this shape

Three approaches were considered:

1. **One longitudinal real Instance — selected.** Deeply exercises one complete
   user journey and isolates framework behavior.
2. **Several Roles in parallel — rejected for this run.** Wider coverage but
   Role-specific behavior would obscure Web/Host/Actor framework defects.
3. **API-first smoke with UI spot checks — rejected.** Faster, but it bypasses
   discoverability, feedback, waiting, continuity, and cleanup experience.

The selected flow tests the product the way a real user experiences it while
keeping the destructive surface bounded to one newly created Instance.

## 3. Entry baseline and protected state

Entry facts on 2026-08-13:

- branch `fea-tool` is clean at `4010434` and equals `origin/fea-tool`;
- `./buddyswitch-codex instance list` reports no Instances;
- `./buddyswitch-codex env status` reports zero Instances and inactive Browser;
- the installed Role catalog contains `secondary-market-investor`;
- `projects/app` is an intentional empty mount point, not a sample application.

Before startup, snapshot external-safe Task and Track IDs and the complete
process/socket inventory attributable to BuddySwitch. Preserve unrelated state,
the installed runtime, `docs/spec`, user browser data, and every pre-existing
product object. Do not use role-wide or environment-wide cleanup merely for
convenience.

## 4. Scenario design

### Scenario A — empty state and Role discovery

1. Start the installed Web server on a free local port.
2. Open the Web UI in the in-app browser at a desktop viewport.
3. Capture the empty Team room and inspect Role selection, primary action,
   initial status, keyboard semantics, console errors, and failed requests.
4. Select `Secondary Market Investor` and start exactly one Instance.
5. Observe starting, ready, selected-Actor, capability, and action states without
   using the CLI to perform the lifecycle action.

Expected outcome: the Role is understandable before creation; the pending state
appears immediately; one Actor becomes interactive; UI and public instance
status agree.

### Scenario B — realistic first research request

Send through the Web composer:

> 围绕港股智谱 02513 建立一份长期投资研究工作，不执行交易。先检查当前
> BuddySwitch 上下文，围绕中国 AI to B 预算池、智谱的价值捕获位置、选手
> 资格、估值赔率与入场条件，形成核心 thesis、五项待验证假设、明确证伪
> 条件和下一步研究动作。公开事实必须注明日期和证据质量；未经验证的 ARR
> 只能作为假设。把需要持续推进的内容写入当前产品状态，避免只在回复里描述。

Observe optimistic send, delivery acknowledgement, pending/work feedback,
response rendering, Task/Track/Artifact projections, error semantics, scroll,
and whether the user can understand what is happening while the Actor works.

Expected outcome: exactly one visible outbound Message reaches the selected
Actor; progress and terminal status do not contradict each other; durable state
matches the response's claims.

### Scenario C — continuity and non-duplication

After the first request reaches a terminal or stable waiting state, send:

> 继续同一项研究，不新建重复 Track。把 Anthropic 的企业收入经验拆成客户
> 新增 AI 支出与从云、软件、IT 服务、外包或知识工作人力迁移的预算，并映射
> 到中国市场。随后对智谱构造质量调整后的前瞻 EV/S 20、25、30 倍三个入场
> 情景，列出每个情景成立所需的 ARR 构成、毛利、资本开支、稀释和竞争证据；
> 信息不足必须明确保留为未知。

Expected outcome: the Actor identifies and advances the same durable work,
does not manufacture unsupported facts, and does not create a duplicate Track
for the same outcome.

### Scenario D — lifecycle continuity

1. Capture current Actor, Task, Track, and conversation state.
2. Stop the Instance through the Web UI and confirm disabled/enabled actions and
   public status.
3. Resume it through the Web UI and wait for the same Actor to become interactive.
4. Send:

> 从当前持久状态恢复：指出上一轮研究使用的 Track、Task 或 Artifact 标识、
> 已完成到哪里、仍未解决的三项风险；不要重建重复对象，也不要把停止前的
> 推测改写成已确认事实。

Expected outcome: lifecycle state and controls are coherent, durable research
survives, and the Actor can name prior work rather than reconstructing a fresh
parallel history.

### Scenario E — destructive confirmation and cleanup

1. Open Delete, test that an incorrect confirmation cannot proceed, and inspect
   focus/escape behavior.
2. Confirm with the exact Actor ID and delete through the Web UI.
3. Verify the roster, public Instance list, environment status, runtime
   processes, sockets, locks, Browser process, and attributable temporary files.
4. Compare Task/Track IDs with the entry snapshot. Do not delete unrelated
   objects. If Actor-owned product residue remains and no exact public deletion
   contract exists, preserve it as a cleanup finding rather than bypassing the
   product boundary.

Expected outcome: deletion is explicit, recoverable until final confirmation,
and removes the Instance's host resources without touching unrelated state.

## 5. Evidence protocol

For each important step:

1. take a fresh accessibility/DOM snapshot before acting;
2. perform one unambiguous UI action;
3. wait for a product-level state change rather than a fixed arbitrary delay;
4. capture and inspect a numbered screenshot before accepting it;
5. record visible copy, control availability, elapsed waiting behavior, console
   errors, failed/non-2xx requests, public status, and relevant object IDs;
6. distinguish observed fact, source-bound inference, and unresolved question.

Store the textual run record beside this plan as
`2026-08-13-buddyswitch-real-web-actor-experience-report.md`. Store accepted
screenshots in a run-specific evidence directory under `docs/memo` only when
they are necessary to support a finding; reject blank, loading, cropped, or
wrong-state captures. Keep the evidence set small enough to remain useful.

Each finding must include:

- severity: `P0` blocking, `P1` major outcome failure, `P2` material friction,
  or `P3` polish;
- scenario and exact UI step;
- expected and observed behavior;
- screenshot/request/log/runtime evidence;
- semantic owner and affected consumer path when source diagnosis is possible;
- reproducibility and cleanup impact;
- disposition: confirmed defect, design risk, evidence gap, or expected behavior.

## 6. Efficient verification

This run does not modify executable source by default, so it does not begin with
a repository-wide test suite. Verification follows the shortest meaningful
consumer path:

1. real browser journey and accepted screenshots;
2. UI network/console evidence for the exact step;
3. public CLI readback for Instance, Task, and Track terminal truth;
4. exact process/socket/resource cleanup probes;
5. source inspection only for an observed contradiction or unclear owner;
6. one currently discoverable focused test only when it directly proves or
   reproduces a diagnosed boundary.

Do not run `./buddyswitch-test full` for an observation-only audit. If a defect
is later authorized for repair, establish the smallest exact RED, make the
owner-correct fix, reprovision when package source changes, run exact/affected
GREEN, then freeze and choose FINAL breadth under `buddyswitch-testing`.

## 7. Execution states

- [ ] `FRAME` — freeze baseline, acceptance sentence, tasks, and cleanup scope.
- [ ] `TRACE` — map Browser/Web/Host/Actor/IM/state owners for each scenario.
- [ ] `PROVE` — capture the empty Web state and exact pre-run identities.
- [ ] `BUILD` — create the real Instance and execute Scenarios B–D through UI.
- [ ] `REPLACE` — inapplicable unless an authorized defect repair replaces a path.
- [ ] `VERIFY` — execute Scenario E and reconcile all terminal truths.
- [ ] `ACCEPT` — audit every scenario claim and publish findings/residual risk.

## 8. Stop and escalation conditions

Stop the affected scenario, preserve evidence, and diagnose before retrying if:

- creation produces more than one Instance or contradictory terminal status;
- the Web UI requires bypassing its own API or lifecycle control;
- an Actor action would execute a trade, write project source, expose secrets,
  or exceed the Role's read-only/source and no-trading boundary;
- a failure leaves an attributable process, socket, lock, or Browser resource;
- a retry would hide a failure/flake rather than test an explicit recovery path;
- cleanup would require deleting pre-existing user or product state.

Product fixes are outside this run's automatic authority. A confirmed defect is
diagnosed and recorded first; implementation begins only after its scope is
explicitly accepted.

## 9. Completion record

Status: `READY — execution not yet started`

The report will record exact server/runtime identity, Actor ID, scenario timing,
accepted screenshots, public object IDs, console/network evidence, cleanup proof,
findings, omitted checks, and final acceptance or rejection.
