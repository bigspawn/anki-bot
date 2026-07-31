"""
Tests for /study_reflexive (sich ...) and /study_rektion (denken an + Akk):
command handlers, repository queries and the study card that has to ask for
the case as well as the translation.
"""

import json
import os
import tempfile
from unittest.mock import AsyncMock, Mock

import pytest
from telegram import Message, Update, User
from telegram.ext import ContextTypes

from src.core.database.database_manager import DatabaseManager
from src.core.handlers.command_handlers import CommandHandlers
from src.utils import format_study_card, format_verb_case, format_verb_forms

REFLEXIVE_WORD = {
    "id": 1,
    "lemma": "sich verlaufen",
    "part_of_speech": "reflexive verb",
    "article": None,
    "translation": "заблудиться (пешком)",
    "example": "Im Wald haben wir uns verlaufen.",
    "additional_forms": json.dumps(
        {"praeteritum": "verlief", "partizip_ii": "verlaufen"}
    ),
    "repetitions": 0,
    "easiness_factor": 2.5,
    "interval_days": 1,
    "next_review_date": None,
    "last_reviewed": None,
}

REKTION_WORD = {
    "id": 2,
    "lemma": "denken an",
    "part_of_speech": "verb + preposition",
    "article": None,
    "translation": "думать о ком-л./чём-л.",
    "example": "Ich denke oft an meine Familie.",
    "additional_forms": json.dumps({"preposition": "an", "case": "Akkusativ"}),
    "repetitions": 0,
    "easiness_factor": 2.5,
    "interval_days": 1,
    "next_review_date": None,
    "last_reviewed": None,
}


class TestReflexiveAndRektionCommands:
    """Command handler behaviour, mirroring the other /study_* commands"""

    @pytest.fixture
    def mock_db_manager(self):
        mock_db = Mock(spec=DatabaseManager)
        mock_db.get_user_by_telegram_id.return_value = {
            "telegram_id": 123456789,
            "username": "testuser",
            "created_at": "2023-01-01",
        }
        mock_db.get_reflexive_verbs.return_value = [REFLEXIVE_WORD]
        mock_db.get_preposition_verbs.return_value = [REKTION_WORD]
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

    @pytest.mark.asyncio
    async def test_reflexive_happy_path(self, command_handlers, mock_update):
        await command_handlers.study_reflexive_command(
            mock_update, self._mock_context()
        )

        command_handlers.db_manager.get_reflexive_verbs.assert_called_once_with(
            123456789, limit=10
        )
        command_handlers._start_study_session.assert_called_once()
        assert command_handlers._start_study_session.call_args[0][2] == "reflexive"

    @pytest.mark.asyncio
    async def test_rektion_happy_path(self, command_handlers, mock_update):
        await command_handlers.study_rektion_command(mock_update, self._mock_context())

        command_handlers.db_manager.get_preposition_verbs.assert_called_once_with(
            123456789, limit=10
        )
        command_handlers._start_study_session.assert_called_once()
        assert command_handlers._start_study_session.call_args[0][2] == "rektion"

    @pytest.mark.asyncio
    async def test_reflexive_user_not_found(self, command_handlers, mock_update):
        command_handlers.db_manager.get_user_by_telegram_id.return_value = None

        await command_handlers.study_reflexive_command(
            mock_update, self._mock_context()
        )

        assert "❌ Пользователь не найден" in (
            command_handlers._safe_reply.call_args[0][1]
        )
        command_handlers.db_manager.get_reflexive_verbs.assert_not_called()
        command_handlers._start_study_session.assert_not_called()

    @pytest.mark.asyncio
    async def test_rektion_user_not_found(self, command_handlers, mock_update):
        command_handlers.db_manager.get_user_by_telegram_id.return_value = None

        await command_handlers.study_rektion_command(mock_update, self._mock_context())

        assert "❌ Пользователь не найден" in (
            command_handlers._safe_reply.call_args[0][1]
        )
        command_handlers.db_manager.get_preposition_verbs.assert_not_called()

    @pytest.mark.asyncio
    async def test_reflexive_no_words(self, command_handlers, mock_update):
        command_handlers.db_manager.get_reflexive_verbs.return_value = []

        await command_handlers.study_reflexive_command(
            mock_update, self._mock_context()
        )

        assert "нет возвратных глаголов" in (
            command_handlers._safe_reply.call_args[0][1]
        )
        command_handlers._start_study_session.assert_not_called()

    @pytest.mark.asyncio
    async def test_rektion_no_words(self, command_handlers, mock_update):
        command_handlers.db_manager.get_preposition_verbs.return_value = []

        await command_handlers.study_rektion_command(mock_update, self._mock_context())

        assert "нет глаголов с предлогами" in (
            command_handlers._safe_reply.call_args[0][1]
        )
        command_handlers._start_study_session.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_effective_user(self, command_handlers):
        update = Mock(spec=Update)
        update.effective_user = None

        await command_handlers.study_reflexive_command(update, self._mock_context())
        await command_handlers.study_rektion_command(update, self._mock_context())

        command_handlers.db_manager.get_user_by_telegram_id.assert_not_called()
        command_handlers._safe_reply.assert_not_called()


