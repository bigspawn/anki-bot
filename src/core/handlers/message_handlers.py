"""
Message handlers for the German Learning Bot
"""

import logging

from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


class MessageHandlers:
    """Handles text messages and callback queries"""

    def __init__(
        self,
        safe_reply_callback,
        process_text_callback,
        handle_study_callback,
    ):
        self._safe_reply = safe_reply_callback
        self._process_text_for_user = process_text_callback
        self._handle_study_callback = handle_study_callback

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text messages (auto-add words)"""
        if not update.message or not update.effective_user:
            return

        text = update.message.text

        if not text or len(text.strip()) < 10:
            await self._safe_reply(
                update,
                "📝 Отправьте мне немецкий текст, и я извлеку из него слова для изучения!\n\n"
                "Или используйте команды:\n"
                "/add <текст> - Добавить слова\n"
                "/study - Начать изучение\n"
                "/help - Справка"
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
