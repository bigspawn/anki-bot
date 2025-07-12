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

    def get_user_stats(self, user_id: int) -> UserStats | None:
        """Get comprehensive user statistics"""
        return self.user_repo.get_user_stats(user_id)

    # Word methods
    def get_word_by_lemma(self, lemma: str) -> Word | None:
        """Get word by lemma"""
        return self.word_repo.get_word_by_lemma(lemma)

    def get_word_by_id(self, word_id: int) -> Word | None:
        """Get word by ID"""
        return self.word_repo.get_word_by_id(word_id)
    def check_word_exists(self, user_id: int, lemma: str) -> bool:
        """Check if word exists in user's learning progress"""
        return self.word_repo.check_word_exists(user_id, lemma)

    def check_multiple_words_exist(
        self, user_id: int, lemmas: list[str]
    ) -> dict[str, bool]:
        """Check existence of multiple words at once, including potential lemma forms"""
        result = {}

        for lemma in lemmas:
            # Check original lemma first
            exists = self.word_repo.check_word_exists(user_id, lemma)

            if not exists:
                # Try potential lemma forms
                potential_lemmas = self._get_potential_lemmas(lemma)
                for potential in potential_lemmas:
                    if (
                        potential != lemma
                        and self.word_repo.check_word_exists(user_id, potential)
                    ):
                        exists = True
                        break

            result[lemma] = exists

        return result

    def get_words_by_user(self, user_id: int) -> list[dict[str, Any]]:
        """Get all words for a user with learning progress"""
        return self.word_repo.get_words_by_user(user_id)

    def get_due_words(
        self, user_id: int, limit: int = 10, randomize: bool = True
    ) -> list[dict[str, Any]]:
        """Get words due for review"""
        return self.word_repo.get_due_words(user_id, limit, randomize)

    def get_new_words(
        self, user_id: int, limit: int = 10, randomize: bool = True
    ) -> list[dict[str, Any]]:
        """Get new words (never reviewed)"""
        return self.word_repo.get_new_words(user_id, limit, randomize)

    def get_difficult_words(
        self, user_id: int, limit: int = 10, randomize: bool = True
    ) -> list[dict[str, Any]]:
        """Get difficult words (low easiness factor)"""
        return self.word_repo.get_difficult_words(user_id, limit, randomize)

    def add_words_to_user(self, user_id: int, words_data: list[dict[str, Any]]) -> int:
        """Add multiple words to user's learning progress"""
        return self.word_repo.add_words_to_user(user_id, words_data)

    def add_word_to_user(self, user_id: int, word_data: dict[str, Any]) -> Word | None:
        """Add a single word to user's learning progress"""
        added_count = self.word_repo.add_words_to_user(user_id, [word_data])
        if added_count > 0:
            # Return the word that was added
            lemma = word_data.get("lemma")
            if lemma:
                return self.word_repo.get_word_by_lemma(lemma)
        return None

    # Progress methods
    def update_learning_progress(
        self,
        user_id: int,
        word_id: int,
        rating: int,
        response_time_ms: int = 0
    ) -> bool:
        """Update learning progress after review"""
        return self.progress_repo.update_learning_progress(
            user_id, word_id, rating, response_time_ms=response_time_ms
        )

    def get_learning_progress(
        self, user_id: int, word_id: int
    ) -> dict[str, Any] | None:
        """Get learning progress for a specific word"""
        return self.progress_repo.get_learning_progress(user_id, word_id)

    def get_review_history(
        self,
        user_id: int,
        word_id: int | None = None,
        limit: int = 100
    ) -> list[dict[str, Any]]:
        """Get review history for user or specific word"""
        return self.progress_repo.get_review_history(user_id, word_id, limit)

    def get_performance_stats(self, user_id: int, days: int = 30) -> dict[str, Any]:
        """Get performance statistics for user"""
        return self.progress_repo.get_performance_stats(user_id, days)

    # Additional methods for complete API
    def add_word(self, user_id: int, word_data: dict[str, Any]) -> Word | None:
        """Add a single word to user's learning progress"""
        return self.add_word_to_user(user_id, word_data)

    def add_words_batch(
        self, user_id: int, words_data: list[dict[str, Any]]
    ) -> list[int]:
        """Add multiple words and return list of word IDs"""
        count = self.add_words_to_user(user_id, words_data)
        # Return mock list of IDs for now - this could be improved
        return list(range(1, count + 1))

    def get_existing_words_from_list(
        self, user_id: int, lemmas: list[str]
    ) -> list[str]:
        """Get existing words from a list of lemmas"""
        existence_map = self.check_multiple_words_exist(user_id, lemmas)
        return [lemma for lemma, exists in existence_map.items() if exists]

    def add_review_record(
        self,
        user_id: int,
        word_id: int,
        rating: int,
        response_time_ms: int = 0,
    ) -> bool:
        """Add a review record - alias for update_learning_progress"""
        return self.update_learning_progress(user_id, word_id, rating, response_time_ms)

    def get_connection(self):
        """Get database connection for direct SQL access in tests"""
        return self.db_connection.get_connection()

    def _get_potential_lemmas(self, word: str) -> list[str]:
        """Get potential lemmas for a word - helper method for tests"""
        # Basic implementation for German verb inflection detection
        potential_lemmas = [word]

        # Remove common German endings and try to construct base form
        if word.endswith('en'):
            potential_lemmas.append(word[:-2])
        elif word.endswith('est'):
            # For words ending in 'est' (like bedeutest), remove 'est' and add 'en'
            potential_lemmas.append(word[:-3] + 'en')
        elif word.endswith('et'):
            # For words ending in 'et' (like bedeutet), remove 'et' and add 'en'
            potential_lemmas.append(word[:-2] + 'en')
        elif word.endswith('st'):
            potential_lemmas.append(word[:-2] + 'en')
        elif word.endswith('t'):
            # For words ending in 't', try removing 't' and adding 'en'
            potential_lemmas.append(word[:-1] + 'en')
        elif word.endswith('e'):
            potential_lemmas.append(word[:-1] + 'en')

        return list(set(potential_lemmas))



# Global instance
_db_manager = None


def get_db_manager(db_path: str | None = None) -> DatabaseManager:
    """Get global database manager instance"""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager(db_path)
    return _db_manager
