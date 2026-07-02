# Memo To Goals

Use this only when a BuddySwitch memo, implementation note, or broad target must be converted into a user effect before choosing the user path.

## Read Order

1. Read the memo title, goal, task restatement, acceptance criteria, and verification notes.
2. Read non-negotiable requirements and out-of-scope sections.
3. Skim file maps only to identify actors, user surfaces, and expected observable effects.

Do not turn file names, helper names, or implementation modules into the goal.

## Extraction Rule

Extract one primary effect unless the memo clearly names multiple independent user promises.

Use this shape:

```text
When <user or actor> does <entry action>, BuddySwitch should <observable effect>,
without <wrong target, stale state, or forbidden residue>.
```

Record only what matters for the user path:

- target effect;
- likely user surface;
- actor/resource that must exist;
- visible/runtime evidence that would prove the effect;
- cleanup proof expected;
- explicit out-of-scope claims.

## Challenge Checks

Reject or downgrade a target when:

- it only names code structure, not a user effect;
- it can be "proved" by unit/static checks without driving a user surface;
- it requires live Codex or signed-in Chrome but the user did not authorize that risk;
- it asks for a broad stability claim without evidence for the named user path;
- existing evidence lacks actor/action/effect/cleanup proof.
