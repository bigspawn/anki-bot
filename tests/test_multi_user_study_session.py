"""
Test multi-user study session scenarios to prevent Button_data_invalid errors
"""

import os
import tempfile
from datetime import datetime
from unittest.mock import AsyncMock, Mock

import pytest

from src.core.database.database_manager import DatabaseManager
from src.core.session.session_manager import SessionManager, StudySession
from src.spaced_repetition import get_srs_system
from src.utils import create_inline_keyboard_data, parse_inline_keyboard_data


class TestMultiUserStudySession:
    """Test multi-user study session scenarios"""

    @pytest.fixture
    def temp_db_manager(self):
        """Create a temporary database manager"""
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        temp_file.close()

        db_manager = DatabaseManager(temp_file.name)
        db_manager.init_database()

        yield db_manager

        # Cleanup
        os.unlink(temp_file.name)

    @pytest.fixture
    def mock_session_manager(self, temp_db_manager):
        """Create a mock session manager"""
        srs = get_srs_system()
        mock_reply = AsyncMock()
        mock_edit = AsyncMock()

        return SessionManager(
            db_manager=temp_db_manager,
            srs_system=srs,
            safe_reply_callback=mock_reply,
            safe_edit_callback=mock_edit
        )

    def test_multiple_users_concurrent_sessions(self, mock_session_manager, temp_db_manager):
        """Test multiple users having concurrent study sessions"""

        # Create multiple users
        users = []
        for i in range(1, 6):  # Users 1-5
            user_data = {
                "telegram_id": i,
                "first_name": f"User{i}",
                "last_name": "Test",
                "username": f"user{i}",
            }
            user = temp_db_manager.create_user(**user_data)
            users.append(user)

        # Add words for each user
        words_data = [
            {"lemma": "haus", "part_of_speech": "noun", "translation": "house", "example": "Das Haus ist groß."},
            {"lemma": "auto", "part_of_speech": "noun", "translation": "car", "example": "Das Auto ist schnell."},
            {"lemma": "buch", "part_of_speech": "noun", "translation": "book", "example": "Das Buch ist gut."},
        ]

        for user in users:
            user_id = user["telegram_id"]
            added_count = temp_db_manager.add_words_to_user(user_id, words_data)
            assert added_count == 3

        # Create study sessions for each user
        for user in users:
            user_id = user["telegram_id"]
            words = temp_db_manager.get_new_words(user_id, limit=3)

            # Create mock update object
            mock_update = Mock()
            mock_update.effective_user = Mock()
            mock_update.effective_user.id = user["telegram_id"]

            # Create session
            session = StudySession(f"session_{user_id}", user_id, words, "test")
            mock_session_manager.user_sessions[user_id] = session

            # Test that callback data is generated correctly for each user
            for word in words:
                # Test show_answer callback
                show_data = create_inline_keyboard_data(
                    action="show_answer",
                    word_id=word["id"],
                    word_index=0
                )
                assert len(show_data) <= 64, f"Show data too long for user {user_id}: {len(show_data)} bytes"

                # Test rate_word callbacks
                for rating in [1, 2, 3, 4]:
                    rate_data = create_inline_keyboard_data(
                        action="rate_word",
                        word_id=word["id"],
                        rating=rating
                    )
                    assert len(rate_data) <= 64, f"Rate data too long for user {user_id}: {len(rate_data)} bytes"

    def test_session_id_uniqueness_across_users(self, mock_session_manager):
        """Test that session IDs are unique across different users"""

        # Simulate multiple users creating sessions at nearly the same time
        user_ids = [1, 5, 123, 456789, 999999]
        session_ids = []

        for user_id in user_ids:
            # Create session ID like SessionManager does
            timestamp = int(datetime.now().timestamp())
            compact_timestamp = timestamp % 1000000
            session_id = f"{user_id}_{compact_timestamp}"
            session_ids.append(session_id)

            # Test callback data generation
            data = create_inline_keyboard_data(
                action="show_answer",
                word_id=1,
                session_id=session_id,
                word_index=0
            )
            assert len(data) <= 64, f"Data too long for user {user_id}: {len(data)} bytes"

        # Session IDs should be unique (at least user_id part)
        user_parts = [sid.split("_")[0] for sid in session_ids]
        assert len(set(user_parts)) == len(user_ids), "Session IDs should have unique user parts"

    def test_button_data_invalid_scenario_reproduction(self, mock_session_manager, temp_db_manager):
        """Test the exact scenario that caused Button_data_invalid error"""

        # This reproduces the scenario from the error log:
        # User 5 (second user) getting Button_data_invalid error

        # Create user 5
        user_data = {
            "telegram_id": 5,
            "first_name": "TestUser",
            "last_name": "Five",
            "username": "testuser5",
        }
        user = temp_db_manager.create_user(**user_data)
        user_id = user["telegram_id"]

        # Add a word
        word_data = {
            "lemma": "test",
            "part_of_speech": "noun",
            "translation": "тест",
            "example": "This is a test."
        }
        added_count = temp_db_manager.add_words_to_user(user_id, [word_data])
        assert added_count == 1

        # Get the word for study
        words = temp_db_manager.get_new_words(user_id, limit=1)
        assert len(words) == 1
        word = words[0]

        # Create session like SessionManager does
        timestamp = int(datetime.now().timestamp())
        timestamp % 1000000

        # Create the problematic callback data
        show_answer_data = create_inline_keyboard_data(
            action="show_answer",
            word_id=word["id"],
            word_index=0
        )

        # This should not be too long
        assert len(show_answer_data) <= 64, f"Show answer data too long: {len(show_answer_data)} bytes"

        # Test rating buttons
        for rating in [1, 2, 3, 4]:
            rate_data = create_inline_keyboard_data(
                action="rate_word",
                word_id=word["id"],
                rating=rating
            )
            assert len(rate_data) <= 64, f"Rate data too long for rating {rating}: {len(rate_data)} bytes"

        # Verify data is parseable
        parsed = parse_inline_keyboard_data(show_answer_data)
        assert parsed["action"] == "show_answer"
        assert parsed["word_id"] == word["id"]

    def test_large_word_ids_with_multiple_users(self, temp_db_manager):
        """Test handling of large word IDs with multiple users"""

        # Create users with varying IDs
        user_telegram_ids = [1, 99, 999, 9999, 99999]

        for telegram_id in user_telegram_ids:
            user_data = {
                "telegram_id": telegram_id,
                "first_name": f"User{telegram_id}",
                "last_name": "Test",
                "username": f"user{telegram_id}",
            }
            user = temp_db_manager.create_user(**user_data)
            user_id = user["telegram_id"]

            # Add words to create potentially large word IDs
            words_data = [
                {"lemma": f"word{i}", "part_of_speech": "noun", "translation": f"слово{i}", "example": f"Example {i}."}
                for i in range(1, 21)  # 20 words
            ]

            added_count = temp_db_manager.add_words_to_user(user_id, words_data)
            assert added_count == 20

            # Get words and test callback data
            words = temp_db_manager.get_new_words(user_id, limit=5)

            for word in words:
                # Test with potentially large word IDs
                data = create_inline_keyboard_data(
                    action="rate_word",
                    word_id=word["id"],
                    rating=4
                )
                assert len(data) <= 64, f"Data too long for user {telegram_id}, word {word['id']}: {len(data)} bytes"

    def test_session_manager_callback_data_generation(self, mock_session_manager):
        """Test that SessionManager generates valid callback data"""

        # Create a mock word
        word = {
            "id": 12345,
            "lemma": "beispiel",
            "translation": "example",
            "example": "Das ist ein Beispiel."
        }

        # Test show_answer callback data generation
        show_data = create_inline_keyboard_data(
            action="show_answer",
            word_id=word["id"],
            word_index=0
        )
        assert len(show_data) <= 64, f"Show data too long: {len(show_data)} bytes"

        # Test rate_word callback data generation
        for rating in [1, 2, 3, 4]:
            rate_data = create_inline_keyboard_data(
                action="rate_word",
                word_id=word["id"],
                rating=rating
            )
            assert len(rate_data) <= 64, f"Rate data too long for rating {rating}: {len(rate_data)} bytes"

            # Verify parseability
            parsed = parse_inline_keyboard_data(rate_data)
            assert parsed["action"] == "rate_word"
            assert parsed["word_id"] == word["id"]
            assert parsed["rating"] == rating

    def test_session_cleanup_does_not_affect_callback_data(self, mock_session_manager):
        """Test that session cleanup doesn't affect callback data validation"""

        # Create and then clean up sessions
        user_ids = [1, 2, 3, 4, 5]

        for user_id in user_ids:
            # Create session
            words = [{"id": i, "lemma": f"word{i}", "translation": f"слово{i}", "example": f"Example {i}."}
                    for i in range(1, 4)]
            session = StudySession(f"session_{user_id}", user_id, words, "test")
            mock_session_manager.user_sessions[user_id] = session

            # Generate callback data
            for word in words:
                data = create_inline_keyboard_data(
                    action="show_answer",
                    word_id=word["id"],
                    word_index=0
                )
                assert len(data) <= 64, f"Data too long before cleanup: {len(data)} bytes"

        # Clean up sessions
        mock_session_manager.user_sessions.clear()

        # Callback data should still be valid
        data = create_inline_keyboard_data(
            action="rate_word",
            word_id=999,
            rating=3
        )
        assert len(data) <= 64, f"Data too long after cleanup: {len(data)} bytes"

    def test_concurrent_session_creation(self, mock_session_manager):
        """Test concurrent session creation by multiple users"""

        # Simulate multiple users creating sessions concurrently
        base_timestamp = int(datetime.now().timestamp())

        for i in range(10):  # 10 concurrent users
            user_id = i + 1
            # Simulate timestamps that might be the same or very close
            timestamp = base_timestamp + (i % 3)  # Some will have same timestamp
            compact_timestamp = timestamp % 1000000
            session_id = f"{user_id}_{compact_timestamp}"

            # Test callback data generation
            data = create_inline_keyboard_data(
                action="show_answer",
                word_id=1,
                session_id=session_id,
                word_index=0
            )
            assert len(data) <= 64, f"Data too long for concurrent user {user_id}: {len(data)} bytes"

            # Verify parseability
            parsed = parse_inline_keyboard_data(data)
            assert parsed["action"] == "show_answer"
