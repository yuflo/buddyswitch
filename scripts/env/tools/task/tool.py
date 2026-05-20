#!/usr/bin/env python3
"""Black-box protocol entrypoint for env.tools.task."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from env.tool_runtime.context import ToolContext
from env.tool_runtime.definition import ActionDefinition, ToolDefinition, validate_definition


def _build_definition() -> ToolDefinition:
    return ToolDefinition(
        id='task',
        title='Task Management',
        description='Manage active-buddy private tasks as optional work aids.',
        cli_resource='task',
        command="python3 scripts/env/client.py task <action> --payload '<json-object>'",
        scope='active-buddy private task work items',
        capability_boundary='Only active-buddy-owned tasks are readable and writable.',
        use_when=(
            'You need to create, list, read, update, or archive tasks owned by the active buddy.',
        ),
        do_not_use_when=(
            'You need shared artifact publication; use track and artifact tools.',
        ),
        actions=(
            ActionDefinition(
                name='create',
                title='task.create',
                description='Create one active-buddy private task.',
                input_schema={
                    'type': 'object',
                    'additionalProperties': False,
                    'properties': {
                        'task_id': {
                            'type': 'string',
                        },
                        'title': {
                            'type': 'string',
                        },
                        'summary': {
                            'type': 'string',
                        },
                        'status': {
                            'type': 'string',
                        },
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
                required_permission='task.create',
                authority='task.buddy_scope',
                preconditions=(
                    'active buddy owns task.create permission',
                ),
                returns=(
                    'task_id',
                    'task',
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
                title='task.list',
                description='List active-buddy private tasks.',
                input_schema={
                    'type': 'object',
                    'additionalProperties': False,
                    'properties': {
                        'status': {
                            'type': 'string',
                        },
                        'track_id': {
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
                required_permission='task.read',
                authority='task.buddy_scope',
                preconditions=(
                    'active buddy owns task.read permission',
                ),
                returns=(
                    'tasks',
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
                name='get',
                title='task.get',
                description='Get one active-buddy private task.',
                input_schema={
                    'type': 'object',
                    'additionalProperties': False,
                    'properties': {
                        'task_id': {
                            'type': 'string',
                        },
                    },
                },
                output_schema={
                    '$ref': 'ToolResult',
                },
                kind='read',
                mutates='none',
                required_permission='task.read',
                authority='task.buddy_scope',
                preconditions=(
                    'task_id references an active-buddy task',
                ),
                returns=(
                    'task',
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
                name='update',
                title='task.update',
                description='Update one active-buddy private task.',
                input_schema={
                    'type': 'object',
                    'additionalProperties': False,
                    'properties': {
                        'task_id': {
                            'type': 'string',
                        },
                        'title': {
                            'type': 'string',
                        },
                        'summary': {
                            'type': 'string',
                        },
                        'status': {
                            'type': 'string',
                        },
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
                required_permission='task.update',
                authority='task.buddy_scope',
                preconditions=(
                    'task_id references an active-buddy task',
                ),
                returns=(
                    'task',
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
                title='task.archive',
                description='Archive one active-buddy private task.',
                input_schema={
                    'type': 'object',
                    'additionalProperties': False,
                    'properties': {
                        'task_id': {
                            'type': 'string',
                        },
                    },
                },
                output_schema={
                    '$ref': 'ToolResult',
                },
                kind='write',
                mutates='runtime_objects',
                required_permission='task.archive',
                authority='task.buddy_scope',
                preconditions=(
                    'task_id references an active-buddy task',
                ),
                returns=(
                    'task',
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
