"""
Unit tests for utility functions
"""

import pytest
import json
from datetime import date, timedelta
from unittest.mock import patch, MagicMock

from src.utils import (
    format_word_display,
    format_study_card,
    format_progress_stats,
    validate_german_text,
    clean_text,
    extract_json_safely,
    format_json_safely,
    escape_markdown,
    validate_rating,
    get_rating_emoji,
    get_rating_text,
    chunk_list,
    safe_int,
    safe_float,
    calculate_success_rate,
    format_duration,
    get_difficulty_level,
    create_inline_keyboard_data,
    parse_inline_keyboard_data,
    Timer,
    format_date_relative,
    truncate_text,
    parse_date_safely,
)


class TestTextFormatting:
    """Test text formatting functions"""

    def test_format_word_display(self):
        """Test word display formatting"""
        word_data = {
            "word": "Haus",
            "lemma": "Haus",
            "article": "das",
            "part_of_speech": "noun",
            "translation": "дом",
            "example": "Das Haus ist schön.",
        }

        result = format_word_display(word_data)
        expected_parts = ["🇩🇪 das Haus", "🏷️ noun", "🇷🇺 дом", "📚 Das Haus ist schön."]

        for part in expected_parts:
            assert part in result

    def test_format_word_display_no_article(self):
        """Test word display without article"""
        word_data = {
            "word": "gehen",
            "lemma": "gehen",
            "part_of_speech": "verb",
            "translation": "идти",
            "example": "Ich gehe zur Schule.",
        }

        result = format_word_display(word_data)
        assert "🇩🇪 gehen" in result
        assert "das" not in result and "die" not in result and "der" not in result

    def test_format_study_card(self):
        """Test study card formatting"""
        word_data = {
            "lemma": "Buch",
            "article": "das",
            "pos": "noun",
            "translation": "книга",
            "example": "Ich lese ein Buch.",
        }

        # Question side - should ask about article for nouns
        word_data["part_of_speech"] = "noun"  # Update key name
        question = format_study_card(word_data, current_index=1, total_words=10)
        assert "1/10. Какой артикль у Buch?" == question
        assert "книга" not in question

        # Test verb question format
        verb_data = {
            "lemma": "sprechen",
            "part_of_speech": "verb",
            "translation": "говорить",
            "example": "Ich spreche Deutsch.",
        }
        verb_question = format_study_card(verb_data, current_index=2, total_words=10)
        assert "2/10. Как переводится sprechen?" == verb_question

    def test_format_progress_stats(self):
        """Test progress statistics formatting"""
        stats = {
            "total_words": 150,
            "due_words": 25,
            "new_words": 10,
            "avg_success_rate": 0.85,
        }

        result = format_progress_stats(stats)
        assert "150" in result
        assert "25" in result
        assert "10" in result
        assert "85.0%" in result


class TestTextValidation:
    """Test text validation functions"""

    def test_validate_german_text(self):
        """Test German text validation"""
        # Valid German texts
        assert validate_german_text("Das ist ein schönes Haus.")
        assert validate_german_text("Ich gehe zur Schule.")
        assert validate_german_text("Die Mädchen spielen im Garten.")

        # Invalid texts
        assert not validate_german_text("")
        assert not validate_german_text("   ")
        assert not validate_german_text("Hello world")
        assert not validate_german_text("12345")

    def test_clean_text(self):
        """Test text cleaning"""
        assert clean_text("  Hello   world  ") == "Hello world"
        assert clean_text("Hallo! Wie geht's?") == "Hallo! Wie geht's?"
        assert clean_text("Text@#$%mit&*()Sonderzeichen") == "TextmitSonderzeichen"
        assert clean_text("") == ""


class TestJSONHandling:
    """Test JSON handling functions"""

    def test_extract_json_safely(self):
        """Test safe JSON extraction"""
        # Valid JSON
        valid_json = '{"key": "value", "number": 42}'
        result = extract_json_safely(valid_json)
        assert result == {"key": "value", "number": 42}

        # Invalid JSON
        assert extract_json_safely("invalid json") == {}
        assert extract_json_safely("") == {}
        assert extract_json_safely(None) == {}

    def test_format_json_safely(self):
        """Test safe JSON formatting"""
        data = {"key": "value", "number": 42}
        result = format_json_safely(data)
        assert result == '{"key":"value","number":42}'

        # Invalid data
        class UnserializableClass:
            pass

        result = format_json_safely(UnserializableClass())
        assert result == "{}"


