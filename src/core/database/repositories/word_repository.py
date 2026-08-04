"""
Word repository for database operations
"""

import json
import logging
from typing import Any

from ..connection import DatabaseConnection
from ..models import Word

logger = logging.getLogger(__name__)

# Study queries are assembled here, at import time, from literal fragments:
# every statement below is a constant by the time anything runs, so no value
# a user can influence ever reaches the SQL text.
_SELECT_STUDY_WORDS = """
    SELECT w.*, lp.repetitions, lp.easiness_factor, lp.interval_days,
           lp.next_review_date, lp.last_reviewed
    FROM words w
    JOIN learning_progress lp ON w.id = lp.word_id
    WHERE lp.telegram_id = ? AND """

# Randomization is a bound flag rather than a swapped-in ORDER BY: when it is
# off every row ties on 0 and the tiebreaker below decides the order.
_ORDER_RANDOM_OR = """
    ORDER BY CASE WHEN ? = 1 THEN RANDOM() ELSE 0 END, """

_LIMIT = """
    LIMIT ?"""

_BY_CREATED = "lp.created_at ASC" + _LIMIT
_BY_DUE_DATE = "lp.next_review_date ASC" + _LIMIT
_BY_EASINESS = "lp.easiness_factor ASC" + _LIMIT

SQL_DUE_WORDS = (
    _SELECT_STUDY_WORDS
    + "datetime(lp.next_review_date) <= datetime('now', 'localtime')"
    + _ORDER_RANDOM_OR
    + _BY_DUE_DATE
)
SQL_NEW_WORDS = (
    _SELECT_STUDY_WORDS + "lp.repetitions = 0" + _ORDER_RANDOM_OR + _BY_CREATED
)
SQL_DIFFICULT_WORDS = (
    _SELECT_STUDY_WORDS
    + "lp.easiness_factor < 2.0 AND lp.repetitions > 0"
    + _ORDER_RANDOM_OR
    + _BY_EASINESS
)
SQL_VERB_WORDS = (
    _SELECT_STUDY_WORDS + "w.part_of_speech = 'verb'" + _ORDER_RANDOM_OR + _BY_CREATED
)
SQL_REFLEXIVE_VERBS = (
    _SELECT_STUDY_WORDS
    + "(LOWER(w.lemma) LIKE 'sich %' OR LOWER(w.part_of_speech) LIKE '%reflexive%')"
    + _ORDER_RANDOM_OR
    + _BY_CREATED
)
SQL_PREPOSITION_VERBS = (
    _SELECT_STUDY_WORDS
    + "LOWER(w.part_of_speech) LIKE '%preposition%'"
    + " AND LOWER(w.part_of_speech) LIKE '%verb%'"
    + _ORDER_RANDOM_OR
    + _BY_CREATED
)
SQL_CLOZE_WORDS = (
    _SELECT_STUDY_WORDS
    + "LOWER(w.part_of_speech) IN ('cloze', 'error fix')"
    + _ORDER_RANDOM_OR
    + _BY_CREATED
)
# Prefix match, so 'noun' also picks up 'noun (informal)'
SQL_WORDS_BY_PART_OF_SPEECH = (
    _SELECT_STUDY_WORDS
    + "LOWER(w.part_of_speech) LIKE LOWER(?) || '%'"
    + _ORDER_RANDOM_OR
    + _BY_CREATED
)
SQL_WORDS_BY_LEVEL = (
    _SELECT_STUDY_WORDS + "UPPER(w.level) = UPPER(?)" + _ORDER_RANDOM_OR + _BY_CREATED
)
SQL_WORDS_BY_TOPIC = (
    _SELECT_STUDY_WORDS
    + "json_valid(w.additional_forms)"
    + " AND LOWER(json_extract(w.additional_forms, '$.topic')) = LOWER(?)"
    + _ORDER_RANDOM_OR
    + _BY_CREATED
)
# Reflexive verbs annotated with the case of the reflexive pronoun. The bare
# verbs get that annotation by backfill, so matching on the stored case rather
# than on part_of_speech keeps them in the rubric alongside the drill cards.
_HAS_CASE = (
    "json_valid(w.additional_forms)"
    " AND json_extract(w.additional_forms, '$.case') IS NOT NULL"
)

