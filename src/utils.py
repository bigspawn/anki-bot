"""
Utility functions for the German Learning Bot
"""

import asyncio
import json
import logging
import re
import time
from datetime import date, datetime
from functools import wraps
from typing import Any

logger = logging.getLogger(__name__)


def format_word_display(word_data: dict[str, Any]) -> str:
    """Format word data for display in Telegram"""
    word_data.get("word", "")
    lemma = word_data.get("lemma", "")
    article = word_data.get("article")
    part_of_speech = word_data.get("part_of_speech", "")
    translation = word_data.get("translation", "")
    example = word_data.get("example", "")

    # Format with article for nouns - handle None values properly
    if article and article != "None" and article.strip():
        display_word = f"{article} {lemma}"
    else:
        display_word = lemma

    # Build formatted string
    result = f"🇩🇪 {display_word}\n"

    if part_of_speech:
        result += f"🏷️ {part_of_speech}\n"

    if translation:
        result += f"🇷🇺 {translation}\n"

    if example:
        result += f"📚 {example}\n"

    return result.strip()


def format_study_card(
    word_data: dict[str, Any], current_index: int = 0, total_words: int = 0
) -> str:
    """Format word as study flashcard"""
    lemma = word_data.get("lemma", "")
    article = word_data.get("article", "")
    part_of_speech = word_data.get("part_of_speech", "")

    # Progress info
    progress_info = f"{current_index}/{total_words}. " if total_words > 0 else ""

    # Question format based on part of speech
    if is_cloze_card(word_data):
        result = f"{progress_info}Заполните пропуск:\n\n{lemma}"
    elif is_error_fix_card(word_data):
        result = f"{progress_info}Исправьте ошибку:\n\n{lemma}"
    elif is_paradigm_card(word_data):
        result = f"{progress_info}Поставьте в нужный падеж:\n\n{lemma}"
    elif is_rule_card(word_data):
        result = f"{progress_info}Как правильно?\n\n{lemma}"
    elif part_of_speech == "noun" and article:
        # Ask for the plural too, but only when there is one to reveal
        if stored_plural(word_data):
            result = f"{progress_info}Какой артикль и множественное число у {lemma}?"
        else:
            result = f"{progress_info}Какой артикль у {lemma}?"
    elif is_reflexive_case_card(word_data):
        result = f"{progress_info}Какой падеж у sich в «{lemma}»?"
    elif is_case_verb(word_data) or is_preposition_verb(word_data):
        result = f"{progress_info}Как переводится {lemma} и какой падеж?"
    else:
        result = f"{progress_info}Как переводится {lemma}?"

    return result


def is_preposition_verb(word_data: dict[str, Any]) -> bool:
    """Check whether the word is a verb governing a preposition"""
    part_of_speech = (word_data.get("part_of_speech") or "").lower()
    return "verb" in part_of_speech and "preposition" in part_of_speech


def is_reflexive_case_card(word_data: dict[str, Any]) -> bool:
    """Check whether the card drills the case of a reflexive pronoun.

    A verb like 'sich erinnern an' also starts with sich and stores a case,
    but that case belongs to the object after the preposition, not to the
    reflexive pronoun — those stay preposition cards.
    """
    if is_preposition_verb(word_data):
        return False

    lemma = (word_data.get("lemma") or "").lower()
    part_of_speech = (word_data.get("part_of_speech") or "").lower()
    if not lemma.startswith("sich ") and "reflexive" not in part_of_speech:
        return False

    return bool(_stored_forms(word_data).get("case"))


def is_case_verb(word_data: dict[str, Any]) -> bool:
    """Check whether the card drills the case a plain verb governs"""
    part_of_speech = (word_data.get("part_of_speech") or "").lower()
    return part_of_speech in ("dativ verb", "dativ akkusativ verb")


def _stored_forms(word_data: dict[str, Any]) -> dict[str, Any]:
    """Parse additional_forms, or {} when it is missing or not a JSON object"""
    raw = word_data.get("additional_forms")
    if not raw:
        return {}

    try:
        forms = json.loads(raw)
    except (TypeError, ValueError):
        return {}

    return forms if isinstance(forms, dict) else {}


