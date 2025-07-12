"""
Word repository for database operations
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime

from ..connection import DatabaseConnection
from ..models import Word, LearningProgress, ReviewHistory

logger = logging.getLogger(__name__)


class WordRepository:
    """Repository for word-related database operations"""

    def __init__(self, db_connection: DatabaseConnection):
        self.db_connection = db_connection

    def create_word(self, word_data: Dict[str, Any]) -> Optional[Word]:
        """Create a new word"""
        try:
            with self.db_connection.get_connection() as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO words (lemma, part_of_speech, article, translation, example, additional_forms, confidence)
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

    def get_word_by_id(self, word_id: int) -> Optional[Word]:
        """Get word by ID"""
        try:
            with self.db_connection.get_connection() as conn:
                cursor = conn.execute(
                    "SELECT * FROM words WHERE id = ?",
                    (word_id,)
                )
                row = cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Error getting word by ID: {e}")
            return None

    def get_word_by_lemma(self, lemma: str) -> Optional[Word]:
        """Get word by lemma"""
        try:
            with self.db_connection.get_connection() as conn:
                cursor = conn.execute(
                    "SELECT * FROM words WHERE lemma = ?",
                    (lemma,)
                )
                row = cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Error getting word by lemma: {e}")
            return None

    def check_word_exists(self, user_id: int, lemma: str) -> bool:
        """Check if word exists in user's learning progress"""
        try:
            with self.db_connection.get_connection() as conn:
                cursor = conn.execute(
                    """
                    SELECT 1 FROM learning_progress lp
                    JOIN words w ON lp.word_id = w.id
                    WHERE lp.user_id = ? AND LOWER(w.lemma) = LOWER(?)
                    """,
                    (user_id, lemma)
                )
                return cursor.fetchone() is not None
        except Exception as e:
            logger.error(f"Error checking word existence: {e}")
            return False

    def check_multiple_words_exist(self, user_id: int, lemmas: List[str]) -> Dict[str, bool]:
        """Check existence of multiple words at once"""
        try:
            with self.db_connection.get_connection() as conn:
                # Create placeholders for the IN clause
                placeholders = ",".join("?" for _ in lemmas)
                
                cursor = conn.execute(
                    f"""
                    SELECT w.lemma FROM learning_progress lp
                    JOIN words w ON lp.word_id = w.id
                    WHERE lp.user_id = ? AND LOWER(w.lemma) IN ({placeholders})
                    """,
                    [user_id] + [lemma.lower() for lemma in lemmas]
                )
                
                existing_lemmas = {row["lemma"].lower() for row in cursor.fetchall()}
                result = {lemma: lemma.lower() in existing_lemmas for lemma in lemmas}
                return result
        except Exception as e:
            logger.error(f"Error checking multiple words existence: {e}")
            return {lemma: False for lemma in lemmas}

    def get_words_by_user(self, user_id: int) -> List[Dict[str, Any]]:
        """Get all words for a user with learning progress"""
        try:
            with self.db_connection.get_connection() as conn:
                cursor = conn.execute(
                    """
                    SELECT w.*, lp.repetitions, lp.easiness_factor, lp.interval_days,
                           lp.next_review_date, lp.last_reviewed
                    FROM words w
                    JOIN learning_progress lp ON w.id = lp.word_id
                    WHERE lp.user_id = ?
                    ORDER BY lp.created_at DESC
                    """,
                    (user_id,)
                )
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error getting words by user: {e}")
            return []

    def get_due_words(self, user_id: int, limit: int = 10, randomize: bool = True) -> List[Dict[str, Any]]:
        """Get words due for review"""
        try:
            with self.db_connection.get_connection() as conn:
                # Choose ordering based on randomize parameter
                order_clause = "ORDER BY RANDOM()" if randomize else "ORDER BY lp.next_review_date ASC"
                
                cursor = conn.execute(
                    f"""
                    SELECT w.*, lp.repetitions, lp.easiness_factor, lp.interval_days,
                           lp.next_review_date, lp.last_reviewed
                    FROM words w
                    JOIN learning_progress lp ON w.id = lp.word_id
                    WHERE lp.user_id = ? AND lp.next_review_date <= datetime('now')
                    {order_clause}
                    LIMIT ?
                    """,
                    (user_id, limit)
                )
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error getting due words: {e}")
            return []

    def get_new_words(self, user_id: int, limit: int = 10, randomize: bool = True) -> List[Dict[str, Any]]:
        """Get new words (never reviewed)"""
        try:
            with self.db_connection.get_connection() as conn:
                # Choose ordering based on randomize parameter
                order_clause = "ORDER BY RANDOM()" if randomize else "ORDER BY lp.created_at ASC"
                
                cursor = conn.execute(
                    f"""
                    SELECT w.*, lp.repetitions, lp.easiness_factor, lp.interval_days,
                           lp.next_review_date, lp.last_reviewed
                    FROM words w
                    JOIN learning_progress lp ON w.id = lp.word_id
                    WHERE lp.user_id = ? AND lp.repetitions = 0
                    {order_clause}
                    LIMIT ?
                    """,
                    (user_id, limit)
                )
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error getting new words: {e}")
            return []

    def get_difficult_words(self, user_id: int, limit: int = 10, randomize: bool = True) -> List[Dict[str, Any]]:
        """Get difficult words (low easiness factor)"""
        try:
            with self.db_connection.get_connection() as conn:
                # Choose ordering based on randomize parameter
                order_clause = "ORDER BY RANDOM()" if randomize else "ORDER BY lp.easiness_factor ASC"
                
                cursor = conn.execute(
                    f"""
                    SELECT w.*, lp.repetitions, lp.easiness_factor, lp.interval_days,
                           lp.next_review_date, lp.last_reviewed
                    FROM words w
                    JOIN learning_progress lp ON w.id = lp.word_id
                    WHERE lp.user_id = ? AND lp.easiness_factor < 2.0 AND lp.repetitions > 0
                    {order_clause}
                    LIMIT ?
                    """,
                    (user_id, limit)
                )
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error getting difficult words: {e}")
            return []

    def add_words_to_user(self, user_id: int, words_data: List[Dict[str, Any]]) -> int:
        """Add multiple words to user's learning progress"""
        added_count = 0
        
        logger.info(f"Starting to add {len(words_data)} words to user {user_id}")
        for i, word_data in enumerate(words_data):
            logger.info(f"Word {i+1}/{len(words_data)}: '{word_data.get('lemma')}' - '{word_data.get('translation')}'")
        
        try:
            with self.db_connection.get_connection() as conn:
                for word_data in words_data:
                    try:
                        lemma = word_data.get("lemma")
                        translation = word_data.get("translation", "")
                        
                                # Validate translation before processing
                        if not self._is_valid_translation(translation):
                            logger.warning(f"SKIP REASON 1: Word '{lemma}' has invalid translation: '{translation}'")
                            continue
                        
                        # Check if word already exists in shared table (case-insensitive)
                        cursor = conn.execute(
                            "SELECT id FROM words WHERE LOWER(lemma) = LOWER(?)",
                            (lemma,)
                        )
                        existing_word = cursor.fetchone()
                        
                        if existing_word:
                            word_id = existing_word["id"]
                            logger.debug(f"Word '{lemma}' already exists in words table with id {word_id}")
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
                            logger.debug(f"Created new word '{lemma}' with id {word_id}")
                        
                        # Check if user already has this word
                        cursor = conn.execute(
                            "SELECT 1 FROM learning_progress WHERE user_id = ? AND word_id = ?",
                            (user_id, word_id)
                        )
                        
                        existing_progress = cursor.fetchone()
                        if not existing_progress:
                            # Add to user's learning progress
                            logger.debug(f"Adding '{lemma}' to learning progress for user {user_id}")
                            cursor = conn.execute(
                                """
                                INSERT INTO learning_progress (user_id, word_id, repetitions, easiness_factor, interval_days, next_review_date)
                                VALUES (?, ?, 0, 2.5, 1, datetime('now'))
                                """,
                                (user_id, word_id)
                            )
                            added_count += 1
                            logger.info(f"SUCCESS: Added '{lemma}' to user {user_id}'s learning progress")
                        else:
                            logger.warning(f"SKIP REASON 2: Word '{lemma}' already exists in learning progress for user {user_id}")
                            
                    except Exception as e:
                        logger.error(f"Error adding word {word_data.get('lemma', 'unknown')}: {e}")
                        continue
                
                conn.commit()
                
        except Exception as e:
            logger.error(f"Error adding words to user: {e}")
        
        logger.info(f"FINAL RESULT: Successfully added {added_count} out of {len(words_data)} words to user {user_id}")
        if added_count < len(words_data):
            skipped = len(words_data) - added_count
            logger.warning(f"SUMMARY: {skipped} words were skipped during addition process")
            
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
            "failed"
        ]
        
        translation_lower = translation.lower().strip()
        return not any(pattern in translation_lower for pattern in invalid_patterns)