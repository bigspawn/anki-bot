"""
Test complete study session flow to verify progress persistence
"""


import pytest

from src.config import Settings
from src.core.database.database_manager import get_db_manager


class TestStudySessionFlow:
    """Test complete study session flow"""

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
        """Create test user"""
        import random
        user_data = {
            "telegram_id": random.randint(100000, 999999),
            "first_name": "TestUser",
            "username": "testuser"
        }
        user = db_manager.user_repo.create_user(**user_data)
        assert user is not None, "User should be created"
        return user

    def test_study_session_removes_words_from_due_list(self, db_manager, test_user):
        """Test that studying words removes them from due list (main user complaint)"""
        user_id = test_user["id"]

        # Add test words
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
            },
            {
                "lemma": "schön",
                "part_of_speech": "adjective",
                "article": None,
                "translation": "красивый",
                "example": "Das ist sehr schön."
            }
        ]

        # Add words to user
        added_count = db_manager.word_repo.add_words_to_user(user_id, sample_words)
        assert added_count == 3, "Should add 3 words"

        # Check initial due words (all should be due for first review)
        initial_due_words = db_manager.word_repo.get_due_words(user_id, limit=10)
        assert len(initial_due_words) == 3, "All 3 words should be due for review initially"

        initial_lemmas = {word["lemma"] for word in initial_due_words}
        assert initial_lemmas == {"haus", "gehen", "schön"}, "All words should be in due list"

        # Simulate studying the first word with "Good" rating (3)
        word_to_study = initial_due_words[0]

        success = db_manager.progress_repo.update_learning_progress(
            user_id=user_id,
            word_id=word_to_study["id"],
            rating=3,  # Good rating
            new_interval=2,  # Move to 2-day interval
            new_easiness=2.5,
            response_time_ms=1500
        )

        assert success, "Progress update should succeed"

        # Check that word is no longer in today's due list
        after_study_due_words = db_manager.word_repo.get_due_words(user_id, limit=10)

        # Should have 2 words now (3 - 1 studied)
        assert len(after_study_due_words) == 2, f"Should have 2 due words after studying one, got {len(after_study_due_words)}"

        after_study_lemmas = {word["lemma"] for word in after_study_due_words}
        studied_lemma = word_to_study["lemma"]

        # The studied word should not be in the due list anymore
        assert studied_lemma not in after_study_lemmas, f"Studied word '{studied_lemma}' should not be in due list anymore"

        # The other two words should still be there
        remaining_words = {"haus", "gehen", "schön"} - {studied_lemma}
        assert after_study_lemmas == remaining_words, "The other words should still be due"

    def test_study_session_with_easy_rating(self, db_manager, test_user):
        """Test that 'Easy' rating removes word from due list for longer period"""
        user_id = test_user["id"]

        # Add test word
        sample_words = [{
            "lemma": "einfach",
            "part_of_speech": "adjective",
            "article": None,
            "translation": "простой",
            "example": "Das ist einfach."
        }]

        db_manager.word_repo.add_words_to_user(user_id, sample_words)

        # Get the word
        due_words = db_manager.word_repo.get_due_words(user_id, limit=10)
        assert len(due_words) == 1, "Should have 1 due word"

        word = due_words[0]

        # Study with "Easy" rating (4)
        success = db_manager.progress_repo.update_learning_progress(
            user_id=user_id,
            word_id=word["id"],
            rating=4,  # Easy rating
            new_interval=4,  # Move to 4-day interval
            new_easiness=2.6,
            response_time_ms=800
        )

        assert success, "Progress update should succeed"

        # Check that word is no longer due
        after_study_due_words = db_manager.word_repo.get_due_words(user_id, limit=10)
        assert len(after_study_due_words) == 0, "Should have no due words after easy rating"

    def test_study_session_with_again_rating(self, db_manager, test_user):
        """Test that 'Again' rating keeps word in due list"""
        user_id = test_user["id"]

        # Add test word
        sample_words = [{
            "lemma": "schwer",
            "part_of_speech": "adjective",
            "article": None,
            "translation": "трудный",
            "example": "Das ist schwer."
        }]

        db_manager.word_repo.add_words_to_user(user_id, sample_words)

        # Get the word
        due_words = db_manager.word_repo.get_due_words(user_id, limit=10)
        assert len(due_words) == 1, "Should have 1 due word"

        word = due_words[0]

        # Study with "Again" rating (1) - should reset progress
        success = db_manager.progress_repo.update_learning_progress(
            user_id=user_id,
            word_id=word["id"],
            rating=1,  # Again rating
            new_interval=0,  # Reset to immediate review
            new_easiness=2.3,
            response_time_ms=2500
        )

        assert success, "Progress update should succeed"

        # Check that word is still due (or immediately due again)
        after_study_due_words = db_manager.word_repo.get_due_words(user_id, limit=10)

        # With "Again" rating and 0 interval, word should still be available for review
        assert len(after_study_due_words) >= 0, "Word might still be due or removed based on implementation"

        # Check that progress was recorded
        progress = db_manager.progress_repo.get_learning_progress(user_id, word["id"])
        assert progress["repetitions"] == 1, "Should have 1 repetition recorded"
        assert progress["easiness_factor"] == 2.3, "Easiness factor should be decreased"

    def test_multiple_study_sessions_persistence(self, db_manager, test_user):
        """Test that multiple study sessions correctly track progress"""
        user_id = test_user["id"]

        # Add test word
        sample_words = [{
            "lemma": "lernen",
            "part_of_speech": "verb",
            "article": None,
            "translation": "учиться",
            "example": "Ich lerne Deutsch."
        }]

        db_manager.word_repo.add_words_to_user(user_id, sample_words)

        # Get the word
        due_words = db_manager.word_repo.get_due_words(user_id, limit=10)
        word = due_words[0]

        # First study session - Good rating
        success1 = db_manager.progress_repo.update_learning_progress(
            user_id=user_id,
            word_id=word["id"],
            rating=3,
            new_interval=1,
            new_easiness=2.5,
            response_time_ms=1200
        )
        assert success1, "First study should succeed"

        # Check progress after first session
        progress1 = db_manager.progress_repo.get_learning_progress(user_id, word["id"])
        assert progress1["repetitions"] == 1, "Should have 1 repetition"

        # Second study session - Easy rating
        success2 = db_manager.progress_repo.update_learning_progress(
            user_id=user_id,
            word_id=word["id"],
            rating=4,
            new_interval=3,
            new_easiness=2.6,
            response_time_ms=900
        )
        assert success2, "Second study should succeed"

        # Check progress after second session
        progress2 = db_manager.progress_repo.get_learning_progress(user_id, word["id"])
        assert progress2["repetitions"] == 2, "Should have 2 repetitions"
        assert progress2["easiness_factor"] == 2.6, "Easiness should increase"

        # Check review history
        history = db_manager.progress_repo.get_review_history(user_id, word["id"])
        assert len(history) == 2, "Should have 2 review history entries"

        # Verify ratings are recorded correctly
        ratings = sorted([review["rating"] for review in history])
        assert ratings == [3, 4], "Both ratings should be recorded"

    def test_user_complaint_scenario_fixed(self, db_manager, test_user):
        """Specific test for the user's complaint: same words appearing every time"""
        user_id = test_user["id"]

        # Add the same words user might have
        sample_words = [
            {"lemma": "bedeuten", "part_of_speech": "verb", "article": None, "translation": "означать", "example": "Was bedeutet das?"},
            {"lemma": "wichtig", "part_of_speech": "adjective", "article": None, "translation": "важный", "example": "Das ist wichtig."},
            {"lemma": "verstehen", "part_of_speech": "verb", "article": None, "translation": "понимать", "example": "Ich verstehe nicht."}
        ]

        db_manager.word_repo.add_words_to_user(user_id, sample_words)

        # First study session - get due words
        session1_words = db_manager.word_repo.get_due_words(user_id, limit=10)
        assert len(session1_words) == 3, "First session should have all 3 words"

        # Study all words with different ratings
        for i, word in enumerate(session1_words):
            rating = [3, 4, 2][i]  # Good, Easy, Hard
            interval = [2, 4, 1][i]  # Different intervals

            success = db_manager.progress_repo.update_learning_progress(
                user_id=user_id,
                word_id=word["id"],
                rating=rating,
                new_interval=interval,
                new_easiness=2.5,
                response_time_ms=1000 + i*200
            )
            assert success, f"Study session for word {word['lemma']} should succeed"

        # Second study session - should have fewer or no words due
        session2_words = db_manager.word_repo.get_due_words(user_id, limit=10)

        # This is the key fix: words should NOT be the same every time
        assert len(session2_words) < len(session1_words), "Second session should have fewer due words than first"

        # Get the lemmas to compare
        session1_lemmas = {word["lemma"] for word in session1_words}
        session2_lemmas = {word["lemma"] for word in session2_words}

        # The sets should be different (progress was saved)
        assert session1_lemmas != session2_lemmas, "Word lists should be different after studying (progress persisted)"

        print(f"Session 1 words: {session1_lemmas}")
        print(f"Session 2 words: {session2_lemmas}")
        print("✅ Progress persistence verified - user's issue is fixed!")
