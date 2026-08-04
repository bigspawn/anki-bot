#!/usr/bin/env python3
"""
Tests for the curated word data and the scripts that load it:
seed/reflexive_verbs.json, seed/preposition_verbs.json, seed/word_levels.json,
scripts/seed_words.py and scripts/backfill_word_levels.py.
"""

import importlib.util
import json
import os
import re
import tempfile
from pathlib import Path

import pytest

from src.core.database.database_manager import DatabaseManager
from src.utils import format_study_card, format_verb_case, format_verb_forms

REPO_ROOT = Path(__file__).resolve().parents[1]
REFLEXIVE_PATH = REPO_ROOT / "seed" / "reflexive_verbs.json"
PREPOSITION_PATH = REPO_ROOT / "seed" / "preposition_verbs.json"
LEVELS_PATH = REPO_ROOT / "seed" / "word_levels.json"

CEFR_LEVELS = {"A1", "A2", "B1", "B2", "C1", "C2"}
CYRILLIC = re.compile(r"[а-яё]", re.IGNORECASE)


def load_script(name: str):
    """Import a scripts/*.py module by path (scripts/ is not a package)"""
    path = REPO_ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def reflexive_words():
    return json.loads(REFLEXIVE_PATH.read_text(encoding="utf-8"))


@pytest.fixture
def preposition_words():
    return json.loads(PREPOSITION_PATH.read_text(encoding="utf-8"))


@pytest.fixture
def db_path():
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
    temp_file.close()

    yield temp_file.name

    os.unlink(temp_file.name)


@pytest.fixture
def db_manager(db_path):
    manager = DatabaseManager(db_path)
    manager.init_database()
    manager.create_user(telegram_id=777, first_name="Test")
    return manager


class TestReflexiveData:
    def test_list_is_not_trivial(self, reflexive_words):
        assert len(reflexive_words) >= 50

    def test_lemmas_are_unique(self, reflexive_words):
        lemmas = [w["lemma"] for w in reflexive_words]
        assert len(lemmas) == len(set(lemmas))

    def test_every_entry_is_a_reflexive_verb(self, reflexive_words):
        for word in reflexive_words:
            assert word["lemma"].startswith("sich "), word["lemma"]
            assert word["part_of_speech"] == "reflexive verb", word["lemma"]
            assert word["article"] is None, word["lemma"]

    def test_translations_are_russian(self, reflexive_words):
        for word in reflexive_words:
            assert CYRILLIC.search(word["translation"]), word["lemma"]
            infinitive = word["lemma"].removeprefix("sich ")
            assert infinitive not in word["translation"], word["lemma"]

    def test_examples_are_german_sentences(self, reflexive_words):
        for word in reflexive_words:
            example = word["example"]
            assert example.endswith((".", "!", "?")), word["lemma"]
            assert not CYRILLIC.search(example), word["lemma"]

    def test_levels_are_valid(self, reflexive_words):
        for word in reflexive_words:
            assert word["level"] in CEFR_LEVELS, word["lemma"]

    def test_principal_parts_are_present_and_render(self, reflexive_words):
        for word in reflexive_words:
            forms = json.loads(word["additional_forms"])
            # case/topic were added later for /study_reflexive_case; the
            # principal parts still have to be there and still have to render
            assert {"praeteritum", "partizip_ii"} <= set(forms), word["lemma"]
            assert forms["praeteritum"] and forms["partizip_ii"], word["lemma"]
            assert format_verb_forms(word).startswith("🔄 "), word["lemma"]


class TestPrepositionVerbData:
    def test_list_is_not_trivial(self, preposition_words):
        assert len(preposition_words) >= 50

    def test_lemmas_are_unique(self, preposition_words):
        lemmas = [w["lemma"] for w in preposition_words]
        assert len(lemmas) == len(set(lemmas))

    def test_lemma_ends_with_its_preposition(self, preposition_words):
        for word in preposition_words:
            forms = json.loads(word["additional_forms"])
            assert word["lemma"].endswith(f" {forms['preposition']}"), word["lemma"]

    def test_case_is_akkusativ_or_dativ(self, preposition_words):
        for word in preposition_words:
            forms = json.loads(word["additional_forms"])
            assert forms["case"] in {"Akkusativ", "Dativ"}, word["lemma"]

    def test_part_of_speech_marks_verb_and_preposition(self, preposition_words):
        for word in preposition_words:
            assert word["part_of_speech"] == "verb + preposition", word["lemma"]

    def test_translations_are_russian(self, preposition_words):
        for word in preposition_words:
            assert CYRILLIC.search(word["translation"]), word["lemma"]

    def test_examples_are_german_sentences(self, preposition_words):
        for word in preposition_words:
            example = word["example"]
            assert example.endswith((".", "!", "?")), word["lemma"]
            assert not CYRILLIC.search(example), word["lemma"]

    def test_levels_are_valid(self, preposition_words):
        for word in preposition_words:
            assert word["level"] in CEFR_LEVELS, word["lemma"]

    def test_every_card_asks_for_the_case_and_can_answer_it(self, preposition_words):
        for word in preposition_words:
            question = format_study_card(word)
            assert question == f"Как переводится {word['lemma']} и какой падеж?"
            assert format_verb_case(word).startswith("🧭 "), word["lemma"]


