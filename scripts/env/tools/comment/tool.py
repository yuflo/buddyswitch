#!/usr/bin/env python3
"""Black-box protocol entrypoint for env.tools.comment."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from env.tool_runtime.context import ToolContext
from env.tool_runtime.definition import ActionDefinition, ToolDefinition, validate_definition


def _build_definition() -> ToolDefinition:
    return ToolDefinition(
        id='comment',
        title='Object Comments',
        description='Add, list, and PM-resolve comments on readable track and artifact targets.',
        cli_resource='comment',
        command="python3 scripts/env/client.py comment <action> --payload '<json-object>'",
        scope='target-scoped plain-text comments on readable tracks and artifacts',
        capability_boundary='Comment scope requires active-buddy readability on the target object.',
        use_when=(
            'You need target-scoped discussion on tracks or artifacts.',
        ),
        do_not_use_when=(
            'You need direct buddy inbox messages; use message tool.',
        ),
        actions=(
            ActionDefinition(
                name='add',
                title='comment.add',
                description='Add one comment row to a readable target thread.',
                input_schema={
                    'type': 'object',
                    'additionalProperties': False,
                    'required': ['target_type', 'target_id', 'content'],
                    'properties': {
                        'target_type': {
                            'type': 'string',
                            'description': 'Comment target type.',
                            'enum': ['track', 'artifact', 'artifact_section'],
                        },
                        'target_id': {
                            'type': 'string',
                            'description': 'Comment target id.',
                        },
                        'content': {
                            'type': 'string',
                            'description': 'Comment body text.',
                        },
                        'reply_to': {
                            'type': 'string',
                            'description': 'Optional parent comment id for threaded replies.',
                        },
                        'artifact_revision_id': {
                            'type': 'string',
                            'description': 'Optional artifact revision id constraint for discussion scope.',
                        },
                        'anchor': {
                            'type': 'string',
                            'description': "Optional section anchor; required when target_type is artifact_section.",
                        },
                        'mentions': {
                            'type': 'array',
                            'description': 'Optional list of manifest buddy ids to mention.',
                            'items': {
                                'type': 'string',
                                'description': 'Mentioned buddy id.',
                            },
                        },
                    },
                },
                output_schema={
                    '$ref': 'ToolResult',
                },
                kind='write',
                mutates='runtime_objects',
                required_permission='comment.add',
                authority='target.read_boundary',
                preconditions=(
                    'target_type is one of track, artifact, artifact_section',
                    'anchor is required when target_type is artifact_section',
                    'active buddy has read access to target',
                ),
                returns=(
                    'comment_id',
                    'comment',
                ),
                use_when=(
                    'You need threaded discussion on a track, artifact, or artifact_section target.',
                    'You need reply chains or mentions attached to a specific object context.',
                ),
                do_not_use_when=(
                    'You need canonical track timeline progress chronology entries; use track.add_update.',
                    'You need direct buddy inbox communication outside object threads; use message.send.',
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
                title='comment.list',
                description='List comment rows for a readable target thread.',
                input_schema={
                    'type': 'object',
                    'additionalProperties': False,
                    'required': ['target_type', 'target_id'],
                    'properties': {
                        'target_type': {
                            'type': 'string',
                            'description': 'Comment target type.',
                            'enum': ['track', 'artifact', 'artifact_section'],
                        },
                        'target_id': {
                            'type': 'string',
                            'description': 'Comment target id.',
                        },
                        'status': {
                            'type': 'string',
                            'description': 'Optional status filter.',
                            'enum': ['open', 'resolved', 'all'],
                        },
                    },
                },
                output_schema={
                    '$ref': 'ToolResult',
                },
                kind='read',
                mutates='none',
                required_permission='comment.list',
                authority='target.read_boundary',
                preconditions=(
                    'target_type is one of track, artifact, artifact_section',
                    'anchor is required when target_type is artifact_section',
                    'active buddy has read access to target',
                ),
                returns=(
                    'comments',
                ),
                use_when=(
                    'You need to read conversation history for one track/artifact/artifact_section thread.',
                    'You need open/resolved comment rows to decide follow-up discussion actions.',
                ),
                do_not_use_when=(
                    'You need shared progress events or publication history; use track.open or track.add_update.',
                    'You need direct buddy inbox history; use message.list.',
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
                name='resolve',
                title='comment.resolve',
                description='PM-only resolution for one full comment thread.',
                input_schema={
                    'type': 'object',
                    'additionalProperties': False,
                    'required': ['comment_id', 'resolution_summary'],
                    'properties': {
                        'comment_id': {
                            'type': 'string',
                            'description': 'Comment id in the thread PM reviewed.',
                        },
                        'resolution_summary': {
                            'type': 'string',
                            'description': 'PM review closure summary.',
                        },
                    },
                },
                output_schema={
                    '$ref': 'ToolResult',
                },
                kind='write',
                mutates='runtime_objects',
                required_permission='comment.resolve',
                authority='pm.review_closure',
                preconditions=(
                    'active buddy is pm',
                    'comment_id references an existing thread comment on a readable non-archived target',
                    'thread has at least one open comment row',
                ),
                returns=(
                    'comments',
                    'updated_ids',
                ),
                use_when=(
                    'PM reviewed a thread and wants durable resolved closure state for all rows in that thread.',
                ),
                do_not_use_when=(
                    'You need to continue discussion; use comment.add for new evidence or follow-up notes.',
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
        ),
    )


DEFINITION = _build_definition()
validate_definition(DEFINITION)


def invoke(*, action: str, args: dict[str, Any], context: ToolContext) -> dict[str, Any]:
    from . import _impl

    return _impl.invoke(action=action, args=args, context=context)
