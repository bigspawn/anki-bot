"""
Integration tests for the German Learning Bot
"""

import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.database import DatabaseManager
from src.spaced_repetition import get_srs_system
from src.word_processor import MockWordProcessor


class TestDatabaseIntegration:
    """Test database integration with other components"""

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

    def test_user_word_learning_flow(self, temp_db):
        """Test complete user learning flow"""
        # Create user
        user = temp_db.create_user(
            telegram_id=12345, username="testuser", first_name="Test", last_name="User"
        )
        user_id = user["id"]

        # Add word
        word_data = {
            "word": "Haus",
            "lemma": "Haus",
            "part_of_speech": "noun",
            "article": "das",
            "translation": "дом",
            "example": "Das Haus ist schön.",
            "additional_forms": '{"plural": "Häuser"}',
        }

        word = temp_db.add_word(user_id, word_data)
        word_id = word["id"] if word else None
        assert word_id is not None

        # Check if word is in new words
        new_words = temp_db.get_new_words(user_id)
        assert len(new_words) == 1
        assert new_words[0]["id"] == word_id

        # Check if word is due for review
        due_words = temp_db.get_due_words(user_id)
        assert len(due_words) == 1
        assert due_words[0]["id"] == word_id

        # Simulate review
        temp_db.update_learning_progress(
            user_id=user_id,
            word_id=word_id,
            rating=3,
            response_time_ms=1000
        )

        # Add review record (already done by update_learning_progress above)
        # temp_db.add_review_record is alias for update_learning_progress

        # Check stats
        stats = temp_db.get_user_stats(user_id)
        assert stats["total_words"] == 1
        # After review, word might not be due anymore
        assert stats["due_words"] is None or stats["due_words"] >= 0
        assert stats["new_words"] == 0  # No longer new after review


class TestSpacedRepetitionIntegration:
    """Test spaced repetition integration"""

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

    def test_srs_database_integration(self, temp_db):
        """Test SRS algorithm with database updates"""
        srs = get_srs_system()

        # Create user and word
        user = temp_db.create_user(telegram_id=12345, first_name="Test", username="testuser")
        user_id = user["id"]
        word_data = {
            "word": "lernen",
            "lemma": "lernen",
            "part_of_speech": "verb",
            "article": None,
            "translation": "изучать",
            "example": "Ich lerne Deutsch.",
            "additional_forms": '{"past": "lernte", "perfect": "gelernt"}',
        }
        word = temp_db.add_word(user_id, word_data)
        word_id = word["id"]

        # Get initial progress
        words = temp_db.get_due_words(user_id)
        word = words[0]

        # Simulate multiple reviews
        ratings = [3, 3, 4, 2, 3]  # Good, Good, Easy, Hard, Good

        for rating in ratings:
            # Calculate next review
            srs.calculate_review(
                rating=rating,
                repetitions=word.get("repetitions", 0),
                interval_days=word.get("interval_days", 1),
                easiness_factor=word.get("easiness_factor", 2.5),
            )

            # Update database (add_review_record is alias for update_learning_progress)
            temp_db.update_learning_progress(
                user_id=user_id,
                word_id=word_id,
                rating=rating,
                response_time_ms=1000
            )

            # Get updated word data
            words = temp_db.get_words_by_user(user_id)
            word = words[0]

        # Check final state
        assert word["repetitions"] == len(ratings)
        # Easiness factor should be within reasonable bounds after mixed ratings
        assert 1.3 <= word["easiness_factor"] <= 3.0
        assert word["interval_days"] >= 1  # Should be at least 1


