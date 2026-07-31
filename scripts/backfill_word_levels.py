#!/usr/bin/env python3
"""
Backfill CEFR levels (A1..C1) for words added before the level field existed.

Levels come from a curated lemma -> level map, so no OpenAI calls are needed.
Only rows with an empty level are touched; already labeled words are kept.

Usage:
    python scripts/backfill_word_levels.py data/bot.db [seed/word_levels.json]
    python scripts/backfill_word_levels.py data/bot.db --dry-run
"""

import json
import sqlite3
import sys
from pathlib import Path

DEFAULT_LEVELS_PATH = "seed/word_levels.json"


def backfill_levels(db_path: str, levels_path: str, dry_run: bool = False) -> bool:
    """Apply the curated level map to words with no level yet"""
    levels: dict[str, str] = json.loads(Path(levels_path).read_text(encoding="utf-8"))
    print(f"📖 Loaded {len(levels)} lemma levels from {levels_path}")

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        cursor = conn.execute(
            "SELECT id, lemma FROM words WHERE level IS NULL OR TRIM(level) = ''"
        )
        pending = [(row["id"], row["lemma"]) for row in cursor.fetchall()]
        print(f"  📝 Words without a level: {len(pending)}")

        updates = []
        unknown = []
        for word_id, lemma in pending:
            level = levels.get(lemma)
            if level:
                updates.append((level, word_id))
            else:
                unknown.append(lemma)

        counts: dict[str, int] = {}
        for level, _ in updates:
            counts[level] = counts.get(level, 0) + 1
        print(f"  🎯 Will set: {dict(sorted(counts.items()))}")
        if unknown:
            print(f"  ❔ No level in map ({len(unknown)}): {sorted(unknown)}")

        if dry_run:
            print("🧪 Dry run — nothing written")
            return True

        conn.executemany("UPDATE words SET level = ? WHERE id = ?", updates)
        conn.commit()
        print(f"✅ Updated {len(updates)} words in {db_path}")

        cursor = conn.execute(
            "SELECT IFNULL(level, 'NULL') AS level, COUNT(*) AS n "
            "FROM words GROUP BY 1 ORDER BY 1"
        )
        for row in cursor.fetchall():
            print(f"  {row['level']}: {row['n']}")

        conn.close()
        return True

    except Exception as e:
        print(f"❌ Backfill failed: {e}")
        return False


def main() -> None:
    args = [a for a in sys.argv[1:] if a != "--dry-run"]
    dry_run = "--dry-run" in sys.argv

    if not args:
        print(__doc__)
        sys.exit(1)

    db_path = args[0]
    levels_path = args[1] if len(args) > 1 else DEFAULT_LEVELS_PATH

    if not Path(db_path).exists():
        print(f"❌ Database not found: {db_path}")
        sys.exit(1)

    sys.exit(0 if backfill_levels(db_path, levels_path, dry_run) else 1)


if __name__ == "__main__":
    main()
