# S5 C6E Web Runtime Boundary Design and Preflight

> Decision: direct Web Runtime owner followed by separate CliHost refresh
> Preflight: `S5C6EP-20260812-01`

## Selected topology

```text
application composition
  -> foundation.web_runtime.contracts
  -> foundation.web_runtime.runtime
       -> injected Host Control
       -> selected passive routes/workers/console projectors
       -> foundation.cli_runtime.contracts machine envelope
       -> owner-local packaged UI assets

current launcher.cli
  -> foundation.cli_runtime.contracts
  -> launches application.entrypoints.web
```

Final physical owners for this checkpoint:

```text
foundation/web_runtime/{contracts.py,runtime.py,assets/web-management/**}
foundation/cli_runtime/contracts.py
```

Both package roots are inert. `cli_runtime/contracts.py` is moved now because
Web already consumes the same machine envelope and Foundation must not depend
on Launcher. The CliHost implementation itself remains current and runnable
under Launcher until the next owner cutover.

## Alternatives rejected

1. **Web and all CLI/shell/Role residue in one candidate.** Rejected because
   the CLI host still spans Browser, cleanup, environment/configuration and
   Role-asset boundaries. It would recreate the oversized dirty candidate the
   ordered C6 plan is meant to avoid.
2. **Move Web but leave `launcher.cli_contract`.** Rejected because it creates
   a reverse Foundation-to-Launcher dependency.
3. **Copy or locally recreate the Web ready envelope.** Rejected because it
   duplicates one current machine-response truth.

## Projected topology proof

The preflight projected the two Web modules and the shared contract to their
final Foundation names, rewrote their live imports, and analyzed the current
BuddySwitch production graph:

```text
non-trivial projected SCCs: none
projected Web/CLI contract Foundation upward dependencies: none after the
  required direct import rewrite
projected graph SHA-256: e1508ea5088219b18df7d49fc613c5a781f8462a7cf76507bc0fb9d73d83e18e
projected unique edges: 480
```

The raw current-source projection initially reported one
`foundation.web_runtime.runtime -> buddyswitch.launcher` edge: the exact
`from buddyswitch.launcher import cli_contract` import that this design moves
to `foundation.cli_runtime.contracts`. This is the intended preservation
baseline, not an unresolved architecture choice.

## Accepted preservation evidence

| Claim | Public command/run | Result |
|---|---|---|
| generic Web routes, workers, HTTP and product adapters | focused explicit Web/unit/integration targets; `05e68f98a675479d91013f53abcaa6fe` | 106 passed, 130 subtests; cleanup clean |
| IM/component/package consumers and replacement assertions | focused discovered integration/architecture/package targets; `f74dd3efc6824a2f97a903b1a28aeea2` | 61 passed, 59 subtests; cleanup clean |
| real public Web process and signal cleanup | focused System target; `c9c8b863f4b14f22bea5d7b26f92eea3` | 1 passed; cleanup clean |
| activated runtime | runtime activation verify | `ok=true`; source `e3d9959e…`, distribution `b821c308…` |

## Assertion inventory

| Observable | Current direct proof |
|---|---|
| ready success and process cleanup | `test_web_command_sigint_keeps_stdout_single_line_and_stops_runtime` |
| loopback authority | `test_validate_bind_host_accepts_loopback_only`; `test_web_entrypoint_rejects_non_local_web_host` |
| route preparation failure before ready | `test_route_preparation_failure_is_not_published_as_ready` |
| HTTP/API success and business errors | complete `test_management_http.py` and `test_management_actions.py` |
| worker failure and cleanup ordering | `test_workers_start_fail_soft_stop_in_reverse_and_close_server_last` |
| packaged UI/static effect | `test_static_assets_are_served` plus Web JavaScript contract tier and package assertions |

No new product behavior is required. This is a behavior-preserving owner
replacement; manufacturing a structural RED is forbidden.
