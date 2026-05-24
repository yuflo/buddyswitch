# Buddy Web Management MVP Objective

Date: 2026-05-24

## Source

This objective concretizes `docs/memo/2026-05-24-buddy-web-management-mvp.md`
after reading the current launcher, app-server helper, manifest, and service
mode tests.

## Goal

Build a local browser page that lets a product manager manage multiple
BuddySwitch buddy instances without typing terminal commands for each action.

The first complete product path must support:

- create a new buddy instance
- view multiple stored instances
- view selected instance health and thread metadata
- send an instruction to an active healthy instance
- interrupt an active turn
- stop an instance
- delete an inactive instance

## Current Code Facts

Current public instance commands are:

```bash
./buddyswitch-codex instance buddies
./buddyswitch-codex instance start --buddy <buddy>
./buddyswitch-codex instance input <instance-id> --text <text>
./buddyswitch-codex instance attach <instance-id>
./buddyswitch-codex instance stop <instance-id>
./buddyswitch-codex instance status <instance-id> --json
./buddyswitch-codex instance interrupt <instance-id>
./buddyswitch-codex instance list [--buddy <buddy>]
./buddyswitch-codex instance delete <instance-id> --yes
```

Current buddy ids from `buddyswitch/manifest.toml` are:

```text
market
pm
design
dev
test
```

Current command output facts that the web layer must handle:

- `instance buddies` returns tab-separated rows:
  `id`, `label`, `scope`.
- `instance list` returns a tab-separated header and rows when instances exist.
- `instance list` returns two human-readable lines when no instances exist.
- `instance status <id> --json` returns the canonical JSON status shape.
- `instance start --buddy <buddy>` prints `BuddySwitch instance: <id> (<buddy>)`
  plus follow-up command hints.
- `instance input <id> --text <text>` prints either `Started turn: <turn-id>` or
  `Steered turn: <turn-id>` on success.
- `instance interrupt <id>` prints `Interrupted turn: <turn-id>` on success.
- `instance stop <id>` prints `Instance stopped: <id>` on success.
- `instance delete <id> --yes` prints `Instance deleted: <id>` on success.
- Current service-mode tests are green at the app-server client layer:
  `python3 -m pytest tests/test_app_server_client.py -q` -> `9 passed`.

Current implementation facts:

- There is no `web` top-level command in `buddyswitch-codex` yet.
- There is no existing FastAPI, Flask, aiohttp, or frontend framework in the
  repository.
- Existing HTTP test usage is based on Python standard library HTTP servers.
- Instance lifecycle truth lives in `buddyswitch-codex` and
  `tools/launcher/instance.sh`.
- Codex app-server wire behavior lives in `tools/launcher/app_server.py` and
  `tools/launcher/app_server.sh`.
- Runtime lock protection already exists for start, stop, delete, reset, and
  cleanup paths.
- Existing tests use fake Codex boundaries to verify launcher behavior without
  starting real model sessions.

## Current Bottleneck

The bottleneck is not service-mode readiness anymore. The service-mode CLI path
exists and is test-bound. The current bottleneck is the missing local web
control surface that product can use to operate multiple instances from one
page.

The first web implementation must therefore close the shortest verified loop:

```text
Browser page -> local Web API -> existing instance CLI -> existing app-server path
```

## Required Approach

Add a thin local Web API and a static one-page UI.

The Web API must call the existing `./buddyswitch-codex instance <command>` commands
as subprocesses. It must not reimplement instance lifecycle, app-server health,
runtime broker behavior, browser cockpit control, or delete safety.

The browser must call the local Web API. It must not call shell scripts,
Unix sockets, app-server JSON-RPC, or runtime files directly.

## Non-Transition Decision

This task must not build a transitional dual path.

Specifically, do not build:

- a separate lifecycle implementation for web
- a second app-server health model
- direct JSON writes to `instance.json`
- direct mutation under `buddyswitch/objects/**`
- direct mutation under `buddyswitch/local/buddybox/**`
- an embedded terminal in the browser
- a compatibility path for the old TUI launcher model
- a remote network management server
- a plugin, workflow, event bus, queue, or permission framework

The web layer is an adapter at the HTTP boundary only. The existing launcher
remains the owner of lifecycle state and safety checks.

## First Complete Product Shape

The first complete page is a single management screen:

- top bar with server status and refresh
- buddy selector and create button
- instance table for all stored instances
- selected instance detail panel
- instruction textarea and send button
- interrupt, stop, and delete controls
- visible per-action result or error message

This is not a landing page, analytics dashboard, transcript viewer, log viewer,
or daemon console.

## API Contract

The first Web API contract is:

```text
GET    /api/health
GET    /api/buddies
GET    /api/instances
GET    /api/instances/<instance_id>/status
POST   /api/instances
POST   /api/instances/<instance_id>/input
POST   /api/instances/<instance_id>/interrupt
POST   /api/instances/<instance_id>/stop
DELETE /api/instances/<instance_id>
```

`POST /api/instances` is the create route. Do not also add
`POST /api/instances/start` in the MVP.

The default bind address is `127.0.0.1`. Non-local hosts are rejected in the
MVP.

## Definition Of Done

This task is complete only when:

1. The Web API and UI are implemented in the current worktree only.
2. A product manager can open the local page and complete the full create,
   list, send, interrupt, stop, delete-inactive flow.
3. API behavior is covered by functional tests derived from requirements.
4. UI behavior is covered by static route tests plus a manual browser smoke.
5. Existing service-mode focused tests still pass.
6. `python3 -m pytest -q` passes.
7. Final review confirms the diff is small, clear, and does not create a
   second lifecycle path.
