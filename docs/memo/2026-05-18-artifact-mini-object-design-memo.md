# Artifact Lightweight Collaboration Page Design Memo

Date: 2026-05-18
Worktree: `/Users/chen/Dev/buddyswitch/.worktrees/fea_artifact_2342`
Branch: `fea_artifact_2342`

Status: discussion memo only. This is not an implementation plan and not a final product spec.

## Purpose

This memo replaces the earlier artifact mini-object direction.

The previous direction over-abstracted artifacts into task-type artifact kinds such as
`insight-brief`, `scope-brief`, `solution-spec`, and `verification-proof`. That was too close to a
programmatic object taxonomy. It also under-specified the collaboration mechanism that makes an
artifact useful across buddies.

The revised direction is:

```text
Artifact = a lightweight collaborative content page published to a track.
```

An artifact is not primarily a buddy output type. It is not a schema-heavy data object. It is not a
design file, asset store, workflow record, or generalized knowledge base page.

An artifact is the place where a track's current shared content becomes readable, discussable,
revisable, and durable enough for another buddy to continue the work.

## Product Borrowing

The design borrows from successful collaboration products without copying their full systems:

- Notion: content pages are flexible containers; structure helps reading, but the page remains the
  primary unit.
- Slack Canvas: a channel or work context can have a shared content surface that teammates discuss
  and update.
- Google Docs / Coda: comments are collaboration state around content; they should not be mixed
  into the document body as the document's current truth.
- Microsoft Loop: a small collaborative content object can be reused in a workflow while keeping a
  current version.

BuddySwitch should take the product lesson:

```text
content container first, embedded collaboration second, hard structure only when proven necessary.
```

BuddySwitch should not take on the platform scope of Notion, Coda, Figma, Docs, or Loop.

## Core Definition

An artifact is a track-published Markdown content page.

It exists to answer:

```text
What does the next buddy need to read to understand the current shared conclusion and next useful
action on this track?
```

The practical quality test is:

```text
A new buddy can read the current artifact body and know what matters, what changed, and what to do
next without chasing private tasks, messages, raw logs, or external design files.
```

External links may exist as provenance, but they must not be the only way to understand the
artifact.

## Object Responsibilities

The collaboration model should stay sharp:

```text
Track    = collaboration site: goal, progress, current shared materials
Artifact = published lightweight content page on a track
Comment  = discussion, feedback, questions, and resolution around a track or artifact
Task     = active-buddy private execution management
Message  = temporary buddy-to-buddy coordination
```

Important consequences:

- Track is the shared collaboration surface.
- Artifact is a current readable content page on that surface.
- Comment is discussion around content, not the content itself.
- Task is not the visibility bridge for artifacts.
- Message is not durable product truth.

The default shared-material path should be direct:

```text
track -> current published artifacts
```

Avoid reintroducing:

```text
track -> task -> artifact
```

as the conceptual read path for collaboration.

## Artifact Shape

The V1 artifact should use a small envelope and a readable body:

```text
artifact
- id
- title
- summary
- body: Markdown
- template: optional soft usage label
- status: draft | published | archived
- published_to_track
- revision
- is_current
- supersedes_artifact_id
- created_by
- authors
- created_at
- updated_at
```

The body is the artifact's current content. It should be written for a human-like buddy reader, not
for a business-rule engine.

Recommended body style:

```markdown
## Context

## Current Conclusion

## Important Details

## Open Questions

## Next
```

Actual templates may suggest different headings, but the runtime should not deeply validate body
sections in V1.

## Template Semantics

`template` identifies the artifact's collaboration use case.

It means:

```text
What role is this content page playing in the track right now?
```

It is primarily for cross-buddy understanding and writing guidance.

It should help:

- the author start with useful headings;
- the reader quickly understand the page's purpose;
- the track view show clear labels for shared materials;
- a buddy decide what kind of content to look for next.

It should not:

- decide permissions;
- decide visibility;
- decide whether comments are allowed;
- force a body schema;
- drive workflow automation;
- become one artifact type per buddy or skill.

Hard collaboration rules should come from:

```text
status
published_to_track
is_current
revision
created_by / write authority
comment status
```

