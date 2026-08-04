#!/usr/bin/env python3
"""
Tests for the noun plural: how it is read, shown on the card, and repaired
for rows written by earlier prompt versions.
"""

import importlib.util
import json
import os
import sqlite3
import tempfile
from pathlib import Path

import pytest

from src.core.database.database_manager import DatabaseManager
from src.core.session.session_manager import SessionManager
from src.utils import format_plural_line, format_study_card, stored_plural

REPO_ROOT = Path(__file__).resolve().parents[1]
TELEGRAM_ID = 646464


def load_script(name: str):
    path = REPO_ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def noun(lemma="Haus", article="das", forms='{"plural": "die Häuser"}'):
    return {
        "id": 1,
        "lemma": lemma,
        "part_of_speech": "noun",
        "article": article,
        "translation": "дом",
        "example": "Das Haus ist groß.",
        "additional_forms": forms,
    }


@pytest.fixture
def db_path():
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
    temp_file.close()
    yield temp_file.name
    os.unlink(temp_file.name)


class TestReadingThePlural:
    def test_the_normal_shape_is_read(self):
        assert stored_plural(noun()) == "die Häuser"

    def test_a_capitalised_key_is_still_found(self):
        """Older answers used 'Plural' alongside 'Singular'"""
        word = noun(forms='{"Singular": "Flugzeug", "Plural": "Flugzeuge"}')

        assert stored_plural(word) == "Flugzeuge"

    def test_a_bare_text_answer_is_still_found(self):
        word = noun(forms="plural: die Beispiele")

        assert stored_plural(word) == "die Beispiele"

    def test_a_noun_without_a_plural_reads_as_none(self):
        assert stored_plural(noun(forms='{"plural": null}')) is None
        assert stored_plural(noun(forms="{}")) is None
        assert stored_plural(noun(forms=None)) is None

    def test_truncated_json_does_not_raise(self):
        assert stored_plural(noun(forms="{")) is None

    def test_only_nouns_are_considered(self):
        verb = {
            "lemma": "gehen",
            "part_of_speech": "verb",
            "additional_forms": '{"plural": "nonsense"}',
        }

        assert stored_plural(verb) is None


class TestShowingThePlural:
    def test_the_reveal_shows_the_plural(self):
        back = SessionManager._format_answer_text(noun())

        assert "🔢 Plural: die Häuser" in back

    def test_the_front_asks_for_the_plural_too(self):
        front = format_study_card(noun(), 1, 10)

        assert "Какой артикль и множественное число у Haus?" in front

    def test_the_front_never_asks_for_a_plural_that_is_missing(self):
        front = format_study_card(noun(forms='{"plural": null}'), 1, 10)

        assert front == "1/10. Какой артикль у Haus?"

    def test_the_front_never_leaks_the_answer(self):
        front = format_study_card(noun(), 1, 10)

        assert "Häuser" not in front

    def test_a_noun_without_a_plural_shows_no_line(self):
        assert format_plural_line(noun(forms="{}")) == ""
        assert "🔢" not in SessionManager._format_answer_text(noun(forms="{}"))

    def test_a_verb_keeps_its_principal_parts(self):
        verb = {
            "lemma": "gehen",
            "part_of_speech": "verb",
            "article": None,
            "translation": "идти",
            "example": "Ich gehe.",
            "additional_forms": '{"praeteritum": "ging", "partizip_ii": "gegangen"}',
        }

        back = SessionManager._format_answer_text(verb)

        assert "🔄 ging – gegangen" in back
        assert "🔢" not in back


