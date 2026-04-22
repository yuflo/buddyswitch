# Page Schemas

## Shared Header
- Page title.
- Last refreshed timestamp.
- Canonical source list.

## Section Budgets
- Keep sections concise and maintenance-focused.
- Prefer deterministic tables or bullet lists.

## Required Top-Level Headings
- `docs/llm-wiki/README.md`: `# LLM Wiki`, `## Canonical Sources`, `## Architecture Map`, `## Update Workflow`
- `docs/llm-wiki/recent-important-changes.md`: `# Recent Important Changes`, `## Change Entries`
- `docs/llm-wiki/verification-map.md`: `# Verification Map`, `## Verification Entries`

## README Schema
- Purpose.
- Canonical sources.
- Main architecture map.
- Update workflow.

## Recent Important Changes Schema
- Rolling window scope.
- Date ordered change entries.
- Impact and verification link for each entry.

## Verification Map Schema
- Canonical claim.
- Verification command.
- Expected evidence location.

## Rolling Window Rules
- Keep only entries within configured day window.
- Respect configured max entry count.
