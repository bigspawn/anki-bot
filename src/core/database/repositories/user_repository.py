"""
User repository for database operations
"""

import logging
from datetime import datetime

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
                cursor = conn.execute(
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
                    "SELECT * FROM users WHERE telegram_id = ?",
                    (telegram_id,)
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
            with self.db_connection.get_connection() as conn:
                updates = []
                params = []

                if first_name is not None:
                    updates.append("first_name = ?")
                    params.append(first_name)

                if last_name is not None:
                    updates.append("last_name = ?")
                    params.append(last_name)

                if username is not None:
                    updates.append("username = ?")
                    params.append(username)

                if not updates:
                    return False

                updates.append("updated_at = ?")
                params.append(datetime.now())
                params.append(telegram_id)

                cursor = conn.execute(
                    f"UPDATE users SET {', '.join(updates)} WHERE telegram_id = ?",  # noqa: S608
                    params
                )
                conn.commit()

                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error updating user: {e}")
            return False

    def deactivate_user(self, user_id: int) -> bool:
        """Deactivate a user"""
        try:
            with self.db_connection.get_connection() as conn:
                cursor = conn.execute(
                    "UPDATE users SET is_active = 0, updated_at = ? WHERE id = ?",
                    (datetime.now(), user_id)
                )
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error deactivating user: {e}")
            return False

    def get_user_stats(self, user_id: int) -> UserStats | None:
        """Get comprehensive user statistics"""
        try:
            with self.db_connection.get_connection() as conn:
                # Get basic word counts
                cursor = conn.execute(
                    """
                    SELECT
                        COUNT(*) as total_words,
                        SUM(CASE WHEN lp.repetitions = 0 THEN 1 ELSE 0 END) as new_words,
                        SUM(CASE WHEN lp.next_review_date <= datetime('now') AND lp.repetitions > 0 THEN 1 ELSE 0 END) as due_words,
                        SUM(CASE WHEN lp.repetitions >= 3 THEN 1 ELSE 0 END) as learned_words,
                        SUM(CASE WHEN lp.easiness_factor < 2.0 THEN 1 ELSE 0 END) as difficult_words
                    FROM learning_progress lp
                    WHERE lp.user_id = ?
                    """,
                    (user_id,)
                )

                row = cursor.fetchone()
                if not row:
                    return None

                stats = dict(row)

                # Get average accuracy from recent reviews
                cursor = conn.execute(
                    """
                    SELECT AVG(CASE WHEN rating >= 3 THEN 1.0 ELSE 0.0 END) as avg_accuracy
                    FROM review_history
                    WHERE user_id = ? AND reviewed_at >= datetime('now', '-30 days')
                    """,
                    (user_id,)
                )

                accuracy_row = cursor.fetchone()
                stats['average_accuracy'] = accuracy_row['avg_accuracy'] if accuracy_row['avg_accuracy'] else 0.0

                # Get today's activity
                cursor = conn.execute(
                    """
                    SELECT
                        COUNT(DISTINCT word_id) as reviews_today
                    FROM review_history
                    WHERE user_id = ? AND date(reviewed_at) = date('now')
                    """,
                    (user_id,)
                )

                today_row = cursor.fetchone()
                stats['reviews_today'] = today_row['reviews_today'] if today_row else 0

                # Calculate study streak (simplified)
                stats['study_streak'] = 0  # Would need more complex logic
                stats['words_today'] = 0   # Would need to track word additions

                return stats

        except Exception as e:
            logger.error(f"Error getting user stats: {e}")
            return None
