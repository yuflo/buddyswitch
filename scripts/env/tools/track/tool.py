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
                preconditions=(
                    'active buddy is pm',
                ),
                returns=(
                    'track',
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
                preconditions=(
                    'active buddy owns track.read permission',
                ),
                returns=(
                    'tracks',
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
                preconditions=(
                    'track_id references an existing non-archived track',
                ),
                returns=(
                    'track',
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
                preconditions=(
                    'track_id references an existing non-archived track',
                ),
                returns=(
                    'track',
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
                            'description': 'Summary shown on track timeline and materials.',
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
                preconditions=(
                    'track_id references an existing non-archived track',
                ),
                returns=(
                    'track',
                    'update',
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
                preconditions=(
                    'active buddy is pm',
                    'track_id references an existing track',
                ),
                returns=(
                    'track',
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
