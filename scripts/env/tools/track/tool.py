#!/usr/bin/env python3
"""Black-box protocol entrypoint for env.tools.track."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from env.tool_runtime.context import ToolContext
from env.tool_runtime.definition import ActionDefinition, ToolDefinition, validate_definition

_NOW_SCHEMA = {
    'type': 'object',
    'description': 'Current next step and optional blocker for the track.',
    'additionalProperties': False,
    'required': ['next'],
    'properties': {
        'next': {
            'type': 'string',
            'description': 'Non-empty next action or current focus.',
        },
        'blocker': {
            'type': ['string', 'null'],
            'description': 'Current blocker text, or null when unblocked.',
        },
    },
    'examples': [{'next': 'Set up PM coordination.', 'blocker': None}],
}

_REFS_ITEM_SCHEMA = {
    'type': 'object',
    'description': 'Artifact reference attached to this update row.',
    'additionalProperties': False,
    'required': ['type', 'id'],
    'properties': {
        'type': {
            'type': 'string',
            'description': "Reference type; track updates only accept 'artifact'.",
            'enum': ['artifact'],
        },
        'id': {
            'type': 'string',
            'description': 'Artifact id referenced by this update.',
        },
    },
}


def _build_definition() -> ToolDefinition:
    return ToolDefinition(
        id='track',
        title='Track Pages',
        description='Operate shared progress pages and shared material/proof publication.',
        cli_resource='track',
        command="python3 scripts/env/client.py track <action> --payload '<json-object>'",
        scope='shared track progress pages and publication timeline',
        capability_boundary='Only PM can create/archive tracks; shared mutation requires readable track scope.',
        object_model=(
            'Track pages are shared product outcome threads. A track can cover a feature iteration, decision thread, delivery slice, or other coherent shared outcome; not every feature mention requires a new track. PM owns create/archive lifecycle; shared mutation publishes material, proof, timeline, or now-state on the track.'
        ),
        use_when=(
            'You need to operate shared collaboration on a non-archived track.',
        ),
        do_not_use_when=(
            'You need full artifact body content by id; use artifact.get.',
        ),
        actions=(
            ActionDefinition(
                name='create',
                title='track.create',
                description='Create one PM-owned shared track page.',
                input_schema={
                    'type': 'object',
                    'additionalProperties': False,
                    'required': ['track_id', 'title', 'outcome', 'appetite', 'now'],
                    'properties': {
                        'track_id': {
                            'type': 'string',
                            'description': 'Stable id for the new track.',
                        },
                        'title': {
                            'type': 'string',
                            'description': 'Human-readable track title.',
                        },
                        'outcome': {
                            'type': 'string',
                            'description': 'Desired track outcome.',
                        },
                        'appetite': {
                            'type': 'string',
                            'description': 'Time or scope appetite for the track.',
                        },
                        'now': _NOW_SCHEMA,
                        'state': {
                            'type': 'string',
                            'description': 'Track state.',
                            'enum': ['active', 'blocked', 'review', 'done'],
                        },
                        'health': {
                            'type': 'string',
                            'description': 'Track health.',
                            'enum': ['ok', 'risk', 'blocked', 'stale'],
                        },
                    },
                },
                output_schema={
                    '$ref': 'ToolResult',
                },
                kind='write',
                mutates='runtime_objects',
                required_permission='track.create',
                authority='pm.lifecycle_authority',
                visibility='shared to buddies with track read access',
                durability='durable',
                result_content_level='track page',
                success_effect='Creates one PM-owned shared product outcome thread with initial outcome, appetite, now focus, state, and health.',
                failure_state_guarantee='Rejected writes do not mutate runtime objects; response explains the permission, payload, lifecycle, or visibility boundary.',
                reads=(
                    'env.tool role-action policy',
                    'existing track ids',
                ),
                writes=(
                    'shared track page',
                ),
                does_not_write=(
                    'artifact body',
                    'task state',
                    'request lifecycle',
                    'buddybox files',
                ),
                preconditions=(
                    'active buddy is pm',
                ),
                returns=(
                    'track',
                ),
                use_when=(
                    'You are PM and need to start a new shared track page with initial outcome and now focus.',
                    'No track exists yet for this initiative and collaborators need a canonical shared page.',
                ),
                do_not_use_when=(
                    'You need to read or update an existing track; use track.list/track.open/track.update_now.',
                    'You need to publish artifacts or timeline rows on an existing track; use add_material/add_update/add_proof.',
                ),
                risk_hints={
                    'read_only': False,
                    'destructive': False,
                    'idempotent': False,
                    'open_world': False,
                    'requires_human_approval': False,
                    'external_effect': False,
                },
            ),
            ActionDefinition(
                name='list',
                title='track.list',
                description='List non-archived track page summaries.',
                input_schema={
                    'type': 'object',
                    'additionalProperties': False,
                    'required': [],
                    'properties': {
                        'state': {
                            'type': 'string',
                            'description': 'Optional state filter for non-archived tracks.',
                            'enum': ['active', 'blocked', 'review', 'done'],
                        },
                        'limit': {
                            'type': 'integer',
                            'description': 'Optional max number of rows to return.',
                            'minimum': 1,
                        },
                    },
                },
                output_schema={
                    '$ref': 'ToolResult',
                },
                kind='read',
                mutates='none',
                required_permission='track.read',
                authority='track.lookup',
                visibility='active-buddy readable track summaries',
                durability='none',
                result_content_level='summary rows',
                success_effect='Returns non-archived track summaries for choosing whether to reuse, split, or open a track.',
                failure_state_guarantee='Rejected reads do not mutate runtime state and return no full object body beyond rejection metadata.',
                reads=(
                    'non-archived track summaries',
                ),
                writes=(),
                does_not_write=(
                    'track state',
                    'artifact state',
                    'task state',
                    'request lifecycle',
                    'buddybox files',
                ),
                preconditions=(
                    'active buddy owns track.read permission',
                ),
                returns=(
                    'tracks',
                ),
                use_when=(
                    'You need a summary index of non-archived tracks to choose where to operate.',
                    'You are filtering candidate tracks by state before opening one in detail.',
                ),
                do_not_use_when=(
                    'You already have track_id and need full page details; use track.open.',
                    'You need to mutate track state or publication timeline; use a write track action.',
                ),
                risk_hints={
                    'read_only': True,
                    'destructive': False,
                    'idempotent': True,
                    'open_world': False,
                    'requires_human_approval': False,
                    'external_effect': False,
                },
            ),
            ActionDefinition(
                name='open',
                title='track.open',
                description='Open one non-archived shared track page.',
                input_schema={
                    'type': 'object',
                    'additionalProperties': False,
                    'required': ['track_id'],
                    'properties': {
                        'track_id': {
                            'type': 'string',
                            'description': 'Existing non-archived track id to open.',
                        },
                    },
                },
                output_schema={
                    '$ref': 'ToolResult',
                },
                kind='read',
                mutates='none',
                required_permission='track.read',
                authority='track.lookup',
                visibility='active-buddy readable track page',
                durability='none',
                result_content_level='track page with refs and summaries',
                success_effect='Opens one shared track page with now-state, timeline, material refs, and proof refs; use artifact.get for full artifact bodies.',
                failure_state_guarantee='Rejected reads do not mutate runtime state and return no full object body beyond rejection metadata.',
                reads=(
                    'one non-archived track page',
                ),
                writes=(),
                does_not_write=(
                    'track state',
                    'artifact body',
                    'task state',
                    'request lifecycle',
                    'buddybox files',
                ),
                preconditions=(
                    'track_id references an existing non-archived track',
                ),
                returns=(
                    'track',
                ),
                use_when=(
                    'You need full shared track page details for one known track_id.',
                    'You are reviewing current now/timeline/material/proof before deciding on the next mutation.',
                ),
                do_not_use_when=(
                    'You need to discover candidate track ids first; use track.list.',
                    'You need to change now/state/health or append publications/updates; use write track actions.',
                ),
                risk_hints={
                    'read_only': True,
                    'destructive': False,
                    'idempotent': True,
                    'open_world': False,
                    'requires_human_approval': False,
                    'external_effect': False,
                },
            ),
            ActionDefinition(
                name='update_now',
                title='track.update_now',
                description='Update now/state/health on a shared track page.',
                input_schema={
                    'type': 'object',
                    'additionalProperties': False,
                    'required': ['track_id'],
                    'properties': {
                        'track_id': {
                            'type': 'string',
                            'description': 'Existing non-archived track id to update.',
                        },
                        'now': _NOW_SCHEMA,
                        'state': {
                            'type': 'string',
                            'description': 'Optional track state patch.',
                            'enum': ['active', 'blocked', 'review', 'done'],
                        },
                        'health': {
                            'type': 'string',
                            'description': 'Optional track health patch.',
                            'enum': ['ok', 'risk', 'blocked', 'stale'],
                        },
                    },
                },
                output_schema={
                    '$ref': 'ToolResult',
                },
                kind='write',
                mutates='runtime_objects',
                required_permission='track.update_now',
                authority='track.shared_mutation',
                visibility='shared to buddies with track read access',
                durability='durable',
                result_content_level='track page',
                success_effect='Updates shared track now/state/health and records the change on the track timeline.',
                failure_state_guarantee='Rejected writes do not mutate runtime objects; response explains the permission, payload, lifecycle, or visibility boundary.',
                reads=(
                    'one non-archived track page',
                ),
                writes=(
                    'track now/state/health',
                    'track timeline update row',
                ),
                does_not_write=(
                    'artifact body',
                    'artifact publication slot',
                    'task state',
                    'request lifecycle',
                    'buddybox files',
                ),
                preconditions=(
                    'track_id references an existing non-archived track',
                ),
                returns=(
                    'track',
                ),
                use_when=(
                    'You need to patch track now.next/blocker or state/health without adding timeline rows.',
                    'You are updating execution status (active/blocked/review/done) on the shared page.',
                ),
                do_not_use_when=(
                    'You need a narrative event row in the timeline; use track.add_update.',
                    'You need artifact publication into material/proof slots; use track.add_material or track.add_proof.',
                ),
                risk_hints={
                    'read_only': False,
                    'destructive': False,
                    'idempotent': False,
                    'open_world': False,
                    'requires_human_approval': False,
                    'external_effect': False,
                },
            ),
            ActionDefinition(
                name='add_material',
                title='track.add_material',
                description='Publish one draft artifact as current shared material.',
                input_schema={
                    'type': 'object',
                    'additionalProperties': False,
                    'required': ['track_id', 'artifact_id', 'label', 'summary'],
                    'properties': {
                        'track_id': {
                            'type': 'string',
                            'description': 'Existing non-archived track id to mutate.',
                        },
                        'artifact_id': {
                            'type': 'string',
                            'description': 'Active-buddy-owned draft artifact id to publish.',
                        },
                        'label': {
                            'type': 'string',
                            'description': 'Human label for published material entry.',
                        },
                        'summary': {
                            'type': 'string',
                            'description': 'Summary shown on the published material entry.',
                        },
                    },
                },
                output_schema={
                    '$ref': 'ToolResult',
                },
                kind='write',
                mutates='runtime_objects',
                required_permission='track.add_material',
                authority='track.shared_mutation',
                visibility='shared to buddies with track read access',
                durability='durable',
                result_content_level='track page plus artifact id',
                success_effect='Publishes one draft artifact as current shared material on the track.',
                failure_state_guarantee='Rejected writes do not mutate runtime objects; response explains the permission, payload, lifecycle, or visibility boundary.',
                reads=(
                    'one non-archived track page',
                    'one publishable artifact',
                ),
                writes=(
                    'track shared_materials',
                    'artifact publication metadata',
                ),
                does_not_write=(
                    'task state',
                    'request lifecycle',
                    'buddybox files',
                    'comment threads',
                ),
                preconditions=(
                    'track_id references an existing non-archived track',
                    'artifact_id references an active-buddy-owned draft artifact',
                    'artifact is not already published to another track',
                ),
                returns=(
                    'artifact_id',
                    'track',
                    'state_changes',
                ),
                use_when=(
                    'You need to publish a draft artifact as current shared material on a track.',
                    'The artifact should appear in track materials state (not as a standalone narrative-only update).',
                ),
                do_not_use_when=(
                    'You need a plain timeline note without material publication; use track.add_update.',
                    'You are publishing close proof rather than working material; use track.add_proof.',
                ),
                risk_hints={
                    'read_only': False,
                    'destructive': False,
                    'idempotent': False,
                    'open_world': False,
                    'requires_human_approval': False,
                    'external_effect': False,
                },
            ),
            ActionDefinition(
                name='add_update',
                title='track.add_update',
                description='Append one track timeline update row.',
                input_schema={
                    'type': 'object',
                    'additionalProperties': False,
                    'required': ['track_id', 'summary'],
                    'properties': {
                        'track_id': {
                            'type': 'string',
                            'description': 'Existing non-archived track id to mutate.',
                        },
                        'summary': {
                            'type': 'string',
                            'description': 'Update summary text appended to timeline.',
                        },
                        'kind': {
                            'type': 'string',
                            'description': 'Optional update kind label.',
                            'enum': ['progress', 'decision', 'blocker', 'proof'],
                        },
                        'refs': {
                            'type': 'array',
                            'description': 'Optional artifact refs related to this update.',
                            'items': _REFS_ITEM_SCHEMA,
                            'examples': [[{'type': 'artifact', 'id': 'art-example-r1'}]],
                        },
                    },
                },
                output_schema={
                    '$ref': 'ToolResult',
                },
                kind='write',
                mutates='runtime_objects',
                required_permission='track.add_update',
                authority='track.shared_mutation',
                visibility='shared to buddies with track read access',
                durability='durable',
                result_content_level='timeline update row and track page',
                success_effect='Appends one narrative progress, decision, blocker, or proof-note update to the track timeline.',
                failure_state_guarantee='Rejected writes do not mutate runtime objects; response explains the permission, payload, lifecycle, or visibility boundary.',
                reads=(
                    'one non-archived track page',
                    'optional readable artifact refs',
                ),
                writes=(
                    'track timeline update row',
                ),
                does_not_write=(
                    'artifact body',
                    'artifact publication slot',
                    'task state',
                    'request lifecycle',
                    'buddybox files',
                ),
                preconditions=(
                    'track_id references an existing non-archived track',
                ),
                returns=(
                    'track',
                    'update',
                ),
                use_when=(
                    'You need to append a timeline event (progress/decision/blocker/proof note) to track history.',
                    'You need narrative status communication on the track without publishing a new material/proof artifact.',
                ),
                do_not_use_when=(
                    'You are publishing an artifact into current material/proof slots; use track.add_material or track.add_proof.',
                    'You only need to patch now/state/health fields; use track.update_now.',
                ),
                risk_hints={
                    'read_only': False,
                    'destructive': False,
                    'idempotent': False,
                    'open_world': False,
                    'requires_human_approval': False,
                    'external_effect': False,
                },
            ),
            ActionDefinition(
                name='add_proof',
                title='track.add_proof',
                description='Publish one draft artifact as current close proof.',
                input_schema={
                    'type': 'object',
                    'additionalProperties': False,
                    'required': ['track_id', 'artifact_id', 'label', 'summary'],
                    'properties': {
                        'track_id': {
                            'type': 'string',
                            'description': 'Existing non-archived track id to mutate.',
                        },
                        'artifact_id': {
                            'type': 'string',
                            'description': 'Active-buddy-owned draft artifact id to publish as proof.',
                        },
                        'label': {
                            'type': 'string',
                            'description': 'Human label for published proof entry.',
                        },
                        'summary': {
                            'type': 'string',
                            'description': 'Summary shown on track timeline and close proof.',
                        },
                    },
                },
                output_schema={
                    '$ref': 'ToolResult',
                },
                kind='write',
                mutates='runtime_objects',
                required_permission='track.add_proof',
                authority='track.shared_mutation',
                visibility='shared to buddies with track read access',
                durability='durable',
                result_content_level='track page plus artifact id and update id',
                success_effect='Publishes one draft artifact as current close proof and records the proof event on the track timeline.',
                failure_state_guarantee='Rejected writes do not mutate runtime objects; response explains the permission, payload, lifecycle, or visibility boundary.',
                reads=(
                    'one non-archived track page',
                    'one publishable artifact',
                ),
                writes=(
                    'track close_proof',
                    'track timeline update row',
                    'artifact publication metadata',
                ),
                does_not_write=(
                    'task state',
                    'request lifecycle',
                    'buddybox files',
                    'comment threads',
                ),
                preconditions=(
                    'track_id references an existing non-archived track',
                    'artifact_id references an active-buddy-owned draft artifact',
                    'artifact is not already published to another track',
                ),
                returns=(
                    'artifact_id',
                    'track',
                    'state_changes',
                ),
                use_when=(
                    'You need to publish a draft artifact as track close proof for outcome validation.',
                    'You are recording evidence in the dedicated proof slot, not general working material.',
                ),
                do_not_use_when=(
                    'You are publishing ongoing working artifacts; use track.add_material.',
                    'You only need a timeline narrative update with optional refs; use track.add_update.',
                ),
                risk_hints={
                    'read_only': False,
                    'destructive': False,
                    'idempotent': False,
                    'open_world': False,
                    'requires_human_approval': False,
                    'external_effect': False,
                },
            ),
            ActionDefinition(
                name='archive',
                title='track.archive',
                description='Archive one PM-owned shared track page.',
                input_schema={
                    'type': 'object',
                    'additionalProperties': False,
                    'required': ['track_id'],
                    'properties': {
                        'track_id': {
                            'type': 'string',
                            'description': 'Track id to archive (PM only).',
                        },
                    },
                },
                output_schema={
                    '$ref': 'ToolResult',
                },
                kind='write',
                mutates='runtime_objects',
                required_permission='track.archive',
                authority='pm.lifecycle_authority',
                visibility='shared to buddies with track read access until archived filters hide it',
                durability='durable',
                result_content_level='track page',
                success_effect='Archives one PM-owned track so it leaves active collaboration flows and rejects routine shared mutations.',
                failure_state_guarantee='Rejected writes do not mutate runtime objects; response explains the permission, payload, lifecycle, or visibility boundary.',
                reads=(
                    'one track page',
                ),
                writes=(
                    'track archived_at',
                ),
                does_not_write=(
                    'artifact body',
                    'artifact publication metadata',
                    'task state',
                    'request lifecycle',
                    'buddybox files',
                ),
                preconditions=(
                    'active buddy is pm',
                    'track_id references an existing track',
                ),
                returns=(
                    'track',
                ),
                use_when=(
                    'You are PM and need to close a track lifecycle so it is archived from active collaboration flows.',
                    'The track should no longer accept routine shared progress mutations.',
                ),
                do_not_use_when=(
                    'You only need to reflect temporary execution blockage or completion; use track.update_now state/health.',
                    'You still expect ongoing material, proof, or timeline updates on the same track.',
                ),
                risk_hints={
                    'read_only': False,
                    'destructive': True,
                    'idempotent': False,
                    'open_world': False,
                    'requires_human_approval': False,
                    'external_effect': False,
                },
            ),
        ),
    )


DEFINITION = _build_definition()
validate_definition(DEFINITION)


def invoke(*, action: str, args: dict[str, Any], context: ToolContext) -> dict[str, Any]:
    from . import _impl

    return _impl.invoke(action=action, args=args, context=context)
