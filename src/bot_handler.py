"""
Refactored Telegram bot handler using modular architecture
"""

import contextlib
import logging
from functools import wraps

from telegram import ReplyKeyboardRemove, Update
from telegram.error import TelegramError
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from .config import get_settings
from .core.database.database_manager import get_db_manager
from .core.handlers.command_handlers import CommandHandlers
from .core.handlers.message_handlers import MessageHandlers
from .core.locks.user_lock_manager import UserLockManager
from .core.session.session_manager import SessionManager
from .core.state.user_state_manager import UserStateManager
from .spaced_repetition import get_srs_system
from .text_parser import get_text_parser
from .utils import Timer
from .word_processor import get_word_processor

logger = logging.getLogger(__name__)


class BotHandler:
    """Main Telegram bot handler using modular architecture"""

    def __init__(self, settings=None):
        self.settings = settings or get_settings()
        self.db_manager = get_db_manager()
        self.word_processor = get_word_processor()
        self.text_parser = get_text_parser()
        self.srs_system = get_srs_system()
        self.lock_manager = UserLockManager(lock_timeout_minutes=5)
        self.state_manager = UserStateManager(state_timeout_minutes=10)

        self.application = None

        # Initialize modular components
        self.session_manager = SessionManager(
            db_manager=self.db_manager,
            srs_system=self.srs_system,
            safe_reply_callback=self._safe_reply,
            safe_edit_callback=self._safe_edit,
        )

        self.command_handlers = CommandHandlers(
            db_manager=self.db_manager,
            word_processor=self.word_processor,
            text_parser=self.text_parser,
            srs_system=self.srs_system,
            safe_reply_callback=self._safe_reply,
            process_text_callback=self._process_text_for_user,
            start_study_session_callback=self.session_manager.start_study_session,
            state_manager=self.state_manager,
            session_manager=self.session_manager,
        )

        self.message_handlers = MessageHandlers(
            safe_reply_callback=self._safe_reply,
            process_text_callback=self._process_text_for_user,
            handle_study_callback=self.session_manager.handle_study_callback,
            state_manager=self.state_manager,
            session_manager=self.session_manager,
        )

    def _is_user_authorized(self, user_id: int) -> bool:
        """Check if user is authorized to use the bot"""
        if not self.settings.allowed_users_list:
            return False
        return user_id in self.settings.allowed_users_list

    async def _check_authorization(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> bool:
        """Check if user is authorized and send unauthorized message if not"""
        user_id = update.effective_user.id

        if not self._is_user_authorized(user_id):
            await self._safe_reply(
                update,
                "❌ У вас нет доступа к этому боту. Обратитесь к администратору.",
                reply_markup=ReplyKeyboardRemove(),
            )
            logger.warning(f"Unauthorized access attempt from user {user_id}")
            return False

        return True

    def require_authorization(self, func):
        """Decorator to require authorization for handler functions"""

        @wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
            if not await self._check_authorization(update, context):
                return
            return await func(update, context)

        return wrapper

    async def start(self):
        """Start the bot"""
        logger.info("Starting German Learning Bot...")

        # Initialize database
        self.db_manager.init_database()

        # Start lock manager and state manager
        await self.lock_manager.start()
        await self.state_manager.start()

        try:
            # Create application
            self.application = (
                Application.builder()
                .token(self.settings.telegram_bot_token)
                .read_timeout(30)
                .write_timeout(30)
                .connect_timeout(30)
                .pool_timeout(30)
                .post_init(self.setup_bot_menu)
                .build()
            )

            # Add handlers
            self._add_handlers()

            # Start polling
            logger.info("Bot started successfully!")
            await self.application.run_polling(
                poll_interval=self.settings.polling_interval,
                timeout=10,
                bootstrap_retries=3,
            )
        finally:
            # Stop managers on shutdown
            await self.lock_manager.stop()
            await self.state_manager.stop()

    def run(self):
        """Run the bot (synchronous entry point)"""
        logger.info("Starting German Learning Bot...")

        # Initialize database
        self.db_manager.init_database()

        # Create application
        self.application = (
            Application.builder()
            .token(self.settings.telegram_bot_token)
            .read_timeout(30)
            .write_timeout(30)
            .connect_timeout(30)
            .pool_timeout(30)
            .post_init(self.setup_bot_menu)
            .build()
        )

        # Add handlers
        self._add_handlers()

        # Start polling
        logger.info("Bot started successfully!")
        self.application.run_polling(
            poll_interval=self.settings.polling_interval,
            timeout=10,
            bootstrap_retries=3,
        )

    def _add_handlers(self):
        """Add command and message handlers"""
        app = self.application

        # Command handlers with authorization
        app.add_handler(
            CommandHandler(
                "start", self.require_authorization(self.command_handlers.start_command)
            )
        )
        app.add_handler(
            CommandHandler(
                "help", self.require_authorization(self.command_handlers.help_command)
            )
        )
        app.add_handler(
            CommandHandler(
                "add", self.require_authorization(self.command_handlers.add_command)
            )
        )
        app.add_handler(
            CommandHandler(
                "study", self.require_authorization(self.command_handlers.study_command)
            )
        )
        app.add_handler(
            CommandHandler(
                "study_new",
                self.require_authorization(self.command_handlers.study_new_command),
            )
        )
        app.add_handler(
            CommandHandler(
                "study_difficult",
                self.require_authorization(
                    self.command_handlers.study_difficult_command
                ),
            )
        )
        app.add_handler(
            CommandHandler(
                "stats", self.require_authorization(self.command_handlers.stats_command)
            )
        )
        app.add_handler(
            CommandHandler(
                "settings",
                self.require_authorization(self.command_handlers.settings_command),
            )
        )

        # Message handlers with authorization
        app.add_handler(
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                self.require_authorization(self.message_handlers.handle_message),
            )
        )

        # Callback query handler with authorization
        app.add_handler(
            CallbackQueryHandler(
                self.require_authorization(self.message_handlers.handle_callback_query)
            )
        )

        # Error handler
        app.add_error_handler(self.error_handler)

    async def setup_bot_menu(self, application):
        """Setup bot menu with commands for better UX"""
        from telegram import BotCommand

        # Define bot commands with descriptions
        commands = [
            BotCommand("add", "📚 Добавить слова из текста"),
            BotCommand("study", "🎯 Начать изучение слов"),
            BotCommand("study_new", "🆕 Изучать только новые слова"),
            BotCommand("study_difficult", "🔥 Повторить сложные слова"),
            BotCommand("stats", "📊 Показать статистику"),
            BotCommand("help", "❓ Справка по командам"),
            BotCommand("settings", "⚙️ Настройки бота"),
        ]

        try:
            # Set commands for the bot menu
            await application.bot.set_my_commands(commands)
            logger.info("Bot menu commands set successfully")
        except Exception as e:
            logger.error(f"Failed to set bot menu commands: {e}")

    async def _process_text_for_user(self, update: Update, text: str):
        """Process German text and add words for user"""
        user = update.effective_user

        # Check if user is already processing
        if self.lock_manager.is_locked(user.id):
            lock_info = self.lock_manager.get_lock_info(user.id)
            await self._safe_reply(
                update,
                f"⏳ Обработка уже выполняется!\n\n"
                f"🔒 Операция: {lock_info.operation}\n"
                f"⏰ Начата: {lock_info.locked_at.strftime('%H:%M:%S')}\n\n"
                f"Пожалуйста, дождитесь завершения текущей операции.",
                reply_markup=ReplyKeyboardRemove(),
            )
            return

        # Acquire lock for this user
        if not self.lock_manager.acquire_lock(user.id, "add_words"):
            await self._safe_reply(
                update,
                "❌ Не удалось заблокировать пользователя для обработки. "
                "Попробуйте позже.",
                reply_markup=ReplyKeyboardRemove(),
            )
            return

        try:
            # Get user from database
            db_user = self.db_manager.get_user_by_telegram_id(user.id)
            if not db_user:
                await self._safe_reply(
                    update,
                    "❌ Пользователь не найден. Используйте /start для регистрации.",
                    reply_markup=ReplyKeyboardRemove(),
                )
                return

            # Show processing message
            processing_msg = await self._safe_reply(
                update,
                "🔍 Извлекаю слова из текста...\n⏳ Проверяю новые слова...",
                reply_markup=ReplyKeyboardRemove(),
            )

            timer = Timer()
            timer.start()

            # Extract words
            extracted_words = self.text_parser.extract_words(text, max_length=50)

            if not extracted_words:
                await self._safe_edit_message(
                    processing_msg,
                    "❌ Не удалось извлечь слова из текста.\n\n"
                    "Убедитесь, что текст содержит немецкие слова."
                )
                return

            # Limit number of words
            max_words = self.settings.max_words_per_request
            if len(extracted_words) > max_words:
                extracted_words = extracted_words[:max_words]

            # Check which words already exist
            word_existence = self.db_manager.check_multiple_words_exist(
                db_user["telegram_id"], extracted_words
            )

            existing_words = [word for word, exists in word_existence.items() if exists]
            new_words = [word for word, exists in word_existence.items() if not exists]

            # Process new words
            if new_words:
                await self._safe_edit_message(
                    processing_msg,
                    f"📝 Найдено слов: <b>{len(extracted_words)}</b>\n"
                    f"🆕 Новых слов: <b>{len(new_words)}</b>\n"
                    f"↩️ Уже изучаются: <b>{len(existing_words)}</b>\n\n"
                    f"🤖 Обрабатываю новые слова с OpenAI...\n"
                    f"⏳ Это может занять несколько секунд.",
                    parse_mode="HTML",
                )

                # Process with word processor
                processed_words = await self.word_processor.process_text(
                    " ".join(new_words), max_words=len(new_words)
                )

                if processed_words:
                    # Convert to dict format for database
                    words_data = []
                    for pw in processed_words:
                        words_data.append(
                            {
                                "lemma": pw.lemma,
                                "part_of_speech": pw.part_of_speech,
                                "article": pw.article,
                                "translation": pw.translation,
                                "example": pw.example,
                                "additional_forms": pw.additional_forms,
                                "confidence": pw.confidence,
                            }
                        )

                    # Add to database
                    added_count = self.db_manager.add_words_to_user(
                        db_user["telegram_id"], words_data
                    )

                    # Log detailed results
                    processed_count = len(processed_words)
                    if added_count != processed_count:
                        skipped_count = processed_count - added_count
                        logger.warning(
                            f"Word addition mismatch: processed {processed_count} "
                            f"words, "
                            f"but only {added_count} were added to database. "
                            f"{skipped_count} words were skipped."
                        )
                        for pw in processed_words:
                            logger.info(
                                f"Processed word details: '{pw.lemma}' "
                                f"({pw.part_of_speech}) - '{pw.translation}'"
                            )

                    timer.stop()

                    # Get details for existing words if any
                    existing_words_details = []
                    if existing_words:
                        existing_words_details = (
                            self.db_manager.get_existing_words_details(
                                db_user["telegram_id"], existing_words
                            )
                        )

                    # Build success message
                    success_msg = f"""✅ <b>Обработка завершена!</b>

📊 <b>Результаты:</b>
• Всего слов найдено: <b>{len(extracted_words)}</b>
• Новых добавлено: <b>{added_count}</b>
• Уже изучаются: <b>{len(existing_words)}</b>

⏱️ <b>Время обработки:</b> {timer.get_elapsed_time():.1f}с"""

                    # Add existing words list if any
                    if existing_words_details:
                        success_msg += "\n\n📚 <b>Уже изучаемые слова:</b>\n"
                        for word in existing_words_details:
                            article_part = (
                                f"{word['article']} " if word["article"] else ""
                            )
                            success_msg += f"• {article_part}<i>{word['lemma']}</i> — {word['translation']}\n"

                    success_msg += "\n🎯 Начните изучение с команды /study"

                    await self._safe_edit_message(processing_msg, success_msg, parse_mode="HTML")
                else:
                    await self._safe_edit_message(
                        processing_msg,
                        "⚠️ Не удалось обработать слова с помощью OpenAI.\n"
                        "Попробуйте позже или обратитесь к администратору."
                    )
            else:
                # Get details for all existing words
                existing_words_details = self.db_manager.get_existing_words_details(
                    db_user["telegram_id"], existing_words
                )

                # Build message showing all existing words
                msg = f"📚 Найдено слов: <b>{len(extracted_words)}</b>\n"
                msg += "↩️ Все слова уже изучаются!\n\n"

                if existing_words_details:
                    msg += "📚 <b>Изучаемые слова:</b>\n"
                    for word in existing_words_details:
                        article_part = f"{word['article']} " if word["article"] else ""
                        msg += f"• {article_part}<i>{word['lemma']}</i> — {word['translation']}\n"
                    msg += "\n"

                msg += "🎯 Используйте /study для повторения слов."

                await self._safe_edit_message(processing_msg, msg, parse_mode="HTML")

        except Exception as e:
            logger.error(f"Error processing text: {e}")
            with contextlib.suppress(Exception):
                await self._safe_edit_message(
                    processing_msg,
                    "❌ Произошла ошибка при обработке текста.\n"
                    "Попробуйте позже или обратитесь к администратору."
                )
        finally:
            # Always release the lock
            self.lock_manager.release_lock(user.id)

    async def _safe_reply(self, update_or_query, text: str, **kwargs):
        """Safely send a reply message"""
        try:
            if hasattr(update_or_query, "message"):
                # It's an Update object
                return await update_or_query.message.reply_text(text, **kwargs)
            else:
                # It's a Message object
                return await update_or_query.reply_text(text, **kwargs)
        except TelegramError as e:
            logger.error(f"Error sending reply: {e}")
            return None

    async def _safe_edit(self, query, text: str, **kwargs):
        """Safely edit a message"""
        try:
            return await query.edit_message_text(text, **kwargs)
        except TelegramError as e:
            logger.error(f"Error editing message: {e}")
            return None

    async def _safe_edit_message(self, message, text: str, **kwargs):
        """Safely edit a message with fallback to new message"""
        try:
            return await message.edit_text(text, **kwargs)
        except TelegramError as e:
            logger.error(f"Error editing message: {e}")
            # If editing fails, send a new message instead
            try:
                return await message.reply_text(text, **kwargs)
            except TelegramError as e2:
                logger.error(f"Error sending fallback message: {e2}")
                return None

    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle errors"""
        logger.error(f"Update {update} caused error {context.error}")


# For backward compatibility
def get_bot_handler(settings=None) -> BotHandler:
    """Get bot handler instance"""
    return BotHandler(settings)
