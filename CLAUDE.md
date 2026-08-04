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
make deploy TAG=v1.0.0  # SSH + docker compose pull/up on the production NAS (default TAG=latest)
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

## Adding a New Bot Feature (Checklist)

When adding a new study command / filter / rubric (anything like `/study_*`),
always touch the full standard flow, not just the DB query — it's easy to
ship a command that works in isolation but is unreachable or undocumented:

1. **Repository method** (`src/core/database/repositories/*.py`) — the raw
   SQL query.
2. **`DatabaseManager` wrapper** (`src/core/database/database_manager.py`) —
   thin pass-through, matches the pattern of existing `get_*` methods.
3. **`CommandHandlers` method** (`src/core/handlers/command_handlers.py`) —
   prefer flat, argument-free commands (`/study_nouns`, `/study_a1`, ...)
   over one command taking a variant as `context.args` — the user explicitly
   rejected the arg-based design ("не нравится что команды надо еще както
   выбирать хочу плоские команды"), so a family of variants gets a thin
   command method per variant delegating to a shared private helper (see
   `_study_pos` / `_study_level` and their `study_nouns_command` /
   `study_a1_command` etc. wrappers). Each guards on
   `update.effective_user`, looks up `db_user`, replies with
   `ReplyKeyboardRemove()` on every branch, and handles the empty-results
   case with its own message.
4. **Register the command** in `src/bot_handler.py`:
   - `CommandHandler(...)` in `_add_handlers` (wrapped in
     `self.require_authorization(...)`)
   - `BotCommand(...)` entry in `setup_bot_menu` — see the rule below.
5. **Update `/help` text** in `command_handlers.py` (`help_command`) — same
   omission risk as the menu entry.
6. **Schema changes**, if any, go in
   `src/core/database/connection.py::_run_migrations`, guarded by
   `PRAGMA table_info(...)` checks (see the `level`/`confidence` column
   pattern) — never a manual `ALTER TABLE` run by hand against the live DB.
7. **OpenAI prompt changes**, if the new feature needs a new field from the
   model, go in both `_get_system_prompt` and `_get_batch_system_prompt` in
   `src/word_processor.py` — the two prompts drift apart easily if only one
   is updated.

### Nouns always carry their plural

Every noun card stores `additional_forms.plural` and shows it on the reveal
(`🔢 Plural: die Häuser`); the front asks for the article *and* the plural
whenever one is stored. Both prompts already request it.

The model does not always spell the key the same way, so
`normalize_additional_forms` rewrites `Plural`/`Plurals` to `plural` on the
way in — without that, 242 nouns held a plural that nothing could read.
Read it back with `stored_plural()`, never with a bare dict lookup.

A noun with genuinely no plural (proper noun, plural-only) stores
`"plural": null` — that is a decided answer, not a gap, and stops the
backfill asking again. Repair and generation live in
`scripts/backfill_noun_plural.py` (`make backfill-plural OPENAI=1`).

### EVERY command belongs in the Telegram quick menu

`setup_bot_menu` in `src/bot_handler.py` must list **every** command
registered in `_add_handlers` — no exceptions, no "internal" commands. The
quick-menu button is how the bot is actually navigated; a command missing
from that list still works when typed but is invisible, so in practice it
does not exist.

This is enforced, not left to review — `tests/test_command_registration.py`
fails the build on any drift:

- `test_every_registered_command_is_in_the_telegram_menu` — a registered
  command missing from the menu
- `test_the_menu_offers_no_command_that_does_not_exist` — a menu entry with
  no handler behind it
- `test_every_registered_command_is_documented_in_help` — a command missing
  from `/help` (only `/start` is exempt, via `COMMANDS_NOT_IN_HELP`)
- `test_startup_pushes_the_menu_to_telegram` — the menu is actually sent on
  startup

Add the `BotCommand(...)` entry in the same edit as the `CommandHandler`, and
these stay green on their own.

**Do not move `setup_bot_menu` back to a `post_init` hook.** PTB only fires
post_init from `run_polling`/`run_webhook`, and `start()` here drives
`initialize`/`start`/`start_polling` by hand, so the hook never ran and
Telegram silently kept a months-stale command list. It is called explicitly
after `initialize()` for that reason.

### Never build SQL by string formatting

Queries are assembled from module-level literal constants only (see the
`SQL_*` constants in `word_repository.py`), never from f-strings, `%`,
`.format()` or concatenation involving runtime values. `make security`
(bandit B608) is clean and must stay clean — do **not** silence it with
`# nosec` or `# noqa: S608`. The three patterns that replaced the old
f-strings:

- **variable-length `IN` lists** → pass a JSON array and match against
  `(SELECT value FROM json_each(?))`
- **`ORDER BY RANDOM()` vs a fixed order** → bind a flag:
  `ORDER BY CASE WHEN ? = 1 THEN RANDOM() ELSE 0 END, <tiebreaker>`
- **date windows** → bind the modifier: `datetime('now', ?)` with
  `f"-{int(days)} days"` as the parameter

For a partial `UPDATE`, use `COALESCE(?, column)` per field rather than
growing a `SET` clause. Covered by `tests/test_sql_hardening.py`.

### Test coverage checklist per command handler

Each new `*_command` needs its own `tests/test_*_feature.py` covering, at
minimum (mirror `tests/test_study_pos_feature.py` /
`tests/test_study_level_feature.py`):
- happy path (valid input → correct `db_manager` call + `_start_study_session`
  called)
- missing/invalid argument (if the command takes one) → helpful message, no
  DB call
- `db_user` not found → "❌ Пользователь не найден" message
- empty result set from the DB → its own "nothing to study" message
- `update.effective_user is None` → early return, no DB calls at all

### Before calling any feature done

- `make lint` (ruff + mypy) must be clean.
- `make security` (bandit) must be clean — see the SQL rule above.
- Run the FULL suite (`uv run pytest tests/ -q`), not just the new test
  file. **The bar is zero failures and zero errors.** There is no accepted
  baseline of "expected" failures: the suite used to show 11 failed / 25
  errors on a clean checkout because it depended on `TELEGRAM_BOT_TOKEN` and
  `OPENAI_API_KEY` being exported (CI injected them, nothing else did).
  `tests/conftest.py` now pins those, so a red test is a real regression.

### The suite is hermetic — keep it that way

`tests/conftest.py` pins the credentials and, importantly, `DATABASE_URL`.
Without that pin `get_db_manager()` with no explicit path resolves to
`data/bot.db` — the developer's own vocabulary — and tests write to it.

- Never read configuration from the ambient environment in a test; if a test
  needs a setting, pass it explicitly (`Settings(...)`) or extend conftest.
- Always construct `DatabaseManager` with a temp path in tests that touch the
  database directly (see the `db_manager` fixtures).
- `tests/test_suite_isolation.py` fails if the resolved database ever lands
  inside the repo, so this cannot regress silently.

## Memories

### Database Best Practices
- Never delete sqlite database file
- Always for tests use testing database
- Use core.database modules for new features
- Maintain backwards compatibility during migration
- Export data before major database changes

### Git Practices
- Git tag versions must be always in semver like v0.0.1