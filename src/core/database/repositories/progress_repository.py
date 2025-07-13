"""
Progress repository for learning progress and review history operations
"""

import logging
from datetime import datetime
from typing import Any

from ..connection import DatabaseConnection
from ..models import LearningProgress, ReviewHistory

logger = logging.getLogger(__name__)


class ProgressRepository:
    """Repository for learning progress and review history operations"""

    def __init__(self, db_connection: DatabaseConnection):
        self.db_connection = db_connection

    def update_learning_progress(
        self,
        telegram_id: int,
        word_id: int,
        rating: int,
        new_interval: int | None = None,
        new_easiness: float | None = None,
        response_time_ms: int = 0,
    ) -> bool:
        """Update learning progress after review"""
        try:
            with self.db_connection.get_connection() as conn:
                # Get current progress
                cursor = conn.execute(
                    """
                    SELECT repetitions, easiness_factor, interval_days
                    FROM learning_progress
                    WHERE telegram_id = ? AND word_id = ?
                    """,
                    (telegram_id, word_id),
                )

                current = cursor.fetchone()
                if not current:
                    logger.info(
                        f"No learning progress found for telegram_id {telegram_id}, word {word_id}. "
                        "Creating initial record."
                    )
                    # Set initial values for calculation
                    current = {
                        "repetitions": 0,
                        "easiness_factor": 2.5,
                        "interval_days": 1,
                    }

                    # Create initial learning progress record with calculated values
                    # We'll calculate the new values first, then insert them directly
                    from ....spaced_repetition import get_srs_system

                    srs = get_srs_system()
                    result = srs.calculate_review(
                        rating,
                        current["repetitions"],
                        current["interval_days"],
                        current["easiness_factor"],
                    )

                    # Calculate next review date
                    next_review_date = datetime.now()
                    if result.new_interval > 0:
                        from datetime import timedelta

                        next_review_date = datetime.now() + timedelta(
                            days=result.new_interval
                        )

                    cursor = conn.execute(
                        """
                        INSERT INTO learning_progress (
                            telegram_id, word_id, repetitions, easiness_factor,
                            interval_days, next_review_date, last_reviewed, created_at, updated_at
                        )
                        VALUES (?, ?, 1, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            telegram_id,
                            word_id,
                            result.new_easiness_factor,
                            result.new_interval,
                            next_review_date,
                            datetime.now(),
                            datetime.now(),
                            datetime.now(),
                        ),
                    )

                    # Add to review history
                    cursor = conn.execute(
                        """
                        INSERT INTO review_history (telegram_id, word_id, rating, response_time_ms, reviewed_at)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            telegram_id,
                            word_id,
                            rating,
                            response_time_ms,
                            datetime.now(),
                        ),
                    )

                    conn.commit()
                    return True
                else:
                    # Convert row to dict for consistent access
                    current = dict(current)

                # Calculate new values if not provided
                if new_interval is None or new_easiness is None:
                    from ....spaced_repetition import get_srs_system

                    srs = get_srs_system()
                    result = srs.calculate_review(
                        rating,
                        current["repetitions"],
                        current["interval_days"],
                        current["easiness_factor"],
                    )
                    new_interval = result.new_interval
                    new_easiness = result.new_easiness_factor

                # Update learning progress
                next_review_date = datetime.now()
                if new_interval > 0:
                    from datetime import timedelta

                    next_review_date = datetime.now() + timedelta(days=new_interval)

                cursor = conn.execute(
                    """
                    UPDATE learning_progress
                    SET repetitions = repetitions + 1,
                        easiness_factor = ?,
                        interval_days = ?,
                        next_review_date = ?,
                        last_reviewed = ?,
                        updated_at = ?
                    WHERE telegram_id = ? AND word_id = ?
                    """,
                    (
                        new_easiness,
                        new_interval,
                        next_review_date,
                        datetime.now(),
                        datetime.now(),
                        telegram_id,
                        word_id,
                    ),
                )

                # Add to review history
                cursor = conn.execute(
                    """
                    INSERT INTO review_history (telegram_id, word_id, rating, response_time_ms, reviewed_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (telegram_id, word_id, rating, response_time_ms, datetime.now()),
                )

                conn.commit()
                return True

        except Exception as e:
            logger.error(f"Error updating learning progress: {e}")
            return False

    def get_learning_progress(
        self, telegram_id: int, word_id: int
    ) -> LearningProgress | None:
        """Get learning progress for a specific word"""
        try:
            with self.db_connection.get_connection() as conn:
                cursor = conn.execute(
                    """
                    SELECT * FROM learning_progress
                    WHERE telegram_id = ? AND word_id = ?
                    """,
                    (telegram_id, word_id),
                )
                row = cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Error getting learning progress: {e}")
            return None

    def get_review_history(
        self, telegram_id: int, word_id: int | None = None, limit: int = 100
    ) -> list[ReviewHistory]:
        """Get review history for user or specific word"""
        try:
            with self.db_connection.get_connection() as conn:
                if word_id:
                    cursor = conn.execute(
                        """
                        SELECT * FROM review_history
                        WHERE telegram_id = ? AND word_id = ?
                        ORDER BY reviewed_at DESC
                        LIMIT ?
                        """,
                        (telegram_id, word_id, limit),
                    )
                else:
                    cursor = conn.execute(
                        """
                        SELECT * FROM review_history
                        WHERE telegram_id = ?
                        ORDER BY reviewed_at DESC
                        LIMIT ?
                        """,
                        (telegram_id, limit),
                    )

                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error getting review history: {e}")
            return []

    def get_recent_reviews(
        self, telegram_id: int, days: int = 7
    ) -> list[dict[str, Any]]:
        """Get recent reviews with word information"""
        try:
            with self.db_connection.get_connection() as conn:
                cursor = conn.execute(
                    f"""
                    SELECT rh.*, w.lemma, w.translation
                    FROM review_history rh
                    JOIN words w ON rh.word_id = w.id
                    WHERE rh.telegram_id = ? AND rh.reviewed_at >= datetime('now', '-{days} days')
                    ORDER BY rh.reviewed_at DESC
                    """,  # noqa: S608  # Safe: days is int parameter
                    (telegram_id,),
                )
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error getting recent reviews: {e}")
            return []

    def get_performance_stats(self, telegram_id: int, days: int = 30) -> dict[str, Any]:
        """Get performance statistics for user"""
        try:
            with self.db_connection.get_connection() as conn:
                cursor = conn.execute(
                    f"""
                    SELECT
                        COUNT(*) as total_reviews,
                        AVG(rating) as avg_rating,
                        SUM(CASE WHEN rating >= 3 THEN 1 ELSE 0 END) as good_reviews,
                        AVG(response_time_ms) as avg_response_time
                    FROM review_history
                    WHERE telegram_id = ? AND reviewed_at >= datetime('now', '-{days} days')
                    """,  # noqa: S608  # Safe: days is int parameter
                    (telegram_id,),
                )

                row = cursor.fetchone()
                if not row:
                    return {
                        "total_reviews": 0,
                        "avg_rating": 0.0,
                        "accuracy": 0.0,
                        "avg_response_time": 0.0,
                    }

                stats = dict(row)
                stats["accuracy"] = (
                    (stats["good_reviews"] / stats["total_reviews"] * 100)
                    if stats["total_reviews"] > 0
                    else 0.0
                )

                return stats
        except Exception as e:
            logger.error(f"Error getting performance stats: {e}")
            return {
                "total_reviews": 0,
                "avg_rating": 0.0,
                "accuracy": 0.0,
                "avg_response_time": 0.0,
            }

    def reset_word_progress(self, telegram_id: int, word_id: int) -> bool:
        """Reset learning progress for a specific word"""
        try:
            with self.db_connection.get_connection() as conn:
                cursor = conn.execute(
                    """
                    UPDATE learning_progress
                    SET repetitions = 0,
                        easiness_factor = 2.5,
                        interval_days = 1,
                        next_review_date = ?,
                        last_reviewed = NULL,
                        updated_at = ?
                    WHERE telegram_id = ? AND word_id = ?
                    """,
                    (datetime.now(), datetime.now(), telegram_id, word_id),
                )

                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error resetting word progress: {e}")
            return False

    def create_learning_progress(self, telegram_id: int, word_id: int) -> bool:
        """Create initial learning progress record for a word"""
        try:
            with self.db_connection.get_connection() as conn:
                # Check if already exists
                cursor = conn.execute(
                    "SELECT 1 FROM learning_progress WHERE telegram_id = ? AND word_id = ?",
                    (telegram_id, word_id),
                )
                if cursor.fetchone():
                    logger.debug(
                        f"Learning progress already exists for telegram_id {telegram_id}, word {word_id}"
                    )
                    return True

                # Create new record
                cursor = conn.execute(
                    """
                    INSERT INTO learning_progress (telegram_id, word_id, repetitions, easiness_factor, interval_days, next_review_date)
                    VALUES (?, ?, 0, 2.5, 1, ?)
                    """,
                    (telegram_id, word_id, datetime.now()),
                )

                conn.commit()
                logger.info(
                    f"Created learning progress for telegram_id {telegram_id}, word {word_id}"
                )
                return True
        except Exception as e:
            logger.error(f"Error creating learning progress: {e}")
            return False

    def delete_word_progress(self, telegram_id: int, word_id: int) -> bool:
        """Delete learning progress and review history for a word"""
        try:
            with self.db_connection.get_connection() as conn:
                # Delete review history first (due to foreign key constraints)
                conn.execute(
                    "DELETE FROM review_history WHERE telegram_id = ? AND word_id = ?",
                    (telegram_id, word_id),
                )

                # Delete learning progress
                cursor = conn.execute(
                    "DELETE FROM learning_progress WHERE telegram_id = ? AND word_id = ?",
                    (telegram_id, word_id),
                )

                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error deleting word progress: {e}")
            return False
