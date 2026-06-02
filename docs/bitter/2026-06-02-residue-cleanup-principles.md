# Residue Cleanup Principles

Date: 2026-06-02
Status: distilled principle note.

## Core Lesson

A semantic change is unfinished while any live surface still teaches the old semantics.

Live surface means anything a user, agent, test, or runtime discovery path can consume now.

Old memos and commit history are evidence, not cleanup targets.

## Rule

For a semantic replacement, require two proofs:

- behavior tests for what the system does;
- surface tests or scoped scans for what the system teaches.

Neither proof substitutes for the other.

## Cleanup Loop

1. Define the old terms and the new terms.
2. Add behavior coverage for the boundary.
3. Add a scoped residue check over only live surfaces.
4. Watch the check fail.
5. Fix all live surfaces in the same task.
6. Run exact no-hit scans.
7. Treat any remaining hit as either valid current semantics or unfinished work.

## Scan Discipline

A good scan is narrow.

It names exact surfaces and exact stale phrases.

It does not search the whole repo for common words.

It does not fail historical notes.

## General Principle

Do not store project memory in cleanup memos.

Encode durable lessons in short principles and durable product constraints in tests.
