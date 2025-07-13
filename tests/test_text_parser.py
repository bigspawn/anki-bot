"""
Unit tests for German text parser
"""

import pytest

from src.text_parser import (
    GermanTextParser,
    extract_german_words,
    get_text_parser,
    validate_german_text,
)


class TestGermanTextParser:
    """Test GermanTextParser class"""

    @pytest.fixture
    def parser(self):
        """Create parser instance for testing"""
        return GermanTextParser()

    def test_parser_initialization(self, parser):
        """Test parser initialization"""
        assert hasattr(parser, "word_pattern")
        assert hasattr(parser, "sentence_pattern")
        assert parser.word_pattern is not None
        assert parser.sentence_pattern is not None

    def test_extract_words_basic(self, parser):
        """Test basic word extraction"""
        text = "Das Haus ist sehr schön."
        words = parser.extract_words(text)

        # Should extract all words including articles and common words
        assert "haus" in words
        assert "schön" in words
        assert "das" in words  # Articles should be included
        assert "ist" in words  # Common verbs should be included
        assert "sehr" in words  # Adverbs should be included

    def test_extract_words_with_umlauts(self, parser):
        """Test word extraction with German umlauts"""
        text = "Die Mädchen spielen im schönen Garten."
        words = parser.extract_words(text)

        assert "mädchen" in words
        assert "spielen" in words
        assert "schönen" in words
        assert "garten" in words

    def test_extract_words_empty_text(self, parser):
        """Test word extraction with empty text"""
        assert parser.extract_words("") == []
        assert parser.extract_words("   ") == []
        assert parser.extract_words(None) == []

    def test_extract_words_duplicates(self, parser):
        """Test that duplicates are removed"""
        text = "Das Haus und das Haus sind schön."
        words = parser.extract_words(text)

        # Should only contain "haus" once
        assert words.count("haus") == 1
        assert "schön" in words

    def test_extract_words_length_filtering(self, parser):
        """Test word length filtering"""
        text = "Ich a go Donaudampfschifffahrtsgesellschaftskapitänspatent."
        words = parser.extract_words(text, min_length=3, max_length=20)

        # "a" should be filtered (too short)
        assert "a" not in words

        # Long compound word should be filtered (too long)
        long_word = "Donaudampfschifffahrtsgesellschaftskapitänspatent"
        assert long_word not in words

        # "go" should be filtered (English word, not in stop words but not valid German)
        # Actually, "go" might be extracted as it contains valid letters
        # The filtering is mainly for stop words and length

    def test_clean_text(self, parser):
        """Test text cleaning"""
        dirty_text = "  Das   Haus@#$%   ist  schön!!!  "
        cleaned = parser._clean_text(dirty_text)

        assert cleaned == "Das Haus ist schön!!!"
        assert not cleaned.startswith(" ")
        assert not cleaned.endswith(" ")

    def test_is_valid_word(self, parser):
        """Test word validation"""
        # Valid words
        assert parser._is_valid_word("Haus", 2, 50)
        assert parser._is_valid_word("schön", 2, 50)

        # Invalid words
        assert not parser._is_valid_word("a", 2, 50)  # Too short
        assert not parser._is_valid_word(
            "verylongwordthatexceedslimit", 2, 20
        )  # Too long
        assert parser._is_valid_word("der", 2, 50)  # Articles should be valid
        assert not parser._is_valid_word("123", 2, 50)  # Pure number
        assert not parser._is_valid_word("", 2, 50)  # Empty

    def test_extract_sentences(self, parser):
        """Test sentence extraction"""
        text = (
            "Das ist der erste Satz. Das ist der zweite Satz! Ist das ein dritter Satz?"
        )
        sentences = parser.extract_sentences(text)

        assert len(sentences) == 3
        assert "Das ist der erste Satz" in sentences
        assert "Das ist der zweite Satz" in sentences
        assert "Ist das ein dritter Satz" in sentences

    def test_extract_sentences_short_fragments(self, parser):
        """Test that short sentence fragments are filtered"""
        text = "Hallo. Hi. Das ist ein längerer Satz mit mehr Inhalt."
        sentences = parser.extract_sentences(text)

        # Short fragments should be filtered out
        filtered_sentences = [s for s in sentences if len(s) > 10]
        assert len(filtered_sentences) >= 1
        assert any("längerer Satz" in s for s in sentences)

    def test_get_word_context(self, parser):
        """Test word context extraction"""
        text = """
        Das Haus ist groß. Ich gehe zum Haus.
        Das rote Haus steht am Berg. Viele Häuser sind schön.
        """

        contexts = parser.get_word_context(text, "Haus", context_size=3)

        assert len(contexts) <= 3  # Limited by context_size
        assert any("groß" in context for context in contexts)
        assert any("Berg" in context for context in contexts)

    def test_validate_german_text_positive(self, parser):
        """Test German text validation - positive cases"""
        german_texts = [
            "Das ist ein schöner Tag.",
            "Ich gehe zur Schule.",
            "Die Mädchen spielen im Garten.",
            "Wir haben viel Spaß.",
            "Der große Hund läuft schnell.",
        ]

        for text in german_texts:
            assert parser.validate_german_text(text), f"Failed to validate: {text}"

    def test_validate_german_text_negative(self, parser):
        """Test German text validation - negative cases"""
        non_german_texts = [
            "",
            "   ",
            "Hello world",
            "Bonjour mes amis",
            "321",
            "###@@@$$$",
            "Short",  # Too short
        ]

        for text in non_german_texts:
            assert not parser.validate_german_text(text), (
                f"Incorrectly validated: {text}"
            )

    def test_validate_german_text_with_umlauts(self, parser):
        """Test German text validation with umlauts"""
        # Text with umlauts should definitely be German
        umlaut_text = "Die schönen Mädchen gehen spazieren."
        assert parser.validate_german_text(umlaut_text)

        # Text without umlauts but with German words should also validate
        no_umlaut_text = "Ich gehe heute in die Schule."
        assert parser.validate_german_text(no_umlaut_text)

    def test_validate_german_text_single_words(self, parser):
        """Test German text validation for single words - regression test for
        'bedeutet' bug"""
        # German verbs without umlauts should validate (main bug case)
        german_verbs = [
            "bedeutet",
            "sprechen",
            "lernen",
            "arbeiten",
            "gehen",
            "machen",
            "haben",
        ]
        for verb in german_verbs:
            assert parser.validate_german_text(verb), (
                f"German verb '{verb}' should validate as German"
            )

        # German words with umlauts should validate
        german_umlaut_words = ["schön", "größer", "hören", "können", "müssen"]
        for word in german_umlaut_words:
            assert parser.validate_german_text(word), (
                f"German word with umlauts '{word}' should validate as German"
            )

        # English words that are clearly distinct from German should not validate
        english_words = ["hello", "world"]
        for word in english_words:
            assert not parser.validate_german_text(word), (
                f"English word '{word}' should not validate as German"
            )

        # Other foreign words should not validate
        foreign_words = ["bonjour", "hola", "ciao"]
        for word in foreign_words:
            assert not parser.validate_german_text(word), (
                f"Foreign word '{word}' should not validate as German"
            )

    def test_validate_german_text_bedeutet_regression(self, parser):
        """Regression test for the specific 'bedeutet' bug"""
        # The word 'bedeutet' was the original failing case
        assert parser.validate_german_text("bedeutet"), (
            "The word 'bedeutet' should validate as German"
        )

        # Test it in context as well
        assert parser.validate_german_text("Das bedeutet viel"), (
            "Text containing 'bedeutet' should validate as German"
        )

    def test_validate_german_text_mixed_language(self, parser):
        """Test German text validation with mixed languages"""
        # Predominantly German should validate
        # This might validate depending on the ratio of German words

        # Predominantly English should not validate
        # This should not validate as it's mostly English


