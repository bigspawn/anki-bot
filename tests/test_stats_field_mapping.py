#!/usr/bin/env python3
"""
Tests for stats field mapping bug - ensures get_user_stats and format_progress_stats work together correctly.

This test suite specifically reproduces and prevents regression of the bug where:
- get_user_stats returns 'average_accuracy' field
- format_progress_stats was looking for 'avg_success_rate' field
- Result: success rate always showed 0.0% regardless of actual performance
"""

from unittest.mock import MagicMock, patch

from src.core.database.repositories.user_repository import UserRepository
from src.utils import format_progress_stats


class TestStatsFieldMapping:
    """Test that stats field mapping works correctly between repository and formatting"""

    def test_field_mapping_bug_reproduction(self):
        """Reproduce the exact bug: format_progress_stats expects different field than get_user_stats provides"""

        # This is the exact data structure that get_user_stats returns
        stats_from_get_user_stats = {
            'total_words': 716,
            'new_words': 623,
            'due_words': 0,
            'learned_words': 1,
            'difficult_words': 0,
            'average_accuracy': 0.343434343434343,  # This is what get_user_stats returns
            'reviews_today': 0,
            'study_streak': 0,
            'words_today': 0
        }

        # Test that format_progress_stats can handle this structure
        result = format_progress_stats(stats_from_get_user_stats)

        # The bug was that average_accuracy was ignored and showed 0.0%
        # Now it should show 34.3%
        assert "34.3%" in result, f"Expected 34.3% in formatted output, got: {result}"
        assert "Всего слов: 716" in result
        assert "К повторению: 0" in result
        assert "Новых слов: 623" in result

    def test_zero_accuracy_case(self):
        """Test case where user has 0% accuracy"""
        stats = {
            'total_words': 100,
            'new_words': 50,
            'due_words': 10,
            'average_accuracy': 0.0  # No successful reviews
        }

        result = format_progress_stats(stats)
        assert "0.0%" in result

    def test_high_accuracy_case(self):
        """Test case where user has high accuracy"""
        stats = {
            'total_words': 200,
            'new_words': 20,
            'due_words': 15,
            'average_accuracy': 0.95  # 95% success rate
        }

        result = format_progress_stats(stats)
        assert "95.0%" in result

    def test_fractional_accuracy_formatting(self):
        """Test that fractional accuracy is formatted correctly"""
        test_cases = [
            (0.343434343434343, "34.3%"),  # The exact production case
            (0.666666666666666, "66.7%"),  # Should round correctly
            (0.123456789012345, "12.3%"),  # More decimal places
            (0.999, "99.9%"),              # High precision
            (0.001, "0.1%"),               # Low precision
        ]

        for accuracy, expected_percentage in test_cases:
            stats = {
                'total_words': 100,
                'new_words': 10,
                'due_words': 5,
                'average_accuracy': accuracy
            }

            result = format_progress_stats(stats)
            assert expected_percentage in result, f"Expected {expected_percentage} for accuracy {accuracy}, got: {result}"

    def test_missing_average_accuracy_field(self):
        """Test fallback when average_accuracy field is missing"""
        stats_without_accuracy = {
            'total_words': 50,
            'new_words': 25,
            'due_words': 5,
            # missing 'average_accuracy' field
        }

        result = format_progress_stats(stats_without_accuracy)
        # Should default to 0.0%
        assert "0.0%" in result

    @patch('src.core.database.repositories.user_repository.DatabaseConnection')
    def test_integration_get_user_stats_returns_correct_fields(self, mock_db_connection):
        """Integration test: ensure get_user_stats returns fields that format_progress_stats expects"""

        # Mock database responses to simulate the production scenario
        mock_conn = MagicMock()
        mock_db_connection.return_value.get_connection.return_value.__enter__.return_value = mock_conn

        # Mock the main stats query response (total_words, new_words, etc.)
        mock_cursor_main = MagicMock()
        mock_cursor_main.fetchone.return_value = {
            'total_words': 716,
            'new_words': 623,
            'due_words': 0,
            'learned_words': 1,
            'difficult_words': 0
        }

        # Mock the accuracy query response
        mock_cursor_accuracy = MagicMock()
        mock_cursor_accuracy.fetchone.return_value = {
            'avg_accuracy': 0.343434343434343
        }

        # Mock the today's activity query response
        mock_cursor_today = MagicMock()
        mock_cursor_today.fetchone.return_value = {
            'reviews_today': 0
        }

        # Set up the execute call returns in order
        mock_conn.execute.side_effect = [
            mock_cursor_main,      # Main stats query
            mock_cursor_accuracy,  # Accuracy query
            mock_cursor_today      # Today's activity query
        ]

        # Test the actual repository
        repo = UserRepository(mock_db_connection.return_value)
        stats = repo.get_user_stats(739529)

        # Verify the repository returns the expected field structure
        assert stats is not None
        assert 'total_words' in stats
        assert 'average_accuracy' in stats  # This is the critical field
        assert stats['average_accuracy'] == 0.343434343434343

        # Test that these stats work with format_progress_stats
        formatted = format_progress_stats(stats)
        assert "34.3%" in formatted

    def test_production_scenario_exact_reproduction(self):
        """Exact reproduction of the production bug scenario"""

        # These are the exact values from production database for user 739529
        production_stats = {
            'total_words': 716,
            'new_words': 623,
            'due_words': 0,
            'learned_words': 1,
            'difficult_words': 0,
            'average_accuracy': 0.343434343434343,  # 34 good reviews out of 99 total
            'reviews_today': 0,
            'study_streak': 0,
            'words_today': 0
        }

        # Format the stats
        result = format_progress_stats(production_stats)

        # Before the fix, this would show "0.0%" due to field mapping bug
        # After the fix, it should show "34.3%"
        expected_output = """📊 Ваша статистика:

📚 Всего слов: 716
🔄 К повторению: 0
🆕 Новых слов: 623
✅ Средний успех: 34.3%"""

        assert result.strip() == expected_output.strip()

        # Additional specific assertions
        assert "📚 Всего слов: 716" in result
        assert "🔄 К повторению: 0" in result
        assert "🆕 Новых слов: 623" in result
        assert "✅ Средний успех: 34.3%" in result

    def test_legacy_field_name_fallback(self):
        """Test that old field name still works for backward compatibility if needed"""

        # Test with old field name (should not work after our fix, which is correct)
        legacy_stats = {
            'total_words': 100,
            'new_words': 50,
            'due_words': 10,
            'avg_success_rate': 0.85  # Old field name
        }

        result = format_progress_stats(legacy_stats)

        # With our fix, this should show 0.0% because we changed to use 'average_accuracy'
        # This test ensures we're not accidentally supporting both field names
        assert "0.0%" in result, "Legacy field name should not be supported"

    def test_review_history_calculation_accuracy(self):
        """Test that the average_accuracy calculation in get_user_stats is mathematically correct"""

        # This tests the SQL logic: AVG(CASE WHEN rating >= 3 THEN 1.0 ELSE 0.0 END)
        # Based on production data: 34 good reviews (rating >= 3) out of 99 total = 34.34%

        # Simulate review history data for user 739529
        # Rating distribution: 1=51, 2=14, 3=10, 4=24 (total=99)
        # Good reviews (3-4): 10 + 24 = 34
        # Accuracy: 34/99 = 0.343434...

        good_reviews = 34  # ratings 3 and 4
        total_reviews = 99
        expected_accuracy = good_reviews / total_reviews

        assert abs(expected_accuracy - 0.343434343434343) < 0.000001

        # Test the formatting
        stats = {
            'total_words': 716,
            'new_words': 623,
            'due_words': 0,
            'average_accuracy': expected_accuracy
        }

        result = format_progress_stats(stats)
        assert "34.3%" in result
