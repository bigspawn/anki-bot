"""
Word processing with OpenAI API integration
"""

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any

from openai import AsyncOpenAI

from .config import get_settings
from .database import get_db_manager
from .text_parser import get_text_parser
from .utils import log_execution_time, rate_limit, retry_on_exception

logger = logging.getLogger(__name__)


@dataclass
class ProcessedWord:
    """Processed word data from OpenAI"""

    word: str
    lemma: str
    part_of_speech: str
    article: str | None
    translation: str
    example: str
    additional_forms: str | None
    confidence: float = 1.0


def validate_article(
    article: str | None, lemma: str, part_of_speech: str
) -> str | None:
    """
    Валидация артикля для немецких существительных

    Args:
        article: Article from OpenAI
        lemma: Word lemma
        part_of_speech: Part of speech

    Returns:
        Valid article or None
    """
    # Only nouns should have articles
    if part_of_speech != "noun":
        return None

    # First check for plural nouns
    if is_likely_plural(lemma):
        if article and article != 'None':
            logger.warning(
                f"Removed article for plural noun '{lemma}': '{article}' -> None"
            )
        return None

    # If lemma is empty, return None
    if not lemma or not lemma.strip():
        return None

    # Check known dictionary regardless of input article
    corrected_article = get_correct_article_from_dict(lemma)
    if corrected_article is not None:
        if corrected_article != article:
            logger.warning(
                f"Corrected article for '{lemma}': '{article}' -> "
                f"'{corrected_article}'"
            )
        return corrected_article

    # If article is empty or incorrect, try to fix it
    if (
        not article
        or article == 'None'
        or article not in ["der", "die", "das"]
    ):
        # If not in dictionary, try to guess by ending
        guessed_article = guess_article_by_ending(lemma)
        if guessed_article and guessed_article != article:
            logger.warning(
                f"Guessed article for '{lemma}': '{article}' -> "
                f"'{guessed_article}' (by ending)"
            )
            return guessed_article

        # If this is clearly a noun but article is wrong
        if article and article not in ["der", "die", "das"]:
            logger.error(f"Invalid article for '{lemma}': '{article}' - set to None")
            return None

    return article


def get_correct_article_from_dict(lemma: str) -> str | None:
    """Get correct article from dictionary of known words"""
    known_articles = {
        # Masculine (der)
        "Mann": "der", "Vater": "der", "Bruder": "der", "Sohn": "der", "Freund": "der",
        "Lehrer": "der", "Schüler": "der", "Hund": "der", "Tisch": "der", "Stuhl": "der",
        "Baum": "der", "Tag": "der", "Abend": "der", "Morgen": "der", "Computer": "der",
        "Fernseher": "der", "Kühlschrank": "der", "Apfel": "der", "Käse": "der", "Fisch": "der",
        "Kaffee": "der", "Tee": "der", "Zucker": "der", "Reis": "der", "Salat": "der",
        "Kuchen": "der", "Film": "der", "Park": "der", "Garten": "der", "Himmel": "der",
        "Regen": "der", "Schnee": "der", "Wind": "der", "Frühling": "der", "Sommer": "der",
        "Herbst": "der", "Winter": "der", "Beruf": "der", "Flur": "der", "Fußball": "der",
        "Zentimeter": "der", "Teppich": "der",

        # Feminine (die)
        "Frau": "die", "Mutter": "die", "Schwester": "die", "Tochter": "die", "Freundin": "die",
        "Lehrerin": "die", "Schülerin": "die", "Katze": "die", "Schule": "die", "Straße": "die",
        "Stadt": "die", "Familie": "die", "Arbeit": "die", "Zeit": "die", "Woche": "die",
        "Musik": "die", "Sprache": "die", "Frage": "die", "Antwort": "die", "Geschichte": "die",
        "Banane": "die", "Orange": "die", "Birne": "die", "Tomate": "die", "Kartoffel": "die",
        "Milch": "die", "Butter": "die", "Schokolade": "die", "Pizza": "die", "Küche": "die",
        "Wohnung": "die", "Tür": "die", "Lampe": "die", "Uhr": "die", "Farbe": "die",
        "Sonne": "die", "Wolke": "die", "Blume": "die", "Natur": "die", "Buchhandlung": "die",
        "Firma": "die",

        # Neuter (das)
        "Kind": "das", "Mädchen": "das", "Tier": "das", "Haus": "das", "Auto": "das",
        "Fahrrad": "das", "Buch": "das", "Bild": "das", "Foto": "das", "Zimmer": "das",
        "Bett": "das", "Radio": "das", "Telefon": "das", "Handy": "das", "Internet": "das",
        "Wasser": "das", "Bier": "das", "Brot": "das", "Ei": "das", "Fleisch": "das",
        "Gemüse": "das", "Obst": "das", "Eis": "das", "Geld": "das", "Jahr": "das",
        "Wetter": "das", "Land": "das", "Hotel": "das", "Restaurant": "das", "Kino": "das",
        "Museum": "das", "Geschäft": "das", "Problem": "das", "Gespräch": "das", "Spiel": "das",
        "Hobby": "das", "Leben": "das", "Abendessen": "das", "Profil": "das",

        # Plural (no article)
        "Eltern": None, "Kinder": None, "Leute": None, "Geschwister": None, "Großeltern": None,
        "Pommes": None,
    }

    return known_articles.get(lemma)


