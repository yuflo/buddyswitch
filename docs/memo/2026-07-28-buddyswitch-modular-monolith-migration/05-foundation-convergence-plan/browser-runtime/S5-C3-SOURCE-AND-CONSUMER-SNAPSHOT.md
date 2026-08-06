# S5 C3 Browser Source and Consumer Snapshot

## 1. Frozen entry identity

```text
branch:                      fea-tool
HEAD:                        34cb192f2d9ee01a2c35b9b0d439c0802da66c7a
worktree/index/untracked:    clean
Browser source manifest:     20c58b572d3d4fd8b69b0c11e59b96e17b0a8c94c91cba425c14585d370b6aca
runtime source digest:       9f138cbccf464216292a59729a940ec7b3b85045fe772216be9fabdf36f89e34
runtime distribution digest:996ac858d9ed8dd395c9eb0ce02e33704020024c388d2fdc9ebc1dfeaa1ff0da
runtime.verify:              ok=true
source-equivalent FINAL:     c1a3466da1b6455ead00dfcdca86bf46; exit 0
```

The FINAL passed 479 Unit Python tests plus 1,144 subtests, 147 JavaScript
tests, 771 Integration tests plus 458 subtests, 260 Process tests plus 374
subtests, 22 System tests, shell syntax and diff-check. Its exact executable
and test tree is the C3 entry tree; the later C2 acceptance commit changed only
historical migration records.

## 2. Current Browser owner fragments

| Current file | LOC | Current responsibility | SHA-256 prefix |
|---|---:|---|---|
| `env/browser_ttl_config.py` | 179 | strict shared Browser TTL config | `c8dcef27` |
| `env/cdp_target.py` | 267 | CDP target transport | `f8fe5d1d` |
| `env/cdp_browser_lifecycle.py` | 284 | page-idle state, lease and schedules | `cd216dea` |
| `launcher/browser_runtime_manager.py` | 981 | Actor-scoped acquire/status/release and process ownership | `94df61c3` |
| `launcher/browser_page_expired_handler.py` | 270 | page-expiry and failed-open cleanup handlers | `b2309505` |
| `launcher/browser_release_handler.py` | 151 | delayed Browser release handler | `5ac3c9e7` |
| `launcher/browser_inbound.py` | 66 | three Browser inbound registrations | `09e3410f` |
| `launcher/chrome_devtools_cockpit_proxy.py` | 1,452 | Browser MCP proxy and page/lease coordination | `095268d7` |
| `launcher/assets/chrome-devtools-mcp-1.1.1-tools.json` | 38 | proxy tool contract asset | `b7f375d5` |

These files form one semantic Browser owner but are physically split across
historical `env` and `launcher` roots. No current product module owns Browser;
D-012 classifies it as an Actor Foundation capability.

## 3. Current owned operations and state

Browser owns:

- strict TTL configuration and its canonical shared path;
- CDP page target list/get/create/close transport;
- Actor-scoped Chrome port, profile, PID/start identity, readiness and usable
  page acquisition;
- ownership-safe stop/release and release-schedule cancellation;
- page-idle target state, active target, expiration, delayed release and
  failed-open cleanup schedules;
- three exact Daemon inbound handlers;
- the Chrome DevTools MCP proxy, focus guard, page metadata, search-page
  opening and upstream process cleanup.

Canonical state paths, JSON shapes, event types, schedule keys, Broker methods,
CLI output and MCP behavior are protected. C3 relocates ownership; it does not
migrate state or redesign Browser behavior.

## 4. Direct production consumers

| Consumer | Current dependency | C3 disposition |
|---|---|---|
| `application/entrypoints/browser_runtime.py` | TTL, target and manager modules | retain thin verified entrypoint; import the new Browser owner |
| `application/entrypoints/browser_cockpit_proxy.py` | proxy `main` | retain thin verified entrypoint; import the new Browser owner |
| `runtime_kernel/dispatcher.py` | Browser acquire/status/release manager | keep Broker protocol/error translation; call the new owner operations |
| `launcher/instance_daemon.py` | Browser inbound registrations | keep Daemon sequencing/validation; consume the new owner registrations |
| `launcher/shell/env.sh` | stable application TTL entrypoint | unchanged unless repository facts require a mechanical path correction |
| `launcher/shell/browser_cockpit.sh` | stable application runtime/proxy entrypoints | unchanged unless repository facts require a mechanical path correction |

The Browser owner still consumes current shared primitives whose physical
relocation belongs later:

- `foundation.daemon.client` for schedules;
- `launcher.daemon_state` for owner-scoped cancellation;
- `launcher.daemon_contracts` and `notification_center` for current host
  contracts;
- `runtime_kernel.process_identity` for process attribution;
- `runtime_kernel.client` for Broker transport.

These are live current contracts, not compatibility paths. C4/C5 may relocate
their owners later without reopening C3 Browser semantics.

## 5. Representation-complete mutable consumer classes

The write boundary includes every current representation of the retired
Browser paths, not only imports:

### Direct imports and application bridges

- the two application entrypoints;
- Runtime Broker dispatcher;
- instance Daemon host;
- root test cleanup support.

### Literal and generated paths

- integration Browser lifecycle/proxy harnesses;
- System Browser lifecycle script-module paths;
- architecture and Daemon contract path tuples;
- package-data declarations and distribution resource assertions.

### Owner and affected tests

- `tests/unit/browser/**`;
- `tests/integration/browser/**` excluding Evidence-only behavior unless a
  Browser path reference requires mechanical update;
- `tests/process/browser/**`;
- `tests/system/browser_lifecycle/**`;
- Broker, Daemon, launcher, package, stale-PID, startup-failure and cleanup
  support tests that import, patch, execute or enumerate a Browser owner path.

### Current architecture guidance

- Daemon guidance must name Browser as an externally registered Foundation
  owner, not a Launcher built-in implementation;
- new current Browser architecture guidance must own the final boundary;
- Web/Search/Evidence guidance remains behaviorally unchanged.

Tests do not earn compatibility modules. Every test that names a retired path
must move to the current owner or become an absence assertion.

## 6. Cross-module private-call defect

`cdp_browser_lifecycle._read_page_idle_state` has six production call sites
outside its defining module: manager, page handlers, release handler and MCP
proxy. Tests also call or patch the private function.

C3 must expose the required read as an ordinary Browser-owned internal
operation and remove all cross-module leading-underscore calls. It must not
retain `_read_page_idle_state` as an alias, re-export it from the package root,
or add a broad service/facade object.

## 7. Current test and package boundary

Browser Foundation tests remain root-owned because they span process, Daemon,
Broker, shell and System resources. D-019 co-located test roots apply to
product modules and Roles; C3 does not alter the public runner to manufacture
a Foundation test tier.

The proxy JSON asset moves with the Browser owner. `pyproject.toml` must
declare only that exact new package-data owner, and the distribution proof must
show the new asset is installed while the retired Launcher asset is absent.

## 8. Contrary signal

The preparation probe `./buddyswitch-codex instance list --json` was rejected
because the current command accepts no `--json` option. It changed no state and
is not evidence. The canonical `./buddyswitch-codex instance list` then
reported zero instances. No test root or attributable BuddySwitch/Browser
process remained.
