#!/usr/bin/env python3
"""
Tests for the verb-case rubrics: /study_reflexive_case, /study_dativ_verbs
and /study_dat_akk, their seed data and the case backfill script.
"""

import importlib.util
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest
from telegram import Message, Update, User
from telegram.ext import ContextTypes

from src.core.database.database_manager import DatabaseManager
from src.core.handlers.command_handlers import CommandHandlers
from src.core.session.session_manager import SessionManager
from src.utils import format_case_line, format_study_card

REPO_ROOT = Path(__file__).resolve().parents[1]
SEED = REPO_ROOT / "seed"

TELEGRAM_ID = 707070
CASES = {"Akkusativ", "Dativ", "Akkusativ/Dativ", "Dativ + Akkusativ"}
# Declension tables also drill Genitiv, which no verb rubric uses
PARADIGM_CASES = CASES | {"Genitiv"}


def load_script(name: str):
    """Import a scripts/*.py module by path (scripts/ is not a package)"""
    path = REPO_ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_seed(name: str) -> list[dict]:
    return json.loads((SEED / name).read_text(encoding="utf-8"))


@pytest.fixture
def reflexive_case_words():
    return load_seed("reflexive_case.json")


@pytest.fixture
def dativ_words():
    return load_seed("dativ_verbs.json")


@pytest.fixture
def dat_akk_words():
    return load_seed("dat_akk_verbs.json")


@pytest.fixture
def reflexive_words():
    return load_seed("reflexive_verbs.json")


@pytest.fixture
def preposition_words():
    return load_seed("preposition_verbs.json")


@pytest.fixture
def db_manager():
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
    temp_file.close()

    manager = DatabaseManager(temp_file.name)
    manager.init_database()
    manager.create_user(telegram_id=TELEGRAM_ID, first_name="Tester")

    yield manager

    os.unlink(temp_file.name)


@pytest.fixture
def seeded_db(
    db_manager,
    reflexive_case_words,
    dativ_words,
    dat_akk_words,
    reflexive_words,
    preposition_words,
):
    db_manager.add_words_with_details(
        TELEGRAM_ID,
        reflexive_case_words
        + dativ_words
        + dat_akk_words
        + reflexive_words
        + preposition_words,
    )
    return db_manager


class TestSeedData:
    """The authored case sets stay well formed"""

    def test_every_card_records_a_known_case(
        self, reflexive_case_words, dativ_words, dat_akk_words
    ):
        for word in reflexive_case_words + dativ_words + dat_akk_words:
            case = json.loads(word["additional_forms"])["case"]
            assert case in CASES, f"{word['lemma']}: {case}"

    def test_reflexive_case_cards_are_all_about_sich(self, reflexive_case_words):
        assert reflexive_case_words
        for word in reflexive_case_words:
            assert word["lemma"].startswith("sich ")
            assert word["part_of_speech"] == "reflexive case"

    def test_dativ_cards_govern_dativ(self, dativ_words):
        assert dativ_words
        for word in dativ_words:
            forms = json.loads(word["additional_forms"])
            assert forms["case"] == "Dativ"
            assert forms["topic"] == "zatyk-16-dativ-verben"

    def test_two_object_cards_govern_both_cases(self, dat_akk_words):
        assert dat_akk_words
        for word in dat_akk_words:
            forms = json.loads(word["additional_forms"])
            assert forms["case"] == "Dativ + Akkusativ"
            assert forms["topic"] == "dat-akk-verbs"

    def test_the_example_shows_the_case_in_use(
        self, reflexive_case_words, dativ_words, dat_akk_words
    ):
        for word in reflexive_case_words + dativ_words + dat_akk_words:
            assert word["example"].strip(), word["lemma"]

    def test_new_cards_do_not_collide_with_the_existing_reflexive_list(
        self, reflexive_case_words, reflexive_words
    ):
        """words.lemma is UNIQUE — a clash would silently drop the new card"""
        existing = {w["lemma"].lower() for w in reflexive_words}

        clashes = [
            w["lemma"] for w in reflexive_case_words if w["lemma"].lower() in existing
        ]

        assert clashes == []

    def test_every_reflexive_verb_now_carries_a_case(self, reflexive_words):
        for word in reflexive_words:
            forms = json.loads(word["additional_forms"])
            assert forms.get("case") in CASES, word["lemma"]
            assert forms.get("topic") == "zatyk-08-reflexive-kasus", word["lemma"]

    def test_the_principal_parts_survived_the_backfill(self, reflexive_words):
        for word in reflexive_words:
            forms = json.loads(word["additional_forms"])
            assert forms.get("praeteritum"), word["lemma"]
            assert forms.get("partizip_ii"), word["lemma"]