def guess_article_by_ending(lemma: str) -> str | None:
    """Guess article by word ending"""
    lemma_lower = lemma.lower()

    # Rules for determining articles by endings
    das_endings = ['chen', 'lein', 'um', 'ma', 'ment', 'tum', 'o']
    die_endings = ['e', 'ei', 'ie', 'in', 'heit', 'keit', 'schaft', 'tion', 'sion', 'tät', 'ung', 'ur']
    der_endings = ['er', 'en', 'el', 'ich', 'ig', 'ling', 'or', 'us']

    # Check in order of specificity (most specific first)
    for ending in sorted(das_endings, key=len, reverse=True):
        if lemma_lower.endswith(ending):
            return "das"

    for ending in sorted(die_endings, key=len, reverse=True):
        if lemma_lower.endswith(ending):
            return "die"

    for ending in sorted(der_endings, key=len, reverse=True):
        if lemma_lower.endswith(ending):
            return "der"

    return None


def is_likely_plural(lemma: str) -> bool:
    """Check if word is likely plural"""
    plural_indicators = [
        'eltern', 'geschwister', 'großeltern', 'leute', 'pommes',
        'kinder', 'menschen', 'personen', 'studenten', 'schüler'
    ]

    lemma_lower = lemma.lower()

    # Exact matches
    if lemma_lower in plural_indicators:
        return True

    # Plural endings
    plural_endings = ['en', 'er', 'e', 's']
    for ending in plural_endings:
        if (
            lemma_lower.endswith(ending)
            and len(lemma) > 3
            and any(
                indicator in lemma_lower
                for indicator in ['kinder', 'menschen', 'leute']
            )
        ):
            return True

    return False


