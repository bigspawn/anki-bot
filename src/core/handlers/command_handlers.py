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
                elapsed_time = existing_session.timer.get_elapsed_time()
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
• Правильных ответов: <b>{existing_session.correct_answers}/{existing_session.total_answers}</b>
• Точность: <b>{accuracy:.1f}%</b>
• Время: <b>{elapsed_time:.1f}с</b>

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