class TestMarkdown:
    """Test markdown handling"""

    def test_escape_markdown(self):
        """Test markdown escaping"""
        text = "Text with *bold* and _italic_ and [link](url)"
        result = escape_markdown(text)
        assert "\\*" in result
        assert "\\_" in result
        assert "\\[" in result
        assert "\\]" in result
        assert "\\(" in result
        assert "\\)" in result


class TestRatingFunctions:
    """Test rating-related functions"""

    def test_validate_rating(self):
        """Test rating validation"""
        assert validate_rating(1) == 1
        assert validate_rating(2) == 2
        assert validate_rating(3) == 3
        assert validate_rating(4) == 4
        assert validate_rating("3") == 3

        # Invalid ratings
        assert validate_rating(0) is None
        assert validate_rating(5) is None
        assert validate_rating("invalid") is None
        assert validate_rating(None) is None

    def test_get_rating_emoji(self):
        """Test rating emoji mapping"""
        assert get_rating_emoji(1) == "❌"
        assert get_rating_emoji(2) == "➖"
        assert get_rating_emoji(3) == "➕"
        assert get_rating_emoji(4) == "✅"
        assert get_rating_emoji(5) == "❓"

    def test_get_rating_text(self):
        """Test rating text mapping"""
        assert get_rating_text(1) == ""
        assert get_rating_text(2) == ""
        assert get_rating_text(3) == ""
        assert get_rating_text(4) == ""
        assert get_rating_text(5) == ""


class TestUtilityFunctions:
    """Test utility functions"""

    def test_chunk_list(self):
        """Test list chunking"""
        lst = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        chunks = chunk_list(lst, 3)
        expected = [[1, 2, 3], [4, 5, 6], [7, 8, 9], [10]]
        assert chunks == expected

        # Empty list
        assert chunk_list([], 3) == []

        # Chunk size larger than list
        assert chunk_list([1, 2], 5) == [[1, 2]]

    def test_safe_int(self):
        """Test safe integer conversion"""
        assert safe_int("123") == 123
        assert safe_int(123.7) == 123
        assert safe_int("invalid") == 0
        assert safe_int(None) == 0
        assert safe_int("invalid", default=42) == 42

    def test_safe_float(self):
        """Test safe float conversion"""
        assert safe_float("123.45") == 123.45
        assert safe_float(123) == 123.0
        assert safe_float("invalid") == 0.0
        assert safe_float(None) == 0.0
        assert safe_float("invalid", default=42.5) == 42.5

    def test_calculate_success_rate(self):
        """Test success rate calculation"""
        assert calculate_success_rate(8, 10) == 80.0
        assert calculate_success_rate(0, 10) == 0.0
        assert calculate_success_rate(10, 10) == 100.0
        assert calculate_success_rate(5, 0) == 0.0  # Division by zero

    def test_format_duration(self):
        """Test duration formatting"""
        assert format_duration(30) == "30с"
        assert format_duration(90) == "1м"
        assert format_duration(3600) == "1ч 0м"
        assert format_duration(3750) == "1ч 2м"

    def test_get_difficulty_level(self):
        """Test difficulty level assessment"""
        assert get_difficulty_level(3.0) == "Легкое"
        assert get_difficulty_level(2.3) == "Среднее"
        assert get_difficulty_level(1.8) == "Трудное"
        assert get_difficulty_level(1.2) == "Очень трудное"

    def test_truncate_text(self):
        """Test text truncation"""
        text = "This is a very long text that should be truncated"
        result = truncate_text(text, max_length=20)
        assert len(result) <= 20
        assert result.endswith("...")

        # Short text should not be truncated
        short_text = "Short"
        assert truncate_text(short_text, max_length=20) == short_text


