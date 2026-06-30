# Task Sys Proactive Rebuild Codebase Survey

Source memo: `docs/memo/2026-06-29-task-sys-proactive-rebuild.md`

## Survey Commands Used

```bash
rg --files -g 'AGENTS.md' -g 'docs/memo/2026-06-29-task-sys-proactive-rebuild.md' -g 'docs/bitter/**' -g 'docs/spec/**'
rg -n "submit_turn|submit_parent_prompt|submit_side_triage_prompt|submit_parent|side_triage|side triage|TASK CHECKPOINT|turn complete|turn_complete|checkpoint|interrupt|taskbox|active-task|active_task|task-management|task_management" tools scripts tests buddyswitch/skills -S
rg -n "message_inbound|im_wake|track_comment|browser_inbound|local trigger|scheduled|daemon_triggers|mailbox|wake|submit" tools/launcher scripts/env tests -S
rg -n "prompt|parent|side|actor" tools/launcher/*handler.py tools/launcher/*inbound.py tools/launcher/daemon*.py tools/launcher/central_daemon_core.py tools/launcher/submit_turn.py tools/launcher/task_checkout_handler.py -S
rg -n "def render_.*prompt|\[[A-Z ]+(MESSAGE|COMMENT|CHECKPOINT|TRIAGE)|Required action|submit_parent_prompt\(|submit_side_triage_prompt\(|launcher_submit_turn\.submit_turn\(|app_server\.input_turn\(|app_server\.side_start\(" tools scripts tests -S
rg -n "wake_actor|wake_im_actor|deliver_track_comment_added|deliver_signal|mailbox\.local_trigger|mailbox\.schedule_trigger|sweep_due_scheduled_triggers|dispatch_trigger\(" tools scripts tests -S
rg -n "taskbox|TaskViewModel|E_ACTIVE_TASK_REQUIRED|TASK_REQUIREMENT_ACTIVE_TASK_REQUIRED|\[TASK CHECKPOINT\]|task\.checkout|task-management" scripts buddyswitch/skills tests -S
```

## Current Old Path Map

| Old path | Current files and functions | Current behavior | Phase |
| --- | --- | --- | --- |
| CLI user input directly submits raw text to actor | `buddyswitch-codex:382` `instance_input`; `tools/launcher/submit_turn.py:23` `submit_turn`; `tools/launcher/app_server.py:806` `input_turn` | `instance input --text` reads the actor thread id and calls `submit_turn.py`, which delegates to app-server `turn/start` or `turn/steer` with raw `text_input_payload(text)`. | Phase 2 |
| Web user input directly submits raw text to actor | `tools/launcher/web_management.py:358` routes `POST /api/instances/<actor>/input`; `tools/launcher/web_management.py:546` `_send_input`; `tools/launcher/web_management.py:591` `_run_input_command` | Web calls the same `instance input` CLI path with raw text. | Phase 2 |
| Manual side input remains exposed as raw side text | `buddyswitch-codex:565` `instance_side`; `tools/launcher/web_management.py:360` and `tools/launcher/web_management.py:601` | `instance side --text` can start or steer side threads directly through app-server side APIs. This is a manual runtime command today, not task sys scheduled side processing. | Phase 3 |
| IM message created wakes actor via business handler prompt | `scripts/env/services/messages.py:173` `send_im_message`; `scripts/env/services/messages.py:280` wake payload; `scripts/env/tool_runtime/daemon_client.py:285` `wake_im_actor`; `tools/launcher/im_wake_handler.py:39` `_parent_prompt`; `tools/launcher/im_wake_handler.py:57` `_side_prompt`; `tools/launcher/im_wake_handler.py:82` `handle` | IM service creates an `im.message.created` wake payload. The daemon handler validates target actor, renders IM-specific parent or side prompt, then calls `runtime.submit_parent_prompt` when idle or `runtime.submit_side_triage_prompt` when running. | Phase 2, Phase 3, Phase 4 |
| Track comment added wakes actor via business handler prompt | `scripts/env/tools/track/_impl.py:285` `_deliver_track_comment_added`; `scripts/env/tool_runtime/context.py:389` `deliver_track_comment_added`; `scripts/env/domain/track_comments.py:194` and `:222` render parent/side prompts; `tools/launcher/track_comment_added_handler.py:99` `_handle_track_comment_added` | Track comment delivery becomes a daemon signal. The handler reads Track/comment state, decides intended recipient, renders Track-specific parent or side prompt, then calls parent or side runtime submit helpers. | Phase 2, Phase 3, Phase 4 |
| Turn complete directly submits old task checkpoint prompt | `tools/launcher/task_checkout_handler.py:31` `completed_turn_for_checkout`; `tools/launcher/task_checkout_handler.py:52` `send_checkout_prompt`; `scripts/env/domain/task_tui.py:50` `render_stop_task_tui` | App-server completion notification becomes a daemon trigger. Handler reads taskbox `TaskViewModel`, renders `[TASK CHECKPOINT]`, and submits it to the parent via `runtime.submit_parent_prompt`. | Phase 2, Phase 5 |
| Side triage direct runtime helper | `tools/launcher/daemon_core.py:1082` `_start_side_triage`; `tools/launcher/daemon_core.py:1126` `_send_side_triage`; `tools/launcher/daemon_core.py:1172` `submit_side_triage_prompt` | Handler-facing runtime surface starts or reuses side thread and sends prompt text directly. | Phase 3 |
| Parent direct runtime helper and interrupt policy | `tools/launcher/daemon_core.py:933` `_submit_parent_once`; `tools/launcher/daemon_core.py:975` `_interrupt_parent`; `tools/launcher/daemon_core.py:1059` `submit_parent_prompt`; `scripts/env/tool_runtime/context.py:403` `request_parent_message_handling` | Handlers and message tool side path pass a prompt and `interrupt_policy`; daemon runtime decides and executes submit/interrupt. | Phase 4 |
| IM side marks message as `needs_parent` and submits parent prompt | `scripts/env/tool_runtime/im_client.py:268` `_request_parent_message_handling`; `scripts/env/tool_runtime/im_client.py:274` `_render_parent_required_prompt`; `scripts/env/tool_runtime/context.py:403` `request_parent_message_handling` | Side can call message `mark(needs_parent)`; the tool renders a parent-required prompt and directly calls daemon runtime parent submit with `ensure_stopped`. | Phase 3, Phase 4 |
| Taskbox is private task truth | `scripts/env/repos/tasks.py:2`; `scripts/env/domain/task_management.py:1`; `scripts/env/tools/task/_impl.py:31`; `scripts/env/tools/task/tool.py:157`; `buddyswitch/skills/shared/task-management/SKILL.md:8` | Actor-facing task tool manages instance-local `taskbox/<role>/tasks/*.json` and `history.md` as the task model. | Phase 6 |
| Active-task gate is parallel task truth enforcement | `scripts/env/tool_runtime/registry.py:358` `_active_task_required_rejection`; `scripts/env/tool_runtime/registry.py:424` `_has_active_task_anchor`; `scripts/env/tool_runtime/registry.py:626` pre-dispatch gate | Some env tool actions are blocked unless taskbox has `TaskViewModel.current_anchor`. This forces actors to maintain taskbox state before tool use. | Phase 6 |

