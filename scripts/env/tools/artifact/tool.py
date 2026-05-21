#!/usr/bin/env python3
"""Black-box protocol entrypoint for env.tools.artifact."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from env.tool_runtime.context import ToolContext
from env.tool_runtime.definition import ActionDefinition, ToolDefinition, validate_definition

_SOURCE_REF_ITEMS_SCHEMA = {
    'type': 'object',
    'description': 'One provenance source reference row.',
    'additionalProperties': False,
    'required': ['type'],
    'properties': {
        'type': {
            'type': 'string',
            'description': 'Source reference kind.',
        },
        'id': {
            'type': 'string',
            'description': 'Referenced artifact/track/task id when type uses ids.',
        },
        'logical_name': {
            'type': 'string',
            'description': 'Referenced private buddybox logical_name when type is buddybox.',
        },
        'label': {
            'type': 'string',
            'description': 'Human label for note/external references.',
        },
        'url': {
            'type': 'string',
            'description': 'Optional URL when source ref type is external.',
        },
    },
    'anyOf': [
        {
            'type': 'object',
            'description': 'Artifact reference.',
            'additionalProperties': False,
            'required': ['type', 'id'],
            'properties': {
                'type': {'type': 'string', 'description': 'Artifact source reference.', 'enum': ['artifact']},
                'id': {'type': 'string', 'description': 'Artifact id.'},
            },
        },
        {
            'type': 'object',
            'description': 'Track reference.',
            'additionalProperties': False,
            'required': ['type', 'id'],
            'properties': {
                'type': {'type': 'string', 'description': 'Track source reference.', 'enum': ['track']},
                'id': {'type': 'string', 'description': 'Track id.'},
            },
        },
        {
            'type': 'object',
            'description': 'Task reference.',
            'additionalProperties': False,
            'required': ['type', 'id'],
            'properties': {
                'type': {'type': 'string', 'description': 'Task source reference.', 'enum': ['task']},
                'id': {'type': 'string', 'description': 'Task id.'},
            },
        },
        {
            'type': 'object',
            'description': 'Buddybox private provenance reference.',
            'additionalProperties': False,
            'required': ['type', 'logical_name'],
            'properties': {
                'type': {'type': 'string', 'description': 'Buddybox source reference.', 'enum': ['buddybox']},
                'logical_name': {'type': 'string', 'description': 'Private buddybox logical_name.'},
            },
        },
        {
            'type': 'object',
            'description': 'External source reference.',
            'additionalProperties': False,
            'required': ['type', 'label'],
            'properties': {
                'type': {'type': 'string', 'description': 'External source reference.', 'enum': ['external']},
                'label': {'type': 'string', 'description': 'External source label.'},
                'url': {'type': 'string', 'description': 'Optional external URL.'},
            },
        },
        {
            'type': 'object',
            'description': 'Note source reference.',
            'additionalProperties': False,
            'required': ['type', 'label'],
            'properties': {
                'type': {'type': 'string', 'description': 'Note source reference.', 'enum': ['note']},
                'label': {'type': 'string', 'description': 'Note label.'},
            },
        },
    ],
    'examples': [
        [{'type': 'note', 'label': 'Source note'}],
        [{'type': 'external', 'label': 'Product page', 'url': 'https://example.com'}],
    ],
}


def _build_definition() -> ToolDefinition:
    return ToolDefinition(
        id='artifact',
        title='Artifact Bodies',
        description='Discover readable artifact summaries, read full artifact bodies, and manage active-buddy private drafts/metadata.',
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
                name='list',
                title='artifact.list',
                description='List readable artifact summary rows with simple filters and no body content.',
                input_schema={
                    'type': 'object',
                    'additionalProperties': False,
                    'required': [],
                    'properties': {
                        'track_id': {
                            'type': 'string',
                            'description': 'Optional readable track id filter.',
                        },
                        'created_by': {
                            'type': 'string',
                            'description': 'Optional creator buddy id filter.',
                        },
                        'template': {
                            'type': 'string',
                            'description': 'Optional artifact template filter.',
                            'enum': ['brief', 'proposal', 'design', 'decision', 'proof', 'note'],
                        },
                        'status': {
                            'type': 'string',
                            'description': 'Optional artifact status filter.',
                            'enum': ['draft', 'published', 'archived'],
                        },
                        'q': {
                            'type': 'string',
                            'description': 'Optional case-insensitive title/summary substring filter.',
                        },
                        'limit': {
                            'type': 'integer',
                            'description': 'Optional maximum number of summary rows to return.',
                            'minimum': 1,
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
                    'filters are valid and within readable scope boundaries',
                ),
                returns=(
                    'artifacts',
                    'count',
                    'filters',
                ),
                use_when=(
                    'You need artifact summary discovery before choosing exact artifact_id values.',
                    'You need simple summary filters without loading full body content.',
                ),
                do_not_use_when=(
                    'You need one full artifact body by exact id; use artifact.get.',
                    'You need full-text body search; artifact.list only filters title and summary.',
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
                title='artifact.get',
                description='Get one readable artifact including full markdown body.',
                input_schema={
                    'type': 'object',
                    'additionalProperties': False,
                    'required': ['artifact_id'],
                    'properties': {
                        'artifact_id': {
                            'type': 'string',
                            'description': 'Readable artifact id to fetch.',
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
                use_when=(
                    'You need one artifact by id with full markdown body content.',
                    'You are validating publication output or source text before quoting/summarizing.',
                ),
                do_not_use_when=(
                    'You need to create a new draft revision; use artifact.create_revision.',
                    'You need to change artifact title/body/metadata; use artifact.update_metadata.',
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
                    'required': ['title', 'template', 'body'],
                    'properties': {
                        'artifact_id': {
                            'type': 'string',
                            'description': 'Optional explicit artifact id for the new draft revision.',
                        },
                        'title': {
                            'type': 'string',
                            'description': 'Draft artifact title.',
                        },
                        'summary': {
                            'type': 'string',
                            'description': 'Optional short summary for the draft.',
                        },
                        'template': {
                            'type': 'string',
                            'description': 'Artifact template.',
                            'enum': ['brief', 'proposal', 'design', 'decision', 'proof', 'note'],
                        },
                        'body': {
                            'type': 'string',
                            'description': 'Full markdown body content.',
                        },
                        'supersedes_artifact_id': {
                            'type': 'string',
                            'description': 'Optional current artifact id this revision supersedes.',
                        },
                        'source_refs': {
                            'type': 'array',
                            'description': 'Optional provenance source reference rows.',
                            'items': _SOURCE_REF_ITEMS_SCHEMA,
                        },
                        'read_claim': {
                            'type': 'string',
                            'description': (
                                "Optional read-scope claim; use 'summarized-full-content' when claiming full readable-source coverage."
                            ),
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
                use_when=(
                    'You are creating a new draft artifact revision from fresh content.',
                    'You need to supersede an earlier artifact while preserving revision lineage.',
                ),
                do_not_use_when=(
                    'You need to publish an existing draft to a shared track; use track.add_material or track.add_proof.',
                    'You only need to read existing content by id; use artifact.get.',
                    'You only need to patch an existing draft artifact fields in place; use artifact.update_metadata.',
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
                    'required': ['artifact_id'],
                    'properties': {
                        'artifact_id': {
                            'type': 'string',
                            'description': 'Active-buddy-owned artifact id to update.',
                        },
                        'title': {
                            'type': 'string',
                            'description': 'Optional replacement title.',
                        },
                        'summary': {
                            'type': 'string',
                            'description': 'Optional replacement summary.',
                        },
                        'template': {
                            'type': 'string',
                            'description': 'Optional replacement template.',
                            'enum': ['brief', 'proposal', 'design', 'decision', 'proof', 'note'],
                        },
                        'body': {
                            'type': 'string',
                            'description': 'Optional replacement markdown body.',
                        },
                        'source_refs': {
                            'type': 'array',
                            'description': 'Optional replacement provenance source reference rows.',
                            'items': _SOURCE_REF_ITEMS_SCHEMA,
                        },
                        'read_claim': {
                            'type': 'string',
                            'description': (
                                "Optional read-scope claim; use 'summarized-full-content' when claiming full readable-source coverage."
                            ),
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
                use_when=(
                    'You need to patch metadata or body on an existing active-buddy artifact id.',
                    'You want to adjust title/summary/template/source refs without creating a new revision id.',
                ),
                do_not_use_when=(
                    'You need to publish draft artifacts to shared material/proof slots; use track.add_material or track.add_proof.',
                    'You are starting a net-new draft revision or superseding another artifact; use artifact.create_revision.',
                    'You only need a read-only fetch of the artifact body; use artifact.get.',
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
