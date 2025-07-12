"""
Unit tests for word processor
"""

import pytest
import json
import asyncio
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from src.word_processor import (
    WordProcessor,
    MockWordProcessor,
    ProcessedWord,
    get_word_processor,
    process_german_words,
    process_german_text,
)
from src.database import get_db_manager


class TestProcessedWord:
    """Test ProcessedWord dataclass"""

    def test_processed_word_creation(self):
        """Test ProcessedWord creation"""
        word = ProcessedWord(
            word="Haus",
            lemma="Haus",
            part_of_speech="noun",
            article="das",
            translation="дом",
            example="Das Haus ist schön.",
            additional_forms='{"plural": "Häuser"}',
            confidence=0.95,
        )

        assert word.word == "Haus"
        assert word.lemma == "Haus"
        assert word.part_of_speech == "noun"
        assert word.article == "das"
        assert word.translation == "дом"
        assert word.example == "Das Haus ist schön."
        assert word.additional_forms == '{"plural": "Häuser"}'
        assert word.confidence == 0.95

    def test_processed_word_defaults(self):
        """Test ProcessedWord default values"""
        word = ProcessedWord(
            word="test",
            lemma="test",
            part_of_speech="noun",
            article=None,
            translation="test",
            example="test",
            additional_forms=None,
        )

        assert word.confidence == 1.0  # Default value


