# Runtime Skill Frontmatter Bugfix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. This is a narrow launcher-startup warning bugfix; do not expand it into launcher, manifest, skill packaging, or runtime-skill architecture work.

**Goal:** Make `message-tool` and `comment-tool` load as valid Codex CLI runtime skills when `buddyswitch-codex instance start --buddy <buddy>` materializes `.agents/skills`.

**Architecture:** Keep the existing launcher and runtime skill materialization path unchanged. `scripts/runtime_skills.py` already copies manifest-declared skill packages byte-for-byte into `.agents/skills`; the fix is to make the two source `SKILL.md` files conform to Codex CLI's required YAML-frontmatter skill format.

**Tech Stack:** Markdown `SKILL.md` files, Codex CLI skill loader, BuddySwitch runtime skill materialization script, shell-based verification in a temporary workspace.

---

## 1. Problem Statement

Starting a BuddySwitch instance currently prints:

```text
Skipped loading 2 skill(s) due to invalid SKILL.md files.
.../.agents/skills/comment-tool/SKILL.md: missing YAML frontmatter delimited by ---
.../.agents/skills/message-tool/SKILL.md: missing YAML frontmatter delimited by ---
```

The installed runtime files are copied from source skill packages, not generated from separate metadata. The source files currently start with Markdown headings:

```text
buddyswitch/skills/shared/message-tool/SKILL.md -> # Message Tool
buddyswitch/skills/shared/comment-tool/SKILL.md -> # Comment Tool
```

Codex CLI expects each loadable `SKILL.md` under `.agents/skills` to start with YAML frontmatter delimited by `---`.

## 2. Scope

### In Scope

- Add YAML frontmatter to `buddyswitch/skills/shared/message-tool/SKILL.md`.
- Add YAML frontmatter to `buddyswitch/skills/shared/comment-tool/SKILL.md`.
- Preserve existing Markdown body content below the inserted frontmatter.
- Verify runtime materialization in a temporary workspace and confirm no materialized `SKILL.md` for the PM buddy is missing frontmatter.

### Out Of Scope

- Do not modify `tools/launcher/workspace.sh`.
- Do not modify `scripts/runtime_skills.py`.
- Do not modify `buddyswitch/manifest.toml`.
- Do not modify tests in this change set.
- Do not add package-level `skill.toml`.
- Do not rewrite skill content, operations, rules, or wording beyond the required frontmatter.
- Do not touch `buddyswitch/objects/**` or `buddyswitch/local/buddybox/**`.

## 3. Files

- Modify: `buddyswitch/skills/shared/message-tool/SKILL.md`
  - Insert YAML frontmatter at the top of the file.
- Modify: `buddyswitch/skills/shared/comment-tool/SKILL.md`
  - Insert YAML frontmatter at the top of the file.

No other files should be modified when executing this plan.

## 4. Target File Content

### `message-tool`

The top of `buddyswitch/skills/shared/message-tool/SKILL.md` must become:

```markdown
---
name: message-tool
description: Use when sending and reading direct buddy-to-buddy inbox messages through runtime env tools.
---

# Message Tool
```

### `comment-tool`

The top of `buddyswitch/skills/shared/comment-tool/SKILL.md` must become:

```markdown
---
name: comment-tool
description: Use when adding and listing comments on readable track and artifact targets through runtime env tools.
---

# Comment Tool
```

## 5. Tasks

### Task 1: Add Frontmatter To `message-tool`

**Files:**

- Modify: `buddyswitch/skills/shared/message-tool/SKILL.md`

- [ ] **Step 1: Insert only the frontmatter block**

Add this block before the existing first line `# Message Tool`:

```markdown
---
name: message-tool
description: Use when sending and reading direct buddy-to-buddy inbox messages through runtime env tools.
---

```

- [ ] **Step 2: Confirm the file starts with the expected lines**

Run:

```bash
sed -n '1,8p' buddyswitch/skills/shared/message-tool/SKILL.md
```

Expected output:

```text
---
name: message-tool
description: Use when sending and reading direct buddy-to-buddy inbox messages through runtime env tools.
---

# Message Tool

## Purpose
```

### Task 2: Add Frontmatter To `comment-tool`

**Files:**

- Modify: `buddyswitch/skills/shared/comment-tool/SKILL.md`

- [ ] **Step 1: Insert only the frontmatter block**

Add this block before the existing first line `# Comment Tool`:

```markdown
---
name: comment-tool
description: Use when adding and listing comments on readable track and artifact targets through runtime env tools.
---

```

- [ ] **Step 2: Confirm the file starts with the expected lines**

Run:

```bash
sed -n '1,8p' buddyswitch/skills/shared/comment-tool/SKILL.md
```

Expected output:

```text
---
name: comment-tool
description: Use when adding and listing comments on readable track and artifact targets through runtime env tools.
---

# Comment Tool

## Purpose
```

### Task 3: Verify Runtime Materialization

**Files:**

- Read: `scripts/runtime_skills.py`
- Read: temporary workspace created by `mktemp -d`

- [ ] **Step 1: Materialize PM runtime skills into a temporary workspace**

Run:

```bash
tmp=$(mktemp -d)
python3 scripts/runtime_skills.py install --buddy pm --workspace "$tmp" >/dev/null
find "$tmp/.agents/skills" -name SKILL.md -type f -print0 | while IFS= read -r -d '' f; do
  first=$(sed -n '1p' "$f")
  if [ "$first" != "---" ]; then
    printf '%s\n' "${f#$tmp/}"
  fi
done | sort
rm -rf "$tmp"
```

Expected output:

```text
```

No paths should print. Any printed path means that materialized skill file is still invalid for Codex CLI frontmatter loading.

- [ ] **Step 2: Confirm the intended diff contains only the two source skill files**

Run:

```bash
git status --short
```

Expected relevant output:

```text
 M buddyswitch/skills/shared/comment-tool/SKILL.md
 M buddyswitch/skills/shared/message-tool/SKILL.md
```

There must be no launcher, manifest, runtime script, object-state, or test-file changes in this fix.

## 6. Definition Of Done

- `message-tool/SKILL.md` starts with YAML frontmatter delimited by `---`.
- `comment-tool/SKILL.md` starts with YAML frontmatter delimited by `---`.
- Existing skill body content remains unchanged below the inserted metadata.
- Temporary runtime materialization for `--buddy pm` prints no `SKILL.md` paths missing frontmatter.
- `git status --short` shows only the two intended `SKILL.md` source files modified during implementation.

## 7. Residual Risk

This plan does not add a durable regression test because the requested implementation scope is intentionally limited to the two broken skill documents. A separate follow-up could add a repository-level validation that all manifest-materialized runtime skills are Codex CLI loadable, but that is outside this narrow fix.
