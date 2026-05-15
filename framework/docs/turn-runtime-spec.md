# Turn Runtime Spec (Runless)

BuddySwitch runtime is runless.

- Broker methods: `env.tool`, `ping`, `status`.
- Durable outputs are written explicitly through env tools.
- Durable state paths:
  - `buddyswitch/objects/tracks/*.json`
  - `buddyswitch/objects/tasks/*.json`
  - `buddyswitch/objects/artifacts/*.json`
  - `buddyswitch/objects/handoffs/*.json`
  - `buddyswitch/local/buddybox/<active-buddy>/**` (private local workspace per active buddy)

`prepare`/`persist` run lifecycle is retired. If a turn matters later, write product-readable content through artifact/handoff objects; keep private working files in the active buddy local buddybox.