class TestWordProcessor:
    """Test WordProcessor class"""

    @pytest.fixture
    def mock_openai_client(self):
        """Mock OpenAI client"""
        client = AsyncMock()
        return client

    @pytest.fixture
    def mock_global_db_manager(self):
        """Mock global database manager"""
        mock_db = Mock()
        mock_db.get_word_by_lemma.return_value = None  # No existing words by default
        return mock_db

    @pytest.fixture
    def word_processor(self, mock_openai_client, mock_global_db_manager):
        """Create WordProcessor with mocked client and isolated database"""
        with patch("src.word_processor.AsyncOpenAI", return_value=mock_openai_client):
            # Create a patcher for get_db_manager that we can control
            db_patcher = patch("src.word_processor.get_db_manager", return_value=mock_global_db_manager)
            db_patcher.start()
            
            processor = WordProcessor(api_key="test_key")
            processor.client = mock_openai_client
            
            # Store the patcher so we can stop it later if needed
            processor._db_patcher = db_patcher
            
            yield processor
            
            # Cleanup: stop the patcher
            db_patcher.stop()

    def test_processor_initialization(self, word_processor):
        """Test processor initialization"""
        # Model can be gpt-4 or newer models like o4-mini
        assert (
            word_processor.model in ["gpt-4", "o4-mini-2025-04-16"]
            or word_processor.model.startswith("gpt-")
            or word_processor.model.startswith("o")
        )
        assert word_processor.max_tokens == 1000
        assert word_processor.temperature == 1.0  # Updated for GPT-4 compatibility
        assert word_processor.request_count == 0

    @pytest.mark.asyncio
    async def test_process_word_success(self, word_processor, mock_openai_client):
        """Test successful word processing"""
        # Mock OpenAI response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps(
            {
                "lemma": "Haus",
                "part_of_speech": "noun",
                "article": "das",
                "translation": "дом",
                "example": "Das Haus ist schön.",
                "additional_forms": '{"plural": "Häuser"}',
                "confidence": 0.95,
            }
        )

        mock_openai_client.chat.completions.create.return_value = mock_response

        # Test processing
        result = await word_processor.process_word("Haus")

        assert result is not None
        assert isinstance(result, ProcessedWord)
        assert result.word == "Haus"
        assert result.lemma == "Haus"
        assert result.part_of_speech == "noun"
        assert result.article == "das"
        assert result.translation == "дом"
        assert result.example == "Das Haus ist schön."

    @pytest.mark.asyncio
    async def test_process_word_empty_input(self, word_processor):
        """Test processing empty word"""
        result = await word_processor.process_word("")
        assert result is None

        result = await word_processor.process_word(None)
        assert result is None

        result = await word_processor.process_word("   ")
        assert result is None

    @pytest.mark.asyncio
    async def test_process_word_rate_limit(self, word_processor):
        """Test rate limiting"""
        # Set request count to maximum
        word_processor.request_count = word_processor.max_requests_per_day

        result = await word_processor.process_word("test")
        assert result is None

    @pytest.mark.asyncio
    async def test_process_word_api_error(self, word_processor, mock_openai_client):
        """Test API error handling"""
        # Mock API exception
        mock_openai_client.chat.completions.create.side_effect = Exception("API Error")

        result = await word_processor.process_word("test")
        assert result is None  # Now returns None instead of fallback data

    @pytest.mark.asyncio
    async def test_process_word_invalid_json(self, word_processor, mock_openai_client):
        """Test invalid JSON response handling"""
        # Mock response with invalid JSON
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "invalid json content"

        mock_openai_client.chat.completions.create.return_value = mock_response

        result = await word_processor.process_word("test")
        assert result is None  # Now returns None instead of fallback data

    @pytest.mark.asyncio
    async def test_process_word_no_response(self, word_processor, mock_openai_client):
        """Test no response handling"""
        # Mock empty response
        mock_response = MagicMock()
        mock_response.choices = []

        mock_openai_client.chat.completions.create.return_value = mock_response

        result = await word_processor.process_word("test")
        assert result is None

    @pytest.mark.asyncio
    async def test_process_text_success(self, word_processor):
        """Test text processing"""
        # Mock the batch_process_words method to return test data
        word_processor.batch_process_words = AsyncMock(
            return_value=[ProcessedWord(
                word="test",
                lemma="Test",
                part_of_speech="noun",
                article="das",
                translation="тест",
                example="Das ist ein Test.",
                additional_forms=None,
            )]
        )

        text = "Das ist ein Test."
        results = await word_processor.process_text(text, max_words=5)

        assert isinstance(results, list)
        assert len(results) > 0
        assert all(isinstance(word, ProcessedWord) for word in results)

    @pytest.mark.asyncio
    async def test_process_text_empty(self, word_processor):
        """Test processing empty text"""
        result = await word_processor.process_text("")
        assert result == []

        result = await word_processor.process_text(None)
        assert result == []

        result = await word_processor.process_text("   ")
        assert result == []

    @pytest.mark.asyncio
    async def test_process_text_non_german(self, word_processor):
        """Test processing non-German text"""
        with patch.object(
            word_processor.text_parser, "validate_german_text", return_value=False
        ):
            result = await word_processor.process_text("This is English text.")
            assert result == []

    @pytest.mark.asyncio
    async def test_batch_process_words(self, word_processor, mock_openai_client):
        """Test batch word processing"""
        # Mock OpenAI batch response with valid translations
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({
            "haus": {
                "lemma": "Haus",
                "part_of_speech": "noun",
                "article": "das",
                "translation": "дом",
                "example": "Das Haus ist groß.",
                "additional_forms": None,
                "confidence": 0.9
            },
            "auto": {
                "lemma": "Auto",
                "part_of_speech": "noun",
                "article": "das",
                "translation": "машина",
                "example": "Das Auto ist schnell.",
                "additional_forms": None,
                "confidence": 0.9
            },
            "buch": {
                "lemma": "Buch",
                "part_of_speech": "noun",
                "article": "das",
                "translation": "книга",
                "example": "Das Buch ist interessant.",
                "additional_forms": None,
                "confidence": 0.9
            }
        })
        mock_openai_client.chat.completions.create.return_value = mock_response

        words = ["haus", "auto", "buch"]
        results = await word_processor.batch_process_words(words)

        assert len(results) == 3
        assert all(isinstance(word, ProcessedWord) for word in results)
        assert results[0].word == "haus"
        assert results[1].word == "auto"
        assert results[2].word == "buch"

    @pytest.mark.asyncio
    async def test_process_words_batch(self, word_processor, mock_openai_client):
        """Test new batch processing method that processes multiple words in single API call"""
        # Mock OpenAI batch response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({
            "Haus": {
                "lemma": "Haus",
                "part_of_speech": "noun",
                "article": "das",
                "translation": "дом",
                "example": "Das Haus ist schön.",
                "additional_forms": '{"plural": "Häuser"}',
                "confidence": 0.95,
            },
            "gehen": {
                "lemma": "gehen",
                "part_of_speech": "verb",
                "article": None,
                "translation": "идти",
                "example": "Ich gehe zur Schule.",
                "additional_forms": '{"past": "ging"}',
                "confidence": 0.90,
            }
        })
        mock_openai_client.chat.completions.create.return_value = mock_response

        words = ["Haus", "gehen"]
        contexts = {"Haus": "Das Haus ist groß."}
        
        results = await word_processor.process_words_batch(words, contexts)
        
        # Should return 2 processed words
        assert len(results) == 2
        assert all(isinstance(result, ProcessedWord) for result in results)
        
        # Check first word
        haus_word = results[0]
        assert haus_word.word == "Haus"
        assert haus_word.lemma == "Haus"
        assert haus_word.part_of_speech == "noun"
        assert haus_word.article == "das"
        assert haus_word.translation == "дом"
        
        # Check second word
        gehen_word = results[1]
        assert gehen_word.word == "gehen"
        assert gehen_word.lemma == "gehen"
        assert gehen_word.part_of_speech == "verb"
        assert gehen_word.article is None
        assert gehen_word.translation == "идти"
        
        # Verify API was called once (batch processing)
        mock_openai_client.chat.completions.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_words_batch_empty_list(self, word_processor):
        """Test batch processing with empty list"""
        results = await word_processor.process_words_batch([])
        assert results == []

    @pytest.mark.asyncio
    async def test_batch_process_empty_list(self, word_processor):
        """Test batch processing with empty list"""
        result = await word_processor.batch_process_words([])
        assert result == []

    def test_get_request_count(self, word_processor):
        """Test request count getter"""
        assert word_processor.get_request_count() == 0

        word_processor.request_count = 5
        assert word_processor.get_request_count() == 5

    def test_reset_request_count(self, word_processor):
        """Test request count reset"""
        word_processor.request_count = 10
        word_processor.reset_request_count()
        assert word_processor.request_count == 0

    @pytest.mark.asyncio
    async def test_test_connection_success(self, word_processor, mock_openai_client):
        """Test successful connection test"""
        # Mock successful response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Verbindungstest erfolgreich"

        mock_openai_client.chat.completions.create.return_value = mock_response

        result = await word_processor.test_connection()
        assert result is True

    @pytest.mark.asyncio
    async def test_test_connection_failure(self, word_processor, mock_openai_client):
        """Test connection test failure"""
        # Mock API exception
        mock_openai_client.chat.completions.create.side_effect = Exception(
            "Connection failed"
        )

        result = await word_processor.test_connection()
        assert result is False

    def test_create_word_analysis_prompt(self, word_processor):
        """Test prompt creation"""
        # Test without context
        prompt = word_processor._create_word_analysis_prompt("Haus")
        assert "Haus" in prompt
        assert "Analyze the German word" in prompt

        # Test with context
        prompt = word_processor._create_word_analysis_prompt(
            "Haus", "Das Haus ist schön."
        )
        assert "Haus" in prompt
        assert "Das Haus ist schön." in prompt
        assert "Context sentence" in prompt

    def test_parse_openai_response_success(self, word_processor):
        """Test successful response parsing"""
        data = {
            "lemma": "Haus",
            "part_of_speech": "noun",
            "article": "das",
            "translation": "дом",
            "example": "Das Haus ist schön.",
            "additional_forms": '{"plural": "Häuser"}',
            "confidence": 0.95,
        }

        result = word_processor._parse_openai_response("haus", data)

        assert result is not None
        assert isinstance(result, ProcessedWord)
        assert result.word == "haus"
        assert result.lemma == "Haus"
        assert result.article == "das"
        assert result.confidence == 0.95

    def test_parse_openai_response_minimal_data(self, word_processor):
        """Test parsing with minimal data"""
        data = {"lemma": "Test", "translation": "тест"}

        result = word_processor._parse_openai_response("test", data)

        assert result is not None
        assert result.word == "test"
        assert result.lemma == "Test"
        assert result.translation == "тест"
        assert result.part_of_speech == "unknown"  # Default value

    def test_parse_openai_response_invalid_data(self, word_processor):
        """Test parsing with invalid data"""
        # Test with invalid confidence
        data = {"lemma": "Test", "confidence": "invalid"}

        result = word_processor._parse_openai_response("test", data)
        assert result is None  # Now returns None for invalid translation


