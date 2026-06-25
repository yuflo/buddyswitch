# Built-In Product Interface Principles

Date: 2026-06-25
Status: distilled principle note.

## Core Lesson

A built-in product is not a bundle of interfaces.

The product owns the model, storage, rules, and contracts.

Tools, HTTP routes, CLIs, UI panels, and runtime hooks are only projections of that product.

## Rule

Do not let any interface layer become the place where product semantics live.

If a capability is built into the system, expose it like this:

```text
product core -> interface projection -> consumer surface
```

Not like this:

```text
consumer surface -> scattered helpers -> incidental product
```

## Boundary Test

A developer should be able to answer:

```text
Where is the product?
Which interfaces project it?
Which code only adapts it for one consumer?
```

If those answers point to different scattered files, the product has not been built in.
