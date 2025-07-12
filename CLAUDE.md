# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Telegram bot for learning German language through intelligent word addition and spaced repetition system. The bot helps users extract German words from text and study them using an Anki-style flashcard system with the SuperMemo 2 algorithm.

## Architecture

### Core Modules
- **bot_handler.py** - Telegram bot interface and command handlers with async event loop management
- **word_processor.py** - Word processing via OpenAI API (lemmatization, translation, examples)
- **text_parser.py** - German word extraction from text input using regex patterns
- **database.py** - SQLite database operations for users, words, and learning progress
- **spaced_repetition.py** - SuperMemo 2 algorithm implementation with easiness factors
- **config.py** - Pydantic-based configuration management with environment variables
- **utils.py** - Utility functions including retry logic, rate limiting, and formatting

### Database Schema
The application uses SQLite with four main tables:
- `users` - User management with Telegram ID mapping
- `words` - German words with lemma, part of speech, article, translation, and examples
- `learning_progress` - Spaced repetition tracking with intervals and easiness factors
- `review_history` - Historical review data for analytics

### Key Integration Points
- **OpenAI API**: Uses chat completions with JSON mode for structured word processing
- **Telegram Bot API**: python-telegram-bot 21.x with async/await patterns
- **Event Loop Management**: Synchronous main.py entry point with async bot operations
- **Error Handling**: Comprehensive retry logic and graceful degradation

## Development Commands

### Essential Commands (use these frequently)
```bash
# Install dependencies and sync environment
uv sync --dev

# Run the bot (requires .env file)
make run

# Run tests with proper environment variables
make test

# Run tests with coverage
make test-cov

# Run specific test file
TELEGRAM_BOT_TOKEN=test_token OPENAI_API_KEY=test_key uv run pytest tests/test_word_processor.py -v

# Run single test
TELEGRAM_BOT_TOKEN=test_token OPENAI_API_KEY=test_key uv run pytest tests/test_spaced_repetition.py::TestSRSSystem::test_calculate_next_interval -v

# Lint and format code
make lint
make format

# Complete development workflow
make dev  # format, lint, test
```

### Docker Development
```bash
# Build and run with Docker Compose
docker-compose up --build -d

# View logs
docker-compose logs -f german-bot

# Run tests in container
docker-compose exec german-bot uv run pytest tests/ -v --cov=src

# Stop services
docker-compose down
```

## Technology Stack

- **Language**: Python 3.11+
- **Bot Framework**: python-telegram-bot 21.x (async/await patterns)
- **Database**: SQLite 3.x with custom date/timestamp adapters for Python 3.13
- **AI Processing**: OpenAI API (GPT-4/O1 models) with structured JSON responses
- **Package Manager**: uv (modern Python package manager)
- **Containerization**: Docker + Docker Compose
- **Testing**: pytest with asyncio support and mock objects for external APIs

## Key Features

### Bot Commands
- `/start` - Welcome and instructions
- `/add <text>` - Extract and add German words from text
- `/study` - Start spaced repetition session
- `/study_new` - Study only new words
- `/study_difficult` - Review difficult words
- `/stats` - Show learning statistics
- `/settings` - Configure session settings
- `/help` - Command help

### Spaced Repetition Algorithm (SuperMemo 2)
Uses four difficulty ratings with specific intervals:
- **Again** (< 1 min): Reset interval, review in current session
- **Hard** (< 6 min): Interval × 1.2, decrease easiness factor
- **Good** (< 10 min): Interval × easiness factor
- **Easy** (4 days): Interval × easiness factor × 1.3

### OpenAI API Integration
- **Model Compatibility**: Supports GPT-4 and O1 models (temperature=1.0 only)
- **Parameter Changes**: Uses `max_completion_tokens` instead of deprecated `max_tokens`
- **Structured Output**: JSON mode for consistent word processing responses
- **Rate Limiting**: Built-in request limiting and retry logic

### User Authorization System
- **Access Control**: Configure allowed users with `ALLOWED_USERS` environment variable
- **Flexible Format**: Support for comma-separated user IDs (e.g., "321,123")
- **Security First**: Empty or unset `ALLOWED_USERS` means no users are allowed
- **Unauthorized Access**: Users not in the list receive a polite denial message
- **Logging**: Unauthorized access attempts are logged for monitoring