class TestMockWordProcessor:
    """Test MockWordProcessor class"""

    @pytest.fixture
    def mock_processor(self):
        """Create MockWordProcessor instance"""
        return MockWordProcessor()

    @pytest.mark.asyncio
    async def test_mock_process_word_known(self, mock_processor):
        """Test mock processing of known words"""
        result = await mock_processor.process_word("haus")

        assert result is not None
        assert isinstance(result, ProcessedWord)
        assert result.word == "haus"
        assert result.lemma == "Haus"
        assert result.part_of_speech == "noun"
        assert result.article == "das"
        assert result.translation == "дом"

    @pytest.mark.asyncio
    async def test_mock_process_word_unknown(self, mock_processor):
        """Test mock processing of unknown words"""
        result = await mock_processor.process_word("unknown")

        assert result is None  # Now returns None for unknown words

    @pytest.mark.asyncio
    async def test_mock_process_text(self, mock_processor):
        """Test mock text processing"""
        text = "Das Haus ist schön."
        results = await mock_processor.process_text(text)

        assert isinstance(results, list)
        assert len(results) > 0
        assert all(isinstance(word, ProcessedWord) for word in results)

    @pytest.mark.asyncio
    async def test_mock_test_connection(self, mock_processor):
        """Test mock connection test"""
        result = await mock_processor.test_connection()
        assert result is True

    def test_mock_get_request_count(self, mock_processor):
        """Test mock request count"""
        initial_count = mock_processor.get_request_count()
        assert initial_count == 0

        # Process a known word to increase count
        asyncio.run(mock_processor.process_word("haus"))

        new_count = mock_processor.get_request_count()
        assert new_count == 1


