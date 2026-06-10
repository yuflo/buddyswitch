# Track-Native Comment Rebuild Phase 2 Prompt

Worktree: `comment`

Execute the plan in:

- `docs/spec/2026-06-10-track-comment-rebuild-test-plan.md`
- `docs/spec/2026-06-10-track-comment-rebuild-development-plan.md`

Rules:

1. Use the current worktree only. Do not touch main.
2. Follow SHARP: solve the current bottleneck, take the shortest verified path, do not keep compatibility branches for old `comment.*`.
3. Use TDD for behavior changes:
   - write or update the failing test first;
   - run the focused test and confirm the expected failure;
   - implement the smallest direct change;
   - rerun the focused test until green.
4. Respect `docs/bitter/2026-05-26-test-resource-lifecycle-principles.md`.
   - Do not start launcher/browser/daemon service suites unless required.
   - Prefer isolated runtime-root pytest groups.
   - Run broad verification only after focused groups pass.
5. Final state must prove:
   - no actor-facing `comment` tool remains;
   - Track comments are stored under `buddyswitch/objects/track-comments/<track_id>/<comment_id>.json`;
   - no active `target_type`, `target_id`, `anchor`, or `artifact_revision_id` comment behavior remains;
   - `track.add_comment`, `track.list_comments`, and `track.resolve_comment_thread` preserve Track discussion capability;
   - replies and resolution cannot cross Tracks;
   - `track.open` and context expose only compact Track comment cues;
   - Artifact comments and Artifact section comments are removed;
   - tests and static sweeps verify the removal.
6. If a product-semantic ambiguity blocks implementation, stop and ask. Otherwise make a grounded local decision and continue.
7. Completion requires focused tests, broad non-service verification, static removal sweep, and a final review against the memo acceptance criteria.

Start with the next failing test from the development plan and keep looping until all required verification passes.
