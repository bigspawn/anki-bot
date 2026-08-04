"""
Unified database manager that coordinates all repositories
"""

import logging
from typing import Any

from .connection import DatabaseConnection
from .models import User, UserStats, Word
from .repositories.progress_repository import ProgressRepository
from .repositories.user_repository import UserRepository
from .repositories.word_repository import WordRepository

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Unified database manager that coordinates all repositories"""

    def __init__(self, db_path: str | None = None):
        self.db_connection = DatabaseConnection(db_path)
        self.user_repo = UserRepository(self.db_connection)
        self.word_repo = WordRepository(self.db_connection)
        self.progress_repo = ProgressRepository(self.db_connection)

    def init_database(self) -> None:
        """Initialize database tables and indexes"""
        self.db_connection.init_database()

    # User methods
    def create_user(
        self,
        telegram_id: int,
        first_name: str,
        last_name: str | None = None,
        username: str | None = None,
    ) -> User | None:
        """Create a new user"""
        return self.user_repo.create_user(telegram_id, first_name, last_name, username)

    def get_user_by_telegram_id(self, telegram_id: int) -> User | None:
        """Get user by Telegram ID"""
        return self.user_repo.get_user_by_telegram_id(telegram_id)

    def get_user_stats(self, telegram_id: int) -> UserStats | None:
        """Get comprehensive user statistics"""
        return self.user_repo.get_user_stats(telegram_id)

    def get_all_active_users(self) -> list[User]:
        """Get all active users"""
        return self.user_repo.get_all_active_users()

    # Word methods
    def get_word_by_lemma(self, lemma: str) -> Word | None:
        """Get word by lemma"""
        return self.word_repo.get_word_by_lemma(lemma)

    def get_word_by_id(self, word_id: int) -> Word | None:
        """Get word by ID"""
        return self.word_repo.get_word_by_id(word_id)

    def check_word_exists(self, telegram_id: int, lemma: str) -> bool:
        """Check if word exists in user's learning progress"""
        return self.word_repo.check_word_exists(telegram_id, lemma)

    def check_multiple_words_exist(
        self, telegram_id: int, lemmas: list[str]
    ) -> dict[str, bool]:
        """Check existence of multiple words at once, including potential lemma forms"""
        result = {}

        for lemma in lemmas:
            # Check original lemma first
            exists = self.word_repo.check_word_exists(telegram_id, lemma)

            if not exists:
                # Try potential lemma forms
                potential_lemmas = self._get_potential_lemmas(lemma)
                for potential in potential_lemmas:
                    if potential != lemma and self.word_repo.check_word_exists(
                        telegram_id, potential
                    ):
                        exists = True
                        break

            result[lemma] = exists

        return result

    def get_words_by_user(self, telegram_id: int) -> list[dict[str, Any]]:
        """Get all words for a user with learning progress"""
        return self.word_repo.get_words_by_user(telegram_id)

    def get_due_words(
        self, telegram_id: int, limit: int = 10, randomize: bool = True
    ) -> list[dict[str, Any]]:
        """Get words due for review"""
        return self.word_repo.get_due_words(telegram_id, limit, randomize)

    def get_new_words(
        self, telegram_id: int, limit: int = 10, randomize: bool = True
    ) -> list[dict[str, Any]]:
        """Get new words (never reviewed)"""
        return self.word_repo.get_new_words(telegram_id, limit, randomize)

    def get_difficult_words(
        self, telegram_id: int, limit: int = 10, randomize: bool = True
    ) -> list[dict[str, Any]]:
        """Get difficult words (low easiness factor)"""
        return self.word_repo.get_difficult_words(telegram_id, limit, randomize)

    def get_verb_words(
        self, telegram_id: int, limit: int = 10, randomize: bool = True
    ) -> list[dict[str, Any]]:
        """Get verb words for study"""
        return self.word_repo.get_verb_words(telegram_id, limit, randomize)

    def get_reflexive_verbs(
        self, telegram_id: int, limit: int = 10, randomize: bool = True
    ) -> list[dict[str, Any]]:
        """Get reflexive verbs for study"""
        return self.word_repo.get_reflexive_verbs(telegram_id, limit, randomize)

    def get_preposition_verbs(
        self, telegram_id: int, limit: int = 10, randomize: bool = True
    ) -> list[dict[str, Any]]:
        """Get verbs governing a preposition for study"""
        return self.word_repo.get_preposition_verbs(telegram_id, limit, randomize)

    def get_cloze_words(
        self, telegram_id: int, limit: int = 10, randomize: bool = True
    ) -> list[dict[str, Any]]:
        """Get gap-fill and error-correction drills for study"""
        return self.word_repo.get_cloze_words(telegram_id, limit, randomize)

    def get_reflexive_case_words(
        self, telegram_id: int, limit: int = 10, randomize: bool = True
    ) -> list[dict[str, Any]]:
        """Get reflexive verbs whose pronoun case is recorded, for study"""
        return self.word_repo.get_reflexive_case_words(telegram_id, limit, randomize)

    def get_pronoun_case_words(
        self, telegram_id: int, limit: int = 10, randomize: bool = True
    ) -> list[dict[str, Any]]:
        """Get pronoun declension cards for study"""
        return self.word_repo.get_pronoun_case_words(telegram_id, limit, randomize)

    def get_article_case_words(
        self, telegram_id: int, limit: int = 10, randomize: bool = True
    ) -> list[dict[str, Any]]:
        """Get article declension cards for study"""
        return self.word_repo.get_article_case_words(telegram_id, limit, randomize)

    def get_dativ_verbs(
        self, telegram_id: int, limit: int = 10, randomize: bool = True
    ) -> list[dict[str, Any]]:
        """Get verbs governing Dativ for study"""
        return self.word_repo.get_dativ_verbs(telegram_id, limit, randomize)

    def get_dat_akk_verbs(
        self, telegram_id: int, limit: int = 10, randomize: bool = True
    ) -> list[dict[str, Any]]:
        """Get verbs taking both a Dativ and an Akkusativ object for study"""
        return self.word_repo.get_dat_akk_verbs(telegram_id, limit, randomize)

    def get_wo_wohin_words(
        self, telegram_id: int, limit: int = 10, randomize: bool = True
    ) -> list[dict[str, Any]]:
        """Get wo/wohin preposition triples for study"""
        return self.word_repo.get_wo_wohin_words(telegram_id, limit, randomize)

    def get_verschmelzung_words(
        self, telegram_id: int, limit: int = 10, randomize: bool = True
    ) -> list[dict[str, Any]]:
        """Get preposition-article contractions for study"""
        return self.word_repo.get_verschmelzung_words(telegram_id, limit, randomize)

    def get_word_order_words(
        self, telegram_id: int, limit: int = 10, randomize: bool = True
    ) -> list[dict[str, Any]]:
        """Get word order cards for study"""
        return self.word_repo.get_word_order_words(telegram_id, limit, randomize)

    def get_adjective_ending_words(
        self, telegram_id: int, limit: int = 10, randomize: bool = True
    ) -> list[dict[str, Any]]:
        """Get adjective ending cards for study"""
        return self.word_repo.get_adjective_ending_words(telegram_id, limit, randomize)

    def get_verb_form_words(
        self, telegram_id: int, limit: int = 10, randomize: bool = True
    ) -> list[dict[str, Any]]:
        """Get imperative and modal past cards for study"""
        return self.word_repo.get_verb_form_words(telegram_id, limit, randomize)

    def get_zeitangabe_words(
        self, telegram_id: int, limit: int = 10, randomize: bool = True
    ) -> list[dict[str, Any]]:
        """Get date and duration cards for study"""
        return self.word_repo.get_zeitangabe_words(telegram_id, limit, randomize)

    def get_personalpronomen_words(
        self, telegram_id: int, limit: int = 10, randomize: bool = True
    ) -> list[dict[str, Any]]:
        """Get personal pronoun declension cards for study"""
        return self.word_repo.get_personalpronomen_words(telegram_id, limit, randomize)

    def get_possessivpronomen_words(
        self, telegram_id: int, limit: int = 10, randomize: bool = True
    ) -> list[dict[str, Any]]:
        """Get possessive pronoun declension cards for study"""
        return self.word_repo.get_possessivpronomen_words(telegram_id, limit, randomize)

    def get_reflexivpronomen_words(
        self, telegram_id: int, limit: int = 10, randomize: bool = True
    ) -> list[dict[str, Any]]:
        """Get reflexive pronoun declension cards for study"""
        return self.word_repo.get_reflexivpronomen_words(telegram_id, limit, randomize)

    def get_demonstrativ_words(
        self, telegram_id: int, limit: int = 10, randomize: bool = True
    ) -> list[dict[str, Any]]:
        """Get demonstrative pronoun declension cards for study"""
        return self.word_repo.get_demonstrativ_words(telegram_id, limit, randomize)

    def get_words_by_topic(
        self, telegram_id: int, topic: str, limit: int = 10, randomize: bool = True
    ) -> list[dict[str, Any]]:
        """Get cards tagged with a topic slug for study"""
        return self.word_repo.get_words_by_topic(telegram_id, topic, limit, randomize)

    def get_topic_slugs(self, telegram_id: int) -> list[str]:
        """Get every topic slug present in the user's cards"""
        return self.word_repo.get_topic_slugs(telegram_id)

    def get_recent_words(
        self, telegram_id: int, limit: int = 10
    ) -> list[dict[str, Any]]:
        """Get the most recently added words for study"""
        return self.word_repo.get_recent_words(telegram_id, limit)

    def get_words_by_part_of_speech(
        self,
        telegram_id: int,
        part_of_speech: str,
        limit: int = 10,
        randomize: bool = True,
    ) -> list[dict[str, Any]]:
        """Get words filtered by part of speech for study"""
        return self.word_repo.get_words_by_part_of_speech(
            telegram_id, part_of_speech, limit, randomize
        )

    def get_words_by_level(
        self, telegram_id: int, level: str, limit: int = 10, randomize: bool = True
    ) -> list[dict[str, Any]]:
        """Get words filtered by CEFR level for study"""
        return self.word_repo.get_words_by_level(telegram_id, level, limit, randomize)

    def get_words_by_lemma_set(
        self,
        telegram_id: int,
        lemmas: list[str],
        limit: int = 10,
        randomize: bool = True,
    ) -> list[dict[str, Any]]:
        """Get user's words whose lemma is in a given set for study"""
        return self.word_repo.get_words_by_lemma_set(
            telegram_id, lemmas, limit, randomize
        )

    def add_words_to_user(
        self, telegram_id: int, words_data: list[dict[str, Any]]
    ) -> int:
        """Add multiple words to user's learning progress"""
        return self.word_repo.add_words_to_user(telegram_id, words_data)

    def add_words_with_details(
        self, telegram_id: int, words_data: list[dict[str, Any]]
    ) -> dict[str, list[str]]:
        """Add words and report which lemmas were added, duplicated or invalid"""
        return self.word_repo.add_words_with_details(telegram_id, words_data)

    def add_word_to_user(
        self, telegram_id: int, word_data: dict[str, Any]
    ) -> Word | None:
        """Add a single word to user's learning progress"""
        added_count = self.word_repo.add_words_to_user(telegram_id, [word_data])
        if added_count > 0:
            # Return the word that was added
            lemma = word_data.get("lemma")
            if lemma:
                return self.word_repo.get_word_by_lemma(lemma)
        return None

    # Progress methods
    def update_learning_progress(
        self, telegram_id: int, word_id: int, rating: int, response_time_ms: int = 0
    ) -> bool:
        """Update learning progress after review"""
        return self.progress_repo.update_learning_progress(
            telegram_id, word_id, rating, response_time_ms=response_time_ms
        )

    def get_learning_progress(
        self, telegram_id: int, word_id: int
    ) -> dict[str, Any] | None:
        """Get learning progress for a specific word"""
        return self.progress_repo.get_learning_progress(telegram_id, word_id)

    def get_review_history(
        self, telegram_id: int, word_id: int | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        """Get review history for user or specific word"""
        return self.progress_repo.get_review_history(telegram_id, word_id, limit)

    def get_performance_stats(self, telegram_id: int, days: int = 30) -> dict[str, Any]:
        """Get performance statistics for user"""
        return self.progress_repo.get_performance_stats(telegram_id, days)

    def get_topic_stats(self, telegram_id: int) -> list[dict[str, Any]]:
        """Aggregate review history per topic slug, worst accuracy first"""
        return self.progress_repo.get_topic_stats(telegram_id)

    def has_reviewed_today(self, telegram_id: int) -> bool:
        """Check whether the user has already reviewed at least one word today"""
        return self.progress_repo.has_reviewed_today(telegram_id)

    # Additional methods for complete API
    def add_word(self, telegram_id: int, word_data: dict[str, Any]) -> Word | None:
        """Add a single word to user's learning progress"""
        return self.add_word_to_user(telegram_id, word_data)

    def add_words_batch(
        self, telegram_id: int, words_data: list[dict[str, Any]]
    ) -> list[int]:
        """Add multiple words and return list of word IDs"""
        count = self.add_words_to_user(telegram_id, words_data)
        # Return mock list of IDs for now - this could be improved
        return list(range(1, count + 1))

    def get_existing_words_from_list(
        self, telegram_id: int, lemmas: list[str]
    ) -> list[str]:
        """Get existing words from a list of lemmas"""
        existence_map = self.check_multiple_words_exist(telegram_id, lemmas)
        return [lemma for lemma, exists in existence_map.items() if exists]

    def get_existing_words_details(
        self, telegram_id: int, lemmas: list[str]
    ) -> list[dict[str, Any]]:
        """Get word details for existing words by lemmas"""
        return self.word_repo.get_existing_words_details(telegram_id, lemmas)

    def add_review_record(
        self,
        telegram_id: int,
        word_id: int,
        rating: int,
        response_time_ms: int = 0,
    ) -> bool:
        """Add a review record - alias for update_learning_progress"""
        return self.update_learning_progress(
            telegram_id, word_id, rating, response_time_ms
        )

    def get_connection(self):
        """Get database connection for direct SQL access in tests"""
        return self.db_connection.get_connection()

    def _get_potential_lemmas(self, word: str) -> list[str]:
        """Get potential lemmas for a word - helper method for tests"""
        # Basic implementation for German verb inflection detection
        potential_lemmas = [word]

        # Remove common German endings and try to construct base form
        if word.endswith("en"):
            potential_lemmas.append(word[:-2])
        elif word.endswith("est"):
            # For words ending in 'est' (like bedeutest), remove 'est' and add 'en'
            potential_lemmas.append(word[:-3] + "en")
        elif word.endswith("et"):
            # For words ending in 'et' (like bedeutet), remove 'et' and add 'en'
            potential_lemmas.append(word[:-2] + "en")
        elif word.endswith("st"):
            potential_lemmas.append(word[:-2] + "en")
        elif word.endswith("t"):
            # For words ending in 't', try removing 't' and adding 'en'
            potential_lemmas.append(word[:-1] + "en")
        elif word.endswith("e"):
            potential_lemmas.append(word[:-1] + "en")

        return list(set(potential_lemmas))


# Global instance
_db_manager = None


def get_db_manager(db_path: str | None = None) -> DatabaseManager:
    """Get global database manager instance"""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager(db_path)
    return _db_manager
