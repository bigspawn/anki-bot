"""
Database connection manager for the German Learning Bot
"""

import logging
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path

from ...config import get_database_path

logger = logging.getLogger(__name__)


class DatabaseConnection:
    """Manages SQLite database connections and settings"""

    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or get_database_path()
        self._ensure_database_directory()
        self._init_connection_settings()

    def _ensure_database_directory(self) -> None:
        """Ensure the database directory exists"""
        db_dir = Path(self.db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)

    def _init_connection_settings(self) -> None:
        """Initialize database connection settings"""
        with self.get_connection() as conn:
            # Enable WAL mode for better concurrency
            conn.execute("PRAGMA journal_mode=WAL")
            # Enable foreign key constraints
            conn.execute("PRAGMA foreign_keys=ON")
            # Set timeout for busy database
            conn.execute("PRAGMA busy_timeout=30000")

    @contextmanager
    def get_connection(self):
        """Get database connection with proper cleanup"""
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, detect_types=sqlite3.PARSE_DECLTYPES)
            conn.row_factory = sqlite3.Row  # Enable dict-like access

            # Add custom date and timestamp adapters to avoid deprecation warnings
            def adapt_date(val):
                return val.isoformat()

            def adapt_datetime(val):
                return val.isoformat()

            def convert_date(val):
                try:
                    return date.fromisoformat(val.decode())
                except ValueError:
                    # Try alternative formats
                    date_str = val.decode()
                    for fmt in ["%Y-%m-%d", "%Y-%m-%d %H:%M:%S"]:
                        try:
                            return datetime.strptime(date_str, fmt).date()
                        except ValueError:
                            continue
                    raise ValueError(f"Invalid date format: {date_str}") from None

            def convert_datetime(val):
                try:
                    return datetime.fromisoformat(val.decode())
                except ValueError:
                    # Try alternative formats
                    datetime_str = val.decode()
                    for fmt in [
                        "%Y-%m-%d %H:%M:%S",
                        "%Y-%m-%d %H:%M:%S.%f",
                        "%Y-%m-%d",
                    ]:
                        try:
                            return datetime.strptime(datetime_str, fmt)
                        except ValueError:
                            continue
                    raise ValueError(
                        f"Invalid datetime format: {datetime_str}"
                    ) from None

            sqlite3.register_adapter(date, adapt_date)
            sqlite3.register_adapter(datetime, adapt_datetime)
            sqlite3.register_converter("date", convert_date)
            sqlite3.register_converter("datetime", convert_datetime)
            sqlite3.register_converter(
                "timestamp", convert_datetime
            )  # Handle TIMESTAMP type

            yield conn
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            if conn:
                conn.close()

    def init_database(self) -> None:
        """Initialize database tables"""
        with self.get_connection() as conn:
            # Create tables
            self._create_tables(conn)
            # Run migrations
            self._run_migrations(conn)
            # Create indexes
            self._create_indexes(conn)

    def _create_tables(self, conn: sqlite3.Connection) -> None:
        """Create database tables"""
        # For testing, drop tables if they exist to ensure fresh schema
        if ":memory:" in str(self.db_path) or "test" in str(self.db_path):
            drop_tables = [
                "DROP TABLE IF EXISTS review_history",
                "DROP TABLE IF EXISTS learning_progress",
                "DROP TABLE IF EXISTS user_settings",
                "DROP TABLE IF EXISTS words",
                "DROP TABLE IF EXISTS users",
            ]
            for drop_sql in drop_tables:
                conn.execute(drop_sql)

        tables = [
            """
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                first_name TEXT NOT NULL,
                last_name TEXT,
                username TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT 1
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS words (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lemma TEXT UNIQUE NOT NULL,
                part_of_speech TEXT NOT NULL,
                article TEXT,
                translation TEXT NOT NULL,
                example TEXT NOT NULL,
                additional_forms TEXT,
                confidence REAL DEFAULT 1.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS learning_progress (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER NOT NULL,
                word_id INTEGER NOT NULL,
                repetitions INTEGER DEFAULT 0,
                easiness_factor REAL DEFAULT 2.5,
                interval_days INTEGER DEFAULT 1,
                next_review_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_reviewed TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (telegram_id) REFERENCES users(telegram_id) ON DELETE CASCADE,
                FOREIGN KEY (word_id) REFERENCES words(id) ON DELETE CASCADE,
                UNIQUE(telegram_id, word_id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS review_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER NOT NULL,
                word_id INTEGER NOT NULL,
                rating INTEGER NOT NULL,
                response_time_ms INTEGER DEFAULT 0,
                reviewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (telegram_id) REFERENCES users(telegram_id) ON DELETE CASCADE,
                FOREIGN KEY (word_id) REFERENCES words(id) ON DELETE CASCADE
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS user_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER NOT NULL,
                cards_per_session INTEGER DEFAULT 10,
                daily_reminder_time TEXT,
                timezone TEXT DEFAULT 'UTC',
                difficulty_level INTEGER DEFAULT 2,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (telegram_id) REFERENCES users(telegram_id) ON DELETE CASCADE,
                UNIQUE(telegram_id)
            )
            """,
        ]

        for table_sql in tables:
            conn.execute(table_sql)

    def _create_indexes(self, conn: sqlite3.Connection) -> None:
        """Create database indexes for performance"""
        # Check which column name is used in learning_progress table
        cursor = conn.execute("PRAGMA table_info(learning_progress)")
        progress_columns = [row[1] for row in cursor.fetchall()]

        # Determine the correct user ID column name
        user_id_column = (
            "telegram_id" if "telegram_id" in progress_columns else "user_id"
        )

        # Check which column name is used in review_history table
        cursor = conn.execute("PRAGMA table_info(review_history)")
        review_columns = [row[1] for row in cursor.fetchall()]
        review_user_id_column = (
            "telegram_id" if "telegram_id" in review_columns else "user_id"
        )

        # Check which column name is used in user_settings table
        cursor = conn.execute("PRAGMA table_info(user_settings)")
        settings_columns = [row[1] for row in cursor.fetchall()]
        settings_user_id_column = (
            "telegram_id" if "telegram_id" in settings_columns else "user_id"
        )

        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_words_lemma ON words(lemma)",
            (
                f"CREATE INDEX IF NOT EXISTS idx_learning_progress_{user_id_column} "
                f"ON learning_progress({user_id_column})"
            ),
            (
                "CREATE INDEX IF NOT EXISTS idx_learning_progress_next_review "
                "ON learning_progress(next_review_date)"
            ),
            (
                f"CREATE INDEX IF NOT EXISTS idx_review_history_{review_user_id_column} "
                f"ON review_history({review_user_id_column})"
            ),
            (
                "CREATE INDEX IF NOT EXISTS idx_review_history_reviewed_at "
                "ON review_history(reviewed_at)"
            ),
            (
                f"CREATE INDEX IF NOT EXISTS idx_user_settings_{settings_user_id_column} "
                f"ON user_settings({settings_user_id_column})"
            ),
        ]

        for index_sql in indexes:
            try:
                conn.execute(index_sql)
            except sqlite3.OperationalError as e:
                logger.warning(f"Failed to create index: {index_sql}, error: {e}")
                # Continue with other indexes

    def _run_migrations(self, conn: sqlite3.Connection) -> None:
        """Run database migrations for schema updates"""
        try:
            # Check if confidence column exists in words table
            cursor = conn.execute("PRAGMA table_info(words)")
            table_info = cursor.fetchall()
            columns = {
                row[1]: {"type": row[2], "notnull": row[3], "default": row[4]}
                for row in table_info
            }

            if "confidence" not in columns:
                logger.info("Adding missing confidence column to words table")
                conn.execute("ALTER TABLE words ADD COLUMN confidence REAL DEFAULT 1.0")
                conn.commit()
                logger.info("Successfully added confidence column to words table")

            # Check if response_time_ms column exists in review_history table
            cursor = conn.execute("PRAGMA table_info(review_history)")
            review_table_info = cursor.fetchall()
            review_columns = {
                row[1]: {"type": row[2], "notnull": row[3], "default": row[4]}
                for row in review_table_info
            }

            if "response_time_ms" not in review_columns:
                logger.info(
                    "Adding missing response_time_ms column to review_history table"
                )
                conn.execute(
                    "ALTER TABLE review_history ADD COLUMN response_time_ms "
                    "INTEGER DEFAULT 0"
                )
                conn.commit()
                logger.info(
                    "Successfully added response_time_ms column to review_history table"
                )

            # Check if word column exists and is NOT NULL - make it optional
            if "word" in columns and columns["word"]["notnull"] == 1:
                logger.info("Making word column optional by recreating table")

                # Create new table with correct schema
                conn.execute("""
                    CREATE TABLE words_new (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        lemma TEXT UNIQUE NOT NULL,
                        part_of_speech TEXT NOT NULL,
                        article TEXT,
                        translation TEXT NOT NULL,
                        example TEXT NOT NULL,
                        additional_forms TEXT,
                        confidence REAL DEFAULT 1.0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # Copy data from old table
                # First check what columns exist
                old_columns = list(columns.keys())

                # Build SELECT query based on existing columns
                select_parts = [
                    "id",
                    "lemma",
                    "COALESCE(part_of_speech, 'unknown') as part_of_speech",
                    "article",
                    "translation",
                    "COALESCE(example, '') as example",
                    "additional_forms",
                    "COALESCE(confidence, 1.0) as confidence",
                ]

                if "created_at" in old_columns:
                    select_parts.append("created_at")
                else:
                    select_parts.append("CURRENT_TIMESTAMP as created_at")

                if "updated_at" in old_columns:
                    select_parts.append("updated_at")
                else:
                    select_parts.append("CURRENT_TIMESTAMP as updated_at")

                select_query = f"""
                    INSERT INTO words_new (
                        id, lemma, part_of_speech, article, translation,
                        example, additional_forms, confidence, created_at, updated_at
                    )
                    SELECT {", ".join(select_parts)}
                    FROM words
                """  # noqa: S608  # Safe: select_parts contains only column names

                conn.execute(select_query)

                # Drop old table and rename new one
                conn.execute("DROP TABLE words")
                conn.execute("ALTER TABLE words_new RENAME TO words")

                conn.commit()
                logger.info("Successfully migrated words table to new schema")

        except Exception as e:
            logger.error(f"Error running database migrations: {e}")
            # Don't raise the exception to avoid breaking initialization
            # for tables that might not exist yet