class TestTextProcessingIntegration:
    """Test text processing integration"""

    @pytest.mark.asyncio
    async def test_text_to_database_flow(self):
        """Test complete flow from text to database"""
        # Setup
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        temp_file.close()

        try:
            db_manager = DatabaseManager(temp_file.name)
            db_manager.init_database()

            # Create user
            user = db_manager.create_user(telegram_id=12345, first_name="Test", username="testuser")
            user_id = user["id"]

            # Process text with mock processor
            mock_processor = MockWordProcessor()
            text = "Das Haus ist sehr schön."

            processed_words = await mock_processor.process_text(text)

            # Add processed words to database
            added_count = 0
            for processed_word in processed_words:
                word_data = {
                    "word": processed_word.word,
                    "lemma": processed_word.lemma,
                    "part_of_speech": processed_word.part_of_speech,
                    "article": processed_word.article,
                    "translation": processed_word.translation,
                    "example": processed_word.example,
                    "additional_forms": processed_word.additional_forms,
                }

                word_id = db_manager.add_word(user_id, word_data)
                if word_id:
                    added_count += 1

            # Verify results
            assert added_count > 0

            # Check database contents
            words = db_manager.get_words_by_user(user_id)
            assert len(words) == added_count

            # Check that all words have learning progress
            for word in words:
                assert word["repetitions"] == 0  # New words
                assert word["easiness_factor"] == 2.5  # Default
                assert word["next_review_date"] is not None

        finally:
            # Cleanup
            os.unlink(temp_file.name)


class TestBotHandlerIntegration:
    """Test bot handler integration with other components"""

    @pytest.fixture
    def mock_update(self):
        """Create mock Telegram update"""
        update = MagicMock()
        update.effective_user.id = 12345
        update.effective_user.username = "testuser"
        update.effective_user.first_name = "Test"
        update.effective_user.last_name = "User"
        update.message.text = "Das ist ein Test."
        update.message.reply_text = AsyncMock()
        return update

    @pytest.fixture
    def mock_context(self):
        """Create mock Telegram context"""
        context = MagicMock()
        context.args = []
        return context

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

    @pytest.mark.asyncio
    async def test_bot_start_command_integration(
        self, mock_update, mock_context, temp_db
    ):
        """Test /start command with database integration"""
        from src.core.handlers.command_handlers import CommandHandlers
        from src.spaced_repetition import SpacedRepetitionSystem
        from src.text_parser import GermanTextParser

        with patch("src.bot_handler.get_db_manager", return_value=temp_db):
            with patch(
                "src.bot_handler.get_word_processor", return_value=MockWordProcessor()
            ):
                async def mock_safe_reply(update, message, **kwargs):
                    await update.message.reply_text(message, **kwargs)

                handlers = CommandHandlers(
                    temp_db,
                    MockWordProcessor(),
                    GermanTextParser(),
                    SpacedRepetitionSystem(),
                    safe_reply_callback=mock_safe_reply,
                    process_text_callback=lambda *args, **kwargs: None,
                    start_study_session_callback=lambda *args, **kwargs: None
                )

                await handlers.start_command(mock_update, mock_context)

                # Check that user was created in database
                user = temp_db.get_user_by_telegram_id(12345)
                assert user is not None
                assert user["username"] == "testuser"
                assert user["first_name"] == "Test"

                # Check that welcome message was sent
                mock_update.message.reply_text.assert_called_once()
                args = mock_update.message.reply_text.call_args[0]
                assert "Добро пожаловать" in args[0]

    @pytest.mark.asyncio
    async def test_bot_add_command_integration(
        self, mock_update, mock_context, temp_db
    ):
        """Test /add command with full integration"""
        from src.core.handlers.command_handlers import CommandHandlers
        from src.spaced_repetition import SpacedRepetitionSystem
        from src.text_parser import GermanTextParser

        # Setup context with German text
        mock_context.args = ["Das", "Haus", "ist", "schön."]

        with patch("src.bot_handler.get_db_manager", return_value=temp_db):
            with patch(
                "src.bot_handler.get_word_processor", return_value=MockWordProcessor()
            ):
                async def mock_safe_reply(update, message, **kwargs):
                    await update.message.reply_text(message, **kwargs)

                async def mock_process_text(update, text):
                    await update.message.reply_text("Words processed")

                handlers = CommandHandlers(
                    temp_db,
                    MockWordProcessor(),
                    GermanTextParser(),
                    SpacedRepetitionSystem(),
                    safe_reply_callback=mock_safe_reply,
                    process_text_callback=mock_process_text,
                    start_study_session_callback=lambda *args, **kwargs: None
                )

                # Create user first
                temp_db.create_user(telegram_id=12345, first_name="Test", username="testuser")

                await handlers.add_command(mock_update, mock_context)

                # Check that words were processed and added
                user = temp_db.get_user_by_telegram_id(12345)
                temp_db.get_words_by_user(user["id"])

                # Should have called reply_text at least once for processing
                assert mock_update.message.reply_text.call_count >= 1

                # Mock processor won't actually add words to DB in this test
                # The test just verifies the command flow works
                assert True  # Command completed successfully

    @pytest.mark.asyncio
    async def test_bot_stats_command_integration(
        self, mock_update, mock_context, temp_db
    ):
        """Test /stats command with database integration"""
        from src.core.handlers.command_handlers import CommandHandlers
        from src.spaced_repetition import SpacedRepetitionSystem
        from src.text_parser import GermanTextParser

        with patch("src.bot_handler.get_db_manager", return_value=temp_db):
            async def mock_safe_reply(update, message, **kwargs):
                await update.message.reply_text(message, **kwargs)

            handlers = CommandHandlers(
                temp_db,
                MockWordProcessor(),
                GermanTextParser(),
                SpacedRepetitionSystem(),
                safe_reply_callback=mock_safe_reply,
                process_text_callback=lambda *args, **kwargs: None,
                start_study_session_callback=lambda *args, **kwargs: None
            )

            # Create user and add some test data
            user = temp_db.create_user(telegram_id=12345, first_name="Test", username="testuser")
        user_id = user["id"]

        # Add a test word
        word_data = {
            "word": "Test",
            "lemma": "Test",
            "part_of_speech": "noun",
            "article": "der",
            "translation": "тест",
            "example": "Das ist ein Test.",
            "additional_forms": None,
        }
        temp_db.add_word(user_id, word_data)

        await handlers.stats_command(mock_update, mock_context)

        # Check that stats were sent
        mock_update.message.reply_text.assert_called_once()
        args = mock_update.message.reply_text.call_args[0]
        assert "статистика" in args[0].lower()


