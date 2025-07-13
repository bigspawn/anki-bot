#!/usr/bin/env python3
"""
Tests for mixed language processing functionality
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.text_parser import get_text_parser
from src.word_processor import WordProcessor


class TestMixedLanguageProcessing:
    """Test mixed language text processing"""

    @pytest.fixture
    def word_processor(self):
        """Get word processor instance with mocked OpenAI"""
        with patch("src.word_processor.AsyncOpenAI") as mock_openai:
            # Mock the OpenAI client
            mock_client = AsyncMock()
            mock_openai.return_value = mock_client

            processor = WordProcessor()
            processor.client = mock_client
            return processor

    @pytest.fixture
    def text_parser(self):
        """Get text parser instance"""
        return get_text_parser()

    def test_text_parser_filters_mixed_language(self, text_parser):
        """Test that text parser correctly filters mixed language input"""
        # The problematic text from user's example
        test_text = "Also, wo Sie bis jetzt gewohnt haben"

        words = text_parser.extract_words(test_text)

        print(f"Input: {test_text}")
        print(f"Extracted German words: {words}")

        # Should extract German words and filter English ones
        expected_german = ["wo", "sie", "bis", "jetzt", "gewohnt", "haben"]
        expected_filtered = ["also"]  # English word should be filtered

        for word in expected_german:
            assert word in [w.lower() for w in words], (
                f"German word '{word}' should be extracted"
            )

        for word in expected_filtered:
            assert word not in [w.lower() for w in words], (
                f"English word '{word}' should be filtered"
            )

    @pytest.mark.asyncio
    async def test_word_processor_handles_mixed_language(self, word_processor):
        """Test that word processor handles mixed language text correctly"""
        # Mock the process_words_batch method to avoid actual OpenAI calls
        mock_result = [
            MagicMock(word="wo", translation="где", lemma="wo"),
            MagicMock(word="Sie", translation="Вы", lemma="Sie"),
            MagicMock(word="bis", translation="до", lemma="bis"),
            MagicMock(word="jetzt", translation="сейчас", lemma="jetzt"),
            MagicMock(word="gewohnt", translation="жил", lemma="wohnen"),
            MagicMock(word="haben", translation="иметь", lemma="haben"),
        ]

        with patch.object(
            word_processor, "process_words_batch", return_value=mock_result
        ):
            # The problematic text from user's example
            test_text = "Also, wo Sie bis jetzt gewohnt haben"

            result = await word_processor.process_text(test_text)

            # Should successfully process German words despite mixed language input
            assert len(result) > 0, "Should process at least some German words"
            assert len(result) == 6, f"Should process 6 German words, got {len(result)}"

            # Verify specific words were processed
            processed_words = [word.word.lower() for word in result]
            expected_words = ["wo", "sie", "bis", "jetzt", "gewohnt", "haben"]

            for expected in expected_words:
                assert expected in processed_words, (
                    f"Expected word '{expected}' not found in processed results"
                )

    @pytest.mark.asyncio
    async def test_word_processor_logs_correctly(self, word_processor, caplog):
        """Test that word processor logs correct information for mixed language"""
        import logging

        caplog.set_level(logging.INFO)

        # Mock the process_words_batch method
        with patch.object(word_processor, "process_words_batch", return_value=[]):
            test_text = "Also, wo Sie bis jetzt gewohnt haben"

            await word_processor.process_text(test_text)

            # Check that it logs finding German words instead of rejecting the text
            assert "Found" in caplog.text and "German words" in caplog.text
            assert "Text does not appear to be German" not in caplog.text

    @pytest.mark.asyncio
    async def test_word_processor_handles_no_german_words(self, word_processor):
        """Test behavior when text contains no German words"""
        with patch.object(word_processor, "process_words_batch", return_value=[]):
            # Text with no German words
            test_text = "Hello world, how are you today?"

            result = await word_processor.process_text(test_text)

            # Should return empty list
            assert len(result) == 0
