# iMessage Channel Product Logic Rebuild Context Audit

Date: 2026-06-28

## Source Read

- `AGENTS.md`
- `docs/bitter/*`
- `docs/memo/2026-06-28-imessage-channel-product-logic-rebuild.md`
- Current launcher, Web, iMessage bridge, External IM, and test files.

## Current Bottleneck

The previous iMessage work completed a fixed-target bridge MVP. The current source memo replaces that target with a Web-started iMessage channel that owns sender-scoped product interaction. The old MVP is now residue, not a compatibility baseline.

## Current Code Facts

- Root launcher help still advertises a retired standalone iMessage command.
- Root launcher still dispatches a top-level iMessage command to a Python helper.
- The retired bridge module owns global connection, fixed actor target, sender allow-list, inbound dedupe, outbound dedupe, and message routes in one state object.
- The retired state path is not the source memo's channel state path.
- The retired bridge tests assert fixed-target and allow-list behavior that the source memo forbids as live behavior.
- Web management currently exposes `/api/im/*` through `ImHttpRouter`, but it does not start or stop an iMessage worker.
- `ExternalImSession` is already the shared `/api/im/*` application boundary and continues to be the correct boundary for channel delivery.
- Channel-specific controls are not currently implemented.

## Boundary Facts

- iMessage channel behavior belongs in a launcher-local iMessage module.
- Web may own lifecycle only.
- `/api/im/*` remains the Integration External IM HTTP API and should not gain iMessage control routes.
- `ExternalImSession` and Central IM should not learn Apple ID, chat route, active actor, pending choice, or iMessage outbound text formatting semantics.

## Residue Evidence

Current scans find retired surface in:

- root launcher helper constants, help, and dispatch;
- retired bridge source;
- retired bridge tests;
- old `docs/spec` bridge plan and smoke guidance before this Phase 0 reset.

The new plan and test plan encode the replacement work in four implementation phases after this documentation gate.

## Phase 0 Decision

Phase 0 is documentation-only. The next allowed phase is Phase 1, which must start with failing channel tests before production code changes.