class TestDateHandling:
    """Test date handling functions"""

    def test_format_date_relative(self):
        """Test relative date formatting"""
        today = date.today()

        assert format_date_relative(today) == "сегодня"
        assert format_date_relative(today + timedelta(days=1)) == "завтра"
        assert format_date_relative(today - timedelta(days=1)) == "вчера"
        assert format_date_relative(today + timedelta(days=5)) == "через 5 дн."
        assert format_date_relative(today - timedelta(days=3)) == "3 дн. назад"

    def test_parse_date_safely(self):
        """Test safe date parsing"""
        # Valid dates
        assert parse_date_safely("2023-12-25") == date(2023, 12, 25)
        assert parse_date_safely("25.12.2023") == date(2023, 12, 25)
        assert parse_date_safely("25/12/2023") == date(2023, 12, 25)

        # Invalid dates
        assert parse_date_safely("invalid") is None
        assert parse_date_safely("") is None
        assert parse_date_safely(None) is None


class TestInlineKeyboard:
    """Test inline keyboard functions"""

    def test_create_inline_keyboard_data(self):
        """Test inline keyboard data creation"""
        data = create_inline_keyboard_data("rate_word", word_id=123, rating=3)
        
        # Test that data is compact and under 64 bytes
        assert len(data) <= 64, f"Data too long: {len(data)} bytes"
        
        # Test that it can be parsed back correctly
        parsed = parse_inline_keyboard_data(data)
        assert parsed["action"] == "rate_word"
        assert parsed["word_id"] == 123
        assert parsed["rating"] == 3

    def test_parse_inline_keyboard_data(self):
        """Test inline keyboard data parsing"""
        data = '{"action":"rate_word","word_id":123,"rating":3}'
        result = parse_inline_keyboard_data(data)

        assert result["action"] == "rate_word"
        assert result["word_id"] == 123
        assert result["rating"] == 3

        # Invalid data
        assert parse_inline_keyboard_data("invalid") == {}


class TestTimer:
    """Test Timer class"""

    def test_timer_basic_functionality(self):
        """Test basic timer functionality"""
        timer = Timer()

        # Timer not started
        assert timer.elapsed() is None
        assert timer.elapsed_ms() is None

        # Start timer
        timer.start()
        assert timer.start_time is not None

        # Elapsed time should be small but positive
        import time

        time.sleep(0.01)  # Small delay

        elapsed = timer.elapsed()
        assert elapsed is not None
        assert elapsed > 0
        assert elapsed < 1  # Should be less than 1 second

        elapsed_ms = timer.elapsed_ms()
        assert elapsed_ms is not None
        assert elapsed_ms > 0

    def test_timer_stop(self):
        """Test timer stop functionality"""
        timer = Timer()
        timer.start()

        import time

        time.sleep(0.01)

        timer.stop()
        first_elapsed = timer.elapsed()

        time.sleep(0.01)

        # Elapsed time should not change after stop
        second_elapsed = timer.elapsed()
        assert first_elapsed == second_elapsed


class TestDecorators:
    """Test decorator functions"""

    @pytest.mark.asyncio
    async def test_retry_decorator_async_success(self):
        """Test retry decorator with async function success"""
        from src.utils import retry_on_exception

        call_count = 0

        @retry_on_exception(max_retries=3, delay=0.01)
        async def async_function():
            nonlocal call_count
            call_count += 1
            return "success"

        result = await async_function()
        assert result == "success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retry_decorator_async_failure(self):
        """Test retry decorator with async function failure"""
        from src.utils import retry_on_exception

        call_count = 0

        @retry_on_exception(max_retries=3, delay=0.01)
        async def failing_async_function():
            nonlocal call_count
            call_count += 1
            raise ValueError("Test error")

        with pytest.raises(ValueError):
            await failing_async_function()

        assert call_count == 3  # Should retry 3 times

    def test_retry_decorator_sync(self):
        """Test retry decorator with sync function"""
        from src.utils import retry_on_exception

        call_count = 0

        @retry_on_exception(max_retries=2, delay=0.01)
        def sync_function():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("Fail on first call")
            return "success"

        result = sync_function()
        assert result == "success"
        assert call_count == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
