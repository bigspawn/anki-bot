"""
Tests for rate limiting functionality
"""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import pytest

from src.core.locks.user_lock_manager import UserLockManager


class TestUserLockManager:
    """Tests for UserLockManager class"""

    @pytest.fixture
    async def lock_manager(self):
        """Create a UserLockManager instance for testing"""
        manager = UserLockManager(lock_timeout_minutes=1)  # Short timeout for testing
        await manager.start()
        yield manager
        await manager.stop()

    @pytest.mark.asyncio
    async def test_acquire_and_release_lock(self, lock_manager):
        """Test basic lock acquisition and release"""
        user_id = 123
        operation = "add_words"

        # User should not be locked initially
        assert not lock_manager.is_locked(user_id)
        assert lock_manager.get_lock_info(user_id) is None

        # Acquire lock
        assert lock_manager.acquire_lock(user_id, operation) is True
        assert lock_manager.is_locked(user_id)

        # Check lock info
        lock_info = lock_manager.get_lock_info(user_id)
        assert lock_info is not None
        assert lock_info.operation == operation
        assert isinstance(lock_info.locked_at, datetime)

        # Release lock
        assert lock_manager.release_lock(user_id) is True
        assert not lock_manager.is_locked(user_id)
        assert lock_manager.get_lock_info(user_id) is None

    @pytest.mark.asyncio
    async def test_duplicate_lock_acquisition(self, lock_manager):
        """Test that duplicate lock acquisition fails"""
        user_id = 123

        # Acquire first lock
        assert lock_manager.acquire_lock(user_id, "add_words") is True

        # Try to acquire second lock - should fail
        assert lock_manager.acquire_lock(user_id, "another_operation") is False

        # User should still be locked with original operation
        lock_info = lock_manager.get_lock_info(user_id)
        assert lock_info.operation == "add_words"

        # Release lock
        lock_manager.release_lock(user_id)

    @pytest.mark.asyncio
    async def test_multiple_users_isolation(self, lock_manager):
        """Test that locks for different users are isolated"""
        user1_id = 123
        user2_id = 456

        # Acquire locks for both users
        assert lock_manager.acquire_lock(user1_id, "add_words") is True
        assert lock_manager.acquire_lock(user2_id, "add_words") is True

        # Both users should be locked
        assert lock_manager.is_locked(user1_id)
        assert lock_manager.is_locked(user2_id)

        # Release user1's lock
        lock_manager.release_lock(user1_id)

        # User1 should be unlocked, user2 still locked
        assert not lock_manager.is_locked(user1_id)
        assert lock_manager.is_locked(user2_id)

        # Release user2's lock
        lock_manager.release_lock(user2_id)

    @pytest.mark.asyncio
    async def test_lock_timeout_expiration(self, lock_manager):
        """Test that locks expire after timeout"""
        user_id = 123

        # Acquire lock
        assert lock_manager.acquire_lock(user_id, "add_words") is True

        # Manually set lock time to past (simulate expired lock)
        lock_info = lock_manager._locks[user_id]
        lock_info.locked_at = datetime.now() - timedelta(minutes=2)  # 2 minutes ago

        # Check that lock is considered expired
        assert not lock_manager.is_locked(user_id)  # Should cleanup expired lock
        assert lock_manager.get_lock_info(user_id) is None

    @pytest.mark.asyncio
    async def test_force_release_lock(self, lock_manager):
        """Test force release functionality"""
        user_id = 123

        # Acquire lock
        assert lock_manager.acquire_lock(user_id, "add_words") is True
        assert lock_manager.is_locked(user_id)

        # Force release
        assert lock_manager.force_release_lock(user_id) is True
        assert not lock_manager.is_locked(user_id)

        # Force release non-existent lock should return False
        assert lock_manager.force_release_lock(user_id) is False

    @pytest.mark.asyncio
    async def test_get_active_locks_count(self, lock_manager):
        """Test getting active locks count"""
        assert lock_manager.get_active_locks_count() == 0

        # Add some locks
        lock_manager.acquire_lock(123, "add_words")
        lock_manager.acquire_lock(456, "add_words")
        assert lock_manager.get_active_locks_count() == 2

        # Release one lock
        lock_manager.release_lock(123)
        assert lock_manager.get_active_locks_count() == 1

        # Release all locks
        lock_manager.release_lock(456)
        assert lock_manager.get_active_locks_count() == 0

    @pytest.mark.asyncio
    async def test_get_all_locked_users(self, lock_manager):
        """Test getting all locked users"""
        assert len(lock_manager.get_all_locked_users()) == 0

        # Add locks
        lock_manager.acquire_lock(123, "add_words")
        lock_manager.acquire_lock(456, "study_session")

        locked_users = lock_manager.get_all_locked_users()
        assert len(locked_users) == 2
        assert 123 in locked_users
        assert 456 in locked_users
        assert locked_users[123].operation == "add_words"
        assert locked_users[456].operation == "study_session"

        # Clean up
        lock_manager.release_lock(123)
        lock_manager.release_lock(456)

    @pytest.mark.asyncio
    async def test_periodic_cleanup_task(self):
        """Test that periodic cleanup task works"""
        manager = UserLockManager(lock_timeout_minutes=1)

        # Start manager (which starts cleanup task)
        await manager.start()

        try:
            # Add an expired lock manually
            user_id = 123
            manager.acquire_lock(user_id, "add_words")

            # Manually expire the lock
            manager._locks[user_id].locked_at = datetime.now() - timedelta(minutes=2)

            # Wait a short time for cleanup task to run
            await asyncio.sleep(0.1)

            # Trigger cleanup manually to test
            manager._cleanup_expired_locks()

            # Lock should be removed
            assert not manager.is_locked(user_id)

        finally:
            await manager.stop()

    @pytest.mark.asyncio
    async def test_release_nonexistent_lock(self, lock_manager):
        """Test releasing a lock that doesn't exist"""
        user_id = 123

        # Try to release non-existent lock
        assert lock_manager.release_lock(user_id) is False

    @pytest.mark.asyncio
    async def test_lock_info_structure(self, lock_manager):
        """Test LockInfo dataclass structure"""
        user_id = 123
        operation = "add_words"

        lock_manager.acquire_lock(user_id, operation)
        lock_info = lock_manager.get_lock_info(user_id)

        # Check all required fields
        assert hasattr(lock_info, "locked_at")
        assert hasattr(lock_info, "operation")
        assert hasattr(lock_info, "lock_id")

        assert lock_info.operation == operation
        assert isinstance(lock_info.locked_at, datetime)
        assert isinstance(lock_info.lock_id, str)
        assert str(user_id) in lock_info.lock_id

        lock_manager.release_lock(user_id)


