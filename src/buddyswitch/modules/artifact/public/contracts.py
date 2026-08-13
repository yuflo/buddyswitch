"""Immutable Artifact Public contracts and typed errors."""

from __future__ import annotations

from dataclasses import dataclass


VALID_ARTIFACT_TEMPLATES = (
    "brief",
    "proposal",
    "design",
    "decision",
    "proof",
    "note",
)


class ArtifactPublicError(ValueError):
    """Base error for typed Artifact Public failures."""


class ArtifactNotFound(ArtifactPublicError):
    """The requested Artifact does not exist."""


class ArtifactOwnershipDenied(ArtifactPublicError):
    """The requested Artifact is owned by another identity."""


class ArtifactNotPublishable(ArtifactPublicError):
    """The requested Artifact cannot be published."""


@dataclass(frozen=True)
class PublicationCandidate:
    artifact_id: str
    template: str


@dataclass(frozen=True)
class AttachmentSummary:
    attachment_id: str
    filename: str
    content_type: str
    size_bytes: int
    sha256: str
    created_by_identity_id: str
    created_at: str

    def to_payload(self) -> dict[str, object]:
        return {
            "attachment_id": self.attachment_id,
            "filename": self.filename,
            "content_type": self.content_type,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
            "created_by_identity_id": self.created_by_identity_id,
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class ArtifactReferenceMetadata:
    artifact_id: str
    template: str
    attachments: tuple[AttachmentSummary, ...]


@dataclass(frozen=True)
class EvidenceTarget:
    artifact_id: str
    author_identity_ids: tuple[str, ...]
