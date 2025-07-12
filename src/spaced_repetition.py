"""
Spaced Repetition System implementation using SuperMemo 2 algorithm
"""

import logging
from datetime import date, timedelta
from typing import Tuple, Dict, Any
from dataclasses import dataclass

from .config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class ReviewResult:
    """Result of a spaced repetition review"""

    new_interval: int
    new_easiness_factor: float
    next_review_date: date
    is_graduated: bool = False  # Word has moved beyond initial learning


class SpacedRepetitionSystem:
    """SuperMemo 2 spaced repetition algorithm implementation"""

    def __init__(self):
        settings = get_settings()
        self.default_easiness = settings.default_easiness_factor
        self.min_easiness = settings.min_easiness_factor
        self.max_easiness = settings.max_easiness_factor

    def calculate_review(
        self,
        rating: int,
        repetitions: int,
        interval_days: int,
        easiness_factor: float,
        review_date: date = None,
    ) -> ReviewResult:
        """
        Calculate next review based on SuperMemo 2 algorithm

        Args:
            rating: User rating (1=Again, 2=Hard, 3=Good, 4=Easy)
            repetitions: Number of successful repetitions
            interval_days: Current interval in days
            easiness_factor: Current easiness factor
            review_date: Date of review (defaults to today)

        Returns:
            ReviewResult with new parameters
        """
        if review_date is None:
            review_date = date.today()

        logger.info(
            f"Calculating review: rating={rating}, reps={repetitions}, "
            f"interval={interval_days}, ef={easiness_factor}"
        )

        if rating < 1 or rating > 4:
            raise ValueError(f"Rating must be between 1 and 4, got {rating}")

        # Handle "Again" rating (1)
        if rating == 1:
            return self._handle_again_rating(review_date, easiness_factor)

        # Calculate new easiness factor for ratings 2-4
        new_easiness = self._calculate_new_easiness(rating, easiness_factor)

        # Calculate new interval
        new_interval = self._calculate_new_interval(
            rating, repetitions, interval_days, new_easiness
        )

        # Calculate next review date
        next_review_date = review_date + timedelta(days=new_interval)

        # Check if word is graduated (past initial learning phase)
        is_graduated = repetitions >= 2 and new_interval > 1

        result = ReviewResult(
            new_interval=new_interval,
            new_easiness_factor=new_easiness,
            next_review_date=next_review_date,
            is_graduated=is_graduated,
        )

        logger.info(
            f"Review result: interval={result.new_interval}, "
            f"ef={result.new_easiness_factor}, next={result.next_review_date}"
        )

        return result

    def _handle_again_rating(
        self, review_date: date, easiness_factor: float
    ) -> ReviewResult:
        """Handle 'Again' rating - reset to beginning"""
        # Decrease easiness factor significantly
        new_easiness = max(self.min_easiness, easiness_factor - 0.2)

        # Reset to immediate review (same day)
        return ReviewResult(
            new_interval=0,  # Review again in current session
            new_easiness_factor=new_easiness,
            next_review_date=review_date,
            is_graduated=False,
        )

    def _calculate_new_easiness(self, rating: int, current_easiness: float) -> float:
        """Calculate new easiness factor based on rating"""
        # SuperMemo 2 formula with modifications
        if rating == 2:  # Hard
            adjustment = -0.15
        elif rating == 3:  # Good
            adjustment = 0.0
        elif rating == 4:  # Easy
            adjustment = 0.15
        else:
            adjustment = 0.0

        new_easiness = current_easiness + adjustment

        # Clamp to valid range
        return max(self.min_easiness, min(self.max_easiness, new_easiness))

    def _calculate_new_interval(
        self,
        rating: int,
        repetitions: int,
        current_interval: int,
        easiness_factor: float,
    ) -> int:
        """Calculate new interval based on SuperMemo 2 algorithm"""

        if repetitions == 0:
            # First repetition
            if rating == 2:  # Hard
                return 1
            elif rating == 3:  # Good
                return 1
            else:  # Easy (4)
                return 4

        elif repetitions == 1:
            # Second repetition
            if rating == 2:  # Hard
                return max(1, int(current_interval * 1.2))
            elif rating == 3:  # Good
                return 6
            else:  # Easy (4)
                return max(6, int(current_interval * easiness_factor * 1.3))

        else:
            # Subsequent repetitions
            if rating == 2:  # Hard
                # Increase interval slightly but less than good
                multiplier = max(1.2, easiness_factor * 0.8)
            elif rating == 3:  # Good
                # Standard SuperMemo 2 formula
                multiplier = easiness_factor
            else:  # Easy (4)
                # Increase interval more aggressively
                multiplier = easiness_factor * 1.3

            new_interval = max(1, int(current_interval * multiplier))

            # Cap maximum interval at 365 days (1 year)
            return min(365, new_interval)

    def get_initial_review_schedule(self) -> ReviewResult:
        """Get initial review schedule for new words"""
        today = date.today()
        return ReviewResult(
            new_interval=1,
            new_easiness_factor=self.default_easiness,
            next_review_date=today,
            is_graduated=False,
        )

    def predict_retention(
        self, days_since_review: int, easiness_factor: float
    ) -> float:
        """Predict retention probability based on time elapsed"""
        # Simplified retention model
        # Higher easiness factor = better retention
        # More days = lower retention

        if days_since_review <= 0:
            return 1.0

        # Base retention decreases exponentially with time
        base_retention = 0.9**days_since_review

        # Easiness factor affects retention curve
        easiness_multiplier = (easiness_factor / self.default_easiness) ** 0.5

        retention = base_retention * easiness_multiplier

        return max(0.0, min(1.0, retention))

    def get_optimal_review_time(
        self, easiness_factor: float, target_retention: float = 0.85
    ) -> int:
        """Calculate optimal review time for target retention"""
        # Binary search for optimal interval
        min_days, max_days = 1, 365

        for _ in range(20):  # Max 20 iterations
            mid_days = (min_days + max_days) // 2
            predicted_retention = self.predict_retention(mid_days, easiness_factor)

            if abs(predicted_retention - target_retention) < 0.01:
                return mid_days
            elif predicted_retention > target_retention:
                min_days = mid_days + 1
            else:
                max_days = mid_days - 1

        return min_days

    def analyze_learning_progress(self, review_history: list) -> Dict[str, Any]:
        """Analyze learning progress from review history"""
        if not review_history:
            return {
                "total_reviews": 0,
                "avg_rating": 0.0,
                "success_rate": 0.0,
                "learning_trend": "stable",
                "difficulty_level": "unknown",
            }

        total_reviews = len(review_history)
        ratings = [review.get("rating", 0) for review in review_history]
        avg_rating = sum(ratings) / len(ratings) if ratings else 0.0

        # Success rate (rating >= 3)
        successful_reviews = sum(1 for rating in ratings if rating >= 3)
        success_rate = successful_reviews / total_reviews if total_reviews > 0 else 0.0

        # Learning trend (compare recent vs older reviews)
        if total_reviews >= 4:
            recent_ratings = ratings[-3:]
            older_ratings = ratings[:-3]
            recent_avg = sum(recent_ratings) / len(recent_ratings)
            older_avg = sum(older_ratings) / len(older_ratings)

            if recent_avg > older_avg + 0.3:
                trend = "improving"
            elif recent_avg < older_avg - 0.3:
                trend = "declining"
            else:
                trend = "stable"
        else:
            trend = "insufficient_data"

        # Difficulty assessment
        if avg_rating >= 3.5:
            difficulty = "easy"
        elif avg_rating >= 2.5:
            difficulty = "moderate"
        elif avg_rating >= 1.5:
            difficulty = "hard"
        else:
            difficulty = "very_hard"

        return {
            "total_reviews": total_reviews,
            "avg_rating": round(avg_rating, 2),
            "success_rate": round(success_rate, 2),
            "learning_trend": trend,
            "difficulty_level": difficulty,
        }


