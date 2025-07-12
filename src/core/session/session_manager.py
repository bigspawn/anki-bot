"""
Session management for the German Learning Bot
"""

import logging
from datetime import datetime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update

from ...database import DatabaseManager
from ...spaced_repetition import SpacedRepetitionSystem
from ...utils import (
    Timer,
    create_inline_keyboard_data,
    format_study_card,
    get_rating_emoji,
    parse_inline_keyboard_data,
)

logger = logging.getLogger(__name__)


class StudySession:
    """Represents a single study session"""

    def __init__(self, session_id: str, user_id: int, words: list[dict], session_type: str):
        self.session_id = session_id
        self.user_id = user_id
        self.words = words
        self.session_type = session_type
        self.current_word_index = 0
        self.correct_answers = 0
        self.total_answers = 0
        self.timer = Timer()
        self.created_at = datetime.now()

    def get_current_word(self) -> dict | None:
        """Get the current word being studied"""
        if self.current_word_index < len(self.words):
            return self.words[self.current_word_index]
        return None

    def advance_to_next_word(self):
        """Move to the next word in the session"""
        self.current_word_index += 1

    def is_finished(self) -> bool:
        """Check if the session is complete"""
        return self.current_word_index >= len(self.words)

    def record_answer(self, correct: bool):
        """Record an answer for statistics"""
        self.total_answers += 1
        if correct:
            self.correct_answers += 1