def stored_plural(word_data: dict[str, Any]) -> str | None:
    """Read the plural of a noun, tolerating the shapes older prompts produced.

    Early answers stored it under 'Plural' or as a bare 'plural: die Häuser'
    string, so a strict lookup would hide a form that is actually there.
    """
    if "noun" not in (word_data.get("part_of_speech") or "").lower():
        return None

    forms = _stored_forms(word_data)
    for key, value in forms.items():
        if key.lower() == "plural" and isinstance(value, str) and value.strip():
            # The model writes "null" as a string often enough that a card
            # would otherwise read 'Plural: null'
            if value.strip().lower() in ("null", "none", "-", "n/a"):
                return None
            return value.strip()

    raw = word_data.get("additional_forms")
    if isinstance(raw, str) and not forms:
        match = re.search(r"plurals?\s*[:=]\s*\"?([^\"\n,}]+)", raw, re.IGNORECASE)
        if match and match.group(1).strip():
            return match.group(1).strip()

    return None


def format_plural_line(word_data: dict[str, Any]) -> str:
    """Format the plural line for a noun, or '' when none is stored"""
    plural = stored_plural(word_data)
    if not plural:
        return ""

    return f"🔢 Plural: {plural}\n\n"


def format_case_line(word_data: dict[str, Any]) -> str:
    """Format the governed-case line for a reflexive or case-governing verb,
    or '' when the card has no case stored"""
    case = _stored_forms(word_data).get("case")
    if not case:
        return ""

    if is_reflexive_case_card(word_data):
        return f"🪞 sich + {case}\n\n"
    if is_case_verb(word_data):
        return f"📐 {word_data.get('lemma')} + {case}\n\n"

    return ""


def is_cloze_card(word_data: dict[str, Any]) -> bool:
    """Check whether the card is a gap-fill drill"""
    return (word_data.get("part_of_speech") or "").lower() == "cloze"


def is_error_fix_card(word_data: dict[str, Any]) -> bool:
    """Check whether the card is an error-correction drill"""
    return (word_data.get("part_of_speech") or "").lower() == "error fix"


def is_paradigm_card(word_data: dict[str, Any]) -> bool:
    """Check whether the card drills one cell of a declension table"""
    part_of_speech = (word_data.get("part_of_speech") or "").lower()
    return part_of_speech in ("pronoun case", "article case", "demonstrativ")


def is_rule_card(word_data: dict[str, Any]) -> bool:
    """Check whether the card drills a rule from the vault's Затыки list.

    Unlike a declension cell these are not always about case — word order and
    the imperative are asked for the same way, so they share a prompt.
    """
    part_of_speech = (word_data.get("part_of_speech") or "").lower()
    return part_of_speech in (
        "wo wohin",
        "verschmelzung",
        "word order",
        "adjective ending",
        "verb form",
        "zeitangabe",
    )


def is_drill_card(word_data: dict[str, Any]) -> bool:
    """Check whether the card is drilled as a form rather than a word.

    Drills carry the rule in the translation, so the article and part-of-speech
    lines of a normal card would only add noise.
    """
    return (
        is_cloze_card(word_data)
        or is_error_fix_card(word_data)
        or is_paradigm_card(word_data)
        or is_rule_card(word_data)
    )


def format_progress_stats(stats: dict[str, Any]) -> str:
    """Format user progress statistics"""
    total_words = stats.get("total_words", 0)
    due_words = stats.get("due_words", 0)
    new_words = stats.get("new_words", 0)
    words_today = stats.get("words_today", 0)
    avg_success_rate = stats.get("average_accuracy", 0.0)
    correct_reviews = stats.get("correct_reviews", 0)
    incorrect_reviews = stats.get("incorrect_reviews", 0)
    study_streak = stats.get("study_streak", 0)

    result = "📊 Ваша статистика:\n\n"
    result += f"📚 Всего слов: {total_words}\n"
    result += f"🔄 К повторению: {due_words}\n"
    result += f"🆕 Новых слов: {new_words}\n"
    result += f"➕ Добавлено сегодня: {words_today}\n"
    result += f"🔥 Дней подряд: {study_streak}\n"
    result += f"✅ Хорошо/легко вспомнил (➕✅) за 30д: {avg_success_rate:.1%}\n"
    result += (
        f"   хорошо/легко: {correct_reviews} / нужно повторить: {incorrect_reviews}\n"
    )

    return result


