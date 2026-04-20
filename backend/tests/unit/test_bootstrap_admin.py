import importlib
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))


SCRIPT_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "scripts", "bootstrap_admin.py")
)


class TestBootstrapAdmin:
    @staticmethod
    def _load_module():
        spec = importlib.util.spec_from_file_location("bootstrap_admin", SCRIPT_PATH)
        assert spec is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_bootstrap_admin_script_exists(self):
        module = self._load_module()
        assert hasattr(module, "bootstrap_admin")

    @pytest.mark.asyncio
    async def test_bootstrap_admin_creates_admin_user(self):
        module = self._load_module()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_session = MagicMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        mock_sm_instance = MagicMock(return_value=mock_session)

        with patch.object(module, "async_sessionmaker", return_value=mock_sm_instance):
            with patch.object(module, "create_async_engine") as mock_engine:
                mock_engine.return_value = MagicMock(dispose=AsyncMock())

                await module.bootstrap_admin(
                    database_url="sqlite+aiosqlite:///:memory:",
                    email="admin@museai.local",
                    password="AdminPass123!@#",
                )

        mock_session.add.assert_called_once()
        added_user = mock_session.add.call_args[0][0]
        assert isinstance(added_user, module.User)
        assert added_user.email == "admin@museai.local"
        assert added_user.role == "admin"

    @pytest.mark.asyncio
    async def test_bootstrap_admin_promotes_existing_non_admin_user(self):
        module = self._load_module()

        existing_user = MagicMock()
        existing_user.role = "user"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_user

        mock_session = MagicMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        mock_sm_instance = MagicMock(return_value=mock_session)

        with patch.object(module, "async_sessionmaker", return_value=mock_sm_instance):
            with patch.object(module, "create_async_engine") as mock_engine:
                mock_engine.return_value = MagicMock(dispose=AsyncMock())

                await module.bootstrap_admin(
                    database_url="sqlite+aiosqlite:///:memory:",
                    email="admin@museai.local",
                    password="AdminPass123!@#",
                )

        assert existing_user.role == "admin"
        mock_session.commit.assert_awaited_once()
        mock_session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_bootstrap_admin_keeps_existing_admin_user(self):
        module = self._load_module()

        existing_user = MagicMock()
        existing_user.role = "admin"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_user

        mock_session = MagicMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        mock_sm_instance = MagicMock(return_value=mock_session)

        with patch.object(module, "async_sessionmaker", return_value=mock_sm_instance):
            with patch.object(module, "create_async_engine") as mock_engine:
                mock_engine.return_value = MagicMock(dispose=AsyncMock())

                await module.bootstrap_admin(
                    database_url="sqlite+aiosqlite:///:memory:",
                    email="admin@museai.local",
                    password="AdminPass123!@#",
                )

        mock_session.commit.assert_not_awaited()
        mock_session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_bootstrap_admin_rejects_weak_password(self):
        module = self._load_module()

        with pytest.raises(ValueError, match="[Pp]assword"):
            await module.bootstrap_admin(
                database_url="sqlite+aiosqlite:///:memory:",
                email="admin@museai.local",
                password="short",
            )
