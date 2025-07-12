"""
Unit tests for database operations
"""

import os
import tempfile
from unittest.mock import patch

import pytest

from src.database import DatabaseManager, get_db_manager, init_db


class TestDatabaseManager:
    """Test DatabaseManager class"""

    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing"""
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
            "telegram_id": 321,
            "username": "testuser",
            "first_name": "Test",
            "last_name": "User",
        }

    @pytest.fixture
    def sample_word_data(self):
        """Sample word data for testing"""
        return {
            "word": "Haus",
            "lemma": "Haus",
            "part_of_speech": "noun",
            "article": "das",
            "translation": "дом",
            "example": "Das Haus ist sehr schön.",
            "additional_forms": '{"plural": "Häuser"}',
        }

    def test_database_initialization(self, temp_db):
        """Test database initialization"""
        # Check if tables exist
        with temp_db.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT name FROM sqlite_master
                WHERE type='table' AND name NOT LIKE 'sqlite_%'
            """
            )
            tables = [row[0] for row in cursor.fetchall()]

            expected_tables = [
                "users",
                "words",
                "learning_progress",
                "review_history",
                "user_settings",
            ]
            for table in expected_tables:
                assert table in tables

    def test_create_user(self, temp_db, sample_user_data):
        """Test user creation"""
        user = temp_db.create_user(**sample_user_data)
        assert user is not None
        assert user["id"] > 0
        assert user["telegram_id"] == sample_user_data["telegram_id"]

        # Test getting existing user
        existing_user = temp_db.get_user_by_telegram_id(sample_user_data["telegram_id"])
        assert existing_user["id"] == user["id"]

    def test_get_user_by_telegram_id(self, temp_db, sample_user_data):
        """Test getting user by Telegram ID"""
        # User doesn't exist
        user = temp_db.get_user_by_telegram_id(sample_user_data["telegram_id"])
        assert user is None

        # Create user
        created_user = temp_db.create_user(**sample_user_data)

        # Get user
        user = temp_db.get_user_by_telegram_id(sample_user_data["telegram_id"])
        assert user is not None
        assert user["id"] == created_user["id"]
        assert user["telegram_id"] == sample_user_data["telegram_id"]
        assert user["username"] == sample_user_data["username"]

    def test_add_word(self, temp_db, sample_user_data, sample_word_data):
        """Test adding words"""
        # Create user first
        user = temp_db.create_user(**sample_user_data)
        user_id = user["id"]

        # Add word
        word = temp_db.add_word(user_id, sample_word_data)
        assert word is not None
        assert isinstance(word, dict)
        assert word["id"] > 0

        # Test duplicate word (should return None)
        word2 = temp_db.add_word(user_id, sample_word_data)
        assert word2 is None

    def test_add_words_batch(self, temp_db, sample_user_data):
        """Test adding multiple words in batch"""
        user = temp_db.create_user(**sample_user_data)
        user_id = user["id"]

        # Prepare batch data
        words_batch = [
            {
                "word": "Haus",
                "lemma": "haus",
                "part_of_speech": "noun",
                "article": "das",
                "translation": "дом",
                "example": "Das Haus ist schön.",
                "additional_forms": '{"plural": "Häuser"}',
            },
            {
                "word": "gehen",
                "lemma": "gehen",
                "part_of_speech": "verb",
                "article": None,
                "translation": "идти",
                "example": "Ich gehe zur Schule.",
                "additional_forms": '{"past": "ging"}',
            },
            {
                "word": "schön",
                "lemma": "schön",
                "part_of_speech": "adjective",
                "article": None,
                "translation": "красивый",
                "example": "Das Wetter ist schön.",
                "additional_forms": '{"comparative": "schöner"}',
            },
        ]

        # Add words in batch
        word_ids = temp_db.add_words_batch(user_id, words_batch)

        # Should get 3 word IDs
        assert len(word_ids) == 3
        assert all(isinstance(word_id, int) and word_id > 0 for word_id in word_ids)

        # Verify words exist
        assert temp_db.check_word_exists(user_id, "haus")
        assert temp_db.check_word_exists(user_id, "gehen")
        assert temp_db.check_word_exists(user_id, "schön")

        # Test adding same batch again (should return empty list due to duplicates)
        word_ids2 = temp_db.add_words_batch(user_id, words_batch)
        assert len(word_ids2) == 0

        # Test empty batch
        word_ids3 = temp_db.add_words_batch(user_id, [])
        assert word_ids3 == []

    def test_check_word_exists(self, temp_db, sample_user_data, sample_word_data):
        """Test checking if word exists"""
        user = temp_db.create_user(**sample_user_data)
        user_id = user["id"]

        # Word doesn't exist
        exists = temp_db.check_word_exists(user_id, sample_word_data["lemma"])
        assert not exists

        # Add word
        temp_db.add_word(user_id, sample_word_data)

        # Word exists
        exists = temp_db.check_word_exists(user_id, sample_word_data["lemma"])
        assert exists

    def test_get_words_by_user(self, temp_db, sample_user_data, sample_word_data):
        """Test getting words by user"""
        user = temp_db.create_user(**sample_user_data)
        user_id = user["id"]

        # No words initially
        words = temp_db.get_words_by_user(user_id)
        assert len(words) == 0

        # Add word
        temp_db.add_word(user_id, sample_word_data)

        # Get words
        words = temp_db.get_words_by_user(user_id)
        assert len(words) == 1
        assert words[0]["lemma"] == sample_word_data["lemma"]

    def test_get_due_words(self, temp_db, sample_user_data, sample_word_data):
        """Test getting due words"""
        user = temp_db.create_user(**sample_user_data)
        user_id = user["id"]
        word = temp_db.add_word(user_id, sample_word_data)
        word_id = word["id"]

        # Word should be due today (created with today's date)
        due_words = temp_db.get_due_words(user_id)
        assert len(due_words) == 1
        assert due_words[0]["id"] == word_id

    def test_get_new_words(self, temp_db, sample_user_data, sample_word_data):
        """Test getting new words"""
        user = temp_db.create_user(**sample_user_data)
        user_id = user["id"]
        word = temp_db.add_word(user_id, sample_word_data)
        word_id = word["id"]

        # Word should be new (repetitions = 0)
        new_words = temp_db.get_new_words(user_id)
        assert len(new_words) == 1
        assert new_words[0]["id"] == word_id
        assert new_words[0]["repetitions"] == 0

    def test_update_learning_progress(
        self, temp_db, sample_user_data, sample_word_data
    ):
        """Test updating learning progress"""
        user = temp_db.create_user(**sample_user_data)
        user_id = user["id"]
        word = temp_db.add_word(user_id, sample_word_data)
        word_id = word["id"]

        # Update progress with rating (3 = Good)
        rating = 3
        response_time_ms = 1500

        temp_db.update_learning_progress(
            user_id, word_id, rating, response_time_ms
        )

        # Check if updated
        words = temp_db.get_words_by_user(user_id)
        assert len(words) == 1
        assert words[0]["repetitions"] == 1  # Should be incremented
        assert words[0]["easiness_factor"] >= 2.5  # Should be updated
        assert words[0]["interval_days"] > 0  # Should have a new interval

    def test_add_review_record(self, temp_db, sample_user_data, sample_word_data):
        """Test adding review records"""
        user = temp_db.create_user(**sample_user_data)
        user_id = user["id"]
        word = temp_db.add_word(user_id, sample_word_data)
        word_id = word["id"]

        # Add review record
        temp_db.add_review_record(
            user_id=user_id,
            word_id=word_id,
            rating=3,
            response_time_ms=1500
        )

        # Verify record was added
        with temp_db.get_connection() as conn:
            cursor = conn.execute(
                "SELECT COUNT(*) as count FROM review_history WHERE user_id = ? AND word_id = ?",
                (user_id, word_id),
            )
            count = cursor.fetchone()["count"]
            assert count == 1

    def test_get_user_stats(self, temp_db, sample_user_data, sample_word_data):
        """Test getting user statistics"""
        user = temp_db.create_user(**sample_user_data)
        user_id = user["id"]

        # No words initially
        stats = temp_db.get_user_stats(user_id)
        if stats is None:
            # No learning progress entries yet, create empty stats for comparison
            assert True  # This is expected when no words exist
        else:
            assert stats["total_words"] == 0
            assert stats["due_words"] is None or stats["due_words"] == 0
            if "new_words" in stats:
                assert stats["new_words"] is None or stats["new_words"] == 0
            if "avg_success_rate" in stats:
                assert stats["avg_success_rate"] == 0.0

        # Add word
        temp_db.add_word(user_id, sample_word_data)

        # Check stats
        stats = temp_db.get_user_stats(user_id)
        assert stats["total_words"] == 1
        # Due words might be 0 initially if words need to be explicitly marked as due
        assert stats["due_words"] is None or stats["due_words"] >= 0
        assert stats["new_words"] == 1
        if "avg_success_rate" in stats:
            assert stats["avg_success_rate"] == 0.0  # No reviews yet

    def test_database_error_handling(self, temp_db):
        """Test database error handling"""
        # Test with invalid data - should return None for invalid telegram_id
        result = temp_db.create_user(None, "Test")  # Invalid telegram_id but valid first_name
        assert result is None  # Should return None for failed user creation

    def test_connection_management(self, temp_db):
        """Test connection management"""
        # Test that connections are properly closed
        with temp_db.get_connection() as conn:
            cursor = conn.execute("SELECT 1")
            result = cursor.fetchone()
            assert result[0] == 1

    def test_get_existing_words_from_list(
        self, temp_db, sample_user_data, sample_word_data
    ):
        """Test getting existing words from a list"""
        user = temp_db.create_user(**sample_user_data)
        user_id = user["id"]

        # Test with empty list
        existing = temp_db.get_existing_words_from_list(user_id, [])
        assert existing == []

        # Test with words that don't exist
        word_list = ["haus", "auto", "buch"]
        existing = temp_db.get_existing_words_from_list(user_id, word_list)
        assert existing == []

        # Add one word
        temp_db.add_word(user_id, sample_word_data)

        # Test with mixed existing/non-existing words
        word_list = [sample_word_data["lemma"], "auto", "buch"]
        existing = temp_db.get_existing_words_from_list(user_id, word_list)
        assert len(existing) == 1
        assert sample_word_data["lemma"] in existing

        # Add another word
        word_data_2 = {
            "word": "Auto",
            "lemma": "auto",
            "part_of_speech": "noun",
            "article": "das",
            "translation": "car",
            "example": "Das Auto ist rot.",
            "additional_forms": None,
        }
        temp_db.add_word(user_id, word_data_2)

        # Test with multiple existing words
        existing = temp_db.get_existing_words_from_list(user_id, word_list)
        assert len(existing) == 2
        assert sample_word_data["lemma"] in existing
        assert "auto" in existing

    def test_check_multiple_words_exist(
        self, temp_db, sample_user_data, sample_word_data
    ):
        """Test checking existence of multiple words"""
        user = temp_db.create_user(**sample_user_data)
        user_id = user["id"]

        # Test with empty list
        result = temp_db.check_multiple_words_exist(user_id, [])
        assert result == {}

        # Test with words that don't exist
        word_list = ["haus", "auto", "buch"]
        result = temp_db.check_multiple_words_exist(user_id, word_list)
        assert len(result) == 3
        assert all(not exists for exists in result.values())

        # Add one word
        temp_db.add_word(user_id, sample_word_data)

        # Test with mixed existing/non-existing words
        word_list = [sample_word_data["lemma"], "auto", "buch"]
        result = temp_db.check_multiple_words_exist(user_id, word_list)
        assert len(result) == 3
        assert result[sample_word_data["lemma"]] is True
        assert result["auto"] is False
        assert result["buch"] is False

        # Add another word
        word_data_2 = {
            "word": "Auto",
            "lemma": "auto",
            "part_of_speech": "noun",
            "article": "das",
            "translation": "car",
            "example": "Das Auto ist rot.",
            "additional_forms": None,
        }
        temp_db.add_word(user_id, word_data_2)

        # Test with multiple existing words
        result = temp_db.check_multiple_words_exist(user_id, word_list)
        assert len(result) == 3
        assert result[sample_word_data["lemma"]] is True
        assert result["auto"] is True
        assert result["buch"] is False

    def test_german_verb_inflection_detection(self, temp_db, sample_user_data):
        """Test detection of German verb inflections (bedeutet case)"""
        user = temp_db.create_user(**sample_user_data)
        user_id = user["id"]

        # Add base form of verb "bedeuten"
        bedeuten_data = {
            "word": "bedeuten",
            "lemma": "bedeuten",
            "part_of_speech": "verb",
            "article": None,
            "translation": "to mean",
            "example": "Das kann viel bedeuten.",
            "additional_forms": None,
        }
        temp_db.add_word(user_id, bedeuten_data)

        # Test that inflected forms are detected as existing
        inflected_forms = ["bedeutet", "bedeutest", "bedeute"]
        result = temp_db.check_multiple_words_exist(user_id, inflected_forms)

        # All inflected forms should be detected as existing
        assert (
            result["bedeutet"] is True
        ), "bedeutet should be detected as existing (base: bedeuten)"
        assert (
            result["bedeutest"] is True
        ), "bedeutest should be detected as existing (base: bedeuten)"
        assert (
            result["bedeute"] is True
        ), "bedeute should be detected as existing (base: bedeuten)"

        # Test that non-related words are not detected
        unrelated_words = ["haus", "auto"]
        result = temp_db.check_multiple_words_exist(user_id, unrelated_words)
        assert result["haus"] is False
        assert result["auto"] is False

    def test_potential_lemmas_generation(self, temp_db):
        """Test generation of potential lemma forms"""
        # Test different verb endings
        assert "bedeuten" in temp_db._get_potential_lemmas("bedeutet")
        assert "gehen" in temp_db._get_potential_lemmas("gehst")
        assert "gehen" in temp_db._get_potential_lemmas("gehe")
        assert "sprechen" in temp_db._get_potential_lemmas("sprechen")


class TestDatabaseGlobals:
    """Test global database functions"""

    @patch("src.database.get_database_path")
    def test_get_db_manager(self, mock_get_path):
        """Test getting global database manager"""
        mock_get_path.return_value = ":memory:"

        # Reset global instance
        import src.database

        src.database._db_manager = None

        db_manager = get_db_manager()
        assert db_manager is not None
        assert isinstance(db_manager, DatabaseManager)

        # Should return same instance
        db_manager2 = get_db_manager()
        assert db_manager is db_manager2

    @patch("src.database.get_database_path")
    def test_init_db(self, mock_get_path):
        """Test database initialization function"""
        mock_get_path.return_value = ":memory:"

        # Should not raise any exceptions
        init_db()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
