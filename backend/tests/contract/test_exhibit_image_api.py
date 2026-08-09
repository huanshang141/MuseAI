from io import BytesIO

import pytest
from app.api.deps import get_current_admin_user, get_db_session
from app.application.exhibit_images import ExhibitImageStorage
from app.infra.postgres.database import get_session, get_session_maker
from app.infra.postgres.models import Base, Exhibit, Hall
from app.main import app
from httpx import ASGITransport, AsyncClient
from PIL import Image

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"
VISIBLE_ID = "00000000-0000-0000-0000-000000000101"
INACTIVE_HALL_ID = "00000000-0000-0000-0000-000000000102"
LEGACY_HALL_ID = "00000000-0000-0000-0000-000000000103"


def _png_bytes(color=(145, 73, 42)) -> bytes:
    output = BytesIO()
    Image.new("RGB", (8, 8), color).save(output, format="PNG")
    return output.getvalue()


@pytest.fixture
async def image_db_session():
    maker = get_session_maker(TEST_DATABASE_URL)
    async with get_session(maker) as session:
        engine = maker.kw["bind"]
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        session.add_all(
            [
                Hall(
                    slug="basic-exhibition-hall",
                    name="基本陈列展厅",
                    description="可信简介",
                    is_active=True,
                ),
                Hall(
                    slug="site-protection-hall",
                    name="遗址保护大厅",
                    description="停用厅",
                    is_active=False,
                ),
                Hall(
                    slug="legacy-image-hall",
                    name="旧图片厅",
                    description="非公开厅",
                    is_active=True,
                ),
                Exhibit(
                    id=VISIBLE_ID,
                    name="公开展品",
                    description="公开介绍",
                    hall="basic-exhibition-hall",
                    category="陶器",
                    is_active=True,
                ),
                Exhibit(
                    id=INACTIVE_HALL_ID,
                    name="停用厅展品",
                    description="不可公开",
                    hall="site-protection-hall",
                    category="陶器",
                    is_active=True,
                    image_path=f"{INACTIVE_HALL_ID}/hidden.png",
                ),
                Exhibit(
                    id=LEGACY_HALL_ID,
                    name="旧厅展品",
                    description="不可公开",
                    hall="legacy-image-hall",
                    category="陶器",
                    is_active=True,
                    image_path=f"{LEGACY_HALL_ID}/hidden.png",
                ),
            ]
        )
        await session.commit()
        yield session


@pytest.fixture
def image_api_overrides(image_db_session, tmp_path, monkeypatch):
    storage = ExhibitImageStorage(tmp_path, max_bytes=1_000_000, max_pixels=1_000_000)

    async def override_db():
        yield image_db_session

    app.dependency_overrides[get_db_session] = override_db
    monkeypatch.setattr("app.api.exhibits.get_exhibit_image_storage", lambda: storage)
    monkeypatch.setattr("app.api.admin.exhibits.get_exhibit_image_storage", lambda: storage)
    yield storage
    app.dependency_overrides.pop(get_db_session, None)
    app.dependency_overrides.pop(get_current_admin_user, None)


@pytest.mark.asyncio
async def test_admin_upload_replace_public_read_and_delete(
    image_db_session,
    image_api_overrides,
):
    app.dependency_overrides[get_current_admin_user] = lambda: {
        "id": "admin-id",
        "email": "test@test.com",
        "role": "admin",
    }
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        first = await client.post(
            f"/api/v1/admin/exhibits/{VISIBLE_ID}/image",
            files={"file": ("spoofed-name.txt", _png_bytes(), "image/png")},
        )
        assert first.status_code == 200
        assert first.json() == {"image_url": f"/api/v1/exhibits/{VISIBLE_ID}/image"}

        listed = await client.get("/api/v1/exhibits")
        assert listed.status_code == 200
        assert listed.json()["exhibits"][0]["image_url"] == f"/api/v1/exhibits/{VISIBLE_ID}/image"

        image = await client.get(f"/api/v1/exhibits/{VISIBLE_ID}/image")
        assert image.status_code == 200
        assert image.headers["content-type"] == "image/png"
        assert image.headers["x-content-type-options"] == "nosniff"
        assert image.content == _png_bytes()

        stored_before = (await image_db_session.get(Exhibit, VISIBLE_ID)).image_path
        second = await client.post(
            f"/api/v1/admin/exhibits/{VISIBLE_ID}/image",
            files={"file": ("replacement.png", _png_bytes((52, 94, 76)), "image/png")},
        )
        assert second.status_code == 200
        stored_after = (await image_db_session.get(Exhibit, VISIBLE_ID)).image_path
        assert stored_after != stored_before
        assert not image_api_overrides.resolve(stored_before).exists()

        deleted = await client.delete(f"/api/v1/admin/exhibits/{VISIBLE_ID}/image")
        assert deleted.status_code == 200
        assert deleted.json() == {"image_url": None}

    await image_db_session.refresh(await image_db_session.get(Exhibit, VISIBLE_ID))
    exhibit = await image_db_session.get(Exhibit, VISIBLE_ID)
    assert exhibit.image_url is None
    assert exhibit.image_path is None
    assert not image_api_overrides.resolve(stored_after).exists()