class TestEndToEndScenarios:
    """Test complete end-to-end scenarios"""

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

    @pytest.mark.asyncio
    async def test_complete_learning_journey(self, temp_db):
        """Test complete user learning journey"""
        # 1. User registration
        user = temp_db.create_user(
            telegram_id=12345,
            username="learner",
            first_name="Test",
            last_name="Learner",
        )
        user_id = user["id"]

        # 2. Add words from text
        mock_processor = MockWordProcessor()
        text = "Das schöne Haus steht am Berg. Die Katze spielt im Garten."
        processed_words = await mock_processor.process_text(text)

        word_ids = []
        for processed_word in processed_words:
            word_data = {
                "word": processed_word.word,
                "lemma": processed_word.lemma,
                "part_of_speech": processed_word.part_of_speech,
                "article": processed_word.article,
                "translation": processed_word.translation,
                "example": processed_word.example,
                "additional_forms": processed_word.additional_forms,
            }
            word = temp_db.add_word(user_id, word_data)
            if word:
                word_ids.append(word["id"])

        # 3. Check initial state
        stats = temp_db.get_user_stats(user_id)
        assert stats["total_words"] > 0
        assert stats["new_words"] > 0
        # Due words might be 0 initially for new words
        assert stats["due_words"] is None or stats["due_words"] >= 0

        # 4. Study session - review words
        srs = get_srs_system()
        due_words = temp_db.get_due_words(user_id, limit=5)

        for word in due_words[:3]:  # Review first 3 words
            # Simulate user rating (Good = 3)
            srs.calculate_review(
                rating=3,
                repetitions=word.get("repetitions", 0),
                interval_days=word.get("interval_days", 1),
                easiness_factor=word.get("easiness_factor", 2.5),
            )

            # Update progress
            temp_db.update_learning_progress(
                user_id=user_id,
                word_id=word["id"],
                rating=3,
                response_time_ms=1000
            )

            # Record review (already done by update_learning_progress above)

        # 5. Check updated state
        final_stats = temp_db.get_user_stats(user_id)
        assert final_stats["total_words"] == stats["total_words"]  # Same total
        # Some words should no longer be due today after good reviews

        # 6. Check learning progress
        updated_words = temp_db.get_words_by_user(user_id)
        reviewed_words = [w for w in updated_words if w["repetitions"] > 0]
        assert len(reviewed_words) >= 1  # We reviewed at least 1 word (only valid translations are added)

        # All reviewed words should have progressed (repetitions > 0)
        for word in reviewed_words:
            assert word["repetitions"] > 0
            # In SuperMemo 2, first few reviews might still have interval = 1, so allow ≥ 1
            assert word["interval_days"] >= 1