# Global instance
_srs_system = None


def get_srs_system() -> SpacedRepetitionSystem:
    """Get global SRS system instance"""
    global _srs_system
    if _srs_system is None:
        _srs_system = SpacedRepetitionSystem()
    return _srs_system


def calculate_next_review(
    rating: int,
    repetitions: int = 0,
    interval_days: int = 1,
    easiness_factor: float = 2.5,
    review_date: date = None,
) -> ReviewResult:
    """Convenience function to calculate next review"""
    srs = get_srs_system()
    return srs.calculate_review(
        rating=rating,
        repetitions=repetitions,
        interval_days=interval_days,
        easiness_factor=easiness_factor,
        review_date=review_date,
    )


if __name__ == "__main__":
    # Test the SRS system
    srs = SpacedRepetitionSystem()

    # Test sequence of reviews
    print("Testing SRS system:")

    # Initial state
    repetitions = 0
    interval = 1
    easiness = 2.5

    for i, rating in enumerate([3, 3, 2, 3, 4]):
        result = srs.calculate_review(rating, repetitions, interval, easiness)
        print(
            f"Review {i+1}: rating={rating} -> interval={result.new_interval}, "
            f"ef={result.new_easiness_factor:.2f}, next={result.next_review_date}"
        )

        repetitions += 1
        interval = result.new_interval
        easiness = result.new_easiness_factor
