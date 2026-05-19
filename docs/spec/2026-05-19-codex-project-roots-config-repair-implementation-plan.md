# Codex Project Roots Config Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop BuddySwitch launcher-generated Codex configs from emitting unsupported `:project_roots` filesystem entries while preserving the runtime read/write boundary.

**Architecture:** Keep the fix inside launcher config generation. Replace the unsupported nested project-root rule table with flat absolute filesystem rules that current Codex understands. Do not add version detection, compatibility branches, prompt instructions, or a new permission abstraction.

**Tech Stack:** Python launcher config generator, TOML config parsing, Python unittest/pytest launcher tests, Codex CLI smoke verification.

---

## Current Failure

`./buddyswitch-codex instance start --buddy <buddy>` generates a `CODEX_HOME/config.toml` profile like:

```toml
[permissions.buddyswitch-runtime.filesystem]
":project_roots" = { "." = "read", "scripts/**" = "none", "tools/**" = "none" }
```

Codex CLI `0.131.0` warns that `:project_roots` and its nested entries are not recognized, then ignores them:

```text
warning: Configured filesystem path `:project_roots` is not recognized by this version of Codex and will be ignored.
warning: Configured filesystem path `:project_roots` with nested entry `scripts` is not recognized by this version of Codex and will be ignored.
```

The ignored entries are meant to deny stale launcher/runtime surfaces inside runtime workspaces. Removing the warning must not weaken those boundaries.

## Target Behavior

Generated product-session config must satisfy all of these:

- No `":project_roots"` filesystem key.
- No nested filesystem permission values.
- No relative filesystem permission keys.
- No glob filesystem permission keys such as `scripts/**`.
- Runtime workspace source/tool surfaces are denied through absolute `none` rules.
- `/` remains `read`.
- source repo checkout remains `none`.
- `project_workspace_dir` remains `read` for non-dev buddies and `write` for dev.
- active buddybox remains `write`.
- instance `home`, `codex-home`, `xdg-config`, and safe temp roots remain `write`.

## Scope

Modify only:

- `tools/launcher/codex_config.py`
- `tests/test_buddy_env_sandbox.py`
- `tests/test_buddyswitch_launcher.py`
- `tests/test_env_layer_boundaries.py`

Do not modify:

- launcher instance lifecycle
- workspace sparse checkout behavior
- env profile JSON contracts
- runtime broker behavior
- buddy AGENTS instructions
- Codex CLI invocation arguments

## Task 1: Add Outcome-Focused Config Shape Tests

**Files:**

- Modify: `tests/test_buddy_env_sandbox.py`

- [ ] **Step 1: Add helpers for flat filesystem assertions**

Add these helpers near the existing `_parse_profile_network` helper:

```python
def _runtime_workspace_denied_paths(workspace_dir: Path) -> set[str]:
    return {
        str((workspace_dir / "buddyswitch" / "skills").resolve(strict=False)),
        str((workspace_dir / "scripts").resolve(strict=False)),
        str((workspace_dir / "tools").resolve(strict=False)),
        str((workspace_dir / "tests").resolve(strict=False)),
        str((workspace_dir / "docs").resolve(strict=False)),
        str((workspace_dir / "buddyswitch" / "objects").resolve(strict=False)),
        str((workspace_dir / "README.md").resolve(strict=False)),
        str((workspace_dir / "buddyswitch-codex").resolve(strict=False)),
    }


def _assert_codex_filesystem_profile_is_flat(test: unittest.TestCase, filesystem: dict[str, object]) -> None:
    test.assertNotIn(":project_roots", filesystem)
    for key, value in filesystem.items():
        test.assertIsInstance(key, str)
        test.assertIsInstance(value, str, msg=key)
        test.assertNotIn("*", key)
        if key != "/":
            test.assertTrue(Path(key).is_absolute(), msg=key)
```

- [ ] **Step 2: Update the non-dev profile test to assert target behavior**

In `test_non_dev_permission_profile_keeps_workspace_read_only_and_writes_only_safe_roots`, remove `project_roots = filesystem[":project_roots"]` and all `project_roots[...]` assertions. Add:

```python
_assert_codex_filesystem_profile_is_flat(self, filesystem)
for denied_path in _runtime_workspace_denied_paths(workspace_dir):
    self.assertEqual(filesystem[denied_path], "none")
```

