"""
Tests for the flat study-by-part-of-speech commands (/study_nouns, /study_adjectives, ...)
"""

from unittest.mock import AsyncMock, Mock

import pytest
from telegram import Message, Update, User
from telegram.ext import ContextTypes

from src.core.database.database_manager import DatabaseManager
from src.core.handlers.command_handlers import CommandHandlers


class TestStudyPosFeature:
    """Test the flat /study_<pos> commands"""

    @pytest.fixture
    def mock_db_manager(self):
        mock_db = Mock(spec=DatabaseManager)
        mock_db.get_user_by_telegram_id.return_value = {
            "telegram_id": 123456789,
            "username": "testuser",
            "created_at": "2023-01-01",
        }
        mock_db.get_words_by_part_of_speech.return_value = [
            {
                "id": 1,
                "lemma": "Haus",
                "part_of_speech": "noun",
                "article": "das",
                "translation": "дом",
                "example": "Das Haus ist groß.",
                "repetitions": 0,
                "easiness_factor": 2.5,
                "interval_days": 1,
                "next_review_date": None,
                "last_reviewed": None,
            }
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

    def _mock_context(self):
        return Mock(spec=ContextTypes.DEFAULT_TYPE)

    @pytest.mark.parametrize(
        "command_name,expected_pos",
        [
            ("study_nouns_command", "noun"),
            ("study_adjectives_command", "adjective"),
            ("study_adverbs_command", "adverb"),
            ("study_pronouns_command", "pronoun"),
            ("study_prepositions_command", "preposition"),
            ("study_conjunctions_command", "conjunction"),
            ("study_numerals_command", "numeral"),
            ("study_interjections_command", "interjection"),
        ],
    )
    @pytest.mark.asyncio
    async def test_flat_pos_command_calls_correct_pos(
        self, command_handlers, mock_update, command_name, expected_pos
    ):
        command = getattr(command_handlers, command_name)
        await command(mock_update, self._mock_context())

        command_handlers.db_manager.get_words_by_part_of_speech.assert_called_once_with(
            123456789, expected_pos, limit=10
        )
        command_handlers._start_study_session.assert_called_once()

    @pytest.mark.asyncio
    async def test_study_pos_no_user(self, command_handlers, mock_update):
        command_handlers.db_manager.get_user_by_telegram_id.return_value = None

        await command_handlers.study_nouns_command(mock_update, self._mock_context())

        command_handlers._safe_reply.assert_called_once()
        call_args = command_handlers._safe_reply.call_args
        assert "❌ Пользователь не найден" in call_args[0][1]

    @pytest.mark.asyncio
    async def test_study_pos_no_words(self, command_handlers, mock_update):
        command_handlers.db_manager.get_words_by_part_of_speech.return_value = []

        await command_handlers.study_adjectives_command(
            mock_update, self._mock_context()
        )

        command_handlers._safe_reply.assert_called_once()
        call_args = command_handlers._safe_reply.call_args
        assert "нет слов с частью речи" in call_args[0][1]

    @pytest.mark.asyncio
    async def test_study_pos_no_effective_user(self, command_handlers):
        mock_update = Mock(spec=Update)
        mock_update.effective_user = None

        await command_handlers.study_nouns_command(mock_update, self._mock_context())

        command_handlers.db_manager.get_user_by_telegram_id.assert_not_called()
        command_handlers._safe_reply.assert_not_called()
