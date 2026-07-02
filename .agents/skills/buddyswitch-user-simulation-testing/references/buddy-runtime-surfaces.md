# BuddySwitch Runtime Surfaces

Use this reference to map user scenarios to code surfaces and evidence.

## Table Of Contents

- [CLI](#cli)
- [Side Thread Lifecycle](#side-thread-lifecycle)
- [Task Sys](#task-sys)
- [Web Management](#web-management)
- [IM Wake](#im-wake)
- [Track Comment Wake](#track-comment-wake)
- [Browser Cockpit / Search](#browser-cockpit--search)
- [Fake Codex](#fake-codex)
- [Live Codex](#live-codex)

## CLI

Main launcher: `./buddyswitch-codex`

Important commands:

```bash
./buddyswitch-codex instance start --role <role> --json
./buddyswitch-codex instance status <actor-id> --json
./buddyswitch-codex instance input <actor-id> --text <text> --json
./buddyswitch-codex instance side <actor-id> --text <text> --json
./buddyswitch-codex instance side <actor-id> --side-thread-id <side-thread-id> --text <text> --json
./buddyswitch-codex instance side close <actor-id> --side-thread-id <side-thread-id> --json
./buddyswitch-codex instance stop <actor-id> --json
./buddyswitch-codex instance delete <actor-id> --yes --json
```

Key files:

- `buddyswitch-codex`
- `tools/launcher/instance.sh`
- `tools/launcher/app_server.py`
- `tools/launcher/daemon_core.py`
- `tools/launcher/runtime_broker.sh`

## Side Thread Lifecycle

Owner:

- `tools/launcher/side_thread_lifecycle.py`

Registry:

- `tools/launcher/side_thread_registry.py`

Core invariants:

- start registers a lease with `parent_thread_id`, `thread_id`, `purpose`, and `turn_id`;
- active send steers using stored `turn_id`;
- cleanup interrupts stored `turn_id` when present and unregisters the lease;
- ephemeral side threads must not require `thread/turns/list`;
- stale and cross-actor side ids reject before steer.

## Task Sys

Key files:

- `tools/launcher/task_sys_ingress.py`
- `tools/launcher/task_sys_runtime.py`
- `scripts/env/tools/task_sys/_impl.py`
- `scripts/env/domain/task_sys.py`

User-like coverage:

- CLI input enters Task Sys.
- `task_sys.close` retires side lease for side-processing tasks.
- `task_sys.need_parent` cleans side lease and submits parent frame.

## Web Management

Key files:

- `tools/launcher/web_management.py`
- `tools/launcher/assets/web-management/app.js`
- `tests/test_web_management.py`
- `tests/web_management_ui_contract.test.js`

Important routes:

```text
GET  /api/instances
POST /api/instances
GET  /api/instances/<actor-id>/status
POST /api/instances/<actor-id>/side
POST /api/instances/<actor-id>/side/close
POST /api/instances/<actor-id>/stop
DELETE /api/instances/<actor-id>
```

## IM Wake

Key files:

- `scripts/env/services/messages.py`
- `scripts/env/tool_runtime/daemon_client.py`
- `tools/launcher/im_wake_handler.py`
- `tests/test_im_wake_handler.py`
- `tests/test_im_external_reply_loop.py`

Core path:

```text
message created -> im.message.created wake -> daemon mailbox -> im_wake_handler -> task_sys_ingress -> runtime.execute_task_sys_instruction
```

## Track Comment Wake

Key files:

- `tools/launcher/track_comment_inbound.py`
- `tools/launcher/track_comment_added_handler.py`
- `scripts/env/repos/track_comments.py`
- `scripts/env/domain/track_comments.py`
- `tests/test_track_comment_added_handler.py`
- `tests/test_track_comment_env_tool.py`

Core path:

```text
track comment added -> track.comment.added trigger -> daemon mailbox/central signal -> track_comment_added_handler -> task_sys_ingress -> runtime.execute_task_sys_instruction
```

## Browser Cockpit / Search

Key files:

- `tools/launcher/browser_cockpit.sh`
- `tools/launcher/browser_runtime_manager.py`
- `tools/launcher/chrome_devtools_cockpit_proxy.py`
- `tools/launcher/browser_release_handler.py`
- `scripts/env/tools/search/_impl.py`
- `scripts/runtime_kernel/dispatcher.py`
- `tests/test_browser_cockpit_launcher.py`
- `tests/test_browser_cockpit_proxy.py`
- `tests/test_browser_lazy_release_integration.py`
- `tests/test_search_env_tool.py`

Core paths:

```text
search.open_browser -> runtime broker browser.open_url -> browser runtime manager -> browser session/CDP
chrome-devtools-cockpit tool call -> control-plane browser acquire -> upstream MCP/CDP proxy
browser idle/release -> browser runtime manager release -> process/socket/page marker cleanup
```

User-like coverage:

- actor asks to open a URL and receives structured page state;
- cockpit tool call opens/reuses a browser target;
- page limit blocks new targets without side effects;
- release/idle cleanup removes resources and next call reacquires cleanly;
- actor runtime never sees source root or launcher CLI paths.

## Fake Codex

Harness:

- `tests/helpers/fake_codex.py`

Useful env vars:

```bash
BUDDYSWITCH_TEST_APP_SERVER_STATE_FILE=<path>
BUDDYSWITCH_TEST_CALLS=<path>
BUDDYSWITCH_TEST_CAPTURE=<path>
BUDDYSWITCH_TEST_PROCESS_REGISTRY=<path>
```

Fake Codex can verify host orchestration and RPC choices, but it cannot prove live Codex service compatibility.

## Live Codex

Live boundary:

- `codex app-server --listen unix://...` launched via `tools/launcher/app_server.py`.

Rules:

- Do not put fake `codex` first in `PATH`.
- Use isolated BuddySwitch state roots.
- Default to role `test` for smoke unless source write is required.
- Report auth/quota/service failure as `BLOCKED`, not `PASS`.
