#!/usr/bin/env python3
"""
Annotate words already in the dictionary with the case their verb governs.

Seeding alone cannot do this: a word like `helfen` or `sich waschen` is
usually already in the user's list, so the curated row is skipped as a
duplicate and its `case`/`topic` never land. This merges those two keys into
the stored `additional_forms`, leaving every other key (praeteritum,
partizip_ii, preposition...) untouched.

Idempotent — running it twice changes nothing.

Usage:
    python scripts/backfill_verb_case.py data/bot.db seed/dativ_verbs.json
    python scripts/backfill_verb_case.py data/bot.db seed/*.json --dry-run
"""

import json
import sqlite3
import sys
from pathlib import Path


def wanted_annotations(json_paths: list[str]) -> dict[str, dict]:
    """Collect lemma -> {case, topic} from the curated files"""
    wanted: dict[str, dict] = {}

    for path in json_paths:
        words = json.loads(Path(path).read_text(encoding="utf-8"))
        found = 0
        for word in words:
            try:
                forms = json.loads(word.get("additional_forms") or "{}")
            except ValueError:
                continue
            if not isinstance(forms, dict):
                continue

            annotation = {k: forms[k] for k in ("case", "topic") if forms.get(k)}
            if annotation:
                wanted[word["lemma"].lower()] = annotation
                found += 1
        print(f"📖 {path}: {found} words carry a case/topic")

    return wanted


def backfill_verb_case(
    db_path: str, json_paths: list[str], dry_run: bool = False
) -> bool:
    """Merge case/topic into additional_forms of words already stored"""
    wanted = wanted_annotations(json_paths)
    if not wanted:
        print("❌ Nothing to apply — no case/topic found in the given files")
        return False

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        cursor = conn.execute("SELECT id, lemma, additional_forms FROM words")

        updates = []
        unchanged = 0
        for row in cursor.fetchall():
            annotation = wanted.get(row["lemma"].lower())
            if not annotation:
                continue

            try:
                forms = json.loads(row["additional_forms"] or "{}")
            except ValueError:
                # A non-JSON legacy value would be lost by merging; replace it
                forms = {}
            if not isinstance(forms, dict):
                forms = {}

            if all(forms.get(k) == v for k, v in annotation.items()):
                unchanged += 1
                continue

            forms.update(annotation)
            updates.append(
                (json.dumps(forms, ensure_ascii=False), row["id"])
            )

        print(f"  🎯 Will annotate: {len(updates)}")
        print(f"  ↩️ Already annotated: {unchanged}")
        missing = len(wanted) - len(updates) - unchanged
        if missing > 0:
            print(f"  ❔ Not in this dictionary yet: {missing} (seed them first)")

        if dry_run:
            print("🧪 Dry run — nothing written")
            return True

        conn.executemany(
            "UPDATE words SET additional_forms = ? WHERE id = ?", updates
        )
        conn.commit()
        print(f"✅ Annotated {len(updates)} words in {db_path}")

        conn.close()
        return True

    except Exception as e:
        print(f"❌ Backfill failed: {e}")
        return False


def main() -> None:
    args = [a for a in sys.argv[1:] if a != "--dry-run"]
    dry_run = "--dry-run" in sys.argv

    if len(args) < 2:
        print(__doc__)
        sys.exit(1)

    db_path, *json_paths = args

    if not Path(db_path).exists():
        print(f"❌ Database not found: {db_path}")
        sys.exit(1)

    sys.exit(0 if backfill_verb_case(db_path, json_paths, dry_run) else 1)


if __name__ == "__main__":
    main()
