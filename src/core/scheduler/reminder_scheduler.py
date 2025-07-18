"""
Daily reminder scheduler for sending study notifications
"""

import asyncio
import contextlib
import logging
from collections.abc import Callable
from datetime import datetime, time

logger = logging.getLogger(__name__)


class ReminderScheduler:
    """Scheduler for daily study reminders"""

    def __init__(self, send_reminder_callback: Callable[[int], None]):
        self.send_reminder_callback = send_reminder_callback
        self.is_running = False
        self.task = None
        self.reminder_time = time(18, 0)  # 6 PM

    async def start(self):
        """Start the reminder scheduler"""
        if self.is_running:
            logger.warning("Reminder scheduler is already running")
            return

        self.is_running = True
        self.task = asyncio.create_task(self._schedule_loop())
        logger.info("Reminder scheduler started")

    async def stop(self):
        """Stop the reminder scheduler"""
        if not self.is_running:
            return

        self.is_running = False
        if self.task:
            self.task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.task
        logger.info("Reminder scheduler stopped")

    async def _schedule_loop(self):
        """Main scheduling loop"""
        while self.is_running:
            try:
                # Calculate next reminder time
                next_reminder = self._get_next_reminder_time()
                now = datetime.now()

                # Calculate sleep duration
                sleep_duration = (next_reminder - now).total_seconds()

                if sleep_duration > 0:
                    logger.info(f"Next reminder scheduled for {next_reminder}")
                    await asyncio.sleep(sleep_duration)

                # Send reminders if still running
                if self.is_running:
                    await self._send_daily_reminders()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in reminder scheduler: {e}")
                # Sleep for a minute before retrying
                await asyncio.sleep(60)

    def _get_next_reminder_time(self) -> datetime:
        """Get the next reminder time"""
        now = datetime.now()
        today_reminder = datetime.combine(now.date(), self.reminder_time)

        # If today's reminder time has passed, schedule for tomorrow
        if now >= today_reminder:
            from datetime import timedelta

            tomorrow = now.date() + timedelta(days=1)
            return datetime.combine(tomorrow, self.reminder_time)
        else:
            return today_reminder

    async def _send_daily_reminders(self):
        """Send daily reminders to all users"""
        try:
            logger.info("Sending daily reminders to all active users")
            await self.send_reminder_callback()
        except Exception as e:
            logger.error(f"Error sending daily reminders: {e}")
