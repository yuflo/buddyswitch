# fea-webui and fea-tool Main Merge Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Merge `fea-webui` and `fea-tool` into `main` while preserving the latest product behavior and removing stale live surfaces instead of keeping compatibility tracks.

**Architecture:** Keep the two feature boundaries separate: `fea-webui` owns the Web-managed iMessage channel and External IM handoff; `fea-tool` owns Chrome DevTools cockpit page lifecycle registration. The integration layer only fixes cross-environment verification issues and deletes stale docs that would teach retired behavior.

**Tech Stack:** Python launcher/runtime code, `pytest`, `unittest`, git merge-tree dry runs, scoped residue scans.

---

## Current Baseline

- `main` is clean at `3d7046a` and matches `origin/main`.
- `fea-webui` is at `8aa0d0f` and matches `origin/fea-webui`.
- `fea-tool` is at `45ae06c` and matches `origin/fea-tool`.
- Both feature worktrees are clean.

## Conflict, Dependency, And Association Assessment

### Conflict Assessment

- `git merge-tree --write-tree main fea-webui` produced tree `d0cdd293344da6d9c489f1bf2dcf96b6e82a2d67`.
- `git merge-tree --write-tree main fea-tool` produced tree `9ae1de3176666467349ca55ca396f10415f89ade`.
- A synthetic sequential merge of `main + fea-webui + fea-tool` produced tree `11c7472e7fbf94f15b295866d8deceb003135552`.
- Result: no textual merge conflicts are expected.

### Dependency Assessment

- No package or lockfile manifests are changed by either branch.
- `fea-webui` adds runtime code under `tools/launcher` and `scripts/env/services`, plus focused tests and iMessage runbook/spec material.
- `fea-tool` changes only `tools/launcher/chrome_devtools_cockpit_proxy.py`, `tests/test_browser_cockpit_proxy.py`, and its browser lifecycle spec.
- Result: no dependency installation or lockfile reconciliation is required.

### Association Assessment

- The branches have no overlapping changed source files.
- `fea-webui` and `fea-tool` are semantically related through launcher/runtime quality gates but do not share behavior paths.
- The only integration fix discovered before merge is in `tools/launcher/external_im_session.py`: its runtime type alias must avoid Python-version-sensitive union syntax because launcher subprocesses can resolve a different `python3` than the parent test process.
- `fea-webui` also contains trailing whitespace in a memo file, so the final tree must pass `git diff --check`.
- `fea-webui` carries historical planning/memo files that still describe the retired iMessage bridge direction. Those should not enter `main` as live guidance. Preserve current product progress in code, tests, and the current smoke runbook; delete stale planning artifacts instead of marking them compatible.

## Merge Plan

### Task 1: Record The Plan

- [ ] Add this merge and test plan under `docs/spec`.
- [ ] Commit the plan before code merge if the worktree is otherwise clean.

Verification:

```bash
git status --short
```

Expected: only this plan file is staged before the planning commit.

### Task 2: Merge `fea-webui`

- [ ] Run `git merge --no-ff --no-commit fea-webui`.
- [ ] Fix `tools/launcher/external_im_session.py` so runtime type aliases do not evaluate `str | None`.
- [ ] Remove stale iMessage bridge planning/memo files that are no longer current execution guidance.
- [ ] Remove trailing whitespace introduced by the branch.
- [ ] Keep the current iMessage channel code, External IM session changes, Web lifecycle changes, tests, and current smoke runbook.
- [ ] Run focused iMessage/Web verification.
- [ ] Commit the merge.

Focused verification:

```bash
python3 -m py_compile tools/launcher/external_im_session.py tools/launcher/imessage_channel.py tools/launcher/web_management.py tools/launcher/im_http_router.py
python3 -m pytest -q tests/test_imessage_channel.py tests/test_external_im_session.py tests/test_im_web_management_projection.py tests/test_web_management.py
git diff --check
```

Expected: compile passes, focused tests pass, whitespace check has no output.

### Task 3: Merge `fea-tool`

- [ ] Run `git merge --no-ff --no-commit fea-tool`.
- [ ] Keep the deterministic post-response `new_page` lifecycle reconciliation path.
- [ ] Ensure the browser lifecycle spec is current or remove stale implementation checklist wording.
- [ ] Run focused browser verification.
- [ ] Commit the merge.

Focused verification:

```bash
python3 -m unittest tests.test_browser_cockpit_proxy
git diff --check
```

Expected: browser cockpit proxy tests pass and whitespace check has no output.

### Task 4: Final Integration Verification

- [ ] Run broad Python verification from `main`.
- [ ] Run scoped residue scans for retired iMessage public surfaces and stale dual-path wording in live runtime/test/spec surfaces.
- [ ] Inspect final git status and recent history.

Broad verification:

```bash
python3 -m pytest -q
git diff --check
git status --short --branch
```

Residue scan:

```bash
python3 -m pytest -q tests/test_imessage_channel.py::ImessageChannelResidueTests::test_no_retired_imessage_surface
```

Expected: no live runtime or test hits for retired iMessage public surfaces; any remaining doc hit must be in a current acceptance/runbook context, not current execution guidance for the retired path.

## Acceptance Criteria

- `main` contains both feature branches' current product behavior.
- No textual merge conflicts remain.
- No dependency manifest reconciliation is required.
- No standalone retired iMessage public entry, parameter path, source module, or test module remains live.
- No compatibility alias, dual state read, or parallel lifecycle path is introduced.
- Focused iMessage/Web and browser tests pass.
- Broad Python verification passes, or any blocker is recorded with exact failing command and root cause.
- Final report includes changed commits, verification evidence, and remaining risk.
