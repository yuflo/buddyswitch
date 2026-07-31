"""Artifact provider adapter for Track-owned input-port failures."""

from __future__ import annotations

from buddyswitch.modules.artifact.public import operations
from buddyswitch.modules.artifact.public.contracts import (
    ArtifactNotFound,
    ArtifactNotPublishable,
    ArtifactOwnershipDenied,
    ArtifactReferenceMetadata,
    PublicationCandidate,
)
from buddyswitch.modules.track.public.contracts import (
    PublicationCandidateNotFound,
    PublicationCandidateNotPublishable,
    PublicationCandidateOwnershipDenied,
)


class _ArtifactCandidateNotFound(
    ArtifactNotFound,
    PublicationCandidateNotFound,
):
    pass


class _ArtifactCandidateOwnershipDenied(
    ArtifactOwnershipDenied,
    PublicationCandidateOwnershipDenied,
):
    pass


class _ArtifactCandidateNotPublishable(
    ArtifactNotPublishable,
    PublicationCandidateNotPublishable,
):
    pass


def resolve_publication_candidate(
    artifact_id: str,
    owner_identity_id: str,
) -> PublicationCandidate:
    try:
        return operations.resolve_publication_candidate(
            artifact_id,
            owner_identity_id,
        )
    except ArtifactNotFound as exc:
        raise _ArtifactCandidateNotFound(str(exc)) from exc
    except ArtifactOwnershipDenied as exc:
        raise _ArtifactCandidateOwnershipDenied(str(exc)) from exc
    except ArtifactNotPublishable as exc:
        raise _ArtifactCandidateNotPublishable(str(exc)) from exc


def read_reference_metadata(
    artifact_id: str,
) -> ArtifactReferenceMetadata:
    try:
        return operations.read_reference_metadata(artifact_id)
    except ArtifactNotFound as exc:
        raise _ArtifactCandidateNotFound(str(exc)) from exc
    except ArtifactNotPublishable as exc:
        raise _ArtifactCandidateNotPublishable(str(exc)) from exc