class SessionManager:
    """Manages user study sessions"""

    def __init__(
        self,
        db_manager: DatabaseManager,
        srs_system: SpacedRepetitionSystem,
        safe_reply_callback,
        safe_edit_callback,
    ):
        self.db_manager = db_manager
        self.srs_system = srs_system
        self._safe_reply = safe_reply_callback
        self._safe_edit = safe_edit_callback
        self.user_sessions: dict[int, StudySession] = {}

    async def start_study_session(
        self,
        update: Update,
        words: list[dict],
        session_type: str
    ):
        """Start a new study session"""
        user_id = update.effective_user.id

        # Create session with compact ID
        # Use only last 6 digits of timestamp for uniqueness while staying compact
        timestamp = int(datetime.now().timestamp())
        compact_timestamp = timestamp % 1000000  # Last 6 digits
        session_id = f"{user_id}_{compact_timestamp}"
        session = StudySession(session_id, user_id, words, session_type)

        # Store session
        self.user_sessions[user_id] = session
        session.timer.start()

        # Show first card
        await self._show_current_card(update, session)

    async def _show_current_card(self, update: Update, session: StudySession):
        """Show the current flashcard"""
        word = session.get_current_word()
        if not word:
            await self._finish_session(update, session)
            return

        # Format study card
        card_text = format_study_card(
            word,
            session.current_word_index + 1,
            len(session.words)
        )

        # Create inline keyboard
        keyboard_data = create_inline_keyboard_data(
            action="show_answer",
            word_id=word["id"],
            word_index=session.current_word_index,
        )

        keyboard = [[InlineKeyboardButton("🔍 Показать ответ", callback_data=keyboard_data)]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await self._safe_reply(update, card_text, reply_markup=reply_markup)

    async def handle_show_answer(self, query, data: dict):
        """Handle showing the answer to a flashcard"""
        user_id = query.from_user.id
        session = self.user_sessions.get(user_id)

        if not session:
            await query.edit_message_text("❌ Сессия истекла. Начните новую с /study")
            return

        word = session.get_current_word()
        if not word:
            return

        # Show answer with rating buttons
        article = word.get('article')
        if article and article != 'None' and article.strip():
            word_display = f"{article} {word['lemma']} - {word['part_of_speech']}"
        else:
            word_display = f"{word['lemma']} - {word['part_of_speech']}"

        answer_text = f"""🔤 <b>{word['lemma']}</b>
{word_display}

🇷🇺 {word['translation']}

📝 <i>{word['example']}</i>

Как хорошо вы знаете это слово?"""

        # Create rating keyboard
        rating_buttons = []
        for rating in [1, 2, 3, 4]:
            emoji = get_rating_emoji(rating)
            callback_data = create_inline_keyboard_data(
                action="rate_word",
                word_id=word["id"],
                rating=rating,
            )
            rating_buttons.append(InlineKeyboardButton(emoji, callback_data=callback_data))

        keyboard = [rating_buttons]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await self._safe_edit(query, answer_text, reply_markup=reply_markup, parse_mode="HTML")

    async def handle_word_rating(self, query, data: dict):
        """Handle word rating"""
        user_id = query.from_user.id
        session = self.user_sessions.get(user_id)

        if not session:
            await query.edit_message_text("❌ Сессия истекла. Начните новую с /study")
            return

        word_id = data.get("word_id")
        rating = data.get("rating")

        if not word_id or not rating:
            logger.error("Missing word_id or rating in callback data")
            return

        # Update word progress
        self.db_manager.update_learning_progress(user_id, word_id, rating)

        # Record answer statistics
        session.record_answer(rating >= 3)  # Consider 3+ as correct

        # Show next card or finish session
        session.advance_to_next_word()

        if session.is_finished():
            await self._finish_session_from_query(query, session)
        else:
            await self._show_next_card(query, session)

    async def _show_next_card(self, query, session: StudySession):
        """Show the next card in the session"""
        word = session.get_current_word()
        if not word:
            return

        # Format next card
        card_text = format_study_card(
            word,
            session.current_word_index + 1,
            len(session.words)
        )

        # Create show answer button
        keyboard_data = create_inline_keyboard_data(
            action="show_answer",
            word_id=word["id"],
            word_index=session.current_word_index,
        )

        keyboard = [[InlineKeyboardButton("🔍 Показать ответ", callback_data=keyboard_data)]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await self._safe_edit(query, card_text, reply_markup=reply_markup)

    async def _finish_session(self, update: Update, session: StudySession):
        """Finish the study session"""
        session.timer.stop()

        # Calculate statistics
        accuracy = (session.correct_answers / session.total_answers * 100) if session.total_answers > 0 else 0

        completion_text = f"""✅ <b>Сессия завершена!</b>

📊 <b>Результаты:</b>
• Слов изучено: <b>{len(session.words)}</b>
• Правильных ответов: <b>{session.correct_answers}/{session.total_answers}</b>
• Точность: <b>{accuracy:.1f}%</b>
• Время: <b>{session.timer.get_elapsed_time():.1f}с</b>

🎯 Отличная работа! Продолжайте изучение для лучшего запоминания."""

        await self._safe_reply(update, completion_text, parse_mode="HTML")

        # Clean up session
        if session.user_id in self.user_sessions:
            del self.user_sessions[session.user_id]

    async def _finish_session_from_query(self, query, session: StudySession):
        """Finish the study session from a callback query"""
        session.timer.stop()

        # Calculate statistics
        accuracy = (session.correct_answers / session.total_answers * 100) if session.total_answers > 0 else 0

        completion_text = f"""✅ <b>Сессия завершена!</b>

📊 <b>Результаты:</b>
• Слов изучено: <b>{len(session.words)}</b>
• Правильных ответов: <b>{session.correct_answers}/{session.total_answers}</b>
• Точность: <b>{accuracy:.1f}%</b>
• Время: <b>{session.timer.get_elapsed_time():.1f}с</b>

🎯 Отличная работа! Продолжайте изучение для лучшего запоминания."""

        await self._safe_edit(query, completion_text, parse_mode="HTML")

        # Clean up session
        if session.user_id in self.user_sessions:
            del self.user_sessions[session.user_id]

    async def handle_study_callback(self, query):
        """Handle study-related callback queries"""
        data = parse_inline_keyboard_data(query.data)
        action = data.get("action")

        if action == "show_answer":
            await self.handle_show_answer(query, data)
        elif action == "rate_word":
            await self.handle_word_rating(query, data)
        elif action == "next_card":
            await self._handle_next_card(query, data)
        elif action == "finish_session":
            await self._handle_finish_session(query, data)
        else:
            logger.warning(f"Unknown study callback action: {action}")

    async def _handle_next_card(self, query, data: dict):
        """Handle next card button"""
        user_id = query.from_user.id
        session = self.user_sessions.get(user_id)

        if not session:
            await query.edit_message_text("❌ Сессия истекла. Начните новую с /study")
            return

        await self._show_next_card(query, session)

    async def _handle_finish_session(self, query, data: dict):
        """Handle finish session button"""
        user_id = query.from_user.id
        session = self.user_sessions.get(user_id)

        if not session:
            await query.edit_message_text("❌ Сессия истекла")
            return

        await self._finish_session_from_query(query, session)

    def get_session(self, user_id: int) -> StudySession | None:
        """Get active session for user"""
        return self.user_sessions.get(user_id)

    def cleanup_expired_sessions(self, max_age_hours: int = 24):
        """Clean up expired sessions"""
        current_time = datetime.now()
        expired_sessions = []

        for user_id, session in self.user_sessions.items():
            age = (current_time - session.created_at).total_seconds() / 3600
            if age > max_age_hours:
                expired_sessions.append(user_id)

        for user_id in expired_sessions:
            del self.user_sessions[user_id]
            logger.info(f"Cleaned up expired session for user {user_id}")
