# S4 Search Source Snapshot

> Snapshot date: 2026-07-30
> Base HEAD/tree: `e4fe342144febc023d1d635012e7e8a5e645138d` /
> `5eec6f43e578456b5e75ba4eee7eec3f56437a08`
> Branch: `fea-tool`

## 1. Repository identity

At refresh:

```text
HEAD == origin/fea-tool
tracked patch: empty
index patch: empty
untracked files: none
instances: 0
Browser: inactive
git diff --check: clean
```

The verified installed runtime was:

```text
activated_at:        2026-07-30T03:01:00.208553Z
source_digest:       8f78328a3fddb2a19fbeba3dd3eff9ddd1384ee76e898b2b5ebbf4da0c1e7d5b
distribution_digest:f13b885405ec04a0f5085949b69f5d0430d563e3aea45c968af925873f264845
package_version:     0.1.0
runtime.verify:      ok=true
```

The preparation-document commit created after this snapshot may change HEAD.
The hub handoff supplies that exact commit. Product source/test identity must
still correspond to this snapshot.

## 2. Current Search owner

Current production files:

```text
src/buddyswitch/env/tools/search/__init__.py
src/buddyswitch/env/tools/search/tool.py
src/buddyswitch/env/tools/search/_impl.py
```

Path/content manifest:

```text
53f8f4b63a0b2c4517f594a43cf226d8fd573b213f44e80dfe699bed58b77aee
```

Per-file SHA-256:

```text
2446ea97a948bd8fef98c38c6b08d802015a92536bec635549b8d42ec470938d  __init__.py
edcd480e5ba61a0149dc7d1013c46efcf6d8421516e7764639b2b13b2d033ca0  tool.py
3b08aca60e1a4fc8be563e76ac94eb5fd34df15c05a6e7a4e7f977c5ef5734e3  _impl.py
```

Current Search-owned behavior tests:

```text
tests/integration/env_tool/test_search.py
tests/integration/env_tool/test_response_search.py
```

Path/content manifest:

```text
46fd312220d24f2193a3b8ba15f76ab76532a1b6cbea262797bdb45b3ce79ecf
```

## 3. Behavior and state

Search owns:

- Tool ID `search`;
- actions `status` and `request`;
- explicit backend/query/engine validation;
- profile-backed backend capability projection;
- non-opening URL planning for Google/Web/Reddit/X;
- rejection guidance for removed `open_browser`;
- `search_api` permission/provider boundary.

Search does not own:

- Browser process or page lifecycle;
- fetched result content;
- canonical state, locks or writes;
- Daemon, Web, CLI, Skill or cleanup contribution;
- a public cross-component service.

The current implementation consumes only generic Tool invocation facts plus
`runtime_support.env_profiles`.

## 4. Preservation baseline

Before mutation, the source-bound affected group passed:

```text
run: b96f488146524dbc97eb14463aea7780
result: 93 passed, 543 subtests
duration: 11.43s
cleanup: run root absent; no attributable process/resource residue
```

The exact command is frozen in the implementation plan. This is preservation
evidence, not candidate GREEN.

Every existing mutable test consumer also passed before product mutation:

```text
run: 978b8137549e47bf9542e69b2045e2d6
scope: Search behavior/response, shared Artifact/registry response consumers,
       Demand/Task/Tool/package architecture consumers
result: 60 passed, 27 subtests
duration: 1.16s
cleanup: run root absent; zero instances; Browser inactive
```

## 5. Current defect to remove

`ToolContext.browser` exposes `BrowserAccess.request(...)`, a Search-shaped
placeholder with no current consumer. Search itself does not call it. Keeping
the method after physical aggregation would leave Search semantics in the
generic host, so this lane removes that method and proves absence.
