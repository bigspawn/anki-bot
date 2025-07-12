"""
Integration test for exercise completion workflow.
Tests the complete flow from completing an exercise to getting new words in the next session.
"""

import os
import tempfile

import pytest

from src.core.database.database_manager import DatabaseManager


class TestExerciseCompletionWorkflow:
    """Test the complete exercise completion workflow"""

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
            "telegram_id": 739529,
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
            {
                "lemma": "buch",
                "part_of_speech": "noun",
                "article": "das",
                "translation": "book",
                "example": "Das Buch ist interessant.",
                "confidence": 0.85,
            },
        ]

    def test_complete_exercise_workflow(self, temp_db_manager, sample_user_data, sample_words_data):
        """Test complete exercise workflow: add words, complete exercise, get new words"""

        # 1. Create user
        user = temp_db_manager.create_user(**sample_user_data)
        assert user is not None
        user_id = user["telegram_id"]

        # 2. Add words to user's learning progress
        added_count = temp_db_manager.add_words_to_user(user_id, sample_words_data)
        assert added_count == 3, f"Expected 3 words to be added, got {added_count}"

        # 3. Verify all words are initially new (repetitions = 0)
        new_words = temp_db_manager.get_new_words(user_id)
        assert len(new_words) == 3, f"Expected 3 new words, got {len(new_words)}"

        # Verify they are all due for review
        due_words = temp_db_manager.get_due_words(user_id)
        assert len(due_words) == 3, f"Expected 3 due words, got {len(due_words)}"

        # 4. Complete first exercise - review first word with rating 3 (Good)
        first_word = new_words[0]
        word_id = first_word["id"]

        # Verify learning progress exists with initial values
        initial_progress = temp_db_manager.get_learning_progress(user_id, word_id)
        assert initial_progress is not None, "Learning progress should exist after adding words"
        assert initial_progress["repetitions"] == 0, "Initial repetitions should be 0"

        # Update learning progress (simulate completing exercise)
        success = temp_db_manager.update_learning_progress(user_id, word_id, rating=3)
        assert success, "Learning progress update should succeed"

        # 5. Verify learning progress was created and updated
        progress = temp_db_manager.get_learning_progress(user_id, word_id)
        assert progress is not None, "Learning progress should exist after exercise completion"
        assert progress["repetitions"] == 1, f"Expected 1 repetition, got {progress['repetitions']}"
        assert progress["easiness_factor"] == 2.5, f"Expected easiness factor 2.5, got {progress['easiness_factor']}"
        assert progress["interval_days"] > 0, f"Expected positive interval, got {progress['interval_days']}"

        # 6. Verify review history was created
        review_history = temp_db_manager.get_review_history(user_id, word_id)
        assert len(review_history) == 1, f"Expected 1 review record, got {len(review_history)}"
        assert review_history[0]["rating"] == 3, f"Expected rating 3, got {review_history[0]['rating']}"

        # 7. Get new words for next session - should have 2 new words remaining
        remaining_new_words = temp_db_manager.get_new_words(user_id)
        assert len(remaining_new_words) == 2, f"Expected 2 remaining new words, got {len(remaining_new_words)}"

        # 8. Verify the completed word is no longer in new words
        new_word_ids = {word["id"] for word in remaining_new_words}
        assert word_id not in new_word_ids, "Completed word should not be in new words list"

        # 9. Complete second exercise with rating 4 (Easy)
        second_word = remaining_new_words[0]
        second_word_id = second_word["id"]

        success = temp_db_manager.update_learning_progress(user_id, second_word_id, rating=4)
        assert success, "Second learning progress update should succeed"

        # 10. Verify we now have only 1 new word remaining
        final_new_words = temp_db_manager.get_new_words(user_id)
        assert len(final_new_words) == 1, f"Expected 1 remaining new word, got {len(final_new_words)}"

        # 11. Verify both completed words have proper learning progress
        all_words_with_progress = temp_db_manager.get_words_by_user(user_id)
        reviewed_words = [w for w in all_words_with_progress if w["repetitions"] > 0]
        assert len(reviewed_words) == 2, f"Expected 2 reviewed words, got {len(reviewed_words)}"

    def test_exercise_completion_with_different_ratings(self, temp_db_manager, sample_user_data, sample_words_data):
        """Test exercise completion with different ratings affects learning progress"""

        # Create user and add words
        user = temp_db_manager.create_user(**sample_user_data)
        user_id = user["telegram_id"]
        added_count = temp_db_manager.add_words_to_user(user_id, sample_words_data)
        assert added_count == 3

        new_words = temp_db_manager.get_new_words(user_id)
        assert len(new_words) == 3

        # Test different ratings
        ratings_to_test = [1, 2, 3, 4]  # Again, Hard, Good, Easy

        for i, rating in enumerate(ratings_to_test[:3]):  # Test first 3 words
            word = new_words[i]
            word_id = word["id"]

            # Complete exercise with specific rating
            success = temp_db_manager.update_learning_progress(user_id, word_id, rating=rating)
            assert success, f"Learning progress update should succeed for rating {rating}"

            # Verify learning progress
            progress = temp_db_manager.get_learning_progress(user_id, word_id)
            assert progress is not None, f"Learning progress should exist for rating {rating}"
            assert progress["repetitions"] == 1, f"Expected 1 repetition for rating {rating}"

            # Verify review history
            review_history = temp_db_manager.get_review_history(user_id, word_id)
            assert len(review_history) == 1, f"Expected 1 review record for rating {rating}"
            assert review_history[0]["rating"] == rating, f"Expected rating {rating} in history"

        # Verify final state
        final_new_words = temp_db_manager.get_new_words(user_id)
        assert len(final_new_words) == 0, "Should have no new words remaining"

    def test_multiple_exercise_sessions(self, temp_db_manager, sample_user_data, sample_words_data):
        """Test multiple exercise sessions with the same word"""

        # Create user and add one word
        user = temp_db_manager.create_user(**sample_user_data)
        user_id = user["telegram_id"]
        added_count = temp_db_manager.add_words_to_user(user_id, [sample_words_data[0]])
        assert added_count == 1

        new_words = temp_db_manager.get_new_words(user_id)
        assert len(new_words) == 1

        word_id = new_words[0]["id"]

        # Complete multiple exercises for the same word
        for repetition in range(1, 4):  # Do 3 repetitions
            success = temp_db_manager.update_learning_progress(user_id, word_id, rating=3)
            assert success, f"Learning progress update should succeed for repetition {repetition}"

            # Verify repetition count increases
            progress = temp_db_manager.get_learning_progress(user_id, word_id)
            assert progress["repetitions"] == repetition, f"Expected {repetition} repetitions, got {progress['repetitions']}"

        # Verify review history has all records
        review_history = temp_db_manager.get_review_history(user_id, word_id)
        assert len(review_history) == 3, f"Expected 3 review records, got {len(review_history)}"

    def test_exercise_completion_creates_missing_progress(self, temp_db_manager, sample_user_data):
        """Test that exercise completion creates learning progress when it's missing"""

        # Create user and word manually without learning progress
        user = temp_db_manager.create_user(**sample_user_data)
        user_id = user["telegram_id"]

        # Create word directly without learning progress
        word_data = {
            "lemma": "test_word",
            "part_of_speech": "noun",
            "article": "das",
            "translation": "test",
            "example": "This is a test.",
            "confidence": 0.9,
        }

        word = temp_db_manager.word_repo.create_word(word_data)
        assert word is not None
        word_id = word["id"]

        # Verify no learning progress exists (since we created word directly, not through add_words_to_user)
        progress = temp_db_manager.get_learning_progress(user_id, word_id)
        assert progress is None, "Should not have learning progress initially"

        # Complete exercise - this should create learning progress
        success = temp_db_manager.update_learning_progress(user_id, word_id, rating=3)
        assert success, "Learning progress update should succeed and create missing progress"

        # Verify learning progress was created
        progress = temp_db_manager.get_learning_progress(user_id, word_id)
        assert progress is not None, "Learning progress should be created"
        assert progress["repetitions"] == 1, f"Expected 1 repetition, got {progress['repetitions']}"
        assert progress["easiness_factor"] == 2.5, f"Expected easiness factor 2.5, got {progress['easiness_factor']}"

        # Verify review history was created
        review_history = temp_db_manager.get_review_history(user_id, word_id)
        assert len(review_history) == 1, f"Expected 1 review record, got {len(review_history)}"
        assert review_history[0]["rating"] == 3, f"Expected rating 3, got {review_history[0]['rating']}"

    def test_get_new_words_after_exercise_completion(self, temp_db_manager, sample_user_data, sample_words_data):
        """Test that get_new_words returns correct words after exercise completion"""

        # Create user and add words
        user = temp_db_manager.create_user(**sample_user_data)
        user_id = user["telegram_id"]
        added_count = temp_db_manager.add_words_to_user(user_id, sample_words_data)
        assert added_count == 3

        # Initially all words should be new
        new_words = temp_db_manager.get_new_words(user_id)
        assert len(new_words) == 3, "Should have 3 new words initially"

        # Complete exercise for one word
        first_word_id = new_words[0]["id"]
        success = temp_db_manager.update_learning_progress(user_id, first_word_id, rating=3)
        assert success, "Learning progress update should succeed"

        # Get new words again - should have 2 remaining
        remaining_new_words = temp_db_manager.get_new_words(user_id)
        assert len(remaining_new_words) == 2, "Should have 2 new words remaining"

        # Verify the completed word is not in the new words list
        remaining_word_ids = {word["id"] for word in remaining_new_words}
        assert first_word_id not in remaining_word_ids, "Completed word should not be in new words"

        # Complete another exercise
        second_word_id = remaining_new_words[0]["id"]
        success = temp_db_manager.update_learning_progress(user_id, second_word_id, rating=4)
        assert success, "Second learning progress update should succeed"

        # Get new words again - should have 1 remaining
        final_new_words = temp_db_manager.get_new_words(user_id)
        assert len(final_new_words) == 1, "Should have 1 new word remaining"

        # Complete final exercise
        final_word_id = final_new_words[0]["id"]
        success = temp_db_manager.update_learning_progress(user_id, final_word_id, rating=2)
        assert success, "Final learning progress update should succeed"

        # Get new words again - should have 0 remaining
        no_new_words = temp_db_manager.get_new_words(user_id)
        assert len(no_new_words) == 0, "Should have no new words remaining"

        # Verify all words have been reviewed
        all_words = temp_db_manager.get_words_by_user(user_id)
        assert len(all_words) == 3, "Should have 3 total words"
        for word in all_words:
            assert word["repetitions"] > 0, f"Word {word['lemma']} should have been reviewed"
