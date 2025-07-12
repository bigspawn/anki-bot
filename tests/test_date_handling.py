"""
Test date handling in database operations
"""

import pytest
import tempfile
import os
from datetime import datetime, date, timedelta
from unittest.mock import Mock, patch
import sqlite3

from src.core.database.database_manager import DatabaseManager
from src.core.database.connection import DatabaseConnection


class TestDateHandling:
    """Test date handling in database operations"""

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
    def sample_user_data(self):
        """Sample user data for testing"""
        return {
            "telegram_id": 12345,
            "first_name": "Test",
            "last_name": "User",
            "username": "testuser",
        }

    @pytest.fixture
    def sample_words_data(self):
        """Sample words data for testing"""
        return [
            {
                "lemma": "haus",
                "part_of_speech": "noun",
                "article": "das",
                "translation": "house",
                "example": "Das Haus ist groß.",
                "confidence": 0.9,
            },
            {
                "lemma": "auto",
                "part_of_speech": "noun",
                "article": "das",
                "translation": "car",
                "example": "Das Auto ist schnell.",
                "confidence": 0.8,
            },
        ]

    def test_date_format_conversion(self):
        """Test that different date formats are properly converted"""
        db_connection = DatabaseConnection(":memory:")
        
        with db_connection.get_connection() as conn:
            # Test different date formats
            test_cases = [
                ('2025-07-10 20:00:30', datetime(2025, 7, 10, 20, 0, 30)),
                ('2025-07-10 20:00:30.123', datetime(2025, 7, 10, 20, 0, 30, 123000)),
                ('2025-07-10', datetime(2025, 7, 10)),
            ]
            
            for date_str, expected_datetime in test_cases:
                # Insert a raw date string
                conn.execute(
                    "CREATE TEMP TABLE test_dates (id INTEGER PRIMARY KEY, test_date TIMESTAMP)"
                )
                conn.execute(
                    "INSERT INTO test_dates (test_date) VALUES (?)",
                    (date_str,)
                )
                
                # Retrieve and check conversion
                cursor = conn.execute("SELECT test_date FROM test_dates")
                result = cursor.fetchone()
                
                # The result should be a datetime object
                assert isinstance(result[0], datetime), f"Expected datetime, got {type(result[0])}"
                assert result[0] == expected_datetime, f"Expected {expected_datetime}, got {result[0]}"
                
                # Clean up
                conn.execute("DROP TABLE test_dates")

    def test_get_due_words_with_date_formats(self, temp_db_manager, sample_user_data, sample_words_data):
        """Test that get_due_words works with various date formats stored in database"""
        
        # Create user and add words
        user = temp_db_manager.create_user(**sample_user_data)
        user_id = user["id"]
        
        added_count = temp_db_manager.add_words_to_user(user_id, sample_words_data)
        assert added_count == 2

        # Get initial words (should be due)
        due_words = temp_db_manager.get_due_words(user_id, limit=10)
        assert len(due_words) == 2, f"Expected 2 due words, got {len(due_words)}"

        # Test that the date fields are properly converted
        for word in due_words:
            assert 'next_review_date' in word
            assert word['next_review_date'] is not None
            # The date should be a datetime object or string that can be processed
            if isinstance(word['next_review_date'], str):
                # Should be able to parse it
                try:
                    datetime.fromisoformat(word['next_review_date'])
                except ValueError:
                    # Try alternative formats
                    datetime.strptime(word['next_review_date'], '%Y-%m-%d %H:%M:%S')

    def test_get_due_words_with_past_dates(self, temp_db_manager, sample_user_data, sample_words_data):
        """Test that get_due_words correctly handles past dates"""
        
        # Create user and add words
        user = temp_db_manager.create_user(**sample_user_data)
        user_id = user["id"]
        
        added_count = temp_db_manager.add_words_to_user(user_id, sample_words_data)
        assert added_count == 2

        # Update one word's review date to be in the past
        words = temp_db_manager.get_words_by_user(user_id)
        first_word_id = words[0]["id"]
        
        # Update learning progress to set next review date to past
        with temp_db_manager.get_connection() as conn:
            past_date = datetime.now() - timedelta(days=1)
            conn.execute(
                "UPDATE learning_progress SET next_review_date = ? WHERE user_id = ? AND word_id = ?",
                (past_date.isoformat(), user_id, first_word_id)
            )
            conn.commit()

        # Get due words - should include the word with past date
        due_words = temp_db_manager.get_due_words(user_id, limit=10)
        assert len(due_words) >= 1, f"Expected at least 1 due word, got {len(due_words)}"
        
        # Find the word we updated
        updated_word = next((w for w in due_words if w["id"] == first_word_id), None)
        assert updated_word is not None, "Updated word should be in due words"

    def test_get_due_words_with_future_dates(self, temp_db_manager, sample_user_data, sample_words_data):
        """Test that get_due_words correctly excludes future dates"""
        
        # Create user and add words
        user = temp_db_manager.create_user(**sample_user_data)
        user_id = user["id"]
        
        added_count = temp_db_manager.add_words_to_user(user_id, sample_words_data)
        assert added_count == 2

        # Update all words' review dates to be in the future
        words = temp_db_manager.get_words_by_user(user_id)
        
        with temp_db_manager.get_connection() as conn:
            future_date = datetime.now() + timedelta(days=1)
            for word in words:
                conn.execute(
                    "UPDATE learning_progress SET next_review_date = ? WHERE user_id = ? AND word_id = ?",
                    (future_date.isoformat(), user_id, word["id"])
                )
            conn.commit()

        # Get due words - should be empty since all are in the future
        due_words = temp_db_manager.get_due_words(user_id, limit=10)
        assert len(due_words) == 0, f"Expected 0 due words, got {len(due_words)}"

    def test_date_handling_edge_cases(self, temp_db_manager, sample_user_data, sample_words_data):
        """Test edge cases in date handling"""
        
        # Create user and add words
        user = temp_db_manager.create_user(**sample_user_data)
        user_id = user["id"]
        
        added_count = temp_db_manager.add_words_to_user(user_id, sample_words_data)
        assert added_count == 2

        # Initially, all words should be due
        initial_due_words = temp_db_manager.get_due_words(user_id, limit=10)
        assert len(initial_due_words) == 2, f"Expected 2 initial due words, got {len(initial_due_words)}"

        # Test that the method doesn't crash with date format issues
        # This is the main test - that get_due_words doesn't raise date format errors
        try:
            due_words = temp_db_manager.get_due_words(user_id, limit=10)
            assert isinstance(due_words, list), "get_due_words should return a list"
            assert len(due_words) >= 0, "get_due_words should return non-negative length"
        except Exception as e:
            pytest.fail(f"get_due_words should not raise date format errors: {e}")

    def test_learning_progress_update_with_dates(self, temp_db_manager, sample_user_data, sample_words_data):
        """Test that learning progress updates handle dates correctly"""
        
        # Create user and add words
        user = temp_db_manager.create_user(**sample_user_data)
        user_id = user["id"]
        
        added_count = temp_db_manager.add_words_to_user(user_id, sample_words_data)
        assert added_count == 2

        # Get a word to update
        words = temp_db_manager.get_words_by_user(user_id)
        word_id = words[0]["id"]

        # Update learning progress
        success = temp_db_manager.update_learning_progress(user_id, word_id, rating=3)
        assert success, "Learning progress update should succeed"

        # Check that dates were updated properly
        progress = temp_db_manager.get_learning_progress(user_id, word_id)
        assert progress is not None
        assert progress["next_review_date"] is not None
        assert progress["last_reviewed"] is not None

        # Dates should be datetime objects or parseable strings
        if isinstance(progress["next_review_date"], str):
            try:
                datetime.fromisoformat(progress["next_review_date"])
            except ValueError:
                datetime.strptime(progress["next_review_date"], '%Y-%m-%d %H:%M:%S')

    def test_date_error_handling(self):
        """Test error handling for invalid date formats"""
        
        # Test the conversion functions directly
        from src.core.database.connection import DatabaseConnection
        
        db_conn = DatabaseConnection(":memory:")
        
        # Test invalid date formats
        with pytest.raises(ValueError, match="Invalid datetime format"):
            with db_conn.get_connection() as conn:
                # Insert invalid date format
                conn.execute(
                    "CREATE TEMP TABLE test_invalid_dates (id INTEGER PRIMARY KEY, test_date TIMESTAMP)"
                )
                conn.execute(
                    "INSERT INTO test_invalid_dates (test_date) VALUES (?)",
                    ("invalid-date-format",)
                )
                
                # This should raise an error when trying to fetch
                cursor = conn.execute("SELECT test_date FROM test_invalid_dates")
                result = cursor.fetchone()
                _ = result[0]  # This should trigger the conversion error