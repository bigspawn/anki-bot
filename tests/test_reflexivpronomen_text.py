#!/usr/bin/env python3
"""
The reflexive pronoun cards must repeat the vault table exactly, and the
resync script must be able to carry a correction to cards already stored.
"""

import importlib.util
import json
import os
import tempfile
from pathlib import Path

import pytest

from src.core.database.database_manager import DatabaseManager

REPO_ROOT = Path(__file__).resolve().parents[1]
PRONOUNS = REPO_ROOT / "seed" / "pronoun_case.json"
TELEGRAM_ID = 313131

# vault:01 – Грамматика/Местоимения, Возвратные местоимения
VAULT_TABLE = {
    ("ich", "Akkusativ"): ("mich", "себя / меня"),
    ("ich", "Dativ"): ("mir", "себе / мне"),
    ("du", "Akkusativ"): ("dich", "себя / тебя"),
    ("du", "Dativ"): ("dir", "себе / тебе"),
    ("er/sie/es", "Akkusativ"): ("sich", "себя"),
    ("er/sie/es", "Dativ"): ("sich", "себе"),
    ("wir", "Akkusativ"): ("uns", "себя / нас"),
    ("wir", "Dativ"): ("uns", "себе / нам"),
    ("ihr", "Akkusativ"): ("euch", "себя / вас"),
    ("ihr", "Dativ"): ("euch", "себе / вам"),
    ("sie/Sie", "Akkusativ"): ("sich", "себя / Вас"),
    ("sie/Sie", "Dativ"): ("sich", "себе / Вам"),
}


def load_script(name: str):
    path = REPO_ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def reflexive_cards() -> dict[tuple[str, str], dict]:
    cards = {}
    for word in json.loads(PRONOUNS.read_text(encoding="utf-8")):
        if " → Reflexiv " in word["lemma"]:
            person, case = word["lemma"].split(" → Reflexiv ")
            cards[(person, case)] = word
    return cards


class TestVaultTable:
    def test_every_cell_of_the_table_has_a_card(self):
        assert set(reflexive_cards()) == set(VAULT_TABLE)

    @pytest.mark.parametrize("cell", sorted(VAULT_TABLE, key=str))
    def test_the_form_and_the_translation_match_the_vault(self, cell):
        form, gloss = VAULT_TABLE[cell]
        card = reflexive_cards()[cell]

        assert card["translation"].startswith(f"{form} — {gloss}"), card["lemma"]

    def test_the_person_specific_gloss_is_not_flattened(self):
        """'себя / меня' carries more than a bare 'себя'"""
        cards = reflexive_cards()

        assert "меня" in cards[("ich", "Akkusativ")]["translation"]
        assert "тебе" in cards[("du", "Dativ")]["translation"]
        assert "нас" in cards[("wir", "Akkusativ")]["translation"]
        assert "Вам" in cards[("sie/Sie", "Dativ")]["translation"]

    def test_the_third_person_stays_plain(self):
        """The vault gives er/sie/es no second gloss"""
        cards = reflexive_cards()

        assert cards[("er/sie/es", "Akkusativ")]["translation"] == "sich — себя"
        assert cards[("er/sie/es", "Dativ")]["translation"].startswith("sich — себе")
        assert "/" not in cards[("er/sie/es", "Akkusativ")]["translation"]

    def test_a_repeated_form_says_so(self):
        cards = reflexive_cards()

        for person in ("er/sie/es", "wir", "ihr", "sie/Sie"):
            assert "совпадает с Akkusativ" in cards[(person, "Dativ")]["translation"]

        assert "совпадает" not in cards[("ich", "Dativ")]["translation"]


class TestResyncScript:
    @pytest.fixture
    def db_path(self):
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        temp_file.close()
        yield temp_file.name
        os.unlink(temp_file.name)

    @pytest.fixture
    def stocked(self, db_path):
        manager = DatabaseManager(db_path)
        manager.init_database()
        manager.create_user(telegram_id=TELEGRAM_ID, first_name="Tester")
        manager.add_words_with_details(
            TELEGRAM_ID,
            [
                {
                    "lemma": "ich → Reflexiv Akkusativ",
                    "part_of_speech": "pronoun case",
                    "translation": "mich — себя",
                    "example": "Ich wasche mich.",
                    "additional_forms": json.dumps({"topic": "reflexivpronomen"}),
                }
            ],
        )
        return manager

    def test_it_carries_the_correction_to_a_stored_card(self, stocked, db_path):
        load_script("resync_seed_text").resync(db_path, [str(PRONOUNS)])

        word = stocked.get_word_by_lemma("ich → Reflexiv Akkusativ")
        assert word["translation"] == "mich — себя / меня"

    def test_a_dry_run_writes_nothing(self, stocked, db_path):
        load_script("resync_seed_text").resync(db_path, [str(PRONOUNS)], dry_run=True)

        word = stocked.get_word_by_lemma("ich → Reflexiv Akkusativ")
        assert word["translation"] == "mich — себя"

    def test_running_twice_changes_nothing(self, stocked, db_path):
        resync = load_script("resync_seed_text")

        resync.resync(db_path, [str(PRONOUNS)])
        first = stocked.get_word_by_lemma("ich → Reflexiv Akkusativ")["translation"]
        resync.resync(db_path, [str(PRONOUNS)])

        assert (
            stocked.get_word_by_lemma("ich → Reflexiv Akkusativ")["translation"] == first
        )

    def test_a_users_own_word_under_the_same_lemma_is_left_alone(self, db_path):
        """Overwriting a word the user added themselves would be data loss"""
        manager = DatabaseManager(db_path)
        manager.init_database()
        manager.create_user(telegram_id=TELEGRAM_ID, first_name="Tester")
        manager.add_words_with_details(
            TELEGRAM_ID,
            [
                {
                    "lemma": "ich → Reflexiv Akkusativ",
                    "part_of_speech": "noun",
                    "translation": "моя собственная заметка",
                    "example": "Mein Beispiel.",
                }
            ],
        )

        load_script("resync_seed_text").resync(db_path, [str(PRONOUNS)])

        word = manager.get_word_by_lemma("ich → Reflexiv Akkusativ")
        assert word["translation"] == "моя собственная заметка"

    def test_a_lookup_map_seed_file_is_skipped(self, stocked, db_path):
        resync = load_script("resync_seed_text")

        assert resync.resync(
            db_path, [str(REPO_ROOT / "seed" / "noun_plurals.json")]
        )
