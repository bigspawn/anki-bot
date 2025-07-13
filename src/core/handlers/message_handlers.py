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
    ):
        self._safe_reply = safe_reply_callback
        self._process_text_for_user = process_text_callback
        self._handle_study_callback = handle_study_callback
        self.state_manager = state_manager

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text messages (auto-add words)"""
        if not update.message or not update.effective_user:
            return

        text = update.message.text

        # Check if user is waiting for text to add
        if self.state_manager and self.state_manager.is_waiting_for_text(update.effective_user.id):
            # Import here to avoid circular imports

            # Clear the waiting state
            self.state_manager.clear_state(update.effective_user.id)

            # Validate text length
            if not text or len(text.strip()) < 3:
                await self._safe_reply(
                    update,
                    "❌ Текст слишком короткий для анализа.\n\n"
                    "Отправьте более длинный немецкий текст или используйте /add снова.",
                    reply_markup=ReplyKeyboardRemove()
                )
                return

            # Process the text
            await self._process_text_for_user(update, text)
            return

        # Normal message handling (auto-add mode)
        if not text or len(text.strip()) < 10:
            await self._safe_reply(
                update,
                "📝 Отправьте мне немецкий текст, и я извлеку из него слова для изучения!\n\n"
                "Или используйте команды:\n"
                "/add - Добавить слова (пошагово)\n"
                "/study - Начать изучение\n"
                "/help - Справка",
                reply_markup=ReplyKeyboardRemove()
            )
            return

        await self._process_text_for_user(update, text)

    async def handle_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
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
