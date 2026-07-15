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

        no_admin_result = MagicMock()
        no_admin_result.scalar_one_or_none.return_value = None
        no_user_result = MagicMock()
        no_user_result.scalar_one_or_none.return_value = None

        mock_session = MagicMock()
        mock_session.execute = AsyncMock(
            side_effect=[no_admin_result, no_user_result]
        )
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

        no_admin_result = MagicMock()
        no_admin_result.scalar_one_or_none.return_value = None
        existing_user_result = MagicMock()
        existing_user_result.scalar_one_or_none.return_value = existing_user

        mock_session = MagicMock()
        mock_session.execute = AsyncMock(
            side_effect=[no_admin_result, existing_user_result]
        )
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

        existing_user.email = "admin@museai.local"
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

    @pytest.mark.parametrize(
        "password,missing",
        [
            ("lowercase123!", "uppercase"),
            ("UPPERCASE123!", "lowercase"),
            ("NoDigitsHere!!", "digit"),
            ("NoSpecial12345", "special"),
        ],
    )
    def test_bootstrap_admin_requires_each_password_character_class(self, password, missing):
        module = self._load_module()

        with pytest.raises(ValueError, match=missing):
            module._validate_password(password)

    def test_resolve_password_prefers_environment_over_prompt(self, monkeypatch):
        module = self._load_module()
        monkeypatch.setenv("MUSEAI_ADMIN_PASSWORD", "AdminFromEnv123!")
        monkeypatch.setattr(module.getpass, "getpass", MagicMock())

        assert module._resolve_password(None) == "AdminFromEnv123!"
        module.getpass.getpass.assert_not_called()

    def test_resolve_password_prompts_without_cli_or_environment(self, monkeypatch):
        module = self._load_module()
        monkeypatch.delenv("MUSEAI_ADMIN_PASSWORD", raising=False)
        monkeypatch.setattr(module.getpass, "getpass", MagicMock(return_value="PromptedAdmin123!"))

        assert module._resolve_password(None) == "PromptedAdmin123!"

    @pytest.mark.asyncio
    async def test_bootstrap_admin_rejects_second_admin_account(self):
        module = self._load_module()

        existing_admin = MagicMock()
        existing_admin.role = "admin"
        existing_admin.email = "first-admin@museai.local"
        result = MagicMock()
        result.scalar_one_or_none.return_value = existing_admin

        mock_session = MagicMock()
        mock_session.execute = AsyncMock(return_value=result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_sm_instance = MagicMock(return_value=mock_session)

        with patch.object(module, "async_sessionmaker", return_value=mock_sm_instance):
            with patch.object(module, "create_async_engine") as mock_engine:
                mock_engine.return_value = MagicMock(dispose=AsyncMock())
                with pytest.raises(ValueError, match="already exists"):
                    await module.bootstrap_admin(
                        database_url="sqlite+aiosqlite:///:memory:",
                        email="second-admin@museai.local",
                        password="AdminPass123!@#",
                    )