SQL_REFLEXIVE_CASE = (
    _SELECT_STUDY_WORDS
    + _HAS_CASE
    + " AND (LOWER(w.lemma) LIKE 'sich %'"
    + " OR LOWER(w.part_of_speech) LIKE '%reflexive%')"
    # 'sich erinnern an' stores the case of the object after the preposition,
    # not of the reflexive pronoun — it belongs to /study_rektion instead
    + " AND LOWER(w.part_of_speech) NOT LIKE '%preposition%'"
    + _ORDER_RANDOM_OR
    + _BY_CREATED
)
SQL_PRONOUN_CASE = (
    _SELECT_STUDY_WORDS
    + "LOWER(w.part_of_speech) = 'pronoun case'"
    + _ORDER_RANDOM_OR
    + _BY_CREATED
)
SQL_ARTICLE_CASE = (
    _SELECT_STUDY_WORDS
    + "LOWER(w.part_of_speech) = 'article case'"
    + _ORDER_RANDOM_OR
    + _BY_CREATED
)
SQL_DATIV_VERBS = (
    _SELECT_STUDY_WORDS
    + _HAS_CASE
    + " AND json_extract(w.additional_forms, '$.topic') = 'dativ-verbs'"
    + _ORDER_RANDOM_OR
    + _BY_CREATED
)
SQL_DAT_AKK_VERBS = (
    _SELECT_STUDY_WORDS
    + _HAS_CASE
    + " AND json_extract(w.additional_forms, '$.topic') = 'dat-akk-verbs'"
    + _ORDER_RANDOM_OR
    + _BY_CREATED
)

# A JSON array carries the variable-length lemma set, so the statement itself
# stays fixed no matter how many lemmas are asked for.
_LEMMA_IN_JSON_ARRAY = "LOWER(w.lemma) IN (SELECT value FROM json_each(?))"