Keep the existing assertions for:

- `filesystem["/"] == "read"`
- `filesystem[str(project_workspace_dir.resolve(strict=False))] == "read"`
- `filesystem[str(ROOT.resolve(strict=False))] == "none"`
- writable instance roots
- forbidden write roots
- network config

- [ ] **Step 3: Update the dev profile test to assert target behavior**

In `test_dev_permission_profile_includes_project_workspace_but_keeps_state_read_only`, remove `project_roots` assertions. Add:

```python
_assert_codex_filesystem_profile_is_flat(self, filesystem)
for denied_path in _runtime_workspace_denied_paths(workspace_dir):
    self.assertEqual(filesystem[denied_path], "none")
```

Keep the existing dev behavior assertions:

- project workspace is writable
- active dev buddybox is writable
- shared state, shared root, shared project root, instance root, and workspace root are not writable
- source repo checkout is `none`

- [ ] **Step 4: Update the launcher-surface hardening test**

In `test_dev_permission_profile_denies_runtime_workspace_launcher_surfaces`, remove `project_roots` assertions. Add:

```python
_assert_codex_filesystem_profile_is_flat(self, filesystem)
for denied_path in _runtime_workspace_denied_paths(workspace_dir):
    self.assertEqual(filesystem[denied_path], "none")
```

Keep the existing assertions proving allowed writes still exist.

- [ ] **Step 5: Update stale-source-surface test**

In `test_permission_profile_denies_stale_runtime_source_surfaces`, remove `project_roots` assertions. Add:

```python
_assert_codex_filesystem_profile_is_flat(self, filesystem)
for denied_path in _runtime_workspace_denied_paths(workspace_dir):
    self.assertEqual(filesystem[denied_path], "none")
```

This test now verifies the same product outcome without relying on the old unsupported implementation shape.

- [ ] **Step 6: Run the focused test and verify it fails before implementation**

Run:

```bash
python3 -m pytest tests/test_buddy_env_sandbox.py -q
```

Expected before implementation: FAIL because generated filesystem entries still contain `:project_roots` and nested values.

## Task 2: Generate Flat Absolute Filesystem Rules

**Files:**

- Modify: `tools/launcher/codex_config.py`

- [ ] **Step 1: Narrow permission profile rendering to string values**

Change `render_permission_profile_block` to reject nested filesystem values:

```python
def render_permission_profile_block(
    filesystem_entries: dict[str, str],
    unix_sockets: list[Path] | None = None,
) -> str:
    rendered_filesystem_rows: list[str] = []
    for key, value in filesystem_entries.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise ValueError("permission profile filesystem entries must use string keys and values")
        rendered_filesystem_rows.append(f"{toml_string(str(key))} = {toml_string(value)}")

    filesystem_block = "\n".join(rendered_filesystem_rows)
    unix_socket_entries = ""
    if unix_sockets:
        rendered_sockets = ", ".join(f"{toml_string(str(path))} = \"allow\"" for path in unix_sockets)
        unix_socket_entries = f"\nunix_sockets = {{ {rendered_sockets} }}"
    return (
        f"""
[permissions.{PERMISSION_PROFILE}.filesystem]
{filesystem_block}

[permissions.{PERMISSION_PROFILE}.network]
enabled = true
mode = "full"{unix_socket_entries}
""".strip()
        + "\n"
    )
```

- [ ] **Step 2: Replace relative deny rules with absolute deny rules**

Replace `_profile_mode_workspace_deny_rules` with:

```python
def _profile_mode_workspace_deny_rules(workspace_dir: Path) -> dict[str, str]:
    denied_paths = [
        workspace_dir / "buddyswitch" / "skills",
        workspace_dir / "scripts",
        workspace_dir / "tools",
        workspace_dir / "tests",
        workspace_dir / "docs",
        workspace_dir / "buddyswitch" / "objects",
        workspace_dir / "README.md",
        workspace_dir / "buddyswitch-codex",
    ]
    return {str(canonical(str(path))): "none" for path in denied_paths}
```

- [ ] **Step 3: Remove `:project_roots` generation**

In `_build_profile_mode_filesystem`, replace:

