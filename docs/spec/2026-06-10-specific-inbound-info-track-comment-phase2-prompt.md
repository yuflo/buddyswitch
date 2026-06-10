# Specific Inbound Track Comment Phase 2 Prompt

Worktree: `main`

Execute the plans in:

- `docs/spec/2026-06-10-specific-inbound-info-track-comment-test-plan.md`
- `docs/spec/2026-06-10-specific-inbound-info-track-comment-development-plan.md`

Rules:

1. Work on `main`, as requested. Do not create a worktree.
2. Follow SHARP: solve this Track comment inbound bottleneck directly; do not add a generic inbound
   lifecycle, wrappers, compatibility branches, or Artifact inbound.
3. Use TDD for behavior changes:
   - write or update the focused failing test first;
   - run it and confirm the expected failure;
   - implement the smallest direct change;
   - rerun the focused test until green.
4. Respect `docs/bitter/2026-05-26-test-resource-lifecycle-principles.md`:
   - do not start launcher/browser/daemon service suites for this task;
   - prefer isolated runtime-root unit and env-tool tests;
   - broaden verification only after focused groups pass.
5. Final behavior must prove:
   - `track.add_comment` delivers `track.comment.added` for explicit mentions;
   - replies notify the replied comment author;
   - duplicate targets are delivered once;
   - authors are not notified about their own new comments;
   - comments without explicit attention do not deliver;
   - offline/unreachable/failed delivery keeps durable Track comment state and reports status;
   - signal payload carries only `track_id`, `comment_id`, and `thread_id`;
   - `TrackCommentAddedHandler` validates source truth before routing;
   - idle parent gets a Track-owned parent prompt;
   - running parent gets a Track-owned side triage prompt;
   - NC only aggregates source registrations;
   - no Artifact inbound is added.
6. If a product semantic ambiguity blocks implementation, stop and ask. Otherwise make the smallest
   grounded local decision and continue.
7. Completion requires focused tests, bounded broad non-service verification, compile verification,
   residue scans, and a final review against the memo acceptance criteria.

Start with Task 2 in the development plan and keep looping until all required verification passes.
