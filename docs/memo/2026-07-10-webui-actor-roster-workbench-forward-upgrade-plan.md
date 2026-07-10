# WebUI Actor Roster Workbench Forward Upgrade Plan

Date: 2026-07-10
Worktree: `fea-webui`
Status: authoritative implementation plan

## 1. Task Restatement

### Objective

Rebuild the actor lifecycle interaction surface in Team room so an operator can immediately answer four questions without scanning unrelated panels:

1. Which actor or Start operation is selected now?
2. Where did the actor created by Start appear?
3. Which exact actor will Stop, Resume, or Delete affect?
4. Which actors are active work and which are stopped inventory?

The selected context must remain part of the existing direct-thread workspace. It must not become a replacement for the conversation, a second detail page, or a mock thread renderer.

### Core Principles

- Rebuild forward through one production path. Do not retain flat and grouped rosters side by side.
- Keep semantics in the owning layer. Backend APIs and lifecycle operation truth remain unchanged; this task rebuilds the browser projection and interaction only.
- Preserve current product contracts before changing presentation. Markdown, direct conversation, model config, Tracks, Open TUI, Clear, Send, Interrupt, lifecycle queueing, and request-race protection remain live features.
- Prefer explicit state and pure render helpers over DOM inference or event-handler duplication.
- Prove behavior with focused tests first, then contract tests, then the live `http://127.0.0.1:8766/` path.
- Delete replaced markup, styling, copy, and event paths. Do not ship old and new action surfaces together.

## 2. Current-System Audit

### What Is Already Correct And Must Stay

| Contract | Current owner | Required preservation |
| --- | --- | --- |
| Markdown parsing, sanitizing, and code highlighting | `markdown-renderer.js`, local `markdown-it`, DOMPurify, highlight.js | `renderMessageContentHtml()` and `.markdown-body` remain the only message rendering path. No prototype thread HTML enters production. |
| Stable direct-thread bubbles and new-reply behavior | `renderImConversation()`, `room-thread`, `new-reply-chip` | Actor switching and lifecycle rendering must not rewrite the message pipeline or scrolling contract. |
| Latest actor intent wins | `selectActor()`, request ids, AbortControllers | Grouping and header rendering must not weaken stale-response guards. |
| Independent actor card and conversation loading | `refreshActorCard()`, `refreshConversation()` | Header updates immediately from roster state and later reconciles without coupling the two requests. |
| Lifecycle queue and same-actor protection | `/api/operations`, `runLifecycleAction()`, operation polling | UI reuses the existing queue; no second optimistic operation engine. |
| Actor model-config payload editor | right-side model-config card and its state | DOM ids, draft preservation, save/revert behavior, and backend validation stay unchanged. |
| Team room messaging and runtime tools | Send, Interrupt, Open TUI, Clear | Controls retain their current handlers and availability semantics. |
| Tracks workspace | existing Track list/detail/rail | No Track markup, APIs, copy, or tests change in this slice. |

### Confirmed Defects

#### A. Flat roster hides lifecycle structure

`renderActorRowsHtml()` concatenates active Start operations and every actor into one list. Active and inactive rows have equal hierarchy, so stopped inventory increasingly competes with current work.

#### B. Selection is technically present but visually weak

The selected row differs only through a pale border and background. It has no persistent accent edge and no `aria-selected` contract. On a long roster, selection can be lost during a quick actor switch.

#### C. Start acknowledgement is visible but not organized

Start operation rows are selected immediately, which is correct, but they are mixed into the same flat list and primarily expose an operation id. They need a stable Starting group and a strong selected treatment before the final actor id exists.

#### D. Action target is spatially detached

The center header says only `Direct thread`; actor identity is in the right rail while lifecycle controls are lower in a separate Actions card. Stop and Delete therefore require the operator to correlate three regions.

#### E. Delete executes without a target confirmation boundary