```python
filesystem_entries: dict[str, object] = {}
project_roots: dict[str, str] = {".": "read"}
project_roots.update(_profile_mode_workspace_deny_rules(workspace_dir))
filesystem_entries[":project_roots"] = project_roots
filesystem_entries[str(project_workspace_dir)] = (
    "write" if profile.get("project", {}).get("access") == "write" else "read"
)
filesystem_entries["/"] = "read"
filesystem_entries[str(canonical_repo_root)] = "none"
```

with:

```python
filesystem_entries: dict[str, str] = {}
filesystem_entries["/"] = "read"
filesystem_entries[str(canonical_repo_root)] = "none"
filesystem_entries[str(project_workspace_dir)] = (
    "write" if profile.get("project", {}).get("access") == "write" else "read"
)
filesystem_entries.update(_profile_mode_workspace_deny_rules(workspace_dir))
```

- [ ] **Step 4: Update profile filesystem type hints**

Change these type hints from `dict[str, object]` to `dict[str, str]`:

```python
def _build_profile_mode_filesystem(args: argparse.Namespace) -> dict[str, str]:
```

```python
profile_filesystem_entries: dict[str, str] | None = None,
```

```python
profile_filesystem_entries: dict[str, str] | None = None
```

- [ ] **Step 5: Run focused tests**

Run:

```bash
python3 -m pytest tests/test_buddy_env_sandbox.py -q
```

Expected after implementation: PASS.

## Task 3: Update Launcher Integration Assertions

**Files:**

- Modify: `tests/test_buddyswitch_launcher.py`

- [ ] **Step 1: Update `_assert_codex_automation_config`**

Inside the `if profile_mode:` block, replace the `project_roots` assertions with flat filesystem assertions:

```python
self.assertNotIn(":project_roots", filesystem)
for key, value in filesystem.items():
    self.assertIsInstance(value, str, msg=key)
    self.assertNotIn("*", key)
    if key != "/":
        self.assertTrue(Path(key).is_absolute(), msg=key)
self.assertEqual(filesystem["/"], "read")
self.assertEqual(filesystem[repo_root_resolved], "none")
for relative_path in (
    "buddyswitch/skills",
    "scripts",
    "tools",
    "tests",
    "docs",
    "buddyswitch/objects",
    "README.md",
    "buddyswitch-codex",
):
    matching_entries = [
        value
        for key, value in filesystem.items()
        if key.endswith(f"/workspace/{relative_path}")
    ]
    self.assertEqual(matching_entries, ["none"], msg=relative_path)
```

Keep the existing network, temp root, source repo, and shared root assertions.

- [ ] **Step 2: Run launcher tests that exercise config generation**

Run:

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py -q
```

Expected: PASS.

## Task 4: Update Env Layer Boundary Assertions

**Files:**

- Modify: `tests/test_env_layer_boundaries.py`

- [ ] **Step 1: Replace old project-root assertions**

In `test_permission_profile_keeps_dev_project_write_and_runtime_reads`, replace:

```python
project_roots = filesystem[":project_roots"]
self.assertIsInstance(project_roots, dict)
assert isinstance(project_roots, dict)
self.assertIn(str(project_workspace_dir.resolve(strict=False)), writable_paths)
self.assertEqual(project_roots["."], "read")
self.assertEqual(project_roots["buddyswitch/skills/**"], "none")
self.assertEqual(project_roots["tools/**"], "none")
```

with:

```python
self.assertNotIn(":project_roots", filesystem)
for key, value in filesystem.items():
    self.assertIsInstance(value, str, msg=key)
    self.assertNotIn("*", key)
    if key != "/":
        self.assertTrue(Path(key).is_absolute(), msg=key)
self.assertIn(str(project_workspace_dir.resolve(strict=False)), writable_paths)
self.assertEqual(
    filesystem[str((shared_root / "instances" / "inst-dev-boundary" / "workspace" / "buddyswitch" / "skills").resolve(strict=False))],
    "none",
)
self.assertEqual(
    filesystem[str((shared_root / "instances" / "inst-dev-boundary" / "workspace" / "tools").resolve(strict=False))],
    "none",
)
```

- [ ] **Step 2: Run env boundary tests**

Run:

```bash
python3 -m pytest tests/test_env_layer_boundaries.py -q
```

Expected: PASS.

## Task 5: Verify Generated Config Against Codex CLI

**Files:** none

- [ ] **Step 1: Generate a representative pm config**

Run:

```bash
tmpdir="$(mktemp -d)"
workspace="$tmpdir/shared/instances/inst-pm-example/workspace"
python3 tools/launcher/codex_config.py \
  --config "$tmpdir/config.toml" \
  --repo-root "$PWD" \
  --shared-root "$tmpdir/shared" \
  --source-codex-home "$tmpdir/source-codex-home" \
  --buddy pm \
  --instance-root "$tmpdir/shared/instances/inst-pm-example" \
  --workspace-dir "$workspace" \
  --project-workspace-dir "$tmpdir/shared/project/workspace" \
  --home "$tmpdir/shared/instances/inst-pm-example/home" \
  --codex-home "$tmpdir/shared/instances/inst-pm-example/codex-home" \
  --xdg-config-home "$tmpdir/shared/instances/inst-pm-example/xdg-config" \
  --temp-root /tmp
