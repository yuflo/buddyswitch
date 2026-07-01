---
name: market-search-operator-builder
description: Use when you need a reproducible browser-native query plan for discovery, validation, negative evidence, source-specific, or freshness checks.
---

# market-search-operator-builder

## Purpose
- Turn a market question into a reproducible query set instead of ad hoc browsing.
- Tie every query to a source family and a reason for running it.

## Use When
- The task needs a query plan before market browsing starts.
- You need source-specific search paths, negative evidence checks, or freshness checks.
- You need a reusable query log for another artifact.

## Do Not Use When
- The main need is scoring source quality after evidence is already collected.
- The task is only about writing a final message map or experiment spec from finished evidence.

## Inputs
- Market question, product hypothesis, segment guess, named competitors, geography, and time window.
- Source-family guidance from `market-source-seed-atlas`.

## Execution Order
1. Before forming external market claims, use `chrome-devtools-cockpit` to open, list, select, and inspect browser pages. Use `search__open_browser` only as a query-to-URL wrapper when the task specifically starts from a search query.
2. Read upstream artifacts and the source atlas before creating queries.
3. If a critical source requires login, pause for mandatory takeover.
4. Do not continue with snippet-only or text-only research when browser-native evidence is required.
5. Use runtime discovery for exact payload semantics before durable writes.

## Workflow
1. Start with discovery queries that explore pain language, alternatives, and source families.
2. Add validation queries that check whether the same claim appears across multiple sources.
3. Add negative evidence queries that look for failure cases, low adoption, or missing proof.
4. Add source-specific queries for review sites, communities, competitor docs, and ecosystem surfaces.
5. Add freshness checks so old threads or stale comparisons do not drive current decisions.
6. Write a query log with the query string, source family, purpose, and what result would count as useful evidence.
7. Prefer primary source and user-language sources before vendor summaries, and never close on a snippet-only conclusion.

## Query Set Shape
- discovery queries
- validation queries
- negative evidence queries
- source-specific queries
- freshness checks

## Query Log Fields
- Query
- Source Family
- Why This Query Exists
- Expected Evidence
- What Would Count As Negative Evidence
- Follow-up Query

## Artifact
- `template`: `brief`
- Required body sections:
  - Research Goal
  - Query Log
  - Discovery Queries
  - Validation Queries
  - Negative Evidence
  - Source-Specific Paths
  - Freshness Checks
  - Query Rationale

## Verification
- Confirm every query has a reason, a source family, and a follow-up path.
- Confirm the plan uses source-family intent from `market-source-seed-atlas`.
- Confirm primary source and user-language coverage appears before vendor summary coverage.
- Confirm no conclusion depends on snippets alone.

## Shared Runtime Rules
- Runtime execution uses native BuddySwitch env MCP tools through env.tool; use runtime discovery when exact schemas matter.
- Use runtime discovery when exact payload semantics matter.
- Durable market deliverables use `artifact.create_revision` with `template: brief`.
- Market artifact commits require broker-issued `tool_evidence`; do not invent token strings.
- No silent downgrade is allowed from required browser-native evidence.

## Guardrails
- Do not invent evidence or fabricate query results.
- Do not stop at search snippets.
- Do not skip negative evidence just because early signal looks promising.
- Do not use vendor summaries as the first or only evidence layer.
