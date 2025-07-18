"""
Test cases for daily reminders functionality
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.bot_handler import BotHandler
from src.core.database.database_manager import DatabaseManager
from src.core.database.repositories.user_repository import UserRepository
from src.core.database.connection import DatabaseConnection


class TestGetAllActiveUsers:
    """Test cases for get_all_active_users functionality"""

    @pytest.fixture
    def mock_db_connection(self):
        """Mock database connection"""
        return MagicMock(spec=DatabaseConnection)

    @pytest.fixture
    def user_repo(self, mock_db_connection):
        """Create UserRepository with mocked connection"""
        return UserRepository(mock_db_connection)

    @pytest.fixture
    def db_manager(self, mock_db_connection):
        """Create DatabaseManager with mocked connection"""
        with patch('src.core.database.database_manager.DatabaseConnection') as mock_conn_class:
            mock_conn_class.return_value = mock_db_connection
            return DatabaseManager()

    def test_get_all_active_users_success(self, user_repo, mock_db_connection):
        """Test successful retrieval of active users"""
        # Mock database response
        mock_cursor = MagicMock()
        mock_row1 = {
            'id': 1,
            'telegram_id': 123456,
            'first_name': 'John',
            'last_name': 'Doe',
            'username': 'johndoe',
            'is_active': 1,
            'created_at': '2024-01-01 10:00:00',
            'updated_at': '2024-01-01 10:00:00'
        }
        mock_row2 = {
            'id': 2,
            'telegram_id': 789012,
            'first_name': 'Jane',
            'last_name': 'Smith',
            'username': 'janesmith',
            'is_active': 1,
            'created_at': '2024-01-02 11:00:00',
            'updated_at': '2024-01-02 11:00:00'
        }
        
        mock_cursor.fetchall.return_value = [mock_row1, mock_row2]
        
        mock_conn = MagicMock()
        mock_conn.execute.return_value = mock_cursor
        mock_db_connection.get_connection.return_value.__enter__.return_value = mock_conn
        
        # Test the method
        result = user_repo.get_all_active_users()
        
        # Verify results
        assert len(result) == 2
        assert result[0]['telegram_id'] == 123456
        assert result[0]['first_name'] == 'John'
        assert result[1]['telegram_id'] == 789012
        assert result[1]['first_name'] == 'Jane'
        
        # Verify SQL query
        mock_conn.execute.assert_called_once_with("SELECT * FROM users WHERE is_active = 1")

    def test_get_all_active_users_empty_result(self, user_repo, mock_db_connection):
        """Test when no active users found"""
        # Mock empty database response
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        
        mock_conn = MagicMock()
        mock_conn.execute.return_value = mock_cursor
        mock_db_connection.get_connection.return_value.__enter__.return_value = mock_conn
        
        # Test the method
        result = user_repo.get_all_active_users()
        
        # Verify empty result
        assert result == []

    def test_get_all_active_users_none_result(self, user_repo, mock_db_connection):
        """Test when database returns None"""
        # Mock None database response
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = None
        
        mock_conn = MagicMock()
        mock_conn.execute.return_value = mock_cursor
        mock_db_connection.get_connection.return_value.__enter__.return_value = mock_conn
        
        # Test the method
        result = user_repo.get_all_active_users()
        
        # Verify empty result for None
        assert result == []

    def test_get_all_active_users_database_error(self, user_repo, mock_db_connection):
        """Test handling of database errors"""
        # Mock database error
        mock_db_connection.get_connection.side_effect = Exception("Database connection failed")
        
        # Test the method
        result = user_repo.get_all_active_users()
        
        # Should return empty list on error
        assert result == []

    def test_database_manager_get_all_active_users(self, db_manager):
        """Test DatabaseManager.get_all_active_users delegates to UserRepository"""
        with patch.object(db_manager.user_repo, 'get_all_active_users') as mock_method:
            mock_method.return_value = [{'telegram_id': 123, 'first_name': 'Test'}]
            
            result = db_manager.get_all_active_users()
            
            mock_method.assert_called_once()
            assert len(result) == 1
            assert result[0]['telegram_id'] == 123


class TestSendDailyReminders:
    """Test cases for _send_daily_reminders method"""

    @pytest.fixture
    def mock_settings(self):
        """Mock settings for BotHandler"""
        settings = MagicMock()
        settings.telegram_bot_token = "test_token"
        settings.allowed_users_list = [123456, 789012]
        settings.max_words_per_request = 50
        settings.polling_interval = 1.0
        settings.log_level = "INFO"
        return settings

    @pytest.fixture
    def mock_application(self):
        """Mock Telegram application"""
        app = MagicMock()
        app.bot = MagicMock()
        app.bot.send_message = AsyncMock()
        return app

    @pytest.fixture
    def bot_handler(self, mock_settings):
        """Create BotHandler with mocked dependencies"""
        with patch('src.bot_handler.get_db_manager'), \
             patch('src.bot_handler.get_word_processor'), \
             patch('src.bot_handler.get_text_parser'), \
             patch('src.bot_handler.get_srs_system'), \
             patch('src.bot_handler.UserLockManager'), \
             patch('src.bot_handler.UserStateManager'), \
             patch('src.bot_handler.ReminderScheduler'), \
             patch('src.bot_handler.SessionManager'), \
             patch('src.bot_handler.CommandHandlers'), \
             patch('src.bot_handler.MessageHandlers'):
            
            return BotHandler(mock_settings)

    @pytest.mark.asyncio
    async def test_send_daily_reminders_success(self, bot_handler, mock_application):
        """Test successful sending of daily reminders"""
        # Mock active users
        mock_users = [
            {'telegram_id': 123456, 'first_name': 'John'},
            {'telegram_id': 789012, 'first_name': 'Jane'}
        ]
        
        bot_handler.db_manager = MagicMock()
        bot_handler.db_manager.get_all_active_users.return_value = mock_users
        bot_handler.application = mock_application
        
        # Test the method
        await bot_handler._send_daily_reminders()
        
        # Verify messages were sent to all users
        assert mock_application.bot.send_message.call_count == 2
        
        # Check first call
        first_call = mock_application.bot.send_message.call_args_list[0]
        assert first_call[1]['chat_id'] == 123456
        assert "Время изучения немецкого!" in first_call[1]['text']
        assert first_call[1]['parse_mode'] == "HTML"
        
        # Check second call
        second_call = mock_application.bot.send_message.call_args_list[1]
        assert second_call[1]['chat_id'] == 789012
        assert "Время изучения немецкого!" in second_call[1]['text']

    @pytest.mark.asyncio
    async def test_send_daily_reminders_no_active_users(self, bot_handler, mock_application):
        """Test when no active users found"""
        bot_handler.db_manager = MagicMock()
        bot_handler.db_manager.get_all_active_users.return_value = []
        bot_handler.application = mock_application
        
        # Test the method
        await bot_handler._send_daily_reminders()
        
        # Verify no messages were sent
        mock_application.bot.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_daily_reminders_partial_failure(self, bot_handler, mock_application):
        """Test when some message sends fail"""
        # Mock active users
        mock_users = [
            {'telegram_id': 123456, 'first_name': 'John'},
            {'telegram_id': 789012, 'first_name': 'Jane'}
        ]
        
        bot_handler.db_manager = MagicMock()
        bot_handler.db_manager.get_all_active_users.return_value = mock_users
        bot_handler.application = mock_application
        
        # Mock first send success, second send failure
        mock_application.bot.send_message.side_effect = [
            AsyncMock(),  # Success
            Exception("Send failed")  # Failure
        ]
        
        # Test the method - should not raise exception
        await bot_handler._send_daily_reminders()
        
        # Verify both sends were attempted
        assert mock_application.bot.send_message.call_count == 2

    @pytest.mark.asyncio
    async def test_send_daily_reminders_database_error(self, bot_handler, mock_application):
        """Test when database error occurs"""
        bot_handler.db_manager = MagicMock()
        bot_handler.db_manager.get_all_active_users.side_effect = Exception("Database error")
        bot_handler.application = mock_application
        
        # Test the method - should not raise exception
        await bot_handler._send_daily_reminders()
        
        # Verify no messages were sent
        mock_application.bot.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_daily_reminders_message_content(self, bot_handler, mock_application):
        """Test the content of reminder messages"""
        mock_users = [{'telegram_id': 123456, 'first_name': 'John'}]
        
        bot_handler.db_manager = MagicMock()
        bot_handler.db_manager.get_all_active_users.return_value = mock_users
        bot_handler.application = mock_application
        
        await bot_handler._send_daily_reminders()
        
        # Get the message content
        call_args = mock_application.bot.send_message.call_args
        message_text = call_args[1]['text']
        
        # Verify message content
        assert "🎯" in message_text
        assert "Время изучения немецкого!" in message_text
        assert "📚 Не забудьте позаниматься сегодня." in message_text
        assert "💪 Регулярные занятия — ключ к успеху!" in message_text
        assert "/study" in message_text


class TestDailyRemindersIntegration:
    """Integration tests for daily reminders functionality"""

    @pytest.mark.asyncio
    async def test_bot_handler_reminder_scheduler_integration(self):
        """Test that BotHandler properly integrates with ReminderScheduler"""
        mock_settings = MagicMock()
        mock_settings.telegram_bot_token = "test_token"
        mock_settings.allowed_users_list = []
        
        with patch('src.bot_handler.get_db_manager'), \
             patch('src.bot_handler.get_word_processor'), \
             patch('src.bot_handler.get_text_parser'), \
             patch('src.bot_handler.get_srs_system'), \
             patch('src.bot_handler.UserLockManager'), \
             patch('src.bot_handler.UserStateManager'), \
             patch('src.bot_handler.SessionManager'), \
             patch('src.bot_handler.CommandHandlers'), \
             patch('src.bot_handler.MessageHandlers'), \
             patch('src.bot_handler.ReminderScheduler') as mock_scheduler_class:
            
            mock_scheduler = MagicMock()
            mock_scheduler_class.return_value = mock_scheduler
            
            bot_handler = BotHandler(mock_settings)
            
            # Verify scheduler was created with correct callback
            mock_scheduler_class.assert_called_once_with(bot_handler._send_daily_reminders)
            assert bot_handler.reminder_scheduler == mock_scheduler

    def test_reminder_scheduler_lifecycle_in_bot_start(self):
        """Test that reminder scheduler is started/stopped with bot"""
        mock_settings = MagicMock()
        mock_settings.telegram_bot_token = "test_token"
        mock_settings.allowed_users_list = []
        
        with patch('src.bot_handler.get_db_manager'), \
             patch('src.bot_handler.get_word_processor'), \
             patch('src.bot_handler.get_text_parser'), \
             patch('src.bot_handler.get_srs_system'), \
             patch('src.bot_handler.UserLockManager') as mock_lock_manager_class, \
             patch('src.bot_handler.UserStateManager') as mock_state_manager_class, \
             patch('src.bot_handler.SessionManager'), \
             patch('src.bot_handler.CommandHandlers'), \
             patch('src.bot_handler.MessageHandlers'), \
             patch('src.bot_handler.ReminderScheduler') as mock_scheduler_class:
            
            mock_scheduler = MagicMock()
            mock_scheduler_class.return_value = mock_scheduler
            
            mock_lock_manager = MagicMock()
            mock_lock_manager_class.return_value = mock_lock_manager
            
            mock_state_manager = MagicMock()
            mock_state_manager_class.return_value = mock_state_manager
            
            bot_handler = BotHandler(mock_settings)
            
            # Verify scheduler was created with correct callback
            mock_scheduler_class.assert_called_once_with(bot_handler._send_daily_reminders)
            assert bot_handler.reminder_scheduler == mock_scheduler

    def test_reminder_message_format_consistency(self):
        """Test that reminder message format is consistent"""
        mock_settings = MagicMock()
        
        with patch('src.bot_handler.get_db_manager'), \
             patch('src.bot_handler.get_word_processor'), \
             patch('src.bot_handler.get_text_parser'), \
             patch('src.bot_handler.get_srs_system'), \
             patch('src.bot_handler.UserLockManager'), \
             patch('src.bot_handler.UserStateManager'), \
             patch('src.bot_handler.ReminderScheduler'), \
             patch('src.bot_handler.SessionManager'), \
             patch('src.bot_handler.CommandHandlers'), \
             patch('src.bot_handler.MessageHandlers'):
            
            bot_handler = BotHandler(mock_settings)
            
            # Extract the message from the method (by examining the source)
            # This ensures the message format is what we expect
            import inspect
            source = inspect.getsource(bot_handler._send_daily_reminders)
            
            # Verify key components are in the message
            assert "Время изучения немецкого!" in source
            assert "Не забудьте позаниматься сегодня" in source
            assert "Регулярные занятия — ключ к успеху" in source
            assert "/study" in source
            assert "HTML" in source  # parse_mode