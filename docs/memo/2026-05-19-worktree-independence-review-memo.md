# Worktree Independence Review Memo

Date: 2026-05-19

Worktree: `track-artifact-pm-runtime-repair`

## Scope

This memo records the review of the current worktree against four independence questions:

1. Whether tools are independent from each other.
2. Whether each tool can be developed independently.
3. Whether skill development is independent from tool development.
4. Whether track, artifact, message, comment, buddybox, and adjacent runtime object development are each independent.

No code was changed during the review that produced these findings.

## Conclusion

The current worktree is partially independent, but not fully independent across the four requested dimensions.

The main architectural direction is clear: the branch has moved toward per-tool services, concrete object repositories, domain modules, runtime catalog discovery, and skill documents that avoid copying full payload/schema tables. That is a meaningful improvement over a single mixed runtime store.

However, the runtime still has important coupling points:

- One tool import failure can break the whole `env.tool` dispatch path.
- The central registry/dispatch/catalog files remain shared edit points for every tool.
- Some tool contracts and service payload allowlists have drifted.
- Track, artifact, and comment are intentionally cross-object workflows rather than fully independent object domains.
- Skill guidance mostly consumes runtime discovery, but some examples still encode stale or misleading payload fields.

The highest-priority bottleneck is runtime import isolation and Python interpreter compatibility. Under the checkout's default `python3`, the env.tool router can fail before any specific tool action runs.

## Finding 1: Tools Are Not Fully Independent

Tool runtime independence is not complete.

`scripts/env/tools/dispatch.py` imports every service module at module load time:

- `env.services.artifacts`
- `env.services.buddybox`
- `env.services.comments`
- `env.services.context`
- `env.services.evidence`
- `env.services.messages`
- `env.services.search`
- `env.services.tasks`
- `env.services.tracks`

Because dispatch imports all services eagerly, one broken tool module can prevent every tool from dispatching.

Concrete failure observed:

```text
python3 --version
Python 3.9.6

python3 -m pytest tests/test_env_tool_router.py::EnvToolRouterTests::test_dispatch_handler_coverage_matches_registry_actions -q
FAILED
TypeError: unsupported operand type(s) for |: 'types.GenericAlias' and 'NoneType'
```

The failure comes from `scripts/env/domain/messages.py`:

```python
GetMessage = Callable[[str], dict[str, Any] | None]
```

Under Python 3.9, this annotation expression is evaluated inside a `Callable[...]` alias and fails. Since `env.tools.dispatch` imports `env.services.messages`, and router imports dispatch, this message-domain problem blocks the router path for unrelated tools too.

The same import path works with `python` pointing to Python 3.13.5:

```text
python --version
Python 3.13.5

python -m pytest tests/test_env_tool_router.py::EnvToolRouterTests::test_dispatch_handler_coverage_matches_registry_actions -q
1 passed, 9 subtests passed
```

Judgment: tools are structurally separated by service modules, but operationally not independent because dispatch is eager and shared.

## Finding 2: Tool Development Is Only Partly Independent

Each major tool now has a focused service and repository path:

- `scripts/env/services/tasks.py` with `scripts/env/repos/tasks.py`
- `scripts/env/services/tracks.py` with `scripts/env/repos/tracks.py`
- `scripts/env/services/artifacts.py` with `scripts/env/repos/artifacts.py`
- `scripts/env/services/messages.py` with `scripts/env/repos/messages.py`
- `scripts/env/services/comments.py` with `scripts/env/repos/comments.py`
- `scripts/env/services/buddybox.py` with `scripts/env/repos/buddybox_files.py`

Repository boundaries are reinforced by tests. For example, `tests/test_env_layer_boundaries.py` checks that object repos only import `runtime_files`, and that domain cross-object imports are allowlisted.

However, tool development still has shared edit points:

- `scripts/env/tools/contracts.py`
- `scripts/env/tools/semantics.py`
- `scripts/env/tools/dispatch.py`
- `scripts/env/tools/router.py`
- `scripts/env/client.py`
- `tests/test_env_tool_semantic_contract.py`
- `tests/test_env_tool_router.py`

Adding or changing an action normally requires touching the registry, semantic projection, dispatch map, CLI surface, and tests. This is acceptable for a small monolith, but it is not independent per-tool development.

There is also contract/service drift:

