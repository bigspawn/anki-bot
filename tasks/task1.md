# Улучшенные требования к AI-агенту: Telegram-бот для изучения немецкого языка

## 🎯 Цель
Создать Telegram-бота, который помогает изучать немецкий язык через интеллектуальное добавление слов и систему интервального повторения.

## 🔧 Функциональные требования

### Основные команды:
- `/start` - приветствие и инструкции
- `/add <текст>` - добавить слова из текста (автоматически извлекает все немецкие слова)
- `/study` - начать сессию изучения
- `/study_new` - изучать только новые слова
- `/study_difficult` - повторить сложные слова
- `/stats` - статистика прогресса
- `/settings` - настройки (количество карточек в сессии, напоминания)
- `/help` - справка по командам

### Обработка слов:
- **Входные данные:** 
  - Любой текст на немецком языке
  - Автоматическое извлечение всех немецких слов из текста
  - Исключение служебных слов (артикли, предлоги, союзы)
  - Обработка множественных слов за один запрос
- **Выходные данные:** 
  - Лемма (начальная форма)
  - Часть речи (существительное, глагол, прилагательное, и т.д.)
  - Артикль (der/die/das для существительных)
  - Перевод на русский
  - Пример использования в предложении
  - Дополнительные формы (множественное число, спряжение)

### Система изучения:
- Карточки в стиле Anki с интервальным повторением
- Кнопки оценки: **Снова** (< 1 мин), **Трудно** (< 6 мин), **Хорошо** (< 10 мин), **Легко** (4 дня)
- Алгоритм SuperMemo 2:
  - **Снова**: интервал сбрасывается, повтор в текущей сессии
  - **Трудно**: интервал × 1.2, easiness_factor -= 0.15
  - **Хорошо**: интервал × easiness_factor
  - **Легко**: интервал × easiness_factor × 1.3
- Отслеживание прогресса по каждому слову
- Ежедневные напоминания о готовых к повторению словах

## 🧱 Технический стек

| Компонент | Технология | Версия |
|-----------|------------|--------|
| Язык | Python | 3.11+ |
| Бот | python-telegram-bot | 21.x |
| База данных | SQLite | 3.x |
| AI обработка | OpenAI API | gpt-4 |
| Менеджер окружения | uv | latest |
| Логирование | logging | built-in |
| Контейнеризация | Docker | 24.x+ |
| Оркестрация | Docker Compose | 2.x+ |

## 🏗️ Архитектура

### Модули:
1. **bot_handler.py** - Telegram интерфейс
2. **word_processor.py** - обработка слов через OpenAI
3. **text_parser.py** - извлечение слов из текста
4. **database.py** - работа с SQLite
5. **spaced_repetition.py** - алгоритм повторения
6. **config.py** - конфигурация
7. **utils.py** - вспомогательные функции

### Схема базы данных:
```sql
-- Пользователи
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    telegram_id INTEGER UNIQUE,
    username TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Слова
CREATE TABLE words (
    id INTEGER PRIMARY KEY,
    user_id INTEGER,
    word TEXT NOT NULL,
    lemma TEXT NOT NULL,
    part_of_speech TEXT,
    article TEXT,
    translation TEXT,
    example TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Прогресс изучения
CREATE TABLE learning_progress (
    id INTEGER PRIMARY KEY,
    user_id INTEGER,
    word_id INTEGER,
    easiness_factor REAL DEFAULT 2.5,
    interval_days INTEGER DEFAULT 1,
    repetitions INTEGER DEFAULT 0,
    next_review_date DATE,
    last_reviewed TIMESTAMP,
    review_count INTEGER DEFAULT 0,
    success_rate REAL DEFAULT 0.0,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (word_id) REFERENCES words(id)
);

-- История повторений
CREATE TABLE review_history (
    id INTEGER PRIMARY KEY,
    user_id INTEGER,
    word_id INTEGER,
    rating INTEGER, -- 1=Снова, 2=Трудно, 3=Хорошо, 4=Легко
    response_time INTEGER, -- время ответа в секундах
    reviewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (word_id) REFERENCES words(id)
);
```

## 📝 Пользовательские сценарии

### Сценарий 1: Добавление слов из текста
```
Пользователь: /add Ich gehe heute in die Schule und treffe meine Freunde. Wir lernen zusammen Mathematik.

Бот: 🔍 Обрабатываю текст... Найдено 6 новых слов:

     📝 gehen → ich gehe
     📖 Лемма: gehen
     🏷️ Часть речи: глагол
     🇷🇺 Перевод: идти, ехать
     📚 Пример: Ich gehe zur Schule.
     
     📝 Schule → die Schule
     📖 Лемма: Schule
     🏷️ Часть речи: существительное
     🇷🇺 Перевод: школа
     📚 Пример: Die Schule beginnt um 8 Uhr.
     
     📝 treffen → ich treffe
     📖 Лемма: treffen
     🏷️ Часть речи: глагол
     🇷🇺 Перевод: встречать
     📚 Пример: Ich treffe meine Freunde.
     
     ... (еще 3 слова)
     
     ✅ Добавлено 6 новых слов в словарь!
     ℹ️ Пропущено 8 служебных слов (ich, in, die, und, wir, etc.)
```