not from `template`.

Candidate V1 templates:

```text
brief    = background, discovery, scope, context, or synthesized information
proposal = recommended product, design, technical, or operational approach
design   = lightweight design description
decision = durable decision and reason
proof    = verification result or evidence-backed judgment
note     = other shared content worth publishing to the track
```

This set is deliberately small. The goal is not to classify every possible work product. The goal is
to make shared content readable across buddies.

## Comments

Comments should remain separate collaboration objects.

Do not store comment text inside the artifact body. If comments are embedded into the body, every
discussion becomes a content edit, and revision history stops distinguishing between "the artifact
changed" and "people discussed the artifact."

Recommended comment model:

```text
comment_thread
- id
- target_type: track | artifact | artifact_section
- target_id
- artifact_revision_id: optional
- anchor: optional section heading or stable section id
- content
- by_buddy
- mentions: optional buddy ids
- status: open | resolved
- reply_to: optional
- created_at
- updated_at
```

Artifact reads may include related comment summaries, but the source of truth remains separate:

```text
artifact body = current content
comment thread = unresolved or resolved discussion around content
revision = accepted content change
```

Useful derived fields can be shown on artifact summaries:

```text
open_comment_count
resolved_comment_count
last_discussed_at
```

These are view helpers, not artifact body content.

## Collaboration Lifecycle

The clean lifecycle is:

```text
draft
  -> publish to track
  -> comment / mention / discuss
  -> resolve comments or capture decision
  -> create new revision when the content conclusion changes
  -> new revision becomes current
```

Rules:

- Only published artifacts appear in track shared materials.
- Track shared materials show current artifacts by default.
- Comments do not automatically become facts.
- If discussion changes the shared conclusion, create a new artifact revision or publish a decision
  artifact.
- Old revisions remain traceable but do not clutter the default track view.
- Archived artifacts are not active collaboration material.

The intended collaboration loop:

```text
PM publishes a scope brief artifact.
Design comments on an unclear state.
PM resolves the discussion by creating a revised current artifact.
Design publishes a lightweight design artifact.
Dev reads current artifacts and implements.
Test publishes a proof artifact.
PM closes or redirects the track based on current artifacts and comments.
```

## Lightweight Design Only

V1 supports only lightweight design artifacts.

Do not introduce design-file hosting, artifact-local media, Figma replacement behavior, reusable
asset objects, or a design material registry.

A lightweight design artifact is a Markdown page that describes enough design intent for Dev, Test,
or PM to continue.

Suggested `design` template:

```markdown
## Goal

## User Flow

## Layout

## States

## Interaction

## Copy

## Acceptance

## Open Questions
```

Good fit:

- page structure;
- user flow;
- low-fidelity layout explanation;
- state and interaction rules;
- copy;
- implementation-facing constraints;
- acceptance criteria for Dev and Test.

Not in V1:

- high-fidelity visual design;
- complex multi-screen prototypes;
- editable Figma source;
- screenshots or embedded media as artifact-owned content;
- reusable design assets;
- design token or component library management.

If a design task truly needs Figma or another external tool, the artifact may include a link as
provenance. The artifact body must still summarize the current design conclusion clearly enough
that another buddy can continue without opening the external source first.

The rule is:

```text
External design source is provenance, not the artifact's required reading path.
```

## Buddy Usage Map

Artifacts are not "buddy homework." They should be used when content becomes shared track material.

### Market

Use artifacts when market work changes product understanding or direction.

Typical cases:

- user feedback synthesis;
- competitor or positioning finding;
- channel or launch signal that affects product judgment;
- recommendation about a segment, problem, or go-to-market direction.

Common templates:

```text
brief
proposal
decision
```

Examples:

```text
User feedback synthesis -> brief
Competitor positioning judgment -> brief
Recommended market direction -> proposal
Decision to avoid a segment -> decision
```

### PM

Use artifacts when defining or changing shared product direction.

Typical cases:

- current track problem and outcome;
- scope, non-goals, and acceptance;
- product behavior decisions;
- tradeoff explanation for Design, Dev, or Test.

Common templates:

```text
brief
proposal
decision
```

