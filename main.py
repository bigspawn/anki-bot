#!/usr/bin/env python3
"""
German Learning Telegram Bot
Main application entry point
"""

import logging
from src.config import get_settings
from src.bot_handler import BotHandler


def main():
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
    
    # Initialize and start bot (this will handle the async event loop)
    bot_handler = BotHandler(settings)
    bot_handler.run()


if __name__ == "__main__":
    main()