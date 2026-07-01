# WebUI Simulated User Browser Observations

## Environment

- Date: 2026-07-01
- Worktree: `/Users/chen/Dev/buddyswitch/.worktrees/fea-webui`
- WebUI URL: `http://127.0.0.1:8767/`
- Browser tooling: Chrome DevTools MCP page snapshot, click, form fill, network, console, viewport resize, screenshots
- Server command:

  ```bash
  ./buddyswitch-codex web --host 127.0.0.1 --port 8767 2>&1 | tee docs/spec/webui-simulated-user-test/webui-server-log.txt
  ```

## Screenshots

- Desktop Team Room: `docs/spec/webui-simulated-user-test/team-room-desktop.png`
- Mobile Team Room: `docs/spec/webui-simulated-user-test/team-room-mobile.png`
- Mobile Tracks: `docs/spec/webui-simulated-user-test/tracks-mobile.png`

## First Arrival

Browser snapshot showed:

- Page title: `BuddySwitch Web Management`
- Primary tabs: `Team room`, `Tracks`
- First visible screen: Team Room
- People list: `No actors available.`
- Start teammate roles: `market`, `pm`, `design`, `dev`, `test`
- Direct thread, composer, selected teammate card, Runtime, Task, Track summary, and Actions were visible.
- Old/fake visible terms checked and absent: `Actor Console`, `Create Actor`, `Workspace`, `Runtime health`, `Workstream OS`, `72%`, `68%`.

Initial network:

- `GET /api/health` -> 200
- `GET /api/roles` -> 200
- `GET /api/actors` -> 200
- `GET /api/tracks` -> 200
- `GET /api/im/session` -> 200

Initial console:

- No console messages before actor creation attempts.

Layout:

- Desktop Team Room grid: `260px 815px 320px`
- No horizontal overflow on desktop.

## Actor Creation Attempts

All three attempts were made through the browser role selector and Start button.

### Dev

Browser operation:

1. Selected `Dev (dev)` in the Role combobox.
2. Clicked `Start`.
3. Waited for the request to return.

Network:

```http
POST /api/instances
Request body: {"role":"dev"}
Status: 502
Response: {"ok": false, "error": {"code": "COMMAND_FAILED", "message": "Preparing worktree (detached HEAD 8c138a6)"}}
```

UI result:

- People list stayed `No actors available.`
- Start button recovered from disabled pending state.
- Message banner showed `Preparing worktree (detached HEAD 8c138a6)`.

### PM

Browser operation:

1. Selected `PM (pm)` in the Role combobox.
2. Clicked `Start`.
3. Waited for the request to return.

Network:

```http
POST /api/instances
Request body: {"role":"pm"}
Status: 502
Response: {"ok": false, "error": {"code": "COMMAND_FAILED", "message": "Preparing worktree (detached HEAD 8c138a6)"}}
```

UI result:

- People list stayed `No actors available.`
- Message banner showed the same backend error.

### Test

Browser operation:

1. Selected `Test (test)` in the Role combobox.
2. Clicked `Start`.
3. Waited for the request to return.

Network:

```http
POST /api/instances
Request body: {"role":"test"}
Status: 502
Response: {"ok": false, "error": {"code": "COMMAND_FAILED", "message": "Preparing worktree (detached HEAD 8c138a6)"}}
```

UI result:

- People list stayed `No actors available.`
- Selected teammate stayed `No teammate selected`.
- Send, Interrupt, Open TUI, Clear, Stop, Resume, and Delete stayed disabled.

Console after all attempts:

```text
Failed to load resource: the server responded with a status of 502 (Bad Gateway) [3 times]
```

## Direct Thread And Lifecycle Coverage

Blocked by actor creation failure.

The browser could not select a real actor, so these user flows could not be executed honestly:

- Send a direct Team Room message to a newly created actor.
- Rapidly switch between dev, pm, and test actors.
- Open TUI, Clear, Stop, Resume, or Delete a created actor.

Observed disabled-state behavior without actor:

- Send disabled.
- Interrupt disabled.
- Open TUI disabled.
- Clear disabled with visible reason: `Clear disabled: Select an actor.`
- Stop disabled.
- Resume disabled.
- Delete disabled.

## Tracks Tab / Studio

Browser operation:

1. Clicked `Tracks`.
2. Inspected Track Studio empty state.
3. Switched back to Team Room and again verified layout state.

Observed:

- Tracks tab became active.
- Team Room was hidden and Track view visible.
- Track list: `No active Tracks.`
- Detail: `Select a Track to inspect details.`
- Right rail: `Select a Track to inspect comments and context.`
- No Track write controls were present in `#track-view`.
- Old/write terms absent in Tracks view: `Actor Console`, `Create Actor`, `Workspace`, `Track workspace`, `Submit`, `Resolve`, `textarea`.
- Desktop Track Studio grid: `250px 920px 320px`.
- No horizontal overflow on desktop.

## Mobile / Narrow View

Tooling requested `390x844`; Chrome reported effective content width `500px`.

Tracks:

- Track Studio switched to single-column grid: `478px`.
- No horizontal overflow.
- No overflowing elements found by bounding-box scan.

Team Room:

- Team Room switched to single-column grid: `463px`.
- Sidebar, main Direct thread, and teammate panel all remained present.
- No horizontal overflow.
- No overflowing elements found by bounding-box scan.

## Server Log Review

`webui-server-log.txt` contained only:

```text
BuddySwitch web management listening on http://127.0.0.1:8767
```

No request lines, tracebacks, or command stderr were emitted to the captured server log. The creation failure evidence came from browser network responses and console messages, not from the server log file.

## Cleanup

No actors were created, so no actor cleanup was possible or required through the UI.

The WebUI server was explicitly interrupted after writing the result files. A subsequent `lsof -nP -iTCP:8767 -sTCP:LISTEN || true` check returned no listener.
