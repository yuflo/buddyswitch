#!/usr/bin/env python3
"""Black-box protocol entrypoint for env.tools.track."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from env.tool_runtime.context import ToolContext
from env.tool_runtime.definition import ActionDefinition, ToolDefinition, validate_definition


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
                    'properties': {
                        'track_id': {
                            'type': 'string',
                        },
                        'title': {
                            'type': 'string',
                        },
                        'outcome': {
                            'type': 'string',
                        },
                        'appetite': {
                            'type': 'string',
                        },
                        'now': {
                            'type': 'object',
                        },
                        'state': {
                            'type': 'string',
                        },
                        'health': {
                            'type': 'string',
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
                    'properties': {
                        'state': {
                            'type': 'string',
                        },
                        'limit': {
                            'type': 'integer',
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
                    'properties': {
                        'track_id': {
                            'type': 'string',
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
                    'properties': {
                        'track_id': {
                            'type': 'string',
                        },
                        'now': {
                            'type': 'object',
                        },
                        'state': {
                            'type': 'string',
                        },
                        'health': {
                            'type': 'string',
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
                    'properties': {
                        'track_id': {
                            'type': 'string',
                        },
                        'artifact_id': {
                            'type': 'string',
                        },
                        'label': {
                            'type': 'string',
                        },
                        'summary': {
                            'type': 'string',
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
                    'properties': {
                        'track_id': {
                            'type': 'string',
                        },
                        'summary': {
                            'type': 'string',
                        },
                        'kind': {
                            'type': 'string',
                        },
                        'refs': {
                            'type': 'array',
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
                    'properties': {
                        'track_id': {
                            'type': 'string',
                        },
                        'artifact_id': {
                            'type': 'string',
                        },
                        'label': {
                            'type': 'string',
                        },
                        'summary': {
                            'type': 'string',
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
                    'properties': {
                        'track_id': {
                            'type': 'string',
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
