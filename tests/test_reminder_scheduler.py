"""
Test cases for the ReminderScheduler functionality
"""

import asyncio
import pytest
from datetime import datetime, time, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from src.core.scheduler.reminder_scheduler import ReminderScheduler


class TestReminderScheduler:
    """Test cases for ReminderScheduler class"""

    @pytest.fixture
    def mock_callback(self):
        """Mock callback for reminder scheduler"""
        return AsyncMock()

    @pytest.fixture
    def scheduler(self, mock_callback):
        """Create a ReminderScheduler instance for testing"""
        return ReminderScheduler(mock_callback)

    def test_reminder_scheduler_initialization(self, mock_callback):
        """Test ReminderScheduler initialization"""
        scheduler = ReminderScheduler(mock_callback)
        
        assert scheduler.send_reminder_callback == mock_callback
        assert scheduler.is_running is False
        assert scheduler.task is None
        assert scheduler.reminder_time == time(18, 0)

    @pytest.mark.asyncio
    async def test_start_scheduler(self, scheduler):
        """Test starting the reminder scheduler"""
        assert scheduler.is_running is False
        
        # Start scheduler
        await scheduler.start()
        
        assert scheduler.is_running is True
        assert scheduler.task is not None
        assert not scheduler.task.done()
        
        # Clean up
        await scheduler.stop()

    @pytest.mark.asyncio
    async def test_stop_scheduler(self, scheduler):
        """Test stopping the reminder scheduler"""
        # Start first
        await scheduler.start()
        assert scheduler.is_running is True
        
        # Stop
        await scheduler.stop()
        
        assert scheduler.is_running is False
        # Task should be cancelled
        if scheduler.task:
            assert scheduler.task.cancelled()

    @pytest.mark.asyncio
    async def test_start_already_running_scheduler(self, scheduler):
        """Test starting scheduler when already running"""
        await scheduler.start()
        
        # Try to start again
        await scheduler.start()
        
        # Should still be running
        assert scheduler.is_running is True
        
        # Clean up
        await scheduler.stop()

    @pytest.mark.asyncio
    async def test_stop_not_running_scheduler(self, scheduler):
        """Test stopping scheduler when not running"""
        assert scheduler.is_running is False
        
        # Should not raise exception
        await scheduler.stop()
        
        assert scheduler.is_running is False

    def test_get_next_reminder_time_today(self, scheduler):
        """Test getting next reminder time when today's time hasn't passed"""
        # Mock current time to be 17:00 (before 18:00)
        with patch('src.core.scheduler.reminder_scheduler.datetime') as mock_datetime:
            mock_now = datetime(2024, 1, 15, 17, 0, 0)  # 5 PM
            mock_datetime.now.return_value = mock_now
            mock_datetime.combine = datetime.combine
            
            next_reminder = scheduler._get_next_reminder_time()
            
            expected = datetime(2024, 1, 15, 18, 0, 0)  # Today at 6 PM
            assert next_reminder == expected

    def test_get_next_reminder_time_tomorrow(self, scheduler):
        """Test getting next reminder time when today's time has passed"""
        # Mock current time to be 19:00 (after 18:00)
        with patch('src.core.scheduler.reminder_scheduler.datetime') as mock_datetime:
            mock_now = datetime(2024, 1, 15, 19, 0, 0)  # 7 PM
            mock_datetime.now.return_value = mock_now
            mock_datetime.combine = datetime.combine
            
            # Mock the timedelta class within the datetime module
            mock_datetime.timedelta = timedelta
            
            next_reminder = scheduler._get_next_reminder_time()
            
            expected = datetime(2024, 1, 16, 18, 0, 0)  # Tomorrow at 6 PM
            assert next_reminder == expected

    @pytest.mark.asyncio
    async def test_send_daily_reminders_success(self, scheduler, mock_callback):
        """Test successful sending of daily reminders"""
        await scheduler._send_daily_reminders()
        
        mock_callback.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_daily_reminders_exception(self, scheduler, mock_callback):
        """Test handling exception during reminder sending"""
        mock_callback.side_effect = Exception("Test error")
        
        # Should not raise exception
        await scheduler._send_daily_reminders()
        
        mock_callback.assert_called_once()

    @pytest.mark.asyncio
    async def test_schedule_loop_single_iteration(self, scheduler, mock_callback):
        """Test single iteration of schedule loop"""
        # Mock sleep to avoid long waits
        with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            # Mock _get_next_reminder_time to return near future
            with patch.object(scheduler, '_get_next_reminder_time') as mock_next_time:
                mock_now = datetime.now()
                mock_next_time.return_value = mock_now + timedelta(seconds=1)
                
                # Start scheduler
                scheduler.is_running = True
                
                # Create task but stop it quickly
                task = asyncio.create_task(scheduler._schedule_loop())
                
                # Wait a bit then stop
                await asyncio.sleep(0.1)
                scheduler.is_running = False
                
                # Cancel and wait for completion
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                
                # Should have called sleep
                mock_sleep.assert_called()

    @pytest.mark.asyncio
    async def test_schedule_loop_exception_handling(self, scheduler):
        """Test exception handling in schedule loop"""
        with patch.object(scheduler, '_get_next_reminder_time', side_effect=Exception("Test error")):
            with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
                scheduler.is_running = True
                
                # Create task but stop it quickly
                task = asyncio.create_task(scheduler._schedule_loop())
                
                # Wait a bit then stop
                await asyncio.sleep(0.1)
                scheduler.is_running = False
                
                # Cancel and wait for completion
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                
                # Should have slept for error recovery
                mock_sleep.assert_called()

    @pytest.mark.asyncio
    async def test_schedule_loop_cancellation(self, scheduler):
        """Test proper cancellation handling in schedule loop"""
        scheduler.is_running = True
        
        # Start the loop
        task = asyncio.create_task(scheduler._schedule_loop())
        
        # Cancel immediately
        task.cancel()
        
        # Should handle CancelledError gracefully
        with pytest.raises(asyncio.CancelledError):
            await task


