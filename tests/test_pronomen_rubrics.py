#!/usr/bin/env python3
"""
Tests for the four pronoun rubrics — personal, possessive, reflexive and
demonstrative — and for the umbrella /study_pronoun_case above them.
"""

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
from src.utils import format_study_card

REPO_ROOT = Path(__file__).resolve().parents[1]
SEED = REPO_ROOT / "seed"
TELEGRAM_ID = 929292

# command suffix -> (topic slugs, DatabaseManager getter)
RUBRICS = {
    "personalpronomen": ({"zatyk-09-pronomen-kasus"}, "get_personalpronomen_words"),
    "possessiv": ({"possessivpronomen"}, "get_possessivpronomen_words"),
    "reflexivpronomen": ({"reflexivpronomen"}, "get_reflexivpronomen_words"),
    "demonstrativ": ({"demonstrativpronomen", "derselbe"}, "get_demonstrativ_words"),
}

PRONOUN_SEEDS = ["pronoun_case.json", "demonstrativ.json"]


def load_seed(name: str) -> list[dict]:
    return json.loads((SEED / name).read_text(encoding="utf-8"))


def topic_of(word: dict) -> str:
    return json.loads(word.get("additional_forms") or "{}").get("topic", "")


def cards_for(slugs: set[str]) -> list[dict]:
    return [
        w for name in PRONOUN_SEEDS for w in load_seed(name) if topic_of(w) in slugs
    ]


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
def seeded(db_manager):
    words = [w for name in PRONOUN_SEEDS for w in load_seed(name)]
    db_manager.add_words_with_details(TELEGRAM_ID, words)
    return db_manager


class TestSeedData:
    @pytest.mark.parametrize("rubric", sorted(RUBRICS))
    def test_the_type_has_cards(self, rubric):
        slugs, _ = RUBRICS[rubric]

        assert cards_for(slugs)

    def test_every_pronoun_card_has_a_rule_and_an_example(self):
        for name in PRONOUN_SEEDS:
            for word in load_seed(name):
                assert word["translation"].strip(), word["lemma"]
                assert word["example"].strip(), word["lemma"]

    def test_all_four_types_are_present(self):
        topics = {topic_of(w) for name in PRONOUN_SEEDS for w in load_seed(name)}

        assert {
            "zatyk-09-pronomen-kasus",
            "possessivpronomen",
            "reflexivpronomen",
            "demonstrativpronomen",
        } <= topics

    def test_the_reflexive_table_covers_every_person(self):
        lemmas = {w["lemma"] for w in cards_for({"reflexivpronomen"})}

        for person in ("ich", "du", "er/sie/es", "wir", "ihr", "sie/Sie"):
            assert f"{person} → Reflexiv Akkusativ" in lemmas, person
            assert f"{person} → Reflexiv Dativ" in lemmas, person

    def test_the_possessive_table_covers_every_person(self):
        lemmas = {w["lemma"] for w in cards_for({"possessivpronomen"})}

        for person in ("ich", "du", "er/es", "sie (она)", "wir", "ihr", "sie/Sie"):
            assert f"{person} → притяжательное" in lemmas, person

    def test_euer_keeps_its_irregular_form(self):
        card = next(
            w
            for w in cards_for({"possessivpronomen"})
            if w["lemma"] == "ihr → притяжательное"
        )

        assert "euer" in card["translation"]
        assert "eure" in card["translation"]

    def test_the_demonstratives_cover_all_four_words(self):
        text = " ".join(w["translation"] for w in cards_for({"demonstrativpronomen"}))

        for word in ("dieser", "jener", "jeder", "solcher"):
            assert word in text, word

    def test_derselbe_declines_in_both_parts(self):
        card = next(
            w
            for w in cards_for({"derselbe"})
            if w["lemma"] == "derselbe Weg → Akkusativ"
        )

        assert "denselben" in card["translation"]


