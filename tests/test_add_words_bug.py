#!/usr/bin/env python3
"""
Test for add words bug after telegram_id migration.

Error: KeyError 'id' when trying to add words to user.
This happens because code still tries to access user["id"] instead of user["telegram_id"].
"""

import os
import tempfile
from unittest.mock import AsyncMock, patch

import pytest

from src.bot_handler import BotHandler
from src.core.database.database_manager import DatabaseManager


class TestAddWordsBug:
    """Test add words functionality after telegram_id migration"""

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

    @pytest.fixture
    def mock_word_processor(self):
        """Mock word processor that returns processed words"""
        from src.word_processor import ProcessedWord

        with patch('src.bot_handler.get_word_processor') as mock_get_processor:
            mock_processor = AsyncMock()
            mock_processor.process_text = AsyncMock(return_value=[
                ProcessedWord(
                    word="test",
                    lemma="test",
                    part_of_speech="noun",
                    article=None,
                    translation="тест",
                    example="This is a test.",
                    additional_forms=None,
                    confidence=0.9
                )
            ])
            mock_get_processor.return_value = mock_processor
            yield mock_processor

    @pytest.fixture
    def mock_text_parser(self):
        """Mock text parser"""
        with patch('src.bot_handler.get_text_parser') as mock_get_parser:
            from unittest.mock import MagicMock
            mock_parser = MagicMock()
            mock_parser.extract_words.return_value = ["test"]
            mock_get_parser.return_value = mock_parser
            yield mock_parser

    def test_user_structure_after_migration(self, temp_db_manager):
        """Test that demonstrates the user structure change that caused the bug"""

        # Create user in database (new schema with telegram_id as PK)
        user = temp_db_manager.create_user(
            telegram_id=739529,
            first_name="Igor",
            username="bigspawn"
        )

        # Verify user was created with telegram_id as primary key
        assert "telegram_id" in user
        assert user["telegram_id"] == 739529
        assert "id" not in user  # This is the key: no 'id' field after migration!

        # This is what would cause KeyError: 'id' in the old code
        # The bug was that code tried to access user["id"] but field doesn't exist
        with pytest.raises(KeyError, match="'id'"):
            _ = user["id"]  # This would fail in production

        # But accessing telegram_id works fine
        assert user["telegram_id"] == 739529

    @pytest.mark.asyncio
    async def test_add_words_should_work_after_fix(
        self, temp_db_manager, mock_word_processor, mock_text_parser
    ):
        """Test that add words works correctly after fixing the bug"""

        # Create user
        temp_db_manager.create_user(
            telegram_id=739529,
            first_name="Igor",
            username="bigspawn"
        )

        # Create bot handler
        bot_handler = BotHandler()

        # Mock the database manager, word processor, and text parser
        with patch.object(bot_handler, 'db_manager', temp_db_manager), \
             patch.object(bot_handler, 'word_processor', mock_word_processor), \
             patch.object(bot_handler, 'text_parser', mock_text_parser):
            # Mock update object
            from unittest.mock import MagicMock
            mock_update = MagicMock()
            mock_update.effective_user.id = 739529
            mock_update.effective_user.first_name = "Igor"
            mock_update.effective_user.username = "bigspawn"
            mock_update.message.text = "test"

            # Mock the _safe_reply method to avoid Telegram API calls
            bot_handler._safe_reply = AsyncMock()

            # This should work without KeyError after the fix
            await bot_handler._process_text_for_user(mock_update, "test")

            # Verify word was added to database
            words = temp_db_manager.get_words_by_user(739529)
            assert len(words) >= 1, "At least one word should be added"

            # Verify the user's word was processed
            added_word = words[0]
            assert added_word["lemma"] == "test"
            assert added_word["translation"] == "тест"

    @pytest.mark.asyncio
    async def test_add_words_with_existing_user(
        self, temp_db_manager, mock_word_processor, mock_text_parser
    ):
        """Test adding words to existing user (common production scenario)"""

        # Pre-create user (simulates existing user in production)
        temp_db_manager.create_user(
            telegram_id=739529,
            first_name="Igor",
            username="bigspawn"
        )

        # Create bot handler
        bot_handler = BotHandler()

        with patch.object(bot_handler, 'db_manager', temp_db_manager), \
             patch.object(bot_handler, 'word_processor', mock_word_processor), \
             patch.object(bot_handler, 'text_parser', mock_text_parser):
            # Mock update object
            from unittest.mock import MagicMock
            mock_update = MagicMock()
            mock_update.effective_user.id = 739529
            mock_update.effective_user.first_name = "Igor"
            mock_update.effective_user.username = "bigspawn"
            mock_update.message.text = "beispiel"

            # Mock reply method
            bot_handler._safe_reply = AsyncMock()

            # Configure text parser to return word
            mock_text_parser.extract_words.return_value = ["beispiel"]

            # Configure mock to return different word
            from src.word_processor import ProcessedWord
            mock_word_processor.process_text = AsyncMock(return_value=[
                ProcessedWord(
                    word='beispiel',
                    lemma='beispiel',
                    part_of_speech='noun',
                    article='das',
                    translation='пример',
                    example='Das ist ein Beispiel.',
                    additional_forms=None,
                    confidence=0.9
                )
            ])

            # This should work for existing user
            await bot_handler._process_text_for_user(mock_update, "beispiel")

            # Verify word was added
            words = temp_db_manager.get_words_by_user(739529)
            assert len(words) >= 1

            # Find the word we just added
            added_words = [w for w in words if w["lemma"] == "beispiel"]
            assert len(added_words) == 1
            assert added_words[0]["translation"] == "пример"

    def test_user_lookup_after_migration(self, temp_db_manager):
        """Test that user lookup works correctly after migration"""

        # Create user
        user = temp_db_manager.create_user(
            telegram_id=123456,
            first_name="Test",
            username="testuser"
        )

        # Verify user structure after migration
        assert "telegram_id" in user
        assert user["telegram_id"] == 123456
        assert "id" not in user  # This field should not exist after migration

        # Test lookup by telegram_id
        found_user = temp_db_manager.get_user_by_telegram_id(123456)
        assert found_user is not None
        assert found_user["telegram_id"] == 123456
        assert "id" not in found_user  # Should not have old 'id' field

        # Test that old id-based lookups would fail
        # (This documents the breaking change from migration)
        assert "id" not in found_user, "Migration should remove internal 'id' field"