class TestRubricQueries:
    """Each rubric returns its own material and nothing else"""

    def test_reflexive_case_covers_drills_and_backfilled_verbs(
        self, seeded_db, reflexive_case_words, reflexive_words
    ):
        found = seeded_db.get_reflexive_case_words(TELEGRAM_ID, limit=500)

        assert len(found) == len(reflexive_case_words) + len(reflexive_words)

    def test_preposition_verbs_stay_out_of_the_reflexive_case_rubric(self, seeded_db):
        """'sich erinnern an' stores the case of its object, not of sich"""
        found = seeded_db.get_reflexive_case_words(TELEGRAM_ID, limit=500)

        assert "sich erinnern an" not in {w["lemma"] for w in found}
        assert not any("preposition" in w["part_of_speech"].lower() for w in found)
        assert not any(
            "preposition" in json.loads(w["additional_forms"]) for w in found
        )

    def test_the_rektion_rubric_still_owns_those_verbs(self, seeded_db):
        found = {
            w["lemma"] for w in seeded_db.get_preposition_verbs(TELEGRAM_ID, limit=500)
        }

        assert "sich erinnern an" in found

    def test_dativ_rubric_returns_only_dativ_verbs(self, seeded_db, dativ_words):
        found = seeded_db.get_dativ_verbs(TELEGRAM_ID, limit=500)

        assert len(found) == len(dativ_words)
        assert all(json.loads(w["additional_forms"])["case"] == "Dativ" for w in found)

    def test_two_object_rubric_returns_only_its_verbs(self, seeded_db, dat_akk_words):
        found = seeded_db.get_dat_akk_verbs(TELEGRAM_ID, limit=500)

        assert len(found) == len(dat_akk_words)

    def test_the_three_rubrics_do_not_overlap(self, seeded_db):
        reflexive = {
            w["lemma"]
            for w in seeded_db.get_reflexive_case_words(TELEGRAM_ID, limit=500)
        }
        dativ = {w["lemma"] for w in seeded_db.get_dativ_verbs(TELEGRAM_ID, limit=500)}
        dat_akk = {
            w["lemma"] for w in seeded_db.get_dat_akk_verbs(TELEGRAM_ID, limit=500)
        }

        assert not reflexive & dativ
        assert not reflexive & dat_akk
        assert not dativ & dat_akk

    def test_words_without_a_case_are_never_returned(self, db_manager):
        db_manager.add_words_with_details(
            TELEGRAM_ID,
            [
                {
                    "lemma": "sich ohne Kasus",
                    "part_of_speech": "reflexive verb",
                    "translation": "без падежа",
                    "example": "Beispiel.",
                    "additional_forms": json.dumps({"praeteritum": "x"}),
                }
            ],
        )

        assert db_manager.get_reflexive_case_words(TELEGRAM_ID, limit=10) == []

    def test_a_non_json_additional_forms_does_not_break_the_query(self, seeded_db):
        with seeded_db.get_connection() as conn:
            conn.execute(
                "INSERT INTO words (lemma, part_of_speech, translation, example, additional_forms)"
                " VALUES ('sich kaputt', 'reflexive verb', 'сломанный', 'Beispiel.', 'not json')"
            )
            word_id = conn.execute(
                "SELECT id FROM words WHERE lemma = 'sich kaputt'"
            ).fetchone()["id"]
            conn.execute(
                "INSERT INTO learning_progress (telegram_id, word_id) VALUES (?, ?)",
                (TELEGRAM_ID, word_id),
            )
            conn.commit()

        assert seeded_db.get_reflexive_case_words(TELEGRAM_ID, limit=500)


