#!/usr/bin/env python3
"""
Tests for the rubrics built from the vault's Затыки list and for the topic
slugs that tie them back to its repeat tracker.
"""

import json
import os
import re
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
TELEGRAM_ID = 818181

# rubric -> (seed file, part_of_speech, DatabaseManager getter)
RUBRICS = {
    "wo_wohin": ("wo_wohin.json", "wo wohin", "get_wo_wohin_words"),
    "verschmelzung": ("verschmelzung.json", "verschmelzung", "get_verschmelzung_words"),
    "wortstellung": ("wortstellung.json", "word order", "get_word_order_words"),
    "adjektive": ("adjektive.json", "adjective ending", "get_adjective_ending_words"),
    "verbformen": ("verbformen.json", "verb form", "get_verb_form_words"),
    "zeitangaben": ("zeitangaben.json", "zeitangabe", "get_zeitangabe_words"),
}

ZATYK_SLUG = re.compile(r"^zatyk-\d{2}-[a-z-]+$")


def load_seed(name: str) -> list[dict]:
    return json.loads((SEED / name).read_text(encoding="utf-8"))


def all_seed_words() -> list[dict]:
    """Every card in seed/. Some seed files are lookup maps, not card lists
    (word_levels.json, noun_plurals.json), so go by shape rather than name."""
    words = []
    for path in SEED.glob("*.json"):
        content = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(content, list):
            words.extend(content)
    return words


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
    words = []
    for seed_file, _, _ in RUBRICS.values():
        words.extend(load_seed(seed_file))
    db_manager.add_words_with_details(TELEGRAM_ID, words)
    return db_manager


class TestSeedData:
    @pytest.mark.parametrize("rubric", sorted(RUBRICS))
    def test_every_card_has_the_expected_part_of_speech(self, rubric):
        seed_file, part_of_speech, _ = RUBRICS[rubric]
        words = load_seed(seed_file)

        assert words
        assert all(w["part_of_speech"] == part_of_speech for w in words)

    @pytest.mark.parametrize("rubric", sorted(RUBRICS))
    def test_every_card_has_a_rule_and_an_example(self, rubric):
        seed_file, _, _ = RUBRICS[rubric]

        for word in load_seed(seed_file):
            assert word["translation"].strip(), word["lemma"]
            assert word["example"].strip(), word["lemma"]

    def test_grammar_cards_do_not_reuse_a_plain_vocabulary_lemma(self):
        """words.lemma is UNIQUE: a bare 'weil' would collide with the
        conjunction already in the dictionary and the card would be dropped as
        a duplicate, leaving the rubric short without any error."""
        plain = {
            "weil",
            "dass",
            "wenn",
            "als",
            "ob",
            "obwohl",
            "damit",
            "denn",
            "aber",
            "und",
            "oder",
            "doch",
            "gar nicht",
        }

        for rubric in (
            "wortstellung.json",
            "wo_wohin.json",
            "verschmelzung.json",
            "adjektive.json",
            "verbformen.json",
            "zeitangaben.json",
        ):
            for word in load_seed(rubric):
                assert word["lemma"].lower() not in plain, f"{rubric}: {word['lemma']}"

    def test_lemmas_are_unique_across_every_seed_file(self):
        lemmas = [w["lemma"].lower() for w in all_seed_words()]

        duplicates = {lemma for lemma in lemmas if lemmas.count(lemma) > 1}

        assert duplicates == set()


class TestTopicNumbering:
    """Topic slugs carry the Затык number so /stats_topics mirrors the tracker"""

    def test_zatyk_slugs_follow_the_numbering_convention(self):
        for word in all_seed_words():
            forms = json.loads(word.get("additional_forms") or "{}")
            topic = forms.get("topic", "")
            if topic.startswith("zatyk"):
                assert ZATYK_SLUG.match(topic), topic

    def test_the_red_tracker_entries_are_all_covered(self):
        """#21, #22, #23 are the topics marked 🔴 in the vault"""
        topics = {
            json.loads(w.get("additional_forms") or "{}").get("topic")
            for w in all_seed_words()
        }

        assert "zatyk-21-route-kasus" in topics
        assert "zatyk-22-satzfeld" in topics
        assert "zatyk-23-trennbare" in topics

    def test_the_yellow_tracker_entries_are_all_covered(self):
        """#24, #15 and #20 are the topics marked 🟡"""
        topics = {
            json.loads(w.get("additional_forms") or "{}").get("topic")
            for w in all_seed_words()
        }

        assert "zatyk-24-verb-praeposition" in topics
        assert "zatyk-15-verschmelzung" in topics
        assert "zatyk-20-wo-wohin" in topics

    def test_no_seed_file_still_uses_a_renamed_slug(self):
        retired = {
            "route-case",
            "word-order-vorfeld",
            "separable-route-verbs",
            "transport-verbs",
            "bis-zu",
            "reflexive-case",
            "pronoun-case",
            "article-case",
            "dativ-verbs",
        }
        topics = {
            json.loads(w.get("additional_forms") or "{}").get("topic")
            for w in all_seed_words()
        }

        assert not topics & retired

    def test_the_dativ_rubric_matches_its_renumbered_slug(self, db_manager):
        """The rubric filters on the slug, so a rename must not orphan it"""
        db_manager.add_words_with_details(TELEGRAM_ID, load_seed("dativ_verbs.json"))

        assert db_manager.get_dativ_verbs(TELEGRAM_ID, limit=100)


