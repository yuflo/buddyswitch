#!/usr/bin/env python3
"""Black-box protocol entrypoint for env.tools.context."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from env.tool_runtime.context import ToolContext
from env.tool_runtime.definition import ActionDefinition, ToolDefinition, validate_definition


def _build_definition() -> ToolDefinition:
    return ToolDefinition(
        id='context',
        title='Context Discovery',
        description='Read runtime orientation, compact affordances, full tool catalog, and operation semantics.',
        cli_resource='context',
        command="python3 scripts/env/client.py context <action> --payload '<json-object>'",
        scope='runless read-only orientation payload',
        capability_boundary='Context actions are read-only and never grant write authority.',
        use_when=(
            'You need runtime discovery and orientation before choosing write operations.',
        ),
        do_not_use_when=(
            'You need to mutate product or private file state.',
        ),
        actions=(
            ActionDefinition(
                name='get',
                title='context.get',
                description='Return full runtime context sections with full tool catalog and operation semantics.',
                input_schema={
                    'type': 'object',
                    'additionalProperties': False,
                    'required': [],
                    'properties': {
                        'track_id': {
                            'type': 'string',
                            'description': 'Optional track id filter for context sections.',
                        },
                        'task_id': {
                            'type': 'string',
                            'description': 'Optional task id filter for context sections.',
                        },
                        'limit': {
                            'type': 'integer',
                            'description': 'Optional maximum number of candidate rows per section.',
                            'minimum': 1,
                        },
                    },
                },
                output_schema={
                    '$ref': 'ToolResult',
                },
                kind='read',
                mutates='none',
                required_permission='none',
                authority='read-only context discovery',
                preconditions=(
                    'filters are valid',
                ),
                returns=(
                    'sections',
                    'tool_catalog',
                    'decision_surface',
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
                name='summarize',
                title='context.summarize',
                description='Return compact runtime context orientation and first-pass affordances.',
                input_schema={
                    'type': 'object',
                    'additionalProperties': False,
                    'required': [],
                    'properties': {
                        'track_id': {
                            'type': 'string',
                            'description': 'Optional track id filter for summary rows.',
                        },
                        'task_id': {
                            'type': 'string',
                            'description': 'Optional task id filter for summary rows.',
                        },
                        'limit': {
                            'type': 'integer',
                            'description': 'Optional maximum number of summary rows per section.',
                            'minimum': 1,
                        },
                    },
                },
                output_schema={
                    '$ref': 'ToolResult',
                },
                kind='read',
                mutates='none',
                required_permission='none',
                authority='read-only context discovery',
                preconditions=(
                    'filters are valid',
                ),
                returns=(
                    'summary',
                    'candidate_tracks',
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
                name='list_sources',
                title='context.list_sources',
                description='Return context source descriptors only.',
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
                required_permission='none',
                authority='read-only context discovery',
                preconditions=(
                    'none',
                ),
                returns=(
                    'sources',
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
