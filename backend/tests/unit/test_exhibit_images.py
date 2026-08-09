from datetime import UTC, datetime
from io import BytesIO

import pytest
from app.application.exhibit_images import (
    ExhibitImagePathError,
    ExhibitImageStorage,
    ExhibitImageTooLargeError,
    ExhibitImageTypeError,
    normalize_external_image_url,
    public_exhibit_image_url,
)
from app.domain.entities import Exhibit
from app.domain.value_objects import ExhibitId, Location
from fastapi import UploadFile
from PIL import Image
from starlette.datastructures import Headers

EXHIBIT_ID = "00000000-0000-0000-0000-000000000001"


def _png_bytes(*, size: tuple[int, int] = (8, 8)) -> bytes:
    output = BytesIO()
    Image.new("RGB", size, (145, 73, 42)).save(output, format="PNG")
    return output.getvalue()


def _upload(data: bytes, content_type: str = "image/png") -> UploadFile:
    return UploadFile(
        BytesIO(data),
        filename="untrusted-name.png",
        headers=Headers({"content-type": content_type}),
    )


@pytest.mark.asyncio
async def test_storage_validates_and_publishes_generated_relative_path(tmp_path):
    storage = ExhibitImageStorage(tmp_path, max_bytes=1_000_000, max_pixels=1_000_000)

    relative_path = await storage.store(EXHIBIT_ID, _upload(_png_bytes()))

    assert relative_path.startswith(f"{EXHIBIT_ID}/")
    assert relative_path.endswith(".png")
    assert storage.resolve(relative_path).is_file()
    assert storage.media_type(relative_path) == "image/png"


@pytest.mark.asyncio
async def test_storage_rejects_spoofed_and_oversized_uploads(tmp_path):
    storage = ExhibitImageStorage(tmp_path, max_bytes=32, max_pixels=1_000_000)

    with pytest.raises(ExhibitImageTypeError, match="signature"):
        await storage.store(EXHIBIT_ID, _upload(b"not an image"))

    with pytest.raises(ExhibitImageTooLargeError, match="byte limit"):
        await storage.store(EXHIBIT_ID, _upload(_png_bytes()))

    assert list(tmp_path.rglob("*.tmp")) == []


@pytest.mark.asyncio
async def test_storage_rejects_decoded_pixel_bomb_boundary(tmp_path):
    storage = ExhibitImageStorage(tmp_path, max_bytes=1_000_000, max_pixels=100)

    with pytest.raises(ExhibitImageTooLargeError, match="pixel limit"):
        await storage.store(EXHIBIT_ID, _upload(_png_bytes(size=(11, 10))))


def test_storage_rejects_path_traversal(tmp_path):
    storage = ExhibitImageStorage(tmp_path, max_bytes=1_000_000, max_pixels=1_000_000)

    with pytest.raises(ExhibitImagePathError):
        storage.resolve("../secret.png")
    with pytest.raises(ExhibitImagePathError):
        storage.resolve("/etc/passwd")


@pytest.mark.parametrize(
    "value",
    [
        "http://museum.example/image.png",
        "https://user:password@museum.example/image.png",
        "https://museum.example/image.png#fragment",
        "not-a-url",
    ],
)
def test_external_image_url_rejects_unsafe_or_ambiguous_values(value):
    with pytest.raises(ValueError):
        normalize_external_image_url(value)


def test_public_image_url_prefers_controlled_upload_path():
    now = datetime.now(UTC)
    exhibit = Exhibit(
        id=ExhibitId(EXHIBIT_ID),
        name="陶盆",
        description="介绍",
        location=Location(x=0, y=0, floor=1),
        hall="basic-exhibition-hall",
        category="陶器",
        era="新石器时代",
        importance=1,
        estimated_visit_time=60,
        document_id=None,
        is_active=True,
        created_at=now,
        updated_at=now,
        image_url="https://museum.example/image.png",
        image_path=f"{EXHIBIT_ID}/upload.png",
    )

    assert public_exhibit_image_url(exhibit) == f"/api/v1/exhibits/{EXHIBIT_ID}/image"
