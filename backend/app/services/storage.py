"""Object storage for raw signal files.

Blueprint Section 14 rule, enforced here: raw bytes never enter the database.
This module returns a storage path; the DB stores that path and metadata only.

Local disk is the MVP backend. The interface is deliberately narrow so an
S3/MinIO implementation can slot in without touching callers.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Final

from fastapi import HTTPException, UploadFile, status

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger(__name__)

CHUNK_SIZE: Final[int] = 1024 * 1024

ALLOWED_AUDIO_EXTENSIONS: Final[set[str]] = {".wav", ".flac", ".ogg"}
ALLOWED_AUDIO_MIME: Final[set[str]] = {
    "audio/wav",
    "audio/x-wav",
    "audio/wave",
    "audio/vnd.wave",
    "audio/flac",
    "audio/x-flac",
    "audio/ogg",
    "application/octet-stream",  # browsers are inconsistent; extension+magic still checked
}

ALLOWED_ECG_EXTENSIONS: Final[set[str]] = {".csv", ".txt", ".dat", ".json"}

# Magic-byte prefixes. Extension and content-type are both client-controlled,
# so the file's actual header is checked too before it reaches the ML layer
# (Blueprint Section 25, file-upload validation).
AUDIO_MAGIC: Final[tuple[bytes, ...]] = (b"RIFF", b"fLaC", b"OggS")


def _reject(detail: str) -> None:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


def _target_dir(kind: str, screening_id: uuid.UUID) -> Path:
    d = settings.storage_root / kind / str(screening_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


async def save_audio_upload(file: UploadFile, screening_id: uuid.UUID) -> tuple[Path, int]:
    """Validate and persist a PCG upload. Returns (path, size_bytes)."""
    filename = file.filename or "recording.wav"
    ext = Path(filename).suffix.lower()

    if ext not in ALLOWED_AUDIO_EXTENSIONS:
        _reject(
            f"Unsupported audio format '{ext or 'unknown'}'. "
            f"Accepted: {', '.join(sorted(ALLOWED_AUDIO_EXTENSIONS))}."
        )
    if file.content_type and file.content_type not in ALLOWED_AUDIO_MIME:
        _reject(f"Unsupported content type '{file.content_type}'.")

    header = await file.read(4)
    if not header.startswith(AUDIO_MAGIC):
        _reject(
            "File contents are not a recognised audio container. The extension "
            "says audio but the file header does not."
        )
    await file.seek(0)

    dest = _target_dir("pcg", screening_id) / f"{uuid.uuid4().hex}{ext}"
    size = await _stream_to_disk(file, dest)
    log.info("pcg_upload_stored", screening_id=str(screening_id), size_bytes=size)
    return dest, size


ALLOWED_IMAGE_EXTENSIONS: Final[set[str]] = {
    ".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"
}


async def save_report_image(file: UploadFile, screening_id: uuid.UUID) -> tuple[Path, int]:
    """Persist an uploaded report photo for OCR extraction."""
    filename = file.filename or "report.jpg"
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        _reject(
            f"Unsupported image format '{ext or 'unknown'}'. "
            f"Accepted: {', '.join(sorted(ALLOWED_IMAGE_EXTENSIONS))}."
        )
    dest = _target_dir("reports", screening_id) / f"{uuid.uuid4().hex}{ext}"
    size = await _stream_to_disk(file, dest)
    log.info("report_image_stored", screening_id=str(screening_id), size_bytes=size)
    return dest, size


async def save_ecg_upload(file: UploadFile, screening_id: uuid.UUID) -> tuple[Path, int]:
    filename = file.filename or "ecg.csv"
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_ECG_EXTENSIONS:
        _reject(
            f"Unsupported ECG format '{ext or 'unknown'}'. "
            f"Accepted: {', '.join(sorted(ALLOWED_ECG_EXTENSIONS))}."
        )
    dest = _target_dir("ecg", screening_id) / f"{uuid.uuid4().hex}{ext}"
    size = await _stream_to_disk(file, dest)
    log.info("ecg_upload_stored", screening_id=str(screening_id), size_bytes=size)
    return dest, size


async def _stream_to_disk(file: UploadFile, dest: Path) -> int:
    """Stream in chunks, enforcing the size cap as we go.

    The cap is checked during the write rather than after: reading a 2 GB upload
    fully into memory to then reject it is its own denial-of-service.
    """
    size = 0
    limit = settings.max_upload_bytes
    try:
        with dest.open("wb") as out:
            while chunk := await file.read(CHUNK_SIZE):
                size += len(chunk)
                if size > limit:
                    out.close()
                    dest.unlink(missing_ok=True)
                    _reject(f"File exceeds the {settings.max_upload_mb} MB limit.")
                out.write(chunk)
    except HTTPException:
        raise
    except OSError as exc:
        dest.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail="Could not store the upload.") from exc

    if size == 0:
        dest.unlink(missing_ok=True)
        _reject("Uploaded file is empty.")
    return size


def relative_path(path: Path) -> str:
    """Store a path relative to the storage root, so the root can move."""
    try:
        return str(path.relative_to(settings.storage_root)).replace("\\", "/")
    except ValueError:
        return str(path)


def absolute_path(stored: str) -> Path:
    p = Path(stored)
    return p if p.is_absolute() else settings.storage_root / stored