Clicking Delete directly invokes the lifecycle API. There is no confirmation showing actor id, role, and state. The terminal delete path clears selection even when another actor remains, leaving the operator without continuity.

#### F. Stop completion changes status but not information architecture

The actor row reconciles to `inactive`, yet it remains in the same undifferentiated list. There is no explicit Stopped group to make the state transition visible.

### Residue And Boundary Audit

The active frontend no longer contains the retired monolithic `refreshAll()` or `renderAll()` interaction path, the old handwritten Markdown parser, or the old Actor Console shell. Those historical memo descriptions are not current implementation work and must not be reintroduced.

The current file size of `app.js` is not by itself a reason to add a module system. Static asset serving already has one stable script path, and this task does not justify backend route or bundler changes. New logic stays as small pure functions within the existing browser module.

## 3. Product Observations Applied

These references inform interaction contracts only:

- Docker Desktop lists running and stopped containers in one lifecycle workspace, exposes direct lifecycle actions, and opens detailed information for the selected container: https://docs.docker.com/desktop/use-desktop/container/
- Docker Desktop has explicitly kept start/stop and delete as the primary visible row actions while moving secondary actions behind a menu: https://docs.docker.com/desktop/release-notes/
- GitHub requires typing the repository name to verify the target before repository deletion: https://docs.github.com/en/repositories/creating-and-managing-repositories/deleting-a-repository
- Amazon EC2 keeps a terminated instance visible briefly with a terminal state after confirmation, reinforcing that lifecycle transitions should remain legible instead of disappearing without context: https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/terminating-instances.html

BuddySwitch-specific conclusion:

```text
roster hierarchy identifies lifecycle state
strong row selection identifies current object
compact thread header binds identity to primary lifecycle actions
typed Delete confirmation binds irreversible intent to an exact actor id
operation reconciliation moves the same actor visibly between groups
```

## 4. Target Architecture

### 4.1 Roster Projection Boundary

The browser derives exactly three groups from existing actor and operation state:

```text
Starting
  active start operations without a confirmed actor row

Active
  actors whose effective lifecycle status is not inactive
  includes stopping, resuming, clearing, and deleting overlays

Stopped
  actors whose effective runtime status is inactive
```

`Stopped` is collapsed by default. It expands when:

- the user opens it;
- a selected actor reconciles from active to inactive after Stop;
- the only available initial actor is stopped;
- a stopped actor becomes the explicit selected target through reconciliation.

The group state is one boolean in `createState()`. No data is copied into separate active/stopped stores; `state.actors` remains the authoritative roster snapshot.

New pure helpers:

```text
actorRosterGroup(state, actor)
partitionActorRoster(state)
renderRosterGroupHtml(state, group)
preferredActorId(actors, options)
```

### 4.2 Selection Contract

Every actor and operation row uses:

- `role="option"`;
- `aria-selected="true|false"`;
- a strong left accent, clear background, and focus-visible outline;
- role, actor/operation id, and effective state in its accessible label.

Selection paints before console or conversation requests settle. Existing request-id and AbortController guards remain unchanged.

### 4.3 Compact Conversation Context

Replace the static center header copy with a compact selected-context header. It contains:

- actor avatar and role;
- full actor id;
- effective lifecycle and health badges;
- current lifecycle operation receipt when present;
- Refresh;
- exactly one primary lifecycle choice, Stop or Resume, plus Delete.

When a Start operation is selected before actor creation finishes, the header shows the role, operation id, and queued/starting state with actor actions protected.

This header is metadata and controls only. It does not render conversation content. The existing `#room-thread`, `#im-conversation`, Markdown renderer, composer, Send, Interrupt, and new-reply chip remain structurally unchanged.

Primary lifecycle controls move from the right Actions card into this header by moving their existing DOM ids. They are not duplicated. The right card becomes `Tools` and retains Open TUI and Clear, which are secondary runtime/thread utilities.

Rendering boundaries after the change:

```text
renderActorList()               roster groups and row selection
renderSelectedActorContext()    selected identity, state, Stop/Resume/Delete, receipts
renderComposer()                draft, Send, Interrupt only
renderActorTools()              Clear and existing Open TUI path
renderActorDetail()             model config, runtime, task, Tracks facts
renderImConversation()          only direct-thread messages and Markdown
```

### 4.4 Delete Confirmation Boundary

The only production Delete click path opens one modal dialog. The dialog snapshots and displays:

- exact actor id;
- role;
- current runtime state;
- irreversible effect.

The confirmation button remains disabled until the exact actor id is typed. Escape, Cancel, backdrop click, and successful completion close the dialog. Focus enters the input and returns to the trigger on cancel.

The confirmed actor id is passed explicitly to lifecycle execution. The API request must not infer a different target from later DOM text.

After successful deletion, selection moves deterministically to the nearest remaining roster actor, preferring active actors when the deleted target has no adjacent survivor. The new selection immediately gets the normal console and conversation load path. If no actors remain, the empty state is explicit.

### 4.5 Lifecycle Transition Contract

```text
Start accepted
  -> selected row appears in Starting now
  -> operation settles with actor id
  -> selected pending actor row appears in Active
  -> roster confirms authoritative actor

Stop accepted
  -> selected Active row shows stopping
  -> header names the same actor and shows operation receipt
  -> terminal inactive projection is applied
  -> Stopped expands and the selected row moves there without stale active flash

Resume accepted
  -> selected Stopped row shows resuming in its current group
  -> terminal active projection is applied
  -> selected row moves to Active

Delete confirmed
  -> exact target row/header show deleting
  -> terminal success removes it
  -> next actor becomes selected and visible
```

## 5. Strict Scope

### Production files allowed

- `tools/launcher/assets/web-management/index.html`
- `tools/launcher/assets/web-management/app.js`
- `tools/launcher/assets/web-management/styles.css`
- `tests/web_management_ui_state.test.js`
- `tests/web_management_ui_contract.test.js`
- `tests/test_web_management.py` only if static-asset assertions require current markup updates

### Documentation files required

- this master plan in `docs/memo/`
- one implementation/acceptance document per stage in `docs/spec/2026-07-10-webui-actor-roster-workbench/`

### Explicitly out of scope

- `tools/launcher/web_management.py` lifecycle/API behavior
- launcher runtime locks, queues, operations, DTOs, and object stores
- `markdown-renderer.js` and vendored Markdown dependencies
- IM router/session/message contracts
- model-config API or payload schema
- Track APIs or write controls
- a framework, bundler, icon package, frontend state library, feature flag, compatibility renderer, or alternate roster view

## 6. Implementation Stages

### Stage 1: Roster Semantics And Strong Selection

Write first:

- `docs/spec/2026-07-10-webui-actor-roster-workbench/01-roster-selection-and-grouping.md`

Red tests:

1. Starting, Active, and Stopped headings render with accurate counts.
2. Inactive actors are absent from Active and present in Stopped.
3. Stopped is collapsed by default.
4. Selected stopped actor is revealed after Stop terminal reconciliation.
5. Start operation context is visibly selected inside Starting.
6. Every row has `aria-selected`; selected CSS has a persistent accent and focus-visible state.
7. Initial auto-selection prefers an active actor; a stopped-only roster opens Stopped.

Implementation:

- add one stopped-group expansion state;
- replace the flat renderer with grouped projection helpers;
- add delegated stopped-group toggle handling;
- strengthen selected/focus CSS;
- keep actor and operation row click handlers delegated.

Focused verification:

```bash
node tests/web_management_ui_state.test.js
node tests/web_management_ui_contract.test.js
node --check tools/launcher/assets/web-management/app.js
```

### Stage 2: Compact Selected Context Without Conversation Regression

Write first:

- `docs/spec/2026-07-10-webui-actor-roster-workbench/02-compact-selected-context.md`

Red tests:

1. Center header renders selected role, full actor id, runtime, and health.
2. Header updates synchronously on actor selection while console/conversation remain pending.
3. Start operation selection renders operation identity without inventing an actor id.
4. Stop/Resume/Delete ids exist exactly once and live in the compact header.
5. Right card retains Open TUI, Clear, model config, runtime, task, and Track summary.
6. `renderComposer()` still preserves Send/Interrupt semantics during lifecycle operations.
7. Existing Markdown output, new-reply behavior, and rapid-switch tests stay green.

Implementation:

- rebuild `.room-header` markup as selected context;
- move existing primary lifecycle button nodes, without duplicate ids or handlers;
- add `renderSelectedActorContext()`;
- narrow `renderComposer()` to message controls;
- keep right-side detail and tools as independent regions;
- add responsive wrapping without changing thread dimensions or Markdown CSS.

Focused verification:

```bash
node tests/web_management_markdown_renderer.test.js
node tests/web_management_ui_state.test.js
node tests/web_management_ui_contract.test.js
```

### Stage 3: Target-Aware Delete And Selection Continuity

Write first:

- `docs/spec/2026-07-10-webui-actor-roster-workbench/03-delete-confirmation-and-reselection.md`

Red tests:

1. Delete click opens a dialog naming actor id, role, and state and does not call the API.
2. Confirmation remains disabled for partial or wrong text.
3. Exact actor id enables confirmation and sends one DELETE for that id.
4. Cancel/Escape closes without a request and restores focus.
5. Delete cannot be confirmed while another lifecycle operation protects the actor.
6. Successful delete selects and loads the next remaining actor.
7. Empty roster after delete produces no stale actor/header/conversation state.

Implementation:

- add one dialog to `index.html`;
- add explicit confirmation state and pure validation;
- replace the direct Delete click handler with open/confirm/close handlers;
- preserve the existing operation queue and terminal reconcile path;
- replace delete-time blank selection with deterministic next selection.

Focused verification:

```bash
node tests/web_management_ui_state.test.js
node tests/web_management_ui_contract.test.js
node --check tools/launcher/assets/web-management/app.js
```

### Stage 4: Residue Cleanup, Full Regression, And Live Acceptance

Write first:

- `docs/spec/2026-07-10-webui-actor-roster-workbench/04-full-acceptance-and-residue.md`

Residue assertions:

- no flat roster return path remains;
- no duplicate lifecycle action card or duplicate action ids remain;
- no Delete handler directly calls the API before confirmation;
- no prototype-only `renderThread`, mock actor facts, or mock operation timeline enters production;
- no Markdown parser or sanitizer logic enters `app.js`;
- no backend/API changes exist in the diff;
- no edits exist outside `fea-webui`.

Full automated verification:

```bash
node --check tools/launcher/assets/web-management/app.js
node --check tools/launcher/assets/web-management/markdown-renderer.js
node tests/web_management_markdown_renderer.test.js
node tests/web_management_ui_state.test.js
node tests/web_management_ui_contract.test.js
python3 -m pytest tests/test_web_management.py -q
python3 -m pytest tests/test_im_web_management_projection.py -q
git diff --check
```

Live browser acceptance on `http://127.0.0.1:8766/`:

1. Confirm port 8766 is served by this worktree.
2. Reload at desktop width; capture the initial Team room state.
3. Switch at least three actors; selection must repaint immediately and remain unmistakable.
4. Confirm active and stopped actors are separated and Stopped collapses/expands.
5. Start one low-risk actor; confirm the selected Starting row appears immediately and later becomes the selected actor row.
6. Stop that actor; confirm the target remains named, shows stopping, and moves into expanded Stopped without stale active flash.
7. Resume it; confirm it moves back to Active and remains selected.
8. Open Delete; verify wrong confirmation cannot submit, Cancel is harmless, then complete exact confirmation for the disposable actor.
9. Confirm deletion selects the next actor instead of leaving an unexplained blank workspace.
10. Switch to an actor with Markdown history and verify headings, lists, links/code, table overflow, bubble sizing, scrolling, and new-reply behavior remain intact.
11. Verify Send, Interrupt, Clear, Open TUI, model-config Configure/Save/Revert states, Refresh, and Tracks still render and respond according to their existing contracts.
12. Repeat layout checks at a narrow viewport; no header/action overlap, hidden controls, horizontal page overflow, or broken thread scrolling.
13. Inspect browser console and failed network requests; no new errors are accepted.