## Runtime Maintenance Paths Not Actor-Driving

- `tools/launcher/browser_page_expired_handler.py` handles `browser.page.expired` scheduled triggers by refreshing page idle state, checking expiry, closing stale pages, or forgetting lifecycle state. It does not submit parent input, start side, or render actor prompts. It can remain daemon/browser maintenance unless a future browser trigger is meant to drive actor work.
- `tools/launcher/central_daemon_core.py:302` `_deliver_signal`, `tools/launcher/daemon_mailbox.py:201` `dispatch`, and `tools/launcher/daemon_triggers.py` are physical routing and envelope normalization layers. They contain actor route projections and mailbox dispatch; the boundary problem is that their trigger dispatcher currently routes straight to business handlers that wake actors.
- `tools/launcher/daemon_core.py:1505` `sweep_due_scheduled_triggers` is scheduled trigger delivery infrastructure. It should stay only as physical scheduled dispatch; any scheduled trigger that drives actor work must become a task sys ingest envelope.
- `buddyswitch-codex:1390` `instance_interrupt` and Web `POST /api/instances/<actor>/interrupt` are explicit human/runtime control surfaces. They are not side outcomes, but Phase 4 must prevent business handlers and side results from deciding interrupt outside task sys.

## Current Test Map

| Test area | Current old behavior locked | Phase |
| --- | --- | --- |
| `tests/test_buddyswitch_launcher.py:2980`, `:3022`, `:3057` | `instance input` starts or steers actor turn with raw user text. | Phase 2 |
| `tests/test_submit_turn.py:38`, `:120` | `submit_turn.py` delegates directly to app-server input and launcher input routes through that helper. | Phase 2, Phase 4 actuator split |
| `tests/test_im_wake_handler.py:67`, `:85` | IM wake handler submits direct parent prompt when idle and side triage when running. | Phase 2, Phase 3 |
| `tests/test_track_comment_added_handler.py:395`, `:453` | Track comment handler submits direct parent prompt or side triage prompt and asserts old prompt text. | Phase 2, Phase 3 |
| `tests/test_task_checkout_handler.py:291` | Completed parent turn submits `[TASK CHECKPOINT]` prompt through `runtime.submit_parent_prompt`. | Phase 5 |
| `tests/test_buddyswitch_launcher.py:5268` | End-to-end daemon completion path submits a prompt starting `[TASK CHECKPOINT]`. | Phase 5 |
| `tests/test_daemon_service_contract.py:284` through `:755` | Daemon runtime public handler surface is `parent_activity`, `submit_parent_prompt`, `submit_side_triage_prompt`; tests cover direct parent submit, interrupt policies, and side triage prompt start/reuse. | Phase 3, Phase 4 |
| `tests/test_message_tool_im_client.py:194` and `tests/test_env_tool_response_contract.py:779` | `message.mark(needs_parent)` attempts direct parent prompt submit and fails without mutating IM state. | Phase 3, Phase 4 |
| `tests/test_task_input_context.py`, `tests/test_task_env_tool.py`, `tests/test_task_management_skill_architecture.py`, `tests/test_env_tool_semantic_contract.py:515` | Taskbox and TaskViewModel are the actor-facing task model and tool contract. | Phase 6 |
| `tests/test_env_tool_active_task_gate.py`, `tests/test_runtime_broker.py:470` | Active-task pre-dispatch gate requires taskbox current anchor for selected tool actions. | Phase 6 |
| `tests/test_daemon_trigger_router.py`, `tests/test_daemon_mailbox.py`, `tests/test_daemon_core.py` | Daemon trigger normalization, mailbox delivery, local trigger, scheduled trigger, and handler dispatch infrastructure. These should be rewritten only where actor-driving semantics move to task sys; physical transport tests remain useful. | Phase 1, Phase 2, Phase 7 |