**Usage Examples:**
```bash
# Allow specific users only
ALLOWED_USERS="321,123"

# Allow single user
ALLOWED_USERS="321"

# Block all users (default if unset)
ALLOWED_USERS=""
```

## Critical Testing Information

### Test Environment Setup
Tests require specific environment variables to avoid external API calls:
```bash
TELEGRAM_BOT_TOKEN=test_token OPENAI_API_KEY=test_key
```

### Test Architecture
- **Mock Objects**: All external APIs (OpenAI, Telegram) use mocks in tests
- **Async Testing**: pytest-asyncio for async function testing
- **Integration Tests**: End-to-end workflow testing with mocked dependencies
- **Coverage Target**: Minimum 80% code coverage

### Common Test Patterns
- Word processing tests expect lowercase output (e.g., "haus" not "Haus")
- Database tests use in-memory SQLite with temporary tables
- Mock word processor returns fallback data for consistent testing
- Integration tests verify complete user workflows

## Security & Limits

- Maximum 50 words per `/add` command
- Maximum 100 words per day per user
- Maximum 200 OpenAI API requests per day
- 60-second timeout for API requests
- Environment-based configuration (no hardcoded secrets)
- User authorization system with allowed users list (optional)

## Environment Variables

### Required Variables
- `TELEGRAM_BOT_TOKEN` - Telegram bot token from @BotFather
- `OPENAI_API_KEY` - OpenAI API key with sufficient credits

### Optional Variables
- `DATABASE_URL` - SQLite database path (default: `sqlite:///data/bot.db`)
- `LOG_LEVEL` - Logging level (default: `INFO`)
- `POLLING_INTERVAL` - Bot polling interval (default: `1.0`)
- `OPENAI_MODEL` - OpenAI model (default: `gpt-4`, supports O1 models)
- `OPENAI_TEMPERATURE` - Model temperature (default: `1.0`, required for GPT-4/O1)
- `OPENAI_MAX_TOKENS` - Max completion tokens (default: `1000`)
- `ALLOWED_USERS` - Comma-separated list of allowed Telegram user IDs (default: empty, disallows all users)

## Development Rules

### Testing After Bug Fixes (Mandatory)
**CRITICAL RULE**: After fixing any bug or error, you MUST create and run a test to verify the fix works correctly.

**Process:**
1. **Identify the Problem**: Understand the exact error or issue
2. **Implement the Fix**: Make the necessary code changes 
3. **Create a Test**: Write a test that reproduces the original problem and verifies the fix
4. **Run the Test**: Execute the test to confirm it passes
5. **Clean Up**: Remove temporary test files if they were created

**Test Types by Problem Category:**
- **Missing Methods/Attributes**: Test that the method exists and works as expected
- **Database Schema Issues**: Test data insertion/retrieval with new schema
- **Button/UI Issues**: Test user interaction flows end-to-end
- **API Integration**: Test external service calls and error handling
- **Configuration Problems**: Test with various config scenarios

**Examples:**
```bash
# After fixing missing database method
pytest tests/test_database.py::test_get_word_by_lemma -v

# After fixing button data issues
pytest tests/test_utils.py::TestInlineKeyboard -v

# After database migration
python test_migration.py && rm test_migration.py
```

**Benefits:**
- Prevents regression of the same issue
- Validates the fix actually works
- Documents expected behavior
- Builds confidence in the codebase

## Common Issues and Solutions

### OpenAI API Compatibility
- **Temperature Error**: GPT-4 and O1 models only support temperature=1.0
- **Token Parameter**: Use `max_completion_tokens` instead of `max_tokens`
- **Model Support**: O1 models like "o4-mini-2025-04-16" are supported

### Event Loop Management
- **Main Entry**: Use synchronous main.py with async bot operations
- **Bot Startup**: BotHandler manages its own event loop for python-telegram-bot 21.x
- **Timeout Configuration**: Move timeout settings to application builder, not run_polling()

### Database Compatibility
- **Python 3.13**: Custom date/timestamp adapters prevent deprecation warnings
- **SQLite Threading**: Use connection per thread for async operations

## Development Guidelines

### Testing Guidelines
- **After any changes run tests**

## Memories

### Database Best Practices
- Never delete sqlite database file
- Always for tests use testing database