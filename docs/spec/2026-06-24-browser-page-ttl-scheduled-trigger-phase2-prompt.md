# Browser Page TTL Scheduled Trigger Phase 2 Prompt

Worktree: `/Users/chen/Dev/buddyswitch/.worktrees/fea-tool`

Execute the plan in:

- `docs/spec/2026-06-24-browser-page-ttl-scheduled-trigger-test-plan.md`
- `docs/spec/2026-06-24-browser-page-ttl-scheduled-trigger-development-plan.md`

Rules:

1. Follow SHARP: solve the current bottleneck with the shortest verified path. Do not add compatibility
   wrappers or speculative frameworks.
2. Use test-driven development for each behavior: write the focused failing test, run it and confirm the
   expected failure, implement the smallest direct change, then run the focused test until green.
3. Protect host resources. Read and obey
   `docs/bitter/2026-05-26-test-resource-lifecycle-principles.md`. Do not run broad service-starting
   suites until the focused tests pass and cleanup is proven.
4. Use generic daemon scheduled triggers. Browser page expiry is the first consumer, not daemon-owned
   browser policy.
5. Only successful real new-page opens with a known CDP target id register TTL. Reuse, select, blocked
   opens, failed opens, and ambiguous target detection do not register or refresh TTL.
6. If schedule registration fails after a page opens, keep the open success explicit and report
   `ttl_registered=false`. Do not claim TTL protection.
7. Browser expiry closes by `target_id` only. Missing target or unavailable browser endpoint is handled as
   stale; close command failure marks the schedule failed once.
8. Completion requires all focused tests passing and a final review against the test plan checklist.

Focused final command:

```bash
python3 -m unittest \
  tests.test_daemon_trigger_router \
  tests.test_daemon_service_contract \
  tests.test_daemon_mailbox \
  tests.test_daemon_core \
  tests.test_instance_daemon_entrypoint \
  tests.test_browser_page_expired_handler \
  tests.test_cdp_browser_session \
  tests.test_browser_cockpit_proxy \
  tests.test_search_env_tool
```

If a special problem or external ambiguity appears, stop and ask the user. Otherwise continue until the
focused suite passes and the review checklist is satisfied.
