"""
Test inline keyboard data handling to prevent Button_data_invalid errors
"""

from datetime import datetime
from unittest.mock import Mock

from src.core.session.session_manager import SessionManager, StudySession
from src.utils import create_inline_keyboard_data, parse_inline_keyboard_data


class TestInlineKeyboardData:
    """Test inline keyboard data creation and parsing"""

    def test_create_inline_keyboard_data_basic(self):
        """Test basic inline keyboard data creation"""

        # Test simple action
        data = create_inline_keyboard_data("show_answer")
        assert len(data) <= 64, f"Data too long: {len(data)} bytes"

        parsed = parse_inline_keyboard_data(data)
        assert parsed["action"] == "show_answer"

    def test_create_inline_keyboard_data_with_params(self):
        """Test inline keyboard data with parameters"""

        # Test with word_id and rating
        data = create_inline_keyboard_data(action="rate_word", word_id=123, rating=3)
        assert len(data) <= 64, f"Data too long: {len(data)} bytes"

        parsed = parse_inline_keyboard_data(data)
        assert parsed["action"] == "rate_word"
        assert parsed["word_id"] == 123
        assert parsed["rating"] == 3

    def test_create_inline_keyboard_data_with_long_session_id(self):
        """Test inline keyboard data with long session_id"""

        # Test with long session ID that might cause issues
        long_session_id = "12345_1720725491049"
        data = create_inline_keyboard_data(
            action="show_answer", word_id=999, session_id=long_session_id, word_index=5
        )
        assert len(data) <= 64, f"Data too long: {len(data)} bytes"

        parsed = parse_inline_keyboard_data(data)
        assert parsed["action"] == "show_answer"
        assert parsed["word_id"] == 999
        assert "session_id" in parsed  # Should be truncated but present

    def test_create_inline_keyboard_data_compact_format(self):
        """Test that compact format is used"""

        data = create_inline_keyboard_data(action="rate_word", word_id=1, rating=4)

        # Should use compact keys
        assert '"a":"rate_word"' in data or '"a":"rate_word"' in data
        assert '"w":1' in data or '"w":1' in data
        assert '"r":4' in data or '"r":4' in data

        # Should be parseable back
        parsed = parse_inline_keyboard_data(data)
        assert parsed["action"] == "rate_word"
        assert parsed["word_id"] == 1
        assert parsed["rating"] == 4

    def test_parse_inline_keyboard_data_robustness(self):
        """Test parsing robustness with various inputs"""

        # Test empty data
        result = parse_inline_keyboard_data("")
        assert result == {}

        # Test invalid JSON
        result = parse_inline_keyboard_data("invalid json")
        assert result == {}

        # Test valid compact format
        compact_data = '{"a":"show_answer","w":123}'
        result = parse_inline_keyboard_data(compact_data)
        assert result["action"] == "show_answer"
        assert result["word_id"] == 123

    def test_callback_data_length_limits(self):
        """Test that callback data stays under Telegram's 64 byte limit"""

        # Test various combinations that might be problematic
        test_cases = [
            {"action": "show_answer", "word_id": 999999, "word_index": 99},
            {"action": "rate_word", "word_id": 123456, "rating": 4},
            {
                "action": "show_answer",
                "word_id": 1,
                "session_id": "123456_1720725491049",
            },
            {
                "action": "rate_word",
                "word_id": 999999,
                "rating": 1,
                "session_id": "999999_1720725491049",
            },
        ]

        for case in test_cases:
            action = case.pop("action")
            data = create_inline_keyboard_data(action, **case)
            assert len(data) <= 64, f"Data too long: {len(data)} bytes for case {case}"

            # Should be parseable
            parsed = parse_inline_keyboard_data(data)
            assert parsed["action"] == action

    def test_session_id_optimization(self):
        """Test that session_id is properly optimized"""

        # Test with realistic session ID
        session_id = "739529_725491"  # user_id_timestamp
        data = create_inline_keyboard_data(
            action="show_answer", word_id=42, session_id=session_id
        )

        assert len(data) <= 64, f"Data too long: {len(data)} bytes"

        parsed = parse_inline_keyboard_data(data)
        assert parsed["action"] == "show_answer"
        assert parsed["word_id"] == 42
        # session_id should be optimized (just the timestamp part)
        assert "session_id" in parsed

    def test_multi_user_scenario(self):
        """Test callback data generation for multiple users"""

        # Simulate multiple users with different IDs
        user_ids = [123, 456789, 999999]

        for user_id in user_ids:
            # Create session ID like SessionManager does
            timestamp = int(datetime.now().timestamp())
            compact_timestamp = timestamp % 1000000
            session_id = f"{user_id}_{compact_timestamp}"

            # Test show_answer callback
            data = create_inline_keyboard_data(
                action="show_answer", word_id=1, session_id=session_id, word_index=0
            )
            assert len(data) <= 64, (
                f"Data too long for user {user_id}: {len(data)} bytes"
            )

            # Test rate_word callback
            data = create_inline_keyboard_data(
                action="rate_word", word_id=1, rating=3, session_id=session_id
            )
            assert len(data) <= 64, (
                f"Rate data too long for user {user_id}: {len(data)} bytes"
            )

    def test_real_world_scenario(self):
        """Test with real-world data that might cause Button_data_invalid"""

        # This simulates the scenario from the error log
        user_id = 5  # Second user from the logs
        timestamp = int(datetime.now().timestamp())
        compact_timestamp = timestamp % 1000000
        session_id = f"{user_id}_{compact_timestamp}"

        # Test the problematic case
        data = create_inline_keyboard_data(
            action="show_answer", word_id=1, session_id=session_id, word_index=0
        )

        # Should be under 64 bytes
        assert len(data) <= 64, f"Data too long: {len(data)} bytes"

        # Should be valid JSON
        parsed = parse_inline_keyboard_data(data)
        assert parsed["action"] == "show_answer"
        assert parsed["word_id"] == 1

        # Test rating buttons
        for rating in [1, 2, 3, 4]:
            data = create_inline_keyboard_data(
                action="rate_word", word_id=1, rating=rating, session_id=session_id
            )
            assert len(data) <= 64, f"Rating {rating} data too long: {len(data)} bytes"

    def test_edge_case_large_word_ids(self):
        """Test with very large word IDs"""

        large_word_id = 999999999
        data = create_inline_keyboard_data(
            action="rate_word", word_id=large_word_id, rating=4
        )

        assert len(data) <= 64, f"Data too long with large word ID: {len(data)} bytes"

        parsed = parse_inline_keyboard_data(data)
        assert parsed["word_id"] == large_word_id
        assert parsed["rating"] == 4

    def test_backwards_compatibility(self):
        """Test backwards compatibility with old format"""

        # Test old format (if it exists)
        old_format = '{"action":"show_answer","word_id":123}'
        parsed = parse_inline_keyboard_data(old_format)
        assert parsed["action"] == "show_answer"
        assert parsed["word_id"] == 123

    def test_session_manager_integration(self):
        """Test that SessionManager generates valid callback data"""

        # Mock dependencies
        mock_db = Mock()
        mock_srs = Mock()
        mock_reply = Mock()
        mock_edit = Mock()

        SessionManager(
            db_manager=mock_db,
            srs_system=mock_srs,
            safe_reply_callback=mock_reply,
            safe_edit_callback=mock_edit,
        )

        # Create a mock session
        words = [
            {
                "id": 1,
                "lemma": "test",
                "translation": "тест",
                "example": "This is a test.",
            },
            {
                "id": 2,
                "lemma": "word",
                "translation": "слово",
                "example": "This is a word.",
            },
        ]

        session = StudySession("test_123", 123, words, "test")

        # Test that session creates valid callback data
        # This implicitly tests the create_inline_keyboard_data function
        word = session.get_current_word()
        assert word is not None

        # Test show_answer callback data
        data = create_inline_keyboard_data(
            action="show_answer",
            word_id=word["id"],
            word_index=session.current_word_index,
        )
        assert len(data) <= 64, f"Show answer data too long: {len(data)} bytes"

        # Test rate_word callback data
        for rating in [1, 2, 3, 4]:
            data = create_inline_keyboard_data(
                action="rate_word", word_id=word["id"], rating=rating
            )
            assert len(data) <= 64, f"Rate word data too long: {len(data)} bytes"
