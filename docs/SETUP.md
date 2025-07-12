# German Learning Bot Setup Guide

## Prerequisites

- Python 3.11 or higher
- [UV package manager](https://docs.astral.sh/uv/)
- Telegram Bot Token (from [@BotFather](https://t.me/botfather))
- OpenAI API Key
- Docker (optional, for containerized deployment)

## Quick Start

### 1. Install UV Package Manager

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or using Homebrew
brew install uv

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### 2. Clone and Setup Project

```bash
git clone <repository-url>
cd anki-bot

# Install dependencies
uv sync --dev

# Copy environment template
cp .env.example .env
```

### 3. Configure Environment Variables

Edit `.env` file with your credentials:

```bash
# Required: Telegram Bot Token from @BotFather
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here

# Required: OpenAI API Key
OPENAI_API_KEY=your_openai_api_key_here

# Optional: Database location (defaults to data/bot.db)
DATABASE_URL=sqlite:///data/bot.db

# Optional: Application settings
LOG_LEVEL=INFO
DEBUG=false
MAX_WORDS_PER_REQUEST=50
MAX_WORDS_PER_DAY=100
```

### 4. Initialize Database

```bash
uv run python -c "from src.database import init_db; init_db()"
```

### 5. Start the Bot

```bash
# Development mode
uv run python main.py

# Or with specific environment
TELEGRAM_BOT_TOKEN=xxx OPENAI_API_KEY=xxx uv run python main.py
```

## Getting API Keys

### Telegram Bot Token

1. Message [@BotFather](https://t.me/botfather) on Telegram
2. Send `/newbot` command
3. Follow instructions to create your bot
4. Copy the provided token

Example bot creation:
```
/newbot
My German Learning Bot
my_german_bot

Done! Your bot token: 321:ABCdefGHIjklMNOpqrsTUVwxyz
```

### OpenAI API Key

1. Visit [OpenAI Platform](https://platform.openai.com/api-keys)
2. Sign up or log in to your account
3. Click "Create new secret key"
4. Copy the key (starts with `sk-`)

**Note**: You'll need credits in your OpenAI account. The bot uses GPT-4 by default.

## Docker Deployment

### Using Docker Compose (Recommended)

```bash
# Copy environment file
cp .env.example .env
# Edit .env with your tokens

# Build and start
docker-compose up --build -d

# View logs
docker-compose logs -f german-bot

# Stop
docker-compose down
```

### Manual Docker Build

```bash
# Build image
docker build -t german-bot -f docker/Dockerfile .

# Run container
docker run -d --name german-bot \
  --env-file .env \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  german-bot
```

## Development Setup

### Code Quality Tools

```bash
# Install pre-commit hooks
uv run pre-commit install

# Run code formatting
uv run black src/ tests/
uv run isort src/ tests/

# Run linting
uv run flake8 src/ tests/
uv run mypy src/
```

### Running Tests

```bash
# Run all tests
uv run pytest tests/ -v

# Run specific test file
uv run pytest tests/test_database.py -v

# Run with coverage
uv run pytest tests/ --cov=src --cov-report=html

# Run integration tests
uv run pytest tests/test_integration.py -v
```

### Testing with Mock Data

For development without OpenAI API calls:

```python
# In your code, use mock processor
from src.word_processor import get_word_processor

# Get mock processor (no API calls)
processor = get_word_processor(use_mock=True)
```

## Configuration Options

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `TELEGRAM_BOT_TOKEN` | Telegram bot token | - | Yes |
| `OPENAI_API_KEY` | OpenAI API key | - | Yes |
| `DATABASE_URL` | Database connection string | `sqlite:///data/bot.db` | No |
| `LOG_LEVEL` | Logging level (DEBUG/INFO/WARNING/ERROR) | `INFO` | No |
| `DEBUG` | Enable debug mode | `false` | No |
| `MAX_WORDS_PER_REQUEST` | Max words to process per /add command | `50` | No |
| `MAX_WORDS_PER_DAY` | Max words per user per day | `100` | No |
| `MAX_OPENAI_REQUESTS_PER_DAY` | Daily OpenAI API limit | `200` | No |
| `API_TIMEOUT` | API request timeout (seconds) | `60` | No |
| `DEFAULT_CARDS_PER_SESSION` | Cards per study session | `10` | No |

### OpenAI Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_MODEL` | GPT model to use | `gpt-4` |
| `OPENAI_MAX_TOKENS` | Max tokens per request | `1000` |
| `OPENAI_TEMPERATURE` | Response creativity (0.0-1.0) | `0.3` |

### Spaced Repetition Settings

| Variable | Description | Default |
|----------|-------------|---------|
| `DEFAULT_EASINESS_FACTOR` | Starting easiness | `2.5` |
| `MIN_EASINESS_FACTOR` | Minimum easiness | `1.3` |
| `MAX_EASINESS_FACTOR` | Maximum easiness | `3.0` |

## Troubleshooting

### Common Issues

**Bot not responding**
- Check if `TELEGRAM_BOT_TOKEN` is correct
- Verify bot is not already running elsewhere
- Check logs for error messages

**OpenAI errors**
- Verify `OPENAI_API_KEY` is valid
- Check OpenAI account has sufficient credits
- Ensure model (default: gpt-4) is available

**Database errors**
- Ensure `data/` directory exists and is writable
- Check if database file is corrupted
- Re-initialize with `init_db()`

**Permission errors**
- Ensure correct file permissions on data/ and logs/ directories
- For Docker: check volume mount permissions

### Debugging Commands

```bash
# Test database connection
uv run python -c "from src.database import init_db; init_db(); print('Database OK')"

# Test OpenAI connection (requires API key)
uv run python -c "
import asyncio
from src.word_processor import WordProcessor
async def test():
    processor = WordProcessor()
    result = await processor.test_connection()
    print(f'OpenAI connection: {result}')
asyncio.run(test())
"

# Test text parser
uv run python -c "
from src.text_parser import extract_german_words
words = extract_german_words('Das Haus ist schön.')
print(f'Extracted words: {words}')
"

# Check configuration
uv run python -c "
from src.config import get_settings
settings = get_settings()
print(f'Log level: {settings.log_level}')
print(f'Database: {settings.database_url}')
"
```

### Log Analysis

```bash
# View recent logs
tail -f logs/bot.log

# Search for errors
grep ERROR logs/bot.log

# View database operations
grep "Database" logs/bot.log
```

### Performance Monitoring

```bash
# Check database size
ls -lh data/bot.db

# Monitor API usage
grep "OpenAI" logs/bot.log | grep "request"

# Check memory usage (if running)
ps aux | grep python | grep main.py
```

## Production Deployment

### Security Considerations

1. **API Keys**: Store securely, never commit to version control
2. **Database**: Regular backups, secure file permissions
3. **Network**: Use HTTPS, consider firewall rules
4. **Updates**: Keep dependencies updated

### Backup Strategy

```bash
# Manual database backup
cp data/bot.db backups/bot_$(date +%Y%m%d_%H%M%S).db

# Automated backup script (add to cron)
#!/bin/bash
BACKUP_DIR="/path/to/backups"
DB_FILE="/path/to/data/bot.db"
DATE=$(date +%Y%m%d_%H%M%S)
cp "$DB_FILE" "$BACKUP_DIR/bot_$DATE.db"
find "$BACKUP_DIR" -name "bot_*.db" -mtime +7 -delete
```

### Health Monitoring

The bot includes health check endpoints when running in Docker:

```bash
# Check if bot is healthy
docker-compose exec german-bot python -c "import sqlite3; sqlite3.connect('data/bot.db').execute('SELECT 1')"
```

### Scaling Considerations

For high-traffic scenarios:
- Use PostgreSQL instead of SQLite
- Implement Redis for session storage
- Use multiple bot instances with load balancing
- Monitor OpenAI API rate limits

## Support

For issues and questions:
1. Check logs for error messages
2. Review this setup guide
3. Test individual components
4. Create GitHub issue with logs and configuration details

## License

MIT License - see LICENSE file for details.