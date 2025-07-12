"""
Tests for multi-user word isolation functionality
"""


import pytest

from src.config import Settings
from src.core.database.database_manager import get_db_manager


class TestMultiUserWordIsolation:
    """Test word isolation between different users"""

    def _create_user_and_get_id(self, db_manager, user_data):
        """Helper to create user and return ID"""
        user = db_manager.user_repo.create_user(**user_data)
        assert user is not None, f"User should be created with data: {user_data}"
        return user["id"]

    def _clean_test_data(self, db_manager):
        """Clean test data to avoid interference between tests"""
        with db_manager.db_connection.get_connection() as conn:
            # Delete in order to respect foreign key constraints
            conn.execute("DELETE FROM review_history")
            conn.execute("DELETE FROM learning_progress")
            conn.execute("DELETE FROM words")
            conn.execute("DELETE FROM users")
            conn.commit()

    @pytest.fixture
    def settings(self):
        """Test settings"""
        return Settings(
            telegram_bot_token="test_token",
            openai_api_key="test_key",
            allowed_users="321,123",
            database_url="sqlite:///:memory:"
        )

    @pytest.fixture
    def db_manager(self, settings):
        """Test database manager with in-memory database"""
        db_mgr = get_db_manager(settings.database_url)
        # Initialize the database
        db_mgr.init_database()
        return db_mgr

    @pytest.fixture
    def user_a_data(self):
        """Test data for user A"""
        import random
        return {
            "telegram_id": random.randint(100000, 999999),
            "first_name": "Alice",
            "username": "alice"
        }

    @pytest.fixture
    def user_b_data(self):
        """Test data for user B"""
        import random
        return {
            "telegram_id": random.randint(100000, 999999),
            "first_name": "Bob",
            "username": "bob"
        }

    @pytest.fixture
    def sample_words(self):
        """Sample German words for testing"""
        return [
            {
                "lemma": "haus",
                "part_of_speech": "noun",
                "article": "das",
                "translation": "дом",
                "example": "Das Haus ist groß."
            },
            {
                "lemma": "gehen",
                "part_of_speech": "verb",
                "article": None,
                "translation": "идти",
                "example": "Ich gehe nach Hause."
            }
        ]

    def test_users_can_add_same_words_independently(self, db_manager, user_a_data, user_b_data, sample_words):
        """Test that users can add the same words and they appear in their individual lists"""
        # Create users
        user_a_id = self._create_user_and_get_id(db_manager, user_a_data)
        user_b_id = self._create_user_and_get_id(db_manager, user_b_data)

        # User A adds words
        db_manager.word_repo.add_words_to_user(user_a_id, sample_words)

        # User B adds the same words
        db_manager.word_repo.add_words_to_user(user_b_id, sample_words)

        # Both users should see their words
        user_a_words = db_manager.word_repo.get_words_by_user(user_a_id)
        user_b_words = db_manager.word_repo.get_words_by_user(user_b_id)

        assert len(user_a_words) == 2, "User A should have 2 words"
        assert len(user_b_words) == 2, "User B should have 2 words"

        # Words should be the same lemmas but separate learning progress
        user_a_lemmas = {word["lemma"] for word in user_a_words}
        user_b_lemmas = {word["lemma"] for word in user_b_words}

        assert user_a_lemmas == {"haus", "gehen"}
        assert user_b_lemmas == {"haus", "gehen"}

    def test_words_exist_check_is_user_specific(self, db_manager, user_a_data, user_b_data, sample_words):
        """Test that word existence check is user-specific"""
        # Create users
        user_a_id = self._create_user_and_get_id(db_manager, user_a_data)
        user_b_id = self._create_user_and_get_id(db_manager, user_b_data)

        # User A adds a word
        db_manager.word_repo.add_words_to_user(user_a_id, [sample_words[0]])  # "haus"

        # Check existence for both users
        user_a_has_haus = db_manager.word_repo.check_word_exists(user_a_id, "haus")
        user_b_has_haus = db_manager.word_repo.check_word_exists(user_b_id, "haus")

        assert user_a_has_haus is True, "User A should have 'haus'"
        assert user_b_has_haus is False, "User B should NOT have 'haus'"

    def test_study_session_isolation(self, db_manager, user_a_data, user_b_data, sample_words):
        """Test that study sessions only show user's own words"""
        # Create users
        user_a_id = self._create_user_and_get_id(db_manager, user_a_data)
        user_b_id = self._create_user_and_get_id(db_manager, user_b_data)

        # User A adds words
        db_manager.word_repo.add_words_to_user(user_a_id, sample_words)

        # User B adds only one word
        db_manager.word_repo.add_words_to_user(user_b_id, [sample_words[0]])  # Only "haus"

        # Get words for study
        user_a_due_words = db_manager.word_repo.get_due_words(user_a_id, limit=10)
        user_b_due_words = db_manager.word_repo.get_due_words(user_b_id, limit=10)

        assert len(user_a_due_words) == 2, "User A should have 2 words for study"
        assert len(user_b_due_words) == 1, "User B should have 1 word for study"

        # User B should not see User A's second word
        user_b_lemmas = {word["lemma"] for word in user_b_due_words}
        assert user_b_lemmas == {"haus"}, "User B should only see 'haus'"

    def test_new_words_isolation(self, db_manager, user_a_data, user_b_data, sample_words):
        """Test that new words are isolated per user"""
        # Create users
        user_a_id = self._create_user_and_get_id(db_manager, user_a_data)
        user_b_id = self._create_user_and_get_id(db_manager, user_b_data)

        # User A adds both words
        db_manager.word_repo.add_words_to_user(user_a_id, sample_words)

        # User B adds only one word
        db_manager.word_repo.add_words_to_user(user_b_id, [sample_words[1]])  # Only "gehen"

        # Get new words for each user
        user_a_new_words = db_manager.word_repo.get_new_words(user_a_id, limit=10)
        user_b_new_words = db_manager.word_repo.get_new_words(user_b_id, limit=10)

        assert len(user_a_new_words) == 2, "User A should have 2 new words"
        assert len(user_b_new_words) == 1, "User B should have 1 new word"

        user_b_lemmas = {word["lemma"] for word in user_b_new_words}
        assert user_b_lemmas == {"gehen"}, "User B should only see 'gehen'"

    def test_word_statistics_isolation(self, db_manager, user_a_data, user_b_data, sample_words):
        """Test that word statistics are user-specific"""
        # Create users
        user_a_id = self._create_user_and_get_id(db_manager, user_a_data)
        user_b_id = self._create_user_and_get_id(db_manager, user_b_data)

        # User A adds both words
        db_manager.word_repo.add_words_to_user(user_a_id, sample_words)

        # User B adds only one word
        db_manager.word_repo.add_words_to_user(user_b_id, [sample_words[0]])  # Only "haus"

        # Get statistics for each user
        user_a_stats = db_manager.user_repo.get_user_stats(user_a_id)
        user_b_stats = db_manager.user_repo.get_user_stats(user_b_id)

        assert user_a_stats["total_words"] == 2, "User A should have 2 total words"
        assert user_b_stats["total_words"] == 1, "User B should have 1 total word"

        assert user_a_stats["new_words"] == 2, "User A should have 2 new words"
        assert user_b_stats["new_words"] == 1, "User B should have 1 new word"

    def test_shared_dictionary_but_isolated_progress(self, db_manager, user_a_data, user_b_data, sample_words):
        """Test that words table is shared but progress is isolated"""
        # Clean any existing test data
        self._clean_test_data(db_manager)

        # Create users
        user_a_id = self._create_user_and_get_id(db_manager, user_a_data)
        user_b_id = self._create_user_and_get_id(db_manager, user_b_data)

        # User A adds a word
        db_manager.word_repo.add_words_to_user(user_a_id, [sample_words[0]])  # "haus"

        # Check that word exists in global dictionary
        with db_manager.db_connection.get_connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM words WHERE lemma = ?", ("haus",))
            word_count = cursor.fetchone()[0]
            assert word_count == 1, "Word should exist in global dictionary"

        # User B adds the same word
        db_manager.word_repo.add_words_to_user(user_b_id, [sample_words[0]])  # "haus"

        # Word count should still be 1 (shared)
        with db_manager.db_connection.get_connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM words WHERE lemma = ?", ("haus",))
            word_count = cursor.fetchone()[0]
            assert word_count == 1, "Word should still be shared in global dictionary"

        # But learning progress should be separate
        with db_manager.db_connection.get_connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM learning_progress WHERE word_id = (SELECT id FROM words WHERE lemma = ?)", ("haus",))
            progress_count = cursor.fetchone()[0]
            assert progress_count == 2, "Should have 2 separate learning progress entries"

    def test_user_cannot_access_other_users_words_directly(self, db_manager, user_a_data, user_b_data, sample_words):
        """Test that users cannot directly access words they haven't added"""
        # Create users
        user_a_id = self._create_user_and_get_id(db_manager, user_a_data)
        user_b_id = self._create_user_and_get_id(db_manager, user_b_data)

        # User A adds a word
        db_manager.word_repo.add_words_to_user(user_a_id, [sample_words[0]])  # "haus"

        # Get the word ID from global dictionary
        with db_manager.db_connection.get_connection() as conn:
            cursor = conn.execute("SELECT id FROM words WHERE lemma = ?", ("haus",))
            cursor.fetchone()[0]

        # User B should not be able to access this word through their word list
        user_b_words = db_manager.word_repo.get_words_by_user(user_b_id)
        assert len(user_b_words) == 0, "User B should not see User A's words"

        # User B should not have this word in their learning progress
        user_b_has_word = db_manager.word_repo.check_word_exists(user_b_id, "haus")
        assert user_b_has_word is False, "User B should not have access to User A's word"
