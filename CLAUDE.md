# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Telegram bot for learning German language through intelligent word addition and spaced repetition system. The bot helps users extract German words from text and study them using an Anki-style flashcard system with the SuperMemo 2 algorithm.

## Development Commands

### Core Commands
```bash
# Install dependencies (uses UV package manager)
make install
uv sync --dev

# Run the bot
make run                    # Uses .env file
make run ENV_FILE=.env.prod # Use custom env file
uv run python main.py       # Direct execution

# Testing
make test                   # Run all tests
make test-cov              # Run tests with coverage report
uv run pytest tests/ -v    # Direct pytest execution
uv run pytest tests/test_specific.py -v  # Single test file

# Code Quality
make format                 # Format code with Ruff
make lint                   # Lint with Ruff and MyPy
make security              # Security checks with Bandit and Safety
make dev                   # Complete dev workflow (format + lint + security + test)

# Database Operations
make init-db               # Initialize database
uv run python -c "from src.database import init_db; init_db()"

# Data Management
make export-words DB_PATH=data/bot.db OUTPUT_PATH=data/words.json
make import-words JSON_PATH=data/words.json DB_PATH=data/bot_new.db

# Docker
make docker-build          # Build Docker image
make docker-run           # Run with docker-compose
make docker-stop          # Stop docker containers

# Deployment
make deploy HOST=ip USER=user TAG=v1.0.0  # Deploy to server using spot
```

### Environment Setup
Required environment variables in `.env` file:
- `TELEGRAM_BOT_TOKEN` - From @BotFather
- `OPENAI_API_KEY` - OpenAI API access
- `DATABASE_URL` - SQLite database path (optional, defaults to `sqlite:///data/bot.db`)
- `ALLOWED_USERS` - Comma-separated Telegram user IDs for access control

## Architecture

### Core Application Structure
- **main.py** - Synchronous entry point that configures logging and starts async bot
- **bot_handler.py** - Main Telegram bot handler using modular architecture with async/await
- **config.py** - Pydantic-based configuration management with environment variable validation

### Legacy Core Modules
- **word_processor.py** - OpenAI API integration for word analysis (lemmatization, translation, examples)
- **text_parser.py** - German word extraction using regex patterns and spaCy NLP
- **database.py** - Legacy SQLite operations (deprecated, use `core.database` instead)
- **spaced_repetition.py** - SuperMemo 2 algorithm implementation with easiness factors
- **utils.py** - Utility functions including retry logic, rate limiting, and formatting helpers

### Modern Modular Architecture (src/core/)

#### Database Layer (`core/database/`)
- **database_manager.py** - Unified database manager coordinating all repositories
- **connection.py** - Database connection management with Python 3.13 compatibility
- **models.py** - Pydantic models for type-safe database operations
- **repositories/** - Repository pattern implementation:
  - **user_repository.py** - User management and statistics
  - **word_repository.py** - Word storage and retrieval operations  
  - **progress_repository.py** - Learning progress and review history tracking

#### Handler Layer (`core/handlers/`)
- **command_handlers.py** - Bot command processing logic (start, add, study, stats)
- **message_handlers.py** - Text message processing and routing

#### State Management (`core/session/`, `core/state/`)
- **session_manager.py** - User session state tracking for multi-step interactions
- **user_state_manager.py** - Persistent user state tracking across command flows

#### Concurrency Control (`core/locks/`)
- **user_lock_manager.py** - Per-user operation locking to prevent race conditions

### Database Schema
SQLite database with four main tables:
- `users` - User management with Telegram ID mapping, usernames, creation timestamps
- `words` - German words with lemma, part of speech, article, translation, and examples
- `learning_progress` - Spaced repetition tracking with intervals, easiness factors, repetition counts
- `review_history` - Historical review data for analytics and progress tracking

### Technology Stack
- **Python 3.11+** with UV package manager for dependency management
- **python-telegram-bot 21.x** - Telegram Bot API with async/await patterns
- **OpenAI API** - Chat completions with JSON mode for structured word processing
- **SQLite** - Local database with repository pattern for data access
- **Pydantic 2.x** - Configuration management and data validation
- **spaCy** - German NLP processing with `de_core_news_sm` model
- **pytest** - Testing framework with async support and coverage reporting
- **Ruff** - Fast Python linter and formatter
- **MyPy** - Type checking (currently configured permissively)

### Event Loop Management
- **Synchronous Entry**: `main.py` provides synchronous entry point for deployment
- **Async Operations**: All bot operations use async/await patterns
- **Graceful Shutdown**: Bot handles shutdown signals and cleanup properly

## Memories

### Database Best Practices
- Never delete sqlite database file
- Always for tests use testing database
- Use core.database modules for new features
- Maintain backwards compatibility during migration
- Export data before major database changes

### Git Practices
- Git tag versions must be always in semver like v0.0.1