class TestBackfillScript:
    """backfill_verb_case annotates words that seeding skips as duplicates"""

    def test_it_annotates_a_word_already_in_the_dictionary(self, db_manager):
        db_manager.add_words_with_details(
            TELEGRAM_ID,
            [
                {
                    "lemma": "helfen",
                    "part_of_speech": "verb",
                    "translation": "помогать",
                    "example": "Ich helfe dir.",
                    "additional_forms": json.dumps(
                        {"praeteritum": "half", "partizip_ii": "geholfen"}
                    ),
                }
            ],
        )
        assert db_manager.get_dativ_verbs(TELEGRAM_ID, limit=10) == []

        backfill = load_script("backfill_verb_case")
        assert backfill.backfill_verb_case(
            db_manager.db_connection.db_path, [str(SEED / "dativ_verbs.json")]
        )

        found = db_manager.get_dativ_verbs(TELEGRAM_ID, limit=10)
        assert [w["lemma"] for w in found] == ["helfen"]

    def test_it_keeps_the_keys_it_did_not_come_for(self, db_manager):
        db_manager.add_words_with_details(
            TELEGRAM_ID,
            [
                {
                    "lemma": "helfen",
                    "part_of_speech": "verb",
                    "translation": "помогать",
                    "example": "Ich helfe dir.",
                    "additional_forms": json.dumps(
                        {"praeteritum": "half", "partizip_ii": "geholfen"}
                    ),
                }
            ],
        )

        backfill = load_script("backfill_verb_case")
        backfill.backfill_verb_case(
            db_manager.db_connection.db_path, [str(SEED / "dativ_verbs.json")]
        )

        forms = json.loads(db_manager.get_word_by_lemma("helfen")["additional_forms"])
        assert forms["praeteritum"] == "half"
        assert forms["partizip_ii"] == "geholfen"
        assert forms["case"] == "Dativ"

    def test_running_it_twice_changes_nothing(self, db_manager):
        db_manager.add_words_with_details(
            TELEGRAM_ID,
            [
                {
                    "lemma": "helfen",
                    "part_of_speech": "verb",
                    "translation": "помогать",
                    "example": "Ich helfe dir.",
                    "additional_forms": json.dumps({"praeteritum": "half"}),
                }
            ],
        )
        backfill = load_script("backfill_verb_case")
        path = db_manager.db_connection.db_path

        backfill.backfill_verb_case(path, [str(SEED / "dativ_verbs.json")])
        first = db_manager.get_word_by_lemma("helfen")["additional_forms"]
        backfill.backfill_verb_case(path, [str(SEED / "dativ_verbs.json")])
        second = db_manager.get_word_by_lemma("helfen")["additional_forms"]

        assert first == second

    def test_a_dry_run_writes_nothing(self, db_manager):
        db_manager.add_words_with_details(
            TELEGRAM_ID,
            [
                {
                    "lemma": "helfen",
                    "part_of_speech": "verb",
                    "translation": "помогать",
                    "example": "Ich helfe dir.",
                    "additional_forms": json.dumps({"praeteritum": "half"}),
                }
            ],
        )

        backfill = load_script("backfill_verb_case")
        backfill.backfill_verb_case(
            db_manager.db_connection.db_path,
            [str(SEED / "dativ_verbs.json")],
            dry_run=True,
        )

        assert db_manager.get_dativ_verbs(TELEGRAM_ID, limit=10) == []

    def test_a_word_not_in_the_dictionary_is_left_alone(self, db_manager):
        backfill = load_script("backfill_verb_case")

        assert backfill.backfill_verb_case(
            db_manager.db_connection.db_path, [str(SEED / "dativ_verbs.json")]
        )
        assert db_manager.get_dativ_verbs(TELEGRAM_ID, limit=10) == []