def format_topic_stats(rows: list[dict[str, Any]]) -> str:
    """Format the per-topic accuracy breakdown, worst topic first"""
    if not rows:
        return (
            "📊 Пока нет статистики по темам.\n\n"
            "Темы появляются у карточек из готовых наборов (маршруты, "
            "пропуски, работа над ошибками) после первого повторения."
        )

    result = "📊 Статистика по темам (худшие сверху):\n\n"
    for row in rows:
        accuracy = (row.get("accuracy") or 0.0) * 100
        result += f"🏷 {row['topic']}\n"
        result += (
            f"   карточек: {row['cards']} | повторений: {row['reviews']} | "
            f"успех: {accuracy:.0f}%\n"
        )
        result += f"   средний EF: {row.get('mean_easiness_factor') or 0.0:.2f}\n"
        if row.get("worst_card"):
            result += f"   слабое место: {row['worst_card']}\n"
        result += f"   повторить: /study_topic {row['topic']}\n\n"

    return result.strip()


def validate_german_text(text: str) -> bool:
    """Validate if text contains German characters"""
    if not text or not text.strip():
        return False

    # Check for German-specific characters
    german_chars = r"[äöüßÄÖÜ]"
    has_german = bool(re.search(german_chars, text))

    # Check for common German words
    german_words = {
        "der",
        "die",
        "das",
        "und",
        "ich",
        "du",
        "er",
        "sie",
        "es",
        "wir",
        "ihr",
        "ist",
        "sind",
        "hat",
        "haben",
        "mit",
        "für",
        "auf",
        "in",
        "zu",
        "von",
    }

    words = text.lower().split()
    has_german_words = any(word in german_words for word in words)

    return has_german or has_german_words


def clean_text(text: str) -> str:
    """Clean and normalize text input"""
    if not text:
        return ""

    # Remove extra whitespace
    text = re.sub(r"\s+", " ", text.strip())

    # Remove special characters except German umlauts and punctuation
    text = re.sub(r"[^\w\säöüßÄÖÜ.,!?;:\-\'\"]", "", text)

    return text


def extract_json_safely(json_str: str) -> dict[str, Any]:
    """Safely extract JSON from string"""
    if not json_str:
        return {}

    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, TypeError):
        logger.warning(f"Failed to parse JSON: {json_str}")
        return {}


def format_json_safely(data: Any) -> str:
    """Safely format data as JSON string"""
    try:
        return json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    except (TypeError, ValueError):
        logger.warning(f"Failed to serialize to JSON: {data}")
        return "{}"


def escape_markdown(text: str) -> str:
    """Escape special characters for Telegram MarkdownV2"""
    if not text:
        return ""

    # Characters that need escaping in MarkdownV2
    escape_chars = r"_*[]()~`>#+-=|{}.!"

    for char in escape_chars:
        text = text.replace(char, f"\\{char}")

    return text


