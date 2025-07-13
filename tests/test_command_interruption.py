"""
Tests for command interruption functionality
"""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from telegram import User
from telegram.ext import ContextTypes

from src.core.handlers.command_handlers import CommandHandlers
from src.core.handlers.message_handlers import MessageHandlers
from src.core.session.session_manager import SessionManager, StudySession
from src.core.state.user_state_manager import UserState, UserStateManager
from src.database import DatabaseManager
from src.spaced_repetition import SpacedRepetitionSystem
from src.text_parser import GermanTextParser
from src.word_processor import WordProcessor


@pytest.fixture
def mock_db_manager():
    """Mock database manager"""
    db_manager = MagicMock(spec=DatabaseManager)
    db_manager.get_user_by_telegram_id.return_value = {
        "telegram_id": 12345,
        "first_name": "Test",
        "last_name": "User",
        "username": "testuser",
        "created_at": "2024-01-01 10:00:00",
    }
    db_manager.get_due_words.return_value = [
        {"id": 1, "lemma": "Hund", "translation": "dog", "example": "Der Hund bellt."},
        {
            "id": 2,
            "lemma": "Katze",
            "translation": "cat",
            "example": "Die Katze miaut.",
        },
    ]
    return db_manager


@pytest.fixture
def mock_srs_system():
    """Mock spaced repetition system"""
    return MagicMock(spec=SpacedRepetitionSystem)


@pytest.fixture
def mock_word_processor():
    """Mock word processor"""
    return MagicMock(spec=WordProcessor)


@pytest.fixture
def mock_text_parser():
    """Mock text parser"""
    return MagicMock(spec=GermanTextParser)


@pytest.fixture
def mock_safe_reply():
    """Mock safe reply callback"""
    return AsyncMock()


@pytest.fixture
def mock_safe_edit():
    """Mock safe edit callback"""
    return AsyncMock()


@pytest.fixture
def mock_process_text():
    """Mock process text callback"""
    return AsyncMock()


@pytest.fixture
def session_manager(mock_db_manager, mock_srs_system, mock_safe_reply, mock_safe_edit):
    """Create SessionManager instance"""
    return SessionManager(
        db_manager=mock_db_manager,
        srs_system=mock_srs_system,
        safe_reply_callback=mock_safe_reply,
        safe_edit_callback=mock_safe_edit,
    )


@pytest.fixture
def state_manager():
    """Create UserStateManager instance"""
    return UserStateManager(state_timeout_minutes=10)


@pytest.fixture
def command_handlers(
    mock_db_manager,
    mock_word_processor,
    mock_text_parser,
    mock_srs_system,
    mock_safe_reply,
    mock_process_text,
    session_manager,
    state_manager,
):
    """Create CommandHandlers instance"""
    return CommandHandlers(
        db_manager=mock_db_manager,
        word_processor=mock_word_processor,
        text_parser=mock_text_parser,
        srs_system=mock_srs_system,
        safe_reply_callback=mock_safe_reply,
        process_text_callback=mock_process_text,
        start_study_session_callback=session_manager.start_study_session,
        state_manager=state_manager,
        session_manager=session_manager,
    )


@pytest.fixture
def message_handlers(
    mock_safe_reply, mock_process_text, session_manager, state_manager
):
    """Create MessageHandlers instance"""
    return MessageHandlers(
        safe_reply_callback=mock_safe_reply,
        process_text_callback=mock_process_text,
        handle_study_callback=session_manager.handle_study_callback,
        state_manager=state_manager,
        session_manager=session_manager,
    )


@pytest.fixture
def mock_update():
    """Create mock Telegram Update"""
    user = User(id=12345, first_name="Test", is_bot=False)
    message = MagicMock()
    message.message_id = 1
    message.date = datetime.now()
    message.chat = MagicMock()
    message.from_user = user
    message.text = "test message"

    update = MagicMock()
    update.update_id = 1
    update.message = message
    update.effective_user = user
    return update


