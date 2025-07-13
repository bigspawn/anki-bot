#!/usr/bin/env python3
"""
Tests for foreign word filtering functionality
"""

import pytest

from src.text_parser import get_text_parser


class TestForeignWordFiltering:
    """Test foreign word filtering functionality"""

    @pytest.fixture
    def parser(self):
        """Get text parser instance"""
        return get_text_parser()

    def test_english_words_are_filtered(self, parser):
        """Test that common English words are filtered out"""
        text = "Das ist a beautiful house with good weather"
        words = parser.extract_words(text)

        # Should keep German words
        german_words = ["das", "ist"]
        for word in german_words:
            assert word in [w.lower() for w in words], (
                f"German word '{word}' should be kept"
            )

        # Should filter English words
        english_words = ["beautiful", "house", "good", "weather"]
        for word in english_words:
            assert word not in [w.lower() for w in words], (
                f"English word '{word}' should be filtered"
            )

    def test_spanish_words_are_filtered(self, parser):
        """Test that Spanish words are filtered out"""
        text = "Das Haus ist muy bonito y grande"
        words = parser.extract_words(text)

        # Should keep German words
        assert "das" in [w.lower() for w in words]
        assert "haus" in [w.lower() for w in words]
        assert "ist" in [w.lower() for w in words]

        # Should filter Spanish words
        spanish_words = ["muy", "bonito", "grande"]
        for word in spanish_words:
            assert word not in [w.lower() for w in words], (
                f"Spanish word '{word}' should be filtered"
            )

    def test_french_words_are_filtered(self, parser):
        """Test that French words are filtered out"""
        text = "Die Maison ist très beau aujourd'hui"
        words = parser.extract_words(text)

        # Should keep German words
        assert "die" in [w.lower() for w in words]
        assert "ist" in [w.lower() for w in words]

        # Should filter French words
        french_words = ["maison", "très", "beau"]
        for word in french_words:
            assert word not in [w.lower() for w in words], (
                f"French word '{word}' should be filtered"
            )

    def test_german_words_with_umlauts_are_kept(self, parser):
        """Test that German words with umlauts are always kept"""
        text = "The schöne Mädchen is très jolie"
        words = parser.extract_words(text)

        # Words with umlauts should always be kept
        umlaut_words = ["schöne", "mädchen"]
        for word in umlaut_words:
            assert word in [w.lower() for w in words], (
                f"German word with umlaut '{word}' should be kept"
            )

    def test_german_pattern_words_are_kept(self, parser):
        """Test that words matching German patterns are kept"""
        text = "The Bildung and Möglichkeit are très wichtig"
        words = parser.extract_words(text)

        # Words with German endings should be kept
        german_pattern_words = ["bildung", "möglichkeit", "wichtig"]
        for word in german_pattern_words:
            assert word in [w.lower() for w in words], (
                f"German pattern word '{word}' should be kept"
            )

    def test_common_german_words_are_kept(self, parser):
        """Test that common German vocabulary is kept"""
        text = "Ich gehe nach Hause with my friend today"
        words = parser.extract_words(text)

        # Common German words should be kept
        german_words = ["ich", "gehe", "nach", "hause"]
        for word in german_words:
            assert word in [w.lower() for w in words], (
                f"Common German word '{word}' should be kept"
            )

        # English words should be filtered
        english_words = ["with", "friend", "today"]
        for word in english_words:
            assert word not in [w.lower() for w in words], (
                f"English word '{word}' should be filtered"
            )

    def test_mixed_language_text_filtering(self, parser):
        """Test filtering in complex mixed language text"""
        text = "Hello! Ich liebe the beautiful Welt and casa bonita sehr much."
        words = parser.extract_words(text)

        # German words that should be kept
        expected_german = ["ich", "liebe", "welt", "sehr"]
        for word in expected_german:
            assert word in [w.lower() for w in words], (
                f"German word '{word}' should be kept"
            )

        # Foreign words that should be filtered
        foreign_words = ["hello", "beautiful", "casa", "bonita", "much"]
        for word in foreign_words:
            assert word not in [w.lower() for w in words], (
                f"Foreign word '{word}' should be filtered"
            )

    def test_proper_nouns_handling(self, parser):
        """Test that potential proper nouns are handled correctly"""
        text = "Peter wohnt in Berlin near the Thames river"
        words = parser.extract_words(text)

        # Common German words should be kept
        assert "wohnt" in [w.lower() for w in words]

        # Proper nouns and foreign words handling
        # Peter and Berlin might be kept (proper nouns), Thames should be filtered
        assert "thames" not in [w.lower() for w in words]
        assert "river" not in [w.lower() for w in words]

    def test_short_words_still_follow_language_rules(self, parser):
        """Test that even short words follow language filtering"""
        text = "I go to der Markt for buy things"
        words = parser.extract_words(text)

        # German words should be kept regardless of length
        assert "der" in [w.lower() for w in words]

        # Short English words should still be filtered if in blacklist
        # Note: very short words (1-2 chars) might not be in blacklist,
        # but longer ones should be filtered
        assert "buy" not in [w.lower() for w in words]

    def test_german_prefixes_and_suffixes(self, parser):
        """Test recognition of German morphological patterns"""
        text = "The vergessen and entstehen are verbs with beautiful meanings"
        words = parser.extract_words(text)

        # Words with German prefixes should be kept
        german_morphology = ["vergessen", "entstehen"]
        for word in german_morphology:
            assert word in [w.lower() for w in words], (
                f"Word with German morphology '{word}' should be kept"
            )

        # English words should be filtered
        english_words = ["verbs", "beautiful", "meanings"]
        for word in english_words:
            assert word not in [w.lower() for w in words], (
                f"English word '{word}' should be filtered"
            )

    def test_case_insensitive_filtering(self, parser):
        """Test that filtering works regardless of case"""
        text = "BEAUTIFUL House ist sehr SCHÖN today"
        words = parser.extract_words(text)

        # German words should be kept
        assert any(w.lower() == "ist" for w in words)
        assert any(w.lower() == "sehr" for w in words)
        assert any(w.lower() == "schön" for w in words)

        # English words should be filtered regardless of case
        assert not any(w.lower() == "beautiful" for w in words)
        assert not any(w.lower() == "house" for w in words)
        assert not any(w.lower() == "today" for w in words)