class WordProcessor:
    """Processes German words using OpenAI API"""

    def __init__(self, api_key: str | None = None):
        settings = get_settings()
        self.client = AsyncOpenAI(
            api_key=api_key or settings.openai_api_key, timeout=settings.api_timeout
        )
        self.model = settings.openai_model
        self.max_tokens = settings.openai_max_tokens
        self.temperature = settings.openai_temperature
        self.text_parser = get_text_parser()

        # Rate limiting
        self.max_requests_per_day = settings.max_openai_requests_per_day
        self.request_count = 0

    @retry_on_exception(max_retries=3, delay=1.0, backoff=2.0)
    @rate_limit(calls_per_minute=20)  # Conservative rate limiting
    @log_execution_time
    async def process_word(
        self, word: str, context: str | None = None
    ) -> ProcessedWord | None:
        """
        Process a single German word using OpenAI

        Args:
            word: German word to process
            context: Optional context sentence

        Returns:
            ProcessedWord object or None if processing failed
        """
        if not word or not word.strip():
            return None

        word = word.strip()
        logger.info(f"Processing word: {word}")

        # Extract potential lemma for checking
        lemma = self._extract_lemma(word)

        # Check if word already exists in shared table
        db_manager = get_db_manager()
        existing_word = db_manager.get_word_by_lemma(lemma)

        if existing_word:
            logger.info(f"Using existing word from shared table: {lemma}")
            return ProcessedWord(
                word=word,
                lemma=existing_word["lemma"],
                part_of_speech=existing_word["part_of_speech"] or "unknown",
                article=existing_word["article"],
                translation=existing_word["translation"],
                example=existing_word["example"] or "",
                additional_forms=existing_word["additional_forms"],
                confidence=1.0,
            )

        # Process new word with OpenAI
        if self.request_count >= self.max_requests_per_day:
            logger.warning("Daily OpenAI request limit reached")
            return None

        try:
            prompt = self._create_word_analysis_prompt(word, context)

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._get_system_prompt()},
                    {"role": "user", "content": prompt},
                ],
                max_completion_tokens=self.max_tokens,
                temperature=self.temperature,  # Now defaults to 1.0 for GPT-4 compatibility
                response_format={"type": "json_object"},
            )

            self.request_count += 1

            if not response.choices:
                logger.error("No response choices from OpenAI")
                logger.debug(f"Full response: {response}")
                return None

            message = response.choices[0].message
            content = message.content

            if not content:
                logger.error("Empty response content from OpenAI")
                logger.debug(f"Full response: {response}")
                logger.debug(f"Message: {message}")
                logger.debug(f"Finish reason: {response.choices[0].finish_reason}")

                # Return None for empty responses
                return None

            # Parse JSON response
            try:
                data = json.loads(content)
                return self._parse_openai_response(word, data)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse OpenAI response as JSON: {e}")
                logger.debug(f"Response content: {content}")
                # Return None for JSON parsing errors
                return None

        except Exception as e:
            logger.error(f"Error processing word '{word}': {e}")
            # Return None for API errors
            return None

    async def process_text(self, text: str, max_words: int = 20) -> list[ProcessedWord]:
        """
        Process German text and extract processed words

        Args:
            text: German text to process
            max_words: Maximum number of words to process

        Returns:
            List of ProcessedWord objects
        """
        if not text or not text.strip():
            return []

        logger.info(f"Processing text with {len(text)} characters")

        # Validate German text
        # TODO: fix it is not working well!!!
        if not self.text_parser.validate_german_text(text):
            logger.warning("Text does not appear to be German")
            return []

        # Extract words from text
        words = self.text_parser.extract_words(text)
        if not words:
            logger.warning("No words extracted from text")
            return []

        # Limit number of words
        if len(words) > max_words:
            logger.info(
                f"Limiting processing to {max_words} words from {len(words)} extracted"
            )
            words = words[:max_words]

        # Get context for words
        word_contexts = {}
        for word in words:
            contexts = self.text_parser.get_word_context(text, word, context_size=1)
            if contexts:
                word_contexts[word] = contexts[0]

        # Use efficient batch processing instead of individual word processing
        processed_words = await self.batch_process_words(words, word_contexts)

        logger.info(
            f"Successfully processed {len(processed_words)} words from {len(words)} attempted"
        )
        return processed_words

    def _get_system_prompt(self) -> str:
        """Get system prompt for OpenAI"""
        return """You are a German language expert assistant. Your task is to analyze German words and provide detailed linguistic information.

For each German word, provide:
1. The base form (lemma)
2. Part of speech (noun, verb, adjective, adverb, etc.)
3. Article (der/die/das) for nouns only
4. Russian translation
5. Example sentence in German
6. Additional forms (plural for nouns, conjugations for verbs, etc.)

Always respond in valid JSON format with these exact keys:
- "lemma": base form of the word
- "part_of_speech": grammatical category
- "article": article for nouns (null for other parts of speech)
- "translation": Russian translation
- "example": German example sentence
- "additional_forms": JSON string with additional forms
- "confidence": confidence score from 0.0 to 1.0

Be accurate and provide high-quality linguistic analysis."""

    def _get_batch_system_prompt(self) -> str:
        """Get system prompt for batch processing multiple words"""
        return """You are a German language expert assistant. Your task is to analyze multiple German words and provide detailed linguistic information for each.

For each German word in the list, provide:
1. The base form (lemma)
2. Part of speech (noun, verb, adjective, adverb, etc.)
3. Article (der/die/das) for nouns only
4. Russian translation
5. Example sentence in German
6. Additional forms (plural for nouns, conjugations for verbs, etc.)

Respond with a JSON object where keys are the original words and values are objects with these exact keys:
- "lemma": base form of the word
- "part_of_speech": grammatical category
- "article": article for nouns (null for other parts of speech)
- "translation": Russian translation
- "example": German example sentence
- "additional_forms": JSON string with additional forms
- "confidence": confidence score from 0.0 to 1.0

Example format:
{
  "word1": {
    "lemma": "lemma1",
    "part_of_speech": "noun",
    "article": "der",
    "translation": "перевод",
    "example": "Example sentence",
    "additional_forms": "{\"plural\": \"form\"}",
    "confidence": 0.95
  },
  "word2": { ... }
}

Be accurate and provide high-quality linguistic analysis for all words."""

    def _create_word_analysis_prompt(self, word: str, context: str | None = None) -> str:
        """Create prompt for word analysis"""
        prompt = f"Analyze the German word: '{word}'"

        if context:
            prompt += f"\n\nContext sentence: '{context}'"

        prompt += "\n\nProvide detailed linguistic analysis in JSON format."

        return prompt

    def _create_batch_analysis_prompt(self, words: list[str], contexts: dict[str, str] | None = None) -> str:
        """Create prompt for batch word analysis"""
        contexts = contexts or {}

        prompt = f"Analyze the following {len(words)} German words:\n\n"

        for i, word in enumerate(words, 1):
            prompt += f"{i}. '{word}'"
            if word in contexts:
                prompt += f" (context: '{contexts[word]}')"
            prompt += "\n"

        prompt += "\nProvide detailed linguistic analysis for each word in the specified JSON format."

        return prompt

    def _parse_openai_response(
        self, original_word: str, data: dict[str, Any]
    ) -> ProcessedWord | None:
        """Parse OpenAI response into ProcessedWord"""
        try:
            translation = data.get("translation", "")

            # Validate translation
            if not self._is_valid_translation(translation):
                logger.warning(f"Invalid translation for word '{original_word}': '{translation}' - skipping word")
                return None

            return ProcessedWord(
                word=original_word,
                lemma=data.get("lemma", original_word),
                part_of_speech=data.get("part_of_speech", "unknown"),
                article=validate_article(data.get("article"), data.get("lemma", original_word), data.get("part_of_speech", "unknown")),
                translation=translation,
                example=data.get("example", ""),
                additional_forms=data.get("additional_forms"),
                confidence=float(data.get("confidence", 1.0)),
            )
        except (TypeError, ValueError) as e:
            logger.error(f"Error parsing OpenAI response: {e}")
            logger.debug(f"Response data: {data}")
            # Return None for parsing errors instead of fallback
            return None

    def _extract_lemma(self, word: str) -> str:
        """Extract potential lemma from word for database lookup"""
        word_lower = word.lower()

        # Simple heuristics for German word forms
        if word_lower.endswith("est"):
            return word_lower[:-3] + "en"
        elif word_lower.endswith("et") or word_lower.endswith("st"):
            return word_lower[:-2] + "en"
        elif word_lower.endswith("t") and len(word_lower) > 3:
            return word_lower[:-1] + "en"
        elif word_lower.endswith("e") and len(word_lower) > 2:
            return word_lower + "n"

        # Return word as-is if no patterns match
        return word_lower

    def _is_valid_translation(self, translation: str) -> bool:
        """Check if translation is valid and usable"""
        if not translation or translation.strip() == "":
            return False

        invalid_patterns = [
            "[translation unavailable]",
            "translation unavailable",
            "[unavailable]",
            "unavailable",
            "[error]",
            "error",
            "[failed]",
            "failed"
        ]

        translation_lower = translation.lower().strip()
        return not any(pattern in translation_lower for pattern in invalid_patterns)

    def _create_fallback_word(self, word: str) -> ProcessedWord | None:
        """Create fallback ProcessedWord when OpenAI fails - returns None to skip invalid words"""
        # Don't create fallback words with invalid translations
        logger.warning(
            f"Skipping word '{word}' due to translation failure - no fallback created"
        )
        return None

    @retry_on_exception(max_retries=3, delay=1.0, backoff=2.0)
    @rate_limit(calls_per_minute=20)
    @log_execution_time
    async def process_words_batch(
        self, words: list[str], contexts: dict[str, str] | None = None
    ) -> list[ProcessedWord]:
        """
        Process multiple words in a single OpenAI request

        Args:
            words: List of German words to process
            contexts: Optional dictionary mapping words to context sentences

        Returns:
            List of ProcessedWord objects
        """
        if not words:
            return []

        if len(words) > 30:  # Reduced max batch size to prevent JSON truncation
            logger.warning(
                f"Batch size {len(words)} too large, processing first 30 words"
            )
            words = words[:30]

        if self.request_count >= self.max_requests_per_day:
            logger.warning("Daily OpenAI request limit reached")
            return []

        logger.info(f"Processing batch of {len(words)} words: {words}")

        try:
            prompt = self._create_batch_analysis_prompt(words, contexts)

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._get_batch_system_prompt()},
                    {"role": "user", "content": prompt},
                ],
                max_completion_tokens=self.max_tokens * min(4, len(words) // 5 + 1),
                # Dynamic token scaling based on batch size
                temperature=self.temperature,
                response_format={"type": "json_object"},
            )

            self.request_count += 1

            if not response.choices:
                logger.error("No response choices from OpenAI")
                return []  # Return empty list for no response choices

            message = response.choices[0].message
            content = message.content

            if not content:
                logger.error("Empty response content from OpenAI")
                return []  # Return empty list for empty responses

            # Parse JSON response
            try:
                data = json.loads(content)
                return self._parse_batch_openai_response(words, data)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse OpenAI batch response as JSON: {e}")
                logger.debug(f"Response content length: {len(content)} chars")
                logger.debug(f"Response content preview: {content[:500]}...")
                logger.warning(
                    f"JSON parsing failed for batch of {len(words)} words - "
                    "consider reducing batch size"
                )
                return []  # Return empty list for JSON parsing errors

        except Exception as e:
            logger.error(f"Error processing batch of words {words}: {e}")
            return []  # Return empty list instead of fallback words

    def _parse_batch_openai_response(
        self, words: list[str], data: dict[str, Any]
    ) -> list[ProcessedWord]:
        """Parse OpenAI batch response into ProcessedWord objects"""
        processed_words = []

        for word in words:
            if word in data and isinstance(data[word], dict):
                try:
                    word_data = data[word]
                    translation = word_data.get("translation", "")

                    # Validate translation
                    if not self._is_valid_translation(translation):
                        logger.warning(
                            f"Invalid translation for word '{word}': '{translation}' - "
                            "skipping word"
                        )
                        continue

                    processed_word = ProcessedWord(
                        word=word,
                        lemma=word_data.get("lemma", word),
                        part_of_speech=word_data.get("part_of_speech", "unknown"),
                        article=validate_article(word_data.get("article"), word_data.get("lemma", word), word_data.get("part_of_speech", "unknown")),
                        translation=translation,
                        example=word_data.get("example", ""),
                        additional_forms=word_data.get("additional_forms"),
                        confidence=float(word_data.get("confidence", 1.0)),
                    )
                    processed_words.append(processed_word)
                except (TypeError, ValueError) as e:
                    logger.error(f"Error parsing word '{word}' from batch response: {e}")
                    # Skip word instead of using fallback
                    continue
            else:
                logger.warning(f"Word '{word}' not found in batch response - skipping")
                # Skip word instead of using fallback
                continue

        return processed_words

    async def batch_process_words(
        self, words: list[str], contexts: dict[str, str] | None = None
    ) -> list[ProcessedWord]:
        """
        Process multiple words efficiently using shared words table and batch processing

        Args:
            words: List of German words to process
            contexts: Optional dictionary mapping words to context sentences

        Returns:
            List of ProcessedWord objects
        """
        if not words:
            return []

        contexts = contexts or {}
        processed_words = []
        db_manager = get_db_manager()

        # Separate words into existing and new
        existing_words = []
        new_words = []

        for word in words:
            lemma = self._extract_lemma(word)
            existing_word = db_manager.get_word_by_lemma(lemma)

            if existing_word:
                processed_word = ProcessedWord(
                    word=word,
                    lemma=existing_word["lemma"],
                    part_of_speech=existing_word["part_of_speech"] or "unknown",
                    article=existing_word["article"],
                    translation=existing_word["translation"],
                    example=existing_word["example"] or "",
                    additional_forms=existing_word["additional_forms"],
                    confidence=1.0,
                )
                processed_words.append(processed_word)
                existing_words.append(word)
            else:
                new_words.append(word)

        logger.info(
            f"Found {len(existing_words)} existing words, processing "
            f"{len(new_words)} new words in batches"
        )

        # Process new words in smaller batches to avoid JSON truncation
        batch_size = 20  # Reduced batch size for better reliability

        for i in range(0, len(new_words), batch_size):
            batch = new_words[i : i + batch_size]
            batch_contexts = {
                word: contexts.get(word) for word in batch if word in contexts
            }

            # Process entire batch in single OpenAI request
            batch_results = await self.process_words_batch(batch, batch_contexts)
            processed_words.extend(batch_results)

            # Rate limiting delay between batches
            if i + batch_size < len(new_words):
                await asyncio.sleep(0.5)

        return processed_words

    def get_request_count(self) -> int:
        """Get current request count"""
        return self.request_count

    def reset_request_count(self) -> None:
        """Reset daily request count"""
        self.request_count = 0
        logger.info("Request count reset")

    async def test_connection(self) -> bool:
        """Test OpenAI API connection"""
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": "Say 'connection test successful' in German.",
                    }
                ],
                max_completion_tokens=10,
                # Note: temperature omitted to use default (1.0) for GPT-4 compatibility
            )

            if response.choices and response.choices[0].message.content:
                logger.info("OpenAI connection test successful")
                return True
            else:
                logger.error("OpenAI connection test failed - no response")
                return False

        except Exception as e:
            logger.error(f"OpenAI connection test failed: {e}")
            return False


