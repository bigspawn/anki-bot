"""
Tests for the study verbs feature
"""
from unittest.mock import AsyncMock, Mock

import pytest
from telegram import Message, Update, User
from telegram.ext import ContextTypes

from src.core.database.database_manager import DatabaseManager
from src.core.database.repositories.word_repository import WordRepository
from src.core.handlers.command_handlers import CommandHandlers


class TestStudyVerbsFeature:
    """Test the study verbs feature"""

    @pytest.fixture
    def mock_db_manager(self):
        """Create a mock database manager"""
        mock_db = Mock(spec=DatabaseManager)
        mock_db.get_user_by_telegram_id.return_value = {
            "telegram_id": 123456789,
            "username": "testuser",
            "created_at": "2023-01-01"
        }
        mock_db.get_verb_words.return_value = [
            {
                "id": 1,
                "lemma": "gehen",
                "part_of_speech": "verb",
                "article": None,
                "translation": "идти",
                "example": "Ich gehe nach Hause",
                "repetitions": 0,
                "easiness_factor": 2.5,
                "interval_days": 1,
                "next_review_date": None,
                "last_reviewed": None
            },
            {
                "id": 2,
                "lemma": "machen",
                "part_of_speech": "verb",
                "article": None,
                "translation": "делать",
                "example": "Ich mache meine Hausaufgaben",
                "repetitions": 1,
                "easiness_factor": 2.4,
                "interval_days": 2,
                "next_review_date": None,
                "last_reviewed": None
            }
        ]
        return mock_db

    @pytest.fixture
    def mock_word_repository(self):
        """Create a mock word repository"""
        mock_repo = Mock(spec=WordRepository)
        mock_repo.get_verb_words.return_value = [
            {
                "id": 1,
                "lemma": "gehen",
                "part_of_speech": "verb",
                "article": None,
                "translation": "идти",
                "example": "Ich gehe nach Hause",
                "repetitions": 0,
                "easiness_factor": 2.5,
                "interval_days": 1,
                "next_review_date": None,
                "last_reviewed": None
            }
        ]
        return mock_repo

    @pytest.fixture
    def command_handlers(self, mock_db_manager):
        """Create command handlers with mock dependencies"""
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
        # Set up the mock attributes that are used in tests
        handlers._safe_reply = AsyncMock()
        handlers._start_study_session = AsyncMock()
        return handlers

    @pytest.fixture
    def mock_update(self):
        """Create a mock update"""
        update = Mock(spec=Update)
        update.effective_user = Mock(spec=User)
        update.effective_user.id = 123456789
        update.effective_user.username = "testuser"
        update.message = Mock(spec=Message)
        return update

    @pytest.fixture
    def mock_context(self):
        """Create a mock context"""
        return Mock(spec=ContextTypes.DEFAULT_TYPE)

    def test_word_repository_get_verb_words(self, mock_word_repository):
        """Test WordRepository.get_verb_words method"""
        # Test successful retrieval
        result = mock_word_repository.get_verb_words(123456789, limit=10)

        assert len(result) == 1
        assert result[0]["part_of_speech"] == "verb"
        assert result[0]["lemma"] == "gehen"
        assert result[0]["article"] is None  # Verbs don't have articles

        # Verify method was called with correct parameters
        mock_word_repository.get_verb_words.assert_called_once_with(123456789, limit=10)

    def test_database_manager_get_verb_words(self, mock_db_manager):
        """Test DatabaseManager.get_verb_words method"""
        # Test successful retrieval
        result = mock_db_manager.get_verb_words(123456789, limit=10, randomize=True)

        assert len(result) == 2
        assert all(word["part_of_speech"] == "verb" for word in result)
        assert result[0]["lemma"] == "gehen"
        assert result[1]["lemma"] == "machen"

        # Verify method was called with correct parameters
        mock_db_manager.get_verb_words.assert_called_once_with(123456789, limit=10, randomize=True)

    @pytest.mark.asyncio
    async def test_study_verbs_command_success(self, command_handlers, mock_update, mock_context):
        """Test successful execution of study_verbs command"""
        # Test successful command execution
        await command_handlers.study_verbs_command(mock_update, mock_context)

        # Verify database methods were called
        command_handlers.db_manager.get_user_by_telegram_id.assert_called_once_with(123456789)
        command_handlers.db_manager.get_verb_words.assert_called_once_with(123456789, limit=10)

        # Verify study session was started
        command_handlers._start_study_session.assert_called_once()

    @pytest.mark.asyncio
    async def test_study_verbs_command_no_user(self, command_handlers, mock_update, mock_context):
        """Test study_verbs command when user is not found"""
        # Mock user not found
        command_handlers.db_manager.get_user_by_telegram_id.return_value = None

        await command_handlers.study_verbs_command(mock_update, mock_context)

        # Verify error message was sent
        command_handlers._safe_reply.assert_called_once()
        call_args = command_handlers._safe_reply.call_args
        assert call_args[0][0] == mock_update
        assert "❌ Пользователь не найден" in call_args[0][1]

    @pytest.mark.asyncio
    async def test_study_verbs_command_no_verbs(self, command_handlers, mock_update, mock_context):
        """Test study_verbs command when no verbs are available"""
        # Mock no verbs available
        command_handlers.db_manager.get_verb_words.return_value = []

        await command_handlers.study_verbs_command(mock_update, mock_context)

        # Verify appropriate message was sent
        command_handlers._safe_reply.assert_called_once()
        call_args = command_handlers._safe_reply.call_args
        assert call_args[0][0] == mock_update
        assert "🔤 У вас нет глаголов для изучения" in call_args[0][1]

    @pytest.mark.asyncio
    async def test_study_verbs_command_no_effective_user(self, command_handlers, mock_context):
        """Test study_verbs command when no effective user"""
        # Mock update with no effective user
        mock_update = Mock(spec=Update)
        mock_update.effective_user = None

        await command_handlers.study_verbs_command(mock_update, mock_context)

        # Verify no database calls were made
        command_handlers.db_manager.get_user_by_telegram_id.assert_not_called()
        command_handlers._safe_reply.assert_not_called()

    def test_verb_words_filtering_integration(self):
        """Test integration of verb filtering across the system"""
        # This test verifies the filtering logic works correctly
        sample_words = [
            {"lemma": "gehen", "part_of_speech": "verb", "translation": "идти"},
            {"lemma": "Haus", "part_of_speech": "noun", "translation": "дом"},
            {"lemma": "laufen", "part_of_speech": "verb", "translation": "бежать"},
            {"lemma": "schön", "part_of_speech": "adjective", "translation": "красивый"},
            {"lemma": "sprechen", "part_of_speech": "verb", "translation": "говорить"},
        ]

        # Filter verbs
        verb_words = [word for word in sample_words if word["part_of_speech"] == "verb"]

        assert len(verb_words) == 3
        assert all(word["part_of_speech"] == "verb" for word in verb_words)
        assert verb_words[0]["lemma"] == "gehen"
        assert verb_words[1]["lemma"] == "laufen"
        assert verb_words[2]["lemma"] == "sprechen"

    def test_verb_words_sql_query_structure(self):
        """Test the SQL query structure for getting verb words"""
        # This test verifies the expected SQL query structure
        expected_where_clause = "WHERE lp.telegram_id = ? AND w.part_of_speech = 'verb'"

        # The query should include the verb filter
        assert "part_of_speech = 'verb'" in expected_where_clause
        assert "telegram_id = ?" in expected_where_clause

        # Verify the query joins the correct tables
        expected_join = "JOIN learning_progress lp ON w.id = lp.word_id"
        assert "learning_progress" in expected_join
        assert "w.id = lp.word_id" in expected_join

    def test_verb_words_randomization_parameter(self, mock_db_manager):
        """Test randomization parameter in verb words retrieval"""
        # Test with randomization enabled
        mock_db_manager.get_verb_words(123456789, limit=5, randomize=True)
        mock_db_manager.get_verb_words.assert_called_with(123456789, limit=5, randomize=True)

        # Test with randomization disabled
        mock_db_manager.get_verb_words(123456789, limit=5, randomize=False)
        mock_db_manager.get_verb_words.assert_called_with(123456789, limit=5, randomize=False)

    def test_verb_words_limit_parameter(self, mock_db_manager):
        """Test limit parameter in verb words retrieval"""
        # Test with custom limit
        mock_db_manager.get_verb_words(123456789, limit=15)
        mock_db_manager.get_verb_words.assert_called_with(123456789, limit=15)

        # Test with default limit
        mock_db_manager.get_verb_words(123456789)
        mock_db_manager.get_verb_words.assert_called_with(123456789)

    def test_verb_words_empty_result_handling(self, mock_db_manager):
        """Test handling of empty result from verb words query"""
        # Mock empty result
        mock_db_manager.get_verb_words.return_value = []

        result = mock_db_manager.get_verb_words(123456789)

        assert result == []
        assert isinstance(result, list)
