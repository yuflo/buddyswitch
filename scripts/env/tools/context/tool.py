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
        description='Read runtime orientation, compact affordances, full tool catalog, operation semantics, and read-only source_workspace and writable_surfaces facts.',
        scope='runless read-only orientation payload',
        capability_boundary='Context actions are read-only orientation only; they do not configure source roots or grant write authority.',
        object_model=(
            'Context is read-only progressive runtime discovery. It exposes current orientation, candidate ids, source workspace facts, generated tool affordances, full catalog, and operation semantics without granting authority or mutating state.'
        ),
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
                description='Return full runtime context sections with full tool catalog, operation semantics, and read-only source workspace and writable_surfaces facts.',
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
                visibility='active-role runtime orientation',
                durability='none',
                result_content_level='full context and catalog',
                success_effect='Returns full read-only context, full generated tool catalog, operation semantics, and source workspace facts.',
                failure_state_guarantee='Rejected reads do not mutate runtime state and return no full object body beyond rejection metadata.',
                reads=(
                    'runtime context sections',
                    'source workspace facts',
                    'writable surface facts',
                    'tool registry',
                    'operation semantics',
                ),
                writes=(),
                does_not_write=(
                    'runtime objects',
                    'runtime files',
                    'browser session',
                    'tokens',
                    'source root config',
                ),
                preconditions=(
                    'filters are valid',
                ),
                returns=(
                    'sections',
                    'source_workspace',
                    'writable_surfaces',
                    'tool_catalog',
                    'decision_surface',
                ),
                use_when=(
                    'You need full runtime sections plus full tool_catalog and operation_semantics before choosing exact downstream tool calls.',
                ),
                do_not_use_when=(
                    'You only need compact orientation or source descriptors; use context.summarize or context.list_sources.',
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
                description='Return compact runtime context orientation with candidate tracks/requests/artifacts plus read-only source workspace facts, writable_surfaces facts, and first-pass affordances.',
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
                visibility='active-role runtime orientation',
                durability='none',
                result_content_level='compact summary',
                success_effect='Returns compact first-pass orientation with candidate ids and generated compact affordances.',
                failure_state_guarantee='Rejected reads do not mutate runtime state and return no full object body beyond rejection metadata.',
                reads=(
                    'runtime context summary',
                    'candidate ids',
                    'registry compact affordances',
                    'source workspace facts',
                    'writable surface facts',
                ),
                writes=(),
                does_not_write=(
                    'runtime objects',
                    'runtime files',
                    'browser session',
                    'tokens',
                    'source root config',
                    'full schemas',
                ),
                preconditions=(
                    'filters are valid',
                ),
                returns=(
                    'current_context_summary',
                    'source_workspace',
                    'candidate_tracks',
                    'candidate_requests',
                    'candidate_artifacts',
                    'open_comment_threads',
                    'recent_updates',
                    'message_cues',
                    'writable_surfaces',
                ),
                use_when=(
                    'You need a compact first-pass summary with candidate tracks/requests/artifacts and quick discussion/update attention cues.',
                ),
                do_not_use_when=(
                    'You need full operation semantics/tool catalog details, full comment bodies, or full artifact markdown body; use context.get/comment.list/artifact.get.',
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
                description='Return context source descriptors, including source_workspace and writable_surfaces read-only semantics.',
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
                visibility='active-role runtime orientation',
                durability='none',
                result_content_level='source descriptors',
                success_effect='Returns read-only source descriptors and boundaries.',
                failure_state_guarantee='Rejected reads do not mutate runtime state and return no full object body beyond rejection metadata.',
                reads=(
                    'context source descriptors',
                ),
                writes=(),
                does_not_write=(
                    'runtime objects',
                    'runtime files',
                    'browser session',
                    'tokens',
                    'source root config',
                ),
                preconditions=(
                    'none',
                ),
                returns=(
                    'sources',
                ),
                use_when=(
                    'You only need source descriptors and scope boundaries, including source_workspace semantics, for context data planes.',
                ),
                do_not_use_when=(
                    'You need candidate ids, affordances, full runtime sections, or full tool catalog semantics; use context.summarize or context.get.',
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