class TestCardRendering:
    """The case is asked for on the front and revealed on the back"""

    @pytest.fixture
    def reflexive_card(self):
        return {
            "id": 1,
            "lemma": "sich die Hände waschen",
            "part_of_speech": "reflexive case",
            "article": None,
            "translation": "мыть себе руки (есть второй объект → Dat)",
            "example": "Ich wasche mir die Hände.",
            "additional_forms": json.dumps(
                {"case": "Dativ", "topic": "zatyk-08-reflexive-kasus"}
            ),
        }

    @pytest.fixture
    def dativ_card(self):
        return {
            "id": 2,
            "lemma": "helfen",
            "part_of_speech": "dativ verb",
            "article": None,
            "translation": "помогать (кому — Dativ)",
            "example": "Ich helfe dir.",
            "additional_forms": json.dumps(
                {"case": "Dativ", "topic": "zatyk-16-dativ-verben"}
            ),
        }

    @pytest.fixture
    def preposition_card(self):
        return {
            "id": 3,
            "lemma": "sich erinnern an",
            "part_of_speech": "verb + preposition",
            "article": None,
            "translation": "вспоминать о",
            "example": "Ich erinnere mich an dich.",
            "additional_forms": json.dumps({"preposition": "an", "case": "Akkusativ"}),
        }

    def test_the_reflexive_front_asks_about_sich(self, reflexive_card):
        front = format_study_card(reflexive_card, 1, 10)

        assert "Какой падеж у sich" in front
        assert reflexive_card["lemma"] in front

    def test_the_reflexive_front_hides_the_answer(self, reflexive_card):
        front = format_study_card(reflexive_card, 1, 10)

        assert "Dativ" not in front
        assert reflexive_card["example"] not in front

    def test_the_reflexive_back_shows_the_case(self, reflexive_card):
        back = SessionManager._format_answer_text(reflexive_card)

        assert "🪞 sich + Dativ" in back
        assert reflexive_card["example"] in back

    def test_the_dativ_back_shows_the_governed_case(self, dativ_card):
        back = SessionManager._format_answer_text(dativ_card)

        assert "📐 helfen + Dativ" in back

    def test_a_preposition_verb_keeps_its_own_card(self, preposition_card):
        """Its case belongs to the object after 'an', not to sich"""
        front = format_study_card(preposition_card, 1, 10)
        back = SessionManager._format_answer_text(preposition_card)

        assert "Какой падеж у sich" not in front
        assert front == "1/10. Как переводится sich erinnern an и какой падеж?"
        assert "🧭 an + Akkusativ" in back
        assert "🪞" not in back

    def test_a_reflexive_verb_without_a_case_keeps_its_principal_parts(self):
        word = {
            "id": 4,
            "lemma": "sich verlaufen",
            "part_of_speech": "reflexive verb",
            "article": None,
            "translation": "заблудиться",
            "example": "Wir haben uns verlaufen.",
            "additional_forms": json.dumps(
                {"praeteritum": "verlief", "partizip_ii": "verlaufen"}
            ),
        }

        assert format_case_line(word) == ""
        assert "🔄 verlief – verlaufen" in SessionManager._format_answer_text(word)

    def test_a_backfilled_reflexive_verb_shows_the_case_instead(self):
        """case wins over the principal parts: it is what the rubric drills"""
        word = {
            "id": 5,
            "lemma": "sich verlaufen",
            "part_of_speech": "reflexive verb",
            "article": None,
            "translation": "заблудиться",
            "example": "Wir haben uns verlaufen.",
            "additional_forms": json.dumps(
                {
                    "praeteritum": "verlief",
                    "partizip_ii": "verlaufen",
                    "case": "Akkusativ",
                    "topic": "zatyk-08-reflexive-kasus",
                }
            ),
        }

        assert "🪞 sich + Akkusativ" in SessionManager._format_answer_text(word)


