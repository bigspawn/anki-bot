"""
Command handlers for the German Learning Bot
"""

import logging

from telegram import ReplyKeyboardRemove, Update
from telegram.ext import ContextTypes

from ...database import DatabaseManager
from ...spaced_repetition import SpacedRepetitionSystem
from ...text_parser import GermanTextParser
from ...utils import format_progress_stats
from ...word_processor import WordProcessor

logger = logging.getLogger(__name__)

# Curated list of the most frequent German verbs (standard DaF/Goethe-Institut
# frequency lists), used for the /study_common_verbs rubric.
COMMON_VERBS = [
    "sein", "haben", "werden", "können", "müssen", "sollen", "wollen", "mögen",
    "dürfen", "machen", "gehen", "kommen", "sagen", "geben", "sehen", "wissen",
    "finden", "denken", "nehmen", "lassen", "stehen", "bleiben", "liegen",
    "heißen", "halten", "bringen", "führen", "sprechen", "leben", "fahren",
    "meinen", "fragen", "kennen", "gelten", "stellen", "spielen", "arbeiten",
    "brauchen", "folgen", "lernen", "verstehen", "setzen", "erhalten",
    "schreiben", "laufen", "erklären", "sitzen", "ziehen", "scheinen",
    "fallen", "gehören", "erwarten", "verlieren", "wohnen", "beginnen",
    "versuchen", "treffen", "schaffen", "kaufen", "erreichen", "feiern",
    "essen", "trinken", "schlafen", "hören", "lesen", "warten", "helfen",
    "tragen", "öffnen", "schließen", "zeigen", "lieben", "reisen", "kochen",
    "tanzen", "singen", "lachen", "weinen", "glauben", "verlassen",
    "erzählen", "antworten", "verkaufen", "bezahlen", "bestellen",
    "wechseln", "entscheiden", "vergessen", "erinnern", "wünschen", "hoffen",
    "erfahren", "benutzen",
]

# German question words (Fragewörter), used for the /study_question_words rubric.
QUESTION_WORDS = [
    "wer", "was", "wo", "wohin", "woher", "wann", "warum", "wieso",
    "weshalb", "wie", "welcher", "welche", "welches", "wessen", "wem",
    "wen", "wieviel", "wie viel", "inwiefern", "inwieweit",
]

# Core German modal verbs, used for the /study_modal_verbs rubric.
MODAL_VERBS = [
    "können", "müssen", "dürfen", "sollen", "wollen", "mögen", "möchten",
]