@pytest.fixture
def mock_context():
    """Create mock Telegram context"""
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.args = []
    return context


class TestSessionManagerInterruption:
    """Test session interruption in SessionManager"""

    @pytest.mark.asyncio
    async def test_start_study_session_interrupts_existing_session(
        self, session_manager, mock_update, mock_safe_reply
    ):
        """Test that starting new session interrupts existing one"""
        # Create existing session with some progress
        words = [
            {
                "id": 1,
                "lemma": "Hund",
                "translation": "dog",
                "example": "Der Hund bellt.",
            },
            {
                "id": 2,
                "lemma": "Katze",
                "translation": "cat",
                "example": "Die Katze miaut.",
            },
        ]

        existing_session = StudySession("session1", 12345, words, "regular")
        existing_session.current_word_index = 1
        existing_session.correct_answers = 1
        existing_session.total_answers = 1
        existing_session.timer.start()

        # Simulate some time passing
        await asyncio.sleep(0.1)

        # Add existing session
        session_manager.user_sessions[12345] = existing_session

        # Start new session
        new_words = [
            {
                "id": 3,
                "lemma": "Buch",
                "translation": "book",
                "example": "Das Buch ist interessant.",
            }
        ]
        await session_manager.start_study_session(mock_update, new_words, "new")

        # Verify interruption message was sent
        interrupt_calls = [
            call for call in mock_safe_reply.call_args_list if "прервана" in str(call)
        ]
        assert len(interrupt_calls) == 1

        # Verify old session was replaced
        assert 12345 in session_manager.user_sessions
        new_session = session_manager.user_sessions[12345]
        assert new_session.words == new_words
        assert new_session.session_type == "new"
        assert new_session.current_word_index == 0

    @pytest.mark.asyncio
    async def test_start_study_session_no_interruption_when_no_existing_session(
        self, session_manager, mock_update, mock_safe_reply
    ):
        """Test that no interruption occurs when no existing session"""
        words = [
            {
                "id": 1,
                "lemma": "Hund",
                "translation": "dog",
                "example": "Der Hund bellt.",
            }
        ]

        await session_manager.start_study_session(mock_update, words, "regular")

        # Verify no interruption message was sent
        interrupt_calls = [
            call for call in mock_safe_reply.call_args_list if "прервана" in str(call)
        ]
        assert len(interrupt_calls) == 0

        # Verify session was created
        assert 12345 in session_manager.user_sessions

    @pytest.mark.asyncio
    async def test_interruption_message_contains_statistics(
        self, session_manager, mock_update, mock_safe_reply
    ):
        """Test that interruption message contains correct statistics"""
        words = [
            {
                "id": 1,
                "lemma": "Hund",
                "translation": "dog",
                "example": "Der Hund bellt.",
            },
            {
                "id": 2,
                "lemma": "Katze",
                "translation": "cat",
                "example": "Die Katze miaut.",
            },
        ]

        existing_session = StudySession("session1", 12345, words, "regular")
        existing_session.current_word_index = 1
        existing_session.correct_answers = 3
        existing_session.total_answers = 4
        existing_session.timer.start()

        session_manager.user_sessions[12345] = existing_session

        new_words = [
            {
                "id": 3,
                "lemma": "Buch",
                "translation": "book",
                "example": "Das Buch ist interessant.",
            }
        ]
        await session_manager.start_study_session(mock_update, new_words, "new")

        # Check interruption message content
        interrupt_call = None
        for call in mock_safe_reply.call_args_list:
            if "прервана" in str(call):
                interrupt_call = call
                break

        assert interrupt_call is not None
        message = interrupt_call[0][1]  # Second argument (message text)

        assert "1/2" in message  # Words studied
        assert "3/4" in message  # Correct answers
        assert "75.0%" in message  # Accuracy
        assert "Время:" in message  # Time


