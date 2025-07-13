"""
Tests for article validation in word_processor.py
"""

from src.word_processor import (
    get_correct_article_from_dict,
    guess_article_by_ending,
    is_likely_plural,
    validate_article,
)


class TestArticleValidation:
    """Tests for article validation functions"""

    def test_validate_article_for_non_nouns(self):
        """Test that non-nouns don't get articles"""
        assert validate_article("der", "schön", "adjective") is None
        assert validate_article("die", "gehen", "verb") is None
        assert validate_article("das", "schnell", "adverb") is None
        assert validate_article(None, "und", "conjunction") is None

    def test_validate_article_correct_articles(self):
        """Test that correct articles pass validation"""
        assert validate_article("der", "Mann", "noun") == "der"
        assert validate_article("die", "Frau", "noun") == "die"
        assert validate_article("das", "Haus", "noun") == "das"

    def test_validate_article_none_handling(self):
        """Test handling of None and empty articles"""
        # For known words should return the correct article
        assert validate_article(None, "Haus", "noun") == "das"
        assert validate_article("", "Mann", "noun") == "der"
        assert validate_article("None", "Frau", "noun") == "die"

        # For unknown words should try to guess
        assert validate_article(None, "Bildung", "noun") == "die"  # by ending -ung
        assert validate_article("", "Mädchen", "noun") == "das"  # by ending -chen

    def test_validate_article_plural_detection(self):
        """Test plural number detection"""
        assert validate_article("die", "Eltern", "noun") is None
        assert validate_article("der", "Geschwister", "noun") is None
        assert validate_article("das", "Großeltern", "noun") is None
        assert validate_article("die", "Pommes", "noun") is None

    def test_validate_article_incorrect_articles(self):
        """Test correction of incorrect articles"""
        assert validate_article("wrong", "Haus", "noun") == "das"
        assert validate_article("xyz", "Mann", "noun") == "der"
        assert validate_article("123", "Frau", "noun") == "die"

    def test_get_correct_article_from_dict(self):
        """Test getting articles from dictionary"""
        # Masculine gender
        assert get_correct_article_from_dict("Mann") == "der"
        assert get_correct_article_from_dict("Vater") == "der"
        assert get_correct_article_from_dict("Teppich") == "der"

        # Feminine gender
        assert get_correct_article_from_dict("Frau") == "die"
        assert get_correct_article_from_dict("Mutter") == "die"
        assert get_correct_article_from_dict("Schule") == "die"

        # Neuter gender
        assert get_correct_article_from_dict("Kind") == "das"
        assert get_correct_article_from_dict("Haus") == "das"
        assert get_correct_article_from_dict("Auto") == "das"

        # Plural nouns
        assert get_correct_article_from_dict("Eltern") is None
        assert get_correct_article_from_dict("Geschwister") is None
        assert get_correct_article_from_dict("Großeltern") is None
        assert get_correct_article_from_dict("Pommes") is None

        # Unknown words
        assert get_correct_article_from_dict("UnknownWord") is None

    def test_guess_article_by_ending(self):
        """Test guessing articles by word endings"""
        # das - endings
        assert guess_article_by_ending("Mädchen") == "das"  # -chen
        assert guess_article_by_ending("Büchlein") == "das"  # -lein
        assert guess_article_by_ending("Zentrum") == "das"  # -um
        assert guess_article_by_ending("Argument") == "das"  # -ment

        # die - endings
        assert guess_article_by_ending("Bildung") == "die"  # -ung
        assert guess_article_by_ending("Freiheit") == "die"  # -heit
        assert guess_article_by_ending("Möglichkeit") == "die"  # -keit
        assert guess_article_by_ending("Freundschaft") == "die"  # -schaft
        assert guess_article_by_ending("Information") == "die"  # -tion
        assert guess_article_by_ending("Diskussion") == "die"  # -sion
        assert guess_article_by_ending("Universität") == "die"  # -tät

        # der - endings
        assert guess_article_by_ending("Lehrer") == "der"  # -er
        assert guess_article_by_ending("Garten") == "der"  # -en
        assert guess_article_by_ending("Apfel") == "der"  # -el
        assert guess_article_by_ending("Teppich") == "der"  # -ich
        assert guess_article_by_ending("König") == "der"  # -ig
        assert guess_article_by_ending("Schmetterling") == "der"  # -ling

        # Unknown endings
        assert guess_article_by_ending("Test") is None
        assert guess_article_by_ending("xyz") is None

    def test_is_likely_plural(self):
        """Test detection of plural forms"""
        # Exact matches
        assert is_likely_plural("eltern") is True
        assert is_likely_plural("Eltern") is True
        assert is_likely_plural("ELTERN") is True
        assert is_likely_plural("geschwister") is True
        assert is_likely_plural("Geschwister") is True
        assert is_likely_plural("großeltern") is True
        assert is_likely_plural("Großeltern") is True
        assert is_likely_plural("pommes") is True
        assert is_likely_plural("Pommes") is True
        assert is_likely_plural("leute") is True
        assert is_likely_plural("Leute") is True
        assert is_likely_plural("kinder") is True
        assert is_likely_plural("Kinder") is True

        # Not plural
        assert is_likely_plural("Mann") is False
        assert is_likely_plural("Frau") is False
        assert is_likely_plural("Kind") is False
        assert is_likely_plural("Haus") is False
        assert is_likely_plural("Auto") is False

        # Edge cases
        assert is_likely_plural("") is False
        assert is_likely_plural("a") is False
        assert is_likely_plural("ab") is False
        assert is_likely_plural("abc") is False

    def test_validation_integration(self):
        """Test integration of all validation functions"""
        # Case 1: Correct article for known word
        assert validate_article("das", "Haus", "noun") == "das"

        # Case 2: Incorrect article for known word - should correct
        assert validate_article("der", "Haus", "noun") == "das"

        # Case 3: Missing article for known word - should add
        assert validate_article(None, "Haus", "noun") == "das"

        # Case 4: Plural with article - should remove
        assert validate_article("die", "Eltern", "noun") is None

        # Case 5: Unknown word with correct article
        assert validate_article("der", "TestWord", "noun") == "der"

        # Case 6: Unknown word with incorrect article - attempt to guess
        result = validate_article("wrong", "Bildung", "noun")
        assert result == "die"  # should guess by ending -ung

        # Case 7: Unknown word without article - attempt to guess
        result = validate_article(None, "Mädchen", "noun")
        assert result == "das"  # should guess by ending -chen

    def test_edge_cases(self):
        """Test edge cases"""
        # Empty strings - should return None
        assert validate_article("", "", "noun") is None
        assert validate_article("der", "", "noun") is None

        # Whitespace - should be corrected for known words
        assert validate_article("   ", "Haus", "noun") == "das"
        assert validate_article("der", "   ", "noun") is None

        # Case - should be corrected for known words
        assert (
            validate_article("DER", "Mann", "noun") == "der"
        )  # should correct wrong case
        assert (
            validate_article("der", "mann", "noun") == "der"
        )  # check works with lowercase

        # Unknown part of speech
        assert validate_article("der", "Test", "unknown") is None
        assert validate_article("der", "Test", "") is None
        assert validate_article("der", "Test", None) is None

    def test_logging_behavior(self):
        """Test that functions log corrections"""
        # This test checks that functions are called without errors
        # Real log checking requires mocking the logger

        # Correcting incorrect article
        result = validate_article("wrong", "Haus", "noun")
        assert result == "das"

        # Guessing article
        result = validate_article(None, "Bildung", "noun")
        assert result == "die"

        # Removing article for plural
        result = validate_article("die", "Eltern", "noun")
        assert result is None
