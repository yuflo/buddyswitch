---
name: request-tool
description: Use when creating and managing durable cross-buddy requests on readable tracks through runtime env tools.
---

# Request Tool

## Purpose

Create and manage durable cross-buddy request lifecycle state on readable tracks.

## Runtime Route
- Primary: use native BuddySwitch env MCP tools such as `request__list`, `request__get`, `request__create`, `request__accept`, `request__block`, `request__complete`, and `request__cancel`.
- Exact payload schemas, allowed lifecycle transitions, effects, and response meanings come from native tool schemas and `context.get.tool_catalog['request']`.
- Diagnostic fallback: `python3 scripts/turn_runtime.py status`.
- Broker method remains `env.tool`; do not edit runtime state files directly.

## Workflow Notes

- Use `context__summarize` when you need current runtime-visible ids before request actions.
- Use `request__list` for inbox/outbox scans and status filters.
- Use `request__get` for one exact request row before mutating lifecycle state.
- Recipient uses `request__accept`, `request__block`, and `request__complete`.
- Requester uses `request__cancel`.
- Request creation stays track-scoped; keep target refs and result refs inside request track context.
- Runtime response fields are authoritative for effects, rejection reasons, and recovery.

## Key Boundary Rules

- Request objects are product-readable collaboration state.
- Request lifecycle is separate from private task state.
- Message stays informal text and does not become request status state.
- Only requester, recipient, or PM can read a request.
- Only recipient can accept, block, or complete.
- Only requester can cancel.

## Do Not

- Do not use request actions as a workflow engine or assignment queue.
- Do not move request lifecycle fields into message or task objects.
- Do not reference tracks/artifacts/comments outside the request track context.
