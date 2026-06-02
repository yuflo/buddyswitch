# Wrong-Boundary Narrowness Principles

Date: 2026-06-02
Status: bitter lesson from daemon ingress design review.

## Core Lesson

Small is not enough.

A narrow change can still be wrong when it is narrow at the wrong boundary.

The question is not:

```text
Is this small?
```

The question is:

```text
Is this small at the boundary that should remain stable?
```

## Failure Pattern

This is the common trap:

```text
avoid overbuilt generic framework
  -> add one narrow special case
  -> repeat for each new need
  -> shared surface becomes a hidden registry
```

The first special case feels clean because it is typed, concrete, and easy to test.

The architecture becomes wrong when future work must keep adding siblings to the same shared
technical surface.

## Boundary Test

Before adding a narrow special case to shared infrastructure, ask:

1. Is this a new stable source/protocol, or only a new business event?
2. Will unrelated future features need to add similar siblings here?
3. Can the shared layer validate source/shape while the owning module handles semantics?
4. Is this reducing the shared surface, or quietly turning it into a router?

If the answer points to repeated siblings, the boundary is wrong.

## Correct Shape

Prefer:

```text
stable ingress
  -> typed payload
  -> owning handler/module
  -> explicit action
```

Over:

```text
shared_method_for_business_case_A
shared_method_for_business_case_B
shared_method_for_business_case_C
```

Do not confuse "not building a framework" with "adding bespoke methods forever."

## Rule

Concrete first does not mean special-case at the shared boundary.

Keep the shared boundary stable and boring. Put business variation behind the owning module.