## Current Module Boundary Problems

- `daemon-service` currently owns business prompt rendering indirectly through handler modules under `tools/launcher`. IM and Track handlers render semantic prompts and decide parent-vs-side based on `parent_activity`.
- Product domains can trigger actor wake directly: IM message service calls `wake_actor`; Track tool implementation delivers a daemon signal for comment attention.
- Side processing is not task sys coordinated. Side receives a handler-rendered prompt and can escalate IM by calling `message.mark(needs_parent)`, which directly creates a parent prompt.
- Parent handoff is prompt-text based and handler-owned. Parent prompts do not have a required task id or task sys frame.
- Checkpoint is tied to taskbox and a prompt renderer, not a task sys checkpoint state transition or innerTUI frame.
- Actor-facing task tools and skill describe taskbox as the product model. That conflicts with the target where task sys is the built-in product and actor-facing tools are projections over it.
- The active-task gate uses taskbox existence as an authorization-like guard. That conflicts with task sys owning task-bound operation validation.

## Phase Ownership By Old Path

- Phase 0 owns this boundary and residue survey.
- Phase 1 must introduce a minimal `task_sys.ingest(envelope)` core, task record, state transition, and runtime instruction contract without calling daemon internals.
- Phase 2 must replace CLI/Web user input, IM wake, Track comment wake, local/cross-actor actor-driving triggers, scheduled actor-driving triggers, and turn-complete actor-driving checkpoint ingress with generic task sys ingest envelopes.
- Phase 3 must replace handler-rendered side triage prompts with task sys side task frames and side result handling limited to `close` and `need_parent(params)`.
- Phase 4 must move parent submit and interrupt decisions behind task sys runtime instructions while keeping daemon-service as the physical actuator.
- Phase 5 must replace `[TASK CHECKPOINT]` prompt submission with task sys checkpoint and a chained innerTUI/tool update loop.
- Phase 6 must relocate `task-management` skill/tool and active-task gate on top of task sys, then remove taskbox as parallel truth.
- Phase 7 must run no-residue searches and rewrite old-behavior tests to prove no raw inbound reaches actor directly and no compatibility track remains.

## Initial Residue Terms

- Raw actor input: `submit_turn`, `turn/start`, `turn/steer`, `text_input_payload`, `instance input`, `/api/instances/`, `/input`.
- Business prompts: `[IM MESSAGE CREATED]`, `[IM MESSAGE TRIAGE]`, `[TRACK COMMENT ATTENTION]`, `[TRACK COMMENT TRIAGE]`, `[MESSAGE NEEDS PARENT]`, `[TASK CHECKPOINT]`, `Required action:`.
- Direct runtime handoff: `submit_parent_prompt`, `submit_side_triage_prompt`, `interrupt_policy`, `request_parent_message_handling`.
- Taskbox truth: `taskbox`, `TaskViewModel`, `E_ACTIVE_TASK_REQUIRED`, `TASK_REQUIREMENT_ACTIVE_TASK_REQUIRED`, `task.active_anchor`, `task-management`.

## Phase 0 Acceptance Status

- Old path deletion targets are identified.
- Each old path is assigned to a target phase.
- Runtime maintenance paths are separated from actor-driving inbound.
- No dual-track compatibility plan is introduced.
