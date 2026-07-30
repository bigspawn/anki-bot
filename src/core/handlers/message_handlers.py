"""
Message handlers for the German Learning Bot
"""

import logging

from telegram import ReplyKeyboardRemove, Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


class MessageHandlers:
    """Handles text messages and callback queries"""

    def __init__(
        self,
        safe_reply_callback,
        process_text_callback,
        handle_study_callback,
        state_manager=None,
        session_manager=None,
    ):
        self._safe_reply = safe_reply_callback
        self._process_text_for_user = process_text_callback
        self._handle_study_callback = handle_study_callback
        self.state_manager = state_manager
        self.session_manager = session_manager

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text messages (auto-add words)"""
        if not update.message or not update.effective_user:
            return

        text = update.message.text
        telegram_id = update.effective_user.id

        # Check for existing study session and interrupt it when processing text
        interrupted_session = False
        if self.session_manager and text and len(text.strip()) >= 3:
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
                interrupted_session = True

        # Check if user is waiting for text to add
        if self.state_manager and self.state_manager.is_waiting_for_text(telegram_id):
            # Clear the waiting state
            self.state_manager.clear_state(telegram_id)

            # Validate text length
            if not text or len(text.strip()) < 3:
                await self._safe_reply(
                    update,
                    "❌ Текст слишком короткий для анализа.\n\n"
                    "Отправьте более длинный немецкий текст или используйте /add снова.",
                    reply_markup=ReplyKeyboardRemove(),
                )
                return

            # Process the text
            await self._process_text_for_user(update, text)
            return

        # Normal message handling (auto-add mode)
        if not text or len(text.strip()) < 10:
            # Don't show help message if we just interrupted a session
            if not interrupted_session:
                await self._safe_reply(
                    update,
                    "📝 Отправьте мне немецкий текст, и я извлеку из него слова для изучения!\n\n"
                    "Или используйте команды:\n"
                    "/add - Добавить слова (пошагово)\n"
                    "/study - Начать изучение\n"
                    "/help - Справка",
                    reply_markup=ReplyKeyboardRemove(),
                )
            return

        await self._process_text_for_user(update, text)

    async def handle_callback_query(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle callback queries from inline keyboards"""
        if not update.callback_query or not update.effective_user:
            return

        query = update.callback_query
        await query.answer()

        # Handle study session callbacks (JSON format)
        if query.data and query.data.startswith("{"):
            await self._handle_study_callback(query)
            return

        # Handle other callbacks as needed
        logger.warning(f"Unhandled callback query: {query.data}")
