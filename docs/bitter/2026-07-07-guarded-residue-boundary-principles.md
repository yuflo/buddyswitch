# Guarded Residue Boundary Principles

Date: 2026-07-07
Status: bitter lesson from rebuild boundary review.

## Core Lesson

A guard against retired structure inside a trusted live path is usually not safety.

It is evidence that the boundary still accepts the wrong shape.

## Failure Pattern

```text
replace old semantics
  -> keep accepting loose internal objects
  -> add a blacklist for known retired shapes
  -> tests prove the blacklist
  -> the boundary still allows future residue
```

This is not rebuilt-forward development.

It is compatibility pressure disguised as safety.

## Rule

External ingress validates untrusted input.

Internal product boundaries define the current contract.

Do not make active runtime code remember retired schemas unless there is a real migration,
external API, or explicit rollback requirement.

Prefer exact schema construction, allowlisted fields, and failing tests over retired-structure
runtime blacklists.

## General Principle

A clean rebuild removes the old shape from the live path.

If the old shape must still be named in active code, prove why; otherwise delete the name and
tighten the boundary.
