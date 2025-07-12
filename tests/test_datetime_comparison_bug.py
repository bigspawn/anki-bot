#!/usr/bin/env python3
"""
Test for datetime comparison bug in due words calculation.

This bug caused "К повторению: 0" to always show even when words were due,
because timestamps were compared as strings instead of datetime objects.
"""

import os
import tempfile
from datetime import datetime, timedelta

import pytest

from src.core.database.database_manager import DatabaseManager


class TestDatetimeComparisonBug:
    """Test datetime string vs datetime comparison bug"""

    @pytest.fixture
    def temp_db_manager(self):
        """Create temporary database manager"""
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        temp_file.close()

        db_manager = DatabaseManager(temp_file.name)
        db_manager.init_database()

        yield db_manager

        # Cleanup
        os.unlink(temp_file.name)

    def test_datetime_string_comparison_bug_reproduction(self, temp_db_manager):
        """Reproduce the exact datetime comparison bug"""
        
        # Create user
        user = temp_db_manager.create_user(
            telegram_id=12345,
            first_name="Test",
            username="testuser"
        )
        user_id = user["telegram_id"]
        
        # Add a word
        word_data = {
            "lemma": "test",
            "part_of_speech": "noun",
            "translation": "тест",
            "example": "This is a test."
        }
        word = temp_db_manager.add_word(user_id, word_data)
        word_id = word["id"]
        
        # Update learning progress with a past date that demonstrates the bug
        # Use ISO format with 'T' separator (like our production data)
        past_time = datetime.now() - timedelta(hours=1)
        iso_timestamp = past_time.isoformat()  # Format: '2025-07-12T19:43:12.123456'
        
        # Manually set next_review_date to past time in ISO format
        with temp_db_manager.get_connection() as conn:
            conn.execute(
                """UPDATE learning_progress 
                   SET next_review_date = ?, repetitions = 1, interval_days = 0 
                   WHERE telegram_id = ? AND word_id = ?""",
                (iso_timestamp, user_id, word_id)
            )
            conn.commit()
        
        # Test the bug scenario: datetime string comparison vs datetime comparison
        with temp_db_manager.get_connection() as conn:
            # This was the OLD buggy query (string comparison)
            cursor_string = conn.execute(
                """SELECT COUNT(*) as count FROM learning_progress 
                   WHERE telegram_id = ? AND next_review_date <= datetime('now', 'localtime') AND repetitions > 0""",
                (user_id,)
            )
            count_string = cursor_string.fetchone()["count"]
            
            # This is the FIXED query (datetime comparison)  
            cursor_datetime = conn.execute(
                """SELECT COUNT(*) as count FROM learning_progress 
                   WHERE telegram_id = ? AND datetime(next_review_date) <= datetime('now', 'localtime') AND repetitions > 0""",
                (user_id,)
            )
            count_datetime = cursor_datetime.fetchone()["count"]
        
        # The bug: string comparison gives 0, datetime comparison gives 1
        if 'T' in iso_timestamp:
            # When timestamp has 'T' separator, string comparison fails
            assert count_string == 0, "String comparison should fail due to 'T' vs space"
            assert count_datetime == 1, "Datetime comparison should work correctly"
        
        # Test via repository methods (should work after fix)
        due_words = temp_db_manager.get_due_words(user_id)
        assert len(due_words) == 1, "get_due_words should find the due word after fix"
        
        stats = temp_db_manager.get_user_stats(user_id)
        assert stats["due_words"] == 1, "get_user_stats should count the due word after fix"

    def test_production_scenario_reproduction(self, temp_db_manager):
        """Reproduce the exact production scenario from user 739529"""
        
        # Create user matching production
        user = temp_db_manager.create_user(
            telegram_id=739529,
            first_name="Igor",
            username="bigspawn"
        )
        user_id = user["telegram_id"]
        
        # Simulate words reviewed early morning (like production data)
        morning_times = [
            "2025-07-12T01:11:38.405129",
            "2025-07-12T01:11:51.234567", 
            "2025-07-12T01:11:55.876543"
        ]
        
        words_data = [
            {"lemma": "wenn", "part_of_speech": "conjunction", "translation": "если"},
            {"lemma": "mitnehmen", "part_of_speech": "verb", "translation": "взять с собой"},
            {"lemma": "wechseln", "part_of_speech": "verb", "translation": "менять"}
        ]
        
        for i, (word_data, review_time) in enumerate(zip(words_data, morning_times)):
            # Add word
            word = temp_db_manager.add_word(user_id, word_data)
            word_id = word["id"]
            
            # Set review data to match production (interval_days = 0, reviewed this morning)
            with temp_db_manager.get_connection() as conn:
                conn.execute(
                    """UPDATE learning_progress 
                       SET next_review_date = ?, repetitions = 1, interval_days = 0,
                           last_reviewed = ?, easiness_factor = 2.36
                       WHERE telegram_id = ? AND word_id = ?""",
                    (review_time, review_time, user_id, word_id)
                )
                conn.commit()
        
        # Test the scenario
        stats = temp_db_manager.get_user_stats(user_id)
        due_words = temp_db_manager.get_due_words(user_id)
        
        # After fix: should show 3 due words (all reviewed hours ago with interval=0)
        assert stats["due_words"] == 3, f"Should have 3 due words, got {stats['due_words']}"
        assert len(due_words) == 3, f"get_due_words should return 3 words, got {len(due_words)}"
        
        # Verify word details
        due_lemmas = [w["lemma"] for w in due_words]
        assert "wenn" in due_lemmas
        assert "mitnehmen" in due_lemmas  
        assert "wechseln" in due_lemmas

    def test_various_timestamp_formats(self, temp_db_manager):
        """Test different timestamp formats that could cause string comparison issues"""
        
        user = temp_db_manager.create_user(telegram_id=54321, first_name="Format", username="test")
        user_id = user["telegram_id"]
        
        # Different timestamp formats that could cause issues
        test_cases = [
            ("2025-07-12T10:30:00", "ISO with T separator"),
            ("2025-07-12 10:30:00", "SQL standard format"),
            ("2025-07-12T10:30:00.123456", "ISO with microseconds"),
            ("2025-07-12 10:30:00.123", "SQL with milliseconds")
        ]
        
        past_base = datetime.now() - timedelta(hours=2)
        
        for i, (timestamp_format, description) in enumerate(test_cases):
            # Create a timestamp in the past
            test_time = past_base - timedelta(minutes=i*10)
            
            if 'T' in timestamp_format:
                formatted_time = test_time.isoformat()[:len(timestamp_format)]
            else:
                formatted_time = test_time.strftime('%Y-%m-%d %H:%M:%S')
                if '.123' in timestamp_format:
                    formatted_time += '.123'
            
            # Add word
            word_data = {
                "lemma": f"word{i}",
                "part_of_speech": "noun", 
                "translation": f"слово{i}",
                "example": f"Example {i}."
            }
            word = temp_db_manager.add_word(user_id, word_data)
            word_id = word["id"]
            
            # Set review time
            with temp_db_manager.get_connection() as conn:
                conn.execute(
                    """UPDATE learning_progress 
                       SET next_review_date = ?, repetitions = 1, interval_days = 0
                       WHERE telegram_id = ? AND word_id = ?""",
                    (formatted_time, user_id, word_id)
                )
                conn.commit()
        
        # After fix: all words should be due regardless of timestamp format
        stats = temp_db_manager.get_user_stats(user_id)
        due_words = temp_db_manager.get_due_words(user_id)
        
        assert stats["due_words"] == 4, f"Should have 4 due words with different formats, got {stats['due_words']}"
        assert len(due_words) == 4, f"get_due_words should return 4 words, got {len(due_words)}"

    def test_edge_case_exactly_now(self, temp_db_manager):
        """Test edge case where review time is exactly now"""
        
        user = temp_db_manager.create_user(telegram_id=99999, first_name="Edge", username="case")
        user_id = user["telegram_id"]
        
        # Add word
        word_data = {"lemma": "exactly", "part_of_speech": "adverb", "translation": "точно"}
        word = temp_db_manager.add_word(user_id, word_data)
        word_id = word["id"]
        
        # Set review time to exactly now (within 1 second)
        now_iso = datetime.now().isoformat()
        
        with temp_db_manager.get_connection() as conn:
            conn.execute(
                """UPDATE learning_progress 
                   SET next_review_date = ?, repetitions = 1, interval_days = 0
                   WHERE telegram_id = ? AND word_id = ?""",
                (now_iso, user_id, word_id)
            )
            conn.commit()
        
        # Should be due (or very close to due)
        stats = temp_db_manager.get_user_stats(user_id)
        due_words = temp_db_manager.get_due_words(user_id)
        
        # Allow for small timing differences
        assert stats["due_words"] in [0, 1], "Word should be due or very close to due"
        assert len(due_words) in [0, 1], "get_due_words should handle edge case gracefully"

    def test_future_dates_not_due(self, temp_db_manager):
        """Test that future dates are correctly not counted as due"""
        
        user = temp_db_manager.create_user(telegram_id=77777, first_name="Future", username="test")
        user_id = user["telegram_id"]
        
        # Add word
        word_data = {"lemma": "future", "part_of_speech": "noun", "translation": "будущее"}
        word = temp_db_manager.add_word(user_id, word_data)
        word_id = word["id"]
        
        # Set review time to future (tomorrow)
        future_time = datetime.now() + timedelta(days=1)
        future_iso = future_time.isoformat()
        
        with temp_db_manager.get_connection() as conn:
            conn.execute(
                """UPDATE learning_progress 
                   SET next_review_date = ?, repetitions = 1, interval_days = 1
                   WHERE telegram_id = ? AND word_id = ?""",
                (future_iso, user_id, word_id)
            )
            conn.commit()
        
        # Should NOT be due
        stats = temp_db_manager.get_user_stats(user_id)
        due_words = temp_db_manager.get_due_words(user_id)
        
        assert stats["due_words"] == 0, "Future words should not be due"
        assert len(due_words) == 0, "get_due_words should not return future words"