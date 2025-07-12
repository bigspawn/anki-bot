"""
Database models for the German Learning Bot
"""

from typing import TypedDict, Optional, Dict, Any
from datetime import datetime


class User(TypedDict):
    """User model"""
    id: int
    telegram_id: int
    first_name: str
    last_name: Optional[str]
    username: Optional[str]
    created_at: datetime
    updated_at: datetime
    is_active: bool


class Word(TypedDict):
    """Word model"""
    id: int
    lemma: str
    part_of_speech: str
    article: Optional[str]
    translation: str
    example: str
    additional_forms: Optional[str]
    confidence: float
    created_at: datetime
    updated_at: datetime


class LearningProgress(TypedDict):
    """Learning progress model"""
    id: int
    user_id: int
    word_id: int
    repetitions: int
    easiness_factor: float
    interval_days: int
    next_review_date: datetime
    last_reviewed: Optional[datetime]
    created_at: datetime
    updated_at: datetime


class ReviewHistory(TypedDict):
    """Review history model"""
    id: int
    user_id: int
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