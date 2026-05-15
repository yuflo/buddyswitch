# Architecture Overview (Runless)

BuddySwitch separates execution infrastructure from durable collaboration state.

System layer:
- active instance identity
- active buddy identity
- broker routing
- lock and atomic write coordination

Product layer:
- tracks
- tasks
- artifacts
- handoffs
- active buddy private local workspace description via `buddybox_desc`

Buddybox files live under `buddyswitch/local/buddybox/<active-buddy>/` as private local working files, not product objects or cross-buddy payloads. Use artifact content when a deliverable must become product-readable.

No execution run history is required for durable product outputs.
