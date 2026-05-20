#!/usr/bin/env python3
"""Black-box protocol entrypoint for env.tools.buddybox."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from env.tool_runtime.context import ToolContext
from env.tool_runtime.definition import ActionDefinition, ToolDefinition, validate_definition


def _build_definition() -> ToolDefinition:
    return ToolDefinition(
        id='buddybox',
        title='Buddybox Files',
        description='Operate active-buddy private files through logical_name values.',
        cli_resource='buddybox',
        command="python3 scripts/env/client.py buddybox <action> --payload '<json-object>'",
        scope='active-buddy private local workspace files',
        capability_boundary='Only files under the active-buddy private file capability are allowed.',
        use_when=(
            'You need active-buddy private file read/write/list/delete operations.',
        ),
        do_not_use_when=(
            'You need product-readable shared output; use artifact and track publication.',
        ),
        actions=(
            ActionDefinition(
                name='desc',
                title='buddybox.desc',
                description='Describe active-buddy private file capability.',
                input_schema={
                    'type': 'object',
                    'additionalProperties': False,
                    'properties': {},
                },
                output_schema={
                    '$ref': 'ToolResult',
                },
                kind='read',
                mutates='none',
                required_permission='buddybox.read',
                authority='buddybox.private_local_scope',
                preconditions=(
                    'active buddy is bound to an instance',
                ),
                returns=(
                    'buddybox_desc',
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
                name='list',
                title='buddybox.list',
                description='List active-buddy private file summaries.',
                input_schema={
                    'type': 'object',
                    'additionalProperties': False,
                    'properties': {
                        'logical_name': {
                            'type': 'string',
                        },
                        'recursive': {
                            'type': 'string',
                        },
                        'limit': {
                            'type': 'string',
                        },
                    },
                },
                output_schema={
                    '$ref': 'ToolResult',
                },
                kind='read',
                mutates='none',
                required_permission='buddybox.read',
                authority='buddybox.private_local_scope',
                preconditions=(
                    'logical_name stays within active buddy private file capability when provided',
                ),
                returns=(
                    'files',
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
                name='read',
                title='buddybox.read',
                description='Read one active-buddy private file.',
                input_schema={
                    'type': 'object',
                    'additionalProperties': False,
                    'properties': {
                        'logical_name': {
                            'type': 'string',
                        },
                        'encoding': {
                            'type': 'string',
                        },
                    },
                },
                output_schema={
                    '$ref': 'ToolResult',
                },
                kind='read',
                mutates='none',
                required_permission='buddybox.read',
                authority='buddybox.private_local_scope',
                preconditions=(
                    'logical_name references one active buddy private file',
                ),
                returns=(
                    'private_file',
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
                name='write',
                title='buddybox.write',
                description='Write one active-buddy private file.',
                input_schema={
                    'type': 'object',
                    'additionalProperties': False,
                    'properties': {
                        'logical_name': {
                            'type': 'string',
                        },
                        'content': {
                            'type': 'string',
                        },
                        'content_base64': {
                            'type': 'string',
                        },
                        'content_type': {
                            'type': 'string',
                        },
                    },
                },
                output_schema={
                    '$ref': 'ToolResult',
                },
                kind='write',
                mutates='runtime_files',
                required_permission='buddybox.write',
                authority='buddybox.private_local_scope',
                preconditions=(
                    'logical_name stays inside active buddy private file capability',
                    'payload provides exactly one of content or content_base64',
                ),
                returns=(
                    'private_file',
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
                name='delete',
                title='buddybox.delete',
                description='Delete one active-buddy private file.',
                input_schema={
                    'type': 'object',
                    'additionalProperties': False,
                    'properties': {
                        'logical_name': {
                            'type': 'string',
                        },
                    },
                },
                output_schema={
                    '$ref': 'ToolResult',
                },
                kind='write',
                mutates='runtime_files',
                required_permission='buddybox.delete',
                authority='buddybox.private_local_scope',
                preconditions=(
                    'logical_name resolves inside active buddy private file capability',
                ),
                returns=(
                    'deleted',
                    'logical_name',
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