class TestCommands:
    """The three commands guard the same edge cases as the older rubrics"""

    @pytest.fixture
    def card(self):
        return {
            "id": 1,
            "lemma": "helfen",
            "part_of_speech": "dativ verb",
            "article": None,
            "translation": "помогать",
            "example": "Ich helfe dir.",
            "repetitions": 0,
            "easiness_factor": 2.5,
            "interval_days": 1,
            "next_review_date": None,
            "last_reviewed": None,
        }

    @pytest.fixture
    def handlers(self, card):
        mock_db = Mock(spec=DatabaseManager)
        mock_db.get_user_by_telegram_id.return_value = {"telegram_id": TELEGRAM_ID}
        mock_db.get_reflexive_case_words.return_value = [card]
        mock_db.get_dativ_verbs.return_value = [card]
        mock_db.get_dat_akk_verbs.return_value = [card]

        handlers = CommandHandlers(
            db_manager=mock_db,
            word_processor=Mock(),
            text_parser=Mock(),
            srs_system=Mock(),
            safe_reply_callback=AsyncMock(),
            process_text_callback=AsyncMock(),
            start_study_session_callback=AsyncMock(),
            state_manager=Mock(),
            session_manager=Mock(),
        )
        handlers._safe_reply = AsyncMock()
        handlers._start_study_session = AsyncMock()
        return handlers

    @pytest.fixture
    def update(self):
        update = Mock(spec=Update)
        update.effective_user = Mock(spec=User)
        update.effective_user.id = TELEGRAM_ID
        update.message = Mock(spec=Message)
        return update

    def _context(self):
        context = Mock(spec=ContextTypes.DEFAULT_TYPE)
        context.args = None
        return context

    @pytest.mark.parametrize(
        "command,getter",
        [
            ("study_reflexive_case_command", "get_reflexive_case_words"),
            ("study_dativ_verbs_command", "get_dativ_verbs"),
            ("study_dat_akk_command", "get_dat_akk_verbs"),
        ],
    )
    @pytest.mark.asyncio
    async def test_command_starts_a_session(self, handlers, update, command, getter):
        await getattr(handlers, command)(update, self._context())

        getattr(handlers.db_manager, getter).assert_called_once_with(
            TELEGRAM_ID, limit=10
        )
        handlers._start_study_session.assert_called_once()

    @pytest.mark.parametrize(
        "command,getter,expected",
        [
            (
                "study_reflexive_case_command",
                "get_reflexive_case_words",
                "нет возвратных глаголов с отмеченным падежом",
            ),
            ("study_dativ_verbs_command", "get_dativ_verbs", "нет глаголов с Dativ"),
            (
                "study_dat_akk_command",
                "get_dat_akk_verbs",
                "нет глаголов с двумя объектами",
            ),
        ],
    )
    @pytest.mark.asyncio
    async def test_empty_rubric_explains_itself(
        self, handlers, update, command, getter, expected
    ):
        getattr(handlers.db_manager, getter).return_value = []

        await getattr(handlers, command)(update, self._context())

        handlers._start_study_session.assert_not_called()
        assert expected in handlers._safe_reply.call_args[0][1]

    @pytest.mark.parametrize(
        "command",
        [
            "study_reflexive_case_command",
            "study_dativ_verbs_command",
            "study_dat_akk_command",
        ],
    )
    @pytest.mark.asyncio
    async def test_unregistered_user_is_told_to_start(self, handlers, update, command):
        handlers.db_manager.get_user_by_telegram_id.return_value = None

        await getattr(handlers, command)(update, self._context())

        handlers._start_study_session.assert_not_called()
        assert "❌ Пользователь не найден" in handlers._safe_reply.call_args[0][1]

    @pytest.mark.parametrize(
        "command",
        [
            "study_reflexive_case_command",
            "study_dativ_verbs_command",
            "study_dat_akk_command",
        ],
    )
    @pytest.mark.asyncio
    async def test_update_without_a_user_does_nothing(self, handlers, command):
        update = Mock(spec=Update)
        update.effective_user = None

        await getattr(handlers, command)(update, self._context())

        handlers.db_manager.get_user_by_telegram_id.assert_not_called()
        handlers._safe_reply.assert_not_called()


