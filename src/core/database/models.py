"""
Database models for the German Learning Bot
"""

from datetime import datetime
from typing import TypedDict


class User(TypedDict):
    """User model"""
    telegram_id: int
    first_name: str
    last_name: str | None
    username: str | None
    created_at: datetime
    updated_at: datetime
    is_active: bool


class Word(TypedDict):
    """Word model"""
    id: int
    lemma: str
    part_of_speech: str
    article: str | None
    translation: str
    example: str
    additional_forms: str | None
    confidence: float
    created_at: datetime
    updated_at: datetime


class LearningProgress(TypedDict):
    """Learning progress model"""
    id: int
    telegram_id: int
    word_id: int
    repetitions: int
    easiness_factor: float
    interval_days: int
    next_review_date: datetime
    last_reviewed: datetime | None
    created_at: datetime
    updated_at: datetime


class ReviewHistory(TypedDict):
    """Review history model"""
    id: int
    telegram_id: int
    word_id: int
    rating: int
    response_time_ms: int
    reviewed_at: datetime


class UserStats(TypedDict):
    """User statistics model"""
    total_words: int
    new_words: int
    due_words: int
    learned_words: int
    difficult_words: int
    average_accuracy: float
    study_streak: int
    words_today: int
    reviews_today: int