```text
task.create:
  contract fields = status, summary, task_id, title, track_id
  service fields  = active_buddy, buddy, status, summary, task_id, title, track_id

track.update_now:
  service additionally allows owner_buddy

track.add_update:
  service additionally allows owner_buddy

comment.add:
  service additionally allows anchor, artifact_revision_id, mentions

comment.list:
  service additionally allows status
```

The `task.create` drift is especially risky. A direct service check showed that passing `buddy=design` and `active_buddy=dev` returns `ok=true`, but the stored task owner is still the runtime active buddy:

```json
{"args_active_buddy":"dev","args_buddy":"design","ok":true,"task_buddy":"pm"}
```

That means stale or misleading payload fields are accepted but ignored. This weakens both the runtime contract and the skill surface.

Judgment: each tool has a clearer development area than before, but shared registry/CLI/catalog files and contract drift prevent true independent tool development.

## Finding 3: Skill Development Is Mostly Independent From Tool Development

Skill development is directionally independent from tool implementation.

The shared tool skills generally route exact operation and payload knowledge to runtime discovery:

- `context.get.tool_catalog['task']`
- `context.get.tool_catalog['track']`
- `context.get.tool_catalog['artifact']`
- `context.get.tool_catalog['buddybox']`
- `context.get.tool_catalog['message']`
- `context.get.tool_catalog['comment']`
- `python3 scripts/turn_runtime.py status`

Tests enforce this boundary:

```text
python -m pytest tests/test_runtime_skills.py tests/test_repo_consistency.py::RepoConsistencyTests::test_skill_and_contract_texts_do_not_copy_payload_field_or_schema_tables -q
12 passed, 39 subtests passed
```

Relevant tests include:

- `RuntimeSkillsTests.test_shared_tool_skills_route_exact_fields_to_runtime_discovery`
- `RuntimeSkillsTests.test_shared_tool_skills_do_not_duplicate_runtime_action_catalogs`
- `RepoConsistencyTests.test_skill_and_contract_texts_do_not_copy_payload_field_or_schema_tables`

This supports the intended rule: skill files should describe when and why to use tools, while runtime code owns exact action/payload semantics.

Remaining issue:

`buddyswitch/skills/shared/task-tool/SKILL.md` includes a concrete example with `"buddy":"design"` in a `task.create` payload. Runtime behavior ignores that field and assigns the task to the active buddy. This example conflicts with the active-buddy-private task model.

Judgment: skill development is mostly independent from tool development, but examples still need cleanup so skill edits do not encode stale runtime semantics.

## Finding 4: Runtime Object Domains Are Not All Independent

The object domains are not all meant to be independent. Current structure has both intended and incidental coupling.

### Track and Artifact

Track and artifact are intentionally coupled through publication.

`scripts/env/domain/publication.py` imports both artifact and track repos and performs cross-object mutations. `track.add_material` and `track.add_proof` publish artifact drafts by updating both:

- the artifact object status/publication fields
- the track page material/proof refs

This is a product workflow boundary, not an accidental dependency. The current branch centralizes it in `publication.py`, which is clearer than spreading track/artifact mutation across both services.

Judgment: track and artifact are not independent; they share a deliberate publication domain.

### Comment

Comment storage is independent at the repo level, but comment behavior depends on target readability.

`scripts/env/domain/comment_targets.py` depends on artifact visibility logic and artifact repo reads. Comments can target readable tracks/artifacts, so comment development is coupled to target scope rules.

The comment repo itself is constrained to comment storage, and boundary tests check this.

Judgment: comment persistence is independent; comment domain behavior is coupled to track/artifact readability by design.

### Message

Message is the most independent product-object tool among the reviewed runtime objects.

`scripts/env/services/messages.py` uses message domain and message repo only, plus manifest buddy ids. It does not depend on track, artifact, comment, or buddybox state.

The current import failure is a Python compatibility problem, not a business-domain coupling problem.

Judgment: message domain is conceptually independent, but eager dispatch import makes its failures affect all tools.

### Buddybox

Buddybox service and repo are mostly independent and instance-local:

- service: `scripts/env/services/buddybox.py`
- repo: `scripts/env/repos/buddybox_files.py`

Buddybox does not mutate runtime product objects. It uses active-buddy private logical names and stores under the active instance workspace.

There is one duplication concern: `scripts/env/services/source_refs.py` repeats buddybox logical-name validation instead of reusing `buddybox_files.normalize_logical_name`. This is not a direct runtime mutation coupling, but it can drift.

Judgment: buddybox is mostly independent, with a small validation duplication risk in source refs.

### Task

