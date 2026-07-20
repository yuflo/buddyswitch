# iMessage Existing IM Capacity Probe Design

Date: 2026-07-20
Status: approved implementation baseline

## Goal

Prove before the iMessage scheduler rewrite whether the current single-session
`/api/im/events` contract can support the agreed local-channel capacity without
changing Central IM, External IM Session, the HTTP router, or iMessage runtime
behavior.

The acceptance claim is: with 100 bound external sessions and 20 active
sessions, the current authenticated HTTP event path can be scanned quickly
enough to reserve at least one second of the two-second bridge SLO for iMessage
delivery.

## Scope

The probe exercises the real local path:

```text
BuddySwitchImApi
  -> ThreadingHTTPServer
  -> ImHttpRouter
  -> ExternalImSession
  -> message service and file repository
```

It runs in `RuntimeWorkspaceTestCase`, so identities, sessions, messages,
events, cursors, and acknowledgements use isolated temporary runtime state.
It does not contact Messages.app, send iMessages, mutate production code, or
introduce a batch/cross-session IM contract.

## Scenarios and Gates

1. Create 100 external sessions through the real HTTP endpoint.
2. Warm the event path, then measure five empty full scans using
   `read_events(wait_ms=0, limit=1)`.
3. Send one actor event to each of 20 active sessions and measure event creation
   to authenticated HTTP discovery plus `get_message` and ordered ACK.
4. Inject a 50-event burst across those 20 sessions, drain it through repeated
   fair full scans, and prove exact event identity and no loss.
5. Stop the HTTP server and join its thread.

Acceptance thresholds:

- empty 100-session full-scan P95: at most 1.0 second;
- 20-active event discovery P95: at most 1.0 second;
- 20-active event discovery P99: at most 1.5 seconds;
- non-empty read/get/ACK flow P99: at most 0.5 second;
- 50-event burst drain: at most 5.0 seconds;
- every fetched event belongs to its authenticated external session;
- every event is fetched, ACKed in session order, and absent after ACK;
- no server-thread or temporary-runtime residue.

## Decision Rule

If the probe passes repeatedly, freeze the current `/api/im` contract and
implement non-blocking scanning plus bounded per-contact delivery entirely in
`tools/launcher/imessage_channel.py`.

If a latency gate fails, treat that result as evidence that the existing IM
read path is not sufficient at the agreed capacity. Stop before changing the
iMessage scheduler and inspect the measured bottleneck; do not weaken the gate
or add a speculative aggregate API.

## Files

- Create `tests/integration/im/test_external_event_capacity.py` as the sole
  executable capacity proof.
- Do not modify runtime source files.
- Execute only through `./buddyswitch-test focused`.
