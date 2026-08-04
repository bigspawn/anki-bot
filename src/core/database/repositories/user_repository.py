"""
User repository for database operations
"""

import logging
from datetime import datetime, timedelta

from ..connection import DatabaseConnection
from ..models import User, UserStats

logger = logging.getLogger(__name__)


class UserRepository:
    """Repository for user-related database operations"""

    def __init__(self, db_connection: DatabaseConnection):
        self.db_connection = db_connection

    def create_user(
        self,
        telegram_id: int,
        first_name: str,
        last_name: str | None = None,
        username: str | None = None,
    ) -> User | None:
        """Create a new user"""
        try:
            with self.db_connection.get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO users (telegram_id, first_name, last_name, username)
                    VALUES (?, ?, ?, ?)
                    """,
                    (telegram_id, first_name, last_name, username),
                )

                conn.commit()

                # Return the created user
                return self.get_user_by_telegram_id(telegram_id)
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            return None

    def get_user_by_telegram_id(self, telegram_id: int) -> User | None:
        """Get user by Telegram ID"""
        try:
            with self.db_connection.get_connection() as conn:
                cursor = conn.execute(
                    "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
                )
                row = cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Error getting user by Telegram ID: {e}")
            return None

    def update_user(
        self,
        telegram_id: int,
        first_name: str | None = None,
        last_name: str | None = None,
        username: str | None = None,
    ) -> bool:
        """Update user information"""
        try:
            if first_name is None and last_name is None and username is None:
                return False

            with self.db_connection.get_connection() as conn:
                # COALESCE keeps the stored value for every field left as None,
                # so the statement stays fixed instead of growing a SET clause
                cursor = conn.execute(
                    """
                    UPDATE users
                    SET first_name = COALESCE(?, first_name),
                        last_name = COALESCE(?, last_name),
                        username = COALESCE(?, username),
                        updated_at = ?
                    WHERE telegram_id = ?
                    """,
                    (
                        first_name,
                        last_name,
                        username,
                        datetime.now(),
                        telegram_id,
                    ),
                )
                conn.commit()

                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error updating user: {e}")
            return False

    def deactivate_user(self, telegram_id: int) -> bool:
        """Deactivate a user"""
        try:
            with self.db_connection.get_connection() as conn:
                cursor = conn.execute(
                    "UPDATE users SET is_active = 0, updated_at = ? WHERE telegram_id = ?",
                    (datetime.now(), telegram_id),
                )
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error deactivating user: {e}")
            return False

    def get_all_active_users(self) -> list[User]:
        """Get all active users"""
        try:
            with self.db_connection.get_connection() as conn:
                cursor = conn.execute("SELECT * FROM users WHERE is_active = 1")
                rows = cursor.fetchall()
                return [dict(row) for row in rows] if rows else []
        except Exception as e:
            logger.error(f"Error getting all active users: {e}")
            return []

    def get_user_stats(self, telegram_id: int) -> UserStats | None:
        """Get comprehensive user statistics"""
        try:
            with self.db_connection.get_connection() as conn:
                # Get basic word counts
                cursor = conn.execute(
                    """
                    SELECT
                        COUNT(*) as total_words,
                        SUM(CASE WHEN lp.repetitions = 0 THEN 1 ELSE 0 END) as new_words,
                        SUM(CASE WHEN datetime(lp.next_review_date) <= datetime('now', 'localtime') AND lp.repetitions > 0 THEN 1 ELSE 0 END) as due_words,
                        SUM(CASE WHEN lp.repetitions >= 3 THEN 1 ELSE 0 END) as learned_words,
                        SUM(CASE WHEN lp.easiness_factor < 2.0 THEN 1 ELSE 0 END) as difficult_words,
                        SUM(CASE WHEN date(lp.created_at) = date('now', 'localtime') THEN 1 ELSE 0 END) as words_today
                    FROM learning_progress lp
                    WHERE lp.telegram_id = ?
                    """,
                    (telegram_id,),
                )

                row = cursor.fetchone()
                if not row:
                    return None

                stats = dict(row)

                # Get review accuracy (correct/incorrect) from recent reviews
                cursor = conn.execute(
                    """
                    SELECT
                        COUNT(*) as total_reviews,
                        SUM(CASE WHEN rating >= 3 THEN 1 ELSE 0 END) as correct_reviews,
                        SUM(CASE WHEN rating < 3 THEN 1 ELSE 0 END) as incorrect_reviews
                    FROM review_history
                    WHERE telegram_id = ? AND reviewed_at >= datetime('now', '-30 days')
                    """,
                    (telegram_id,),
                )

                accuracy_row = cursor.fetchone()
                total_reviews = accuracy_row["total_reviews"] or 0
                stats["correct_reviews"] = accuracy_row["correct_reviews"] or 0
                stats["incorrect_reviews"] = accuracy_row["incorrect_reviews"] or 0
                stats["average_accuracy"] = (
                    stats["correct_reviews"] / total_reviews if total_reviews else 0.0
                )

                # Get today's activity
                cursor = conn.execute(
                    """
                    SELECT
                        COUNT(DISTINCT word_id) as reviews_today
                    FROM review_history
                    WHERE telegram_id = ? AND date(reviewed_at, 'localtime') = date('now', 'localtime')
                    """,
                    (telegram_id,),
                )

                today_row = cursor.fetchone()
                stats["reviews_today"] = today_row["reviews_today"] if today_row else 0

                # Calculate study streak: consecutive days (ending today or
                # yesterday) with at least one review
                cursor = conn.execute(
                    """
                    SELECT DISTINCT date(reviewed_at, 'localtime') as review_date
                    FROM review_history
                    WHERE telegram_id = ?
                    """,
                    (telegram_id,),
                )
                review_dates = {r["review_date"] for r in cursor.fetchall()}
                stats["study_streak"] = self._calculate_streak(review_dates)

                return stats

        except Exception as e:
            logger.error(f"Error getting user stats: {e}")
            return None

    @staticmethod
    def _calculate_streak(review_dates: set[str]) -> int:
        """Count consecutive days with at least one review, walking back from today"""
        if not review_dates:
            return 0

        today = datetime.now().date()
        cursor_date = today
        if cursor_date.isoformat() not in review_dates:
            # No review today yet - streak can still continue from yesterday
            cursor_date -= timedelta(days=1)
            if cursor_date.isoformat() not in review_dates:
                return 0

        streak = 0
        while cursor_date.isoformat() in review_dates:
            streak += 1
            cursor_date -= timedelta(days=1)

        return streak
