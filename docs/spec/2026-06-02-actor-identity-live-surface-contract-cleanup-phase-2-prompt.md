# Actor Identity Live Surface Contract Cleanup Phase 2 Prompt

Use this prompt in worktree `/Users/chen/Dev/buddyswitch/.worktrees/fea-daemon`.

```text
Continue the Actor Identity live surface contract cleanup in /Users/chen/Dev/buddyswitch/.worktrees/fea-daemon.

Read first:
- AGENTS.md
- docs/bitter/2026-05-26-test-resource-lifecycle-principles.md
- docs/memo/2026-06-02-actor-identity-live-surface-contract-cleanup-task.md
- docs/spec/2026-06-02-actor-identity-live-surface-contract-cleanup-test-plan.md
- docs/spec/2026-06-02-actor-identity-live-surface-contract-cleanup-development-plan.md

Goal:
Remove remaining live actor/role identity residue so direct message identity, inbox ownership, conversation selection, task private ownership, actor private workspace guidance, Web UI instance management, and runtime skill guidance use actor-correct wording. Keep role wording only for role permissions, capability profiles, request queues, track ownership, artifact template allowlists, and readable target access.

Rules:
1. Stay in worktree fea-daemon. Do not touch main.
2. Use TDD. Update or add focused tests first, run them, and confirm the expected failure before implementation.
3. Implement direct replacements only. Do not add compatibility aliases, wrappers, or dual terminology.
4. Do not edit runtime state under buddyswitch/objects/**.
5. Be careful with resource lifecycle. Avoid broad launcher/browser/app-server tests unless required. If a test starts daemon/app-server/browser/broker/fake Codex processes, run one focused test first and inspect residual processes after.
6. Keep BuddySwitch brand strings. Do not treat the product name as legacy buddy identity.
7. Do not globally ban active role wording. Ban only exact role-as-actor residue on the scoped live surfaces.

Execution order:
1. Add/update tests from the test plan:
   - tests/test_env_tool_semantic_contract.py
   - tests/test_runtime_skills.py
   - tests/test_message_env_tool.py
   - tests/test_repo_consistency.py
   - tests/web_management_ui_state.test.js
   - tests/web_management_ui_contract.test.js
   - tests/test_buddy_env_profiles.py
2. Run the focused red checks and record which commands fail for the expected stale wording.
3. Fix runtime catalog and message domain feedback:
   - scripts/env/tools/message/tool.py
   - scripts/env/domain/messages.py
   - scripts/env/tools/comment/tool.py
   - scripts/env/tools/task/tool.py
4. Run:
   python3 -m pytest tests/test_env_tool_semantic_contract.py tests/test_message_env_tool.py -q
5. Fix live skills, README, Web UI, and env profiles:
   - buddyswitch/skills/shared/message-tool/SKILL.md
   - buddyswitch/skills/shared/comment-tool/SKILL.md
   - buddyswitch/skills/pm/define-scope/SKILL.md
   - README.md
   - tools/launcher/assets/web-management/index.html
   - tools/launcher/assets/web-management/app.js
   - framework/contracts/role-env-profile.json
   - buddyswitch/env-profiles/*.json
6. Run:
   python3 -m pytest tests/test_runtime_skills.py tests/test_repo_consistency.py tests/test_buddy_env_profiles.py -q
   node --test tests/web_management_ui_state.test.js tests/web_management_ui_contract.test.js
   python3 scripts/env_profiles.py validate-all
7. Run exact live-surface scans:
   rg -n -i "role messages|direct_role_channel|active_role_inbox|active-role inbox|not the active role|outside the active role|active role cannot|same role id|direct role inbox|direct role messaging|active-role tasksnapshot|active-role taskbox|current active-role taskbox task" scripts/env/tools/message/tool.py scripts/env/tools/comment/tool.py scripts/env/tools/task/tool.py
   rg -n -i "active role cannot|same role id|direct role messaging|active-role work management|role-locked codex instances|runtime workspace per role" buddyswitch/skills/shared/message-tool/SKILL.md buddyswitch/skills/shared/comment-tool/SKILL.md buddyswitch/skills/pm/define-scope/SKILL.md README.md
   rg -n "selectedBuddy|>Buddy<|Stored local role instances" tools/launcher/assets/web-management tests/web_management_ui_state.test.js tests/web_management_ui_contract.test.js
   rg -n "active-role-only" framework/contracts/role-env-profile.json buddyswitch/env-profiles
8. Run broad informational scan and classify any remaining hits:
   rg -n "active-role|active role|direct role|same role|role-locked|workspace per role" scripts/env/tools buddyswitch/skills README.md tools/launcher/assets framework/contracts buddyswitch/env-profiles
9. Run final focused verification:
   python3 -m pytest tests/test_env_tool_semantic_contract.py tests/test_runtime_skills.py tests/test_message_env_tool.py tests/test_repo_consistency.py tests/test_buddy_env_profiles.py -q
   node --test tests/web_management_ui_state.test.js tests/web_management_ui_contract.test.js
   python3 scripts/env_profiles.py validate-all
10. Run broader non-launcher verification:
   python3 -m pytest tests/test_env_tool_schema_contract.py tests/test_context_binding_env_tool.py tests/test_task_env_tool.py tests/test_comment_env_tool.py -q

Completion requires:
- same actor self-send remains rejected;
- same-role different-actor direct messaging remains allowed;
- message.conversation with role=<active_role> returns active actor visible same-role conversation rows;
- runtime message catalog uses actor-address identity language;
- comment/task catalogs no longer teach direct role inbox or active-role taskbox ownership;
- message skill says active actor cannot send to itself and same role with a different actor is allowed;
- README uses role-configured actor instances and runtime workspace per actor;
- Web UI uses Role labels and selectedRole state;
- env profiles and contract use role-profile-only;
- focused tests, Node UI tests, env profile validation, exact scans, and broader non-launcher verification pass;
- remaining broad-scan role wording is reviewed and classified as valid role authorization/capability/product ownership wording.

If a command repeatedly fails because the target behavior or data shape requires a product decision, stop and report the exact blocker with file paths, failing command, and observed output.
```

## Review

This prompt is intentionally scoped to one cleanup bottleneck. It does not ask the implementer to rebuild actor identity again, change request/track/artifact role semantics, or run resource-heavy launcher suites before focused proof.
