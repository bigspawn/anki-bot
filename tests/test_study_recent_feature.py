"""
Tests for the study_recent feature (study last N added words)
"""

from unittest.mock import AsyncMock, Mock

import pytest
from telegram import Message, Update, User
from telegram.ext import ContextTypes

from src.core.database.database_manager import DatabaseManager
from src.core.handlers.command_handlers import CommandHandlers


class TestStudyRecentFeature:
    """Test the study_recent feature"""

    @pytest.fixture
    def mock_db_manager(self):
        mock_db = Mock(spec=DatabaseManager)
        mock_db.get_user_by_telegram_id.return_value = {
            "telegram_id": 123456789,
            "username": "testuser",
            "created_at": "2023-01-01",
        }
        mock_db.get_recent_words.return_value = [
            {
                "id": 2,
                "lemma": "Vegetation",
                "part_of_speech": "noun",
                "article": "die",
                "translation": "растительность",
                "example": "Die Vegetation ist vielfältig.",
                "repetitions": 0,
                "easiness_factor": 2.5,
                "interval_days": 1,
                "next_review_date": None,
                "last_reviewed": None,
            },
            {
                "id": 1,
                "lemma": "stolz",
                "part_of_speech": "adjective",
                "article": None,
                "translation": "гордый",
                "example": "Er ist stolz.",
                "repetitions": 0,
                "easiness_factor": 2.5,
                "interval_days": 1,
                "next_review_date": None,
                "last_reviewed": None,
            },
        ]
        return mock_db

    @pytest.fixture
    def command_handlers(self, mock_db_manager):
        handlers = CommandHandlers(
            db_manager=mock_db_manager,
            word_processor=Mock(),
            text_parser=Mock(),
            srs_system=Mock(),
            safe_reply_callback=AsyncMock(),
            process_text_callback=AsyncMock(),
            start_study_session_callback=AsyncMock(),
            state_manager=Mock(),
            session_manager=Mock(),
        )
        handlers._safe_reply = AsyncMock()
        handlers._start_study_session = AsyncMock()
        return handlers

    @pytest.fixture
    def mock_update(self):
        update = Mock(spec=Update)
        update.effective_user = Mock(spec=User)
        update.effective_user.id = 123456789
        update.effective_user.username = "testuser"
        update.message = Mock(spec=Message)
        return update

    def _mock_context(self, args=None):
        context = Mock(spec=ContextTypes.DEFAULT_TYPE)
        context.args = args or []
        return context

    @pytest.mark.asyncio
    async def test_study_recent_default_limit(self, command_handlers, mock_update):
        await command_handlers.study_recent_command(mock_update, self._mock_context())

        command_handlers.db_manager.get_recent_words.assert_called_once_with(
            123456789, limit=10
        )
        command_handlers._start_study_session.assert_called_once()

    @pytest.mark.asyncio
    async def test_study_recent_custom_limit(self, command_handlers, mock_update):
        await command_handlers.study_recent_command(
            mock_update, self._mock_context(["50"])
        )

        command_handlers.db_manager.get_recent_words.assert_called_once_with(
            123456789, limit=50
        )

    @pytest.mark.asyncio
    async def test_study_recent_limit_clamped_to_max(
        self, command_handlers, mock_update
    ):
        await command_handlers.study_recent_command(
            mock_update, self._mock_context(["9999"])
        )

        command_handlers.db_manager.get_recent_words.assert_called_once_with(
            123456789, limit=200
        )

    @pytest.mark.asyncio
    async def test_study_recent_invalid_arg(self, command_handlers, mock_update):
        await command_handlers.study_recent_command(
            mock_update, self._mock_context(["abc"])
        )

        command_handlers.db_manager.get_recent_words.assert_not_called()
        command_handlers._safe_reply.assert_called_once()
        call_args = command_handlers._safe_reply.call_args
        assert "Укажите число слов" in call_args[0][1]

    @pytest.mark.asyncio
    async def test_study_recent_no_user(self, command_handlers, mock_update):
        command_handlers.db_manager.get_user_by_telegram_id.return_value = None

        await command_handlers.study_recent_command(mock_update, self._mock_context())

        command_handlers._safe_reply.assert_called_once()
        call_args = command_handlers._safe_reply.call_args
        assert "❌ Пользователь не найден" in call_args[0][1]

    @pytest.mark.asyncio
    async def test_study_recent_no_words(self, command_handlers, mock_update):
        command_handlers.db_manager.get_recent_words.return_value = []

        await command_handlers.study_recent_command(mock_update, self._mock_context())

        command_handlers._safe_reply.assert_called_once()
        call_args = command_handlers._safe_reply.call_args
        assert "нет добавленных слов" in call_args[0][1]

    @pytest.mark.asyncio
    async def test_study_recent_no_effective_user(self, command_handlers):
        mock_update = Mock(spec=Update)
        mock_update.effective_user = None

        await command_handlers.study_recent_command(mock_update, self._mock_context())

        command_handlers.db_manager.get_user_by_telegram_id.assert_not_called()
        command_handlers._safe_reply.assert_not_called()
