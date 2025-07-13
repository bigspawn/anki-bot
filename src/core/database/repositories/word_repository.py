"""
Word repository for database operations
"""

import logging
from typing import Any

from ..connection import DatabaseConnection
from ..models import Word

logger = logging.getLogger(__name__)


class WordRepository:
    """Repository for word-related database operations"""

    def __init__(self, db_connection: DatabaseConnection):
        self.db_connection = db_connection

    def create_word(self, word_data: dict[str, Any]) -> Word | None:
        """Create a new word"""
        try:
            with self.db_connection.get_connection() as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO words (
                        lemma, part_of_speech, article, translation,
                        example, additional_forms, confidence
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        word_data.get("lemma"),
                        word_data.get("part_of_speech"),
                        word_data.get("article"),
                        word_data.get("translation"),
                        word_data.get("example"),
                        word_data.get("additional_forms"),
                        word_data.get("confidence", 1.0),
                    ),
                )

                word_id = cursor.lastrowid
                conn.commit()

                # Return the created word
                return self.get_word_by_id(word_id)
        except Exception as e:
            logger.error(f"Error creating word: {e}")
            return None

    def get_word_by_id(self, word_id: int) -> Word | None:
        """Get word by ID"""
        try:
            with self.db_connection.get_connection() as conn:
                cursor = conn.execute("SELECT * FROM words WHERE id = ?", (word_id,))
                row = cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Error getting word by ID: {e}")
            return None

    def get_word_by_lemma(self, lemma: str) -> Word | None:
        """Get word by lemma"""
        try:
            with self.db_connection.get_connection() as conn:
                cursor = conn.execute("SELECT * FROM words WHERE lemma = ?", (lemma,))
                row = cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Error getting word by lemma: {e}")
            return None

    def check_word_exists(self, telegram_id: int, lemma: str) -> bool:
        """Check if word exists in user's learning progress"""
        try:
            with self.db_connection.get_connection() as conn:
                cursor = conn.execute(
                    """
                    SELECT 1 FROM learning_progress lp
                    JOIN words w ON lp.word_id = w.id
                    WHERE lp.telegram_id = ? AND LOWER(w.lemma) = LOWER(?)
                    """,
                    (telegram_id, lemma),
                )
                return cursor.fetchone() is not None
        except Exception as e:
            logger.error(f"Error checking word existence: {e}")
            return False

    def check_multiple_words_exist(
        self, telegram_id: int, lemmas: list[str]
    ) -> dict[str, bool]:
        """Check existence of multiple words at once"""
        try:
            with self.db_connection.get_connection() as conn:
                # Create placeholders for the IN clause
                placeholders = ",".join("?" for _ in lemmas)

                cursor = conn.execute(
                    f"""
                    SELECT w.lemma FROM learning_progress lp
                    JOIN words w ON lp.word_id = w.id
                    WHERE lp.telegram_id = ? AND LOWER(w.lemma) IN ({placeholders})
                    """,  # noqa: S608  # Safe: placeholders contains only ? chars
                    [telegram_id] + [lemma.lower() for lemma in lemmas],
                )

                existing_lemmas = {row["lemma"].lower() for row in cursor.fetchall()}
                result = {lemma: lemma.lower() in existing_lemmas for lemma in lemmas}
                return result
        except Exception as e:
            logger.error(f"Error checking multiple words existence: {e}")
            return dict.fromkeys(lemmas, False)

    def get_words_by_user(self, telegram_id: int) -> list[dict[str, Any]]:
        """Get all words for a user with learning progress"""
        try:
            with self.db_connection.get_connection() as conn:
                cursor = conn.execute(
                    """
                    SELECT w.*, lp.repetitions, lp.easiness_factor, lp.interval_days,
                           lp.next_review_date, lp.last_reviewed
                    FROM words w
                    JOIN learning_progress lp ON w.id = lp.word_id
                    WHERE lp.telegram_id = ?
                    ORDER BY lp.created_at DESC
                    """,
                    (telegram_id,),
                )
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error getting words by user: {e}")
            return []

    def get_due_words(
        self, telegram_id: int, limit: int = 10, randomize: bool = True
    ) -> list[dict[str, Any]]:
        """Get words due for review"""
        try:
            with self.db_connection.get_connection() as conn:
                # Choose ordering based on randomize parameter
                order_clause = (
                    "ORDER BY RANDOM()"
                    if randomize
                    else "ORDER BY lp.next_review_date ASC"
                )

                cursor = conn.execute(
                    f"""
                    SELECT w.*, lp.repetitions, lp.easiness_factor, lp.interval_days,
                           lp.next_review_date, lp.last_reviewed
                    FROM words w
                    JOIN learning_progress lp ON w.id = lp.word_id
                    WHERE lp.telegram_id = ? AND datetime(lp.next_review_date) <= datetime('now', 'localtime')
                    {order_clause}
                    LIMIT ?
                    """,  # noqa: S608  # Safe: order_clause is from predefined strings
                    (telegram_id, limit),
                )
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error getting due words: {e}")
            return []

    def get_new_words(
        self, telegram_id: int, limit: int = 10, randomize: bool = True
    ) -> list[dict[str, Any]]:
        """Get new words (never reviewed)"""
        try:
            with self.db_connection.get_connection() as conn:
                # Choose ordering based on randomize parameter
                order_clause = (
                    "ORDER BY RANDOM()" if randomize else "ORDER BY lp.created_at ASC"
                )

                cursor = conn.execute(
                    f"""
                    SELECT w.*, lp.repetitions, lp.easiness_factor, lp.interval_days,
                           lp.next_review_date, lp.last_reviewed
                    FROM words w
                    JOIN learning_progress lp ON w.id = lp.word_id
                    WHERE lp.telegram_id = ? AND lp.repetitions = 0
                    {order_clause}
                    LIMIT ?
                    """,  # noqa: S608  # Safe: order_clause is from predefined strings
                    (telegram_id, limit),
                )
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error getting new words: {e}")
            return []

    def get_difficult_words(
        self, telegram_id: int, limit: int = 10, randomize: bool = True
    ) -> list[dict[str, Any]]:
        """Get difficult words (low easiness factor)"""
        try:
            with self.db_connection.get_connection() as conn:
                # Choose ordering based on randomize parameter
                order_clause = (
                    "ORDER BY RANDOM()"
                    if randomize
                    else "ORDER BY lp.easiness_factor ASC"
                )

                cursor = conn.execute(
                    f"""
                    SELECT w.*, lp.repetitions, lp.easiness_factor, lp.interval_days,
                           lp.next_review_date, lp.last_reviewed
                    FROM words w
                    JOIN learning_progress lp ON w.id = lp.word_id
                    WHERE lp.telegram_id = ? AND lp.easiness_factor < 2.0 AND lp.repetitions > 0
                    {order_clause}
                    LIMIT ?
                    """,  # noqa: S608  # Safe: order_clause is from predefined strings
                    (telegram_id, limit),
                )
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error getting difficult words: {e}")
            return []

    def add_words_to_user(
        self, telegram_id: int, words_data: list[dict[str, Any]]
    ) -> int:
        """Add multiple words to user's learning progress"""
        added_count = 0

        logger.info(f"Starting to add {len(words_data)} words to user {telegram_id}")
        for i, word_data in enumerate(words_data):
            logger.info(
                f"Word {i + 1}/{len(words_data)}: '{word_data.get('lemma')}' - '{word_data.get('translation')}'"
            )

        try:
            with self.db_connection.get_connection() as conn:
                for word_data in words_data:
                    try:
                        lemma = word_data.get("lemma")
                        translation = word_data.get("translation", "")

                        # Validate translation before processing
                        if not self._is_valid_translation(translation):
                            logger.warning(
                                f"SKIP REASON 1: Word '{lemma}' has invalid translation: '{translation}'"
                            )
                            continue

                        # Check if word already exists in shared table (case-insensitive)
                        cursor = conn.execute(
                            "SELECT id FROM words WHERE LOWER(lemma) = LOWER(?)",
                            (lemma,),
                        )
                        existing_word = cursor.fetchone()

                        if existing_word:
                            word_id = existing_word["id"]
                            logger.debug(
                                f"Word '{lemma}' already exists in words table with id {word_id}"
                            )
                        else:
                            # Create new word
                            logger.debug(f"Creating new word entry for '{lemma}'")
                            cursor = conn.execute(
                                """
                                INSERT INTO words (lemma, part_of_speech, article, translation, example, additional_forms, confidence)
                                VALUES (?, ?, ?, ?, ?, ?, ?)
                                """,
                                (
                                    lemma,
                                    word_data.get("part_of_speech", "unknown"),
                                    word_data.get("article"),
                                    translation,
                                    word_data.get("example", ""),
                                    word_data.get("additional_forms"),
                                    word_data.get("confidence", 1.0),
                                ),
                            )
                            word_id = cursor.lastrowid
                            logger.debug(
                                f"Created new word '{lemma}' with id {word_id}"
                            )

                        # Check if user already has this word
                        cursor = conn.execute(
                            "SELECT 1 FROM learning_progress WHERE telegram_id = ? AND word_id = ?",
                            (telegram_id, word_id),
                        )

                        existing_progress = cursor.fetchone()
                        if not existing_progress:
                            # Add to user's learning progress
                            logger.debug(
                                f"Adding '{lemma}' to learning progress for user {telegram_id}"
                            )
                            cursor = conn.execute(
                                """
                                INSERT INTO learning_progress (telegram_id, word_id, repetitions, easiness_factor, interval_days, next_review_date)
                                VALUES (?, ?, 0, 2.5, 1, datetime('now'))
                                """,
                                (telegram_id, word_id),
                            )
                            added_count += 1
                            logger.info(
                                f"SUCCESS: Added '{lemma}' to user {telegram_id}'s learning progress"
                            )
                        else:
                            logger.warning(
                                f"SKIP REASON 2: Word '{lemma}' already exists in learning progress for user {telegram_id}"
                            )

                    except Exception as e:
                        logger.error(
                            f"Error adding word {word_data.get('lemma', 'unknown')}: {e}"
                        )
                        continue

                conn.commit()

        except Exception as e:
            logger.error(f"Error adding words to user: {e}")

        logger.info(
            f"FINAL RESULT: Successfully added {added_count} out of {len(words_data)} words to user {telegram_id}"
        )
        if added_count < len(words_data):
            skipped = len(words_data) - added_count
            logger.warning(
                f"SUMMARY: {skipped} words were skipped during addition process"
            )

        return added_count

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
            "failed",
        ]

        translation_lower = translation.lower().strip()
        return not any(pattern in translation_lower for pattern in invalid_patterns)

    def get_existing_words_details(
        self, telegram_id: int, lemmas: list[str]
    ) -> list[dict[str, Any]]:
        """Get word details for existing words by lemmas"""
        if not lemmas:
            return []

        try:
            with self.db_connection.get_connection() as conn:
                # Use multiple separate queries to avoid dynamic SQL construction
                results = []
                for lemma in lemmas:
                    cursor = conn.execute(
                        """
                        SELECT w.lemma, w.part_of_speech, w.article, w.translation, w.example, w.additional_forms
                        FROM words w
                        JOIN learning_progress lp ON w.id = lp.word_id
                        WHERE lp.telegram_id = ? AND w.lemma = ?
                        """,
                        (telegram_id, lemma),
                    )

                    row = cursor.fetchone()
                    if row:
                        results.append(dict(row))

                # Sort by lemma to maintain consistent ordering
                return sorted(results, key=lambda x: x["lemma"])

        except Exception as e:
            logger.error(f"Error getting existing words details: {e}")
            return []
