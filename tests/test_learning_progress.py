"""
Tests for learning progress functionality
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch

from src.core.database.database_manager import get_db_manager
from src.config import Settings


class TestLearningProgress:
    """Test learning progress tracking and updates"""

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
        db_mgr.init_database()
        return db_mgr

    @pytest.fixture
    def test_user(self, db_manager):
        """Create test user and return user data"""
        import random
        user_data = {
            "telegram_id": random.randint(100000, 999999),
            "first_name": "TestUser",
            "username": "testuser"
        }
        user = db_manager.user_repo.create_user(**user_data)
        assert user is not None, "User should be created"
        return user

    @pytest.fixture
    def test_words(self, db_manager, test_user):
        """Create test words and return word data"""
        sample_words = [
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
        
        # Add words to user
        added_count = db_manager.word_repo.add_words_to_user(test_user["id"], sample_words)
        assert added_count == 2, "Should add 2 words"
        
        # Get the words with their IDs
        user_words = db_manager.word_repo.get_words_by_user(test_user["id"])
        assert len(user_words) == 2, "User should have 2 words"
        
        return user_words

    def test_initial_learning_progress_creation(self, db_manager, test_user, test_words):
        """Test that learning progress is created when words are added"""
        user_id = test_user["id"]
        
        # Check that learning progress exists for all words
        for word in test_words:
            progress = db_manager.progress_repo.get_learning_progress(user_id, word["id"])
            assert progress is not None, f"Learning progress should exist for word {word['lemma']}"
            assert progress["repetitions"] == 0, "Initial repetitions should be 0"
            assert progress["easiness_factor"] == 2.5, "Initial easiness factor should be 2.5"
            assert progress["interval_days"] == 1, "Initial interval should be 1 day"

    def test_update_learning_progress_good_rating(self, db_manager, test_user, test_words):
        """Test updating learning progress with good rating"""
        user_id = test_user["id"]
        word = test_words[0]  # Use first word
        word_id = word["id"]
        
        # Update progress with good rating (3)
        success = db_manager.progress_repo.update_learning_progress(
            user_id=user_id,
            word_id=word_id,
            rating=3,  # Good rating
            new_interval=2,
            new_easiness=2.5,
            response_time_ms=1500
        )
        
        assert success, "Progress update should succeed"
        
        # Check updated progress
        progress = db_manager.progress_repo.get_learning_progress(user_id, word_id)
        assert progress is not None, "Progress should exist after update"
        assert progress["repetitions"] == 1, "Repetitions should be incremented"
        assert progress["interval_days"] == 2, "Interval should be updated"
        assert progress["easiness_factor"] == 2.5, "Easiness factor should be updated"

    def test_update_learning_progress_again_rating(self, db_manager, test_user, test_words):
        """Test updating learning progress with 'again' rating (resets progress)"""
        user_id = test_user["id"]
        word = test_words[0]
        word_id = word["id"]
        
        # First, update with good rating
        db_manager.progress_repo.update_learning_progress(
            user_id=user_id,
            word_id=word_id,
            rating=3,
            new_interval=3,
            new_easiness=2.6,
            response_time_ms=1000
        )
        
        # Then update with 'again' rating (1)
        success = db_manager.progress_repo.update_learning_progress(
            user_id=user_id,
            word_id=word_id,
            rating=1,  # Again rating - should reset
            new_interval=1,
            new_easiness=2.3,
            response_time_ms=2000
        )
        
        assert success, "Progress update should succeed"
        
        # Check that progress was updated appropriately
        progress = db_manager.progress_repo.get_learning_progress(user_id, word_id)
        assert progress is not None, "Progress should exist after update"
        assert progress["interval_days"] == 1, "Interval should be reset to 1"
        assert progress["easiness_factor"] == 2.3, "Easiness factor should be decreased"

    def test_review_history_creation(self, db_manager, test_user, test_words):
        """Test that review history is created when progress is updated"""
        user_id = test_user["id"]
        word = test_words[0]
        word_id = word["id"]
        
        # Update progress
        success = db_manager.progress_repo.update_learning_progress(
            user_id=user_id,
            word_id=word_id,
            rating=3,
            new_interval=2,
            new_easiness=2.5,
            response_time_ms=1200
        )
        
        assert success, "Progress update should succeed"
        
        # Check review history
        history = db_manager.progress_repo.get_review_history(user_id, word_id, limit=1)
        assert len(history) == 1, "Should have one review history entry"
        
        review = history[0]
        assert review["user_id"] == user_id, "Review should belong to correct user"
        assert review["word_id"] == word_id, "Review should belong to correct word"
        assert review["rating"] == 3, "Review should have correct rating"
        assert review["response_time_ms"] == 1200, "Review should have correct response time"

    def test_multiple_reviews_tracking(self, db_manager, test_user, test_words):
        """Test that multiple reviews are tracked correctly"""
        user_id = test_user["id"]
        word = test_words[0]
        word_id = word["id"]
        
        # Perform multiple reviews
        ratings = [3, 4, 2, 3]  # Good, Easy, Hard, Good
        response_times = [1000, 800, 2000, 1200]
        
        for i, (rating, response_time) in enumerate(zip(ratings, response_times)):
            success = db_manager.progress_repo.update_learning_progress(
                user_id=user_id,
                word_id=word_id,
                rating=rating,
                new_interval=i + 2,  # Increasing intervals
                new_easiness=2.5 + (i * 0.1),  # Varying easiness
                response_time_ms=response_time
            )
            assert success, f"Review {i+1} should succeed"
        
        # Check final progress
        progress = db_manager.progress_repo.get_learning_progress(user_id, word_id)
        assert progress["repetitions"] == 4, "Should have 4 repetitions"
        
        # Check review history count
        history = db_manager.progress_repo.get_review_history(user_id, word_id)
        assert len(history) == 4, "Should have 4 review history entries"
        
        # Check that all ratings are recorded
        recorded_ratings = [review["rating"] for review in history]
        assert sorted(recorded_ratings) == sorted(ratings), "All ratings should be recorded"

    def test_next_review_date_calculation(self, db_manager, test_user, test_words):
        """Test that next review date is calculated correctly"""
        user_id = test_user["id"]
        word = test_words[0]
        word_id = word["id"]
        
        # Update progress with 3-day interval
        success = db_manager.progress_repo.update_learning_progress(
            user_id=user_id,
            word_id=word_id,
            rating=3,
            new_interval=3,
            new_easiness=2.5,
            response_time_ms=1000
        )
        
        assert success, "Progress update should succeed"
        
        # Check next review date
        progress = db_manager.progress_repo.get_learning_progress(user_id, word_id)
        next_review_date = progress["next_review_date"]
        if isinstance(next_review_date, str):
            next_review = datetime.fromisoformat(next_review_date.replace('Z', '+00:00'))
        else:
            next_review = next_review_date
        
        # Should be approximately 3 days from now (allowing some tolerance)
        expected_date = datetime.now() + timedelta(days=3)
        time_diff = abs((next_review - expected_date).total_seconds())
        
        assert time_diff < 3600, "Next review date should be approximately 3 days from now"

    def test_performance_stats_calculation(self, db_manager, test_user, test_words):
        """Test that performance statistics are calculated correctly"""
        user_id = test_user["id"]
        
        # Add reviews for multiple words
        word1_id = test_words[0]["id"]
        word2_id = test_words[1]["id"]
        
        # Word 1: Good performance (ratings 3, 4)
        db_manager.progress_repo.update_learning_progress(user_id, word1_id, 3, 2, 2.6, 1000)
        db_manager.progress_repo.update_learning_progress(user_id, word1_id, 4, 4, 2.7, 800)
        
        # Word 2: Mixed performance (ratings 1, 3)
        db_manager.progress_repo.update_learning_progress(user_id, word2_id, 1, 1, 2.3, 2000)
        db_manager.progress_repo.update_learning_progress(user_id, word2_id, 3, 2, 2.4, 1200)
        
        # Get performance stats
        stats = db_manager.progress_repo.get_performance_stats(user_id)
        
        assert stats is not None, "Performance stats should be available"
        assert stats["total_reviews"] == 4, "Should have 4 total reviews"
        assert stats["avg_rating"] > 0, "Should have positive average rating"
        assert stats.get("avg_response_time", 0) >= 0, "Should have non-negative average response time"

    def test_word_progress_isolation_between_users(self, db_manager, test_words):
        """Test that progress updates don't affect other users"""
        # Create two users
        import random
        user1_data = {"telegram_id": random.randint(100000, 999999), "first_name": "User1", "username": "user1"}
        user2_data = {"telegram_id": random.randint(100000, 999999), "first_name": "User2", "username": "user2"}
        
        user1 = db_manager.user_repo.create_user(**user1_data)
        user2 = db_manager.user_repo.create_user(**user2_data)
        
        # Add same words to both users
        sample_word = [{
            "lemma": "test_word",
            "part_of_speech": "noun",
            "article": "das",
            "translation": "тест",
            "example": "Das ist ein Test."
        }]
        
        db_manager.word_repo.add_words_to_user(user1["id"], sample_word)
        db_manager.word_repo.add_words_to_user(user2["id"], sample_word)
        
        # Get word IDs for both users
        user1_words = db_manager.word_repo.get_words_by_user(user1["id"])
        user2_words = db_manager.word_repo.get_words_by_user(user2["id"])
        
        word_id = user1_words[0]["id"]  # Same word ID for both users
        
        # Update progress for user1 only
        success = db_manager.progress_repo.update_learning_progress(
            user_id=user1["id"],
            word_id=word_id,
            rating=4,
            new_interval=5,
            new_easiness=2.8,
            response_time_ms=900
        )
        
        assert success, "User1 progress update should succeed"
        
        # Check that user1 progress was updated
        user1_progress = db_manager.progress_repo.get_learning_progress(user1["id"], word_id)
        assert user1_progress["repetitions"] == 1, "User1 should have 1 repetition"
        assert user1_progress["interval_days"] == 5, "User1 should have 5-day interval"
        
        # Check that user2 progress was not affected
        user2_progress = db_manager.progress_repo.get_learning_progress(user2["id"], word_id)
        assert user2_progress["repetitions"] == 0, "User2 should still have 0 repetitions"
        assert user2_progress["interval_days"] == 1, "User2 should still have 1-day interval"

    def test_database_error_handling(self, db_manager, test_user):
        """Test error handling when database operations fail"""
        user_id = test_user["id"]
        invalid_word_id = 99999  # Non-existent word ID
        
        # Try to update progress for non-existent word
        success = db_manager.progress_repo.update_learning_progress(
            user_id=user_id,
            word_id=invalid_word_id,
            rating=3,
            new_interval=2,
            new_easiness=2.5,
            response_time_ms=1000
        )
        
        # Should handle gracefully - either succeed (by creating record) or fail gracefully
        # The exact behavior depends on implementation, but it shouldn't crash
        assert isinstance(success, bool), "Should return boolean result"