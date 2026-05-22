---
name: hallucination-guard
description: Use when a market deliverable needs a final claim audit for URLs, dates, numbers, wording, and unsupported statements before publication.
---

# hallucination-guard

## Purpose
- Catch unsupported or overconfident claims before they leave the runtime.
- Force cautious wording or block claims that evidence cannot support.

## Use When
- A market artifact is ready for publication and needs final evidence audit.
- You need to check whether URLs, dates, numbers, and claims still match the source.
- You suspect the synthesis may have drifted beyond the evidence.

## Do Not Use When
- The task is still at initial source selection or first-pass note capture.
- The task is only about formatting an artifact without validating claims.

## Inputs
- Draft artifact body, source rows, screenshots, notes, and supporting links.

## Execution Order
1. Before forming external market claims, call `python3 scripts/env/client.py search open-browser --payload '{"query":"<claim wording>","engine":"google"}'`, then continue discovery in `chrome-devtools-cockpit` and keep the workflow browser-native.
2. Re-open every source behind material claims.
3. If a critical source requires login, pause for mandatory takeover.
4. Do not continue with snippet-only or text-only research when browser-native evidence is required.
5. Use runtime discovery for exact payload semantics before durable writes.

## Workflow
1. Audit URLs and confirm each cited page exists and matches the claim.
2. Audit dates so stale pages are not described as current without a qualifier.
3. Audit numbers, units, ranges, and directionality.
4. Audit claim-source mapping so every statement can point to a source row.
5. Rewrite unsupported claims with cautious wording or block them from publication.

## Audit Fields
- URLs
- Dates
- Numbers
- Claim-Source Mapping
- Cautious Wording
- Blocked Claims

## Artifact
- `template`: `brief`
- Required body sections:
  - Draft Claims Reviewed
  - URL Audit
  - Date Audit
  - Number Audit
  - Claim-Source Mapping
  - Rewrites
  - Blocked Claims

## Verification
- Confirm URLs, dates, numbers, and claim-source mapping are audited.
- Confirm unsupported claims are rewritten with cautious wording or block them.
- Confirm the final artifact does not contain invented facts or invented evidence.

## Shared Runtime Rules
- Runtime execution uses env.tool through `python3 scripts/env/client.py ...`.
- Use runtime discovery when exact payload semantics matter.
- Durable market deliverables use `artifact.create_revision` with `template: brief`.
- Market artifact commits require broker-issued `tool_evidence`; do not invent token strings.
- No silent downgrade is allowed from required browser-native evidence.

## Guardrails
- Do not invent evidence, dates, URLs, or numbers.
- Do not let a polished sentence outrun the source record.
- Do not ship unsupported claims.
- Do not silently keep high-confidence wording when the evidence only supports directional language.
