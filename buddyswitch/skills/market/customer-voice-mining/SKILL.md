---
name: customer-voice-mining
description: Use when you need to convert interviews, reviews, support notes, sales notes, or community posts into traceable pain themes and language patterns.
---

# customer-voice-mining

## Purpose
- Turn raw user language into evidence-backed pain themes.
- Keep quotes and paraphrases traceable instead of invented.

## Use When
- You need to summarize what users actually say across multiple evidence sources.
- The task needs pain themes, language patterns, or phrase-level message input.
- You need a voice-of-customer layer before segment or ICP work.

## Do Not Use When
- You only need a source map or search plan before evidence collection.
- You already have a locked segment and only need channel selection.

## Inputs
- Interviews, reviews, support notes, sales notes, community posts, and existing evidence rows.

## Execution Order
1. Before forming external market claims, call `python3 scripts/env/client.py search open-browser --payload '{"query":"<problem phrase> review complaint","engine":"google"}'`, then continue discovery in `chrome-devtools-cockpit` and keep the workflow browser-native.
2. Read upstream artifacts and the original source rows before grouping themes.
3. If a critical source requires login, pause for mandatory takeover.
4. Do not continue with snippet-only or text-only research when browser-native evidence is required.
5. Use runtime discovery for exact payload semantics before durable writes.

## Workflow
1. Pull direct language from interviews, reviews, support notes, sales notes, and community posts.
2. Group the evidence into pain themes, language patterns, triggers, and current alternatives.
3. Keep every quote traceable to a source row, screenshot, or note.
4. Distinguish direct quotes from paraphrase and do not invent quotes.
5. Call out where one segment uses different words for the same pain.

## Artifact
- `template`: `brief`
- Required body sections:
  - Evidence Sources
  - Pain Themes
  - Language Patterns
  - Trigger Moments
  - Current Alternatives
  - Traceable Quotes
  - Gaps And Conflicts

## Verification
- Confirm interviews, reviews, support notes, sales notes, and community posts are represented when relevant.
- Confirm every quote is traceable to a source row.
- Confirm the artifact does not invent quotes or compress conflicting language into one fake consensus.

## Shared Runtime Rules
- Runtime execution uses env.tool through `python3 scripts/env/client.py ...`.
- Use runtime discovery when exact payload semantics matter.
- Durable market deliverables use `artifact.create_revision` with `template: brief`.
- Market artifact commits require broker-issued `tool_evidence`; do not invent token strings.
- No silent downgrade is allowed from required browser-native evidence.

## Guardrails
- Do not invent evidence or quotes.
- Do not flatten segment differences too early.
- Do not treat one vivid quote as representative by itself.
- Do not hide uncertainty about source quality or recency.
