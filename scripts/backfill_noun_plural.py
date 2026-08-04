#!/usr/bin/env python3
"""
Make sure every noun stores its plural under `additional_forms.plural`.

Two passes, because the two problems have different costs:

1. Repair — earlier prompt versions answered with `Plural`, `{"Singular": ...}`
   or a bare `plural: die Häuser` string, and some rows hold truncated JSON.
   Those forms are already correct German, they are just unreachable; this
   pass rewrites them in place without calling anything.
2. Generate — nouns with no plural anywhere are sent to OpenAI in batches.
   Off by default: it costs money and needs a key, so it is opt-in.

Proper nouns and plural-only words legitimately have none. They are recorded
as `"plural": null` so a later run does not ask about them again.

Usage:
    python scripts/backfill_noun_plural.py data/bot.db --dry-run
    python scripts/backfill_noun_plural.py data/bot.db
    python scripts/backfill_noun_plural.py data/bot.db --openai
    python scripts/backfill_noun_plural.py data/bot.db --recheck-nulls
"""

import json
import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

BATCH_SIZE = 40

PLURAL_IN_TEXT = re.compile(r"plurals?\s*[:=]\s*\"?([^\"\n,}]+)", re.IGNORECASE)


def parse_forms(raw: str | None) -> dict:
    """Read additional_forms, returning {} for anything unusable"""
    if not raw or raw in ("null", "None", "N/A"):
        return {}
    try:
        forms = json.loads(raw)
    except ValueError:
        return {}
    return forms if isinstance(forms, dict) else {}


def recover_plural(raw: str | None) -> str | None:
    """Find a plural that is present but stored in a shape nothing reads"""
    forms = parse_forms(raw)

    for key, value in forms.items():
        if key.lower() == "plural" and isinstance(value, str) and value.strip():
            return value.strip()

    if not forms and isinstance(raw, str):
        match = PLURAL_IN_TEXT.search(raw)
        if match and match.group(1).strip():
            return match.group(1).strip()

    return None


def has_plural(raw: str | None) -> bool:
    """Whether the row already stores a readable plural, or a decided 'none'"""
    forms = parse_forms(raw)
    return "plural" in forms


def set_plural(raw: str | None, plural: str | None) -> str:
    """Merge the plural into additional_forms, keeping every other key"""
    forms = parse_forms(raw)
    # Drop the legacy spellings so only one key remains authoritative
    for key in [k for k in forms if k.lower() in ("plural", "plurals")]:
        del forms[key]
    forms["plural"] = plural
    return json.dumps(forms, ensure_ascii=False)


def repair(conn: sqlite3.Connection, dry_run: bool) -> list[sqlite3.Row]:
    """Rewrite recoverable plurals; return the nouns still without one"""
    rows = conn.execute(
        "SELECT id, lemma, additional_forms FROM words"
        " WHERE LOWER(part_of_speech) LIKE 'noun%'"
    ).fetchall()

    updates = []
    still_missing = []
    already = 0

    for row in rows:
        if has_plural(row["additional_forms"]):
            already += 1
            continue

        plural = recover_plural(row["additional_forms"])
        if plural:
            updates.append((set_plural(row["additional_forms"], plural), row["id"]))
        else:
            still_missing.append(row)

    print(f"📖 Nouns: {len(rows)}")
    print(f"  ✔️ Already fine: {already}")
    print(f"  🔧 Recovered from a legacy shape: {len(updates)}")
    print(f"  ❔ Still without a plural: {len(still_missing)}")

    if updates and not dry_run:
        conn.executemany(
            "UPDATE words SET additional_forms = ? WHERE id = ?", updates
        )
        conn.commit()

    return still_missing


# "Fast jedes" is deliberate: a first version offered null as an option up
# front and got it for Sonne, Kino and Gehalt, which all have a plural.
STRICT_PLURAL_PROMPT = (
    "Gib für jedes deutsche Substantiv den Plural mit Artikel an, "
    "zum Beispiel 'die Häuser'. Fast jedes Substantiv mit Artikel hat einen "
    "Plural — gib ihn an. Nur wenn das Wort wirklich unzählbar ist "
    "(Stoffname wie Wasser, Abstraktum wie Gesundheit), ein Eigenname ist "
    "oder selbst schon Plural, antworte mit null. Im Zweifel gib die "
    'Pluralform an. Antworte NUR als JSON-Objekt {"Wort": "die Plural-Form"}.'
    "\n\n"
)