class TestRubricQueries:
    @pytest.mark.parametrize("rubric", sorted(RUBRICS))
    def test_the_rubric_returns_its_whole_set(self, seeded, rubric):
        seed_file, _, getter = RUBRICS[rubric]

        found = getattr(seeded, getter)(TELEGRAM_ID, limit=500)

        assert len(found) == len(load_seed(seed_file))

    def test_the_rubrics_never_overlap(self, seeded):
        seen: set[str] = set()

        for _, _, getter in RUBRICS.values():
            lemmas = {
                w["lemma"] for w in getattr(seeded, getter)(TELEGRAM_ID, limit=500)
            }
            assert not lemmas & seen
            seen |= lemmas

    def test_they_stay_out_of_the_plain_word_rubrics(self, seeded):
        for pos in ("noun", "verb", "adjective", "adverb"):
            found = seeded.get_words_by_part_of_speech(TELEGRAM_ID, pos, limit=500)
            assert found == [], pos

    def test_drills_do_not_leak_into_the_part_of_speech_rubrics(self, db_manager):
        """'pronoun case' shares a prefix with 'pronoun', which is a LIKE match"""
        db_manager.add_words_with_details(
            TELEGRAM_ID,
            load_seed("pronoun_case.json")
            + load_seed("adjektive.json")
            + load_seed("article_case.json")
            + [
                {
                    "lemma": "Katze",
                    "part_of_speech": "noun",
                    "article": "die",
                    "translation": "кошка",
                    "example": "Die Katze schläft.",
                }
            ],
        )

        assert (
            db_manager.get_words_by_part_of_speech(TELEGRAM_ID, "pronoun", limit=500)
            == []
        )
        assert (
            db_manager.get_words_by_part_of_speech(TELEGRAM_ID, "adjective", limit=500)
            == []
        )
        assert (
            len(db_manager.get_words_by_part_of_speech(TELEGRAM_ID, "noun", limit=500))
            == 1
        )

    def test_every_new_topic_is_reachable_by_slug(self, seeded):
        for slug in seeded.get_topic_slugs(TELEGRAM_ID):
            assert seeded.get_words_by_topic(TELEGRAM_ID, slug, limit=500), slug


class TestRendering:
    def test_a_rule_card_asks_how_it_is_done_right(self):
        card = load_seed("wortstellung.json")[0]

        front = format_study_card(card, 1, 10)

        assert front.startswith("1/10. Как правильно?")
        assert card["lemma"] in front

    def test_a_rule_card_hides_its_rule_until_the_reveal(self):
        for word in load_seed("verbformen.json"):
            assert word["translation"] not in format_study_card(word, 1, 10)

    def test_the_reveal_shows_the_rule_and_the_example(self):
        card = load_seed("wo_wohin.json")[0]

        back = SessionManager._format_answer_text(card)

        assert card["translation"] in back
        assert card["example"] in back
        assert "wo wohin" not in back


class TestCommands:
    @pytest.fixture
    def handlers(self):
        card = {
            "id": 1,
            "lemma": "zu + der",
            "part_of_speech": "verschmelzung",
            "article": None,
            "translation": "zur",
            "example": "Ich gehe zur Arbeit.",
            "repetitions": 0,
            "easiness_factor": 2.5,
            "interval_days": 1,
            "next_review_date": None,
            "last_reviewed": None,
        }
        mock_db = Mock(spec=DatabaseManager)
        mock_db.get_user_by_telegram_id.return_value = {"telegram_id": TELEGRAM_ID}
        for _, _, getter in RUBRICS.values():
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
        _, _, getter = RUBRICS[rubric]

        await getattr(handlers, f"study_{rubric}_command")(update, self._context())

        getattr(handlers.db_manager, getter).assert_called_once_with(
            TELEGRAM_ID, limit=10
        )
        handlers._start_study_session.assert_called_once()

    @pytest.mark.parametrize("rubric", sorted(RUBRICS))
    @pytest.mark.asyncio
    async def test_empty_rubric_explains_itself(self, handlers, update, rubric):
        _, _, getter = RUBRICS[rubric]
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