## 7. Requirement Traceability

| User concern | Design response | Primary proof |
| --- | --- | --- |
| Started actor is hard to find | selected Starting group row, then selected pending actor row | Stage 1 state test + live Start |
| Delete target is hard to identify | actor identity beside Delete plus exact-id modal | Stage 3 tests + live confirmation |
| Stop target is hard to identify | actor identity, status, and Stop share compact header | Stage 2 test + live Stop |
| Actor switching lacks highlight | strong persistent selected row + `aria-selected` | Stage 1 CSS/HTML tests + live switching |
| Stopped and active actors are mixed | Starting/Active/Stopped projection and collapsed Stopped | Stage 1 grouping tests + live roster |
| Selected area conflicts with conversation | compact metadata/action header only; thread and composer unchanged | Stage 2 contract + Markdown regression |
| Existing WebUI features may regress | explicit protected-surface matrix and full regression set | Stage 4 full suite + live feature pass |
| No historical residue or dual track | old flat/action/direct-delete paths removed and scanned | Stage 4 residue assertions |

## 8. Completion Gate

This plan is complete only when all four stage documents exist, every stage begins with failing behavior tests, the production implementation uses one grouped roster and one selected-context action path, every focused and full verification command passes, browser acceptance is completed on the worktree-owned 8766 server, and the final audit reports any residual risk explicitly.

No stage may be marked complete because its code looks correct. It must have fresh command output and, where user-visible, browser evidence.

## 9. Plan Self-Review

- Goal, principles, defects, architecture risks, module boundaries, scope, tests, residue checks, and live acceptance are all explicit.
- The plan modifies only frontend projection and tests; backend lifecycle truth stays in its owning layer.
- The plan contains no compatibility mode, feature flag, duplicate roster, duplicate action surface, or fallback Markdown renderer.
- The selected-context design answers the user's concern without replacing the conversation UI.
- Markdown and every named existing feature have a preservation owner and an acceptance step.
- Every implementation stage has an exact pre-development `docs/spec` artifact and focused commands.
- Destructive testing is limited to an actor created for this acceptance run.

## 10. Completion Record

Completed on 2026-07-10.

- Stages 1-4 were implemented through one grouped roster, one compact selected-context action surface, and one exact-id Delete confirmation path.
- All focused and full automated verification commands passed; the final counts were 5 Markdown renderer tests, 81 Web Management API tests, and 8 IM projection tests, with the state/contract suites, JavaScript checks, residue scan, and `git diff --check` also passing.
- Live acceptance ran on the worktree-owned `http://127.0.0.1:8766/` server with three disposable actors. Start, Stop, Resume, switching, confirmed Delete, newer-selection precedence, Markdown rendering, model config, Tracks, Refresh, and tool availability were verified.
- The final live roster contained zero actor or operation rows after cleanup. No backend, Markdown renderer/vendor, IM, Tracks, runtime-object, or parent-checkout changes were introduced.
- Desktop visual inspection passed. At 390 x 844 live DOM geometry showed one stacked column, no element outside the viewport, and no horizontal overflow. Narrow bitmap capture timed out in the Browser client; this is the only residual evidence limitation and not a known product defect.
- Final independent review exposed and closed three previously untested lifecycle races: newer actor selection now wins over Start completion, concurrent Starts reconcile through one multi-actor pending map, and Delete revalidates target runtime eligibility at dispatch. The superseded single pending-actor fields were deleted rather than retained as compatibility state.
