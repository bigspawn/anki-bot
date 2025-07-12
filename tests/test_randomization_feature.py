"""
Test randomization feature for study commands
"""

import pytest
import tempfile
import os
from typing import List, Dict, Any

from src.core.database.database_manager import DatabaseManager


class TestRandomizationFeature:
    """Test randomization feature in word retrieval methods"""

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
    def large_word_set(self):
        """Large set of words for testing randomization"""
        return [
            {
                "lemma": f"word{i:02d}",
                "part_of_speech": "noun",
                "translation": f"слово{i:02d}",
                "example": f"Example sentence {i}.",
                "confidence": 0.9,
            }
            for i in range(1, 21)  # 20 words
        ]

    def test_get_new_words_randomization(self, temp_db_manager, sample_user_data, large_word_set):
        """Test that get_new_words returns different orders when randomized"""
        
        # Create user and add words
        user = temp_db_manager.create_user(**sample_user_data)
        user_id = user["id"]
        
        added_count = temp_db_manager.add_words_to_user(user_id, large_word_set)
        assert added_count == 20, f"Expected 20 words to be added, got {added_count}"

        # Test randomization
        results = []
        for _ in range(5):
            new_words = temp_db_manager.get_new_words(user_id, limit=5, randomize=True)
            word_lemmas = [word["lemma"] for word in new_words]
            results.append(tuple(word_lemmas))

        # Should get different orders (with high probability)
        unique_orders = set(results)
        assert len(unique_orders) >= 3, f"Expected at least 3 unique orders, got {len(unique_orders)}"

    def test_get_new_words_non_randomized_consistency(self, temp_db_manager, sample_user_data, large_word_set):
        """Test that non-randomized results are consistent"""
        
        # Create user and add words
        user = temp_db_manager.create_user(**sample_user_data)
        user_id = user["id"]
        
        added_count = temp_db_manager.add_words_to_user(user_id, large_word_set)
        assert added_count == 20

        # Test non-randomized consistency
        results = []
        for _ in range(3):
            new_words = temp_db_manager.get_new_words(user_id, limit=5, randomize=False)
            word_lemmas = [word["lemma"] for word in new_words]
            results.append(tuple(word_lemmas))

        # All results should be identical
        unique_orders = set(results)
        assert len(unique_orders) == 1, f"Expected 1 unique order, got {len(unique_orders)}"

    def test_get_due_words_randomization(self, temp_db_manager, sample_user_data, large_word_set):
        """Test that get_due_words returns different orders when randomized"""
        
        # Create user and add words
        user = temp_db_manager.create_user(**sample_user_data)
        user_id = user["id"]
        
        added_count = temp_db_manager.add_words_to_user(user_id, large_word_set)
        assert added_count == 20

        # All words should be due initially
        due_words = temp_db_manager.get_due_words(user_id, limit=10, randomize=False)
        assert len(due_words) == 10, f"Expected 10 due words, got {len(due_words)}"

        # Test randomization
        results = []
        for _ in range(5):
            due_words = temp_db_manager.get_due_words(user_id, limit=5, randomize=True)
            word_lemmas = [word["lemma"] for word in due_words]
            results.append(tuple(word_lemmas))

        # Should get different orders (with high probability)
        unique_orders = set(results)
        assert len(unique_orders) >= 3, f"Expected at least 3 unique orders, got {len(unique_orders)}"

    def test_get_difficult_words_randomization(self, temp_db_manager, sample_user_data, large_word_set):
        """Test that get_difficult_words returns different orders when randomized"""
        
        # Create user and add words
        user = temp_db_manager.create_user(**sample_user_data)
        user_id = user["id"]
        
        added_count = temp_db_manager.add_words_to_user(user_id, large_word_set)
        assert added_count == 20

        # Create some difficult words by giving them low ratings repeatedly
        for i in range(1, 11):  # Make first 10 words difficult
            word_id = i
            # Give multiple low ratings to make them difficult (easiness_factor < 2.0)
            for _ in range(5):  # Multiple low ratings to drop easiness factor
                temp_db_manager.update_learning_progress(user_id, word_id, rating=1)

        # Test randomization
        results = []
        for _ in range(5):
            difficult_words = temp_db_manager.get_difficult_words(user_id, limit=5, randomize=True)
            word_lemmas = [word["lemma"] for word in difficult_words]
            results.append(tuple(word_lemmas))

        # Should have some difficult words
        assert len(results[0]) >= 3, "Should have at least 3 difficult words"

        # Should get different orders (with high probability)
        unique_orders = set(results)
        assert len(unique_orders) >= 2, f"Expected at least 2 unique orders, got {len(unique_orders)}"

    def test_backward_compatibility_default_randomization(self, temp_db_manager, sample_user_data, large_word_set):
        """Test that methods work with default randomization parameter"""
        
        # Create user and add words
        user = temp_db_manager.create_user(**sample_user_data)
        user_id = user["id"]
        
        added_count = temp_db_manager.add_words_to_user(user_id, large_word_set)
        assert added_count == 20

        # Test that methods work without explicit randomize parameter (should default to True)
        new_words = temp_db_manager.get_new_words(user_id, limit=5)
        due_words = temp_db_manager.get_due_words(user_id, limit=5)
        
        # Should work without error
        assert len(new_words) == 5
        assert len(due_words) == 5

        # Test with explicit parameters
        new_words_random = temp_db_manager.get_new_words(user_id, limit=5, randomize=True)
        new_words_ordered = temp_db_manager.get_new_words(user_id, limit=5, randomize=False)
        
        assert len(new_words_random) == 5
        assert len(new_words_ordered) == 5

    def test_randomization_with_limited_words(self, temp_db_manager, sample_user_data):
        """Test randomization behavior with limited number of words"""
        
        # Create user and add only 3 words
        user = temp_db_manager.create_user(**sample_user_data)
        user_id = user["id"]
        
        small_word_set = [
            {"lemma": "word1", "part_of_speech": "noun", "translation": "слово1", "example": "Example 1."},
            {"lemma": "word2", "part_of_speech": "noun", "translation": "слово2", "example": "Example 2."},
            {"lemma": "word3", "part_of_speech": "noun", "translation": "слово3", "example": "Example 3."},
        ]
        
        added_count = temp_db_manager.add_words_to_user(user_id, small_word_set)
        assert added_count == 3

        # Test that we get all 3 words regardless of randomization
        new_words_random = temp_db_manager.get_new_words(user_id, limit=5, randomize=True)
        new_words_ordered = temp_db_manager.get_new_words(user_id, limit=5, randomize=False)
        
        assert len(new_words_random) == 3
        assert len(new_words_ordered) == 3

        # Both should contain the same words (just potentially in different order)
        random_lemmas = {word["lemma"] for word in new_words_random}
        ordered_lemmas = {word["lemma"] for word in new_words_ordered}
        
        assert random_lemmas == ordered_lemmas == {"word1", "word2", "word3"}