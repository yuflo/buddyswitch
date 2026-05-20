#!/usr/bin/env python3
"""Black-box protocol entrypoint for env.tools.artifact."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from env.tool_runtime.context import ToolContext
from env.tool_runtime.definition import ActionDefinition, ToolDefinition, validate_definition


def _build_definition() -> ToolDefinition:
    return ToolDefinition(
        id='artifact',
        title='Artifact Bodies',
        description='Read full artifact bodies and manage active-buddy private drafts/metadata.',
        cli_resource='artifact',
        command="python3 scripts/env/client.py artifact <action> --payload '<json-object>'",
        scope='private drafts and published track material/proof artifacts',
        capability_boundary='Private drafts are owner-scoped until published on a non-archived track.',
        use_when=(
            'You need full body reads or private draft artifact mutation.',
        ),
        do_not_use_when=(
            'You need shared publication mutation; use track.add_material or track.add_proof.',
        ),
        actions=(
            ActionDefinition(
                name='get',
                title='artifact.get',
                description='Get one readable artifact including full markdown body.',
                input_schema={
                    'type': 'object',
                    'additionalProperties': False,
                    'properties': {
                        'artifact_id': {
                            'type': 'string',
                        },
                    },
                },
                output_schema={
                    '$ref': 'ToolResult',
                },
                kind='read',
                mutates='none',
                required_permission='artifact.read',
                authority='artifact.owner_or_publication_boundary',
                preconditions=(
                    'artifact_id references a readable artifact',
                ),
                returns=(
                    'artifact',
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
                name='create_revision',
                title='artifact.create_revision',
                description='Create one active-buddy private draft artifact revision.',
                input_schema={
                    'type': 'object',
                    'additionalProperties': False,
                    'properties': {
                        'artifact_id': {
                            'type': 'string',
                        },
                        'title': {
                            'type': 'string',
                        },
                        'summary': {
                            'type': 'string',
                        },
                        'template': {
                            'type': 'string',
                        },
                        'body': {
                            'type': 'string',
                        },
                        'supersedes_artifact_id': {
                            'type': 'string',
                        },
                        'source_refs': {
                            'type': 'array',
                        },
                        'read_claim': {
                            'type': 'string',
                        },
                    },
                },
                output_schema={
                    '$ref': 'ToolResult',
                },
                kind='write',
                mutates='runtime_objects',
                required_permission='artifact.create',
                authority='artifact.buddy_scope',
                preconditions=(
                    'active buddy owns artifact.create permission',
                    'status and published_to_track are not accepted create_revision inputs',
                ),
                returns=(
                    'artifact',
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
                name='update_metadata',
                title='artifact.update_metadata',
                description='Update metadata on one active-buddy-owned artifact.',
                input_schema={
                    'type': 'object',
                    'additionalProperties': False,
                    'properties': {
                        'artifact_id': {
                            'type': 'string',
                        },
                        'title': {
                            'type': 'string',
                        },
                        'summary': {
                            'type': 'string',
                        },
                        'template': {
                            'type': 'string',
                        },
                        'body': {
                            'type': 'string',
                        },
                        'source_refs': {
                            'type': 'array',
                        },
                        'read_claim': {
                            'type': 'string',
                        },
                    },
                },
                output_schema={
                    '$ref': 'ToolResult',
                },
                kind='write',
                mutates='runtime_objects',
                required_permission='artifact.update',
                authority='artifact.buddy_scope',
                preconditions=(
                    'artifact_id references an active-buddy-owned artifact',
                ),
                returns=(
                    'artifact',
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
