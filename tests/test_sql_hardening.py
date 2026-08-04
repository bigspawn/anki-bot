#!/usr/bin/env python3
"""
Tests for the query paths that stopped building SQL out of f-strings:
partial user updates, variable-length lemma sets, the randomize flag and the
day windows in the review statistics.
"""

import os
import tempfile

import pytest

from src.core.database.database_manager import DatabaseManager

TELEGRAM_ID = 424242


@pytest.fixture
def db_manager():
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
    temp_file.close()

    manager = DatabaseManager(temp_file.name)
    manager.init_database()

    yield manager

    os.unlink(temp_file.name)


@pytest.fixture
def user_db(db_manager):
    db_manager.create_user(
        telegram_id=TELEGRAM_ID,
        first_name="Igor",
        last_name="Petrov",
        username="igor",
    )
    return db_manager


def words(count: int, **overrides):
    return [
        {
            "lemma": f"wort{i}",
            "part_of_speech": "noun",
            "translation": f"слово {i}",
            "example": f"Das ist wort{i}.",
            **overrides,
        }
        for i in range(count)
    ]


class TestPartialUserUpdate:
    """update_user touches only the fields it was given"""

    def test_updating_one_field_preserves_the_others(self, user_db):
        assert user_db.user_repo.update_user(TELEGRAM_ID, username="new_handle") is True

        user = user_db.get_user_by_telegram_id(TELEGRAM_ID)
        assert user["username"] == "new_handle"
        assert user["first_name"] == "Igor"
        assert user["last_name"] == "Petrov"

    def test_updating_every_field_at_once(self, user_db):
        user_db.user_repo.update_user(
            TELEGRAM_ID, first_name="Igor2", last_name="Ivanov", username="handle2"
        )

        user = user_db.get_user_by_telegram_id(TELEGRAM_ID)
        assert (user["first_name"], user["last_name"], user["username"]) == (
            "Igor2",
            "Ivanov",
            "handle2",
        )

    def test_updating_nothing_is_rejected(self, user_db):
        assert user_db.user_repo.update_user(TELEGRAM_ID) is False

        user = user_db.get_user_by_telegram_id(TELEGRAM_ID)
        assert user["first_name"] == "Igor"

    def test_updating_an_unknown_user_reports_failure(self, user_db):
        assert user_db.user_repo.update_user(999999, first_name="Ghost") is False

    def test_a_quote_in_a_name_is_stored_verbatim(self, user_db):
        # Would be a syntax error or an injection if names reached the SQL text
        user_db.user_repo.update_user(
            TELEGRAM_ID, first_name="O'Brien'; DROP TABLE users;--"
        )

        user = user_db.get_user_by_telegram_id(TELEGRAM_ID)
        assert user["first_name"] == "O'Brien'; DROP TABLE users;--"
        assert user_db.get_user_by_telegram_id(TELEGRAM_ID) is not None


class TestLemmaSetQueries:
    """The IN-list queries carry their values as a JSON array"""

    @pytest.fixture
    def stocked(self, user_db):
        user_db.add_words_with_details(TELEGRAM_ID, words(5))
        return user_db

    def test_lemma_set_matches_case_insensitively(self, stocked):
        found = stocked.get_words_by_lemma_set(
            TELEGRAM_ID, ["WORT1", "wort3"], limit=10
        )

        assert {w["lemma"] for w in found} == {"wort1", "wort3"}

    def test_an_empty_lemma_set_returns_nothing(self, stocked):
        assert stocked.get_words_by_lemma_set(TELEGRAM_ID, [], limit=10) == []

    def test_a_large_lemma_set_still_runs(self, stocked):
        found = stocked.get_words_by_lemma_set(
            TELEGRAM_ID, [f"wort{i}" for i in range(500)], limit=10
        )

        assert len(found) == 5

    def test_existence_check_matches_case_insensitively(self, stocked):
        existence = stocked.check_multiple_words_exist(
            TELEGRAM_ID, ["WORT0", "nicht_da"]
        )

        assert existence == {"WORT0": True, "nicht_da": False}

    def test_a_quote_in_a_lemma_is_not_sql(self, stocked):
        existence = stocked.check_multiple_words_exist(
            TELEGRAM_ID, ["'; DROP TABLE words;--"]
        )

        assert existence == {"'; DROP TABLE words;--": False}
        assert len(stocked.get_words_by_user(TELEGRAM_ID)) == 5


