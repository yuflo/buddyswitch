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
                    'required': ['title', 'summary'],
                    'properties': {
                        'task_id': {
                            'type': 'string',
                            'description': 'Optional explicit task id.',
                        },
                        'title': {
                            'type': 'string',
                            'description': 'Task title.',
                        },
                        'summary': {
                            'type': 'string',
                            'description': 'Task summary.',
                        },
                        'status': {
                            'type': 'string',
                            'description': 'Optional initial task status.',
                            'enum': ['active', 'blocked', 'done', 'archived'],
                        },
                        'track_id': {
                            'type': 'string',
                            'description': 'Optional linked track id.',
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
                use_when=(
                    'You need to capture a new private work item for the active buddy.',
                    'You are turning a newly identified step into a track-linked or standalone task row.',
                ),
                do_not_use_when=(
                    'You need to modify an existing task; use task.update.',
                    'You need to retire an existing task; use task.archive.',
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
                    'required': [],
                    'properties': {
                        'status': {
                            'type': 'string',
                            'description': 'Optional status filter.',
                            'enum': ['active', 'blocked', 'done', 'archived'],
                        },
                        'track_id': {
                            'type': 'string',
                            'description': 'Optional linked track filter.',
                        },
                        'limit': {
                            'type': 'integer',
                            'description': 'Optional maximum number of rows to return.',
                            'minimum': 1,
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
                use_when=(
                    'You need a filtered task list view across many tasks by status or track_id.',
                    'You are triaging active-buddy workload before selecting one task to edit.',
                ),
                do_not_use_when=(
                    'You need one specific task summary row by task id; use task.get.',
                    'You need to create or mutate task state; use task.create/task.update/task.archive.',
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
                    'required': ['task_id'],
                    'properties': {
                        'task_id': {
                            'type': 'string',
                            'description': 'Task id to read.',
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
                use_when=(
                    'You already know the task id and need the current full task row.',
                    'You need to inspect one task before deciding whether to update or archive it.',
                ),
                do_not_use_when=(
                    'You need multi-row filtering or queue triage; use task.list.',
                    'You need to mutate task fields or lifecycle; use task.update or task.archive.',
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
                    'required': ['task_id'],
                    'properties': {
                        'task_id': {
                            'type': 'string',
                            'description': 'Task id to update.',
                        },
                        'title': {
                            'type': 'string',
                            'description': 'Optional replacement title.',
                        },
                        'summary': {
                            'type': 'string',
                            'description': 'Optional replacement summary.',
                        },
                        'status': {
                            'type': 'string',
                            'description': 'Optional replacement status.',
                            'enum': ['active', 'blocked', 'done', 'archived'],
                        },
                        'track_id': {
                            'type': 'string',
                            'description': 'Optional replacement linked track id.',
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
                use_when=(
                    'You need to patch title/summary/status/track_id on an existing task.',
                    'You want to move a task between active, blocked, and done without archiving it.',
                ),
                do_not_use_when=(
                    'You need to create a brand-new task row; use task.create.',
                    'You are removing the task from active workflow via archival; use task.archive.',
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
                    'required': ['task_id'],
                    'properties': {
                        'task_id': {
                            'type': 'string',
                            'description': 'Task id to archive.',
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
                use_when=(
                    'You need to close out a task so it leaves active workflow views.',
                    'You are preserving history while marking the task as archived lifecycle state.',
                ),
                do_not_use_when=(
                    'You only need to mark ongoing progress states like blocked/done; use task.update.',
                    'You need to inspect tasks without mutation; use task.get or task.list.',
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
