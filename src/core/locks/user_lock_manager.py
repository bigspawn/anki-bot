"""User lock manager for preventing concurrent operations"""

import asyncio
import contextlib
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


@dataclass
class LockInfo:
    """Information about a user lock"""

    locked_at: datetime
    operation: str
    lock_id: str


class UserLockManager:
    """Manages user locks to prevent concurrent operations"""

    def __init__(self, lock_timeout_minutes: int = 5):
        """
        Initialize the user lock manager

        Args:
            lock_timeout_minutes: Minutes after which locks expire automatically
        """
        self._locks: dict[int, LockInfo] = {}
        self._lock_timeout = timedelta(minutes=lock_timeout_minutes)
        self._cleanup_task: asyncio.Task | None = None

    async def start(self):
        """Start the lock manager and cleanup task"""
        logger.info("Starting UserLockManager")
        self._cleanup_task = asyncio.create_task(self._periodic_cleanup())

    async def stop(self):
        """Stop the lock manager and cleanup task"""
        logger.info("Stopping UserLockManager")
        if self._cleanup_task:
            self._cleanup_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._cleanup_task
        self._locks.clear()

    def is_locked(self, user_id: int) -> bool:
        """
        Check if user is currently locked

        Args:
            user_id: Telegram user ID

        Returns:
            True if user is locked, False otherwise
        """
        self._cleanup_expired_locks()
        return user_id in self._locks

    def get_lock_info(self, user_id: int) -> LockInfo | None:
        """
        Get lock information for user

        Args:
            user_id: Telegram user ID

        Returns:
            LockInfo if user is locked, None otherwise
        """
        self._cleanup_expired_locks()
        return self._locks.get(user_id)

    def acquire_lock(self, user_id: int, operation: str) -> bool:
        """
        Try to acquire lock for user

        Args:
            user_id: Telegram user ID
            operation: Name of operation being locked

        Returns:
            True if lock acquired, False if user already locked
        """
        self._cleanup_expired_locks()

        if user_id in self._locks:
            logger.warning(
                f"User {user_id} already locked for operation: {self._locks[user_id].operation}"
            )
            return False

        lock_info = LockInfo(
            locked_at=datetime.now(),
            operation=operation,
            lock_id=f"{user_id}_{operation}_{datetime.now().timestamp()}",
        )

        self._locks[user_id] = lock_info
        logger.info(f"Acquired lock for user {user_id}, operation: {operation}")
        return True

    def release_lock(self, user_id: int) -> bool:
        """
        Release lock for user

        Args:
            user_id: Telegram user ID

        Returns:
            True if lock was released, False if user was not locked
        """
        if user_id not in self._locks:
            logger.warning(f"Attempted to release non-existent lock for user {user_id}")
            return False

        lock_info = self._locks.pop(user_id)
        logger.info(
            f"Released lock for user {user_id}, operation: {lock_info.operation}"
        )
        return True

    def force_release_lock(self, user_id: int) -> bool:
        """
        Force release lock for user (admin operation)

        Args:
            user_id: Telegram user ID

        Returns:
            True if lock was released, False if user was not locked
        """
        if user_id not in self._locks:
            return False

        lock_info = self._locks.pop(user_id)
        logger.warning(
            f"Force released lock for user {user_id}, operation: {lock_info.operation}"
        )
        return True

    def get_active_locks_count(self) -> int:
        """Get number of currently active locks"""
        self._cleanup_expired_locks()
        return len(self._locks)

    def get_all_locked_users(self) -> dict[int, LockInfo]:
        """Get all currently locked users"""
        self._cleanup_expired_locks()
        return self._locks.copy()

    def _cleanup_expired_locks(self):
        """Remove expired locks"""
        current_time = datetime.now()
        expired_users = []

        for user_id, lock_info in self._locks.items():
            if current_time - lock_info.locked_at > self._lock_timeout:
                expired_users.append(user_id)

        for user_id in expired_users:
            lock_info = self._locks.pop(user_id)
            logger.warning(
                f"Expired lock removed for user {user_id}, operation: {lock_info.operation}"
            )

    async def _periodic_cleanup(self):
        """Periodic cleanup task that runs every minute"""
        while True:
            try:
                await asyncio.sleep(60)  # Run every minute
                self._cleanup_expired_locks()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in periodic cleanup: {e}")