def retry_on_exception(max_retries: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """Decorator for retrying functions on exception"""

    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        wait_time = delay * (backoff**attempt)
                        logger.warning(
                            f"Attempt {attempt + 1} failed: {e}. Retrying in {wait_time}s..."
                        )
                        await asyncio.sleep(wait_time)
                    else:
                        logger.error(
                            f"All {max_retries} attempts failed for {func.__name__}"
                        )

            raise last_exception

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        wait_time = delay * (backoff**attempt)
                        logger.warning(
                            f"Attempt {attempt + 1} failed: {e}. Retrying in {wait_time}s..."
                        )
                        time.sleep(wait_time)
                    else:
                        logger.error(
                            f"All {max_retries} attempts failed for {func.__name__}"
                        )

            raise last_exception

        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def rate_limit(calls_per_minute: int = 60):
    """Rate limiting decorator"""
    min_interval = 60.0 / calls_per_minute
    last_called = {}

    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            key = f"{func.__name__}_{id(args[0]) if args else 'global'}"
            now = time.time()

            if key in last_called:
                elapsed = now - last_called[key]
                if elapsed < min_interval:
                    sleep_time = min_interval - elapsed
                    await asyncio.sleep(sleep_time)

            last_called[key] = time.time()
            return await func(*args, **kwargs)

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            key = f"{func.__name__}_{id(args[0]) if args else 'global'}"
            now = time.time()

            if key in last_called:
                elapsed = now - last_called[key]
                if elapsed < min_interval:
                    sleep_time = min_interval - elapsed
                    time.sleep(sleep_time)

            last_called[key] = time.time()
            return func(*args, **kwargs)

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def parse_date_safely(date_str: str) -> date | None:
    """Safely parse date string"""
    if not date_str:
        return None

    try:
        # Try ISO format first
        return datetime.fromisoformat(date_str).date()
    except ValueError:
        pass

    # Try other common formats
    formats = ["%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"]
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue

    logger.warning(f"Failed to parse date: {date_str}")
    return None


def format_date_relative(target_date: date) -> str:
    """Format date relative to today"""
    today = date.today()
    delta = (target_date - today).days

    if delta == 0:
        return "сегодня"
    elif delta == 1:
        return "завтра"
    elif delta == -1:
        return "вчера"
    elif delta > 0:
        return f"через {delta} дн."
    else:
        return f"{abs(delta)} дн. назад"


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """Truncate text to maximum length"""
    if not text or len(text) <= max_length:
        return text

    return text[: max_length - len(suffix)] + suffix


def validate_rating(rating: int | str) -> int | None:
    """Validate and convert rating value"""
    try:
        rating_int = int(rating)
        if 1 <= rating_int <= 4:
            return rating_int
    except (ValueError, TypeError):
        pass

    return None


def format_verb_forms(word: dict[str, Any]) -> str:
    """Format the Präteritum/Partizip II line for a verb's additional_forms,
    or '' if the word isn't a verb or has no clean forms stored"""
    part_of_speech = (word.get("part_of_speech") or "").lower()
    if part_of_speech not in ("verb", "reflexive verb"):
        return ""

    raw = word.get("additional_forms")
    if not raw:
        return ""

    try:
        forms = json.loads(raw)
    except (TypeError, ValueError):
        return ""

    if not isinstance(forms, dict):
        return ""

    praeteritum = forms.get("praeteritum")
    partizip_ii = forms.get("partizip_ii")
    if not praeteritum or not partizip_ii:
        return ""

    return f"🔄 {praeteritum} – {partizip_ii}\n\n"


def format_verb_case(word: dict[str, Any]) -> str:
    """Format the 'preposition + case' line for a verb governing a preposition,
    or '' if the word has no case stored"""
    if not is_preposition_verb(word):
        return ""

    raw = word.get("additional_forms")
    if not raw:
        return ""

    try:
        forms = json.loads(raw)
    except (TypeError, ValueError):
        return ""

    if not isinstance(forms, dict):
        return ""

    preposition = forms.get("preposition")
    case = forms.get("case")
    if not preposition or not case:
        return ""

    return f"🧭 {preposition} + {case}\n\n"


def get_rating_emoji(rating: int) -> str:
    """Get emoji for rating"""
    emojis = {1: "❌", 2: "➖", 3: "➕", 4: "✅"}  # Again  # Hard  # Good  # Easy
    return emojis.get(rating, "❓")


def get_rating_text(rating: int) -> str:
    """Get text description for rating"""
    texts = {1: "", 2: "", 3: "", 4: ""}  # Only emojis, no text
    return texts.get(rating, "")


def chunk_list(lst: list[Any], chunk_size: int) -> list[list[Any]]:
    """Split list into chunks of specified size"""
    return [lst[i : i + chunk_size] for i in range(0, len(lst), chunk_size)]


def safe_int(value: Any, default: int = 0) -> int:
    """Safely convert value to integer"""
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def safe_float(value: Any, default: float = 0.0) -> float:
    """Safely convert value to float"""
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def calculate_success_rate(correct: int, total: int) -> float:
    """Calculate success rate as percentage"""
    if total == 0:
        return 0.0
    return (correct / total) * 100.0


def format_duration(seconds: int) -> str:
    """Format duration in human-readable format"""
    if seconds < 60:
        return f"{seconds}с"
    elif seconds < 3600:
        minutes = seconds // 60
        return f"{minutes}м"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours}ч {minutes}м"


