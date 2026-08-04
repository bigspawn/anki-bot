"""
Shared pytest setup.

Imported by pytest before any test module, so the environment is settled
before `src.config` is first read.

Two things are pinned here on purpose:

- The required credentials. Without them `Settings()` raises, and anything
  that builds a real `BotHandler` or reaches `get_settings()` fails. That
  used to make the suite pass only where the variables happened to be set
  (CI injects them) and fail everywhere else.
- The database URL. `get_db_manager()` with no explicit path resolves to
  `data/bot.db` — the developer's own vocabulary. Tests must never open it.
"""

import os
import tempfile
from pathlib import Path

# Assigned rather than defaulted: a stray .env or exported variable would
# otherwise decide what the suite runs against.
_TEST_DB_DIR = Path(tempfile.mkdtemp(prefix="anki-bot-tests-"))

os.environ["TELEGRAM_BOT_TOKEN"] = "test_token"
os.environ["OPENAI_API_KEY"] = "test_key"
os.environ["ALLOWED_USERS"] = ""
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB_DIR / 'test_bot.db'}"

from src.config import get_settings  # noqa: E402

# The cache may already hold settings read during collection
get_settings.cache_clear()