class TestRubricQueries:
    @pytest.mark.parametrize("rubric", sorted(RUBRICS))
    def test_the_rubric_returns_its_whole_type(self, seeded, rubric):
        slugs, getter = RUBRICS[rubric]

        found = getattr(seeded, getter)(TELEGRAM_ID, limit=500)

        assert len(found) == len(cards_for(slugs))

    def test_the_four_types_never_overlap(self, seeded):
        seen: set[str] = set()

        for _, getter in RUBRICS.values():
            lemmas = {
                w["lemma"] for w in getattr(seeded, getter)(TELEGRAM_ID, limit=500)
            }
            assert not lemmas & seen
            seen |= lemmas

    def test_the_umbrella_is_exactly_the_union_of_the_types(self, db_manager):
        """Including the gap-fill drills, which carry the same topics"""
        db_manager.add_words_with_details(
            TELEGRAM_ID,
            [w for name in PRONOUN_SEEDS for w in load_seed(name)]
            + load_seed("cloze_pronomen.json")
            + load_seed("cloze_demonstrativ.json"),
        )

        umbrella = {
            w["lemma"] for w in db_manager.get_pronoun_case_words(TELEGRAM_ID, limit=900)
        }
        union: set[str] = set()
        for _, getter in RUBRICS.values():
            union |= {
                w["lemma"] for w in getattr(db_manager, getter)(TELEGRAM_ID, limit=900)
            }

        assert umbrella == union
        assert any("___" in lemma for lemma in umbrella), "drills are missing"

    def test_demonstratives_are_in_the_umbrella_too(self, seeded):
        umbrella = seeded.get_pronoun_case_words(TELEGRAM_ID, limit=500)

        assert any(w["part_of_speech"] == "demonstrativ" for w in umbrella)

    def test_pronoun_drills_stay_out_of_the_plain_pronoun_rubric(self, seeded):
        """'pronoun case' and 'demonstrativ' must not reach /study_pronouns"""
        assert (
            seeded.get_words_by_part_of_speech(TELEGRAM_ID, "pronoun", limit=500) == []
        )

    def test_each_type_is_reachable_by_its_topic_slug(self, seeded):
        for slugs, _ in RUBRICS.values():
            for slug in slugs:
                assert seeded.get_words_by_topic(TELEGRAM_ID, slug, limit=500), slug


class TestRendering:
    def test_a_demonstrative_card_asks_for_the_form(self):
        card = next(
            w
            for w in load_seed("demonstrativ.json")
            if w["lemma"] == "dieser Mann → Akkusativ"
        )

        front = format_study_card(card, 1, 10)

        assert "dieser Mann → Akkusativ" in front
        assert "diesen" not in front

    def test_the_reveal_shows_the_form_and_the_example(self):
        card = next(
            w
            for w in load_seed("demonstrativ.json")
            if w["lemma"] == "dieser Mann → Akkusativ"
        )

        back = SessionManager._format_answer_text(card)

        assert "diesen Mann" in back
        assert card["example"] in back
        assert "demonstrativ" not in back

    def test_a_reflexive_pronoun_card_does_not_pretend_to_be_a_verb(self):
        card = next(
            w
            for w in load_seed("pronoun_case.json")
            if w["lemma"] == "ich → Reflexiv Dativ"
        )

        back = SessionManager._format_answer_text(card)

        assert "mir" in back
        assert "🪞 sich +" not in back


class TestCommands:
    @pytest.fixture
    def handlers(self):
        card = {
            "id": 1,
            "lemma": "ich → Reflexiv Dativ",
            "part_of_speech": "pronoun case",
            "article": None,
            "translation": "mir — себе",
            "example": "Ich wasche mir die Hände.",
            "repetitions": 0,
            "easiness_factor": 2.5,
            "interval_days": 1,
            "next_review_date": None,
            "last_reviewed": None,
        }
        mock_db = Mock(spec=DatabaseManager)
        mock_db.get_user_by_telegram_id.return_value = {"telegram_id": TELEGRAM_ID}
        for _, getter in RUBRICS.values():
            getattr(mock_db, getter).return_value = [card]

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

    @pytest.mark.parametrize("rubric", sorted(RUBRICS))
    @pytest.mark.asyncio
    async def test_command_starts_a_session(self, handlers, update, rubric):
        _, getter = RUBRICS[rubric]

        await getattr(handlers, f"study_{rubric}_command")(update, self._context())

        getattr(handlers.db_manager, getter).assert_called_once_with(
            TELEGRAM_ID, limit=10
        )
        handlers._start_study_session.assert_called_once()

    @pytest.mark.parametrize("rubric", sorted(RUBRICS))
    @pytest.mark.asyncio
    async def test_empty_rubric_explains_itself(self, handlers, update, rubric):
        _, getter = RUBRICS[rubric]
        getattr(handlers.db_manager, getter).return_value = []

        await getattr(handlers, f"study_{rubric}_command")(update, self._context())

        handlers._start_study_session.assert_not_called()
        assert "make seed-words" in handlers._safe_reply.call_args[0][1]

    @pytest.mark.parametrize("rubric", sorted(RUBRICS))
    @pytest.mark.asyncio
    async def test_unregistered_user_is_told_to_start(self, handlers, update, rubric):
        handlers.db_manager.get_user_by_telegram_id.return_value = None

        await getattr(handlers, f"study_{rubric}_command")(update, self._context())

        handlers._start_study_session.assert_not_called()
        assert "❌ Пользователь не найден" in handlers._safe_reply.call_args[0][1]

    @pytest.mark.parametrize("rubric", sorted(RUBRICS))
    @pytest.mark.asyncio
    async def test_update_without_a_user_does_nothing(self, handlers, rubric):
        update = Mock(spec=Update)
        update.effective_user = None

        await getattr(handlers, f"study_{rubric}_command")(update, self._context())

        handlers.db_manager.get_user_by_telegram_id.assert_not_called()
        handlers._safe_reply.assert_not_called()
