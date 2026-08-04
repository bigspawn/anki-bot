# German Learning Bot Makefile

.PHONY: help install run test test-cov lint format clean init-db docker-build docker-run docker-stop all export-words import-words backfill-levels seed-words deploy

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
	@echo "  backfill-levels - Fill CEFR levels for old words"
	@echo "  seed-words  - Seed curated groups (verbs, route phrases, drills)"
	@echo "  deploy      - Deploy to production NAS (TAG=version, default latest)"
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

# Backfill CEFR levels for words added before the level field existed
# Usage: make backfill-levels [DB_PATH=data/bot.db] [DRY_RUN=1]
backfill-levels:
	@DB_PATH=$${DB_PATH:-data/bot.db}; \
	FLAGS=$${DRY_RUN:+--dry-run}; \
	uv run python scripts/backfill_word_levels.py "$$DB_PATH" seed/word_levels.json $$FLAGS

# Seed curated word groups (reflexive verbs, verbs with prepositions,
# route phrases, cloze and error-correction drills)
# Usage: make seed-words TELEGRAM_ID=739529 [DB_PATH=data/bot.db] [DRY_RUN=1]
seed-words:
	@DB_PATH=$${DB_PATH:-data/bot.db}; \
	FLAGS=$${DRY_RUN:+--dry-run}; \
	if [ -z "$$TELEGRAM_ID" ]; then echo "TELEGRAM_ID is required"; exit 1; fi; \
	uv run python scripts/seed_words.py "$$DB_PATH" "$$TELEGRAM_ID" \
		seed/reflexive_verbs.json seed/preposition_verbs.json \
		seed/route_phrases.json seed/cloze_route.json seed/error_fix_route.json \
		seed/reflexive_case.json seed/dativ_verbs.json seed/dat_akk_verbs.json \
		seed/cloze_verb_case.json seed/pronoun_case.json seed/article_case.json \
		seed/cloze_paradigm.json seed/wo_wohin.json seed/verschmelzung.json \
		seed/wortstellung.json seed/adjektive.json seed/verbformen.json \
		seed/zeitangaben.json seed/cloze_zatyk.json seed/demonstrativ.json \
		seed/cloze_demonstrativ.json seed/cloze_pronomen.json $$FLAGS; \
	uv run python scripts/backfill_verb_case.py "$$DB_PATH" seed/*.json $$FLAGS

# Deploy to production (NAS) over SSH + docker compose, no extra tooling needed
# Usage: make deploy [TAG=v1.0.0] [HOST=other-host]
deploy:
	@HOST=$${HOST:-bgspwn-home-nas.tailba405.ts.net}; \
	TAG=$${TAG:-latest}; \
	DEPLOY_DIR=/volume1/docker/anki-bot; \
	DOCKER=/usr/local/bin/docker; \
	echo "Deploying anki-bot:$$TAG to $$HOST..."; \
	ssh "$$HOST" "cd $$DEPLOY_DIR && \
		IMAGE_TAG=$$TAG $$DOCKER compose -f docker-compose.prod.yml pull && \
		IMAGE_TAG=$$TAG $$DOCKER compose -f docker-compose.prod.yml up -d && \
		echo '=== Status ===' && \
		$$DOCKER compose -f docker-compose.prod.yml ps && \
		echo '=== Recent logs ===' && \
		$$DOCKER compose -f docker-compose.prod.yml logs --tail=15 german-bot"
