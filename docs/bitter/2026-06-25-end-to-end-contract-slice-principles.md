# End-To-End Contract Slice Principles

Date: 2026-06-25
Status: bitter lesson from IM rebuild gap review.

## Core Lesson

A design is not implemented because every layer has a test.

It is implemented only when the user-visible contract crosses all required layers.

Layer tests can prove components exist while the product path is still broken.

## Failure Pattern

The common drift is:

```text
memo defines end-to-end outcome
  -> plan splits outcome into slices
  -> each slice gets a local test
  -> no test reconnects the slices
  -> completion is claimed with the real user loop missing
```

This is especially dangerous when async systems are involved.

Send, store, wake, process, reply, subscribe, and render can all be "covered" separately while no
human or client can complete the conversation.

## Rule

For every cross-layer capability, write one contract sentence in this shape:

```text
consumer action -> system path -> observable consumer result
```

Then keep at least one acceptance test or smoke script that proves exactly that sentence.

Do not replace it with a list of component responsibilities.

## Slice Checklist

Before marking a sliced plan complete, ask:

1. Which user-visible loop proves the original promise?
2. Which test executes the handoff between slices?
3. Which async callback or polling path proves the result returns to the consumer?
4. Which required negative case would still pass if the real loop were broken?

If the answer is only "unit tests pass", the plan has lost the contract.

## General Principle

Slicing is for implementation order, not for shrinking the definition of done.

Keep the end-to-end promise alive as a first-class test target until the work is actually usable.
