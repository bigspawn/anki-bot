"""
Unit tests for spaced repetition system
"""

from datetime import date

import pytest

from src.spaced_repetition import (
    ReviewResult,
    SpacedRepetitionSystem,
    calculate_next_review,
    get_srs_system,
)


class TestReviewResult:
    """Test ReviewResult dataclass"""

    def test_review_result_creation(self):
        """Test ReviewResult creation"""
        result = ReviewResult(
            new_interval=3,
            new_easiness_factor=2.8,
            next_review_date=date.today(),
            is_graduated=True,
        )

        assert result.new_interval == 3
        assert result.new_easiness_factor == 2.8
        assert result.next_review_date == date.today()
        assert result.is_graduated is True

    def test_review_result_defaults(self):
        """Test ReviewResult default values"""
        result = ReviewResult(
            new_interval=1, new_easiness_factor=2.5, next_review_date=date.today()
        )

        assert result.is_graduated is False  # Default value


class TestSpacedRepetitionSystem:
    """Test SpacedRepetitionSystem class"""

    @pytest.fixture
    def srs(self):
        """Create SRS instance for testing"""
        return SpacedRepetitionSystem()

    def test_srs_initialization(self, srs):
        """Test SRS system initialization"""
        assert srs.default_easiness == 2.5
        assert srs.min_easiness == 1.3
        assert srs.max_easiness == 3.0

    def test_again_rating(self, srs):
        """Test 'Again' rating (1) - should reset interval"""
        result = srs.calculate_review(
            rating=1, repetitions=3, interval_days=10, easiness_factor=2.8
        )

        assert result.new_interval == 0  # Reset to immediate review
        assert result.new_easiness_factor < 2.8  # Decreased easiness
        assert result.next_review_date == date.today()
        assert result.is_graduated is False

    def test_hard_rating(self, srs):
        """Test 'Hard' rating (2)"""
        result = srs.calculate_review(
            rating=2, repetitions=2, interval_days=6, easiness_factor=2.5
        )

        assert result.new_interval >= 1
        assert result.new_easiness_factor < 2.5  # Decreased
        assert result.next_review_date > date.today()

    def test_good_rating(self, srs):
        """Test 'Good' rating (3)"""
        result = srs.calculate_review(
            rating=3, repetitions=2, interval_days=6, easiness_factor=2.5
        )

        assert result.new_interval >= 6
        assert result.new_easiness_factor == 2.5  # Unchanged
        assert result.next_review_date > date.today()

    def test_easy_rating(self, srs):
        """Test 'Easy' rating (4)"""
        result = srs.calculate_review(
            rating=4, repetitions=2, interval_days=6, easiness_factor=2.5
        )

        assert result.new_interval > 6  # Increased more than good
        assert result.new_easiness_factor > 2.5  # Increased
        assert result.next_review_date > date.today()

    def test_first_repetition_sequence(self, srs):
        """Test first few repetitions sequence"""
        # First review - Good
        result1 = srs.calculate_review(
            rating=3, repetitions=0, interval_days=1, easiness_factor=2.5
        )
        assert result1.new_interval == 1

        # Second review - Good
        result2 = srs.calculate_review(
            rating=3,
            repetitions=1,
            interval_days=result1.new_interval,
            easiness_factor=result1.new_easiness_factor,
        )
        assert result2.new_interval == 6

        # Third review - Good
        result3 = srs.calculate_review(
            rating=3,
            repetitions=2,
            interval_days=result2.new_interval,
            easiness_factor=result2.new_easiness_factor,
        )
        assert result3.new_interval > 6
        assert result3.is_graduated is True

    def test_easiness_factor_bounds(self, srs):
        """Test easiness factor stays within bounds"""
        # Test minimum bound
        result = srs.calculate_review(
            rating=2,  # Hard rating
            repetitions=1,
            interval_days=1,
            easiness_factor=1.3,  # Already at minimum
        )
        assert result.new_easiness_factor >= srs.min_easiness

        # Test maximum bound (simulate many easy ratings)
        easiness = 2.9
        for _ in range(5):
            result = srs.calculate_review(
                rating=4,  # Easy rating
                repetitions=3,
                interval_days=10,
                easiness_factor=easiness,
            )
            easiness = result.new_easiness_factor

        assert easiness <= srs.max_easiness

    def test_interval_maximum_cap(self, srs):
        """Test interval doesn't exceed maximum"""
        # Simulate many successful reviews
        interval = 100
        easiness = 3.0

        result = srs.calculate_review(
            rating=4,  # Easy
            repetitions=10,
            interval_days=interval,
            easiness_factor=easiness,
        )

        assert result.new_interval <= 365  # Should be capped at 1 year

    def test_invalid_rating(self, srs):
        """Test invalid rating raises error"""
        with pytest.raises(ValueError):
            srs.calculate_review(
                rating=0, repetitions=1, interval_days=1, easiness_factor=2.5  # Invalid
            )

        with pytest.raises(ValueError):
            srs.calculate_review(
                rating=5, repetitions=1, interval_days=1, easiness_factor=2.5  # Invalid
            )

    def test_get_initial_review_schedule(self, srs):
        """Test initial review schedule"""
        result = srs.get_initial_review_schedule()

        assert result.new_interval == 1
        assert result.new_easiness_factor == srs.default_easiness
        assert result.next_review_date == date.today()
        assert result.is_graduated is False

    def test_predict_retention(self, srs):
        """Test retention prediction"""
        # Same day retention should be high
        retention_today = srs.predict_retention(0, 2.5)
        assert retention_today == 1.0

        # Retention decreases over time
        retention_week = srs.predict_retention(7, 2.5)
        retention_month = srs.predict_retention(30, 2.5)

        assert 0.0 <= retention_week <= 1.0
        assert 0.0 <= retention_month <= 1.0
        assert retention_week > retention_month

        # Higher easiness should give better retention
        retention_easy = srs.predict_retention(7, 3.0)
        retention_hard = srs.predict_retention(7, 2.0)

        assert retention_easy > retention_hard

    def test_get_optimal_review_time(self, srs):
        """Test optimal review time calculation"""
        optimal_days = srs.get_optimal_review_time(2.5, target_retention=0.85)

        assert isinstance(optimal_days, int)
        assert optimal_days >= 1
        assert optimal_days <= 365

        # Higher easiness should allow longer intervals
        optimal_easy = srs.get_optimal_review_time(3.0, target_retention=0.85)
        optimal_hard = srs.get_optimal_review_time(2.0, target_retention=0.85)

        assert optimal_easy >= optimal_hard

    def test_analyze_learning_progress_empty(self, srs):
        """Test learning progress analysis with empty history"""
        result = srs.analyze_learning_progress([])

        assert result["total_reviews"] == 0
        assert result["avg_rating"] == 0.0
        assert result["success_rate"] == 0.0
        assert result["learning_trend"] == "stable"
        assert result["difficulty_level"] == "unknown"

    def test_analyze_learning_progress_with_data(self, srs):
        """Test learning progress analysis with review data"""
        review_history = [
            {"rating": 2},
            {"rating": 3},
            {"rating": 3},
            {"rating": 4},
            {"rating": 4},
            {"rating": 3},
        ]

        result = srs.analyze_learning_progress(review_history)

        assert result["total_reviews"] == 6
        assert result["avg_rating"] > 0
        assert result["success_rate"] > 0  # Ratings >= 3
        assert result["learning_trend"] in ["improving", "declining", "stable"]
        assert result["difficulty_level"] in ["easy", "moderate", "hard", "very_hard"]

    def test_analyze_learning_progress_improving_trend(self, srs):
        """Test learning progress with improving trend"""
        # Start with poor performance, end with good
        review_history = [
            {"rating": 1},
            {"rating": 2},
            {"rating": 2},
            {"rating": 3},
            {"rating": 4},
            {"rating": 4},
        ]

        result = srs.analyze_learning_progress(review_history)
        assert result["learning_trend"] == "improving"

    def test_analyze_learning_progress_declining_trend(self, srs):
        """Test learning progress with declining trend"""
        # Start with good performance, end with poor
        review_history = [
            {"rating": 4},
            {"rating": 4},
            {"rating": 3},
            {"rating": 2},
            {"rating": 1},
            {"rating": 1},
        ]

        result = srs.analyze_learning_progress(review_history)
        assert result["learning_trend"] == "declining"