async def ask_openai(lemmas: list[str]) -> dict[str, str | None]:
    """Ask for the plural of each lemma, null when the noun has none"""
    from src.word_processor import get_word_processor

    processor = get_word_processor()
    plurals: dict[str, str | None] = {}

    for start in range(0, len(lemmas), BATCH_SIZE):
        batch = lemmas[start : start + BATCH_SIZE]
        prompt = STRICT_PLURAL_PROMPT + "\n".join(batch)

        response = await processor.client.chat.completions.create(
            model=processor.model,
            messages=[
                {
                    "role": "system",
                    "content": "Du bist ein deutscher Grammatik-Experte. "
                    "Antworte ausschließlich mit gültigem JSON.",
                },
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content or "{}"
        try:
            answer = json.loads(content)
        except ValueError:
            print(f"  ⚠️ Unparsable answer for batch starting at {start}")
            continue

        if isinstance(answer, dict):
            for lemma in batch:
                if lemma in answer:
                    value = answer[lemma]
                    plurals[lemma] = value if isinstance(value, str) else None

        print(f"  🤖 {min(start + BATCH_SIZE, len(lemmas))}/{len(lemmas)}")

    return plurals


def generate(conn: sqlite3.Connection, missing: list[sqlite3.Row], dry_run: bool) -> None:
    """Fill the remaining plurals with one OpenAI pass"""
    import asyncio

    lemmas = [row["lemma"] for row in missing]
    if not lemmas:
        print("✅ Nothing left to generate")
        return

    plurals = asyncio.run(ask_openai(lemmas))
    print(f"  📝 Answered: {len(plurals)}/{len(lemmas)}")

    updates = [
        (set_plural(row["additional_forms"], plurals.get(row["lemma"])), row["id"])
        for row in missing
        if row["lemma"] in plurals
    ]

    if dry_run:
        for row in missing[:15]:
            if row["lemma"] in plurals:
                print(f"    + {row['lemma']} → {plurals[row['lemma']]}")
        print("🧪 Dry run — nothing written")
        return

    conn.executemany("UPDATE words SET additional_forms = ? WHERE id = ?", updates)
    conn.commit()
    print(f"✅ Generated plurals for {len(updates)} nouns")


def recheck_nulls(conn: sqlite3.Connection, dry_run: bool) -> None:
    """Ask again about nouns recorded as having no plural.

    Only nouns that carry an article are rechecked — those are ordinary
    countable words, so a null there is far more likely to be a bad answer
    than a real gap. A null answer is kept as is, so this can only add.
    """
    import asyncio

    rows = conn.execute(
        "SELECT id, lemma, additional_forms FROM words"
        " WHERE LOWER(part_of_speech) LIKE 'noun%'"
        " AND article IS NOT NULL AND TRIM(article) != ''"
        " AND json_valid(additional_forms)"
        " AND json_extract(additional_forms, '$.plural') IS NULL"
    ).fetchall()

    print(f"🔁 Nouns with an article but no plural: {len(rows)}")
    if not rows:
        return

    plurals = asyncio.run(ask_openai([row["lemma"] for row in rows]))

    updates = []
    for row in rows:
        plural = plurals.get(row["lemma"])
        if plural:
            updates.append((set_plural(row["additional_forms"], plural), row["id"]))

    print(f"  ✏️ Now have a plural: {len(updates)}")
    print(f"  ➖ Still none, kept as null: {len(rows) - len(updates)}")

    if dry_run:
        for forms, word_id in updates[:15]:
            lemma = next(r["lemma"] for r in rows if r["id"] == word_id)
            print(f"    + {lemma} → {json.loads(forms)['plural']}")
        print("🧪 Dry run — nothing written")
        return

    conn.executemany("UPDATE words SET additional_forms = ? WHERE id = ?", updates)
    conn.commit()
    print(f"✅ Corrected {len(updates)} nouns")


def backfill(
    db_path: str,
    dry_run: bool = False,
    use_openai: bool = False,
    recheck: bool = False,
) -> bool:
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        missing = repair(conn, dry_run)

        if use_openai:
            generate(conn, missing, dry_run)
        elif missing:
            print("  ℹ️ Re-run with --openai to generate the missing ones")

        if recheck:
            recheck_nulls(conn, dry_run)

        if dry_run:
            print("🧪 Dry run — nothing written")

        conn.close()
        return True
    except Exception as e:
        print(f"❌ Backfill failed: {e}")
        return False


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry_run = "--dry-run" in sys.argv
    use_openai = "--openai" in sys.argv
    recheck = "--recheck-nulls" in sys.argv

    if not args:
        print(__doc__)
        sys.exit(1)

    db_path = args[0]
    if not Path(db_path).exists():
        print(f"❌ Database not found: {db_path}")
        sys.exit(1)

    sys.exit(0 if backfill(db_path, dry_run, use_openai, recheck) else 1)


if __name__ == "__main__":
    main()
