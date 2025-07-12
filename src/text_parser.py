"""
German text parsing and word extraction
"""

import logging
import re

try:
    import spacy

    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False

logger = logging.getLogger(__name__)


class GermanTextParser:
    """Parser for extracting German words from text"""

    def __init__(self):
        self.word_pattern = re.compile(r"\b[a-zA-ZäöüßÄÖÜ]+\b")
        self.sentence_pattern = re.compile(r"[.!?]+")

        # Initialize SpaCy if available
        self.nlp = None
        if SPACY_AVAILABLE:
            try:
                self.nlp = spacy.load("de_core_news_sm")

                logger.info("SpaCy German model loaded successfully")
            except OSError:
                logger.warning(
                    "SpaCy German model not found, falling back to regex-based validation"
                )
                self.nlp = None

    def extract_words(
        self, text: str, min_length: int = 2, max_length: int = 50
    ) -> list[str]:
        """
        Extract German words from text

        Args:
            text: Input German text
            min_length: Minimum word length
            max_length: Maximum word length

        Returns:
            List of extracted German words (lowercased, deduplicated)
        """
        if not text or not text.strip():
            return []

        # Clean and normalize text
        text = self._clean_text(text)

        # Extract words using regex
        words = self.word_pattern.findall(text.lower())

        # Filter words
        filtered_words = []
        for word in words:
            if self._is_valid_word(word, min_length, max_length):
                filtered_words.append(word)

        # Remove duplicates while preserving order
        unique_words = list(dict.fromkeys(filtered_words))

        logger.info(
            f"Extracted {len(unique_words)} unique words from text of {len(text)} characters"
        )
        return unique_words

    def _clean_text(self, text: str) -> str:
        """Clean and normalize German text"""
        # Remove non-German characters except punctuation
        text = re.sub(r"[^\w\säöüßÄÖÜ.,!?;:\-\'\"()]", " ", text)

        # Remove extra whitespace
        text = re.sub(r"\s+", " ", text.strip())

        return text

    def _is_valid_word(self, word: str, min_length: int, max_length: int) -> bool:
        """Check if word is valid for extraction"""
        # Length check
        if len(word) < min_length or len(word) > max_length:
            return False

        # Skip pure numbers
        if word.isdigit():
            return False

        # Must contain at least one letter
        if not re.search(r"[a-zA-ZäöüßÄÖÜ]", word):
            return False

        # Skip words that are mostly punctuation
        letter_count = len(re.findall(r"[a-zA-ZäöüßÄÖÜ]", word))
        if letter_count < len(word) * 0.7:  # At least 70% letters
            return False

        return True

    def extract_sentences(self, text: str) -> list[str]:
        """Extract sentences from German text"""
        if not text or not text.strip():
            return []

        # Split by sentence endings
        sentences = self.sentence_pattern.split(text)

        # Clean and filter sentences
        cleaned_sentences = []
        for sentence in sentences:
            sentence = sentence.strip()
            if sentence and len(sentence) > 10:  # Minimum sentence length
                cleaned_sentences.append(sentence)

        return cleaned_sentences

    def get_word_context(
        self, text: str, target_word: str, context_size: int = 10
    ) -> list[str]:
        """Get context sentences containing the target word"""
        sentences = self.extract_sentences(text)
        contexts = []

        target_word_lower = target_word.lower()

        for sentence in sentences:
            words_in_sentence = self.word_pattern.findall(sentence.lower())
            if target_word_lower in words_in_sentence:
                contexts.append(sentence.strip())

        # Limit number of contexts
        return contexts[:context_size]

    def validate_german_text(self, text: str) -> bool:
        """Validate if text appears to be German using ONLY SpaCy"""
        if not text or len(text.strip()) < 3:
            return False

        # SpaCy is required - no fallback
        if self.nlp is None:
            logger.error(
                "SpaCy German model not available - cannot validate German text"
            )
            return False

        try:
            doc = self.nlp(text)

            # Count total valid tokens first
            valid_tokens = [
                token for token in doc if token.is_alpha and len(token.text) > 1
            ]
            total_tokens = len(valid_tokens)
            is_single_word = total_tokens == 1

            # Use SpaCy's German model analysis capabilities
            german_indicators = 0
            foreign_indicators = 0
            has_german_umlauts = False

            for token in valid_tokens:
                # Strong indicator: German umlauts
                if any(char in token.text for char in "äöüßÄÖÜ"):
                    german_indicators += 3  # Weight umlauts heavily
                    has_german_umlauts = True

                # Check for foreign language markers (SpaCy detects non-German)
                elif hasattr(token, "morph") and token.morph:
                    morph_str = str(token.morph)
                    if "Foreign=Yes" in morph_str:
                        foreign_indicators += 1
                        continue

                    # German case system is distinctive, but be conservative
                    # Only count if token has German characteristics
                    if any(
                        case in morph_str
                        for case in ["Case=Nom", "Case=Acc", "Case=Dat", "Case=Gen"]
                    ):
                        # Only count as German if it's a function word (DET, PRON, AUX) which are more reliable
                        # or if it's combined with other German indicators
                        if token.pos_ in ["DET", "PRON", "AUX"] or has_german_umlauts:
                            german_indicators += 2
                    # German-specific morphological features for determiners
                    elif (
                        any(
                            feat in morph_str
                            for feat in ["Definite=Def", "Definite=Ind"]
                        )
                        and token.pos_ == "DET"
                    ):
                        german_indicators += 1

                # Check if SpaCy processes it as proper German (not foreign)
                # Only count specific German function words or words with umlauts
                if token.pos_ in ["DET", "PRON", "AUX"] and token.pos_ != "X":
                    # Function words are more reliable for language detection
                    # But exclude common foreign words that might be misclassified as pronouns
                    foreign_words_blacklist = [
                        # English
                        "dog", "man", "he", "she", "it", "they", "cat", "house", "world", "short",
                        # Spanish
                        "hola", "casa", "mundo", "amor", "vida", "tiempo",
                        # French
                        "bonjour", "maison", "monde", "amour", "vie", "temps",
                        # Italian
                        "ciao", "casa", "mondo", "amore", "vita", "tempo"
                    ]
                    if token.pos_ == "PRON" and token.text.lower() in foreign_words_blacklist:
                        # Skip these likely false positives
                        pass
                    else:
                        german_indicators += 1
                elif token.pos_ in ["NOUN", "VERB", "ADJ", "ADV"] and token.pos_ != "X":
                    # Content words: count if they have umlauts OR specific German morphology
                    if any(char in token.text for char in "äöüßÄÖÜ"):
                        german_indicators += 1
                    elif hasattr(token, "morph") and token.morph:
                        morph_str = str(token.morph)
                        # Be conservative: require case system + gender/number for nouns
                        # or verb-specific features for verbs
                        has_case = "Case=" in morph_str
                        has_gender = "Gender=" in morph_str
                        has_number = "Number=" in morph_str
                        has_verb_features = any(feat in morph_str for feat in ["Mood=", "Tense=", "VerbForm="])

                        # Comprehensive foreign words blacklist
                        foreign_words_blacklist = [
                            # English
                            "dog", "cat", "hello", "world", "house", "man", "woman", "good", "bad", "nice",
                            "love", "time", "life", "water", "fire", "earth", "air", "book", "table", "chair",
                            "short", "work", "yes", "no", "big", "small", "new", "old", "young", "fast",
                            # Spanish
                            "hola", "casa", "mundo", "amor", "vida", "tiempo", "agua", "fuego", "tierra", "aire",
                            "libro", "mesa", "silla", "perro", "gato", "bueno", "malo", "bonito",
                            # French
                            "bonjour", "maison", "monde", "amour", "vie", "temps", "eau", "feu", "terre", "air",
                            "livre", "table", "chaise", "chien", "chat", "bon", "mauvais", "beau",
                            # Italian
                            "ciao", "casa", "mondo", "amore", "vita", "tempo", "acqua", "fuoco", "terra", "aria",
                            "libro", "tavolo", "sedia", "cane", "gatto", "buono", "cattivo", "bello"
                        ]

                        # For nouns: require German case system + gender/number
                        if token.pos_ == "NOUN" and has_case and (has_gender or has_number):
                            # Additional check: avoid common foreign words
                            if token.text.lower() not in foreign_words_blacklist:
                                # Extra validation: for single words without umlauts, be more conservative
                                if is_single_word and not has_german_umlauts:
                                    # Require at least 4 characters for foreign-looking single nouns
                                    if len(token.text) >= 4:
                                        german_indicators += 1
                                else:
                                    german_indicators += 1
                        # For verbs: require German verbal morphology
                        elif token.pos_ == "VERB" and has_verb_features:
                            german_indicators += 1
                        # For adjectives: require case or degree
                        elif token.pos_ == "ADJ" and (has_case or "Degree=" in morph_str):
                            if token.text.lower() not in foreign_words_blacklist:
                                german_indicators += 1

            # Decision logic based on SpaCy analysis
            if total_tokens == 0:
                return False

            # If we found umlauts, it's definitely German
            if has_german_umlauts:
                return True

            # If SpaCy marked too many words as foreign, it's not German
            if foreign_indicators > total_tokens * 0.5:
                return False

            # For texts without umlauts, require evidence from SpaCy
            confidence_ratio = german_indicators / total_tokens

            # Single word: need some confidence from SpaCy
            if total_tokens == 1:
                return confidence_ratio >= 0.5

            # Multiple words: need moderate confidence
            return confidence_ratio >= 0.4

        except Exception as e:
            logger.error(f"SpaCy language detection failed: {e}")
            return False


# Global parser instance
_parser = None


def get_text_parser() -> GermanTextParser:
    """Get global text parser instance"""
    global _parser
    if _parser is None:
        _parser = GermanTextParser()
    return _parser


def extract_german_words(
    text: str, min_length: int = 2, max_length: int = 50
) -> list[str]:
    """Convenience function to extract German words"""
    parser = get_text_parser()
    return parser.extract_words(text, min_length, max_length)


def validate_german_text(text: str) -> bool:
    """Convenience function to validate German text"""
    parser = get_text_parser()
    return parser.validate_german_text(text)