class MockWordProcessor:
    """Mock word processor for testing"""

    def __init__(self):
        self.processed_words = []

    async def process_word(
        self, word: str, context: str | None = None
    ) -> ProcessedWord:
        """Mock word processing"""
        # Simple mock data
        mock_data = {
            "haus": ProcessedWord(
                word="haus",
                lemma="Haus",
                part_of_speech="noun",
                article="das",
                translation="дом",
                example="Das Haus ist sehr schön.",
                additional_forms='{"plural": "Häuser"}',
            ),
            "gehen": ProcessedWord(
                word="gehen",
                lemma="gehen",
                part_of_speech="verb",
                article=None,
                translation="идти",
                example="Ich gehe zur Schule.",
                additional_forms='{"past": "ging", "perfect": "gegangen"}',
            ),
            "schön": ProcessedWord(
                word="schön",
                lemma="schön",
                part_of_speech="adjective",
                article=None,
                translation="красивый",
                example="Das Wetter ist schön.",
                additional_forms='{"comparative": "schöner", "superlative": "schönste"}',
            ),
        }

        processed = mock_data.get(word.lower())
        if processed:
            # Update original word
            processed.word = word
            self.processed_words.append(processed)
            return processed

        # Return None for unknown words instead of creating invalid fallback
        return None

    async def process_text(self, text: str, max_words: int = 20) -> list[ProcessedWord]:
        """Mock text processing"""
        text_parser = get_text_parser()
        words = text_parser.extract_words(text)[:max_words]

        results = []
        for word in words:
            processed = await self.process_word(word)
            if processed is not None:  # Only add valid processed words
                results.append(processed)

        return results

    async def batch_process_words(
        self, words: list[str], contexts: dict[str, str] | None = None
    ) -> list[ProcessedWord]:
        """Mock batch processing"""
        results = []
        for word in words:
            context = contexts.get(word) if contexts else None
            processed = await self.process_word(word, context)
            if processed is not None:  # Only add valid processed words
                results.append(processed)
        return results

    async def test_connection(self) -> bool:
        """Mock connection test"""
        return True

    def get_request_count(self) -> int:
        """Mock request count"""
        return len(self.processed_words)


