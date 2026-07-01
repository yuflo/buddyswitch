---
name: workaround-miner
description: Use when you need to find behavior-linked demand in ugly workarounds, stitched workflows, or manual operations that users already maintain.
---

# workaround-miner

## Purpose
- Extract demand signals from what people already do, not just what they say.
- Turn workaround evidence into a structured validation artifact.

## Use When
- Users mention spreadsheets, scripts, or manual processes.
- You need stronger behavior-linked demand than generic praise.
- The task needs switching implications or operational pain clues.

## Do Not Use When
- The only evidence available is polished marketing copy or abstract trend commentary.
- You already have a locked experiment and only need messaging edits.

## Inputs
- Threads, reviews, interviews, docs, screenshots, notes, and examples of current workflows.

## Execution Order
1. Before forming external market claims, use `chrome-devtools-cockpit` to open, list, select, and inspect browser pages. Use `search__open_browser` only as a query-to-URL wrapper when the task specifically starts from a search query.
2. Read upstream artifacts and source evidence before labeling the workaround.
3. If a critical source requires login, pause for mandatory takeover.
4. Do not continue with snippet-only or text-only research when browser-native evidence is required.
5. Use runtime discovery for exact payload semantics before durable writes.

## Workflow
1. Look for spreadsheets, scripts, Zapier chains, Notion or Airtable boards, manual services, internal tools, stitched-together products, and repeated copy-paste processes.
2. Extract the current workaround, trigger moment, cost, owner, frequency, failure mode, and switching implication.
3. Explain why the behavior is interesting and what hidden demand it may imply.
4. Add alternative explanations, expansion queries, and one validation probe.
5. Mark the confidence as spark, pattern, or commitment.

## Artifact
- `template`: `brief`
- Required body sections:
  - Micro Signal
  - Why It Is Interesting
  - Possible Hidden Demand
  - Alternative Explanations
  - Expansion Queries
  - Validation Probe
  - Confidence
  - Current Workaround
  - Trigger Moment
  - Cost
  - Owner
  - Frequency
  - Failure Mode
  - Switching Implication
- Use one of: spark, pattern, commitment.

## Verification
- Confirm the workaround is tied to a real source row.
- Confirm the extracted fields include current workaround, trigger moment, cost, owner, frequency, failure mode, and switching implication.
- Confirm the note says workaround evidence is stronger than praise but still not enough for willingness to pay without commitment evidence.

## Shared Runtime Rules
- Runtime execution uses native BuddySwitch env MCP tools through env.tool; use runtime discovery when exact schemas matter.
- Use runtime discovery when exact payload semantics matter.
- Durable market deliverables use `artifact.create_revision` with `template: brief`.
- Market artifact commits require broker-issued `tool_evidence`; do not invent token strings.
- No silent downgrade is allowed from required browser-native evidence.

## Guardrails
- Do not invent evidence or unsupported workflow detail.
- Do not generalize one anecdote into broad demand.
- Do not treat likes, upvotes, or generic praise as commitment.
- Do not hide uncertainty.
- Do not turn hunches into facts.
- Do not infer willingness to pay without commitment evidence.
- Always propose the next validation probe.
