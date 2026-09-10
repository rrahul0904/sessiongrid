from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import uuid

from app.config import settings


@dataclass(frozen=True)
class StoredArtifact:
    storage_key: str
    size_bytes: int
    sha256: str
    content_type: str


class LocalArtifactStore:
    """Filesystem artifact provider used by the current single-node runtime.

    Only opaque relative storage keys leave this service. Production can swap
    this implementation for an S3-compatible store without changing artifact
    metadata or API contracts.
    """

    def __init__(self, root: Path | None = None) -> None:
        self.root = (root or settings.artifact_path).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def put(
        self,
        *,
        organization_id: int,
        profile_id: int,
        session_id: int | None,
        kind: str,
        content: bytes,
        content_type: str,
        extension: str,
    ) -> StoredArtifact:
        session_segment = str(session_id) if session_id is not None else "none"
        relative = Path(
            str(organization_id),
            str(profile_id),
            session_segment,
            f"{kind}-{uuid.uuid4().hex}.{extension.lstrip('.')}",
        )
        destination = (self.root / relative).resolve()
        if self.root not in destination.parents:
            raise ValueError("Artifact path escapes storage root")

        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(destination.suffix + ".tmp")
        temporary.write_bytes(content)
        os.replace(temporary, destination)

        return StoredArtifact(
            storage_key=relative.as_posix(),
            size_bytes=len(content),
            sha256=hashlib.sha256(content).hexdigest(),
            content_type=content_type,
        )

    def get(self, storage_key: str) -> bytes:
        path = (self.root / storage_key).resolve()
        if self.root not in path.parents:
            raise ValueError("Artifact path escapes storage root")
        return path.read_bytes()


artifact_store = LocalArtifactStore()