class TestReminderSchedulerIntegration:
    """Integration tests for ReminderScheduler"""

    @pytest.mark.asyncio
    async def test_scheduler_lifecycle(self):
        """Test complete scheduler lifecycle"""
        callback_called = False
        
        async def test_callback():
            nonlocal callback_called
            callback_called = True
        
        scheduler = ReminderScheduler(test_callback)
        
        # Start
        await scheduler.start()
        assert scheduler.is_running is True
        
        # Stop
        await scheduler.stop()
        assert scheduler.is_running is False

    @pytest.mark.asyncio
    async def test_multiple_start_stop_cycles(self):
        """Test multiple start/stop cycles"""
        callback = AsyncMock()
        scheduler = ReminderScheduler(callback)
        
        # Multiple cycles
        for _ in range(3):
            await scheduler.start()
            assert scheduler.is_running is True
            
            await scheduler.stop()
            assert scheduler.is_running is False

    @pytest.mark.asyncio
    async def test_scheduler_with_immediate_reminder_time(self):
        """Test scheduler when reminder time is immediate"""
        callback = AsyncMock()
        scheduler = ReminderScheduler(callback)
        
        # Mock time to be exactly reminder time
        with patch('src.core.scheduler.reminder_scheduler.datetime') as mock_datetime:
            mock_now = datetime(2024, 1, 15, 18, 0, 0)  # Exactly 6 PM
            mock_datetime.now.return_value = mock_now
            mock_datetime.combine = datetime.combine
            
            # Mock the timedelta class within the datetime module
            mock_datetime.timedelta = timedelta
            
            next_reminder = scheduler._get_next_reminder_time()
            
            # Should schedule for tomorrow since current time >= reminder time
            expected = datetime(2024, 1, 16, 18, 0, 0)
            assert next_reminder == expected