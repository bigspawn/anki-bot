#!/usr/bin/env python3
"""
Push corrected text from a seed file onto cards already in the dictionary.

Seeding cannot do this: a card that is already there is skipped as a
duplicate, so fixing a translation in seed/*.json never reaches the database.
This updates `translation` and `example` for matching rows.

Only rows whose `part_of_speech` matches the seed card are touched. A seeded
lemma can collide with an ordinary word the user added themselves, and
overwriting that word's own translation would be data loss.

Usage:
    python scripts/resync_seed_text.py data/bot.db seed/pronoun_case.json --dry-run
    python scripts/resync_seed_text.py data/bot.db seed/pronoun_case.json
"""

import json
import sqlite3
import sys
from pathlib import Path


def resync(db_path: str, json_paths: list[str], dry_run: bool = False) -> bool:
    """Copy translation/example from the seed files onto existing rows"""
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        updates = []
        missing = 0
        mismatched = 0

        for path in json_paths:
            cards = json.loads(Path(path).read_text(encoding="utf-8"))
            if not isinstance(cards, list):
                print(f"⏭️ {path}: not a card list, skipped")
                continue

            touched = 0
            for card in cards:
                row = conn.execute(
                    "SELECT id, part_of_speech, translation, example FROM words"
                    " WHERE lemma = ?",
                    (card["lemma"],),
                ).fetchone()

                if not row:
                    missing += 1
                    continue

                if row["part_of_speech"] != card["part_of_speech"]:
                    # Someone else's word under the same lemma — leave it be
                    mismatched += 1
                    continue

                if (
                    row["translation"] == card["translation"]
                    and row["example"] == card["example"]
                ):
                    continue

                updates.append((card["translation"], card["example"], row["id"]))
                touched += 1
                if dry_run:
                    print(f"    ~ {card['lemma']}")
                    print(f"      было : {row['translation']}")
                    print(f"      стало: {card['translation']}")

            print(f"📖 {path}: {len(cards)} cards, {touched} to update")

        print(f"  ✏️ Will update: {len(updates)}")
        if missing:
            print(f"  ❔ Not in this dictionary: {missing}")
        if mismatched:
            print(f"  ⏭️ Same lemma, different part of speech — left alone: {mismatched}")

        if dry_run:
            print("🧪 Dry run — nothing written")
            return True

        conn.executemany(
            "UPDATE words SET translation = ?, example = ? WHERE id = ?", updates
        )
        conn.commit()
        print(f"✅ Updated {len(updates)} cards in {db_path}")

        conn.close()
        return True

    except Exception as e:
        print(f"❌ Resync failed: {e}")
        return False


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry_run = "--dry-run" in sys.argv

    if len(args) < 2:
        print(__doc__)
        sys.exit(1)

    db_path, *json_paths = args

    if not Path(db_path).exists():
        print(f"❌ Database not found: {db_path}")
        sys.exit(1)

    sys.exit(0 if resync(db_path, json_paths, dry_run) else 1)


if __name__ == "__main__":
    main()
