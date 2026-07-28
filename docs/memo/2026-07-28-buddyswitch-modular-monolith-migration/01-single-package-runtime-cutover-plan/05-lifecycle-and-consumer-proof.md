# S1.5 Lifecycle and Consumer Proof

## Outcome

> Packaging and projection are behavior-preserving across every current
> consumer and terminal lifecycle state.

## Lifecycle matrix

Directly prove:

| Operation | Required effect |
|---|---|
| roles | current exact Role set |
| start | atomic projection, Broker/MCP/Browser/App/thread/bootstrap/Daemon active |
| list/status | component health and runtime identity agree |
| input | turn reaches exact active thread |
| interrupt | exact thread interrupted |
| compact | exact thread compacted |
| clear | new thread bootstrapped; Daemon restarted; failure cleanup exact |
| resume | recorded runtime/thread validation and exact resume |
| stop | Daemon/App/Broker/Browser stopped; inactive record |
| delete | safe inactive exact root removal; ambiguous Browser blocks |
| Web retry | old deletion and replacement start remain attributable |
| capability get/set | exact instance mutation/projection |

## Consumer groups

Run claim-scoped proof for:

- public CLI and HostControl;
- Runtime Broker/Tool/MCP black-box flow;
- Daemon core/instance/central service and recovery;
- App Server process/RPC identity;
- Browser/CDP/proxy lifecycle and evidence;
- Web management routes/lifecycle/product projections;
- IM external session/iMessage worker;
- Role bootstrap/profile/authority/Skills;
- cleanup/dry-run/destructive safety;
- Demand/Task/Goal/Track/Artifact/Message current behavior;
- test runner and fakes in clean installed runtime.

## Failure agreement

For start/clear/resume failures verify:

- persisted instance status;
- protocol result;
- consumer-visible status;
- runtime error/log attribution;
- process/socket/PID/lock/temp cleanup.

Any contradiction rejects the checkpoint.

## Test command policy

Use only:

```bash
./buddyswitch-test focused <exact targets>
```

until the final frozen S1 candidate, when `./buddyswitch-test full` is
appropriate.

The exact target list is refreshed against source before S1 becomes READY.