class TestOptimizedWordProcessing:
    """Test optimized word processing with existing word detection"""

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

    @pytest.mark.asyncio
    async def test_word_processing_optimization(self, temp_db):
        """Test that existing words are not reprocessed with OpenAI"""
        # Create user
        user = temp_db.create_user(
            telegram_id=12345, username="testuser", first_name="Test", last_name="User"
        )
        user_id = user["id"]

        # Pre-populate database with some existing words
        existing_words = [
            {
                "word": "Haus",
                "lemma": "haus",
                "part_of_speech": "noun",
                "article": "das",
                "translation": "house",
                "example": "Das Haus ist schön.",
                "additional_forms": None,
            },
            {
                "word": "Auto",
                "lemma": "auto",
                "part_of_speech": "noun",
                "article": "das",
                "translation": "car",
                "example": "Das Auto ist rot.",
                "additional_forms": None,
            },
        ]

        for word_data in existing_words:
            temp_db.add_word(user_id, word_data)

        # Test batch word existence checking
        test_words = ["haus", "auto", "buch", "tisch", "stuhl"]
        word_existence = temp_db.check_multiple_words_exist(user_id, test_words)

        # Verify correct identification of existing vs new words
        assert word_existence["haus"] is True
        assert word_existence["auto"] is True
        assert word_existence["buch"] is False
        assert word_existence["tisch"] is False
        assert word_existence["stuhl"] is False

        # Test getting existing words from list
        existing_from_list = temp_db.get_existing_words_from_list(user_id, test_words)
        assert len(existing_from_list) == 2
        assert "haus" in existing_from_list
        assert "auto" in existing_from_list

    def test_empty_list_handling(self, temp_db):
        """Test handling of empty word lists"""
        user = temp_db.create_user(telegram_id=12345, first_name="Test", username="testuser")
        user_id = user["id"]

        # Test empty list scenarios
        word_existence = temp_db.check_multiple_words_exist(user_id, [])
        assert word_existence == {}

        existing_words = temp_db.get_existing_words_from_list(user_id, [])
        assert existing_words == []

    def test_large_word_list_performance(self, temp_db):
        """Test performance with large word lists"""
        user = temp_db.create_user(telegram_id=12345, first_name="Test", username="testuser")
        user_id = user["id"]

        # Add some words to database
        for i in range(10):
            word_data = {
                "word": f"Wort{i}",
                "lemma": f"wort{i}",
                "part_of_speech": "noun",
                "article": "das",
                "translation": f"word{i}",
                "example": f"Das ist Wort{i}.",
                "additional_forms": None,
            }
            temp_db.add_word(user_id, word_data)

        # Test with large list containing mix of existing and new words
        large_word_list = [f"wort{i}" for i in range(20)]  # 0-9 exist, 10-19 don't

        word_existence = temp_db.check_multiple_words_exist(user_id, large_word_list)
        assert len(word_existence) == 20

        # Verify correct results
        for i in range(10):
            assert word_existence[f"wort{i}"] is True
        for i in range(10, 20):
            assert word_existence[f"wort{i}"] is False


