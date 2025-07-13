# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Telegram bot for learning German language through intelligent word addition and spaced repetition system. The bot helps users extract German words from text and study them using an Anki-style flashcard system with the SuperMemo 2 algorithm.

## Architecture

### Core Modules
- **bot_handler.py** - Telegram bot interface and command handlers with async event loop management
- **word_processor.py** - Word processing via OpenAI API (lemmatization, translation, examples)
- **text_parser.py** - German word extraction from text input using regex patterns
- **database.py** - Legacy SQLite database operations (deprecated, use core.database instead)
- **spaced_repetition.py** - SuperMemo 2 algorithm implementation with easiness factors
- **config.py** - Pydantic-based configuration management with environment variables
- **utils.py** - Utility functions including retry logic, rate limiting, and formatting

#### New Modular Architecture (src/core/)
- **core/database/** - Modern database layer with repositories and models
  - **database_manager.py** - Unified database manager coordinating all repositories
  - **connection.py** - Database connection management with Python 3.13 compatibility
  - **models.py** - Pydantic models for type-safe database operations
  - **repositories/** - Repository pattern for data access layer
    - **user_repository.py** - User management and statistics
    - **word_repository.py** - Word storage and retrieval operations
    - **progress_repository.py** - Learning progress and review history
- **core/handlers/** - Modular command and message handlers
  - **command_handlers.py** - Bot command processing logic
  - **message_handlers.py** - Text message processing and routing
- **core/session/** - Session management for multi-step interactions
  - **session_manager.py** - User session state tracking
- **core/state/** - User state management for command flows
  - **user_state_manager.py** - Persistent user state tracking
- **core/locks/** - Concurrency control for multi-user operations
  - **user_lock_manager.py** - Per-user operation locking

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

# Run with custom environment file
make run ENV_FILE=.env.production

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

# Security checks
make security

# Complete development workflow
make dev  # format, lint, security, test

# Quick pre-commit check
make check  # format, lint, test-cov

# Data export/import
make export-words  # Export words to JSON
make import-words  # Import words from JSON
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
- **NLP**: spaCy 3.7+ with German language model (de_core_news_sm)
- **Package Manager**: uv (modern Python package manager)
- **Containerization**: Docker + Docker Compose with multi-architecture support
- **Testing**: pytest with asyncio support and mock objects for external APIs
- **CI/CD**: GitHub Actions with automated testing, building, and releases
- **Code Quality**: Ruff (linting/formatting), MyPy (type checking), Bandit (security), Safety (dependency scanning)

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
- **Modular Testing**: Separate test files for each core module and feature

### New Test Categories
- **Repository Tests**: Database operations with in-memory SQLite
- **Manager Tests**: Business logic coordination between repositories
- **Handler Tests**: Command and message processing workflows
- **Session Tests**: Multi-step user interaction flows
- **Concurrency Tests**: Multi-user isolation and locking mechanisms
- **Migration Tests**: Database schema and data migration verification

### Common Test Patterns
- Word processing tests expect lowercase output (e.g., "haus" not "Haus")
- Database tests use in-memory SQLite with temporary tables
- Mock word processor returns fallback data for consistent testing
- Integration tests verify complete user workflows
- Repository tests verify data integrity and business rules
- Handler tests use mock telegram contexts and responses

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
- **Repository/Manager Issues**: Test business logic and data flow
- **Concurrency Issues**: Test multi-user scenarios and locking
- **Session/State Issues**: Test user workflow state management

**Examples:**
```bash
# After fixing missing database method
pytest tests/test_database.py::test_get_word_by_lemma -v

# After fixing repository issues
pytest tests/test_database.py::TestWordRepository -v

# After fixing button data issues
pytest tests/test_utils.py::TestInlineKeyboard -v

# After fixing session management
pytest tests/test_study_session_flow.py -v

# After database migration
python test_migration.py && rm test_migration.py
```

**Benefits:**
- Prevents regression of the same issue
- Validates the fix actually works
- Documents expected behavior
- Builds confidence in the codebase
- Ensures modular architecture integrity

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
- **Use the modular test structure** for new features
- **Test both legacy and new database layers** during migration
- **Always test concurrency scenarios** for multi-user features

### Architecture Guidelines
- **Prefer core/ modules** for new functionality
- **Use repository pattern** for data access
- **Implement proper session management** for multi-step workflows
- **Add appropriate locking** for concurrent operations
- **Follow type safety** with Pydantic models

### CI/CD Guidelines
- **All commits trigger** automated testing and security checks
- **Multi-architecture Docker builds** for production deployment
- **Automated releases** with changelog generation
- **Coverage reporting** to Codecov for quality tracking

## Continuous Integration

### GitHub Actions Workflows
- **CI/CD Pipeline** (.github/workflows/ci-cd.yml)
  - Automated testing with Python 3.11
  - Linting with Ruff and type checking with MyPy
  - Multi-architecture Docker builds (linux/amd64, linux/arm64)
  - Automated releases with changelog generation
  - Coverage reporting to Codecov
- **Security Workflow** (.github/workflows/security.yml)
  - Dependency vulnerability scanning
  - Security linting with Bandit
  - Code quality monitoring

### Release Process
- **Automated Releases**: Tag with `v*` pattern triggers full release workflow
- **Multi-Architecture**: Docker images built for AMD64 and ARM64
- **Changelog Generation**: Automatic changelog from git commits
- **Asset Deployment**: docker-compose.yml and .env.example included in releases

## Data Management

### Export/Import System
- **Export Words**: `make export-words` - Export user data to JSON format
- **Import Words**: `make import-words` - Import data from JSON to new database
- **Database Migration**: Tools for moving between database versions
- **Backup Strategy**: JSON export for data portability and backup

### Scripts
- **scripts/export_words.py** - Database to JSON export utility
- **scripts/import_words.py** - JSON to database import utility
- **Configurable paths** via environment variables (DB_PATH, OUTPUT_PATH, JSON_PATH)

## Memories

### Database Best Practices
- Never delete sqlite database file
- Always for tests use testing database
- Use core.database modules for new features
- Maintain backwards compatibility during migration
- Export data before major database changes