# Global processor instance
_word_processor = None


def get_word_processor(use_mock: bool = False) -> WordProcessor:
    """Get global word processor instance"""
    global _word_processor
    if _word_processor is None:
        _word_processor = MockWordProcessor() if use_mock else WordProcessor()
    return _word_processor


async def process_german_words(
    words: list[str], contexts: dict[str, str] | None = None
) -> list[ProcessedWord]:
    """Convenience function to process German words"""
    processor = get_word_processor()
    return await processor.batch_process_words(words, contexts)


async def process_german_text(text: str, max_words: int = 20) -> list[ProcessedWord]:
    """Convenience function to process German text"""
    processor = get_word_processor()
    return await processor.process_text(text, max_words)


if __name__ == "__main__":
    # Test the word processor
    async def test_processor():
        processor = WordProcessor()

        # Test connection
        print("Testing OpenAI connection...")
        connected = await processor.test_connection()
        print(f"Connection successful: {connected}")

        if connected:
            # Test single word
            print("\nTesting single word processing...")
            result = await processor.process_word("Haus")
            if result:
                print(f"Word: {result.word}")
                print(f"Lemma: {result.lemma}")
                print(f"Translation: {result.translation}")
                print(f"Example: {result.example}")

            # Test text processing
            print("\nTesting text processing...")
            text = "Das schöne Haus steht am Berg."
            results = await processor.process_text(text, max_words=5)
            print(f"Processed {len(results)} words from text")

            for word in results:
                print(f"- {word.lemma}: {word.translation}")

    # Run test
    asyncio.run(test_processor())
