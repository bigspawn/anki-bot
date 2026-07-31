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
                        example, additional_forms, confidence, level
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        word_data.get("lemma"),
                        word_data.get("part_of_speech"),
                        word_data.get("article"),
                        word_data.get("translation"),
                        word_data.get("example"),
                        word_data.get("additional_forms"),
                        word_data.get("confidence", 1.0),
                        word_data.get("level"),
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

    def get_verb_words(
        self, telegram_id: int, limit: int = 10, randomize: bool = True
    ) -> list[dict[str, Any]]:
        """Get verb words for study"""
        try:
            with self.db_connection.get_connection() as conn:
                order_clause = (
                    "ORDER BY RANDOM()" if randomize else "ORDER BY lp.created_at ASC"
                )

                cursor = conn.execute(
                    f"""
                    SELECT w.*, lp.repetitions, lp.easiness_factor, lp.interval_days,
                           lp.next_review_date, lp.last_reviewed
                    FROM words w
                    JOIN learning_progress lp ON w.id = lp.word_id
                    WHERE lp.telegram_id = ? AND w.part_of_speech = 'verb'
                    {order_clause}
                    LIMIT ?
                    """,  # noqa: S608  # Safe: order_clause is from predefined strings
                    (telegram_id, limit),
                )
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error getting verb words: {e}")
            return []

    def get_reflexive_verbs(
        self, telegram_id: int, limit: int = 10, randomize: bool = True
    ) -> list[dict[str, Any]]:
        """Get reflexive verbs ('sich ...') for study"""
        return self._get_words_where(
            telegram_id,
            "(LOWER(w.lemma) LIKE 'sich %' "
            "OR LOWER(w.part_of_speech) LIKE '%reflexive%')",
            limit,
            randomize,
            "reflexive verbs",
        )

    def get_preposition_verbs(
        self, telegram_id: int, limit: int = 10, randomize: bool = True
    ) -> list[dict[str, Any]]:
        """Get verbs governing a preposition ('denken an + Akk') for study"""
        return self._get_words_where(
            telegram_id,
            "LOWER(w.part_of_speech) LIKE '%preposition%' "
            "AND LOWER(w.part_of_speech) LIKE '%verb%'",
            limit,
            randomize,
            "preposition verbs",
        )

    def _get_words_where(
        self,
        telegram_id: int,
        condition: str,
        limit: int,
        randomize: bool,
        what: str,
    ) -> list[dict[str, Any]]:
        """Run a study query with a caller-supplied literal WHERE condition"""
        try:
            with self.db_connection.get_connection() as conn:
                order_clause = (
                    "ORDER BY RANDOM()" if randomize else "ORDER BY lp.created_at ASC"
                )

                cursor = conn.execute(
                    f"""
                    SELECT w.*, lp.repetitions, lp.easiness_factor, lp.interval_days,
                           lp.next_review_date, lp.last_reviewed
                    FROM words w
                    JOIN learning_progress lp ON w.id = lp.word_id
                    WHERE lp.telegram_id = ? AND {condition}
                    {order_clause}
                    LIMIT ?
                    """,  # noqa: S608  # Safe: condition/order_clause are literals
                    (telegram_id, limit),
                )
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error getting {what}: {e}")
            return []

    def get_words_by_part_of_speech(
        self,
        telegram_id: int,
        part_of_speech: str,
        limit: int = 10,
        randomize: bool = True,
    ) -> list[dict[str, Any]]:
        """Get words filtered by part of speech (prefix match, e.g. 'noun' also
        matches 'noun (informal)') for study"""
        try:
            with self.db_connection.get_connection() as conn:
                order_clause = (
                    "ORDER BY RANDOM()" if randomize else "ORDER BY lp.created_at ASC"
                )

                cursor = conn.execute(
                    f"""
                    SELECT w.*, lp.repetitions, lp.easiness_factor, lp.interval_days,
                           lp.next_review_date, lp.last_reviewed
                    FROM words w
                    JOIN learning_progress lp ON w.id = lp.word_id
                    WHERE lp.telegram_id = ? AND LOWER(w.part_of_speech) LIKE LOWER(?) || '%'
                    {order_clause}
                    LIMIT ?
                    """,  # noqa: S608  # Safe: order_clause is from predefined strings
                    (telegram_id, part_of_speech, limit),
                )
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error getting words by part of speech: {e}")
            return []

    def get_words_by_level(
        self,
        telegram_id: int,
        level: str,
        limit: int = 10,
        randomize: bool = True,
    ) -> list[dict[str, Any]]:
        """Get words filtered by CEFR level (A1-C2) for study"""
        try:
            with self.db_connection.get_connection() as conn:
                order_clause = (
                    "ORDER BY RANDOM()" if randomize else "ORDER BY lp.created_at ASC"
                )

                cursor = conn.execute(
                    f"""
                    SELECT w.*, lp.repetitions, lp.easiness_factor, lp.interval_days,
                           lp.next_review_date, lp.last_reviewed
                    FROM words w
                    JOIN learning_progress lp ON w.id = lp.word_id
                    WHERE lp.telegram_id = ? AND UPPER(w.level) = UPPER(?)
                    {order_clause}
                    LIMIT ?
                    """,  # noqa: S608  # Safe: order_clause is from predefined strings
                    (telegram_id, level, limit),
                )
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error getting words by level: {e}")
            return []

    def get_words_by_lemma_set(
        self,
        telegram_id: int,
        lemmas: list[str],
        limit: int = 10,
        randomize: bool = True,
    ) -> list[dict[str, Any]]:
        """Get user's words whose lemma (case-insensitive) is in a given set,
        e.g. a curated list of common verbs, for study"""
        if not lemmas:
            return []
        try:
            with self.db_connection.get_connection() as conn:
                order_clause = (
                    "ORDER BY RANDOM()" if randomize else "ORDER BY lp.created_at ASC"
                )
                placeholders = ",".join("?" for _ in lemmas)

                cursor = conn.execute(
                    f"""
                    SELECT w.*, lp.repetitions, lp.easiness_factor, lp.interval_days,
                           lp.next_review_date, lp.last_reviewed
                    FROM words w
                    JOIN learning_progress lp ON w.id = lp.word_id
                    WHERE lp.telegram_id = ? AND LOWER(w.lemma) IN ({placeholders})
                    {order_clause}
                    LIMIT ?
                    """,  # noqa: S608  # Safe: placeholders contains only ? chars
                    [telegram_id] + [lemma.lower() for lemma in lemmas] + [limit],
                )
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error getting words by lemma set: {e}")
            return []

    def get_recent_words(
        self, telegram_id: int, limit: int = 10
    ) -> list[dict[str, Any]]:
        """Get the most recently added words for study, regardless of SM2 due date"""
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
                    LIMIT ?
                    """,
                    (telegram_id, limit),
                )
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error getting recent words: {e}")
            return []

    def add_words_to_user(
        self, telegram_id: int, words_data: list[dict[str, Any]]
    ) -> int:
        """Add multiple words to user's learning progress"""
        return len(self.add_words_with_details(telegram_id, words_data)["added"])

    def add_words_with_details(
        self, telegram_id: int, words_data: list[dict[str, Any]]
    ) -> dict[str, list[str]]:
        """Add words and report per-lemma outcome.

        Callers need the duplicate lemmas: the caller-side existence check runs
        on surface forms, so a word can only be recognized as already learned
        after lemmatization.
        """
        added: list[str] = []
        duplicates: list[str] = []
        invalid: list[str] = []

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
                            invalid.append(str(lemma))
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
                                INSERT INTO words (lemma, part_of_speech, article, translation, example, additional_forms, confidence, level)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                                """,
                                (
                                    lemma,
                                    word_data.get("part_of_speech", "unknown"),
                                    word_data.get("article"),
                                    translation,
                                    word_data.get("example", ""),
                                    word_data.get("additional_forms"),
                                    word_data.get("confidence", 1.0),
                                    word_data.get("level"),
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
                            added.append(str(lemma))
                            logger.info(
                                f"SUCCESS: Added '{lemma}' to user {telegram_id}'s learning progress"
                            )
                        else:
                            duplicates.append(str(lemma))
                            logger.warning(
                                f"SKIP REASON 2: Word '{lemma}' already exists in learning progress for user {telegram_id}"
                            )

                    except Exception as e:
                        logger.error(
                            f"Error adding word {word_data.get('lemma', 'unknown')}: {e}"
                        )
                        # Counted as invalid, otherwise the word vanishes from
                        # every counter shown to the user
                        invalid.append(str(word_data.get("lemma")))
                        continue

                conn.commit()

        except Exception as e:
            logger.error(f"Error adding words to user: {e}")

        logger.info(
            f"FINAL RESULT: Successfully added {len(added)} out of {len(words_data)} words to user {telegram_id}"
        )
        if len(added) < len(words_data):
            logger.warning(
                f"SUMMARY: {len(duplicates)} duplicates, {len(invalid)} invalid "
                f"words were skipped during addition process"
            )

        return {"added": added, "duplicates": duplicates, "invalid": invalid}

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
                        WHERE lp.telegram_id = ? AND LOWER(w.lemma) = LOWER(?)
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