class CommandHandlers:
    """Handles all bot commands"""

    def __init__(
        self,
        db_manager: DatabaseManager,
        word_processor: WordProcessor,
        text_parser: GermanTextParser,
        srs_system: SpacedRepetitionSystem,
        safe_reply_callback,
        process_text_callback,
        start_study_session_callback,
        state_manager=None,
        session_manager=None,
    ):
        self.db_manager = db_manager
        self.word_processor = word_processor
        self.text_parser = text_parser
        self.srs_system = srs_system
        self._safe_reply = safe_reply_callback
        self._process_text_for_user = process_text_callback
        self._start_study_session = start_study_session_callback
        self.state_manager = state_manager
        self.session_manager = session_manager

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        if not update.effective_user:
            return

        user = update.effective_user

        # Create or get user
        db_user = self.db_manager.get_user_by_telegram_id(user.id)
        if not db_user:
            db_user = self.db_manager.create_user(
                telegram_id=user.id,
                first_name=user.first_name,
                last_name=user.last_name,
                username=user.username,
            )

        welcome_message = f"""🎉 Привет, {user.first_name}!

Добро пожаловать в German Learning Bot! 🇩🇪

Я помогу вам изучать немецкие слова с помощью умной системы повторения.

🔤 <b>Как начать:</b>
1. Используйте /add и отправьте немецкий текст
2. Изучайте слова командой /study
3. Повторяйте слова по расписанию

📚 <b>Основные команды:</b>
/add - Добавить слова из текста
/study - Начать изучение
/help - Подробная справка

Просто отправьте мне любой немецкий текст, и я автоматически извлеку слова для изучения!"""

        await self._safe_reply(
            update,
            welcome_message,
            parse_mode="HTML",
            reply_markup=ReplyKeyboardRemove(),
        )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        if not update.effective_user:
            return
        help_message = """📖 Справка по командам German Learning Bot

🔤 <b>Добавление слов:</b>
/add - Добавить слова из немецкого текста (пошагово)
/add &lt;текст&gt; - Быстрое добавление слов
Пример: /add Ich gehe heute in die Schule

📚 <b>Изучение:</b>
/study - Изучение слов, готовых к повторению
/study_new - Только новые слова (ещё не изучались)
/study_difficult - Сложные слова (низкий рейтинг успешности)
/study_verbs - Только глаголы
/study_nouns - Только существительные
/study_adjectives - Только прилагательные
/study_adverbs - Только наречия
/study_pronouns - Только местоимения
/study_prepositions - Только предлоги
/study_conjunctions - Только союзы
/study_numerals - Только числительные
/study_interjections - Только междометия
/study_recent [N] - Последние N добавленных слов (по умолчанию 10)
/study_a1, /study_a2, /study_b1, /study_b2, /study_c1, /study_c2 - Слова по уровню CEFR
/study_common_verbs - Популярные немецкие глаголы из вашего списка
/study_question_words - Вопросительные слова (wer, was, wo...)
/study_modal_verbs - Модальные глаголы (können, müssen, wollen...)

📊 <b>Статистика:</b>
/stats - Подробная статистика изучения
Показывает общее количество слов, слова к повторению, новые слова и средний успех

⚙️ <b>Настройки:</b>
/settings - Настройки количества карточек в сессии и напоминаний

🤖 <b>Автоматическое добавление:</b>
Отправьте любой немецкий текст без команды, и я автоматически извлеку слова!

🎯 <b>Система оценок:</b>
❌ Снова - Не помню (повтор в текущей сессии)
➖ Трудно - Помню с трудом (повтор через короткое время)
➕ Хорошо - Помню хорошо (стандартный интервал)
✅ Легко - Помню легко (увеличенный интервал)

❓ Вопросы? Просто напишите /help"""

        await self._safe_reply(
            update, help_message, parse_mode="HTML", reply_markup=ReplyKeyboardRemove()
        )

    async def add_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /add command"""
        if not update.effective_user:
            return

        telegram_id = update.effective_user.id

        # Check for existing study session and interrupt it
        if self.session_manager:
            existing_session = self.session_manager.get_session(telegram_id)
            if existing_session:
                # Calculate partial statistics for the interrupted session
                accuracy = (
                    (
                        existing_session.correct_answers
                        / existing_session.total_answers
                        * 100
                    )
                    if existing_session.total_answers > 0
                    else 0
                )

                # Notify user about interrupted session
                interrupt_message = f"""⚠️ <b>Сессия изучения прервана</b>

📊 <b>Частичные результаты:</b>
• Слов изучено: <b>{existing_session.current_word_index}/{len(existing_session.words)}</b>
• Хорошо/легко вспомнил (➕✅): <b>{existing_session.correct_answers}/{existing_session.total_answers}</b>
• Точность: <b>{accuracy:.1f}%</b>

