---
name: write-prd
description: Use when the task is producing PM product definition outputs such as product brief, direction, scope, requirements, acceptance criteria, or PM decisions.
---

# write-prd

## Purpose
- Produce durable PM product-definition outputs that guide downstream design/dev/test collaboration.

## Use when
- The task is drafting product brief/PRD/direction/scope/requirements/acceptance criteria.
- The task needs PM decisions captured as shared collaboration material or close proof.

## Do Not Use When
- The task is pure track lifecycle admin without product-definition content.
- The main outcome is direct implementation, design execution, market research collection, or test execution.

## Workflow
1. Read current collaboration context with `track.open` and `artifact.get` when ids are available.
2. Draft PM content in markdown body using:
   - `template="brief"` for product brief/direction/scope output
   - `template="decision"` for PM decision output
3. Create a private draft/revision artifact via `artifact.create_revision`.
4. Publish with exactly one track action:
   - `track.add_material` for shared current material
   - `track.add_proof` for close proof
5. Verify publication with `track.open` and `artifact.get`.

## Verification
- Confirm publish/create responses include `state_changes`.
- Confirm `track.open.shared_materials` or `track.open.close_proof` contains the expected `artifact_id`.
- Confirm `artifact.get` returns the expected full markdown body.
- Keep durable writes inside env.tool (`python3 scripts/env/client.py ...`) only.

## Shared Runtime Rules
- `artifact.create_revision` creates private draft/revision artifacts only.
- Shared publication happens via `track.add_material` or `track.add_proof`.
- Start with `python3 scripts/env/client.py context summarize --payload '{}'`, then use `python3 scripts/env/client.py context get --payload '{}'` when exact payload keys or response fields are unclear.
- Do not edit projected runtime object storage directly.
- Use buddybox `logical_name` only for active-buddy-private working files.

## Examples
- `Draft landing-page product brief with acceptance criteria`
- `Publish PM decision about scope tradeoff`
- `Revise current PM brief and republish as latest shared material`
