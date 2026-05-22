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
        object_model=(
            'Buddybox files are active-buddy private file records in instance-local storage addressed by logical_name. They are not product-readable and do not mutate tracks, tasks, artifacts, requests, comments, or messages.'
        ),
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
                    'required': [],
                    'properties': {},
                },
                output_schema={
                    '$ref': 'ToolResult',
                },
                kind='read',
                mutates='none',
                required_permission='buddybox.read',
                authority='buddybox.private_local_scope',
                visibility='active-buddy private',
                durability='none',
                result_content_level='capability descriptor',
                success_effect='Describes private buddybox file boundaries and logical-name addressing.',
                failure_state_guarantee='Rejected reads do not mutate runtime state and return no full object body beyond rejection metadata.',
                reads=(
                    'active-buddy private file capability descriptor',
                ),
                writes=(),
                does_not_write=(
                    'private files',
                    'product objects',
                    'browser session',
                    'tokens',
                ),
                preconditions=(
                    'active buddy is bound to an instance',
                ),
                returns=(
                    'buddybox_desc',
                ),
                use_when=(
                    'You need the private-file capability boundary, visibility semantics, or quick scope orientation before buddybox file operations.',
                ),
                do_not_use_when=(
                    'You need private file rows or file bodies; use buddybox.list or buddybox.read. Do not use for product-readable publication paths.',
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
                    'required': [],
                    'properties': {
                        'logical_name': {
                            'type': 'string',
                            'description': 'Optional prefix logical_name to list under.',
                        },
                        'recursive': {
                            'type': 'boolean',
                            'description': 'Whether to recurse into nested directories.',
                            'default': False,
                        },
                        'limit': {
                            'type': 'integer',
                            'description': 'Maximum number of summary rows to return.',
                            'minimum': 1,
                            'default': 200,
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
                visibility='active-buddy private',
                durability='none',
                result_content_level='private file summary rows',
                success_effect='Lists active-buddy private file summaries without reading product state.',
                failure_state_guarantee='Rejected reads do not mutate runtime state and return no full object body beyond rejection metadata.',
                reads=(
                    'active-buddy private file summaries',
                ),
                writes=(),
                does_not_write=(
                    'private files',
                    'product objects',
                    'browser session',
                    'tokens',
                ),
                preconditions=(
                    'logical_name stays within active buddy private file capability when provided',
                ),
                returns=(
                    'files',
                ),
                use_when=(
                    'You need private logical_name inventory or summary rows within the active-buddy private file boundary.',
                ),
                do_not_use_when=(
                    'You need one file body; use buddybox.read. Do not use this for product-readable outputs; use artifact.create_revision when content must leave private scope.',
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
                    'required': ['logical_name'],
                    'properties': {
                        'logical_name': {
                            'type': 'string',
                            'description': 'Logical_name of the private file to read.',
                        },
                        'encoding': {
                            'type': 'string',
                            'description': 'Requested payload encoding for returned file content.',
                            'enum': ['auto', 'utf-8', 'base64'],
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
                visibility='active-buddy private',
                durability='none',
                result_content_level='private file body',
                success_effect='Reads one active-buddy private file by logical name.',
                failure_state_guarantee='Rejected reads do not mutate runtime state and return no full object body beyond rejection metadata.',
                reads=(
                    'one active-buddy private file body',
                ),
                writes=(),
                does_not_write=(
                    'private files',
                    'product objects',
                    'browser session',
                    'tokens',
                ),
                preconditions=(
                    'logical_name references one active buddy private file',
                ),
                returns=(
                    'private_file',
                ),
                use_when=(
                    "You need one exact active-buddy private file body by logical_name, optionally with explicit encoding or implementation-selected 'auto' encoding.",
                ),
                do_not_use_when=(
                    'You need private inventory discovery by path prefix; use buddybox.list first when logical_name is unknown.',
                    'You need product-readable/shared artifact content; use artifact.create_revision and publication flows instead of private-file reads.',
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
                    'required': ['logical_name'],
                    'properties': {
                        'logical_name': {
                            'type': 'string',
                            'description': 'Logical_name of the private file to write.',
                        },
                        'content': {
                            'type': 'string',
                            'description': 'UTF-8 text content. Provide exactly one of content or content_base64.',
                        },
                        'content_base64': {
                            'type': 'string',
                            'description': 'Base64-encoded binary payload. Provide exactly one of content or content_base64.',
                        },
                        'content_type': {
                            'type': 'string',
                            'description': 'Optional content type metadata for the written file.',
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
                visibility='active-buddy private',
                durability='durable',
                result_content_level='private file row',
                success_effect='Creates or replaces one active-buddy private file; content is not product-readable.',
                failure_state_guarantee='Rejected file writes do not create, replace, or delete private files; response explains the private file boundary.',
                reads=(
                    'active-buddy private file namespace',
                ),
                writes=(
                    'active-buddy private file',
                ),
                does_not_write=(
                    'tracks',
                    'tasks',
                    'artifacts',
                    'requests',
                    'comments',
                    'messages',
                    'browser session',
                    'tokens',
                ),
                preconditions=(
                    'logical_name stays inside active buddy private file capability',
                    'payload provides exactly one of content or content_base64',
                ),
                returns=(
                    'private_file',
                ),
                use_when=(
                    'You need to create or replace one active-buddy private file without mutating product-readable artifacts.',
                ),
                do_not_use_when=(
                    'You intend to share content across buddies or publish product-readable state; use artifact.create_revision and track publication actions.',
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
                    'required': ['logical_name'],
                    'properties': {
                        'logical_name': {
                            'type': 'string',
                            'description': 'Logical_name of the private file to delete.',
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
                visibility='active-buddy private',
                durability='durable',
                result_content_level='delete result',
                success_effect='Deletes one active-buddy private file without retracting published product content.',
                failure_state_guarantee='Rejected file writes do not create, replace, or delete private files; response explains the private file boundary.',
                reads=(
                    'one active-buddy private file',
                ),
                writes=(
                    'active-buddy private file deletion',
                ),
                does_not_write=(
                    'tracks',
                    'tasks',
                    'artifacts',
                    'requests',
                    'comments',
                    'messages',
                    'browser session',
                    'tokens',
                ),
                preconditions=(
                    'logical_name resolves inside active buddy private file capability',
                ),
                returns=(
                    'deleted',
                    'logical_name',
                ),
                use_when=(
                    'You need to remove one active-buddy private file from the private workspace boundary.',
                ),
                do_not_use_when=(
                    'You need to archive tasks/tracks or change product-readable artifacts/materials; this only deletes private files and does not retract published content.',
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
