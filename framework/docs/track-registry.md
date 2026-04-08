# BuddySwitch v1 Track Registry

## Purpose

The Track Registry is the explicit project state for product iteration records.

A Track is not inferred from filenames, agent roles, or artifact folders. A Track exists only when the user explicitly asks to create, continue, promote, register, or associate work with a product iteration.

## Location

- Registry file: `artifacts/workspace-registry.json`
- Registry artifact entries use:
  - `role`: `market`, `pm`, `design`, `dev`, or `test`
  - `type`: `research`, `prd`, `design-spec`, `implementation-report`, or `smoke-test`
  - `path`: repo-relative artifact path

## Trigger Rules

Handle the registry only when the user explicitly mentions one of:
- `track`
- `registry`
- `register`
- `promote`
- `创建 track`
- `登记到 track`
- `推进为产品迭代`

If the user only asks for an artifact, write the artifact and leave it untracked. Optionally suggest a next switch to register it.

## Existing Track Handling

When the user explicitly references an existing Track:
1. Read `artifacts/workspace-registry.json`.
2. Write or update the current agent's artifact.
3. Add or update only the current agent's artifact entry under that Track.
4. Do not remove or rewrite other agents' entries.
5. List the registry change in the final `deliverables or changed files` block.

## Missing Track Handling

If the user asks to register work to a Track ID that does not exist, and does not explicitly ask to create a new Track, stop and ask for clarification. Do not create the Track by guessing.

## New Track Handling

Create a new Track only when the user explicitly asks to create a Track or promote work into a product iteration.

If the user does not provide a `track_id`, derive one from the artifact slug or task title using lowercase kebab-case, set `state` to `active`, and state the derived ID in the response.

## Agent Role Map

- `market`: `type` = `research`
- `pm`: `type` = `prd`
- `design`: `type` = `design-spec`
- `dev`: `type` = `implementation-report`
- `test`: `type` = `smoke-test`

Agents must only register artifacts for their own role.