class TestRepairPass:
    """The repair pass recovers plurals without calling anything"""

    @pytest.fixture
    def stocked(self, db_path):
        manager = DatabaseManager(db_path)
        manager.init_database()
        manager.create_user(telegram_id=TELEGRAM_ID, first_name="Tester")
        manager.add_words_with_details(
            TELEGRAM_ID,
            [
                {
                    "lemma": "Haus", "part_of_speech": "noun", "article": "das",
                    "translation": "дом", "example": "Das Haus.",
                    "additional_forms": '{"plural": "die Häuser"}',
                },
                {
                    "lemma": "Flugzeug", "part_of_speech": "noun", "article": "das",
                    "translation": "самолёт", "example": "Das Flugzeug.",
                    "additional_forms": '{"Singular": "Flugzeug", "Plural": "Flugzeuge"}',
                },
                {
                    "lemma": "Beispiel", "part_of_speech": "noun", "article": "das",
                    "translation": "пример", "example": "Das Beispiel.",
                    "additional_forms": "plural: die Beispiele",
                },
                {
                    "lemma": "Sonne", "part_of_speech": "noun", "article": "die",
                    "translation": "солнце", "example": "Die Sonne.",
                    "additional_forms": None,
                },
                {
                    "lemma": "gehen", "part_of_speech": "verb", "article": None,
                    "translation": "идти", "example": "Ich gehe.",
                    "additional_forms": '{"praeteritum": "ging", "partizip_ii": "gegangen"}',
                },
            ],
        )
        return manager

    def _forms(self, db_path, lemma):
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT additional_forms FROM words WHERE lemma = ?", (lemma,)
        ).fetchone()
        conn.close()
        return json.loads(row["additional_forms"])

    def test_a_capitalised_key_is_rewritten(self, stocked, db_path):
        load_script("backfill_noun_plural").backfill(db_path)

        forms = self._forms(db_path, "Flugzeug")
        assert forms["plural"] == "Flugzeuge"
        assert "Plural" not in forms
        assert forms["Singular"] == "Flugzeug", "other keys must survive"

    def test_a_text_answer_is_rewritten(self, stocked, db_path):
        load_script("backfill_noun_plural").backfill(db_path)

        assert self._forms(db_path, "Beispiel")["plural"] == "die Beispiele"

    def test_a_correct_row_is_left_alone(self, stocked, db_path):
        load_script("backfill_noun_plural").backfill(db_path)

        assert self._forms(db_path, "Haus")["plural"] == "die Häuser"

    def test_a_verb_is_never_touched(self, stocked, db_path):
        load_script("backfill_noun_plural").backfill(db_path)

        forms = self._forms(db_path, "gehen")
        assert forms == {"praeteritum": "ging", "partizip_ii": "gegangen"}

    def test_a_noun_with_nothing_to_recover_is_left_for_openai(self, stocked, db_path):
        backfill = load_script("backfill_noun_plural")
        backfill.backfill(db_path)

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT additional_forms FROM words WHERE lemma = 'Sonne'"
        ).fetchone()
        conn.close()

        assert not backfill.has_plural(row["additional_forms"])

    def test_a_dry_run_writes_nothing(self, stocked, db_path):
        load_script("backfill_noun_plural").backfill(db_path, dry_run=True)

        assert "plural" not in self._forms(db_path, "Flugzeug")

    def test_running_twice_changes_nothing(self, stocked, db_path):
        backfill = load_script("backfill_noun_plural")

        backfill.backfill(db_path)
        first = self._forms(db_path, "Flugzeug")
        backfill.backfill(db_path)

        assert self._forms(db_path, "Flugzeug") == first


class TestSetPlural:
    def test_it_keeps_the_other_keys(self):
        backfill = load_script("backfill_noun_plural")

        result = json.loads(
            backfill.set_plural('{"genus": "n", "Plural": "alt"}', "die Häuser")
        )

        assert result == {"genus": "n", "plural": "die Häuser"}

    def test_a_noun_without_a_plural_is_recorded_as_null(self):
        backfill = load_script("backfill_noun_plural")

        result = json.loads(backfill.set_plural("{}", None))

        assert result == {"plural": None}
        assert backfill.has_plural(json.dumps(result)), "must not be asked again"


class TestNormalizationOnWrite:
    """A plural must land under 'plural' whatever spelling the model used"""

    def test_a_capitalised_key_is_renamed(self):
        from src.word_processor import normalize_additional_forms

        result = json.loads(
            normalize_additional_forms({"Singular": "Haus", "Plural": "Häuser"})
        )

        assert result["plural"] == "Häuser"
        assert "Plural" not in result

    def test_the_normal_key_is_left_alone(self):
        from src.word_processor import normalize_additional_forms

        result = json.loads(normalize_additional_forms({"plural": "die Häuser"}))

        assert result == {"plural": "die Häuser"}

    def test_a_verb_answer_is_untouched(self):
        from src.word_processor import normalize_additional_forms

        result = json.loads(
            normalize_additional_forms({"praeteritum": "ging", "partizip_ii": "gegangen"})
        )

        assert result == {"praeteritum": "ging", "partizip_ii": "gegangen"}

    def test_a_string_answer_still_passes_through(self):
        from src.word_processor import normalize_additional_forms

        assert normalize_additional_forms('{"plural": "die Häuser"}') == (
            '{"plural": "die Häuser"}'
        )

    def test_a_freshly_normalized_noun_renders_its_plural(self):
        from src.word_processor import normalize_additional_forms

        word = noun(forms=normalize_additional_forms({"Plural": "die Häuser"}))

        assert "🔢 Plural: die Häuser" in SessionManager._format_answer_text(word)