class TestRandomizeFlag:
    """Randomization is a bound value now, not a swapped-in ORDER BY"""

    @pytest.fixture
    def stocked(self, user_db):
        user_db.add_words_with_details(TELEGRAM_ID, words(20))
        return user_db

    def test_randomized_order_varies(self, stocked):
        orders = {
            tuple(w["lemma"] for w in stocked.get_new_words(TELEGRAM_ID, limit=8))
            for _ in range(15)
        }

        assert len(orders) > 1

    def test_non_randomized_order_is_stable(self, stocked):
        orders = {
            tuple(
                w["lemma"]
                for w in stocked.get_new_words(TELEGRAM_ID, limit=8, randomize=False)
            )
            for _ in range(10)
        }

        assert len(orders) == 1

    def test_the_limit_is_respected_either_way(self, stocked):
        assert len(stocked.get_new_words(TELEGRAM_ID, limit=5)) == 5
        assert len(stocked.get_new_words(TELEGRAM_ID, limit=5, randomize=False)) == 5

    def test_the_same_rows_are_eligible_either_way(self, stocked):
        random_rows = {
            w["lemma"] for w in stocked.get_new_words(TELEGRAM_ID, limit=100)
        }
        ordered_rows = {
            w["lemma"]
            for w in stocked.get_new_words(TELEGRAM_ID, limit=100, randomize=False)
        }

        assert random_rows == ordered_rows
        assert len(random_rows) == 20

    @pytest.mark.parametrize(
        "getter", ["get_due_words", "get_new_words", "get_difficult_words"]
    )
    def test_every_rubric_accepts_both_modes(self, stocked, getter):
        assert isinstance(getattr(stocked, getter)(TELEGRAM_ID, limit=5), list)
        assert isinstance(
            getattr(stocked, getter)(TELEGRAM_ID, limit=5, randomize=False), list
        )


class TestReviewWindows:
    """The day window is bound as a datetime modifier"""

    @pytest.fixture
    def reviewed(self, user_db):
        user_db.add_words_with_details(TELEGRAM_ID, words(3))
        for word in user_db.get_words_by_user(TELEGRAM_ID):
            user_db.update_learning_progress(TELEGRAM_ID, word["id"], 4)
        return user_db

    def test_recent_reviews_land_inside_the_window(self, reviewed):
        assert len(reviewed.progress_repo.get_recent_reviews(TELEGRAM_ID, days=7)) == 3

    def test_a_zero_day_window_is_valid_sql(self, reviewed):
        assert isinstance(
            reviewed.progress_repo.get_recent_reviews(TELEGRAM_ID, days=0), list
        )

    def test_performance_stats_count_the_window(self, reviewed):
        stats = reviewed.get_performance_stats(TELEGRAM_ID, days=30)

        assert stats["total_reviews"] == 3
        assert stats["accuracy"] == 100.0

    def test_a_narrow_window_excludes_older_reviews(self, reviewed):
        with reviewed.get_connection() as conn:
            conn.execute(
                "UPDATE review_history SET reviewed_at = datetime('now', '-40 days')"
            )
            conn.commit()

        assert (
            reviewed.get_performance_stats(TELEGRAM_ID, days=30)["total_reviews"] == 0
        )
        assert (
            reviewed.get_performance_stats(TELEGRAM_ID, days=60)["total_reviews"] == 3
        )