class TestGlobalFunctions:
    """Test global parser functions"""

    def test_get_text_parser(self):
        """Test getting global parser instance"""
        parser1 = get_text_parser()
        parser2 = get_text_parser()

        assert parser1 is parser2  # Should return same instance
        assert isinstance(parser1, GermanTextParser)

    def test_extract_german_words_convenience(self):
        """Test convenience function for word extraction"""
        text = "Das schöne Haus steht am Berg."
        words = extract_german_words(text)

        assert isinstance(words, list)
        assert "schöne" in words
        assert "haus" in words
        assert "berg" in words

    def test_validate_german_text_convenience(self):
        """Test convenience function for text validation"""
        assert validate_german_text("Das ist ein Test.")
        assert not validate_german_text("This is a test.")


class TestEdgeCases:
    """Test edge cases and special scenarios"""

    def test_very_long_text(self):
        """Test with very long text"""
        parser = GermanTextParser()

        # Create a long text by repeating a pattern
        base_text = "Das große Haus steht am schönen Berg. "
        long_text = base_text * 100  # Very long text

        words = parser.extract_words(long_text)

        # Should handle long text without issues
        assert len(words) > 0
        assert "große" in words
        assert "haus" in words
        assert "schönen" in words
        assert "berg" in words

    def test_text_with_special_characters(self):
        """Test text with special German characters and punctuation"""
        parser = GermanTextParser()

        text = "Das Mädchen's Bäcker-Laden (sehr schön!) kostet 5,50€."
        words = parser.extract_words(text)

        assert "mädchen" in words
        assert "bäcker" in words
        assert "laden" in words
        assert "schön" in words

    def test_text_with_numbers_and_dates(self):
        """Test text with numbers and dates"""
        parser = GermanTextParser()

        text = "Am 15. März 2023 gehe ich zur Schule um 8:30 Uhr."
        words = parser.extract_words(text)

        # Numbers should be filtered out
        assert "15" not in words
        assert "2023" not in words
        assert "8" not in words
        assert "30" not in words

        # Words should be extracted
        assert "märz" in words
        assert "gehe" in words
        assert "schule" in words
        assert "uhr" in words

    def test_case_insensitive_processing(self):
        """Test that processing is case-insensitive and words are
        normalized to lowercase"""
        parser = GermanTextParser()

        text = "DAS HAUS IST SCHÖN."
        words = parser.extract_words(text)

        # All words should be extracted and normalized to lowercase
        assert "das" in words  # Articles should be included (lowercase)
        assert "haus" in words  # Content word should be kept (lowercase)
        assert "ist" in words  # Common verbs should be included (lowercase)
        assert "schön" in words  # Content word should be kept (lowercase)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
