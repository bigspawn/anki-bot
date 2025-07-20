#!/usr/bin/env python3
"""
German Learning Telegram Bot
Main application entry point
"""

import asyncio
import logging
from src.config import get_settings
from src.bot_handler import BotHandler


async def main():
    """Main application entry point"""
    # Load configuration
    settings = get_settings()
    
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, settings.log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logger = logging.getLogger(__name__)
    logger.info("Starting German Learning Bot...")
    
    # Initialize bot handler
    bot_handler = BotHandler(settings)
    
    try:
        # Start bot
        await bot_handler.start()
        logger.info("Bot stopped gracefully")
    except KeyboardInterrupt:
        logger.info("Shutdown requested, stopping bot...")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())