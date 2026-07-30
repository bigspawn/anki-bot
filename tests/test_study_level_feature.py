"""
Tests for the flat study-by-level commands (/study_a1, /study_a2, ...) and
study_common_verbs feature (topic/rubric study)
"""

from unittest.mock import AsyncMock, Mock

import pytest
from telegram import Message, Update, User
from telegram.ext import ContextTypes

from src.core.database.database_manager import DatabaseManager
from src.core.handlers.command_handlers import COMMON_VERBS, CommandHandlers


class _BaseFixtures:
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

    def _mock_context(self):
        return Mock(spec=ContextTypes.DEFAULT_TYPE)


class TestStudyLevelFeature(_BaseFixtures):
    """Test the flat /study_<level> commands"""

    @pytest.fixture
    def mock_db_manager(self):
        mock_db = Mock(spec=DatabaseManager)
        mock_db.get_user_by_telegram_id.return_value = {
            "telegram_id": 123456789,
            "username": "testuser",
            "created_at": "2023-01-01",
        }
        mock_db.get_words_by_level.return_value = [
            {
                "id": 1,
                "lemma": "Haus",
                "part_of_speech": "noun",
                "article": "das",
                "translation": "дом",
                "example": "Das Haus ist groß.",
                "level": "A1",
                "repetitions": 0,
                "easiness_factor": 2.5,
                "interval_days": 1,
                "next_review_date": None,
                "last_reviewed": None,
            }
        ]
        return mock_db

    @pytest.mark.parametrize(
        "command_name,expected_level",
        [
            ("study_a1_command", "A1"),
            ("study_a2_command", "A2"),
            ("study_b1_command", "B1"),
            ("study_b2_command", "B2"),
            ("study_c1_command", "C1"),
            ("study_c2_command", "C2"),
        ],
    )
    @pytest.mark.asyncio
    async def test_flat_level_command_calls_correct_level(
        self, command_handlers, mock_update, command_name, expected_level
    ):
        command = getattr(command_handlers, command_name)
        await command(mock_update, self._mock_context())

        command_handlers.db_manager.get_words_by_level.assert_called_once_with(
            123456789, expected_level, limit=10
        )
        command_handlers._start_study_session.assert_called_once()

    @pytest.mark.asyncio
    async def test_study_level_no_words(self, command_handlers, mock_update):
        command_handlers.db_manager.get_words_by_level.return_value = []

        await command_handlers.study_b2_command(mock_update, self._mock_context())

        call_args = command_handlers._safe_reply.call_args
        assert "нет слов уровня" in call_args[0][1]

    @pytest.mark.asyncio
    async def test_study_level_no_user(self, command_handlers, mock_update):
        command_handlers.db_manager.get_user_by_telegram_id.return_value = None

        await command_handlers.study_a1_command(mock_update, self._mock_context())

        call_args = command_handlers._safe_reply.call_args
        assert "❌ Пользователь не найден" in call_args[0][1]

    @pytest.mark.asyncio
    async def test_study_level_no_effective_user(self, command_handlers):
        mock_update = Mock(spec=Update)
        mock_update.effective_user = None

        await command_handlers.study_a1_command(mock_update, self._mock_context())

        command_handlers.db_manager.get_user_by_telegram_id.assert_not_called()
        command_handlers._safe_reply.assert_not_called()


class TestStudyCommonVerbsFeature(_BaseFixtures):
    """Test the study_common_verbs feature"""

    @pytest.fixture
    def mock_db_manager(self):
        mock_db = Mock(spec=DatabaseManager)
        mock_db.get_user_by_telegram_id.return_value = {
            "telegram_id": 123456789,
            "username": "testuser",
            "created_at": "2023-01-01",
        }
        mock_db.get_words_by_lemma_set.return_value = [
            {
                "id": 1,
                "lemma": "gehen",
                "part_of_speech": "verb",
                "article": None,
                "translation": "идти",
                "example": "Ich gehe nach Hause.",
                "repetitions": 0,
                "easiness_factor": 2.5,
                "interval_days": 1,
                "next_review_date": None,
                "last_reviewed": None,
            }
        ]
        return mock_db

    @pytest.mark.asyncio
    async def test_study_common_verbs_success(self, command_handlers, mock_update):
        await command_handlers.study_common_verbs_command(
            mock_update, self._mock_context()
        )

        command_handlers.db_manager.get_words_by_lemma_set.assert_called_once_with(
            123456789, COMMON_VERBS, limit=10
        )
        command_handlers._start_study_session.assert_called_once()

    @pytest.mark.asyncio
    async def test_study_common_verbs_no_words(self, command_handlers, mock_update):
        command_handlers.db_manager.get_words_by_lemma_set.return_value = []

        await command_handlers.study_common_verbs_command(
            mock_update, self._mock_context()
        )

        call_args = command_handlers._safe_reply.call_args
        assert "нет популярных глаголов" in call_args[0][1]

    @pytest.mark.asyncio
    async def test_study_common_verbs_no_user(self, command_handlers, mock_update):
        command_handlers.db_manager.get_user_by_telegram_id.return_value = None

        await command_handlers.study_common_verbs_command(
            mock_update, self._mock_context()
        )

        call_args = command_handlers._safe_reply.call_args
        assert "❌ Пользователь не найден" in call_args[0][1]

    @pytest.mark.asyncio
    async def test_study_common_verbs_no_effective_user(self, command_handlers):
        mock_update = Mock(spec=Update)
        mock_update.effective_user = None

        await command_handlers.study_common_verbs_command(
            mock_update, self._mock_context()
        )

        command_handlers.db_manager.get_user_by_telegram_id.assert_not_called()
        command_handlers._safe_reply.assert_not_called()
