# S4 Communication Owner and Consumer Manifest

> Packet: `BS-MM-S4-COMMUNICATION-R1-20260803-01`
> Rule: exact owner classes are authorized; a new semantic/shared-host write
> outside them stops execution and returns to the hub.

## 1. Final owner

All Communication-private change belongs under:

```text
src/buddyswitch/modules/communication/**
```

The root contains one passive `module.py`, a four-operation Public surface,
private Message state/domain and Tool/Daemon/Web/channel/cleanup adapters, and
only genuine single-module tests. Exact Private file splitting is owned by the
executor; no second Communication package or shared IM utility layer exists.

## 2. Absorbed and deleted paths

The module absorbs and deletes in the same candidate:

```text
src/buddyswitch/env/repos/messages.py
src/buddyswitch/env/services/messages.py
src/buddyswitch/env/tools/message/**
src/buddyswitch/env/tool_runtime/im_client.py
src/buddyswitch/env/tool_runtime/im_actor_delivery.py
src/buddyswitch/launcher/external_im_session.py
src/buddyswitch/launcher/im_http_router.py
src/buddyswitch/launcher/im_wake_handler.py
src/buddyswitch/launcher/imessage_channel.py
src/buddyswitch/launcher/message_inbound.py
src/buddyswitch/launcher/web_im_identity.py
```

No forwarding import, compatibility facade, duplicate registration, fallback
read, old Tool discovery package or old adapter filename remains.

## 3. Public and input-port edges

Communication Public exposes only the real external operations:

```text
get_im_message
list_im_replies
send_im_message
list_im_events_for_identity
```

Demand triage imports the first three. Context imports the fourth. They return
the current consumer-visible results without repositories or mutable internal
objects.

Communication declares one consumer-owned callable contract for Demand
ingress. `build_communication_module(...)` receives the callable; application
composition passes `demand_public.enqueue_inbound`. Communication Private does
not import Demand Public or Private. This is exact wiring, not dependency
negotiation.

Required graph:

```text
Demand Private -> Communication Public -> Communication Private
Context adapter -> Communication Public
Application composition -> Demand Public callable -> Communication input port
```

Forbidden graph:

```text
Communication Private -> Demand package
Demand Private -> Communication Private
component -> service locator/dynamic registry -> component
```

## 4. Shared host-contract writes

Authorized exact shared production paths:

```text
src/buddyswitch/foundation/composition/__init__.py
src/buddyswitch/application/build.py
src/buddyswitch/application/composition.py
src/buddyswitch/launcher/web_contracts.py
src/buddyswitch/launcher/web_management.py
src/buddyswitch/launcher/instance_daemon.py
src/buddyswitch/application/entrypoints/web.py
src/buddyswitch/application/entrypoints/instance_daemon.py
src/buddyswitch/runtime_support/env_cleanup.py
src/buddyswitch/env/tool_runtime/context.py
src/buddyswitch/env/tools/context/_impl.py
src/buddyswitch/modules/demand/private/adapters/daemon/demand_triage_runtime.py
```

Allowed meanings only:

- add and flatten typed `web_routes` and `web_workers` assembly fields;
- validate duplicate/invalid route and worker registrations;
- configure generic WebHost with passive registrations;
- remove concrete Communication imports/branches from WebHost and Daemon;
- replace Message-shaped ToolContext members with module-owned adapters;
- replace Message-specific cleanup parsing with the approved generic indexed,
  multi-owner cleanup contract;
- redirect Demand and Context through Communication Public.

No other host feature, route framework, daemon ordering change, generic
lifecycle manager, plugin discovery, DI container, event bus or state schema
change is authorized.

## 5. Cleanup-contract participants

The cleanup contract cutover necessarily updates current accepted
contributors so one generic shape remains live:

```text
src/buddyswitch/modules/demand/private/adapters/cleanup.py
src/buddyswitch/modules/task/private/adapters/cleanup.py
src/buddyswitch/modules/track/private/adapters/cleanup.py
src/buddyswitch/modules/artifact/private/adapters/cleanup.py
```

These are mechanical contract projections only. Their ownership, paths,
records, warnings and role/all-data behavior do not change.

## 6. Test disposition

Move beneath Communication only tests whose fixtures and assertions stay
inside Communication plus foundation primitives:

```text
tests/unit/im/test_actor_delivery.py
tests/unit/im/test_delivery.py
tests/unit/im/test_imessage_command_client.py
tests/unit/im/test_imessage_inbound_parser.py
tests/integration/im/_imessage_fakes.py
tests/integration/im/test_external_session.py
tests/integration/im/test_http_router.py
tests/integration/im/test_imessage_outbound.py
tests/integration/im/test_imessage_routing.py
tests/integration/im/test_imessage_state.py
tests/integration/im/test_imessage_worker.py
tests/integration/im/test_product_core.py
```

Keep root-owned because they prove host or cross-module behavior:

```text
tests/unit/im/test_notification_center.py
tests/unit/im/test_wake_handler.py
tests/integration/im/test_communication_identity_cutover.py
tests/integration/im/test_external_event_capacity.py
tests/integration/im/test_external_projection.py
tests/integration/im/test_external_query.py
tests/integration/im/test_external_reply_loop.py
tests/integration/im/test_identity_global_convergence.py
tests/integration/im/test_identity_product_ownership.py
```

Relevant root Web, Daemon, Context, cleanup, Tool, process, package and
architecture tests remain root-owned. The architecture proof must scan module
test roots; it may not exclude them.

## 7. Package and current-doc writes

Package metadata may change only if required to include Communication runtime
files or exclude module tests from the wheel. Current architecture documents
are exactly:

```text
docs/arch/web-interface-call-architecture.md
docs/arch/communication-capability-architecture.md  (create)
```

They name the final owner and generic host edges only. Migration master truth
and acceptance records remain hub-owned.