class TestGlobalFunctions:
    """Test global processor functions"""

    def test_get_word_processor_real(self):
        """Test getting real word processor"""
        with patch("src.word_processor.WordProcessor") as mock_class:
            mock_instance = MagicMock()
            mock_class.return_value = mock_instance

            # Reset global instance
            import src.word_processor

            src.word_processor._word_processor = None

            processor = get_word_processor(use_mock=False)
            assert processor == mock_instance
            mock_class.assert_called_once()

    def test_get_word_processor_mock(self):
        """Test getting mock word processor"""
        # Reset global instance
        import src.word_processor

        src.word_processor._word_processor = None

        processor = get_word_processor(use_mock=True)
        assert isinstance(processor, MockWordProcessor)

    def test_get_word_processor_singleton(self):
        """Test singleton behavior"""
        # Reset global instance
        import src.word_processor

        src.word_processor._word_processor = None

        processor1 = get_word_processor(use_mock=True)
        processor2 = get_word_processor(use_mock=True)

        assert processor1 is processor2

    @pytest.mark.asyncio
    async def test_process_german_words_convenience(self):
        """Test convenience function for processing words"""
        with patch("src.word_processor.get_word_processor") as mock_get:
            mock_processor = AsyncMock()
            mock_processor.batch_process_words.return_value = [
                ProcessedWord(
                    word="test",
                    lemma="Test",
                    part_of_speech="noun",
                    article="das",
                    translation="тест",
                    example="Test example",
                    additional_forms=None,
                )
            ]
            mock_get.return_value = mock_processor

            words = ["test"]
            results = await process_german_words(words)

            assert len(results) == 1
            assert isinstance(results[0], ProcessedWord)
            mock_processor.batch_process_words.assert_called_once_with(words, None)

    @pytest.mark.asyncio
    async def test_process_german_text_convenience(self):
        """Test convenience function for processing text"""
        with patch("src.word_processor.get_word_processor") as mock_get:
            mock_processor = AsyncMock()
            mock_processor.process_text.return_value = [
                ProcessedWord(
                    word="test",
                    lemma="Test",
                    part_of_speech="noun",
                    article="das",
                    translation="тест",
                    example="Test example",
                    additional_forms=None,
                )
            ]
            mock_get.return_value = mock_processor

            text = "Das ist ein Test."
            results = await process_german_text(text, max_words=5)

            assert len(results) == 1
            assert isinstance(results[0], ProcessedWord)
            mock_processor.process_text.assert_called_once_with(text, 5)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
