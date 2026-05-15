# Browser Cockpit (Runless)

## Purpose

Define market browser execution constraints inside a buddy-locked instance without introducing run-based persistence.

## Runtime Contract

- Browser executor: `chrome-devtools-cockpit`
- Mode/profile: headed `instance-browser`
- Discovery: `browser-native`
- Login policy: `mandatory-takeover`
- Fallback policy: `no-silent-degrade`
- Session continuity: `instance-cockpit`

## Search Entry

Use runtime search surface first:

- `python3 scripts/env/client.py search status`
- `python3 scripts/env/client.py search open-browser --query "<query>" --engine google`

Native Codex `web_search` is outside BuddySwitch product-mode runtime surface.

## Evidence Gate

Market evidence is target-scoped (artifact), not run-scoped.

- `python3 scripts/env/client.py evidence issue-browser --target-type artifact --target-id <id>`
- `python3 scripts/env/client.py evidence approve-downgrade --target-type artifact --target-id <id> --reason "..."`

## Source Of Truth

Canonical product outputs remain product objects. Buddybox remains private local workspace state:

- `buddyswitch/objects/tasks/*.json`
- `buddyswitch/objects/artifacts/*.json`
- `buddyswitch/objects/handoffs/*.json`
- `buddyswitch/local/buddybox/<active-buddy>/**` (private local workspace per active buddy)

Browser tabs/cookies/session traces are execution-time state only.
