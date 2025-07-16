"""
Tests for the message editing bug fix
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from telegram.error import TelegramError

from src.bot_handler import BotHandler


class TestMessageEditingBugFix:
    """Test the fix for message editing errors"""

    @pytest.fixture
    def bot_handler(self):
        """Create a minimal bot handler for testing"""
        # Create a minimal instance just to test the _safe_edit_message method
        handler = BotHandler.__new__(BotHandler)
        return handler

    @pytest.mark.asyncio
    async def test_safe_edit_message_success(self, bot_handler):
        """Test successful message editing"""
        # Create a mock message
        mock_message = Mock()
        mock_message.edit_text = AsyncMock(return_value=Mock())

        # Test successful edit
        result = await bot_handler._safe_edit_message(mock_message, "Test message")

        # Verify edit was called and succeeded
        mock_message.edit_text.assert_called_once_with("Test message")
        assert result is not None

    @pytest.mark.asyncio
    async def test_safe_edit_message_fallback_to_reply(self, bot_handler):
        """Test fallback to reply when edit fails"""
        # Create a mock message
        mock_message = Mock()
        mock_message.edit_text = AsyncMock(
            side_effect=TelegramError("Message can't be edited")
        )
        mock_message.reply_text = AsyncMock(return_value=Mock())

        # Test edit with fallback
        result = await bot_handler._safe_edit_message(mock_message, "Test message")

        # Verify edit was attempted and fallback was used
        mock_message.edit_text.assert_called_once_with("Test message")
        mock_message.reply_text.assert_called_once_with("Test message")
        assert result is not None

    @pytest.mark.asyncio
    async def test_safe_edit_message_both_fail(self, bot_handler):
        """Test when both edit and reply fail"""
        # Create a mock message
        mock_message = Mock()
        mock_message.edit_text = AsyncMock(
            side_effect=TelegramError("Message can't be edited")
        )
        mock_message.reply_text = AsyncMock(side_effect=TelegramError("Reply failed"))

        # Test when both fail
        result = await bot_handler._safe_edit_message(mock_message, "Test message")

        # Verify both were attempted and None was returned
        mock_message.edit_text.assert_called_once_with("Test message")
        mock_message.reply_text.assert_called_once_with("Test message")
        assert result is None

    @pytest.mark.asyncio
    async def test_safe_edit_message_with_kwargs(self, bot_handler):
        """Test safe edit with additional kwargs"""
        # Create a mock message
        mock_message = Mock()
        mock_message.edit_text = AsyncMock(return_value=Mock())

        # Test with kwargs
        result = await bot_handler._safe_edit_message(
            mock_message, "Test message", parse_mode="HTML", reply_markup=None
        )

        # Verify kwargs were passed
        mock_message.edit_text.assert_called_once_with(
            "Test message", parse_mode="HTML", reply_markup=None
        )
        assert result is not None

    @pytest.mark.asyncio
    async def test_safe_edit_message_fallback_with_kwargs(self, bot_handler):
        """Test fallback with kwargs when edit fails"""
        # Create a mock message
        mock_message = Mock()
        mock_message.edit_text = AsyncMock(
            side_effect=TelegramError("Message can't be edited")
        )
        mock_message.reply_text = AsyncMock(return_value=Mock())

        # Test with kwargs
        result = await bot_handler._safe_edit_message(
            mock_message, "Test message", parse_mode="HTML", reply_markup=None
        )

        # Verify kwargs were passed to both methods
        mock_message.edit_text.assert_called_once_with(
            "Test message", parse_mode="HTML", reply_markup=None
        )
        mock_message.reply_text.assert_called_once_with(
            "Test message", parse_mode="HTML", reply_markup=None
        )
        assert result is not None

    @pytest.mark.asyncio
    async def test_safe_edit_message_logging_level(self, bot_handler):
        """Test that edit failures are logged at debug level, not error"""
        # Create a mock message
        mock_message = Mock()
        mock_message.edit_text = AsyncMock(
            side_effect=TelegramError("Message can't be edited")
        )
        mock_message.reply_text = AsyncMock(return_value=Mock())

        # Test with logger patching
        with patch("src.bot_handler.logger") as mock_logger:
            result = await bot_handler._safe_edit_message(mock_message, "Test message")

            # Verify debug level is used for edit failure, not error
            mock_logger.debug.assert_called_once_with(
                "Message edit failed: Message can't be edited"
            )
            mock_logger.error.assert_not_called()
            assert result is not None

    @pytest.mark.asyncio
    async def test_safe_edit_message_no_fallback(self, bot_handler):
        """Test that use_fallback=False doesn't send fallback message"""
        # Create a mock message
        mock_message = Mock()
        mock_message.edit_text = AsyncMock(
            side_effect=TelegramError("Message can't be edited")
        )
        mock_message.reply_text = AsyncMock(return_value=Mock())

        # Test with use_fallback=False
        result = await bot_handler._safe_edit_message(
            mock_message, "Test message", use_fallback=False
        )

        # Verify edit was attempted but no fallback was used
        mock_message.edit_text.assert_called_once_with("Test message")
        mock_message.reply_text.assert_not_called()

        # Verify result is None (failed silently)
        assert result is None

    @pytest.mark.asyncio
    async def test_safe_edit_message_no_fallback_logging(self, bot_handler):
        """Test that use_fallback=False logs appropriately"""
        # Create a mock message
        mock_message = Mock()
        mock_message.edit_text = AsyncMock(
            side_effect=TelegramError("Message can't be edited")
        )

        # Test with logging capture
        with patch("src.bot_handler.logger") as mock_logger:
            result = await bot_handler._safe_edit_message(
                mock_message, "Test message", use_fallback=False
            )

            # Verify debug logging was used for edit failure
            mock_logger.debug.assert_called_with(
                "Message edit failed, no fallback used: Message can't be edited"
            )

            # Verify no error logging
            mock_logger.error.assert_not_called()

            # Verify result is None
            assert result is None
