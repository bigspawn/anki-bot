#!/usr/bin/env python3
"""
Tests for the route/grammar drill rubrics and topic tracking:
seed/route_phrases.json, seed/cloze_route.json, seed/error_fix_route.json,
/study_route, /study_cloze, /study_topic and /stats_topics.
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
from src.utils import format_study_card, format_topic_stats

REPO_ROOT = Path(__file__).resolve().parents[1]
ROUTE_PATH = REPO_ROOT / "seed" / "route_phrases.json"
CLOZE_PATH = REPO_ROOT / "seed" / "cloze_route.json"
ERROR_FIX_PATH = REPO_ROOT / "seed" / "error_fix_route.json"

TELEGRAM_ID = 555000111


def load_script(name: str):
    """Import a scripts/*.py module by path (scripts/ is not a package)"""
    path = REPO_ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def route_words():
    return json.loads(ROUTE_PATH.read_text(encoding="utf-8"))


@pytest.fixture
def cloze_words():
    return json.loads(CLOZE_PATH.read_text(encoding="utf-8"))


@pytest.fixture
def error_fix_words():
    return json.loads(ERROR_FIX_PATH.read_text(encoding="utf-8"))


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
def seeded_db(db_manager, route_words, cloze_words, error_fix_words):
    db_manager.add_words_with_details(
        TELEGRAM_ID, route_words + cloze_words + error_fix_words
    )
    return db_manager


class TestSeedData:
    """The authored card sets must stay loadable and self-consistent"""

    def test_route_cards_are_tagged_as_route_phrases(self, route_words):
        assert route_words
        assert all(w["part_of_speech"] == "route phrase" for w in route_words)

    def test_every_card_carries_a_topic_slug(
        self, route_words, cloze_words, error_fix_words
    ):
        for word in route_words + cloze_words + error_fix_words:
            forms = json.loads(word["additional_forms"])
            topic = forms.get("topic")
            assert topic, f"{word['lemma']} has no topic"
            assert topic == topic.lower(), f"{topic} is not kebab-case"
            assert " " not in topic

    def test_cloze_cards_carry_a_prompt_and_an_answer(self, cloze_words):
        assert cloze_words
        for word in cloze_words:
            assert "___" in word["lemma"], f"{word['lemma']} has no gap"
            forms = json.loads(word["additional_forms"])
            assert forms.get("answer"), f"{word['lemma']} has no answer"

    def test_cloze_example_resolves_the_gap(self, cloze_words):
        for word in cloze_words:
            assert "___" not in word["example"]

    def test_error_fix_cards_show_the_wrong_sentence(self, error_fix_words):
        assert error_fix_words
        for word in error_fix_words:
            assert word["part_of_speech"] == "error fix"
            assert word["lemma"].startswith("❌ ")

    def test_lemmas_are_unique_across_the_new_sets(
        self, route_words, cloze_words, error_fix_words
    ):
        lemmas = [
            w["lemma"].lower() for w in route_words + cloze_words + error_fix_words
        ]
        assert len(lemmas) == len(set(lemmas))


class TestSeedValidation:
    """scripts/seed_words.py rejects unusable cloze cards before writing"""

    def test_authored_sets_report_no_problems(
        self, route_words, cloze_words, error_fix_words
    ):
        seed = load_script("seed_words")
        assert seed.validate_words(route_words + cloze_words + error_fix_words) == []

    def test_cloze_without_answer_is_rejected(self):
        seed = load_script("seed_words")
        problems = seed.validate_words(
            [
                {
                    "lemma": "Vor ___ Bahnhof links.",
                    "part_of_speech": "cloze",
                    "additional_forms": json.dumps({"topic": "zatyk-21-route-kasus"}),
                }
            ]
        )
        assert len(problems) == 1
        assert "without additional_forms.answer" in problems[0]

    def test_cloze_with_broken_json_is_rejected(self):
        seed = load_script("seed_words")
        problems = seed.validate_words(
            [
                {
                    "lemma": "Vor ___ Bahnhof links.",
                    "part_of_speech": "cloze",
                    "additional_forms": "{not json",
                }
            ]
        )
        assert len(problems) == 1
        assert "not valid JSON" in problems[0]

    def test_non_cloze_cards_need_no_answer(self):
        seed = load_script("seed_words")
        assert (
            seed.validate_words(
                [
                    {
                        "lemma": "❌ bis zu der Kirche",
                        "part_of_speech": "error fix",
                        "additional_forms": json.dumps({"topic": "bis-zu"}),
                    }
                ]
            )
            == []
        )

    def test_seeding_aborts_on_an_invalid_cloze_card(self, db_manager, tmp_path):
        seed = load_script("seed_words")
        bad = tmp_path / "bad.json"
        bad.write_text(
            json.dumps(
                [
                    {
                        "lemma": "Vor ___ Bahnhof links.",
                        "part_of_speech": "cloze",
                        "translation": "dem — Dativ",
                        "example": "Vor dem Bahnhof links.",
                        "additional_forms": json.dumps(
                            {"topic": "zatyk-21-route-kasus"}
                        ),
                    }
                ]
            ),
            encoding="utf-8",
        )

        assert (
            seed.seed_words(db_manager.db_connection.db_path, TELEGRAM_ID, [str(bad)])
            is False
        )
        assert db_manager.get_cloze_words(TELEGRAM_ID, limit=10) == []


class TestRubricQueries:
    """The new study filters return exactly their own card type"""

    def test_study_route_returns_only_route_phrases(self, seeded_db, route_words):
        words = seeded_db.get_words_by_part_of_speech(
            TELEGRAM_ID, "route phrase", limit=100
        )

        assert len(words) == len(route_words)
        assert all(w["part_of_speech"] == "route phrase" for w in words)

    def test_study_cloze_returns_cloze_and_error_fix(
        self, seeded_db, cloze_words, error_fix_words
    ):
        words = seeded_db.get_cloze_words(TELEGRAM_ID, limit=100)

        assert len(words) == len(cloze_words) + len(error_fix_words)
        assert {w["part_of_speech"] for w in words} == {"cloze", "error fix"}

    def test_rubrics_do_not_leak_into_each_other(self, seeded_db):
        route = {
            w["lemma"]
            for w in seeded_db.get_words_by_part_of_speech(
                TELEGRAM_ID, "route phrase", limit=100
            )
        }
        cloze = {w["lemma"] for w in seeded_db.get_cloze_words(TELEGRAM_ID, limit=100)}

        assert not route & cloze

    def test_drills_stay_out_of_the_part_of_speech_rubrics(self, seeded_db):
        for pos in ("noun", "verb", "adverb", "preposition"):
            words = seeded_db.get_words_by_part_of_speech(TELEGRAM_ID, pos, limit=100)
            assert all(
                w["part_of_speech"] not in ("cloze", "error fix", "route phrase")
                for w in words
            ), pos

    def test_study_topic_ignores_the_due_date(self, seeded_db):
        # Push every card far into the future: a topic session must still find them
        with seeded_db.get_connection() as conn:
            conn.execute(
                "UPDATE learning_progress SET next_review_date = datetime('now', '+30 days')"
            )
            conn.commit()

        assert seeded_db.get_due_words(TELEGRAM_ID, limit=100) == []
        assert seeded_db.get_words_by_topic(
            TELEGRAM_ID, "zatyk-21-route-kasus", limit=100
        )

    def test_study_topic_is_case_insensitive(self, seeded_db):
        assert seeded_db.get_words_by_topic(
            TELEGRAM_ID, "ZATYK-21-ROUTE-KASUS", limit=100
        )

    def test_unknown_topic_returns_nothing(self, seeded_db):
        assert (
            seeded_db.get_words_by_topic(TELEGRAM_ID, "no-such-topic", limit=10) == []
        )

    def test_topic_slugs_are_listed_alphabetically(self, seeded_db):
        slugs = seeded_db.get_topic_slugs(TELEGRAM_ID)

        assert "zatyk-21-route-kasus" in slugs
        assert "zatyk-24-verb-praeposition" in slugs
        assert slugs == sorted(slugs)

    def test_queries_survive_cards_with_non_json_additional_forms(self, seeded_db):
        # Older rows store plain strings there; json_extract must not abort
        with seeded_db.get_connection() as conn:
            conn.execute(
                "INSERT INTO words (lemma, part_of_speech, translation, example, additional_forms)"
                " VALUES ('kaputt', 'adjective', 'сломанный', 'Es ist kaputt.', 'not json at all')"
            )
            word_id = conn.execute(
                "SELECT id FROM words WHERE lemma = 'kaputt'"
            ).fetchone()["id"]
            conn.execute(
                "INSERT INTO learning_progress (telegram_id, word_id) VALUES (?, ?)",
                (TELEGRAM_ID, word_id),
            )
            conn.commit()

        assert seeded_db.get_words_by_topic(
            TELEGRAM_ID, "zatyk-21-route-kasus", limit=100
        )
        assert seeded_db.get_topic_slugs(TELEGRAM_ID)
        assert seeded_db.get_topic_stats(TELEGRAM_ID) == []

    def test_reseeding_adds_no_duplicates(
        self, seeded_db, route_words, cloze_words, error_fix_words
    ):
        before = len(seeded_db.get_words_by_user(TELEGRAM_ID))

        result = seeded_db.add_words_with_details(
            TELEGRAM_ID, route_words + cloze_words + error_fix_words
        )

        assert result["added"] == []
        assert len(seeded_db.get_words_by_user(TELEGRAM_ID)) == before


class TestTopicAggregation:
    """/stats_topics ranks topics by how badly they go, worst first"""

    @pytest.fixture
    def three_topics(self, db_manager):
        cards = []
        for topic, count in (("bad-topic", 2), ("mixed-topic", 2), ("good-topic", 2)):
            for index in range(count):
                cards.append(
                    {
                        "lemma": f"{topic}-{index}",
                        "part_of_speech": "cloze",
                        "translation": f"перевод {topic} {index}",
                        "example": f"Beispiel {topic} {index}.",
                        "additional_forms": json.dumps({"answer": "x", "topic": topic}),
                    }
                )
        # A topic nobody has reviewed yet must not show up at all
        cards.append(
            {
                "lemma": "untouched-card",
                "part_of_speech": "cloze",
                "translation": "нетронутая карточка",
                "example": "Unberührt.",
                "additional_forms": json.dumps(
                    {"answer": "x", "topic": "untouched-topic"}
                ),
            }
        )
        db_manager.add_words_with_details(TELEGRAM_ID, cards)

        ratings = {"bad-topic": [1, 1], "mixed-topic": [1, 4], "good-topic": [4, 4]}
        for topic, topic_ratings in ratings.items():
            words = sorted(
                db_manager.get_words_by_topic(TELEGRAM_ID, topic, limit=10),
                key=lambda w: w["lemma"],
            )
            for word, rating in zip(words, topic_ratings, strict=True):
                db_manager.update_learning_progress(TELEGRAM_ID, word["id"], rating)

        return db_manager

    def test_topics_are_sorted_worst_first(self, three_topics):
        rows = three_topics.get_topic_stats(TELEGRAM_ID)

        assert [r["topic"] for r in rows] == [
            "bad-topic",
            "mixed-topic",
            "good-topic",
        ]

    def test_accuracy_is_the_share_of_good_ratings(self, three_topics):
        rows = {r["topic"]: r for r in three_topics.get_topic_stats(TELEGRAM_ID)}

        assert rows["bad-topic"]["accuracy"] == 0.0
        assert rows["mixed-topic"]["accuracy"] == 0.5
        assert rows["good-topic"]["accuracy"] == 1.0

    def test_cards_and_reviews_are_counted_per_topic(self, three_topics):
        rows = {r["topic"]: r for r in three_topics.get_topic_stats(TELEGRAM_ID)}

        assert rows["mixed-topic"]["cards"] == 2
        assert rows["mixed-topic"]["reviews"] == 2

    def test_repeated_reviews_of_one_card_do_not_inflate_the_card_count(
        self, three_topics
    ):
        word = three_topics.get_words_by_topic(TELEGRAM_ID, "bad-topic", limit=1)[0]
        three_topics.update_learning_progress(TELEGRAM_ID, word["id"], 1)

        rows = {r["topic"]: r for r in three_topics.get_topic_stats(TELEGRAM_ID)}

        assert rows["bad-topic"]["cards"] == 2
        assert rows["bad-topic"]["reviews"] == 3

    def test_worst_card_is_the_one_that_keeps_failing(self, three_topics):
        rows = {r["topic"]: r for r in three_topics.get_topic_stats(TELEGRAM_ID)}

        # mixed-topic-0 was rated 1, mixed-topic-1 was rated 4
        assert rows["mixed-topic"]["worst_card"] == "mixed-topic-0"

    def test_mean_easiness_factor_is_reported(self, three_topics):
        rows = {r["topic"]: r for r in three_topics.get_topic_stats(TELEGRAM_ID)}

        assert rows["bad-topic"]["mean_easiness_factor"] < 2.5
        assert rows["good-topic"]["mean_easiness_factor"] >= 2.5

    def test_topics_without_reviews_are_skipped(self, three_topics):
        topics = {r["topic"] for r in three_topics.get_topic_stats(TELEGRAM_ID)}

        assert "untouched-topic" not in topics

    def test_stats_are_isolated_per_user(self, three_topics):
        assert three_topics.get_topic_stats(TELEGRAM_ID + 1) == []


class TestTopicStatsFormatting:
    """format_topic_stats renders one readable block per topic"""

    def test_empty_stats_explain_where_topics_come_from(self):
        assert "нет статистики по темам" in format_topic_stats([])

    def test_each_topic_shows_its_numbers_and_a_restudy_command(self):
        text = format_topic_stats(
            [
                {
                    "topic": "zatyk-21-route-kasus",
                    "cards": 18,
                    "reviews": 6,
                    "accuracy": 0.5,
                    "mean_easiness_factor": 2.34,
                    "worst_card": "an der Ampel",
                }
            ]
        )

        assert "zatyk-21-route-kasus" in text
        assert "18" in text
        assert "50%" in text
        assert "2.34" in text
        assert "an der Ampel" in text
        assert "/study_topic zatyk-21-route-kasus" in text


class TestDrillCardRendering:
    """A drill hides its answer until the reveal"""

    @pytest.fixture
    def cloze_card(self):
        return {
            "id": 1,
            "lemma": "Biegen Sie ___ Supermarkt rechts ab.",
            "part_of_speech": "cloze",
            "article": None,
            "translation": "am (an + dem) — ориентир поворота → Dativ",
            "example": "Biegen Sie am Supermarkt rechts ab.",
            "additional_forms": json.dumps(
                {"answer": "am", "topic": "zatyk-21-route-kasus"}
            ),
        }

    @pytest.fixture
    def error_fix_card(self):
        return {
            "id": 2,
            "lemma": "❌ bis zu der Kirche",
            "part_of_speech": "error fix",
            "article": None,
            "translation": "bis zur Kirche — zu + der = zur",
            "example": "bis zur Kirche",
            "additional_forms": json.dumps({"topic": "bis-zu"}),
        }

    def test_prompt_shows_the_gapped_sentence(self, cloze_card):
        prompt = format_study_card(cloze_card, 1, 10)

        assert "1/10" in prompt
        assert "Заполните пропуск" in prompt
        assert cloze_card["lemma"] in prompt

    def test_prompt_never_leaks_the_answer(self, cloze_card):
        prompt = format_study_card(cloze_card, 1, 10)

        assert cloze_card["translation"] not in prompt
        assert cloze_card["example"] not in prompt

    def test_error_fix_prompt_asks_for_a_correction(self, error_fix_card):
        prompt = format_study_card(error_fix_card, 3, 5)

        assert "Исправьте ошибку" in prompt
        assert error_fix_card["lemma"] in prompt
        assert error_fix_card["translation"] not in prompt

    def test_reveal_shows_the_rule_then_the_fixed_sentence(self, cloze_card):
        reveal = SessionManager._format_answer_text(cloze_card)

        assert reveal.index(cloze_card["translation"]) < reveal.index(
            cloze_card["example"]
        )

    def test_reveal_omits_the_article_and_part_of_speech_line(self, cloze_card):
        reveal = SessionManager._format_answer_text(cloze_card)

        assert "cloze" not in reveal

    def test_error_fix_reveal_shows_the_correction(self, error_fix_card):
        reveal = SessionManager._format_answer_text(error_fix_card)

        assert error_fix_card["translation"] in reveal
        assert "error fix" not in reveal

    def test_ordinary_words_keep_the_old_card(self):
        word = {
            "id": 3,
            "lemma": "Haus",
            "part_of_speech": "noun",
            "article": "das",
            "translation": "дом",
            "example": "Das Haus ist groß.",
            "additional_forms": None,
        }

        assert "Какой артикль" in format_study_card(word, 1, 10)
        assert "das Haus - noun" in SessionManager._format_answer_text(word)


class TestDrillCommands:
    """The command handlers guard the same edge cases as the older rubrics"""

    @pytest.fixture
    def mock_db_manager(self):
        card = {
            "id": 1,
            "lemma": "am Supermarkt abbiegen",
            "part_of_speech": "route phrase",
            "article": None,
            "translation": "повернуть у супермаркета",
            "example": "Biegen Sie am Supermarkt rechts ab.",
            "repetitions": 0,
            "easiness_factor": 2.5,
            "interval_days": 1,
            "next_review_date": None,
            "last_reviewed": None,
        }

        mock_db = Mock(spec=DatabaseManager)
        mock_db.get_user_by_telegram_id.return_value = {
            "telegram_id": TELEGRAM_ID,
            "username": "testuser",
            "created_at": "2023-01-01",
        }
        mock_db.get_words_by_part_of_speech.return_value = [card]
        mock_db.get_cloze_words.return_value = [card]
        mock_db.get_words_by_topic.return_value = [card]
        mock_db.get_topic_slugs.return_value = [
            "zatyk-21-route-kasus",
            "transport-verbs",
        ]
        mock_db.get_topic_stats.return_value = [
            {
                "topic": "zatyk-21-route-kasus",
                "cards": 2,
                "reviews": 4,
                "accuracy": 0.25,
                "mean_easiness_factor": 2.1,
                "worst_card": "an der Ampel",
            }
        ]
        return mock_db

    @pytest.fixture
    def handlers(self, mock_db_manager):
        handlers = CommandHandlers(
            db_manager=mock_db_manager,
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
    def mock_update(self):
        update = Mock(spec=Update)
        update.effective_user = Mock(spec=User)
        update.effective_user.id = TELEGRAM_ID
        update.effective_user.username = "testuser"
        update.message = Mock(spec=Message)
        return update

    def _context(self, args=None):
        context = Mock(spec=ContextTypes.DEFAULT_TYPE)
        context.args = args
        return context

    @pytest.mark.asyncio
    async def test_study_route_filters_route_phrases(self, handlers, mock_update):
        await handlers.study_route_command(mock_update, self._context())

        handlers.db_manager.get_words_by_part_of_speech.assert_called_once_with(
            TELEGRAM_ID, "route phrase", limit=10
        )
        handlers._start_study_session.assert_called_once()

    @pytest.mark.asyncio
    async def test_study_route_without_cards(self, handlers, mock_update):
        handlers.db_manager.get_words_by_part_of_speech.return_value = []

        await handlers.study_route_command(mock_update, self._context())

        handlers._start_study_session.assert_not_called()
        assert "нет фраз для описания маршрута" in handlers._safe_reply.call_args[0][1]

    @pytest.mark.asyncio
    async def test_study_cloze_starts_a_session(self, handlers, mock_update):
        await handlers.study_cloze_command(mock_update, self._context())

        handlers.db_manager.get_cloze_words.assert_called_once_with(
            TELEGRAM_ID, limit=10
        )
        handlers._start_study_session.assert_called_once()

    @pytest.mark.asyncio
    async def test_study_cloze_without_cards(self, handlers, mock_update):
        handlers.db_manager.get_cloze_words.return_value = []

        await handlers.study_cloze_command(mock_update, self._context())

        handlers._start_study_session.assert_not_called()
        assert "нет упражнений с пропусками" in handlers._safe_reply.call_args[0][1]

    @pytest.mark.asyncio
    async def test_study_topic_studies_the_requested_slug(self, handlers, mock_update):
        await handlers.study_topic_command(
            mock_update, self._context(["zatyk-21-route-kasus"])
        )

        handlers.db_manager.get_words_by_topic.assert_called_once_with(
            TELEGRAM_ID, "zatyk-21-route-kasus", limit=10
        )
        handlers._start_study_session.assert_called_once()

    @pytest.mark.asyncio
    async def test_study_topic_without_a_slug_lists_the_topics(
        self, handlers, mock_update
    ):
        await handlers.study_topic_command(mock_update, self._context())

        handlers.db_manager.get_words_by_topic.assert_not_called()
        handlers._start_study_session.assert_not_called()
        message = handlers._safe_reply.call_args[0][1]
        assert "zatyk-21-route-kasus" in message
        assert "transport-verbs" in message

    @pytest.mark.asyncio
    async def test_unknown_slug_lists_the_available_ones(self, handlers, mock_update):
        handlers.db_manager.get_words_by_topic.return_value = []

        await handlers.study_topic_command(mock_update, self._context(["nope"]))

        handlers._start_study_session.assert_not_called()
        message = handlers._safe_reply.call_args[0][1]
        assert "«nope»" in message
        assert "zatyk-21-route-kasus" in message

    @pytest.mark.asyncio
    async def test_topic_hint_without_any_topics(self, handlers, mock_update):
        handlers.db_manager.get_topic_slugs.return_value = []
        handlers.db_manager.get_words_by_topic.return_value = []

        await handlers.study_topic_command(mock_update, self._context(["nope"]))

        assert "нет карточек с темами" in handlers._safe_reply.call_args[0][1]

    @pytest.mark.asyncio
    async def test_stats_topics_renders_the_breakdown(self, handlers, mock_update):
        await handlers.stats_topics_command(mock_update, self._context())

        handlers.db_manager.get_topic_stats.assert_called_once_with(TELEGRAM_ID)
        message = handlers._safe_reply.call_args[0][1]
        assert "zatyk-21-route-kasus" in message
        assert "25%" in message

    @pytest.mark.parametrize(
        "command_name",
        [
            "study_route_command",
            "study_cloze_command",
            "study_topic_command",
            "stats_topics_command",
        ],
    )
    @pytest.mark.asyncio
    async def test_unregistered_user_is_told_to_start(
        self, handlers, mock_update, command_name
    ):
        handlers.db_manager.get_user_by_telegram_id.return_value = None

        await getattr(handlers, command_name)(
            mock_update, self._context(["zatyk-21-route-kasus"])
        )

        handlers._start_study_session.assert_not_called()
        assert "❌ Пользователь не найден" in handlers._safe_reply.call_args[0][1]

    @pytest.mark.parametrize(
        "command_name",
        [
            "study_route_command",
            "study_cloze_command",
            "study_topic_command",
            "stats_topics_command",
        ],
    )
    @pytest.mark.asyncio
    async def test_update_without_a_user_does_nothing(self, handlers, command_name):
        update = Mock(spec=Update)
        update.effective_user = None

        await getattr(handlers, command_name)(update, self._context())

        handlers.db_manager.get_user_by_telegram_id.assert_not_called()
        handlers._safe_reply.assert_not_called()