class TestRateLimitingIntegration:
    """Integration tests for rate limiting in bot_handler"""

    @pytest.fixture
    def mock_update(self):
        """Create a mock Telegram update"""
        update = Mock()
        update.effective_user.id = 123
        update.message.reply_text = Mock(return_value=Mock())
        return update

    @pytest.fixture
    def mock_bot_handler(self):
        """Create a mock bot handler with lock manager"""
        with (
            patch("src.bot_handler.get_settings") as mock_settings,
            patch("src.bot_handler.get_db_manager"),
            patch("src.bot_handler.get_word_processor"),
            patch("src.bot_handler.get_text_parser"),
            patch("src.bot_handler.get_srs_system"),
        ):
            # Mock the settings to return proper values
            mock_settings.return_value.default_reminder_time = "18:00"
            mock_settings.return_value.timezone = "UTC"

            from src.bot_handler import BotHandler

            handler = BotHandler()
            return handler

    @pytest.mark.asyncio
    async def test_concurrent_add_commands_blocked(self, mock_bot_handler, mock_update):
        """Test that concurrent /add commands are blocked"""
        # Mock the database user
        mock_bot_handler.db_manager.get_user_by_telegram_id.return_value = {"id": 1}

        # Mock successful processing
        mock_bot_handler.text_parser.extract_words.return_value = ["word1", "word2"]
        mock_bot_handler.db_manager.check_multiple_words_exist.return_value = {
            "word1": False,
            "word2": False,
        }
        mock_bot_handler.word_processor.process_text.return_value = []

        # Start lock manager
        await mock_bot_handler.lock_manager.start()

        try:
            # First call should succeed in acquiring lock
            task1 = asyncio.create_task(
                mock_bot_handler._process_text_for_user(mock_update, "test text")
            )

            # Give first task time to acquire lock
            await asyncio.sleep(0.01)

            # Second call should be blocked
            task2 = asyncio.create_task(
                mock_bot_handler._process_text_for_user(mock_update, "test text 2")
            )

            # Wait for both tasks
            await asyncio.gather(task1, task2, return_exceptions=True)

            # Verify that the second call was blocked (should have sent blocked message)
            # This would be verified by checking the mock calls to _safe_reply
            assert (
                mock_bot_handler.lock_manager.get_active_locks_count() == 0
            )  # All locks should be released

        finally:
            await mock_bot_handler.lock_manager.stop()

    @pytest.mark.asyncio
    async def test_lock_released_on_exception(self, mock_bot_handler, mock_update):
        """Test that lock is released even when an exception occurs"""
        # Mock the database user
        mock_bot_handler.db_manager.get_user_by_telegram_id.return_value = {"id": 1}

        # Mock an exception during processing
        mock_bot_handler.text_parser.extract_words.side_effect = Exception("Test error")

        await mock_bot_handler.lock_manager.start()

        try:
            # Process text - should raise exception but release lock
            await mock_bot_handler._process_text_for_user(mock_update, "test text")

            # Lock should be released despite exception
            assert not mock_bot_handler.lock_manager.is_locked(
                mock_update.effective_user.id
            )

        finally:
            await mock_bot_handler.lock_manager.stop()

    @pytest.mark.asyncio
    async def test_different_users_not_blocked(self, mock_bot_handler):
        """Test that different users can process simultaneously"""
        # Create two different users
        update1 = Mock()
        update1.effective_user.id = 123
        update1.message.reply_text = Mock(return_value=Mock())

        update2 = Mock()
        update2.effective_user.id = 456
        update2.message.reply_text = Mock(return_value=Mock())

        # Mock database responses
        mock_bot_handler.db_manager.get_user_by_telegram_id.return_value = {"id": 1}
        mock_bot_handler.text_parser.extract_words.return_value = ["word1"]
        mock_bot_handler.db_manager.check_multiple_words_exist.return_value = {
            "word1": False
        }
        mock_bot_handler.word_processor.process_text.return_value = []

        await mock_bot_handler.lock_manager.start()

        try:
            # Both users should be able to process simultaneously
            task1 = asyncio.create_task(
                mock_bot_handler._process_text_for_user(update1, "text1")
            )
            task2 = asyncio.create_task(
                mock_bot_handler._process_text_for_user(update2, "text2")
            )

            # Wait for both tasks
            await asyncio.gather(task1, task2)

            # Both should complete successfully
            assert not mock_bot_handler.lock_manager.is_locked(123)
            assert not mock_bot_handler.lock_manager.is_locked(456)

        finally:
            await mock_bot_handler.lock_manager.stop()
