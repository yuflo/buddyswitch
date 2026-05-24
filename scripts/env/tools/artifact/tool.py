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
        object_model=(
            'Artifacts are buddy-authored product content records. Draft revisions are owner-scoped until track.add_material or track.add_proof publishes them to shared track state; artifact.get returns full body content only for readable artifact ids.'
        ),
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
                visibility='active-buddy readable artifact summaries',
                durability='none',
                result_content_level='summary rows only',
                success_effect='Returns readable artifact summaries and filters without loading full markdown bodies.',
                failure_state_guarantee='Rejected reads do not mutate runtime state and return no full object body beyond rejection metadata.',
                reads=(
                    'readable artifact summaries',
                ),
                writes=(),
                does_not_write=(
                    'artifact body',
                    'artifact state',
                    'track state',
                    'task state',
                    'request lifecycle',
                    'buddybox files',
                ),
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
                visibility='active-buddy readable artifact body',
                durability='none',
                result_content_level='full markdown body',
                success_effect='Returns one readable artifact including full markdown body.',
                failure_state_guarantee='Rejected reads do not mutate runtime state and return no full object body beyond rejection metadata.',
                reads=(
                    'one readable artifact body',
                ),
                writes=(),
                does_not_write=(
                    'artifact state',
                    'track state',
                    'task state',
                    'request lifecycle',
                    'buddybox files',
                ),
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
                visibility='owner-scoped draft until track publication',
                durability='durable',
                result_content_level='artifact row with draft body',
                success_effect='Creates one active-buddy private draft artifact revision; publication starts only with track.add_material or track.add_proof.',
                failure_state_guarantee='Rejected writes do not mutate runtime objects; response explains the permission, payload, lifecycle, or visibility boundary.',
                reads=(
                    'optional superseded artifact',
                    'source refs metadata',
                ),
                writes=(
                    'active-buddy private draft artifact revision',
                ),
                does_not_write=(
                    'track state',
                    'track material slot',
                    'track proof slot',
                    'track.add_material publication path',
                    'track.add_proof publication path',
                    'task state',
                    'request lifecycle',
                    'buddybox files',
                ),
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
                visibility='owner-scoped unless already published through track state',
                durability='durable',
                result_content_level='artifact row',
                success_effect='Patches metadata or body on one active-buddy-owned artifact without changing track publication slots.',
                failure_state_guarantee='Rejected writes do not mutate runtime objects; response explains the permission, payload, lifecycle, or visibility boundary.',
                reads=(
                    'one active-buddy-owned artifact',
                ),
                writes=(
                    'active-buddy-owned artifact metadata/body',
                ),
                does_not_write=(
                    'track state',
                    'track material slot',
                    'track proof slot',
                    'task state',
                    'request lifecycle',
                    'buddybox files',
                ),
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
            ActionDefinition(
                name='attach_file',
                title='artifact.attach_file',
                description='Attach one existing file from the active instance buddybox directory to an active-buddy-owned draft artifact.',
                input_schema={
                    'type': 'object',
                    'additionalProperties': False,
                    'required': ['artifact_id', 'filename', 'source_path'],
                    'properties': {
                        'artifact_id': {
                            'type': 'string',
                            'description': 'Active-buddy-owned draft artifact id to attach a file to.',
                        },
                        'filename': {
                            'type': 'string',
                            'description': 'Display filename without path separators.',
                        },
                        'source_path': {
                            'type': 'string',
                            'description': 'Existing source file path under the active instance buddybox directory.',
                        },
                        'content_type': {
                            'type': 'string',
                            'description': 'Optional MIME content type metadata.',
                        },
                    },
                },
                output_schema={'$ref': 'ToolResult'},
                kind='write',
                mutates='runtime_objects',
                required_permission='artifact.update',
                authority='artifact.buddy_scope',
                visibility='owner-scoped draft attachment metadata until later publication makes the artifact readable',
                durability='durable',
                result_content_level='attachment summary row',
                success_effect='Promotes one active-buddy private buddybox file into artifact-owned attachment metadata and pinned storage without exposing filesystem paths.',
                failure_state_guarantee='Rejected attachment writes do not mutate artifact metadata, pinned files, buddybox files, or track state.',
                reads=(
                    'one active-buddy-owned draft artifact',
                    'one source file under the active instance buddybox directory',
                ),
                writes=(
                    'artifact attachment metadata',
                    'artifact-owned pinned attachment file',
                ),
                does_not_write=(
                    'track state',
                    'task state',
                    'request lifecycle',
                    'comments',
                    'messages',
                    'buddybox files',
                    'browser session',
                ),
                preconditions=(
                    'artifact_id references an active-buddy-owned draft artifact',
                    'source_path references one non-empty file inside the active instance buddybox directory',
                ),
                returns=('attachment',),
                use_when=(
                    'You need to promote one file from $BUDDYSWITCH_BUDDYBOX_DIR into draft artifact attachment metadata.',
                ),
                do_not_use_when=(
                    'You need to create a new draft body first; use artifact.create_revision.',
                    'You only need private file storage without artifact ownership; write the file directly under $BUDDYSWITCH_BUDDYBOX_DIR.',
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
                name='list_attachments',
                title='artifact.list_attachments',
                description='List attachment summary rows for one readable artifact.',
                input_schema={
                    'type': 'object',
                    'additionalProperties': False,
                    'required': ['artifact_id'],
                    'properties': {
                        'artifact_id': {
                            'type': 'string',
                            'description': 'Readable artifact id whose attachment summaries should be listed.',
                        },
                    },
                },
                output_schema={'$ref': 'ToolResult'},
                kind='read',
                mutates='none',
                required_permission='artifact.read',
                authority='artifact.owner_or_publication_boundary',
                visibility='attachment summary rows for readable artifacts only',
                durability='none',
                result_content_level='attachment summaries only',
                success_effect='Returns attachment summary rows for one readable artifact without returning blob content.',
                failure_state_guarantee='Rejected attachment reads do not mutate runtime state and return no attachment body.',
                reads=('one readable artifact attachment summary list',),
                writes=(),
                does_not_write=(
                    'artifact state',
                    'track state',
                    'task state',
                    'request lifecycle',
                    'buddybox files',
                    'pinned attachment files',
                ),
                preconditions=('artifact_id references a readable artifact',),
                returns=('attachments',),
                use_when=(
                    'You need attachment summary discovery before choosing one exact attachment_id.',
                ),
                do_not_use_when=(
                    'You need exact blob content for one attachment_id; use artifact.get_attachment.',
                    'You need the full markdown body; use artifact.get.',
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
                name='get_attachment',
                title='artifact.get_attachment',
                description='Read one exact attachment body from one readable artifact.',
                input_schema={
                    'type': 'object',
                    'additionalProperties': False,
                    'required': ['artifact_id', 'attachment_id'],
                    'properties': {
                        'artifact_id': {
                            'type': 'string',
                            'description': 'Readable artifact id that owns the attachment.',
                        },
                        'attachment_id': {
                            'type': 'string',
                            'description': 'Exact attachment id to read.',
                        },
                    },
                },
                output_schema={'$ref': 'ToolResult'},
                kind='read',
                mutates='none',
                required_permission='artifact.read',
                authority='artifact.owner_or_publication_boundary',
                visibility='one attachment body for one readable artifact',
                durability='none',
                result_content_level='exact attachment content_base64 payload',
                success_effect='Returns one exact readable attachment metadata row plus content_base64 without exposing filesystem paths.',
                failure_state_guarantee='Rejected attachment reads do not mutate runtime state and return no attachment body beyond rejection metadata.',
                reads=('one readable artifact attachment body',),
                writes=(),
                does_not_write=(
                    'artifact state',
                    'track state',
                    'task state',
                    'request lifecycle',
                    'buddybox files',
                    'pinned attachment files',
                ),
                preconditions=(
                    'artifact_id references a readable artifact',
                    'attachment_id references one attachment owned by that artifact',
                ),
                returns=('attachment', 'content_base64'),
                use_when=(
                    'You have artifact_id plus attachment_id and need the exact attachment body as content_base64.',
                ),
                do_not_use_when=(
                    'You only need attachment summaries; use artifact.list_attachments.',
                    'You need the full artifact body instead of one attachment blob; use artifact.get.',
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
