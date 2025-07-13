"""
Tests for user authorization functionality
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from telegram import Update, User
from telegram.ext import ContextTypes

from src.bot_handler import BotHandler
from src.config import Settings


class TestUserAuthorization:
    """Test user authorization functionality"""

    def test_is_user_authorized_empty_list(self):
        """Test authorization when no users are configured - should disallow all"""
        settings = Settings(
            telegram_bot_token="test_token",
            openai_api_key="test_key",
            allowed_users=""
        )
        handler = BotHandler(settings)

        # Should disallow any user when list is empty
        assert not handler._is_user_authorized(321)
        assert not handler._is_user_authorized(123)

    def test_is_user_authorized_with_allowed_users(self):
        """Test authorization with specific allowed users"""
        settings = Settings(
            telegram_bot_token="test_token",
            openai_api_key="test_key",
            allowed_users="321,123"
        )
        handler = BotHandler(settings)

        # Should allow users in the list
        assert handler._is_user_authorized(321)
        assert handler._is_user_authorized(123)

        # Should deny users not in the list
        assert not handler._is_user_authorized(111)
        assert not handler._is_user_authorized(222)

    @pytest.mark.asyncio
    async def test_check_authorization_allowed_user(self):
        """Test authorization check for allowed user"""
        settings = Settings(
            telegram_bot_token="test_token",
            openai_api_key="test_key",
            allowed_users="321"
        )
        handler = BotHandler(settings)

        # Mock update and context
        user = User(id=321, is_bot=False, first_name="Test")
        update = MagicMock(spec=Update)
        update.effective_user = user
        context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)

        # Mock _safe_reply to avoid actual message sending
        handler._safe_reply = AsyncMock()

        # Should return True for allowed user
        result = await handler._check_authorization(update, context)
        assert result is True

        # Should not send any message
        handler._safe_reply.assert_not_called()

    @pytest.mark.asyncio
    async def test_check_authorization_denied_user(self):
        """Test authorization check for denied user"""
        settings = Settings(
            telegram_bot_token="test_token",
            openai_api_key="test_key",
            allowed_users="321"
        )
        handler = BotHandler(settings)

        # Mock update and context
        user = User(id=999, is_bot=False, first_name="Unauthorized")
        update = MagicMock(spec=Update)
        update.effective_user = user
        context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)

        # Mock _safe_reply to avoid actual message sending
        handler._safe_reply = AsyncMock()

        # Should return False for denied user
        result = await handler._check_authorization(update, context)
        assert result is False

        # Should send unauthorized message
        handler._safe_reply.assert_called_once()
        call_args = handler._safe_reply.call_args
        assert "У вас нет доступа к этому боту" in call_args[0][1]

    @pytest.mark.asyncio
    async def test_authorization_decorator_allowed_user(self):
        """Test authorization decorator with allowed user"""
        settings = Settings(
            telegram_bot_token="test_token",
            openai_api_key="test_key",
            allowed_users="321"
        )
        handler = BotHandler(settings)

        # Mock update and context
        user = User(id=321, is_bot=False, first_name="Test")
        update = MagicMock(spec=Update)
        update.effective_user = user
        context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)

        # Mock _safe_reply
        handler._safe_reply = AsyncMock()

        # Create a mock handler function
        mock_handler = AsyncMock()
        decorated_handler = handler.require_authorization(mock_handler)

        # Call the decorated handler
        await decorated_handler(update, context)

        # Should call the original handler
        mock_handler.assert_called_once_with(update, context)

    @pytest.mark.asyncio
    async def test_authorization_decorator_denied_user(self):
        """Test authorization decorator with denied user"""
        settings = Settings(
            telegram_bot_token="test_token",
            openai_api_key="test_key",
            allowed_users="321"
        )
        handler = BotHandler(settings)

        # Mock update and context
        user = User(id=999, is_bot=False, first_name="Unauthorized")
        update = MagicMock(spec=Update)
        update.effective_user = user
        context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)

        # Mock _safe_reply
        handler._safe_reply = AsyncMock()

        # Create a mock handler function
        mock_handler = AsyncMock()
        decorated_handler = handler.require_authorization(mock_handler)

        # Call the decorated handler
        await decorated_handler(update, context)

        # Should NOT call the original handler
        mock_handler.assert_not_called()

        # Should send unauthorized message
        handler._safe_reply.assert_called_once()

    def test_config_parse_allowed_users_string(self):
        """Test parsing allowed users from comma-separated string"""
        settings = Settings(
            telegram_bot_token="test_token",
            openai_api_key="test_key",
            allowed_users="321,123,456"
        )

        expected_users = [321, 123, 456]
        assert settings.allowed_users_list == expected_users

    def test_config_parse_allowed_users_empty_string(self):
        """Test parsing allowed users from empty string - should disallow all"""
        settings = Settings(
            telegram_bot_token="test_token",
            openai_api_key="test_key",
            allowed_users=""
        )

        assert settings.allowed_users_list == []

        # Verify empty list means no access
        handler = BotHandler(settings)
        assert not handler._is_user_authorized(321)

    def test_config_parse_allowed_users_with_spaces(self):
        """Test parsing allowed users with spaces"""
        settings = Settings(
            telegram_bot_token="test_token",
            openai_api_key="test_key",
            allowed_users="321, 123 , 456"
        )

        expected_users = [321, 123, 456]
        assert settings.allowed_users_list == expected_users
