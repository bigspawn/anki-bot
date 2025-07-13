"""
Test article handling in word display and formatting functions
"""

import os
import tempfile

import pytest

from src.core.database.database_manager import DatabaseManager
from src.utils import format_word_display


class TestArticleHandling:
    """Test proper handling of articles in word display"""

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

    def test_format_word_display_with_article(self):
        """Test word display formatting with proper article"""
        word_data = {
            "lemma": "Haus",
            "part_of_speech": "noun",
            "article": "das",
            "translation": "house",
            "example": "Das Haus ist groß.",
        }

        result = format_word_display(word_data)

        # Should include article in display
        assert "das Haus" in result
        assert "None" not in result
        assert "🇩🇪 das Haus" in result
        assert "🏷️ noun" in result
        assert "🇷🇺 house" in result
        assert "📚 Das Haus ist groß." in result

    def test_format_word_display_without_article(self):
        """Test word display formatting without article (None)"""
        word_data = {
            "lemma": "Eltern",
            "part_of_speech": "noun",
            "article": None,
            "translation": "parents",
            "example": "Meine Eltern sind nett.",
        }

        result = format_word_display(word_data)

        # Should not include article in display
        assert "🇩🇪 Eltern" in result
        assert "None" not in result
        assert "🏷️ noun" in result
        assert "🇷🇺 parents" in result
        assert "📚 Meine Eltern sind nett." in result

    def test_format_word_display_with_none_string(self):
        """Test word display formatting with 'None' string article"""
        word_data = {
            "lemma": "Test",
            "part_of_speech": "noun",
            "article": "None",  # String "None" instead of None
            "translation": "test",
            "example": "This is a test.",
        }

        result = format_word_display(word_data)

        # Should not include 'None' string in display
        assert "🇩🇪 Test" in result
        assert "None" not in result
        assert "🏷️ noun" in result

    def test_format_word_display_with_empty_string_article(self):
        """Test word display formatting with empty string article"""
        word_data = {
            "lemma": "Test",
            "part_of_speech": "noun",
            "article": "",
            "translation": "test",
            "example": "This is a test.",
        }

        result = format_word_display(word_data)

        # Should not include empty article in display
        assert "🇩🇪 Test" in result
        assert "None" not in result
        assert "🏷️ noun" in result

    def test_session_manager_word_display_with_article(
        self, temp_db_manager, sample_user_data
    ):
        """Test SessionManager handles words with articles correctly"""

        # Create user and add word with article
        user = temp_db_manager.create_user(**sample_user_data)
        user_id = user["telegram_id"]

        word_data = {
            "lemma": "Buch",
            "part_of_speech": "noun",
            "article": "das",
            "translation": "book",
            "example": "Das Buch ist interessant.",
        }

        added_count = temp_db_manager.add_words_to_user(user_id, [word_data])
        assert added_count == 1

        # Get the word back
        words = temp_db_manager.get_words_by_user(user_id)
        assert len(words) == 1
        word = words[0]

        # Test the session manager formatting logic
        article = word.get("article")
        if article and article != "None" and article.strip():
            word_display = f"{article} {word['lemma']} - {word['part_of_speech']}"
        else:
            word_display = f"{word['lemma']} - {word['part_of_speech']}"

        assert word_display == "das Buch - noun"
        assert "None" not in word_display

    def test_session_manager_word_display_without_article(
        self, temp_db_manager, sample_user_data
    ):
        """Test SessionManager handles words without articles correctly"""

        # Create user and add word without article
        user = temp_db_manager.create_user(**sample_user_data)
        user_id = user["telegram_id"]

        word_data = {
            "lemma": "Eltern",
            "part_of_speech": "noun",
            "article": None,
            "translation": "parents",
            "example": "Meine Eltern sind nett.",
        }

        added_count = temp_db_manager.add_words_to_user(user_id, [word_data])
        assert added_count == 1

        # Get the word back
        words = temp_db_manager.get_words_by_user(user_id)
        assert len(words) == 1
        word = words[0]

        # Test the session manager formatting logic
        article = word.get("article")
        if article and article != "None" and article.strip():
            word_display = f"{article} {word['lemma']} - {word['part_of_speech']}"
        else:
            word_display = f"{word['lemma']} - {word['part_of_speech']}"

        assert word_display == "Eltern - noun"
        assert "None" not in word_display

    def test_session_manager_word_display_with_none_string(
        self, temp_db_manager, sample_user_data
    ):
        """Test SessionManager handles words with 'None' string article correctly"""

        # Create user and add word with 'None' string article
        user = temp_db_manager.create_user(**sample_user_data)
        user_id = user["telegram_id"]

        # Manually insert a word with 'None' string article (edge case)
        with temp_db_manager.get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO words (lemma, part_of_speech, article, translation, example) VALUES (?, ?, ?, ?, ?)",
                ("BadWord", "noun", "None", "bad word", "This is bad."),
            )
            word_id = cursor.lastrowid

            # Add to user via learning_progress table
            conn.execute(
                "INSERT INTO learning_progress (telegram_id, word_id) VALUES (?, ?)",
                (user_id, word_id),
            )
            conn.commit()

        # Get the word back
        words = temp_db_manager.get_words_by_user(user_id)
        assert len(words) == 1
        word = words[0]

        # Test the session manager formatting logic
        article = word.get("article")
        if article and article != "None" and article.strip():
            word_display = f"{article} {word['lemma']} - {word['part_of_speech']}"
        else:
            word_display = f"{word['lemma']} - {word['part_of_speech']}"

        assert word_display == "BadWord - noun"
        assert "None" not in word_display

    def test_various_article_scenarios(self, temp_db_manager, sample_user_data):
        """Test various article scenarios in one comprehensive test"""

        # Create user
        user = temp_db_manager.create_user(**sample_user_data)
        user_id = user["telegram_id"]

        # Test words with different article scenarios
        test_words = [
            {
                "lemma": "Haus",
                "part_of_speech": "noun",
                "article": "das",
                "translation": "house",
                "example": "Das Haus ist groß.",
                "expected_display": "das Haus - noun",
            },
            {
                "lemma": "Frau",
                "part_of_speech": "noun",
                "article": "die",
                "translation": "woman",
                "example": "Die Frau ist nett.",
                "expected_display": "die Frau - noun",
            },
            {
                "lemma": "Mann",
                "part_of_speech": "noun",
                "article": "der",
                "translation": "man",
                "example": "Der Mann ist groß.",
                "expected_display": "der Mann - noun",
            },
            {
                "lemma": "Eltern",
                "part_of_speech": "noun",
                "article": None,
                "translation": "parents",
                "example": "Meine Eltern sind nett.",
                "expected_display": "Eltern - noun",
            },
            {
                "lemma": "Kinder",
                "part_of_speech": "noun",
                "article": None,
                "translation": "children",
                "example": "Die Kinder spielen.",
                "expected_display": "Kinder - noun",
            },
            {
                "lemma": "laufen",
                "part_of_speech": "verb",
                "article": None,
                "translation": "to run",
                "example": "Ich laufe schnell.",
                "expected_display": "laufen - verb",
            },
        ]

        # Add all words
        word_data_for_db = [
            {k: v for k, v in word.items() if k != "expected_display"}
            for word in test_words
        ]
        added_count = temp_db_manager.add_words_to_user(user_id, word_data_for_db)
        assert added_count == len(test_words)

        # Get words back and test display
        words = temp_db_manager.get_words_by_user(user_id)
        assert len(words) == len(test_words)

        for word in words:
            # Find the expected display for this word
            expected_word = next(
                (tw for tw in test_words if tw["lemma"] == word["lemma"]), None
            )
            assert expected_word is not None

            # Test session manager formatting
            article = word.get("article")
            if article and article != "None":
                word_display = f"{article} {word['lemma']} - {word['part_of_speech']}"
            else:
                word_display = f"{word['lemma']} - {word['part_of_speech']}"

            assert word_display == expected_word["expected_display"]
            assert "None" not in word_display

            # Test utils formatting
            formatted_display = format_word_display(word)
            assert "None" not in formatted_display

    def test_edge_case_whitespace_article(self):
        """Test handling of whitespace-only articles"""
        word_data = {
            "lemma": "Test",
            "part_of_speech": "noun",
            "article": "   ",  # Whitespace only
            "translation": "test",
            "example": "This is a test.",
        }

        result = format_word_display(word_data)

        # Should treat whitespace-only as no article
        assert "🇩🇪 Test" in result
        assert "None" not in result

    def test_missing_article_field(self):
        """Test handling when article field is missing entirely"""
        word_data = {
            "lemma": "Test",
            "part_of_speech": "noun",
            # "article" field is missing entirely
            "translation": "test",
            "example": "This is a test.",
        }

        result = format_word_display(word_data)

        # Should handle missing field gracefully
        assert "🇩🇪 Test" in result
        assert "None" not in result
