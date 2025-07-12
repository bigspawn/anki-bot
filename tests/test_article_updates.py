"""
Тесты для проверки обновления артиклей в базе данных
"""

import os
import tempfile

import pytest

from src.core.database.database_manager import DatabaseManager
from src.utils import format_word_display


class TestArticleUpdates:
    """Тесты для проверки правильности артиклей после обновлений"""

    @pytest.fixture
    def temp_db_manager(self):
        """Создать временную базу данных с тестовыми данными"""
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        temp_file.close()

        db_manager = DatabaseManager(temp_file.name)
        db_manager.init_database()

        # Создаем тестового пользователя
        user_data = {
            "telegram_id": 12345,
            "first_name": "Test",
            "last_name": "User",
            "username": "testuser",
        }
        user = db_manager.create_user(**user_data)

        # Добавляем тестовые слова с правильными артиклями
        test_words = [
            # Слова во множественном числе (без артикля)
            {"lemma": "Eltern", "part_of_speech": "noun", "article": None, "translation": "родители", "example": "Meine Eltern sind nett."},
            {"lemma": "Geschwister", "part_of_speech": "noun", "article": None, "translation": "братья и сестры", "example": "Meine Geschwister sind älter."},
            {"lemma": "Großeltern", "part_of_speech": "noun", "article": None, "translation": "дедушка и бабушка", "example": "Meine Großeltern besuchen uns."},
            {"lemma": "Pommes", "part_of_speech": "noun", "article": None, "translation": "фри", "example": "Ich esse gern Pommes."},

            # Слова с артиклями
            {"lemma": "Haus", "part_of_speech": "noun", "article": "das", "translation": "дом", "example": "Das Haus ist groß."},
            {"lemma": "Mann", "part_of_speech": "noun", "article": "der", "translation": "мужчина", "example": "Der Mann liest."},
            {"lemma": "Frau", "part_of_speech": "noun", "article": "die", "translation": "женщина", "example": "Die Frau arbeitet."},
            {"lemma": "Teppich", "part_of_speech": "noun", "article": "der", "translation": "ковёр", "example": "Der Teppich ist schön."},
        ]

        user_id = user["id"]
        added_count = db_manager.add_words_to_user(user_id, test_words)
        assert added_count == len(test_words)

        yield db_manager, user_id

        # Очистка
        os.unlink(temp_file.name)

    def test_plural_nouns_without_articles(self, temp_db_manager):
        """Тест что слова во множественном числе корректно отображаются без артиклей"""
        db_manager, user_id = temp_db_manager

        # Получаем слова во множественном числе
        plural_words = ["Eltern", "Geschwister", "Großeltern", "Pommes"]

        words = db_manager.get_words_by_user(user_id)

        for word in words:
            if word["lemma"] in plural_words:
                # Проверяем что артикль None
                assert word["article"] is None, f"{word['lemma']} должно иметь article = None"

                # Проверяем форматирование в utils.py
                formatted = format_word_display(word)
                assert "None" not in formatted, f"Форматирование не должно содержать 'None': {formatted}"
                assert f"🇩🇪 {word['lemma']}" in formatted, f"Должно содержать только имя слова: {formatted}"

                # Проверяем форматирование в session manager
                article = word.get('article')
                if article and article != 'None' and article.strip():
                    word_display = f"{article} {word['lemma']} - {word['part_of_speech']}"
                else:
                    word_display = f"{word['lemma']} - {word['part_of_speech']}"

                assert word_display == f"{word['lemma']} - noun", f"Session manager должен показывать без артикля: {word_display}"
                assert "None" not in word_display, f"Session manager не должен показывать 'None': {word_display}"

    def test_singular_nouns_with_articles(self, temp_db_manager):
        """Тест что слова в единственном числе корректно отображаются с артиклями"""
        db_manager, user_id = temp_db_manager

        # Ожидаемые артикли
        expected_articles = {
            "Haus": "das",
            "Mann": "der",
            "Frau": "die",
            "Teppich": "der"
        }

        words = db_manager.get_words_by_user(user_id)

        for word in words:
            if word["lemma"] in expected_articles:
                expected_article = expected_articles[word["lemma"]]

                # Проверяем что артикль правильный
                assert word["article"] == expected_article, f"{word['lemma']} должно иметь артикль {expected_article}, но имеет {word['article']}"

                # Проверяем форматирование в utils.py
                formatted = format_word_display(word)
                assert f"🇩🇪 {expected_article} {word['lemma']}" in formatted, f"Должно содержать артикль: {formatted}"
                assert "None" not in formatted, f"Не должно содержать 'None': {formatted}"

                # Проверяем форматирование в session manager
                article = word.get('article')
                if article and article != 'None' and article.strip():
                    word_display = f"{article} {word['lemma']} - {word['part_of_speech']}"
                else:
                    word_display = f"{word['lemma']} - {word['part_of_speech']}"

                expected_display = f"{expected_article} {word['lemma']} - noun"
                assert word_display == expected_display, f"Session manager должен показывать с артиклем: {word_display}"

    def test_database_consistency_after_updates(self, temp_db_manager):
        """Тест что база данных остается консистентной после обновлений"""
        db_manager, user_id = temp_db_manager

        # Получаем все существительные
        with db_manager.get_connection() as conn:
            cursor = conn.execute(
                "SELECT lemma, article FROM words WHERE part_of_speech = 'noun'"
            )
            nouns = cursor.fetchall()

        # Проверяем что нет артиклей 'None' (строка)
        for lemma, article in nouns:
            assert article != 'None', f"Слово {lemma} не должно иметь артикль 'None' (строка)"

            # Если артикль есть, то он должен быть правильным
            if article is not None:
                assert article in ["der", "die", "das"], f"Слово {lemma} имеет неправильный артикль: {article}"

    def test_word_display_formatting_consistency(self, temp_db_manager):
        """Тест что форматирование слов консистентно во всех местах"""
        db_manager, user_id = temp_db_manager

        words = db_manager.get_words_by_user(user_id)

        for word in words:
            # Тестируем format_word_display
            formatted_utils = format_word_display(word)

            # Тестируем session manager логику
            article = word.get('article')
            if article and article != 'None' and article.strip():
                session_display = f"{article} {word['lemma']} - {word['part_of_speech']}"
            else:
                session_display = f"{word['lemma']} - {word['part_of_speech']}"

            # Оба форматирования не должны содержать 'None'
            assert "None" not in formatted_utils, f"Utils formatting содержит 'None': {formatted_utils}"
            assert "None" not in session_display, f"Session manager formatting содержит 'None': {session_display}"

            # Если есть артикль, оба должны его показывать
            if word.get('article'):
                assert word['article'] in formatted_utils, f"Utils должен показывать артикль {word['article']}: {formatted_utils}"
                assert word['article'] in session_display, f"Session manager должен показывать артикль {word['article']}: {session_display}"

    def test_specific_corrected_words(self, temp_db_manager):
        """Тест конкретных слов, которые были исправлены"""
        db_manager, user_id = temp_db_manager

        # Слова, которые были исправлены (теперь должны быть None)
        corrected_words = {
            "Eltern": None,
            "Geschwister": None,
            "Großeltern": None,
            "Pommes": None
        }

        words = db_manager.get_words_by_user(user_id)

        for word in words:
            if word["lemma"] in corrected_words:
                expected_article = corrected_words[word["lemma"]]

                # Проверяем что артикль правильно исправлен
                assert word["article"] == expected_article, f"{word['lemma']} должно иметь артикль {expected_article}, но имеет {word['article']}"

                # Проверяем отображение
                formatted = format_word_display(word)
                assert "None" not in formatted, f"Исправленное слово {word['lemma']} не должно показывать 'None': {formatted}"

    def test_edge_cases_with_articles(self, temp_db_manager):
        """Тест граничных случаев с артиклями"""
        db_manager, user_id = temp_db_manager

        # Тестируем слова с различными значениями артиклей
        edge_cases = [
            {"lemma": "TestEmpty", "article": "", "expected_display": "TestEmpty - noun"},
            {"lemma": "TestNull", "article": None, "expected_display": "TestNull - noun"},
            {"lemma": "TestSpace", "article": "   ", "expected_display": "TestSpace - noun"},
        ]

        # Добавляем тестовые слова
        with db_manager.get_connection() as conn:
            for case in edge_cases:
                cursor = conn.execute(
                    "INSERT INTO words (lemma, part_of_speech, article, translation, example) VALUES (?, ?, ?, ?, ?)",
                    (case["lemma"], "noun", case["article"], "тест", "Test example.")
                )
                word_id = cursor.lastrowid

                # Добавляем к пользователю
                conn.execute(
                    "INSERT INTO learning_progress (user_id, word_id) VALUES (?, ?)",
                    (user_id, word_id)
                )
            conn.commit()

        # Проверяем форматирование
        words = db_manager.get_words_by_user(user_id)

        for word in words:
            for case in edge_cases:
                if word["lemma"] == case["lemma"]:
                    # Проверяем session manager логику
                    article = word.get('article')
                    if article and article != 'None' and article.strip():
                        word_display = f"{article} {word['lemma']} - {word['part_of_speech']}"
                    else:
                        word_display = f"{word['lemma']} - {word['part_of_speech']}"

                    assert word_display == case["expected_display"], f"Граничный случай {case['lemma']}: ожидалось {case['expected_display']}, получено {word_display}"
                    assert "None" not in word_display, f"Граничный случай не должен содержать 'None': {word_display}"

    def test_real_world_scenario_multiple_users(self, temp_db_manager):
        """Тест реального сценария с несколькими пользователями"""
        db_manager, first_user_id = temp_db_manager

        # Создаем второго пользователя
        user_data = {
            "telegram_id": 67890,
            "first_name": "Second",
            "last_name": "User",
            "username": "seconduser",
        }
        second_user = db_manager.create_user(**user_data)
        second_user_id = second_user["id"]

        # Добавляем те же слова второму пользователю
        test_words = [
            {"lemma": "Kinder", "part_of_speech": "noun", "article": None, "translation": "дети", "example": "Die Kinder spielen."},
            {"lemma": "Auto", "part_of_speech": "noun", "article": "das", "translation": "машина", "example": "Das Auto ist schnell."},
        ]

        added_count = db_manager.add_words_to_user(second_user_id, test_words)
        assert added_count == len(test_words)

        # Проверяем что оба пользователя видят правильные артикли
        for user_id in [first_user_id, second_user_id]:
            words = db_manager.get_words_by_user(user_id)

            for word in words:
                # Все слова должны иметь правильное форматирование
                formatted = format_word_display(word)
                assert "None" not in formatted, f"Пользователь {user_id}, слово {word['lemma']}: форматирование содержит 'None'"

                # Session manager форматирование
                article = word.get('article')
                if article and article != 'None' and article.strip():
                    word_display = f"{article} {word['lemma']} - {word['part_of_speech']}"
                else:
                    word_display = f"{word['lemma']} - {word['part_of_speech']}"

                assert "None" not in word_display, f"Пользователь {user_id}, слово {word['lemma']}: session display содержит 'None'"
