"""Validation and controlled storage for exhibit images.

Uploaded files are addressed by generated names below a configured root.  The
database stores only a POSIX relative path; public APIs expose a stable API URL
instead of the filesystem location.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
import warnings
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit, urlunsplit
from uuid import UUID, uuid4

import aiofiles
from fastapi import UploadFile
from PIL import Image, UnidentifiedImageError

from app.domain.entities import Exhibit

IMAGE_API_PATH = "/api/v1/exhibits/{exhibit_id}/image"
UPLOAD_CHUNK_BYTES = 64 * 1024
ALLOWED_UPLOAD_CONTENT_TYPES = frozenset({"image/jpeg", "image/png", "image/webp", "application/octet-stream"})
FORMAT_METADATA = {
    "JPEG": (".jpg", "image/jpeg"),
    "PNG": (".png", "image/png"),
    "WEBP": (".webp", "image/webp"),
}


class ExhibitImageError(ValueError):
    """Base error for a rejected or unsafe exhibit image."""


class ExhibitImageTooLargeError(ExhibitImageError):
    """Raised when upload bytes or decoded pixels exceed configured limits."""


class ExhibitImageTypeError(ExhibitImageError):
    """Raised when the upload is not a supported, structurally valid image."""


class ExhibitImagePathError(ExhibitImageError):
    """Raised when a stored relative path escapes the configured root."""


def normalize_external_image_url(value: str | None) -> str | None:
    """Return a normalized absolute HTTPS URL, or ``None`` for an empty value."""
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    if len(normalized) > 2048:
        raise ValueError("image_url exceeds 2048 characters")
    parsed = urlsplit(normalized)
    if (
        parsed.scheme.lower() != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
    ):
        raise ValueError("image_url must be an absolute HTTPS URL without credentials or a fragment")
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("image_url contains an invalid port") from exc
    try:
        hostname = parsed.hostname.encode("idna").decode("ascii").lower()
    except UnicodeError as exc:
        raise ValueError("image_url contains an invalid hostname") from exc
    if ":" in hostname and not hostname.startswith("["):
        hostname = f"[{hostname}]"
    netloc = hostname if port is None else f"{hostname}:{port}"
    return urlunsplit(("https", netloc, parsed.path or "/", parsed.query, ""))


def public_exhibit_image_url(exhibit: Exhibit) -> str | None:
    """Map internal uploaded paths to the stable public API route."""
    if exhibit.image_path:
        return IMAGE_API_PATH.format(exhibit_id=exhibit.id.value)
    return exhibit.image_url


def _magic_format(header: bytes) -> str | None:
    if header.startswith(b"\xff\xd8\xff"):
        return "JPEG"
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "PNG"
    if len(header) >= 12 and header[:4] == b"RIFF" and header[8:12] == b"WEBP":
        return "WEBP"
    return None


def _inspect_image(path: Path, *, max_pixels: int) -> str:
    """Verify image structure and decoded dimensions without decoding pixels."""
    with path.open("rb") as file:
        header = file.read(16)
    magic_format = _magic_format(header)
    if magic_format is None:
        raise ExhibitImageTypeError("file signature is not JPEG, PNG, or WebP")

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(path) as image:
                if image.format != magic_format or image.format not in FORMAT_METADATA:
                    raise ExhibitImageTypeError("declared image format does not match its signature")
                if getattr(image, "n_frames", 1) != 1:
                    raise ExhibitImageTypeError("animated or multi-frame images are not supported")
                width, height = image.size
                if width <= 0 or height <= 0 or width * height > max_pixels:
                    raise ExhibitImageTooLargeError(f"decoded image exceeds the {max_pixels} pixel limit")
                image.verify()
    except ExhibitImageError:
        raise
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ExhibitImageTooLargeError("decoded image dimensions are unsafe") from exc
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as exc:
        raise ExhibitImageTypeError("image data is corrupt or unsupported") from exc
    return magic_format


def _fsync_file(path: Path) -> None:
    flags = os.O_RDWR | getattr(os, "O_BINARY", 0)
    descriptor = os.open(path, flags)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


class ExhibitImageStorage:
    """Store and resolve exhibit images below one configured filesystem root."""

    def __init__(self, root: str | Path, *, max_bytes: int, max_pixels: int):
        if max_bytes <= 0 or max_pixels <= 0:
            raise ValueError("image limits must be positive")
        self.root = Path(root).expanduser().resolve()
        self.max_bytes = max_bytes
        self.max_pixels = max_pixels

    def resolve(self, relative_path: str) -> Path:
        """Resolve a DB path while rejecting absolute paths, traversal, and symlinks out."""
        raw = PurePosixPath(relative_path)
        if raw.is_absolute() or not raw.parts or any(part in {"", ".", ".."} for part in raw.parts):
            raise ExhibitImagePathError("stored image path is not a safe relative path")
        candidate = self.root.joinpath(*raw.parts).resolve()
        if candidate != self.root and self.root not in candidate.parents:
            raise ExhibitImagePathError("stored image path escapes the configured root")
        return candidate

    async def store(self, exhibit_id: str, upload: UploadFile) -> str:
        """Validate, write, and atomically publish one uploaded image."""
        try:
            normalized_id = str(UUID(exhibit_id))
        except ValueError as exc:
            raise ExhibitImagePathError("exhibit ID is not a UUID") from exc
        content_type = (upload.content_type or "").lower()
        if content_type and content_type not in ALLOWED_UPLOAD_CONTENT_TYPES:
            raise ExhibitImageTypeError("Content-Type must be image/jpeg, image/png, or image/webp")

        exhibit_dir = self.root / normalized_id
        await asyncio.to_thread(exhibit_dir.mkdir, parents=True, exist_ok=True)
        temp_fd, temp_name = tempfile.mkstemp(
            prefix=".upload-",
            suffix=".tmp",
            dir=exhibit_dir,
        )
        os.close(temp_fd)
        temp_path = Path(temp_name)
        published_path: Path | None = None
        try:
            total = 0
            async with aiofiles.open(temp_path, "wb") as output:
                while chunk := await upload.read(UPLOAD_CHUNK_BYTES):
                    total += len(chunk)
                    if total > self.max_bytes:
                        raise ExhibitImageTooLargeError(f"image exceeds the {self.max_bytes} byte limit")
                    await output.write(chunk)
                await output.flush()
            if total == 0:
                raise ExhibitImageTypeError("image file is empty")

            image_format = await asyncio.to_thread(
                _inspect_image,
                temp_path,
                max_pixels=self.max_pixels,
            )
            extension, _ = FORMAT_METADATA[image_format]
            published_path = exhibit_dir / f"{uuid4().hex}{extension}"
            await asyncio.to_thread(_fsync_file, temp_path)
            await asyncio.to_thread(os.replace, temp_path, published_path)
            return published_path.relative_to(self.root).as_posix()
        except Exception:
            for path in (temp_path, published_path):
                if path is not None:
                    try:
                        await asyncio.to_thread(path.unlink, missing_ok=True)
                    except OSError:
                        pass
            raise

    async def delete(self, relative_path: str | None) -> None:
        """Delete only a safely resolved file below the configured root."""
        if not relative_path:
            return
        path = self.resolve(relative_path)
        await asyncio.to_thread(path.unlink, missing_ok=True)
        if path.parent != self.root:
            try:
                await asyncio.to_thread(path.parent.rmdir)
            except OSError:
                pass

    def media_type(self, relative_path: str) -> str:
        extension = self.resolve(relative_path).suffix.lower()
        for suffix, media_type in FORMAT_METADATA.values():
            if extension == suffix:
                return media_type
        raise ExhibitImageTypeError("stored image has an unsupported extension")
