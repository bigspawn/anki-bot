# German Learning Telegram Bot

A Telegram bot for learning German language through intelligent word addition and spaced repetition system.

## 🎯 Features

- **Smart Word Addition**: Extract German words from text with automatic analysis
- **Spaced Repetition**: SuperMemo 2 algorithm for optimal learning
- **OpenAI Integration**: Automatic word processing with translations and examples (GPT-4/O1 models)
- **Progress Tracking**: Detailed learning statistics and progress monitoring
- **User-Friendly Interface**: Intuitive Telegram bot commands
- **Multi-User Support**: Isolated user sessions with concurrent study support
- **Rate Limiting**: Built-in protection against API abuse and system overload
- **User Authorization**: Configurable access control with allowed users list
- **Docker Support**: Full containerization for easy deployment

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- [UV package manager](https://docs.astral.sh/uv/)
- Telegram Bot Token (from [@BotFather](https://t.me/botfather))
- OpenAI API Key

### Installation

```bash
# Install UV
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone and setup
git clone <repository-url>
cd anki-bot
uv sync --dev

# Setup environment
cp .env.example .env
# Edit .env with your tokens

# Initialize database
uv run python -c "from src.database import init_db; init_db()"

# Start bot (or use Makefile)
uv run python main.py
# OR
make run
```

## 🤖 Bot Commands

- `/start` - Welcome and instructions
- `/add <text>` - Add German words from text
- `/study` - Start spaced repetition session
- `/study_new` - Study only new words
- `/study_difficult` - Review difficult words
- `/stats` - Show learning statistics
- `/settings` - Configure session settings
- `/help` - Command help

## 📖 Usage Examples

### Adding Words

```
/add Ich gehe heute in die Schule und treffe meine Freunde.
```

The bot will:
1. Extract German words from the text
2. Analyze each word with OpenAI (lemma, part of speech, article)
3. Generate translations and example sentences
4. Add words to your personal vocabulary

### Study Session

```
/study
```

Interactive flashcard session with:
- Word presentation (German side)
- Show answer button
- Rating system: ❌ Again | ➖ Hard | ➕ Good | ✅ Easy
- Automatic interval calculation using SuperMemo 2

### Automatic Text Processing

Simply send any German text to the bot:

```
Das Wetter ist heute sehr schön und warm.
```

The bot automatically extracts and processes words for learning.

## 🏗️ Architecture

### Core Components

- **`database.py`** - SQLite database management
- **`word_processor.py`** - OpenAI API integration for word analysis
- **`text_parser.py`** - German text parsing and word extraction
- **`spaced_repetition.py`** - SuperMemo 2 algorithm implementation
- **`bot_handler.py`** - Telegram bot interface
- **`utils.py`** - Utility functions and helpers

### Database Schema

```sql
-- Users management
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    telegram_id INTEGER UNIQUE,
    username TEXT,
    created_at TIMESTAMP
);

-- Word storage
CREATE TABLE words (
    id INTEGER PRIMARY KEY,
    user_id INTEGER,
    word TEXT,
    lemma TEXT,
    part_of_speech TEXT,
    article TEXT,
    translation TEXT,
    example TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Learning progress tracking
CREATE TABLE learning_progress (
    id INTEGER PRIMARY KEY,
    user_id INTEGER,
    word_id INTEGER,
    easiness_factor REAL DEFAULT 2.5,
    interval_days INTEGER DEFAULT 1,
    repetitions INTEGER DEFAULT 0,
    next_review_date DATE,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (word_id) REFERENCES words(id)
);
```

## 🧪 Development

### Makefile Commands

```bash
# Show all available commands
make help

# Install dependencies
make install

# Run the bot
make run

# Run tests
make test

# Run tests with coverage
make test-cov

# Lint code
make lint

# Format code
make format

# Complete development workflow (format + lint + test)
make dev
```

### Running Tests

```bash
# All tests
make test
# OR manually:
uv run pytest tests/ -v

# Specific test suite
uv run pytest tests/test_database.py -v
uv run pytest tests/test_spaced_repetition.py -v
uv run pytest tests/test_word_processor.py -v

# Integration tests
uv run pytest tests/test_integration.py -v

# With coverage
make test-cov
```

### Code Quality

```bash
# Formatting
uv run black src/ tests/
uv run isort src/ tests/

# Linting
uv run flake8 src/ tests/
uv run mypy src/

# Pre-commit hooks
uv run pre-commit install
uv run pre-commit run --all-files
```

### Development with Mock Data

For development without OpenAI API calls:

```python
from src.word_processor import get_word_processor

# Use mock processor (no API calls)
processor = get_word_processor(use_mock=True)
```

## 🐳 Docker Deployment

### Docker Compose (Recommended)

```bash
# Setup environment
cp .env.example .env
# Edit .env with your tokens

# Deploy
docker-compose up --build -d

# View logs
docker-compose logs -f german-bot

# Stop
docker-compose down
```

### Manual Docker

```bash
# Build
docker build -t german-bot -f docker/Dockerfile .

# Run
docker run -d --name german-bot \
  --env-file .env \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  german-bot
```

## ⚙️ Configuration

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `TELEGRAM_BOT_TOKEN` | Telegram bot token | - | ✅ |
| `OPENAI_API_KEY` | OpenAI API key | - | ✅ |
| `DATABASE_URL` | Database path | `sqlite:///data/bot.db` | ❌ |
| `LOG_LEVEL` | Logging level | `INFO` | ❌ |
| `MAX_WORDS_PER_REQUEST` | Max words per /add | `50` | ❌ |
| `MAX_WORDS_PER_DAY` | Daily word limit | `100` | ❌ |
| `MAX_OPENAI_REQUESTS_PER_DAY` | Daily OpenAI API limit | `200` | ❌ |
| `ALLOWED_USERS` | Comma-separated user IDs | `""` (all blocked) | ❌ |
| `POLLING_INTERVAL` | Bot polling interval | `1.0` | ❌ |

### OpenAI Settings

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_MODEL` | Model to use | `gpt-4` |
| `OPENAI_MAX_TOKENS` | Max completion tokens | `1000` |
| `OPENAI_TEMPERATURE` | Model temperature | `1.0` |

**Note**: GPT-4 and O1 models require `OPENAI_TEMPERATURE=1.0`. Use `max_completion_tokens` instead of deprecated `max_tokens`.

### User Authorization

Control access to your bot with the `ALLOWED_USERS` environment variable:

```bash
# Allow specific users only (comma-separated Telegram user IDs)
ALLOWED_USERS="321,123,456"

# Allow single user
ALLOWED_USERS="321"

# Block all users (default behavior)
ALLOWED_USERS=""
```

**Security Features:**
- Empty or unset `ALLOWED_USERS` blocks all access
- Unauthorized users receive polite denial message
- Access attempts are logged for monitoring
- User IDs can be found in Telegram logs when users interact with bot

## 📊 Spaced Repetition System

Uses SuperMemo 2 algorithm with four difficulty ratings:

- **❌ Again** (< 1 min): Reset interval, review in current session
- **➖ Hard** (< 6 min): Interval × 1.2, decrease easiness factor
- **➕ Good** (< 10 min): Interval × easiness factor
- **✅ Easy** (4 days): Interval × easiness factor × 1.3

### Learning Algorithm

1. **New words**: Start with 1-day interval
2. **Successful reviews**: Increase interval based on easiness factor
3. **Failed reviews**: Reset interval and decrease easiness
4. **Graduation**: Words become "learned" after successful repetitions

## 🔒 Security & Limits

- Maximum 50 words per `/add` command
- Maximum 100 words per day per user
- Maximum 200 OpenAI API requests per day
- 60-second timeout for API requests
- Encrypted API keys storage

## 📈 Monitoring

### Logging

```bash
# View logs
tail -f logs/bot.log

# Search for errors
grep ERROR logs/bot.log

# Monitor API usage
grep "OpenAI" logs/bot.log
```

### Health Checks

```bash
# Test database
uv run python -c "from src.database import init_db; init_db(); print('DB OK')"

# Test OpenAI connection
uv run python -c "
import asyncio
from src.word_processor import WordProcessor
async def test():
    processor = WordProcessor()
    result = await processor.test_connection()
    print(f'OpenAI: {result}')
asyncio.run(test())
"
```

## 🛠️ Troubleshooting

### Common Issues

**Bot not responding**
- Verify `TELEGRAM_BOT_TOKEN` is correct
- Check if bot is already running elsewhere
- Review logs for errors

**OpenAI errors**
- Confirm `OPENAI_API_KEY` is valid
- Check OpenAI account has credits
- Verify model availability

**Database errors**
- Ensure `data/` directory is writable
- Re-initialize database if corrupted
- Check file permissions

### Getting Help

1. Check logs for specific error messages
2. Review [setup documentation](docs/SETUP.md)
3. Test individual components
4. Create GitHub issue with logs and configuration

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Run tests (`uv run pytest tests/ -v`)
4. Commit changes (`git commit -m 'Add amazing feature'`)
5. Push to branch (`git push origin feature/amazing-feature`)
6. Open Pull Request

## 🎯 Roadmap

### Phase 2 Features
- Audio pronunciation support
- Grammar exercises
- Anki deck export
- Statistics by time zones

### Phase 3 Features
- Group challenges
- Integration with other services
- Mobile application
- Multi-language support

---

**Made with ❤️ for German language learners**