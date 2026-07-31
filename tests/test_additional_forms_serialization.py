#!/usr/bin/env python3
"""
Tests for additional_forms coming back from OpenAI as a real JSON object.

Regression: "Training" and "mitkommen" were never added — the model returned
additional_forms as a dict, sqlite3 cannot bind a dict, and the failure was
swallowed word by word ("Error binding parameter 6: type 'dict' is not
supported"), so the word appeared in no counter at all.
"""

import json
import os
import tempfile

import pytest

from src.core.database.database_manager import DatabaseManager
from src.utils import format_verb_forms
from src.word_processor import WordProcessor, normalize_additional_forms


class TestNormalizeAdditionalForms:
    def test_dict_becomes_a_json_string(self):
        value = normalize_additional_forms({"plural": "Trainings"})

        assert isinstance(value, str)
        assert json.loads(value) == {"plural": "Trainings"}

    def test_umlauts_are_kept_readable(self):
        value = normalize_additional_forms({"plural": "Häuser"})

        assert "Häuser" in value

    def test_string_is_passed_through(self):
        assert normalize_additional_forms('{"plural": "Häuser"}') == (
            '{"plural": "Häuser"}'
        )

    def test_empty_values_become_none(self):
        assert normalize_additional_forms(None) is None
        assert normalize_additional_forms("") is None

    def test_unsupported_types_become_none(self):
        assert normalize_additional_forms(42) is None
        assert normalize_additional_forms(object()) is None

    def test_list_is_serialized(self):
        assert normalize_additional_forms(["a", "b"]) == '["a", "b"]'


class TestOpenAIResponseParsing:
    @pytest.fixture
    def processor(self):
        return WordProcessor.__new__(WordProcessor)

    def test_single_word_response_with_dict_forms(self, processor):
        word = processor._parse_openai_response(
            "training",
            {
                "lemma": "Training",
                "part_of_speech": "noun",
                "article": "das",
                "translation": "тренировка",
                "example": "Das Training war hart.",
                "additional_forms": {"plural": "Trainings"},
                "confidence": 0.95,
                "level": "A2",
            },
        )

        assert word is not None
        assert isinstance(word.additional_forms, str)
        assert json.loads(word.additional_forms) == {"plural": "Trainings"}

    def test_verb_forms_still_render_on_the_card(self, processor):
        word = processor._parse_openai_response(
            "mitkommen",
            {
                "lemma": "mitkommen",
                "part_of_speech": "verb",
                "article": None,
                "translation": "идти вместе",
                "example": "Willst du mitkommen?",
                "additional_forms": {
                    "praeteritum": "kam mit",
                    "partizip_ii": "mitgekommen",
                },
                "confidence": 0.95,
                "level": "A2",
            },
        )

        assert word is not None
        assert format_verb_forms(
            {
                "part_of_speech": word.part_of_speech,
                "additional_forms": word.additional_forms,
            }
        ) == "🔄 kam mit – mitgekommen\n\n"


class TestDatabaseAcceptsTheseWords:
    @pytest.fixture
    def db_manager(self):
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        temp_file.close()

        manager = DatabaseManager(temp_file.name)
        manager.init_database()
        manager.create_user(telegram_id=888, first_name="Test")

        yield manager

        os.unlink(temp_file.name)

    def test_word_with_serialized_forms_is_added(self, db_manager):
        result = db_manager.add_words_with_details(
            888,
            [
                {
                    "lemma": "Training",
                    "part_of_speech": "noun",
                    "article": "das",
                    "translation": "тренировка",
                    "example": "Das Training war hart.",
                    "additional_forms": normalize_additional_forms(
                        {"plural": "Trainings"}
                    ),
                }
            ],
        )

        assert result["added"] == ["Training"]
        assert result["invalid"] == []

    def test_unbindable_word_is_reported_as_invalid_not_lost(self, db_manager):
        """A raw dict still fails to bind, but must not vanish from the counters"""
        result = db_manager.add_words_with_details(
            888,
            [
                {
                    "lemma": "Training",
                    "part_of_speech": "noun",
                    "translation": "тренировка",
                    "additional_forms": {"plural": "Trainings"},
                },
                {
                    "lemma": "Ort",
                    "part_of_speech": "noun",
                    "translation": "место",
                },
            ],
        )

        assert result["added"] == ["Ort"]
        assert result["invalid"] == ["Training"]
        total = len(result["added"]) + len(result["duplicates"]) + len(result["invalid"])
        assert total == 2
