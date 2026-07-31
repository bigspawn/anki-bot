#!/usr/bin/env python3
"""Tests for the add-words result counters.

Regression: a surface form ("Mülltonnen") passed the existence check but its
lemma ("Mülltonne") was already learned, so the word vanished from both the
"added" and the "already learned" counters shown to the user.
"""

import os
import tempfile

import pytest

from src.core.database.database_manager import DatabaseManager


@pytest.fixture
def db_manager():
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
    temp_file.close()

    manager = DatabaseManager(temp_file.name)
    manager.init_database()

    yield manager

    os.unlink(temp_file.name)


def _word(lemma: str, translation: str = "перевод") -> dict:
    return {
        "lemma": lemma,
        "part_of_speech": "noun",
        "article": "die",
        "translation": translation,
        "example": f"Das ist eine {lemma}.",
        "confidence": 1.0,
    }


class TestAddWordsWithDetails:
    def test_reports_added_duplicates_and_invalid(self, db_manager):
        user = db_manager.create_user(telegram_id=111, first_name="Test")
        db_manager.add_words_to_user(user["telegram_id"], [_word("Mülltonne")])

        result = db_manager.add_words_with_details(
            user["telegram_id"],
            [
                _word("Hinterhaus"),
                _word("Mülltonne"),
                _word("Ort"),
                _word("Hof", translation=""),
            ],
        )

        assert result["added"] == ["Hinterhaus", "Ort"]
        assert result["duplicates"] == ["Mülltonne"]
        assert result["invalid"] == ["Hof"]

    def test_add_words_to_user_still_returns_added_count(self, db_manager):
        user = db_manager.create_user(telegram_id=222, first_name="Test")

        assert db_manager.add_words_to_user(user["telegram_id"], [_word("Haus")]) == 1
        assert db_manager.add_words_to_user(user["telegram_id"], [_word("Haus")]) == 0

    def test_counters_add_up_for_lemma_collision(self, db_manager):
        """The reported numbers must sum to the number of words found."""
        user = db_manager.create_user(telegram_id=333, first_name="Test")
        # Already learned: "Hof" as a surface form, "Mülltonne" only as lemma
        db_manager.add_words_to_user(
            user["telegram_id"], [_word("Hof"), _word("Mülltonne")]
        )

        extracted = ["Hinterhaus", "Hof", "Mülltonnen", "Ort"]
        existence = db_manager.check_multiple_words_exist(
            user["telegram_id"], extracted
        )
        existing_words = [w for w, exists in existence.items() if exists]
        assert existing_words == ["Hof"]  # "Mülltonnen" is missed here

        result = db_manager.add_words_with_details(
            user["telegram_id"],
            [_word("Hinterhaus"), _word("Mülltonne"), _word("Ort")],
        )
        already_known = existing_words + result["duplicates"]

        assert len(result["added"]) == 2
        assert len(already_known) == 2
        assert len(result["added"]) + len(already_known) == len(extracted)

    def test_existing_words_details_are_case_insensitive(self, db_manager):
        user = db_manager.create_user(telegram_id=444, first_name="Test")
        db_manager.add_words_to_user(user["telegram_id"], [_word("Mülltonne")])

        details = db_manager.get_existing_words_details(
            user["telegram_id"], ["mülltonne"]
        )

        assert [d["lemma"] for d in details] == ["Mülltonne"]
