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
        description='Add and list comments on readable track and artifact targets.',
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
                    'target_type is track or artifact',
                    'active buddy has read access to target',
                ),
                returns=(
                    'comment_id',
                    'comment',
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
                            'enum': ['open', 'resolved'],
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
                    'target_type is track or artifact',
                    'active buddy has read access to target',
                ),
                returns=(
                    'comments',
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
        ),
    )


DEFINITION = _build_definition()
validate_definition(DEFINITION)


def invoke(*, action: str, args: dict[str, Any], context: ToolContext) -> dict[str, Any]:
    from . import _impl

    return _impl.invoke(action=action, args=args, context=context)