class TestGlobalFunctions:
    """Test global SRS functions"""

    def test_get_srs_system(self):
        """Test getting global SRS system"""
        srs1 = get_srs_system()
        srs2 = get_srs_system()

        assert srs1 is srs2  # Should return same instance
        assert isinstance(srs1, SpacedRepetitionSystem)

    def test_calculate_next_review(self):
        """Test convenience function"""
        result = calculate_next_review(
            rating=3, repetitions=1, interval_days=1, easiness_factor=2.5
        )

        assert isinstance(result, ReviewResult)
        assert result.new_interval > 0
        assert result.new_easiness_factor > 0
        assert result.next_review_date >= date.today()


class TestRealWorldScenarios:
    """Test real-world learning scenarios"""

    def test_struggling_word_scenario(self):
        """Test scenario with a difficult word"""
        srs = SpacedRepetitionSystem()

        # Word that user keeps forgetting
        ratings = [1, 2, 1, 2, 3, 2, 3, 3, 4]

        repetitions = 0
        interval = 1
        easiness = 2.5

        results = []
        for rating in ratings:
            result = srs.calculate_review(rating, repetitions, interval, easiness)
            results.append(result)

            if rating > 1:  # Only increment if not "Again"
                repetitions += 1
            else:
                repetitions = 0  # Reset on "Again"

            interval = result.new_interval
            easiness = result.new_easiness_factor

        # Final easiness should be lower due to difficulties
        assert results[-1].new_easiness_factor < 2.5

        # Should eventually have some graduation
        graduated_count = sum(1 for r in results if r.is_graduated)
        assert graduated_count > 0

    def test_easy_word_scenario(self):
        """Test scenario with an easy word"""
        srs = SpacedRepetitionSystem()

        # Word that user finds easy
        ratings = [4, 4, 4, 3, 4, 4]

        repetitions = 0
        interval = 1
        easiness = 2.5

        for i, rating in enumerate(ratings):
            current_repetitions = repetitions + i
            result = srs.calculate_review(rating, current_repetitions, interval, easiness)
            interval = result.new_interval
            easiness = result.new_easiness_factor

        # Final easiness should be higher
        assert easiness > 2.5

        # Final interval should be substantial
        assert interval > 10

    def test_consistent_good_performance(self):
        """Test consistent good performance"""
        srs = SpacedRepetitionSystem()

        repetitions = 0
        interval = 1
        easiness = 2.5

        # Simulate 10 "Good" ratings
        for i in range(10):
            current_repetitions = repetitions + i
            result = srs.calculate_review(3, current_repetitions, interval, easiness)
            interval = result.new_interval
            easiness = result.new_easiness_factor

        # Easiness should remain stable around default
        assert abs(easiness - 2.5) < 0.1

        # Interval should grow significantly but not excessively
        assert 20 <= interval <= 400  # Allow for longer intervals in SuperMemo 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
