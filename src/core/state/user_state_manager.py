"""
User state management for bot interactions
"""

import asyncio
import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class UserState(Enum):
    """Available user states"""
    IDLE = "idle"
    WAITING_FOR_TEXT_TO_ADD = "waiting_for_text_to_add"


class UserStateInfo:
    """Information about user state"""
    
    def __init__(self, state: UserState, timestamp: Optional[datetime] = None, data: Optional[Dict] = None):
        self.state = state
        self.timestamp = timestamp or datetime.now()
        self.data = data or {}


class UserStateManager:
    """Manages user states for bot interactions"""
    
    def __init__(self, state_timeout_minutes: int = 10):
        self.user_states: Dict[int, UserStateInfo] = {}
        self.state_timeout_minutes = state_timeout_minutes
        self._cleanup_task: Optional[asyncio.Task] = None
    
    async def start(self):
        """Start the state manager and cleanup task"""
        logger.info("Starting UserStateManager")
        self._cleanup_task = asyncio.create_task(self._periodic_cleanup())
    
    async def stop(self):
        """Stop the state manager and cleanup task"""
        logger.info("Stopping UserStateManager")
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
    
    def set_state(self, telegram_id: int, state: UserState, data: Optional[Dict] = None):
        """Set user state"""
        self.user_states[telegram_id] = UserStateInfo(state, data=data)
        logger.debug(f"Set state for user {telegram_id}: {state.value}")
    
    def get_state(self, telegram_id: int) -> UserState:
        """Get user state"""
        if telegram_id not in self.user_states:
            return UserState.IDLE
        
        state_info = self.user_states[telegram_id]
        
        # Check if state has expired
        if self._is_state_expired(state_info):
            self.clear_state(telegram_id)
            return UserState.IDLE
        
        return state_info.state
    
    def get_state_data(self, telegram_id: int) -> Dict:
        """Get user state data"""
        if telegram_id not in self.user_states:
            return {}
        
        state_info = self.user_states[telegram_id]
        
        if self._is_state_expired(state_info):
            self.clear_state(telegram_id)
            return {}
        
        return state_info.data
    
    def clear_state(self, telegram_id: int):
        """Clear user state"""
        if telegram_id in self.user_states:
            old_state = self.user_states[telegram_id].state
            del self.user_states[telegram_id]
            logger.debug(f"Cleared state for user {telegram_id} (was: {old_state.value})")
    
    def is_waiting_for_text(self, telegram_id: int) -> bool:
        """Check if user is waiting for text to add"""
        return self.get_state(telegram_id) == UserState.WAITING_FOR_TEXT_TO_ADD
    
    def _is_state_expired(self, state_info: UserStateInfo) -> bool:
        """Check if state has expired"""
        if state_info.state == UserState.IDLE:
            return False
            
        timeout = timedelta(minutes=self.state_timeout_minutes)
        return datetime.now() - state_info.timestamp > timeout
    
    async def _periodic_cleanup(self):
        """Periodically clean up expired states"""
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute
                
                expired_users = []
                for telegram_id, state_info in self.user_states.items():
                    if self._is_state_expired(state_info):
                        expired_users.append(telegram_id)
                
                for telegram_id in expired_users:
                    logger.info(f"Cleaning up expired state for user {telegram_id}")
                    self.clear_state(telegram_id)
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in state cleanup: {e}")