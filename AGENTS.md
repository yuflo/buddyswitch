# BuddySwitch Sharp Forward Guide

BuddySwitch uses sharp-forward, testing-bound development.

Core rule: rebuild forward through the shortest tested path. Do not preserve old structure, compatibility, or hypothetical production stability unless the user explicitly asks for release, hotfix, security, payment, external API, or irreversible data work.

## Priorities

1. Product capability
2. Iteration speed
3. Test-bound quality
4. Code clarity
5. Cost

## Sharp Forward

- Move the current bottleneck to verified product improvement.
- Prefer rebuild-forward over compatibility-forward.
- Prefer direct replacement over wrappers, adapters, and dual paths.
- Prefer deleting stale logic over preserving it just in case.
- Prefer simple concrete code, existing project patterns, and one clear path.
- Break internal contracts when it makes the main path clearer; protect only documented external contracts.
- Do not add generic engines, plugin systems, rule systems, or abstraction frameworks without repeated real need.
- Do not optimize for rollback comfort, historical compatibility, conservative migration, or online stability unless the task explicitly enters a production-sensitive scope.

Compatibility is a cost, not a virtue. Keep it only for real users, real data migration, explicit external contracts, or clear rollback requirements.

## Testing Bound

Forward speed is allowed because tests hold the boundary.

- New behavior starts with a failing test whenever practical.
- Bug fixes start with a regression test that fails first.
- Refactors run behavior tests first and keep them green while structure changes.
- Core product paths need high meaningful coverage.
- Coverage means behavior and risk coverage, not shallow line-count chasing.
- Tests must be fast, deterministic, developer-owned, and cheap to run repeatedly.
- Flaky, vague, or over-mocked tests are not quality gates; fix or replace them.
- Escaped defects get the smallest regression test that would have caught them.

Manual checks can supplement automated tests, but should not replace automated proof for repeatable behavior.

## Execution Loop

1. Identify the current bottleneck.
2. Write or select the test that defines expected behavior.
3. Watch the new test fail when changing behavior.
4. Implement the smallest direct change.
5. Run the focused test until green.
6. Refactor or delete baggage while tests stay green.
7. Run broader relevant verification.
8. Report result, verification, and remaining risk.

Do not expand the task after the bottleneck is clear. Do not keep old and new behavior side by side unless explicitly required.

## Verification

No test or verification, no done.

The only public test entry is `./buddyswitch-test`:

```bash
./buddyswitch-test focused <file-or-nodeid>...
./buddyswitch-test full
```

For executable code, tests, runtime contracts, or test infrastructure, follow
`$buddyswitch-testing`. It owns dynamic target discovery, claim-scoped
escalation, evidence reuse/invalidation, and reviewer probes. The commands above
are its repository verification contract; the runner owns target validation,
isolation, exclusivity, and cleanup.

Do not encode feature-to-test mappings in `AGENTS.md` or the skill. Discover
targets from the current diff, code, tests, contracts, and runner constraints.
Generic completion or review guidance must not upgrade focused proof to `full`
unless the skill reaches FINAL, repository-wide acceptance is explicit, or the
user directly requests it.

Use `focused` for the shortest relevant proof and `full` for serial acceptance
across unit, integration, process, and system tiers. Do not publish or add a
second test entry.

Use the fastest meaningful proof available:

- focused unit test
- regression test
- integration or CLI main-path run
- typecheck, lint, or build
- log inspection
- UI screenshot or manual run when relevant

A passing test suite must prove real behavior. If verification is blocked, report the blocker instead of claiming completion.

## BuddySwitch Context

Use this checkout for BuddySwitch source, tests, docs, launcher behavior, and framework contracts.

Key paths:

- Shared product-source mount point: `projects/app/`
- Env manifest: `buddyswitch/manifest.toml`
- Product runtime launcher: `./buddyswitch-codex instance start --role <role>`
- Role host instructions: `tools/launcher/assets/roles/<role>/AGENTS.md`

Runtime state is projected under:

- `buddyswitch/objects/tracks/*.json`
- `buddyswitch/objects/tasks/*.json`
- `buddyswitch/objects/artifacts/*.json`

Persistent private host files live under `$BUDDYSWITCH_ACTOR_PRIVATE_DIR`, which resolves to the active instance `workspace/private`. Product objects still require explicit env tools; do not edit `buddyswitch/objects/**` or old private workspace runtime paths directly.

Use env tools for product-mode runtime state. Do not edit `buddyswitch/objects/**` or `buddyswitch/local/private/**` directly.
Runtime contracts are owned by code, JSON contracts, role contracts, and tests; do not create prose mirrors for runtime behavior.

## Done

A task is done only when the bottleneck moved forward, the scope stayed focused, important behavior is covered by meaningful tests, replaced baggage was removed or explicitly justified, relevant verification passed, and the final response states what changed, how it was verified, and what risk remains.