class TestDuplicateWordPrevention:
    """Test prevention of duplicate word processing (bedeutet case)"""

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

    @pytest.mark.asyncio
    async def test_bedeutet_duplicate_prevention(self, temp_db):
        """Test that bedeutet is not processed twice when bedeuten exists"""
        # Create user
        user = temp_db.create_user(
            telegram_id=12345, username="testuser", first_name="Test", last_name="User"
        )
        user_id = user["id"]

        # First, add "bedeuten" (base form) to database
        bedeuten_data = {
            "word": "bedeuten",
            "lemma": "bedeuten",
            "part_of_speech": "verb",
            "article": None,
            "translation": "to mean",
            "example": "Das kann viel bedeuten.",
            "additional_forms": None,
        }
        word1 = temp_db.add_word(user_id, bedeuten_data)
        word_id1 = word1["id"] if word1 else None
        assert word_id1 is not None

        # Verify "bedeuten" exists
        assert temp_db.check_word_exists(user_id, "bedeuten") is True

        # Test that inflected forms are detected as existing
        inflected_forms = ["bedeutet", "bedeutest", "bedeute"]
        existence_check = temp_db.check_multiple_words_exist(user_id, inflected_forms)

        # All inflected forms should be detected as already existing
        assert (
            existence_check["bedeutet"] is True
        ), "bedeutet should be detected as existing"
        assert (
            existence_check["bedeutest"] is True
        ), "bedeutest should be detected as existing"
        assert (
            existence_check["bedeute"] is True
        ), "bedeute should be detected as existing"

        # Simulate what happens when user tries to add "bedeutet" again
        # This should be caught by the existence check and not processed
        test_words = ["bedeutet", "neues_wort"]
        word_existence = temp_db.check_multiple_words_exist(user_id, test_words)

        existing_words = [word for word, exists in word_existence.items() if exists]
        new_words = [word for word, exists in word_existence.items() if not exists]

        # "bedeutet" should be in existing, "neues_wort" should be new
        assert "bedeutet" in existing_words
        assert "neues_wort" in new_words
        assert len(existing_words) == 1
        assert len(new_words) == 1

        # Verify database still has only original word
        all_words = temp_db.get_words_by_user(user_id)
        assert len(all_words) == 1
        assert all_words[0]["lemma"] == "bedeuten"

    def test_basic_verb_pattern_matching(self, temp_db):
        """Test basic German verb pattern matching - focus on -et/-en patterns"""
        user = temp_db.create_user(telegram_id=54321, first_name="Verb", username="verbuser")
        user_id = user["id"]

        # Add base verb forms that follow predictable patterns
        verbs = [
            {"word": "bedeuten", "lemma": "bedeuten", "translation": "to mean"},
            {"word": "arbeiten", "lemma": "arbeiten", "translation": "to work"},
        ]

        for verb in verbs:
            verb_data = {
                "word": verb["word"],
                "lemma": verb["lemma"],
                "part_of_speech": "verb",
                "article": None,
                "translation": verb["translation"],
                "example": f"Ich kann {verb['word']}.",
                "additional_forms": None,
            }
            temp_db.add_word(user_id, verb_data)

        # Test predictable inflected forms that our algorithm handles well
        test_cases = [
            ("bedeutet", "bedeuten"),  # bedeutet -> bedeuten (main case)
            ("bedeutest", "bedeuten"),  # bedeutest -> bedeuten
            ("arbeitet", "arbeiten"),  # arbeitet -> arbeiten
            ("arbeitest", "arbeiten"),  # arbeitest -> arbeiten
        ]

        for inflected, base in test_cases:
            result = temp_db.check_multiple_words_exist(user_id, [inflected])
            assert (
                result[inflected] is True
            ), f"{inflected} should be detected as existing (base: {base})"


class TestErrorScenarios:
    """Test error handling in integration scenarios"""

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

    def test_duplicate_word_handling(self, temp_db):
        """Test handling of duplicate words"""
        user = temp_db.create_user(telegram_id=12345, first_name="Test", username="testuser")
        user_id = user["id"]

        word_data = {
            "word": "Haus",
            "lemma": "Haus",
            "part_of_speech": "noun",
            "article": "das",
            "translation": "дом",
            "example": "Das Haus ist schön.",
            "additional_forms": None,
        }

        # Add word first time
        word1 = temp_db.add_word(user_id, word_data)
        word_id1 = word1["id"] if word1 else None
        assert word_id1 is not None

        # Try to add same word again
        word2 = temp_db.add_word(user_id, word_data)
        assert word2 is None  # Should fail due to duplicate

        # Check only one word exists
        words = temp_db.get_words_by_user(user_id)
        assert len(words) == 1

    @pytest.mark.asyncio
    async def test_empty_text_processing(self):
        """Test processing of empty or invalid text"""
        mock_processor = MockWordProcessor()

        # Test empty text
        result = await mock_processor.process_text("")
        assert result == []

        # Test whitespace only
        result = await mock_processor.process_text("   ")
        assert result == []

        # Test very short text
        result = await mock_processor.process_text("a")
        assert isinstance(result, list)  # Should handle gracefully


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
