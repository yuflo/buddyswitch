# S5 C5B Source and Consumer Snapshot

## Source identity

```text
HEAD:                    25ba242e402f505c91ac5bf0a18cd29fa84591a9
tree:                    1a3791264e43866aadb742ea8de65ee7e4c90295
owner content digest:    d48d8148a648643870eebcbc5eae834dec81416c890a8ce1df8f7a823a62892a
representation digest:   3160e901960193d48a92dc330cdd067dd17dd422af3869f620ac04bca7d56b4e
runtime source:           5d76ea13017b006b1b759a362270084b106cf458395deef1147e12b853a915ad
runtime distribution:     2f120c8a7a3de5fb9b7d87bce9188ccf14ac3fbfcb63c433385b0a20091f6736
```

The executable base includes the separately committed observation-race and
module-reload isolation fixes at `25ba242`; they are not part of the C5B
product candidate.

## Current owner spread

The Daemon implementation is 3,694 lines across the existing Foundation
client and eleven Launcher files:

- central service protocol, registry, reachability, signal delivery, socket
  server and process lifecycle;
- instance contracts, context, state, generic triggers, mailbox, schedules,
  dispatch, reconciliation, status and process lifecycle;
- inbound-source normalization and handler construction;
- handler-facing parent activity/input runtime;
- a generic JSONL runtime-event helper shared with App Server.

The owner is semantically coherent but physically split. The Foundation
client already owns both `buddyswitch-central-daemon/v1` and
`buddyswitch-daemon-mailbox/v1`; the service/state/host side remains under
`launcher/**`.

## Representation classes

The refresh found 76 current source/test/current-architecture files naming a
Daemon owner symbol or module: 31 source, 42 test and three current
architecture documents. They include more than direct imports:

- application build and central/instance entrypoint composition;
- Foundation composition and Browser handler/inbound/state consumers;
- Demand, Task, Track and Communication registrations/handlers;
- Launcher CLI, App Server and shell/subprocess entrypoints;
- direct unit/integration/process/system proofs and support harnesses;
- literal module/path/package assertions;
- current Daemon, Browser and Demand architecture guidance.

This list is a source snapshot, not a closed edit allowlist. The executor must
rediscover mechanically equivalent representations after movement and update
every affected live consumer.

## Current dependency findings

Three edges determine the cutover:

1. `daemon_core` and `daemon_runtime` import Launcher App Server and Actor
   Session behavior. Moving them verbatim would create
   `Foundation -> Launcher`, so App/Actor calls require one narrow injected
   host capability owned by application wiring.
2. the generic instance entrypoint imports Browser inbound registrations.
   Browser remains its own Foundation owner; application composition must
   supply those registrations instead of the generic Daemon naming Browser.
3. `runtime_event_log` is shared by Daemon and App Server. It is a generic
   process-runtime primitive; leaving it in Launcher would also create a
   reverse dependency.

No Daemon implementation imports Runtime Broker after C5A. Both services use
the same service-neutral JSON framing primitive directly.

## Protected observable paths

```text
central request -> protocol validation -> registry/reachability/signal -> same envelope/effect
mailbox request -> control or registered application command -> same result/failure
App notification/local/cross-Actor/scheduled trigger -> ordered handlers -> same telemetry/state
bounded polling -> ordered reconciliation + heartbeat -> same recovery behavior
handler runtime -> parent activity/input capability -> same App/Actor outcome
service start/status/stop -> process identity + socket/state/log cleanup -> same lifecycle
```

Exact handler order remains:

```text
inbound registrations -> Browser registrations -> contributed component order
demand_triage -> task_goal -> demand_orchestration
```

The first line describes the current handler groups; application composition
must preserve the same flattened order without making Daemon interpret their
meaning.

## Entry evidence

```text
C5B focused baseline: 433a2e2766d34929b10b6aa2e4111213
result:               217 passed, 70 subtests
source-equivalent full:7643bdc832c648729ab87c0eef6e0c39
result:               506 unit + 1196 subtests; 147 JavaScript;
                      771 integration + 458 subtests;
                      257 process + 374 subtests; 22 system; exit 0
cleanup:              test roots and attributable instances/processes absent
```