@pytest.mark.asyncio
async def test_upload_requires_admin_and_rejects_spoofed_content(image_api_overrides):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        unauthenticated = await client.post(
            f"/api/v1/admin/exhibits/{VISIBLE_ID}/image",
            files={"file": ("image.png", _png_bytes(), "image/png")},
        )
        assert unauthenticated.status_code == 401

        app.dependency_overrides[get_current_admin_user] = lambda: {
            "id": "admin-id",
            "email": "test@test.com",
            "role": "admin",
        }
        spoofed = await client.post(
            f"/api/v1/admin/exhibits/{VISIBLE_ID}/image",
            files={"file": ("image.png", b"not an image", "image/png")},
        )
        assert spoofed.status_code == 415


@pytest.mark.asyncio
async def test_admin_can_set_only_an_absolute_https_external_image(image_db_session, image_api_overrides):
    app.dependency_overrides[get_current_admin_user] = lambda: {
        "id": "admin-id",
        "email": "test@test.com",
        "role": "admin",
    }
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        rejected = await client.put(
            f"/api/v1/admin/exhibits/{VISIBLE_ID}",
            json={"image_url": "http://museum.example/image.png"},
        )
        assert rejected.status_code == 422

        accepted = await client.put(
            f"/api/v1/admin/exhibits/{VISIBLE_ID}",
            json={"image_url": "https://museum.example/image.png"},
        )
        assert accepted.status_code == 200
        assert accepted.json()["image_url"] == "https://museum.example/image.png"

        public = await client.get("/api/v1/exhibits")
        assert public.json()["exhibits"][0]["image_url"] == "https://museum.example/image.png"

    exhibit = await image_db_session.get(Exhibit, VISIBLE_ID)
    assert exhibit.image_url == "https://museum.example/image.png"
    assert exhibit.image_path is None


@pytest.mark.asyncio
@pytest.mark.parametrize("exhibit_id", [INACTIVE_HALL_ID, LEGACY_HALL_ID])
async def test_public_image_get_hides_disabled_and_noncanonical_halls(
    exhibit_id,
    image_api_overrides,
):
    hidden_path = image_api_overrides.resolve(f"{exhibit_id}/hidden.png")
    hidden_path.parent.mkdir(parents=True, exist_ok=True)
    hidden_path.write_bytes(_png_bytes())

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(f"/api/v1/exhibits/{exhibit_id}/image")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_exhibit_removes_committed_local_image(
    image_db_session,
    image_api_overrides,
):
    app.dependency_overrides[get_current_admin_user] = lambda: {
        "id": "admin-id",
        "email": "test@test.com",
        "role": "admin",
    }
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        uploaded = await client.post(
            f"/api/v1/admin/exhibits/{VISIBLE_ID}/image",
            files={"file": ("image.png", _png_bytes(), "image/png")},
        )
        assert uploaded.status_code == 200
        stored_path = (await image_db_session.get(Exhibit, VISIBLE_ID)).image_path

        deleted = await client.delete(f"/api/v1/admin/exhibits/{VISIBLE_ID}")

    assert deleted.status_code == 200
    assert await image_db_session.get(Exhibit, VISIBLE_ID) is None
    assert not image_api_overrides.resolve(stored_path).exists()
