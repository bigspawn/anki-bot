# German Learning Bot Makefile

.PHONY: help install run test test-cov lint format clean init-db docker-build docker-run docker-stop all export-words import-words deploy

# Default target
help:
	@echo "Available commands:"
	@echo "  install     - Install dependencies"
	@echo "  run         - Run the bot (ENV_FILE=.env.custom to use custom env file)"
	@echo "  test        - Run tests"
	@echo "  test-cov    - Run tests with coverage"
	@echo "  lint        - Run linting"
	@echo "  format      - Format code"
	@echo "  init-db     - Initialize database"
	@echo "  clean       - Clean temporary files"
	@echo "  docker-build - Build Docker image"
	@echo "  docker-run  - Run with Docker"
	@echo "  docker-stop - Stop Docker container"
	@echo "  export-words - Export words data to JSON"
	@echo "  import-words - Import words data from JSON"
	@echo "  deploy      - Deploy to server (HOST=ip USER=user TAG=version)"
	@echo "  all         - Install, test, lint, format"

# Install dependencies
install:
	uv sync --dev

# Run the bot (requires .env file with TELEGRAM_BOT_TOKEN and OPENAI_API_KEY)
# Usage: make run [ENV_FILE=.env.custom]
run:
	@ENV_FILE=${ENV_FILE}; \
	if [ -z "$$ENV_FILE" ]; then \
		ENV_FILE=.env; \
	fi; \
	if [ ! -f "$$ENV_FILE" ]; then \
		echo "Error: $$ENV_FILE file not found. Please create $$ENV_FILE file with TELEGRAM_BOT_TOKEN and OPENAI_API_KEY"; \
		echo "You can copy .env.example to $$ENV_FILE and edit it with your tokens"; \
		exit 1; \
	fi; \
	echo "Using environment file: $$ENV_FILE"; \
	export $$(grep -v '^#' "$$ENV_FILE" | xargs) && uv run python main.py

# Run tests
test:
	TELEGRAM_BOT_TOKEN=test_token OPENAI_API_KEY=test_key uv run pytest tests/ -v

# Run tests with coverage
test-cov:
	TELEGRAM_BOT_TOKEN=test_token OPENAI_API_KEY=test_key uv run pytest tests/ -v --cov=src --cov-report=html --cov-report=term

# Run linting
lint:
	uv run ruff check src/ tests/
	uv run mypy src/ --ignore-missing-imports

# Format code
format:
	uv run ruff format src/ tests/
	uv run ruff check --fix src/ tests/

# Security checks
security:
	uv run bandit -r src/
	uv run safety check

# Initialize database
init-db:
	uv run python -c "from src.database import init_db; init_db()"

# Clean temporary files
clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf .pytest_cache/
	rm -rf htmlcov/
	rm -rf .coverage

# Docker commands
docker-build:
	docker build -t german-bot -f docker/Dockerfile .

docker-run:
	docker-compose up --build -d

docker-stop:
	docker-compose down

# Run everything
all: install test lint format

# Development workflow
dev: format lint security test

# Quick check before commit
check: format lint test-cov

# Install spacy
install-spacy:
	uv add spacy
	uv add pip
	uv run spacy download de_core_news_sm

# Export words data to JSON
export-words:
	@DB_PATH=$${DB_PATH:-data/bot.db}; \
	OUTPUT_PATH=$${OUTPUT_PATH:-data/bot_words.json}; \
	echo "Exporting from $$DB_PATH to $$OUTPUT_PATH"; \
	python scripts/export_words.py "$$DB_PATH" "$$OUTPUT_PATH"

# Import words data from JSON
import-words:
	@JSON_PATH=$${JSON_PATH:-data/bot_words.json}; \
	DB_PATH=$${DB_PATH:-data/bot_new.db}; \
	echo "Importing from $$JSON_PATH to $$DB_PATH"; \
	python scripts/import_words.py "$$JSON_PATH" "$$DB_PATH"

# Deploy to production server
# Usage: make deploy HOST=host USER=root [TAG=v1.0.0]
deploy:
	@if [ -z "$$HOST" ]; then \
		echo "Error: HOST parameter is required"; \
		echo "Usage: make deploy HOST=host USER=root [TAG=v1.0.0]"; \
		exit 1; \
	fi; \
	if [ -z "$$USER" ]; then \
		echo "Error: USER parameter is required"; \
		echo "Usage: make deploy HOST=host USER=root [TAG=v1.0.0]"; \
		exit 1; \
	fi; \
	TAG=$${TAG:-latest}; \
	echo "Deploying $$TAG to $$HOST as user $$USER..."; \
	spot -t $$HOST -u $$USER -e IMAGE_TAG:$$TAG