def get_difficulty_level(easiness_factor: float) -> str:
    """Get difficulty level description"""
    if easiness_factor >= 2.5:
        return "Легкое"
    elif easiness_factor >= 2.0:
        return "Среднее"
    elif easiness_factor >= 1.5:
        return "Трудное"
    else:
        return "Очень трудное"


def create_inline_keyboard_data(action: str, **kwargs) -> str:
    """Create callback data for inline keyboard with compact format"""
    # Use compact encoding to stay under 64 byte limit
    compact_data = {"a": action}

    # Use compact keys and optimize values
    key_mappings = {
        "word_id": "w",
        "session_id": "s",
        "word_index": "i",
        "rating": "r",
    }

    for key, value in kwargs.items():
        compact_key = key_mappings.get(key, key)
        # Further optimize session_id by removing user_id prefix if present
        if key == "session_id" and isinstance(value, str) and "_" in value:
            # Extract just the timestamp part
            parts = value.split("_")
            if len(parts) >= 2:
                compact_data[compact_key] = parts[-1]  # Just the timestamp
            else:
                compact_data[compact_key] = value
        else:
            compact_data[compact_key] = value

    result = format_json_safely(compact_data)

    # Additional safety check - if still too long, truncate session_id further
    if len(result) > 64 and "s" in compact_data:
        # Try with even shorter session ID
        session_val = str(compact_data["s"])
        if len(session_val) > 4:
            compact_data["s"] = session_val[-4:]  # Just last 4 digits
            result = format_json_safely(compact_data)

    return result


def parse_inline_keyboard_data(callback_data: str) -> dict[str, Any]:
    """Parse callback data from inline keyboard with compact format support"""
    raw_data = extract_json_safely(callback_data)

    # If it's already in the old format, return as is
    if "action" in raw_data:
        return raw_data

    # Convert from compact format
    expanded_data = {}

    # Reverse key mappings
    key_mappings = {
        "a": "action",
        "w": "word_id",
        "s": "session_id",
        "i": "word_index",
        "r": "rating",
    }

    for key, value in raw_data.items():
        expanded_key = key_mappings.get(key, key)
        expanded_data[expanded_key] = value

    return expanded_data


class Timer:
    """Simple timer for measuring duration"""

    def __init__(self):
        self.start_time = None
        self.end_time = None

    def start(self):
        """Start the timer"""
        self.start_time = time.time()
        self.end_time = None

    def stop(self):
        """Stop the timer"""
        if self.start_time is not None:
            self.end_time = time.time()

    def elapsed(self) -> float | None:
        """Get elapsed time in seconds"""
        if self.start_time is None:
            return None

        end = self.end_time or time.time()
        return end - self.start_time

    def elapsed_ms(self) -> int | None:
        """Get elapsed time in milliseconds"""
        elapsed = self.elapsed()
        return int(elapsed * 1000) if elapsed is not None else None

    def get_elapsed_time(self) -> float:
        """Get elapsed time in seconds (for backward compatibility)"""
        return self.elapsed() or 0.0


def log_execution_time(func):
    """Decorator to log function execution time"""

    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        timer = Timer()
        timer.start()
        try:
            result = await func(*args, **kwargs)
            timer.stop()
            logger.debug(f"{func.__name__} executed in {timer.elapsed():.3f}s")
            return result
        except Exception as e:
            timer.stop()
            logger.error(f"{func.__name__} failed after {timer.elapsed():.3f}s: {e}")
            raise

    @wraps(func)
    def sync_wrapper(*args, **kwargs):
        timer = Timer()
        timer.start()
        try:
            result = func(*args, **kwargs)
            timer.stop()
            logger.debug(f"{func.__name__} executed in {timer.elapsed():.3f}s")
            return result
        except Exception as e:
            timer.stop()
            logger.error(f"{func.__name__} failed after {timer.elapsed():.3f}s: {e}")
            raise

    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    else:
        return sync_wrapper
