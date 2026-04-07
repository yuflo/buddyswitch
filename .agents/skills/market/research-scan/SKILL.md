# research-scan

name: research-scan
description: Run a focused market research scan and produce a durable report aligned with the market contract.

## Agent

- `market`

## Contract And Template

- Contract: `framework/contracts/market.md`
- Template: `framework/templates/research-report.md`

## Inputs

- Research question or hypothesis.
- Target market and user context.
- Provided sources, links, or prior artifacts.
- Optional output file path.

## Steps

1. Restate the research question and scope in one concise paragraph.
2. Collect evidence only from provided context or explicitly requested sources.
3. Group findings into patterns and insights.
4. Record caveats, uncertainty, and evidence gaps.
5. Write the final report using the research template.

## Output Path

- Default: `artifacts/research/<slug>.md`
- If user provides a path, use it as-is.

## Required Output Fields

- `research_question`
- `evidence`
- `patterns_and_insights`
- `risks_and_caveats`
- `conclusion`

## Guardrails

- Do not write PRD content.
- Do not propose implementation details as if they were validated evidence.
- Do not invent evidence.
