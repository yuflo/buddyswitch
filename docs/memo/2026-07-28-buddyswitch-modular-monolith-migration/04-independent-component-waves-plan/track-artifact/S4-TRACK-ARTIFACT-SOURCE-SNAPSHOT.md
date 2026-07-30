# S4 Track–Artifact Source Snapshot

> Snapshot date: 2026-07-30
> Snapshot HEAD/tree: `5c065a6d85bae8723ab0a29f602a09ac7f179a67` /
> `7d290b313c7ac754e8d07e96e72dee1676b9c85a`
> Accepted executable predecessor: `25916f58fbce46c4ad28d7359b61340ead59d986`
> Branch: `fea-tool`

## 1. Repository identity

At refresh:

```text
tracked patch SHA-256:
  e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
index patch SHA-256:
  e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
untracked path manifest SHA-256:
  e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
git diff --check:
  clean
```

`5c065a6` differs from the accepted Search commit only by the approved
Track–Artifact boundary memo. No executable source, test, fixture, manifest,
package declaration or runtime asset changed after Search acceptance.

The installed runtime remains source-correspondent:

```text
activated_at:
  2026-07-30T05:15:04.307720Z
source_digest:
  1ac19eb878ec0ff8989836280710d9c2b6ea9d00972295430f57548cb74742a9
distribution_digest:
  81f301201e85a5e3d7008dc4ca853804d93dbf863b6b6987a1b468f5c851d4fa
package_version:
  0.1.0
runtime.verify:
  ok=true
```

The preparation-document commit created after this snapshot may advance HEAD.
It must change coordinating documents only. The executor verifies executable
equivalence to this snapshot before mutation.

## 2. Current owner manifests

### Track-owned live sources

```text
src/buddyswitch/env/repos/tracks.py
src/buddyswitch/env/repos/track_comments.py
src/buddyswitch/env/domain/track_comments.py
src/buddyswitch/env/domain/track_read.py
src/buddyswitch/env/domain/track_artifact_relations.py
src/buddyswitch/env/tools/track/__init__.py
src/buddyswitch/env/tools/track/tool.py
src/buddyswitch/env/tools/track/_impl.py
src/buddyswitch/launcher/track_comment_inbound.py
src/buddyswitch/launcher/track_comment_added_handler.py
src/buddyswitch/skills/shared/track-tool/SKILL.md
src/buddyswitch/skills/pm/triage-track/SKILL.md
```

Path/content manifest:

```text
429f88387c78ad8e55c1ba2a2e38d14eb670ad99e9182a40dbd5bba82fcf35b3
```

### Artifact-owned live sources and assets

```text
src/buddyswitch/env/repos/artifacts.py
src/buddyswitch/env/domain/artifact_visibility.py
src/buddyswitch/env/domain/artifact_relations.py
src/buddyswitch/env/domain/source_refs.py
src/buddyswitch/env/tools/artifact/__init__.py
src/buddyswitch/env/tools/artifact/tool.py
src/buddyswitch/env/tools/artifact/_impl.py
src/buddyswitch/runtime_support/artifact_selection.py
src/buddyswitch/config/artifact-selection-v1.json
src/buddyswitch/config/artifact-selection-v2.json
src/buddyswitch/skills/shared/artifact-tool/SKILL.md
```

Path/content manifest:

```text
b252d5e66f81668b208153b2ef7c6672bfc4cac132962aca4fb36260da7c8706
```

The exact per-file digests are reproducible from the snapshot commit. The two
manifest digests cover path and content identity; they are not future layout
requirements.

## 3. Current semantic facts

The refresh re-established:

- `track.artifact_relations` is Track-persisted state;
- Track `done` requires a current proof relation;
- Track relation mutation currently reads Artifact Private state before writing
  Track state;
- Artifact visibility and backlink projection currently scan Track Private
  state;
- Track projections currently read Artifact metadata and attachments;
- generic `ToolContext` exposes both modules' repositories and rules;
- Context and Evidence bypass the future Public owners;
- CLI and Web import the Track read implementation directly;
- generic instance Daemon imports the Track comment source directly;
- generic runtime paths and cleanup encode Track/Artifact namespaces;
- the stable Artifact selection application command delegates to a
  `runtime_support` implementation;
- Track/Artifact Skills and selection assets remain in shared roots.

No source fact contradicts the approved ownership or dependency direction.

## 4. Current owner tests

The directly owning tests currently include:

```text
Track
  tests/integration/env_tool/test_track.py
  tests/integration/env_tool/test_track_comment.py
  tests/integration/track/test_comment_added_handler.py
  tests/integration/track/test_owner_actor_model.py
  tests/unit/track/test_comments_repo.py

Artifact
  tests/integration/env_tool/_artifact_env_tool_case.py
  tests/integration/env_tool/test_artifact_attachments.py
  tests/integration/env_tool/test_artifact_listing.py
  tests/integration/env_tool/test_artifact_publication.py
  tests/integration/env_tool/test_artifact_relations.py
  tests/integration/env_tool/test_artifact_validation.py
  tests/integration/env_tool/test_response_artifact.py
  tests/unit/env_tool/test_artifact_selection.py
```

Cross-component, Process, System, Web/CLI, Context, Evidence, package and
repository architecture tests remain root-owned.

## 5. Behavior-preserving entry evidence

The frozen Search FINAL is valid refactor-entry evidence for the unchanged
executable snapshot:

```text
run:
  7ecfb65c5e0643c6b112cc8af3c7e98b
command:
  ./buddyswitch-test full
result:
  Unit Python 440 passed, 1,122 subtests
  Unit JavaScript 147 passed
  Integration 761 passed, 442 subtests
  Process 262 passed, 377 subtests
  System 22 passed
  shell syntax PASS
  diff check PASS
  exit 0
cleanup:
  run root absent; no attributable runtime residue
```

This evidence is reused because only a historical memo was added afterward.
The executor must still discover and record a narrower Track–Artifact
behavior-preserving baseline if current source, tests or material runtime no
longer match. It must not rerun the full repository merely to establish entry.

## 6. Current coupling to remove

The migration is incomplete while any of these remain live:

- a Track or Artifact implementation under `env/repos`, `env/domain`,
  `env/tools`, `launcher`, `runtime_support`, shared `config` or shared
  `skills`;
- direct cross-Private import or repository access;
- Track/Artifact repository or rule access on generic `ToolContext`;
- Track/Artifact-specific paths in generic `runtime_files`;
- Track/Artifact-owned discovery in generic cleanup;
- Track inbound imported by the generic Daemon;
- old and new Tool discovery at the same time;
- a stable entrypoint that delegates to the retired Artifact selection path;
- root owning-test duplicates after module-local relocation;
- current guidance or package projection teaching the retired owner.
