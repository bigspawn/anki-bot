#!/usr/bin/env python3
"""
Tests that every study command is reachable: registered as a handler, listed
in the Telegram menu and documented in /help. A command missing from the menu
works when typed but stays invisible in the UI.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from telegram import Message, Update, User
from telegram.ext import ContextTypes

from src.bot_handler import BotHandler
from src.config import Settings
from src.core.database.database_manager import DatabaseManager
from src.core.handlers.command_handlers import CommandHandlers

NEW_COMMANDS = [
    "study_reflexive",
    "study_rektion",
    "study_route",
    "study_cloze",
    "study_topic",
    "stats_topics",
]

# /start is reachable from the menu but has no /help line: it is the entry
# point the help text is reached from.
COMMANDS_NOT_IN_HELP = {"start"}


@pytest.fixture
def bot_handler():
    settings = Settings(telegram_bot_token="test-token", openai_api_key="test-key")

    with (
        patch("src.bot_handler.get_db_manager", return_value=Mock()),
        patch("src.bot_handler.get_word_processor", return_value=AsyncMock()),
        patch("src.bot_handler.get_text_parser", return_value=MagicMock()),
        patch("src.bot_handler.get_srs_system", return_value=MagicMock()),
    ):
        return BotHandler(settings=settings)


@pytest.mark.parametrize("command", NEW_COMMANDS)
def test_command_is_registered_as_a_handler(bot_handler, command):
    bot_handler.application = MagicMock()
    bot_handler._add_handlers()

    registered = {
        call.args[0].commands
        for call in bot_handler.application.add_handler.call_args_list
        if hasattr(call.args[0], "commands")
    }

    assert any(command in commands for commands in registered)


@pytest.mark.parametrize("command", NEW_COMMANDS)
@pytest.mark.asyncio
async def test_command_is_in_the_telegram_menu(bot_handler, command):
    application = MagicMock()
    application.bot.set_my_commands = AsyncMock()

    await bot_handler.setup_bot_menu(application)

    menu = {c.command for c in application.bot.set_my_commands.call_args[0][0]}

    assert command in menu


@pytest.mark.parametrize("command", NEW_COMMANDS)
@pytest.mark.asyncio
async def test_command_is_documented_in_help(command):
    handlers = CommandHandlers(
        db_manager=Mock(spec=DatabaseManager),
        word_processor=Mock(),
        text_parser=Mock(),
        srs_system=Mock(),
        safe_reply_callback=AsyncMock(),
        process_text_callback=AsyncMock(),
        start_study_session_callback=AsyncMock(),
        state_manager=Mock(),
        session_manager=Mock(),
    )
    handlers._safe_reply = AsyncMock()

    update = Mock(spec=Update)
    update.effective_user = Mock(spec=User)
    update.effective_user.id = 1
    update.message = Mock(spec=Message)

    await handlers.help_command(update, Mock(spec=ContextTypes.DEFAULT_TYPE))

    help_text = handlers._safe_reply.call_args[0][1]

    assert f"/{command}" in help_text


def registered_commands(bot_handler) -> set[str]:
    """Every command name wired up as a CommandHandler"""
    bot_handler.application = MagicMock()
    bot_handler._add_handlers()

    return {
        command
        for call in bot_handler.application.add_handler.call_args_list
        if hasattr(call.args[0], "commands")
        for command in call.args[0].commands
    }


async def menu_commands(bot_handler) -> set[str]:
    """Every command name offered in the Telegram menu button"""
    application = MagicMock()
    application.bot.set_my_commands = AsyncMock()

    await bot_handler.setup_bot_menu(application)

    return {c.command for c in application.bot.set_my_commands.call_args[0][0]}


@pytest.mark.asyncio
async def test_every_registered_command_is_in_the_telegram_menu(bot_handler):
    missing = registered_commands(bot_handler) - await menu_commands(bot_handler)

    assert not missing, (
        f"commands work but are invisible in the menu: {sorted(missing)}"
    )


@pytest.mark.asyncio
async def test_the_menu_offers_no_command_that_does_not_exist(bot_handler):
    dangling = await menu_commands(bot_handler) - registered_commands(bot_handler)

    assert not dangling, f"menu offers unhandled commands: {sorted(dangling)}"


@pytest.mark.asyncio
async def test_the_menu_fits_the_telegram_limit(bot_handler):
    assert len(await menu_commands(bot_handler)) <= 100


@pytest.mark.asyncio
async def test_every_registered_command_is_documented_in_help(bot_handler):
    handlers = CommandHandlers(
        db_manager=Mock(spec=DatabaseManager),
        word_processor=Mock(),
        text_parser=Mock(),
        srs_system=Mock(),
        safe_reply_callback=AsyncMock(),
        process_text_callback=AsyncMock(),
        start_study_session_callback=AsyncMock(),
        state_manager=Mock(),
        session_manager=Mock(),
    )
    handlers._safe_reply = AsyncMock()

    update = Mock(spec=Update)
    update.effective_user = Mock(spec=User)
    update.effective_user.id = 1
    update.message = Mock(spec=Message)

    await handlers.help_command(update, Mock(spec=ContextTypes.DEFAULT_TYPE))
    help_text = handlers._safe_reply.call_args[0][1]

    undocumented = {
        command
        for command in registered_commands(bot_handler) - COMMANDS_NOT_IN_HELP
        if f"/{command}" not in help_text
    }

    assert not undocumented, f"missing from /help: {sorted(undocumented)}"


@pytest.mark.asyncio
async def test_startup_pushes_the_menu_to_telegram(bot_handler):
    """The menu must be sent on every start.

    PTB only runs post_init hooks from run_polling/run_webhook, and this bot
    drives initialize/start/start_polling by hand: registering the menu as a
    post_init hook would leave Telegram showing a long-stale command list.
    """
    application = MagicMock()
    application.initialize = AsyncMock()
    application.start = AsyncMock()
    application.bot.set_my_commands = AsyncMock()
    application.updater.start_polling = AsyncMock()
    application.updater.stop = AsyncMock()
    application.stop = AsyncMock()
    application.shutdown = AsyncMock()

    builder = MagicMock()
    builder.token.return_value = builder
    builder.read_timeout.return_value = builder
    builder.write_timeout.return_value = builder
    builder.connect_timeout.return_value = builder
    builder.pool_timeout.return_value = builder
    # Accepted but never fired by PTB on this lifecycle: registering the menu
    # here instead must fail the assertion below.
    builder.post_init.return_value = builder
    builder.build.return_value = application

    # The bot idles in a sleep loop until interrupted; that is its stop signal
    with (
        patch("src.bot_handler.Application.builder", return_value=builder),
        patch("asyncio.sleep", AsyncMock(side_effect=asyncio.CancelledError)),
    ):
        await bot_handler.start()

    application.bot.set_my_commands.assert_awaited_once()
    sent = {c.command for c in application.bot.set_my_commands.call_args[0][0]}
    assert "study_route" in sent
    assert "stats_topics" in sent
