# Repo Config

## Required Fields
- `version`
- `wiki_root`
- `recent_change_window_days`
- `recent_change_max_entries`
- `canonical_sources`
- `maintained_files`

## Optional Fields
- `owner`
- `notes`

## Defaults
- No implicit defaults for required fields.
- Optional fields default to empty.

## Bootstrap and Preconditions
- `.llm-wiki.toml` may be absent only for first-run `wiki-init`, which may create it.
- `wiki-refresh` and `wiki-lint` require `.llm-wiki.toml` to already exist.

## Conflict Policy
- The scaffold policy is fixed to `block_on_canonical_conflict`.
- Do not introduce additional conflict-policy options in Task 1.

## Conflict Semantics
- If derived wiki content conflicts with canonical source content, stop and report.

## Promotion Semantics
- Wiki content is informational only.
- Canonical docs remain source of truth.
