"""Black-box protocol entrypoint for env.tools.search."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from env.tool_runtime.context import ToolContext
from env.tool_runtime.definition import ActionDefinition, TASK_REQUIREMENT_ACTIVE_TASK_REQUIRED, TASK_REQUIREMENT_FREE, ToolDefinition, validate_definition


def _build_definition() -> ToolDefinition:
    return ToolDefinition(
        id='search',
        title='Search Boundary',
        description='Expose search backend metadata and non-opening URL planning.',
        scope='runtime-visible search capability boundary',
        capability_boundary='Search actions remain inside configured profile backend and launcher browser boundaries.',
        object_model=(
            'Search is a runtime-visible search boundary. It exposes backend status and URL planning only; it does not fetch, summarize, open browser pages, or persist search result content as product state.'
        ),
        use_when=(
            'You need runtime search boundary metadata or explicit non-opening search URL planning.',
        ),
        do_not_use_when=(
            'You need durable product object mutation.',
        ),
        actions=(
            ActionDefinition(
                name='status',
                title='search.status',
                description='Read search capability and backend/browser readiness metadata.',
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
                task_requirement=TASK_REQUIREMENT_FREE,
                required_permission='none',
                authority='profile.search_boundary',
                visibility='active-role runtime orientation',
                durability='none',
                result_content_level='backend status',
                success_effect='Returns configured search/backend/browser readiness metadata.',
                failure_state_guarantee='Rejected reads do not mutate runtime state and return no full object body beyond rejection metadata.',
                reads=(
                    'search profile',
                    'browser readiness',
                ),
                writes=(),
                does_not_write=(
                    'product objects',
                    'runtime files',
                    'browser page',
                    'tokens',
                ),
                preconditions=(
                    'active instance is available',
                ),
                returns=(
                    'backend_status',
                ),
                use_when=(
                    'You need search capability boundary and backend/browser readiness metadata only.',
                ),
                do_not_use_when=(
                    'You need target URL planning or browser page opening.',
                ),
                risk_hints={
                    'read_only': True,
                    'destructive': False,
                    'idempotent': True,
                    'open_world': True,
                    'requires_human_approval': False,
                    'external_effect': False,
                },
            ),
            ActionDefinition(
                name='request',
                title='search.request',
                description='Resolve one explicit search target URL intent.',
                input_schema={
                    'type': 'object',
                    'additionalProperties': False,
                    'required': ['query', 'backend'],
                    'properties': {
                        'query': {
                            'type': 'string',
                            'description': 'Non-empty search query text.',
                        },
                        'backend': {
                            'type': 'string',
                            'description': 'Explicit search backend choice.',
                            'enum': ['browser', 'search_api'],
                        },
                        'engine': {
                            'type': 'string',
                            'description': 'Optional search engine choice.',
                            'enum': ['google', 'web', 'reddit', 'x'],
                        },
                    },
                },
                output_schema={
                    '$ref': 'ToolResult',
                },
                kind='request',
                mutates='none',
                task_requirement=TASK_REQUIREMENT_ACTIVE_TASK_REQUIRED,
                required_permission='none',
                authority='profile.search_boundary',
                visibility='active-role runtime orientation',
                durability='none',
                result_content_level='target URL plan',
                success_effect='Resolves a target URL plan for a query; it does not fetch results and does not open a browser page.',
                failure_state_guarantee='Rejected reads do not mutate runtime state and return no full object body beyond rejection metadata.',
                reads=(
                    'search profile',
                    'query payload',
                ),
                writes=(),
                does_not_write=(
                    'product objects',
                    'runtime files',
                    'browser page',
                    'tokens',
                    'fetched results',
                ),
                preconditions=(
                    'query is non-empty',
                ),
                returns=(
                    'target_url',
                    'backend',
                    'engine',
                ),
                use_when=(
                    'You need explicit backend/query/engine URL planning metadata, including target_url, without opening a browser page (page_opened=false).',
                ),
                do_not_use_when=(
                    'You need general browser discovery or page inspection; use chrome-devtools-cockpit.',
                    'You need to open a browser search page; use chrome-devtools-cockpit.search_page.',
                    'You want implicit backend auto selection instead of explicit backend payload.',
                ),
                risk_hints={
                    'read_only': True,
                    'destructive': False,
                    'idempotent': True,
                    'open_world': True,
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