Task is mostly private and independent from shared publication. Tests explicitly verify that `task.track_id` is only a private organizational hint and does not mutate track or artifact state.

However, `task_domain.optional_track_context` reads the track repo to validate `track_id`. That is a read-only dependency. It is acceptable if the product wants task hints to reference existing tracks, but it means task is not purely standalone.

Judgment: task is mostly independent, with read-only track validation and payload drift around `buddy`/`active_buddy`.

## Verification Commands Run

The review used the following commands.

Failed under default `python3`:

```bash
python3 --version
python3 -m pytest tests/test_env_tool_router.py::EnvToolRouterTests::test_dispatch_handler_coverage_matches_registry_actions -q
python3 -m pytest tests/test_message_env_tool.py -q
python3 -m pytest tests/test_env_layer_boundaries.py::EnvLayerBoundaryTests::test_domain_cross_object_imports_are_allowlisted -q
```

Observed result:

- `python3` is Python 3.9.6.
- Router/message/boundary test collection fails through `env.domain.messages.GetMessage`.

Passed under `python`:

```bash
python --version
python -m pytest tests/test_env_tool_router.py::EnvToolRouterTests::test_dispatch_handler_coverage_matches_registry_actions -q
python -m pytest tests/test_runtime_skills.py tests/test_repo_consistency.py::RepoConsistencyTests::test_skill_and_contract_texts_do_not_copy_payload_field_or_schema_tables -q
python -m pytest tests/test_env_layer_boundaries.py::EnvLayerBoundaryTests::test_object_repo_sibling_imports_are_restricted_to_runtime_files tests/test_env_layer_boundaries.py::EnvLayerBoundaryTests::test_domain_cross_object_imports_are_allowlisted tests/test_env_layer_boundaries.py::EnvLayerBoundaryTests::test_skills_and_boundary_guides_do_not_copy_payload_or_schema_tables -q
```

Observed result:

- `python` is Python 3.13.5.
- Focused router, skill, repo-boundary, domain-boundary, and skill-schema-copy tests pass.

Additional inspection:

```bash
git status --short
git diff --stat main...HEAD
git diff --name-status main...HEAD
rg imports under scripts/env
```

The worktree was clean before this memo was added.

## Recommended Fix Order

1. Fix the default `python3` runtime import failure.
   - Either make annotations Python 3.9-safe or standardize launcher/test commands on a newer Python.
   - Do this before claiming env.tool independence because current default `python3` breaks dispatch.

2. Make dispatch isolate per-tool load failures.
   - Prefer lazy per-tool service import or per-tool handler modules.
   - A message tool import problem should not block task, track, artifact, buddybox, or context dispatch.

3. Add a contract-vs-service payload allowlist test.
   - Runtime service accepted fields should match `contracts.TOOL_REGISTRY`.
   - If hidden compatibility fields are intentional, document and expose them explicitly; otherwise reject them.

4. Remove ignored payload fields from task service.
   - `buddy` and `active_buddy` should not be accepted by `task.create` unless they have real semantics.
   - Current behavior accepts them and silently ignores them.

5. Clean skill examples.
   - Remove `"buddy":"design"` from `task-tool` examples.
   - Keep examples minimal and continue routing exact payload knowledge to `context.get.tool_catalog`.

6. Consider extracting shared buddybox logical-name validation.
   - Avoid duplication between `buddybox_files.py` and `source_refs.py`.
   - Keep the source_refs behavior provenance-only; do not introduce buddybox read grants through source refs.

7. Keep track/artifact/comment coupling explicit.
   - Do not chase false independence where product workflow requires cross-object semantics.
   - Track/artifact publication belongs in one explicit domain module.
   - Comment target readability belongs in one explicit target-domain module.

## Short Answer To The Four Questions

1. Tool 彼此之间是否独立？
   - No. They are modularized, but eager dispatch imports mean one tool can break all tools.

2. Tool 各个开发是否独立？
   - Partly. Services/repos are separated, but registry, semantics, dispatch, CLI, and shared tests are still common edit points. Payload contract drift also remains.

3. Skill 开发是否跟 tool 开发独立？
   - Mostly. Skills rely on runtime discovery instead of copying full schemas, and tests enforce that. Some examples still encode stale fields.

4. track、artifact、message、comment、buddybox 等开发是否各自独立？
   - Mixed. Message and buddybox are mostly independent. Task is mostly independent with read-only track validation. Track/artifact/comment are intentionally coupled around publication and target readability.