class TestCommandHandlersInterruption:
    """Test session interruption in CommandHandlers"""

    @pytest.mark.asyncio
    async def test_add_command_interrupts_study_session(
        self, command_handlers, mock_update, mock_context, mock_safe_reply
    ):
        """Test that /add command interrupts active study session"""
        # Create existing study session
        words = [
            {
                "id": 1,
                "lemma": "Hund",
                "translation": "dog",
                "example": "Der Hund bellt.",
            }
        ]
        existing_session = StudySession("session1", 12345, words, "regular")
        existing_session.current_word_index = 1
        existing_session.correct_answers = 2
        existing_session.total_answers = 3
        existing_session.timer.start()

        command_handlers.session_manager.user_sessions[12345] = existing_session

        # Execute /add command without arguments
        await command_handlers.add_command(mock_update, mock_context)

        # Verify interruption message was sent
        interrupt_calls = [
            call for call in mock_safe_reply.call_args_list if "прервана" in str(call)
        ]
        assert len(interrupt_calls) == 1

        # Verify session was cleaned up
        assert 12345 not in command_handlers.session_manager.user_sessions

    @pytest.mark.asyncio
    async def test_add_command_with_args_interrupts_session(
        self,
        command_handlers,
        mock_update,
        mock_context,
        mock_safe_reply,
        mock_process_text,
    ):
        """Test that /add command with arguments interrupts session and processes text"""
        # Setup context with arguments
        mock_context.args = ["Das", "ist", "ein", "Test"]

        # Create existing study session
        words = [
            {
                "id": 1,
                "lemma": "Hund",
                "translation": "dog",
                "example": "Der Hund bellt.",
            }
        ]
        existing_session = StudySession("session1", 12345, words, "regular")
        command_handlers.session_manager.user_sessions[12345] = existing_session

        # Execute /add command with arguments
        await command_handlers.add_command(mock_update, mock_context)

        # Verify interruption occurred
        interrupt_calls = [
            call for call in mock_safe_reply.call_args_list if "прервана" in str(call)
        ]
        assert len(interrupt_calls) == 1

        # Verify text processing was called
        mock_process_text.assert_called_once_with(mock_update, "Das ist ein Test")

    @pytest.mark.asyncio
    async def test_add_command_no_interruption_when_no_session(
        self, command_handlers, mock_update, mock_context, mock_safe_reply
    ):
        """Test that /add command doesn't send interruption when no active session"""
        # Execute /add command without existing session
        await command_handlers.add_command(mock_update, mock_context)

        # Verify no interruption message was sent
        interrupt_calls = [
            call for call in mock_safe_reply.call_args_list if "прервана" in str(call)
        ]
        assert len(interrupt_calls) == 0