SQL_WORDS_BY_LEMMA_SET = (
    _SELECT_STUDY_WORDS + _LEMMA_IN_JSON_ARRAY + _ORDER_RANDOM_OR + _BY_CREATED
)


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
                cursor = conn.execute(
                    """
                    SELECT w.lemma FROM learning_progress lp
                    JOIN words w ON lp.word_id = w.id
                    WHERE lp.telegram_id = ?
                      AND LOWER(w.lemma) IN (SELECT value FROM json_each(?))
                    """,
                    (telegram_id, json.dumps([lemma.lower() for lemma in lemmas])),
                )

                existing_lemmas = {row["lemma"].lower() for row in cursor.fetchall()}
                result = {lemma: lemma.lower() in existing_lemmas for lemma in lemmas}
                return result
        except Exception as e:
            logger.error(f"Error checking multiple words existence: {e}")
            return dict.fromkeys(lemmas, False)

    def _fetch_study_words(
        self, sql: str, params: tuple, what: str
    ) -> list[dict[str, Any]]:
        """Run one of the module-level study statements"""
        try:
            with self.db_connection.get_connection() as conn:
                cursor = conn.execute(sql, params)
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error getting {what}: {e}")
            return []

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
        return self._fetch_study_words(
            SQL_DUE_WORDS, (telegram_id, int(randomize), limit), "due words"
        )

    def get_new_words(
        self, telegram_id: int, limit: int = 10, randomize: bool = True
    ) -> list[dict[str, Any]]:
        """Get new words (never reviewed)"""
        return self._fetch_study_words(
            SQL_NEW_WORDS, (telegram_id, int(randomize), limit), "new words"
        )

    def get_difficult_words(
        self, telegram_id: int, limit: int = 10, randomize: bool = True
    ) -> list[dict[str, Any]]:
        """Get difficult words (low easiness factor)"""
        return self._fetch_study_words(
            SQL_DIFFICULT_WORDS, (telegram_id, int(randomize), limit), "difficult words"
        )

    def get_verb_words(
        self, telegram_id: int, limit: int = 10, randomize: bool = True
    ) -> list[dict[str, Any]]:
        """Get verb words for study"""
        return self._fetch_study_words(
            SQL_VERB_WORDS, (telegram_id, int(randomize), limit), "verb words"
        )

    def get_reflexive_verbs(
        self, telegram_id: int, limit: int = 10, randomize: bool = True
    ) -> list[dict[str, Any]]:
        """Get reflexive verbs ('sich ...') for study"""
        return self._fetch_study_words(
            SQL_REFLEXIVE_VERBS, (telegram_id, int(randomize), limit), "reflexive verbs"
        )

    def get_preposition_verbs(
        self, telegram_id: int, limit: int = 10, randomize: bool = True
    ) -> list[dict[str, Any]]:
        """Get verbs governing a preposition ('denken an + Akk') for study"""
        return self._fetch_study_words(
            SQL_PREPOSITION_VERBS,
            (telegram_id, int(randomize), limit),
            "preposition verbs",
        )

    def get_cloze_words(
        self, telegram_id: int, limit: int = 10, randomize: bool = True
    ) -> list[dict[str, Any]]:
        """Get gap-fill and error-correction drills for study"""
        return self._fetch_study_words(
            SQL_CLOZE_WORDS, (telegram_id, int(randomize), limit), "cloze words"
        )

    def get_reflexive_case_words(
        self, telegram_id: int, limit: int = 10, randomize: bool = True
    ) -> list[dict[str, Any]]:
        """Get reflexive verbs whose pronoun case is recorded, for study"""
        return self._fetch_study_words(
            SQL_REFLEXIVE_CASE,
            (telegram_id, int(randomize), limit),
            "reflexive case words",
        )

    def get_pronoun_case_words(
        self, telegram_id: int, limit: int = 10, randomize: bool = True
    ) -> list[dict[str, Any]]:
        """Get personal and possessive pronoun declension cards for study"""
        return self._fetch_study_words(
            SQL_PRONOUN_CASE, (telegram_id, int(randomize), limit), "pronoun case words"
        )

    def get_article_case_words(
        self, telegram_id: int, limit: int = 10, randomize: bool = True
    ) -> list[dict[str, Any]]:
        """Get article declension cards for study"""
        return self._fetch_study_words(
            SQL_ARTICLE_CASE, (telegram_id, int(randomize), limit), "article case words"
        )

    def get_dativ_verbs(
        self, telegram_id: int, limit: int = 10, randomize: bool = True
    ) -> list[dict[str, Any]]:
        """Get verbs governing Dativ ('helfen', 'gefallen') for study"""
        return self._fetch_study_words(
            SQL_DATIV_VERBS, (telegram_id, int(randomize), limit), "dativ verbs"
        )

    def get_dat_akk_verbs(
        self, telegram_id: int, limit: int = 10, randomize: bool = True
    ) -> list[dict[str, Any]]:
        """Get verbs taking both a Dativ and an Akkusativ object for study"""
        return self._fetch_study_words(
            SQL_DAT_AKK_VERBS,
            (telegram_id, int(randomize), limit),
            "dativ+akkusativ verbs",
        )

    def get_words_by_topic(
        self, telegram_id: int, topic: str, limit: int = 10, randomize: bool = True
    ) -> list[dict[str, Any]]:
        """Get cards tagged with a topic slug, regardless of SM2 due date"""
        return self._fetch_study_words(
            SQL_WORDS_BY_TOPIC,
            (telegram_id, topic, int(randomize), limit),
            "words by topic",
        )

    def get_topic_slugs(self, telegram_id: int) -> list[str]:
        """Get every topic slug present in the user's cards, alphabetically"""
        try:
            with self.db_connection.get_connection() as conn:
                cursor = conn.execute(
                    """
                    SELECT DISTINCT json_extract(w.additional_forms, '$.topic') AS topic
                    FROM words w
                    JOIN learning_progress lp ON w.id = lp.word_id
                    WHERE lp.telegram_id = ?
                      AND json_valid(w.additional_forms)
                      AND json_extract(w.additional_forms, '$.topic') IS NOT NULL
                    ORDER BY topic
                    """,
                    (telegram_id,),
                )
                return [row["topic"] for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error getting topic slugs: {e}")
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
        return self._fetch_study_words(
            SQL_WORDS_BY_PART_OF_SPEECH,
            (telegram_id, part_of_speech, int(randomize), limit),
            "words by part of speech",
        )

    def get_words_by_level(
        self,
        telegram_id: int,
        level: str,
        limit: int = 10,
        randomize: bool = True,
    ) -> list[dict[str, Any]]:
        """Get words filtered by CEFR level (A1-C2) for study"""
        return self._fetch_study_words(
            SQL_WORDS_BY_LEVEL,
            (telegram_id, level, int(randomize), limit),
            "words by level",
        )

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

        return self._fetch_study_words(
            SQL_WORDS_BY_LEMMA_SET,
            (
                telegram_id,
                json.dumps([lemma.lower() for lemma in lemmas]),
                int(randomize),
                limit,
            ),
            "words by lemma set",
        )

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