class TestParadigmRubrics:
    """/study_article_case and /study_pronoun_case drill declension tables"""

    @pytest.fixture
    def paradigm_db(self, db_manager):
        db_manager.add_words_with_details(
            TELEGRAM_ID,
            load_seed("pronoun_case.json") + load_seed("article_case.json"),
        )
        return db_manager

    def test_every_paradigm_card_carries_its_answer(self):
        for word in load_seed("pronoun_case.json") + load_seed("article_case.json"):
            forms = json.loads(word["additional_forms"])
            assert forms.get("answer"), word["lemma"]
            assert forms.get("case") in PARADIGM_CASES, word["lemma"]
            assert "→" in word["lemma"], word["lemma"]

    def test_the_answer_is_visible_on_the_back_only(self):
        for word in load_seed("article_case.json"):
            answer = json.loads(word["additional_forms"])["answer"]
            # "die Kinder (Pl)" carries a number marker the answer never has
            nominative = word["lemma"].split(" → ")[0].split(" (")[0]
            assert answer in word["translation"], word["lemma"]

            # Some cells genuinely do not change (die Frau → Akkusativ), and
            # there the answer cannot help but appear on the front
            if answer != nominative:
                assert answer not in format_study_card(word, 1, 10), word["lemma"]

    def test_article_rubric_returns_only_article_cards(self, paradigm_db):
        found = paradigm_db.get_article_case_words(TELEGRAM_ID, limit=500)

        assert len(found) == len(load_seed("article_case.json"))
        assert all(w["part_of_speech"] == "article case" for w in found)

    def test_pronoun_rubric_returns_only_pronoun_cards(self, paradigm_db):
        found = paradigm_db.get_pronoun_case_words(TELEGRAM_ID, limit=500)

        assert len(found) == len(load_seed("pronoun_case.json"))
        assert all(w["part_of_speech"] == "pronoun case" for w in found)

    def test_the_two_paradigm_rubrics_do_not_overlap(self, paradigm_db):
        articles = {
            w["lemma"]
            for w in paradigm_db.get_article_case_words(TELEGRAM_ID, limit=500)
        }
        pronouns = {
            w["lemma"]
            for w in paradigm_db.get_pronoun_case_words(TELEGRAM_ID, limit=500)
        }

        assert not articles & pronouns

    def test_paradigm_cards_stay_out_of_the_verb_rubrics(self, paradigm_db):
        assert paradigm_db.get_dativ_verbs(TELEGRAM_ID, limit=500) == []
        assert paradigm_db.get_dat_akk_verbs(TELEGRAM_ID, limit=500) == []
        assert paradigm_db.get_reflexive_case_words(TELEGRAM_ID, limit=500) == []

    def test_the_front_asks_for_the_form(self):
        card = load_seed("article_case.json")[0]

        front = format_study_card(card, 2, 9)

        assert front.startswith("2/9. Поставьте в нужный падеж:")
        assert card["lemma"] in front

    def test_the_back_shows_the_form_and_the_example(self):
        card = load_seed("article_case.json")[0]

        back = SessionManager._format_answer_text(card)

        assert card["translation"] in back
        assert card["example"] in back
        assert "article case" not in back
