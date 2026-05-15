# Turn Runtime Spec (Runless)

BuddySwitch runtime is runless.

- Broker methods: `env.tool`, `ping`, `status`.
- Durable outputs are written explicitly through env tools.
- Durable state paths:
  - `buddyswitch/objects/tracks/*.json`
  - `buddyswitch/objects/tasks/*.json`
  - `buddyswitch/objects/artifacts/*.json`
  - `buddyswitch/objects/handoffs/*.json`
  - `buddyswitch/content/buddybox/<buddy>/**`

`prepare`/`persist` run lifecycle is retired. If a turn matters later, write artifact/handoff/buddybox objects directly.