sed -n '1,120p' "$tmpdir/config.toml"
```

Expected generated config:

- contains `[permissions.buddyswitch-runtime.filesystem]`
- does not contain `:project_roots`
- contains absolute `none` entries for `workspace/scripts`, `workspace/tools`, `workspace/tests`, `workspace/docs`, `workspace/buddyswitch/skills`, and `workspace/buddyswitch/objects`

- [ ] **Step 2: Verify Codex sandbox behavior**

Run:

```bash
mkdir -p "$workspace/buddyswitch/skills"
printf 'visible\n' > "$workspace/visible.txt"
printf 'blocked\n' > "$workspace/buddyswitch/skills/secret.txt"
CODEX_HOME="$tmpdir" codex sandbox macos \
  --permissions-profile buddyswitch-runtime \
  --cd "$workspace" \
  /bin/zsh -lc 'cat visible.txt; cat buddyswitch/skills/secret.txt'
```

Expected:

```text
visible
cat: buddyswitch/skills/secret.txt: Operation not permitted
```

The command exit code should be non-zero because the denied read is real.

- [ ] **Step 3: Verify Codex no longer emits filesystem config warnings**

Run:

```bash
CODEX_HOME="$tmpdir" codex exec --skip-git-repo-check "probe" >"$tmpdir/codex.out" 2>&1 || true
rg -n "Configured filesystem path|:project_roots|nested entry" "$tmpdir/codex.out" || true
```

Expected: no matches from `rg`. Authentication or network errors may appear later in the output; they are not part of this config repair.

## Task 6: Full Relevant Verification

**Files:** none

- [ ] **Step 1: Run focused launcher/config tests**

Run:

```bash
python3 -m pytest tests/test_buddy_env_sandbox.py tests/test_env_layer_boundaries.py -q
```

Expected: PASS.

- [ ] **Step 2: Run broader launcher tests**

Run:

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py -q
```

Expected: PASS.

- [ ] **Step 3: Scan for stale unsupported `:project_roots` test expectations**

Run:

```bash
rg -n 'project_roots|":project_roots"|\\[":project_roots"\\]|scripts/\\*\\*|tools/\\*\\*|buddyswitch/skills/\\*\\*' \
  tools tests

rg -n 'project_roots|":project_roots"|\\[":project_roots"\\]|scripts/\\*\\*|tools/\\*\\*|buddyswitch/skills/\\*\\*' \
  docs/spec \
  -g '!docs/spec/2026-05-19-codex-project-roots-config-repair-implementation-plan.md' \
  || true
```

Expected: no matches in `tools` or `tests`. Matches in older `docs/spec` implementation plans are acceptable only when they are historical notes, not current runtime contract guidance.

## Definition of Done

- Generated BuddySwitch product Codex config contains only flat string filesystem entries.
- `:project_roots` is absent from generated runtime permission profiles.
- Runtime deny surfaces are expressed as absolute `none` paths.
- Dev and non-dev project workspace access behavior is unchanged.
- Active buddybox, instance home, Codex home, XDG config, and safe temp write behavior is unchanged.
- Existing source repo checkout remains denied.
- Focused and broader launcher tests pass.
- Codex CLI smoke shows no `Configured filesystem path` warning.

## Remaining Risk

The launcher depends on Codex honoring more-specific absolute path rules over `"/" = "read"`. This was manually verified with `codex sandbox macos` on Codex CLI `0.131.0`; keep the sandbox smoke in this task so the fix proves the actual runtime boundary, not only the generated TOML shape.
