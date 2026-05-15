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
- buddybox files

No execution run history is required for durable product outputs.
