# BuddySwitch Runtime Surfaces

Use this only to choose concrete BuddySwitch commands, user surfaces, and evidence for the mandatory user path.

## CLI Actor Path

```bash
./buddyswitch-codex instance start --role <role> --json
./buddyswitch-codex instance status <actor-id> --json
./buddyswitch-codex instance input <actor-id> --text "<task>" --json
./buddyswitch-codex instance status <actor-id> --json
./buddyswitch-codex instance stop <actor-id> --json
./buddyswitch-codex instance delete <actor-id> --yes --json
```

Evidence to keep:

- command JSON output;
- actor id;
- status before and after entry action;
- observed effect;
- stop/delete result.

## Side Thread Path

```bash
./buddyswitch-codex instance side <actor-id> --text "<task>" --json
./buddyswitch-codex instance side <actor-id> --side-thread-id <side-thread-id> --text "<task>" --json
./buddyswitch-codex instance side close <actor-id> --side-thread-id <side-thread-id> --json
```

Evidence to keep:

- side-thread id;
- parent actor id;
- send/close result;
- status or log showing the side target was used;
- cleanup result.

## Web UI Or HTTP API

Use the Web UI or API when the target effect is visible management behavior.

Relevant routes:

```text
GET  /api/instances
POST /api/instances
GET  /api/instances/<actor-id>/status
POST /api/instances/<actor-id>/side
POST /api/instances/<actor-id>/side/close
POST /api/instances/<actor-id>/stop
DELETE /api/instances/<actor-id>
```

Evidence to keep:

- screenshot, DOM snapshot, or HTTP response;
- matching API/status response;
- actor id or explicit target id;
- server process cleanup if started by the simulation.

## IM Or Track Wake

Use IM or Track wake only when the target effect names those entry surfaces.

Evidence to keep:

- message or comment id;
- target actor/resource id;
- resulting status, task, or log;
- wrong-recipient or stale-target negative evidence when relevant;
- cleanup proof for created actors/resources.

## Browser And Cockpit

Use browser/cockpit only when the target effect names browser behavior, page reuse, target state, or user-visible page outcome.

Evidence to keep:

- actor/resource id;
- actor-facing browser/cockpit action;
- URL, page id, target id, or screenshot;
- state/log evidence;
- cleanup or release result.

Fake CDP endpoints, direct manager calls, and unit tests can diagnose control flow, but they do not prove browser user behavior by themselves.

## Live Boundaries

Live Codex, signed-in Chrome profile, Desktop `@Chrome`, browser history, and Computer Use require explicit user authorization. If authorization or environment support is missing, report `BLOCKED` or `PARTIAL`; do not claim live user-path proof.