class TestSeeding:
    def test_seeded_words_are_reachable_by_their_commands(
        self, db_manager, db_path, reflexive_words, preposition_words
    ):
        seed = load_script("seed_words")

        assert (
            seed.seed_words(db_path, 777, [str(REFLEXIVE_PATH), str(PREPOSITION_PATH)])
            is True
        )

        reflexive = db_manager.get_reflexive_verbs(777, limit=1000)
        rektion = db_manager.get_preposition_verbs(777, limit=1000)

        assert {w["lemma"] for w in reflexive} >= {w["lemma"] for w in reflexive_words}
        assert {w["lemma"] for w in rektion} >= {w["lemma"] for w in preposition_words}

    def test_reflexive_verbs_with_a_preposition_land_in_both_groups(
        self, db_manager, preposition_words
    ):
        """'sich freuen auf' is both reflexive and governed by a preposition"""
        db_manager.add_words_to_user(777, preposition_words)

        reflexive = {
            w["lemma"] for w in db_manager.get_reflexive_verbs(777, limit=1000)
        }

        assert "sich freuen auf" in reflexive

    def test_seeding_an_unknown_user_fails(self, db_path):
        seed = load_script("seed_words")

        assert seed.seed_words(db_path, 999, [str(REFLEXIVE_PATH)]) is False

    def test_seeding_twice_adds_nothing_new(self, db_manager, reflexive_words):
        first = db_manager.add_words_with_details(777, reflexive_words)
        second = db_manager.add_words_with_details(777, reflexive_words)

        assert len(first["added"]) == len(reflexive_words)
        assert second["added"] == []
        assert len(second["duplicates"]) == len(reflexive_words)


class TestLevelBackfill:
    def test_levels_file_is_valid(self):
        levels = json.loads(LEVELS_PATH.read_text(encoding="utf-8"))

        assert len(levels) > 500
        assert set(levels.values()) <= CEFR_LEVELS

    def test_backfill_fills_only_empty_levels(self, db_manager, db_path):
        backfill = load_script("backfill_word_levels")

        db_manager.add_words_to_user(
            777,
            [
                {"lemma": "Haus", "part_of_speech": "noun", "translation": "дом"},
                {
                    "lemma": "Behörde",
                    "part_of_speech": "noun",
                    "translation": "ведомство",
                },
                {
                    "lemma": "Quatschwort",
                    "part_of_speech": "noun",
                    "translation": "ерунда",
                },
                {
                    "lemma": "Ort",
                    "part_of_speech": "noun",
                    "translation": "место",
                    "level": "C2",  # already labeled, must be kept
                },
            ],
        )

        assert backfill.backfill_levels(db_path, str(LEVELS_PATH)) is True

        with db_manager.get_connection() as conn:
            levels = {
                row["lemma"]: row["level"]
                for row in conn.execute("SELECT lemma, level FROM words")
            }

        assert levels["Haus"] == "A1"
        assert levels["Behörde"] == "B1"
        assert levels["Ort"] == "C2"
        assert levels["Quatschwort"] is None

    def test_dry_run_changes_nothing(self, db_manager, db_path):
        backfill = load_script("backfill_word_levels")

        db_manager.add_words_to_user(
            777, [{"lemma": "Haus", "part_of_speech": "noun", "translation": "дом"}]
        )

        assert backfill.backfill_levels(db_path, str(LEVELS_PATH), dry_run=True) is True

        with db_manager.get_connection() as conn:
            level = conn.execute(
                "SELECT level FROM words WHERE lemma = 'Haus'"
            ).fetchone()["level"]

        assert level is None