### Сценарий 2: Сессия изучения
```
Пользователь: /study
Бот: 🎯 Начинаем изучение! У вас 5 слов на повторение.
     
     Карточка 1/5:
     🇩🇪 das Haus
     
     [Кнопка: 👁️ Показать ответ]

Пользователь: [нажимает "Показать ответ"]
Бот: 🇩🇪 das Haus
     🇷🇺 дом
     📚 Пример: Das Haus ist sehr schön.
     
     Как хорошо вы знаете это слово?
     [Кнопки: 🔴 Снова | 🟡 Трудно | 🟢 Хорошо | 🔵 Легко]

Пользователь: [нажимает "Хорошо"]
Бот: ✅ Следующее повторение через 3 дня
     
     Карточка 2/5:
     🇩🇪 lernen
     
     [Кнопка: 👁️ Показать ответ]
```

## 🛡️ Обработка ошибок

### Сценарии ошибок:
- Неизвестное слово → запрос уточнения
- Сбой OpenAI API → повторная попытка + fallback
- Неправильный формат ввода → инструкция
- Превышение лимитов → уведомление

### Validation:
- Проверка длины слова (1-50 символов)
- Проверка на немецкие символы
- Санитизация входных данных

## 🔒 Безопасность

### Ограничения:
- Максимум 50 слов за один запрос /add
- Максимум 100 слов в день на пользователя
- Максимум 200 запросов к OpenAI в день
- Timeout для API запросов: 60 секунд (увеличен для обработки текста)

### Конфиденциальность:
- Шифрование API ключей
- Отсутствие логирования личных данных
- Возможность удалить все данные пользователя

## 📊 Мониторинг

### Метрики:
- Количество активных пользователей
- Использование OpenAI API
- Ошибки и время отклика
- Статистика изучения

### Логирование:
- Уровни: INFO, WARNING, ERROR
- Ротация логов: ежедневно
- Мониторинг критических ошибок

## 🧪 Тестирование

### Unit тесты:
- **bot_handler.py** - тестирование обработчиков команд
- **word_processor.py** - тестирование логики обработки слов
- **text_parser.py** - тестирование извлечения слов из текста
- **database.py** - тестирование операций с базой данных
- **spaced_repetition.py** - тестирование алгоритма повторения
- **utils.py** - тестирование вспомогательных функций

### Покрытие:
- Минимум 80% покрытия кода unit тестами
- Тестирование edge cases (пустой ввод, некорректные данные)
- Мок-объекты для OpenAI API и Telegram Bot API

### Инструменты:
- **pytest** - фреймворк для тестирования
- **pytest-cov** - измерение покрытия кода
- **unittest.mock** - создание мок-объектов

### Запуск тестов в Docker:
```bash
# Запуск тестов в контейнере
docker-compose exec german-bot uv run pytest tests/ -v --cov=src

# Или создание отдельного сервиса для тестов
docker-compose -f docker-compose.test.yml up --build
```

## 🚀 Развертывание

### Docker конфигурация:

**Dockerfile:**
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Установка uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Копирование файлов зависимостей
COPY pyproject.toml .
COPY uv.lock .

# Установка зависимостей
RUN uv sync --frozen

# Копирование исходного кода
COPY src/ src/
COPY main.py .

# Создание директорий для данных
RUN mkdir -p data logs

# Запуск приложения
CMD ["uv", "run", "python", "main.py"]
```

**docker-compose.yml:**
```yaml
version: '3.8'

services:
  german-bot:
    build:
      context: .
      dockerfile: docker/Dockerfile
    container_name: german-bot
    restart: unless-stopped
    environment:
      - TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - DATABASE_URL=sqlite:///data/bot.db
      - LOG_LEVEL=${LOG_LEVEL:-INFO}
      - POLLING_INTERVAL=${POLLING_INTERVAL:-1.0}
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
    env_file:
      - .env
    healthcheck:
      test: ["CMD", "python", "-c", "import sqlite3; sqlite3.connect('/app/data/bot.db').execute('SELECT 1')"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s
```

### Команды запуска:
```bash
# Копирование примера окружения
cp .env.example .env
# Заполнить .env файл своими токенами

# Сборка и запуск
docker-compose up --build -d

# Просмотр логов
docker-compose logs -f german-bot

# Остановка
docker-compose down

# Пересборка при изменениях
docker-compose up --build --force-recreate

# Подключение к контейнеру для отладки
docker-compose exec german-bot bash
```

### Требования к окружению хоста:
- Docker Engine 24.x+
- Docker Compose 2.x+
- 1GB RAM минимум
- 5GB свободного места для образов

## 📈 Будущие улучшения

### Фаза 2:
- Поддержка аудио произношения
- Грамматические упражнения
- Экспорт в Anki
- Статистика по временным зонам

### Фаза 3:
- Групповые испытания
- Интеграция с другими сервисами
- Мобильное приложение
- Поддержка других языков

## 🎯 Критерии успеха

### Технические:
- Время отклика < 3 сек
- Доступность > 99%
- Точность переводов > 95%

### Пользовательские:
- Retention rate > 30% через месяц
- Средняя сессия > 5 минут
- Положительные отзывы > 4.5/5