class TestMessageHandlersInterruption:
    """Test session interruption in MessageHandlers"""

    @pytest.mark.asyncio
    async def test_handle_message_interrupts_study_session(
        self,
        message_handlers,
        mock_update,
        mock_context,
        mock_safe_reply,
        mock_process_text,
    ):
        """Test that text message interrupts active study session"""
        # Setup message text
        mock_update.message.text = "Das ist ein deutscher Text für den Test."

        # Create existing study session
        words = [
            {
                "id": 1,
                "lemma": "Hund",
                "translation": "dog",
                "example": "Der Hund bellt.",
            }
        ]
        existing_session = StudySession("session1", 12345, words, "regular")
        existing_session.current_word_index = 1
        existing_session.correct_answers = 1
        existing_session.total_answers = 2
        existing_session.timer.start()

        message_handlers.session_manager.user_sessions[12345] = existing_session

        # Handle message
        await message_handlers.handle_message(mock_update, mock_context)

        # Verify interruption message was sent
        interrupt_calls = [
            call for call in mock_safe_reply.call_args_list if "прервана" in str(call)
        ]
        assert len(interrupt_calls) == 1

        # Verify text processing was called
        mock_process_text.assert_called_once()

        # Verify session was cleaned up
        assert 12345 not in message_handlers.session_manager.user_sessions

    @pytest.mark.asyncio
    async def test_handle_message_no_interruption_for_short_text(
        self, message_handlers, mock_update, mock_context, mock_safe_reply
    ):
        """Test that short text doesn't interrupt session"""
        # Setup short message text
        mock_update.message.text = "Hi"

        # Create existing study session
        words = [
            {
                "id": 1,
                "lemma": "Hund",
                "translation": "dog",
                "example": "Der Hund bellt.",
            }
        ]
        existing_session = StudySession("session1", 12345, words, "regular")
        message_handlers.session_manager.user_sessions[12345] = existing_session

        # Handle message
        await message_handlers.handle_message(mock_update, mock_context)

        # Verify no interruption message was sent
        interrupt_calls = [
            call for call in mock_safe_reply.call_args_list if "прервана" in str(call)
        ]
        assert len(interrupt_calls) == 0

        # Verify session still exists
        assert 12345 in message_handlers.session_manager.user_sessions

    @pytest.mark.asyncio
    async def test_handle_message_waiting_for_text_interrupts_session(
        self,
        message_handlers,
        mock_update,
        mock_context,
        mock_safe_reply,
        mock_process_text,
    ):
        """Test that message while waiting for text interrupts session"""
        # Setup message text
        mock_update.message.text = "Das ist ein Test."

        # Set user state to waiting for text
        message_handlers.state_manager.set_state(
            12345, UserState.WAITING_FOR_TEXT_TO_ADD
        )

        # Create existing study session
        words = [
            {
                "id": 1,
                "lemma": "Hund",
                "translation": "dog",
                "example": "Der Hund bellt.",
            }
        ]
        existing_session = StudySession("session1", 12345, words, "regular")
        message_handlers.session_manager.user_sessions[12345] = existing_session

        # Handle message
        await message_handlers.handle_message(mock_update, mock_context)

        # Verify interruption message was sent
        interrupt_calls = [
            call for call in mock_safe_reply.call_args_list if "прервана" in str(call)
        ]
        assert len(interrupt_calls) == 1

        # Verify text processing was called
        mock_process_text.assert_called_once_with(mock_update, "Das ist ein Test.")

        # Verify state was cleared
        assert message_handlers.state_manager.get_state(12345) == UserState.IDLE

    @pytest.mark.asyncio
    async def test_handle_message_prevents_help_after_interruption(
        self, message_handlers, mock_update, mock_context, mock_safe_reply
    ):
        """Test that help message is not shown after interruption for short text"""
        # Setup short message text (less than 3 chars to not trigger interruption)
        mock_update.message.text = "Hi"

        # Create existing study session
        words = [
            {
                "id": 1,
                "lemma": "Hund",
                "translation": "dog",
                "example": "Der Hund bellt.",
            }
        ]
        existing_session = StudySession("session1", 12345, words, "regular")
        existing_session.timer.start()
        message_handlers.session_manager.user_sessions[12345] = existing_session

        # Handle message (short text doesn't trigger interruption)
        await message_handlers.handle_message(mock_update, mock_context)

        # Count help messages and interruption messages
        help_calls = [
            call
            for call in mock_safe_reply.call_args_list
            if "Отправьте мне немецкий текст" in str(call)
        ]
        interrupt_calls = [
            call for call in mock_safe_reply.call_args_list if "прервана" in str(call)
        ]

        # Should show help message since no interruption occurred
        assert len(interrupt_calls) == 0
        assert len(help_calls) == 1


