#!/usr/bin/env python3
"""
Guards on the test environment itself (see tests/conftest.py).

The suite must run identically wherever it is started, and must never touch
the developer's own vocabulary database.
"""

from pathlib import Path

from src.config import get_database_path, get_settings
from src.core.database.database_manager import get_db_manager

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_settings_resolve_without_any_ambient_configuration():
    """Missing credentials used to fail every test that built a BotHandler"""
    settings = get_settings()

    assert settings.telegram_bot_token
    assert settings.openai_api_key


def test_the_suite_never_resolves_to_a_repository_database():
    resolved = Path(get_database_path()).resolve()

    assert REPO_ROOT not in resolved.parents, (
        f"tests would run against a database inside the repo: {resolved}"
    )


def test_the_default_database_manager_is_not_the_real_one():
    """get_db_manager() with no path falls back to the configured URL"""
    in_use = Path(get_db_manager().db_connection.db_path).resolve()

    assert in_use != (REPO_ROOT / "data" / "bot.db").resolve()
    assert in_use != (REPO_ROOT / "data" / "bot_prod.db").resolve()


def test_no_user_is_authorized_by_default():
    """A leaked ALLOWED_USERS would silently change authorization tests"""
    assert get_settings().allowed_users_list == []
