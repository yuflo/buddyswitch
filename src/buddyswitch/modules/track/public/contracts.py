"""Immutable Track Public contracts and consumer-owned Artifact ports."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol


class PublicationCandidateError(ValueError):
    """Typed base failure exposed by the publication candidate port."""


class PublicationCandidateNotFound(PublicationCandidateError):
    """The requested Artifact does not exist."""


class PublicationCandidateOwnershipDenied(PublicationCandidateError):
    """The requested Artifact is owned by another identity."""


class PublicationCandidateNotPublishable(PublicationCandidateError):
    """The requested Artifact is not publishable."""


@dataclass(frozen=True)
class TrackScope:
    track_id: str
    owner_identity_id: str
    archived_at: str | None


@dataclass(frozen=True)
class ArtifactRelationFact:
    track_id: str
    track_archived_at: str | None
    relation_id: str | None
    artifact_id: str
    role: str | None
    label: str | None
    template: str | None
    from_identity_id: str | None
    summary: str
    current: bool
    created_at: str | None


@dataclass(frozen=True)
class TrackUpdateReferenceFact:
    track_id: str
    track_archived_at: str | None
    update_id: str
    kind: str | None
    summary: str | None
    by_identity_id: str | None
    created_at: str | None


@dataclass(frozen=True)
class ArtifactUsage:
    artifact_id: str
    relations: tuple[ArtifactRelationFact, ...]
    update_references: tuple[TrackUpdateReferenceFact, ...]


@dataclass(frozen=True)
class TrackContextSnapshot:
    tracks: tuple[dict[str, object], ...]
    candidate_tracks: tuple[dict[str, object], ...]
    open_comment_threads: tuple[dict[str, object], ...]
    recent_updates: tuple[dict[str, object], ...]


class PublicationCandidatePort(Protocol):
    artifact_id: str
    template: str


class AttachmentSummaryPort(Protocol):
    attachment_id: str
    filename: str
    content_type: str
    size_bytes: int
    sha256: str
    created_by_identity_id: str
    created_at: str

    def to_payload(self) -> dict[str, object]: ...


class ArtifactReferenceMetadataPort(Protocol):
    artifact_id: str
    template: str
    attachments: tuple[AttachmentSummaryPort, ...]


ResolvePublicationCandidate = Callable[
    [str, str],
    PublicationCandidatePort,
]
ReadReferenceMetadata = Callable[[str], ArtifactReferenceMetadataPort]