Examples:

```text
Track scope and acceptance -> brief
Product behavior proposal -> proposal
Durable product tradeoff -> decision
```

### Design

Use artifacts for lightweight design conclusions that another buddy must read.

Typical cases:

- page structure;
- user flow;
- state and interaction behavior;
- copy direction;
- acceptance points for implementation and verification.

Common templates:

```text
design
proposal
decision
```

Examples:

```text
Settings page interaction rules -> design
Empty-state layout and copy -> design
Recommended UX flow change -> proposal
Finalized interaction tradeoff -> decision
```

### Dev

Use artifacts when technical work produces shared conclusions or proof, not for private work logs.

Typical cases:

- technical approach that other buddies need to understand;
- data, API, or runtime constraint;
- implementation result that changes the product path;
- focused verification evidence.

Common templates:

```text
proposal
brief
proof
decision
```

Examples:

```text
Technical implementation approach -> proposal
Runtime or API constraint -> brief
Build/test result -> proof
Architecture tradeoff that affects future work -> decision
```

### Test

Use artifacts when validation results or failure patterns need to become shared track material.

Typical cases:

- verification scope and result;
- pass/fail judgment;
- failure pattern synthesis;
- remaining risk before close or next iteration.

Common templates:

```text
proof
brief
decision
```

Examples:

```text
Regression result -> proof
Failure pattern summary -> brief
Release/block judgment -> proof
Decision that track can close -> decision
```

### Any Buddy

Any buddy may publish an artifact when:

- a message or comment has become stable shared content;
- a decision must be remembered across future work;
- a private task result now affects the track;
- another buddy needs durable context to continue.

Boundary rule:

```text
Message solves immediate coordination.
Comment solves feedback and discussion.
Task solves private execution.
Artifact solves durable shared track content.
```

## What Not To Build In V1

Do not build:

- asset objects;
- material registries;
- attachment lifecycle;
- artifact-local media;
- Notion-style block trees;
- Figma or design-file replacement behavior;
- per-template body schemas;
- one artifact kind per buddy;
- one artifact kind per skill;
- workflow engines driven by template;
- permissions driven by template;
- artifact visibility through private task chains;
- long-lived dual paths between old task-bound artifacts and new track-published artifacts.

These may become future work only after repeated real use proves the need.

## V1 Recommendation

Proceed with this product direction:

```text
Artifact V1 = track-published Markdown content page.
Collaboration = independent comments + resolved threads + revisions.
Design support = lightweight design text only.
Template = soft use-case label for writing and reading, not rule processing.
Track shared materials = current published artifacts.
```

This is the smallest design that preserves the useful product lesson from Notion, Slack Canvas,
Google Docs, Coda, and Loop: collaboration works best when shared content is a readable object with
discussion and revision around it.

It avoids turning BuddySwitch into a content platform, asset system, design tool, or schema-heavy
workflow engine.

## Open Implementation Questions

These questions should be resolved in a later implementation plan, not in this memo:

1. Should the runtime keep the field name `kind` for compatibility while exposing product language
   as `template`?
2. Should `body` be stored directly as `artifact.body`, or remain under the current
   `artifact.content.body` contract during the transition?
3. What is the minimal comment anchor model: whole artifact only, heading text, or stable section id?
4. How should track shared materials publish artifacts directly without depending on private task
   ownership?
5. What focused tests should prove current-artifact visibility, comment separation, and revision
   behavior?

## References

- Notion block/page model:
  https://www.notion.com/help/guides/block-basics-build-the-foundation-for-your-teams-pages
- Notion databases as page-backed structured content:
  https://www.notion.com/en-gb/help/intro-to-databases
- Slack Canvas:
  https://slack.com/help/articles/203950418-Use-a-canvas-in-Slack
- Google Docs comments and action items:
  https://support.google.com/docs/answer/65129/use-comments-and-action-items-computer
- Coda comments:
  https://help.coda.io/en/articles/6810088-comment-on-coda-docs
- Microsoft Loop components:
  https://support.microsoft.com/en-gb/office/get-to-know-loop-components-fc574b2a-ead0-4d7e-bb56-94dd6469ebcf
