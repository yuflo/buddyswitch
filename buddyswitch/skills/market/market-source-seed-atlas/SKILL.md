---
name: market-source-seed-atlas
description: Use when you need a source-family map, named seed sites, and claim limits before startup market research or GTM evidence collection.
---

# market-source-seed-atlas

## Purpose
- Give Market Role a reusable source atlas before search starts.
- Prevent overclaiming by pairing each source family with allowed claims and forbidden overclaims.

## Use When
- You are starting market discovery and need to choose high-signal sources first.
- You need named seed sites, query operators, access constraints, and evidence caveats.
- You need to explain what each source can validate and what it cannot.

## Do Not Use When
- You already have enough source evidence and only need claim scoring or synthesis.
- The task is purely product scoping, implementation, or design execution.

## Inputs
- Product category, segment guess, market question, geography, and time window.
- Any existing evidence rows or competitor names.

## Execution Order
1. Before forming external market claims, use `chrome-devtools-cockpit` to open, list, select, and inspect browser pages. Use `chrome-devtools-cockpit.search_page` for browser-native search page opening when starting from a query, then continue with cockpit evidence. Use `search__request` only for URL planning without opening and `search__status` for capability status.
2. Read upstream artifacts and source evidence before adding new claims.
3. If a critical source requires login, pause for mandatory takeover.
4. Do not continue with snippet-only or text-only research when browser-native evidence is required.
5. Use runtime discovery for exact payload semantics before durable writes.

## Workflow
1. Pick the minimum source mix: one user-language communities source, one review and comparison source, and one official and competitor source.
2. Add source-family intent, named seeds, best for, bad for, query operators, access constraints, allowed claims, and forbidden overclaims.
3. Mark which seeds can only support weak signals, which can support demand validation, and which are only supporting context.
4. Flag login gates, rate limits, or account-only surfaces before the rest of the research plan is written.

## Source Families

### user-language communities
- Seeds: reddit, x.com, hacker news, github issues.
- Best for: raw pain language, workarounds, repeated complaints, emotionally charged phrasing, edge-user friction, small strange clues.
- Bad for: direct market size claims, TAM math, broad adoption estimates.
- Query operators: `site:reddit.com`, `site:x.com`, `site:news.ycombinator.com`, `site:github.com/issues`.
- Access constraints: rate limits, modals, logged-in threads, takeover when critical.
- Allowed claims: user language, weak signals, workaround patterns, niche adoption friction.
- Forbidden overclaims: reddit and x can support user language and weak signals, not market size.

### review and comparison
- Seeds: g2, capterra, product hunt, chrome web store.
- Best for: dissatisfaction with alternatives, implementation pain, pricing friction, review themes, category comparison.
- Bad for: market size, total demand, willingness to pay without other commitment evidence.
- Query operators: `site:g2.com`, `site:capterra.com`, `site:producthunt.com`, `site:chromewebstore.google.com`.
- Access constraints: some deeper comment areas or sorting views may need login.
- Allowed claims: review volume, complaints, role-specific friction, alternative comparisons.
- Forbidden overclaims: review volume is not TAM and review volume is not market size.

### official and competitor
- Seeds: competitor pricing, competitor docs, competitor changelog, competitor careers.
- Best for: pricing anchors, scope reality, packaging, roadmap hints, positioning, operational complexity.
- Bad for: direct proof of pain, user demand, or satisfaction.
- Query operators: `site:<competitor-domain> pricing`, `site:<competitor-domain> docs`, `site:<competitor-domain> changelog`, `site:<competitor-domain> careers`.
- Access constraints: mostly public, but some docs or release notes may sit behind login.
- Allowed claims: category language, packaging assumptions, capability direction, onboarding depth.
- Forbidden overclaims: competitor homepage claims are not user pain evidence and homepage claims are not market size.

### search and content demand
- Seeds: google trends, competitor blogs, SEO category pages.
- Best for: normalized search interest, topic timing, adjacent questions, freshness checks.
- Bad for: absolute demand, revenue, or conversion assumptions.
- Query operators: quoted problem phrases, `intitle:`, `site:`, freshness filters, comparison modifiers.
- Access constraints: public, but trends are relative and not raw volume.
- Allowed claims: directional search movement and topic clustering.
- Forbidden overclaims: google trends is normalized search interest, not absolute demand.

### ad and distribution
- Seeds: meta ads library, google ads transparency.
- Best for: message tests already in market, positioning angles, active category spend hints.
- Bad for: unit economics, channel effectiveness, or buyer conversion proof.
- Query operators: brand names, competitor names, value-claim phrases, geography filters.
- Access constraints: public with uneven coverage and time windows.
- Allowed claims: active messaging surfaces and distribution experiments.
- Forbidden overclaims: ads presence is not proof of traction or efficient CAC.

### b2b structural
- Seeds: sec edgar, census, job posts, patents.
- Best for: company shape, budget context, hiring direction, regulatory exposure, industry concentration.
- Bad for: immediate buyer intent or product demand confirmation.
- Query operators: `site:sec.gov`, NAICS keywords, role titles, `patent`, `hiring`, `careers`.
- Access constraints: public, but interpretation requires caution and recency checks.
- Allowed claims: capability building, segment size context, organizational maturity hints.
- Forbidden overclaims: job posts and patents imply capability building, not confirmed product intent and not confirmed product intent.

### developer ecosystem
- Seeds: github issues, package registries, extension stores, docs changelogs.
- Best for: integration pain, feature requests, setup friction, adoption blockers, internal tool clues.
- Bad for: broad consumer demand or non-technical segment size.
- Query operators: `site:github.com/issues`, package names, plugin names, error phrases.
- Access constraints: public for many repos, but some enterprise communities require login.
- Allowed claims: technical workflow pain, demand for integrations, workaround evidence.
- Forbidden overclaims: issue count alone is not demand size or willingness to pay.

## Artifact
- `template`: `brief`
- Required body sections:
  - Source Family
  - Seed Site
  - Best For
  - Bad For
  - Query Operators
  - Access Constraints
  - Allowed Claims
  - Forbidden Overclaims
  - First Queries

## Verification
- Confirm every included seed maps to a real claim type and a real overclaim caveat.
- Confirm the atlas includes reddit, x.com, hacker news, github issues, g2, capterra, product hunt, chrome web store, google trends, meta ads library, google ads transparency, sec edgar, census, job posts, competitor pricing, competitor docs, competitor changelog, and competitor careers.
- Confirm no source family is presented as enough for market size by itself.

## Shared Runtime Rules
- Runtime execution uses native BuddySwitch env MCP tools through env.tool; use runtime discovery when exact schemas matter.
- Use runtime discovery when exact payload semantics matter.
- Durable market deliverables use `artifact.create_revision` with `template: brief`.
- Market artifact commits require broker-issued `tool_evidence`; do not invent token strings.
- No silent downgrade is allowed from required browser-native evidence.

## Guardrails
- Do not invent evidence or unsupported source capabilities.
- Do not treat snippets or AI summaries as final proof.
- Do not pretend review volume, homepage claims, or normalized search interest are enough for broad demand claims.
- Do not continue past critical login gates without takeover.
