---
name: source-quality-rater
description: Use when you need to rate source quality, bias, freshness, and usable claims before market evidence is promoted into conclusions.
---

# source-quality-rater

## Purpose
- Rank whether a source deserves high trust, directional use, or rejection.
- Separate useful evidence from noisy or biased input before synthesis.

## Use When
- You have collected market evidence and need a quality gate.
- A source seems strong but may have freshness, bias, or methodology problems.
- You need a claim-by-claim evidence rating for another market artifact.

## Do Not Use When
- The task is about building the first query set.
- The task is about choosing one experiment without reviewing evidence quality first.

## Inputs
- Source rows, URLs, screenshots, notes, dates, and extracted claims.

## Execution Order
1. Before forming external market claims, call `python3 scripts/env/client.py search open-browser --payload '{"query":"<source title>","engine":"google"}'`, then continue discovery in `chrome-devtools-cockpit` and keep the workflow browser-native.
2. Re-open the original pages for the highest-impact claims.
3. If a critical source requires login, pause for mandatory takeover.
4. Do not continue with snippet-only or text-only research when browser-native evidence is required.
5. Use runtime discovery for exact payload semantics before durable writes.

## Workflow
1. Rate freshness for each source and note whether the date is precise or inferred.
2. Rate bias by source incentives, role, publication context, and promotional pressure.
3. Classify source type such as user-language, review, official page, analyst note, or market report.
4. Check methodology when numbers or market-size claims appear.
5. Mark usable claims, directional claims, and blocked claims.

## Rating Fields
- Freshness
- Bias
- Source Type
- Methodology
- Usable Claims
- Confidence

## Artifact
- `template`: `brief`
- Required body sections:
  - Sources Reviewed
  - Freshness
  - Bias
  - Source Type
  - Methodology
  - Usable Claims
  - Blocked Claims
  - Confidence Notes

## Verification
- Confirm each accepted claim has a source row, date, and claim type.
- Confirm freshness, bias, source type, methodology, and usable claims are explicitly rated.
- Confirm unsupported numbers are blocked from downstream use.

## Shared Runtime Rules
- Runtime execution uses env.tool through `python3 scripts/env/client.py ...`.
- Use runtime discovery when exact payload semantics matter.
- Durable market deliverables use `artifact.create_revision` with `template: brief`.
- Market artifact commits require broker-issued `tool_evidence`; do not invent token strings.
- No silent downgrade is allowed from required browser-native evidence.

## Guardrails
- Do not invent evidence quality that the source did not earn.
- Do not treat official claims as neutral by default.
- Do not hide date ambiguity when freshness is weak.
- Do not pass through numbers with unclear methodology.