class TestInterruptionIntegration:
    """Integration tests for command interruption scenarios"""

    @pytest.mark.asyncio
    async def test_study_to_add_to_study_workflow(
        self,
        session_manager,
        command_handlers,
        mock_update,
        mock_context,
        mock_safe_reply,
        mock_db_manager,
    ):
        """Test complete workflow: study -> add -> study"""
        # Start first study session
        words1 = [
            {
                "id": 1,
                "lemma": "Hund",
                "translation": "dog",
                "example": "Der Hund bellt.",
            }
        ]
        await session_manager.start_study_session(mock_update, words1, "regular")

        # Verify first session exists
        assert 12345 in session_manager.user_sessions
        first_session = session_manager.user_sessions[12345]
        assert first_session.session_type == "regular"

        # Simulate some progress
        first_session.current_word_index = 1
        first_session.correct_answers = 1
        first_session.total_answers = 1

        # Execute /add command (should interrupt)
        await command_handlers.add_command(mock_update, mock_context)

        # Verify interruption occurred (command_handlers uses different message)
        interrupt_calls = [
            call for call in mock_safe_reply.call_args_list if "прервана" in str(call)
        ]
        assert len(interrupt_calls) == 1

        # Start second study session
        words2 = [
            {
                "id": 2,
                "lemma": "Katze",
                "translation": "cat",
                "example": "Die Katze miaut.",
            }
        ]
        await session_manager.start_study_session(mock_update, words2, "new")

        # Verify only one interruption occurred (add command already cleared session)
        interrupt_calls = [
            call for call in mock_safe_reply.call_args_list if "прервана" in str(call)
        ]
        assert len(interrupt_calls) == 1  # Only one interruption (add command)

        # Verify final session is the new one
        assert 12345 in session_manager.user_sessions
        final_session = session_manager.user_sessions[12345]
        assert final_session.words == words2
        assert final_session.session_type == "new"

    @pytest.mark.asyncio
    async def test_multiple_session_types_interruption(
        self, session_manager, mock_update, mock_safe_reply
    ):
        """Test interruption between different session types"""
        # Start regular session
        regular_words = [
            {
                "id": 1,
                "lemma": "Hund",
                "translation": "dog",
                "example": "Der Hund bellt.",
            }
        ]
        await session_manager.start_study_session(mock_update, regular_words, "regular")

        # Start new words session (should interrupt regular)
        new_words = [
            {
                "id": 2,
                "lemma": "Katze",
                "translation": "cat",
                "example": "Die Katze miaut.",
            }
        ]
        await session_manager.start_study_session(mock_update, new_words, "new")

        # Start difficult words session (should interrupt new)
        difficult_words = [
            {
                "id": 3,
                "lemma": "Buch",
                "translation": "book",
                "example": "Das Buch ist gut.",
            }
        ]
        await session_manager.start_study_session(
            mock_update, difficult_words, "difficult"
        )

        # Verify three interruptions occurred (first session has no interruption)
        interrupt_calls = [
            call for call in mock_safe_reply.call_args_list if "прервана" in str(call)
        ]
        assert len(interrupt_calls) == 2

        # Verify final session is difficult words
        final_session = session_manager.user_sessions[12345]
        assert final_session.words == difficult_words
        assert final_session.session_type == "difficult"

    @pytest.mark.asyncio
    async def test_session_cleanup_on_interruption(
        self, session_manager, mock_update, mock_safe_reply
    ):
        """Test that interrupted sessions are properly cleaned up"""
        # Start first session
        words1 = [
            {
                "id": 1,
                "lemma": "Hund",
                "translation": "dog",
                "example": "Der Hund bellt.",
            }
        ]
        await session_manager.start_study_session(mock_update, words1, "regular")

        first_session = session_manager.user_sessions[12345]
        assert first_session.timer.start_time is not None

        # Start second session (should stop first timer)
        words2 = [
            {
                "id": 2,
                "lemma": "Katze",
                "translation": "cat",
                "example": "Die Katze miaut.",
            }
        ]
        await session_manager.start_study_session(mock_update, words2, "new")

        # Verify first session timer was stopped
        assert first_session.timer.end_time is not None

        # Verify only one session exists
        assert (
            len(
                [
                    s
                    for s in session_manager.user_sessions.values()
                    if s.telegram_id == 12345
                ]
            )
            == 1
        )

        # Verify current session is the new one
        current_session = session_manager.user_sessions[12345]
        assert current_session.words == words2
        assert current_session.timer.start_time is not None
        assert current_session.timer.end_time is None  # Still running