📝 Переходим к добавлению новых слов..."""

                await self._safe_reply(update, interrupt_message, parse_mode="HTML")

                # Clean up the interrupted session
                existing_session.timer.stop()
                if telegram_id in self.session_manager.user_sessions:
                    del self.session_manager.user_sessions[telegram_id]

        # Import here to avoid circular imports
        from ..state.user_state_manager import UserState

        # If arguments provided, process immediately (backward compatibility)
        if context.args:
            text = " ".join(context.args)
            await self._process_text_for_user(update, text)
            return

        # If no arguments, set state to wait for next message
        if self.state_manager:
            self.state_manager.set_state(telegram_id, UserState.WAITING_FOR_TEXT_TO_ADD)
            await self._safe_reply(
                update,
                "📝 Отправьте мне немецкий текст для анализа.\n\n"
                "Например: Das Wetter ist heute sehr schön.\n\n"
                "🕒 У вас есть 10 минут для отправки текста.",
                reply_markup=ReplyKeyboardRemove(),
            )
        else:
            # Fallback if state manager not available
            await self._safe_reply(
                update,
                "📝 Пожалуйста, укажите немецкий текст для анализа.\n\n"
                "Пример: /add Das Wetter ist heute sehr schön.",
                reply_markup=ReplyKeyboardRemove(),
            )

    async def study_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /study command"""
        if not update.effective_user:
            return

        user = update.effective_user

        # Get user from database
        db_user = self.db_manager.get_user_by_telegram_id(user.id)
        if not db_user:
            await self._safe_reply(
                update,
                "❌ Пользователь не найден. Используйте /start для регистрации.",
                reply_markup=ReplyKeyboardRemove(),
            )
            return

        # Get due words
        due_words = self.db_manager.get_due_words(db_user["telegram_id"], limit=10)

        if not due_words:
            await self._safe_reply(
                update,
                "🎉 Отлично! У вас нет слов для повторения сейчас.\n\n"
                "Используйте /study_new для изучения новых слов или /add для добавления новых.",
                reply_markup=ReplyKeyboardRemove(),
            )
            return

        # Start study session
        await self._start_study_session(update, due_words, "regular")

    async def study_new_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle /study_new command"""
        if not update.effective_user:
            return

        user = update.effective_user

        db_user = self.db_manager.get_user_by_telegram_id(user.id)
        if not db_user:
            await self._safe_reply(
                update,
                "❌ Пользователь не найден. Используйте /start для регистрации.",
                reply_markup=ReplyKeyboardRemove(),
            )
            return

        new_words = self.db_manager.get_new_words(db_user["telegram_id"], limit=10)

        if not new_words:
            await self._safe_reply(
                update,
                "📚 У вас нет новых слов для изучения.\n\n"
                "Используйте /add для добавления новых слов из текста.",
                reply_markup=ReplyKeyboardRemove(),
            )
            return

        await self._start_study_session(update, new_words, "new")

    async def study_difficult_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle /study_difficult command"""
        if not update.effective_user:
            return

        user = update.effective_user

        db_user = self.db_manager.get_user_by_telegram_id(user.id)
        if not db_user:
            await self._safe_reply(
                update,
                "❌ Пользователь не найден. Используйте /start для регистрации.",
                reply_markup=ReplyKeyboardRemove(),
            )
            return

        difficult_words = self.db_manager.get_difficult_words(
            db_user["telegram_id"], limit=10
        )

        if not difficult_words:
            await self._safe_reply(
                update,
                "🎯 У вас нет сложных слов для повторения!\n\n"
                "Используйте /study для обычного повторения.",
                reply_markup=ReplyKeyboardRemove(),
            )
            return

        await self._start_study_session(update, difficult_words, "difficult")

    async def study_verbs_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle /study_verbs command"""
        if not update.effective_user:
            return

        user = update.effective_user

        db_user = self.db_manager.get_user_by_telegram_id(user.id)
        if not db_user:
            await self._safe_reply(
                update,
                "❌ Пользователь не найден. Используйте /start для регистрации.",
                reply_markup=ReplyKeyboardRemove(),
            )
            return

        verb_words = self.db_manager.get_verb_words(db_user["telegram_id"], limit=10)

        if not verb_words:
            await self._safe_reply(
                update,
                "🔤 У вас нет глаголов для изучения.\n\n"
                "Используйте /add для добавления новых слов из текста.",
                reply_markup=ReplyKeyboardRemove(),
            )
            return

        await self._start_study_session(update, verb_words, "verbs")

    async def study_recent_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle /study_recent [N] command - study the last N added words"""
        if not update.effective_user:
            return

        user = update.effective_user

        db_user = self.db_manager.get_user_by_telegram_id(user.id)
        if not db_user:
            await self._safe_reply(
                update,
                "❌ Пользователь не найден. Используйте /start для регистрации.",
                reply_markup=ReplyKeyboardRemove(),
            )
            return

        limit = 10
        if context.args:
            try:
                limit = int(context.args[0])
            except ValueError:
                await self._safe_reply(
                    update,
                    "❌ Укажите число слов, например: /study_recent 20",
                    reply_markup=ReplyKeyboardRemove(),
                )
                return
        limit = max(1, min(limit, 200))

        recent_words = self.db_manager.get_recent_words(
            db_user["telegram_id"], limit=limit
        )

        if not recent_words:
            await self._safe_reply(
                update,
                "📚 У вас пока нет добавленных слов.\n\n"
                "Используйте /add для добавления новых слов из текста.",
                reply_markup=ReplyKeyboardRemove(),
            )
            return

        await self._start_study_session(update, recent_words, "recent")

    async def _study_pos(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE, part_of_speech: str
    ):
        """Shared logic for the flat /study_<pos> commands"""
        if not update.effective_user:
            return

        user = update.effective_user

        db_user = self.db_manager.get_user_by_telegram_id(user.id)
        if not db_user:
            await self._safe_reply(
                update,
                "❌ Пользователь не найден. Используйте /start для регистрации.",
                reply_markup=ReplyKeyboardRemove(),
            )
            return

        pos_words = self.db_manager.get_words_by_part_of_speech(
            db_user["telegram_id"], part_of_speech, limit=10
        )

        if not pos_words:
            await self._safe_reply(
                update,
                f"📚 У вас нет слов с частью речи «{part_of_speech}».\n\n"
                "Используйте /add для добавления новых слов из текста.",
                reply_markup=ReplyKeyboardRemove(),
            )
            return

        await self._start_study_session(update, pos_words, f"pos:{part_of_speech}")

    async def study_nouns_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle /study_nouns command"""
        await self._study_pos(update, context, "noun")

    async def study_adjectives_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle /study_adjectives command"""
        await self._study_pos(update, context, "adjective")

    async def study_adverbs_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle /study_adverbs command"""
        await self._study_pos(update, context, "adverb")

    async def study_pronouns_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle /study_pronouns command"""
        await self._study_pos(update, context, "pronoun")

    async def study_prepositions_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle /study_prepositions command"""
        await self._study_pos(update, context, "preposition")

    async def study_conjunctions_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle /study_conjunctions command"""
        await self._study_pos(update, context, "conjunction")

    async def study_numerals_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle /study_numerals command"""
        await self._study_pos(update, context, "numeral")

    async def study_interjections_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle /study_interjections command"""
        await self._study_pos(update, context, "interjection")

    async def _study_level(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE, level: str
    ):
        """Shared logic for the flat /study_<level> commands"""
        if not update.effective_user:
            return

        user = update.effective_user

        db_user = self.db_manager.get_user_by_telegram_id(user.id)
        if not db_user:
            await self._safe_reply(
                update,
                "❌ Пользователь не найден. Используйте /start для регистрации.",
                reply_markup=ReplyKeyboardRemove(),
            )
            return

        level_words = self.db_manager.get_words_by_level(
            db_user["telegram_id"], level, limit=10
        )

        if not level_words:
            await self._safe_reply(
                update,
                f"📚 У вас нет слов уровня «{level}».\n\n"
                "Слова получают уровень при добавлении через /add — "
                "старые слова, добавленные раньше, могут быть без уровня.",
                reply_markup=ReplyKeyboardRemove(),
            )
            return

        await self._start_study_session(update, level_words, f"level:{level}")

    async def study_a1_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle /study_a1 command"""
        await self._study_level(update, context, "A1")

    async def study_a2_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle /study_a2 command"""
        await self._study_level(update, context, "A2")

    async def study_b1_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle /study_b1 command"""
        await self._study_level(update, context, "B1")

    async def study_b2_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle /study_b2 command"""
        await self._study_level(update, context, "B2")

    async def study_c1_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle /study_c1 command"""
        await self._study_level(update, context, "C1")

    async def study_c2_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle /study_c2 command"""
        await self._study_level(update, context, "C2")

    async def study_common_verbs_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle /study_common_verbs command - study from a curated list of
        the most frequent German verbs"""
        if not update.effective_user:
            return

        user = update.effective_user

        db_user = self.db_manager.get_user_by_telegram_id(user.id)
        if not db_user:
            await self._safe_reply(
                update,
                "❌ Пользователь не найден. Используйте /start для регистрации.",
                reply_markup=ReplyKeyboardRemove(),
            )
            return

        common_verb_words = self.db_manager.get_words_by_lemma_set(
            db_user["telegram_id"], COMMON_VERBS, limit=10
        )

        if not common_verb_words:
            await self._safe_reply(
                update,
                "📚 Среди ваших слов нет популярных глаголов из списка.\n\n"
                "Используйте /add для добавления новых слов из текста.",
                reply_markup=ReplyKeyboardRemove(),
            )
            return

        await self._start_study_session(update, common_verb_words, "common_verbs")

    async def study_question_words_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle /study_question_words command - study German question words
        (Fragewörter)"""
        if not update.effective_user:
            return

        user = update.effective_user

        db_user = self.db_manager.get_user_by_telegram_id(user.id)
        if not db_user:
            await self._safe_reply(
                update,
                "❌ Пользователь не найден. Используйте /start для регистрации.",
                reply_markup=ReplyKeyboardRemove(),
            )
            return

        question_words = self.db_manager.get_words_by_lemma_set(
            db_user["telegram_id"], QUESTION_WORDS, limit=10
        )

        if not question_words:
            await self._safe_reply(
                update,
                "📚 Среди ваших слов нет вопросительных слов из списка.\n\n"
                "Используйте /add для добавления новых слов из текста.",
                reply_markup=ReplyKeyboardRemove(),
            )
            return

        await self._start_study_session(update, question_words, "question_words")

    async def study_modal_verbs_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle /study_modal_verbs command - study German modal verbs"""
        if not update.effective_user:
            return

        user = update.effective_user

        db_user = self.db_manager.get_user_by_telegram_id(user.id)
        if not db_user:
            await self._safe_reply(
                update,
                "❌ Пользователь не найден. Используйте /start для регистрации.",
                reply_markup=ReplyKeyboardRemove(),
            )
            return

        modal_verb_words = self.db_manager.get_words_by_lemma_set(
            db_user["telegram_id"], MODAL_VERBS, limit=10
        )

        if not modal_verb_words:
            await self._safe_reply(
                update,
                "📚 Среди ваших слов нет модальных глаголов из списка.\n\n"
                "Используйте /add для добавления новых слов из текста.",
                reply_markup=ReplyKeyboardRemove(),
            )
            return

        await self._start_study_session(update, modal_verb_words, "modal_verbs")

    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stats command"""
        if not update.effective_user:
            return

        user = update.effective_user

        db_user = self.db_manager.get_user_by_telegram_id(user.id)
        if not db_user:
            await self._safe_reply(
                update,
                "❌ Пользователь не найден. Используйте /start для регистрации.",
                reply_markup=ReplyKeyboardRemove(),
            )
            return

        stats = self.db_manager.get_user_stats(db_user["telegram_id"])
        stats_message = format_progress_stats(stats)

        await self._safe_reply(
            update, stats_message, reply_markup=ReplyKeyboardRemove()
        )

    async def settings_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle /settings command"""
        if not update.effective_user:
            return

        await self._safe_reply(
            update,
            "⚙️ Настройки (в разработке)\n\n"
            "Скоро здесь будут доступны настройки:\n"
            "• Количество карточек в сессии\n"
            "• Время ежедневных напоминаний\n"
            "• Часовой пояс\n"
            "• Сложность изучения",
            reply_markup=ReplyKeyboardRemove(),
        )
