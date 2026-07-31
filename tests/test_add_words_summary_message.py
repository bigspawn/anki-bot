#!/usr/bin/env python3
"""
Tests for the summary message shown after /add.

Regression: with "Hinterhaus Hof Mülltonnen Ort" the bot reported 4 found,
2 added, 1 already learned — "Mülltonnen" lemmatized to the already learned
"Mülltonne" and disappeared from both counters.
"""

import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.bot_handler import BotHandler
from src.config import Settings
from src.core.database.database_manager import DatabaseManager
from src.word_processor import ProcessedWord

TELEGRAM_ID = 739529


def processed(lemma: str, translation: str, article: str | None = None):
    return ProcessedWord(
        word=lemma.lower(),
        lemma=lemma,
        part_of_speech="noun",
        article=article,
        translation=translation,
        example=f"Das ist das {lemma}.",
        additional_forms=None,
        confidence=0.9,
    )


@pytest.fixture
def db_manager():
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
    temp_file.close()

    manager = DatabaseManager(temp_file.name)
    manager.init_database()
    manager.create_user(telegram_id=TELEGRAM_ID, first_name="Igor")

    yield manager

    os.unlink(temp_file.name)


async def run_add(db_manager, extracted, processed_words):
    """Run the /add flow and return the final message text"""
    settings = Settings(telegram_bot_token="test-token", openai_api_key="test-key")

    with (
        patch("src.bot_handler.get_db_manager", return_value=db_manager),
        patch("src.bot_handler.get_word_processor", return_value=AsyncMock()),
        patch("src.bot_handler.get_text_parser", return_value=MagicMock()),
        patch("src.bot_handler.get_srs_system", return_value=MagicMock()),
    ):
        bot_handler = BotHandler(settings=settings)

    text_parser = MagicMock()
    text_parser.extract_words.return_value = extracted

    word_processor = AsyncMock()
    word_processor.process_text = AsyncMock(return_value=processed_words)

    with (
        patch.object(bot_handler, "db_manager", db_manager),
        patch.object(bot_handler, "word_processor", word_processor),
        patch.object(bot_handler, "text_parser", text_parser),
    ):
        update = MagicMock()
        update.effective_user.id = TELEGRAM_ID
        update.effective_user.first_name = "Igor"

        bot_handler._safe_reply = AsyncMock()
        bot_handler._safe_edit_message = AsyncMock()

        await bot_handler._process_text_for_user(update, " ".join(extracted))

    # The last edit carries the summary
    return bot_handler._safe_edit_message.call_args[0][1]


class TestAddSummaryCounters:
    @pytest.mark.asyncio
    async def test_lemma_duplicate_counts_as_already_learned(self, db_manager):
        """The reported bug: 4 found must not be reported as 2 + 1"""
        db_manager.add_words_to_user(
            TELEGRAM_ID,
            [
                {"lemma": "Hof", "part_of_speech": "noun", "translation": "двор"},
                {
                    "lemma": "Mülltonne",
                    "part_of_speech": "noun",
                    "translation": "мусорный контейнер",
                },
            ],
        )

        message = await run_add(
            db_manager,
            ["Hinterhaus", "Hof", "Mülltonnen", "Ort"],
            [
                processed("Hinterhaus", "задний двор"),
                processed("Mülltonne", "мусорный контейнер"),
                processed("Ort", "место"),
            ],
        )

        assert "• Всего слов найдено: <b>4</b>" in message
        assert "• Новых добавлено: <b>2</b>" in message
        assert "• Уже изучаются: <b>2</b>" in message
        assert "Не удалось обработать" not in message

    @pytest.mark.asyncio
    async def test_duplicate_lemma_is_listed_among_learned_words(self, db_manager):
        db_manager.add_words_to_user(
            TELEGRAM_ID,
            [
                {
                    "lemma": "Mülltonne",
                    "part_of_speech": "noun",
                    "translation": "мусорный контейнер",
                }
            ],
        )

        message = await run_add(
            db_manager,
            ["Mülltonnen", "Ort"],
            [
                processed("Mülltonne", "мусорный контейнер"),
                processed("Ort", "место"),
            ],
        )

        assert "📚 <b>Уже изучаемые слова:</b>" in message
        assert "<i>Mülltonne</i> — мусорный контейнер" in message

    @pytest.mark.asyncio
    async def test_unprocessed_line_appears_when_a_word_is_lost(self, db_manager):
        """A word with an unusable translation is skipped on insert"""
        message = await run_add(
            db_manager,
            ["Hinterhaus", "Ort"],
            [
                processed("Hinterhaus", "задний двор"),
                processed("Ort", "[translation unavailable]"),
            ],
        )

        assert "• Всего слов найдено: <b>2</b>" in message
        assert "• Новых добавлено: <b>1</b>" in message
        assert "• Уже изучаются: <b>0</b>" in message
        assert "• Не удалось обработать: <b>1</b>" in message

    @pytest.mark.asyncio
    async def test_all_words_new_counters(self, db_manager):
        message = await run_add(
            db_manager,
            ["Hinterhaus", "Ort"],
            [processed("Hinterhaus", "задний двор"), processed("Ort", "место")],
        )

        assert "• Всего слов найдено: <b>2</b>" in message
        assert "• Новых добавлено: <b>2</b>" in message
        assert "• Уже изучаются: <b>0</b>" in message
        assert "Не удалось обработать" not in message


class TestAddedWordsList:
    @pytest.mark.asyncio
    async def test_added_words_are_listed_with_translations(self, db_manager):
        message = await run_add(
            db_manager,
            ["Hinterhaus", "Ort"],
            [
                processed("Hinterhaus", "задний двор"),
                processed("Ort", "место"),
            ],
        )

        assert "🆕 <b>Добавленные слова:</b>" in message
        assert "<i>Hinterhaus</i> — задний двор" in message
        assert "<i>Ort</i> — место" in message

    @pytest.mark.asyncio
    async def test_added_list_shows_the_article_for_nouns(self, db_manager):
        message = await run_add(
            db_manager,
            ["Mülltonne"],
            [processed("Mülltonne", "мусорный контейнер", article="die")],
        )

        assert "• die <i>Mülltonne</i> — мусорный контейнер" in message

    @pytest.mark.asyncio
    async def test_skipped_words_are_not_listed_as_added(self, db_manager):
        db_manager.add_words_to_user(
            TELEGRAM_ID,
            [
                {
                    "lemma": "Mülltonne",
                    "part_of_speech": "noun",
                    "translation": "мусорный контейнер",
                }
            ],
        )

        message = await run_add(
            db_manager,
            ["Mülltonnen", "Ort"],
            [
                processed("Mülltonne", "мусорный контейнер"),
                processed("Ort", "место"),
            ],
        )

        added_block = message.split("🆕 <b>Добавленные слова:</b>")[1].split("📚")[0]
        assert "Ort" in added_block
        assert "Mülltonne" not in added_block
