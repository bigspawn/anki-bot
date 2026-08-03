#!/usr/bin/env python3
"""
Seed a curated word list into a user's dictionary.

Used for word groups that are hard to collect from texts one by one:
reflexive verbs (seed/reflexive_verbs.json) and verbs governing a preposition
(seed/preposition_verbs.json). Words already in the user's list are skipped.

Usage:
    python scripts/seed_words.py data/bot.db 739529 seed/reflexive_verbs.json
    python scripts/seed_words.py data/bot.db 739529 seed/*.json --dry-run
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.database.database_manager import DatabaseManager  # noqa: E402


def validate_words(words: list[dict]) -> list[str]:
    """Return a message per malformed card.

    A cloze card without an answer is unusable: the reveal side would show a
    rule with nothing to check it against.
    """
    problems = []
    for word in words:
        lemma = word.get("lemma", "<no lemma>")

        if word.get("part_of_speech") != "cloze":
            continue

        try:
            forms = json.loads(word.get("additional_forms") or "{}")
        except ValueError:
            problems.append(f"{lemma}: additional_forms is not valid JSON")
            continue

        if not isinstance(forms, dict) or not forms.get("answer"):
            problems.append(f"{lemma}: cloze card without additional_forms.answer")

    return problems


def seed_words(
    db_path: str, telegram_id: int, json_paths: list[str], dry_run: bool = False
) -> bool:
    """Add the curated words to the user's dictionary"""
    words = []
    for path in json_paths:
        batch = json.loads(Path(path).read_text(encoding="utf-8"))
        print(f"📖 {path}: {len(batch)} words")
        words.extend(batch)

    problems = validate_words(words)
    if problems:
        print(f"⚠️ Skipped as invalid: {len(problems)}")
        for problem in problems:
            print(f"    ! {problem}")
        return False
    print("  ✔️ Invalid: 0")

    db_manager = DatabaseManager(db_path)
    db_manager.init_database()

    user = db_manager.get_user_by_telegram_id(telegram_id)
    if not user:
        print(f"❌ User {telegram_id} not found in {db_path}")
        return False

    existing = db_manager.check_multiple_words_exist(
        telegram_id, [w["lemma"] for w in words]
    )
    new_words = [w for w in words if not existing.get(w["lemma"])]
    print(f"  🆕 New for user {telegram_id}: {len(new_words)}")
    print(f"  ↩️ Already in the list: {len(words) - len(new_words)}")

    if dry_run:
        for word in new_words:
            print(f"    + {word['lemma']} — {word['translation']}")
        print("🧪 Dry run — nothing written")
        return True

    result = db_manager.add_words_with_details(telegram_id, words)
    print(f"✅ Added {len(result['added'])} words to {db_path}")
    if result["duplicates"]:
        print(f"  ↩️ Skipped as duplicates: {len(result['duplicates'])}")
    if result["invalid"]:
        print(f"  ⚠️ Skipped as invalid: {result['invalid']}")

    return True


def main() -> None:
    args = [a for a in sys.argv[1:] if a != "--dry-run"]
    dry_run = "--dry-run" in sys.argv

    if len(args) < 3:
        print(__doc__)
        sys.exit(1)

    db_path, telegram_id, *json_paths = args

    if not Path(db_path).exists():
        print(f"❌ Database not found: {db_path}")
        sys.exit(1)

    sys.exit(0 if seed_words(db_path, int(telegram_id), json_paths, dry_run) else 1)


if __name__ == "__main__":
    main()
