# Browser Tool Page Limit Phase 2 Prompt

Use this prompt in `fea-tool` to execute the plan.

```text
Work in /Users/chen/Dev/buddyswitch/.worktrees/fea-tool.

Read first:
- AGENTS.md
- docs/memo/2026-06-23-browser-tool-page-limit.md
- docs/bitter/2026-05-26-test-resource-lifecycle-principles.md
- docs/spec/2026-06-23-browser-tool-page-limit-test-plan.md
- docs/spec/2026-06-23-browser-tool-page-limit-development-plan.md

Implement the browser tool page-limit gate with TDD:
1. Add the focused failing tests from the test plan.
2. Verify the new focused tests fail for the expected missing behavior.
3. Implement the smallest direct change:
   - one shared CDP helper for page-count gate evaluation;
   - integration in search.open_browser;
   - integration in chrome-devtools-cockpit new_page;
   - response contract and semantic text updates only where behavior changed.
4. Run the focused tests until green:
   python3 -m pytest tests/test_search_env_tool.py -q
   python3 -m pytest tests/test_browser_cockpit_proxy.py -q
   python3 -m pytest tests/test_env_tool_response_contract.py -q
   python3 -m pytest tests/test_env_tool_semantic_contract.py -q
5. Run:
   git diff --check
   git status --short --branch
6. Review the diff against the memo and the development-plan acceptance checks.

Do not add innerTUI prompts, skills, role AGENTS text, prompt routers, generic resource frameworks, auto-close logic, URL normalization beyond exact match, or browser page scoring. Do not run broad service-starting suites unless focused cleanup is proven. The task is complete only when focused tests pass and review passes.
```

## Prompt Review

- The prompt is short enough to execute directly.
- It requires reading the memo, resource lifecycle warning, test plan, and development plan.
- It enforces TDD and focused verification.
- It preserves the forward-only scope: shared helper, two callers, tests, and review.