class TestReflexiveAndRektionQueries:
    """Repository queries against a real database"""

    @pytest.fixture
    def db_manager(self):
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        temp_file.close()

        manager = DatabaseManager(temp_file.name)
        manager.init_database()
        manager.create_user(telegram_id=555, first_name="Test")
        manager.add_words_to_user(
            555,
            [
                {
                    "lemma": "sich verlaufen",
                    "part_of_speech": "reflexive verb",
                    "translation": "заблудиться",
                    "example": "Wir haben uns verlaufen.",
                },
                {
                    "lemma": "sich freuen",
                    "part_of_speech": "verb",  # only the lemma marks it
                    "translation": "радоваться",
                    "example": "Ich freue mich.",
                },
                {
                    "lemma": "denken an",
                    "part_of_speech": "verb + preposition",
                    "translation": "думать о",
                    "example": "Ich denke an dich.",
                },
                {
                    "lemma": "gehen",
                    "part_of_speech": "verb",
                    "translation": "идти",
                    "example": "Ich gehe.",
                },
                {
                    "lemma": "auf",
                    "part_of_speech": "preposition",
                    "translation": "на",
                    "example": "Auf dem Tisch.",
                },
            ],
        )

        yield manager

        os.unlink(temp_file.name)

    def test_reflexive_query_matches_lemma_and_part_of_speech(self, db_manager):
        lemmas = {w["lemma"] for w in db_manager.get_reflexive_verbs(555, limit=10)}

        assert lemmas == {"sich verlaufen", "sich freuen"}

    def test_rektion_query_excludes_plain_verbs_and_prepositions(self, db_manager):
        lemmas = {w["lemma"] for w in db_manager.get_preposition_verbs(555, limit=10)}

        assert lemmas == {"denken an"}

    def test_queries_are_scoped_to_the_user(self, db_manager):
        db_manager.create_user(telegram_id=666, first_name="Other")

        assert db_manager.get_reflexive_verbs(666, limit=10) == []
        assert db_manager.get_preposition_verbs(666, limit=10) == []

    def test_limit_is_respected(self, db_manager):
        assert len(db_manager.get_reflexive_verbs(555, limit=1)) == 1


class TestStudyCardForTheseGroups:
    """The card must ask for the case and reveal it in the answer"""

    def test_rektion_question_asks_for_the_case(self):
        card = format_study_card(REKTION_WORD, current_index=1, total_words=5)

        assert card == "1/5. Как переводится denken an и какой падеж?"

    def test_reflexive_question_is_the_plain_translation_question(self):
        card = format_study_card(REFLEXIVE_WORD, current_index=1, total_words=5)

        assert card == "1/5. Как переводится sich verlaufen?"

    def test_answer_shows_preposition_and_case(self):
        assert format_verb_case(REKTION_WORD) == "🧭 an + Akkusativ\n\n"

    def test_reflexive_answer_still_shows_principal_parts(self):
        assert format_verb_forms(REFLEXIVE_WORD) == "🔄 verlief – verlaufen\n\n"

    def test_case_line_is_empty_for_other_words(self):
        assert format_verb_case(REFLEXIVE_WORD) == ""
        assert format_verb_case({"part_of_speech": "noun", "additional_forms": None}) == ""

    def test_verb_forms_line_is_empty_for_rektion_words(self):
        """additional_forms holds the case there, not Präteritum/Partizip II"""
        assert format_verb_forms(REKTION_WORD) == ""

    def test_malformed_additional_forms_are_ignored(self):
        broken = dict(REKTION_WORD, additional_forms="{not json")
        assert format_verb_case(broken) == ""

        partial = dict(REKTION_WORD, additional_forms=json.dumps({"preposition": "an"}))
        assert format_verb_case(partial) == ""
