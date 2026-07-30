# Issues & Feature Requests

Running list of user complaints and feature requests, dictated by the user and
recorded by Claude. Each item: description, status, and (once investigated) root
cause / fix plan.

**Deployment note:** the live bot runs on `bgspwn-home-nas.tailba405.ts.net`
(Synology NAS), container `german-bot`, project dir
`/volume1/docker/anki-bot/`, DB at `/volume1/docker/anki-bot/data/bot.db`
(`docker compose -f docker-compose.prod.yml`, docker binary at
`/usr/local/bin/docker`). The `do-fra1` host also has an old copy of this
project (`/root/projects/anki-bot/`) but its `german-bot` container doesn't
exist there and its DB hasn't been touched since 2026-03-23 — it's a stale/
abandoned deployment, not the live one. Don't use it for investigation.

## 1. Statistics are calculated incorrectly

Status: **root cause found**

`/stats` shows wrong/missing numbers: words added, filtered, correct/incorrect
review counts.

Confirmed in code (`src/core/database/repositories/user_repository.py:183-185`):

```python
# Calculate study streak (simplified)
stats["study_streak"] = 0  # Would need more complex logic
stats["words_today"] = 0  # Would need to track word additions
```

- `words_today` (words added today) is hardcoded to `0` — never actually queried.
- `study_streak` is hardcoded to `0` — never actually computed.
- `format_progress_stats` (`src/utils.py:67`) only prints `total_words`,
  `due_words`, `new_words`, `average_accuracy` — no correct/incorrect review
  counts, no "filtered" (skipped/rejected) word count anywhere in `/stats`.
- Filtered/skipped words (duplicates, non-German, parse failures) are only
  reported in the one-off `/add` success message
  (`src/bot_handler.py:444-462`), not in `/stats`.

## 2. Study last N added words

Status: **implemented**

Added `/study_recent [N]` command (default 10, max 200) — studies the most
recently added words ordered by `learning_progress.created_at DESC`,
regardless of SM2 due date. New repo method `WordRepository.get_recent_words`
+ `DatabaseManager.get_recent_words`, handler
`CommandHandlers.study_recent_command`
(`src/core/handlers/command_handlers.py`), registered in `src/bot_handler.py`
and bot command menu. Tests: `tests/test_study_recent_feature.py`.

## 3. Translation/example quality

Status: **root cause found, prompt fix applied, model switch pending your
action** — checked against the **live** production DB on
`bgspwn-home-nas.tailba405.ts.net` (2033 words as of 2026-07-29).

Root cause candidate #1 — cheap model (still live, needs your action):

```
# /volume1/docker/anki-bot/.env on bgspwn-home-nas
OPENAI_MODEL=gpt-4.1-nano-2025-04-14
```

`nano` is OpenAI's smallest/cheapest tier, not suited for nuanced linguistic
analysis (idioms, polysemy, article edge cases). This is the most likely
driver of "wrong translation" complaints, more than the prompt itself.
**Not changed — I don't edit `.env` files. See instructions below.**

Root cause candidate #2 — system prompt had no guardrails. **Fixed** in
`src/word_processor.py` (`_get_system_prompt` / `_get_batch_system_prompt`):
added explicit rules forbidding the translation from echoing the German word
and forbidding Russian text inside the example sentence. Evidence that
prompted the fix (11/2033 = 0.5% of all words, 2/471 = 0.4% of words added
since March, so it's rare but ongoing, not fully fixed by an earlier prompt
version as previously assumed):

- Lemma leaked into translation: `Vegetation` → `" Vegetation"` (not
  translated at all), `sichern` → `"обеспечивать, sichern — охранять,
  закреплять"`, `Rechnung` → `"Счёт, Rechnung"`, `Weiterbildung` →
  `"повышение квалификации, Weiterbildung"`, and 7 more.
- 8 very early rows (ids 203-217) have the Russian translation stuffed into
  the `example` field in parentheses, e.g. `"Ich bin immer pünktlich. (Я
  всегда пунктуален.)"` — none found in recent additions, so this specific
  pattern does look fixed already (unrelated to today's prompt change).

**Action needed from you** — I won't touch `.env`. On
`bgspwn-home-nas.tailba405.ts.net`, edit
`/volume1/docker/anki-bot/.env` and change:

```
OPENAI_MODEL=gpt-4.1-mini
```

then restart:

```
/usr/local/bin/docker compose -f /volume1/docker/anki-bot/docker-compose.prod.yml up -d
```

I can run the restart for you once you've made the `.env` change — just ask.

## 4. Data audit: bad lemma forms, wrong translations, wrong examples

Status: **list compiled, fixes NOT yet applied — awaiting your decision on the
delete-vs-fix items below**

Audited the live DB (2033 words) with targeted SQL heuristics (non-infinitive
verb lemmas, lowercase nouns, non-Cyrillic translations, examples not
containing the lemma, duplicated examples, self-flagged part-of-speech
values), then manually verified every candidate. This is not a 100%
line-by-line read of all 2033 rows — it's heuristic-guided, so some subtle
mistranslations may still be missed.

### A. Junk entries — not real words, propose **deleting** (needs your OK,
removes the word + its learning history)

| id | lemma | why |
|---|---|---|
| 429 | `der/das` | AI self-tagged part_of_speech as "incorrect form" |
| 432 | `der/die` | same, self-tagged "incorrect form" |
| 804 | `verb` | literal placeholder entry, translation "глаголы" |
| 931 | `ga` | AI's own example field literally says "Нет корректного примера" |
| 1698 | `txt` | file extension, not a German word |

### B. Broken/fragment entries — fixable by correcting the lemma (keeps
learning history)

| id | current lemma | fix to | why |
|---|---|---|---|
| 899 | *(empty)* | `kennenlernen` | lemma is blank; translation/example clearly point to colloquial "kennenlernen" |
| 871 | `fu` | `pfui` | AI self-tagged "not a standard word, possibly a typo"; translation "фу" matches German interjection `pfui` |
| 1754 | `zanzen` | `Zähne` | not a real German word; translation "зубы" (teeth) = `Zähne` |
| 1751 | `düsterstraße` | delete or keep? | ad-hoc invented compound ("dark street"), not a dictionary word — your call |

### C. Wrong case / non-base lemma form (fixable, capitalization or
infinitive)

| id | current | fix to |
|---|---|---|
| 1465 | `einhaltung` (verb) | `Einhaltung` (noun) |
| 1903 | `festgestellt` (Partizip II) | `feststellen` (infinitive) |
| 632 | `liebling` | `Liebling` |
| 904 | `splitter` | `Splitter` (see also C below — translation/example also wrong) |
| 1225 | `mitte` | `Mitte` |
| 197 | `morgen` | conflates adverb "tomorrow" + noun "morning" in one lowercase entry — needs splitting or picking one sense |
| 602 | `angestellt` | tagged both adjective and verb; as verb should be `anstellen` |

### D. Wrong translation (confirmed factually incorrect)

| id | lemma | current translation | should be |
|---|---|---|---|
| 250 | `fallen` (падать) | `нравится` | `падать` — this is the meaning of `gefallen`, a different verb |
| 465 | `Rock` (юбка) | `рок, камень` | `юбка` — got confused with English "rock" |
| 783 | `Gesicht` | `脸` | `лицо` — translated into **Chinese**, not Russian |
| 904 | `splitter`/`Splitter` | `камертоны... (музыкальных инструментов)` ("tuning forks") | `осколок, щепка` |
| 1983 | `Geschenkpapier` | `gift wrap` | `подарочная бумага` — translated into **English**, not Russian |

### E. Wrong/broken example sentence

| id | lemma | current example | problem |
|---|---|---|---|
| 250 | `fallen` | `Das Bild gefällt mir sehr.` | example is for `gefallen`, doesn't use `fallen` at all (duplicate of id 1147's example) |
| 465 | `Rock` | `Der Felsen ist sehr groß.` | doesn't mention `Rock` at all, talks about a cliff |
| 904 | `splitter` | `Die Musiker stimmen ihre Späne.` | uses wrong word `Späne`, nonsensical sentence |
| 1225 | `mitte` | `Im mitten der Stadt gibt es einen Park.` | ungrammatical, should be `In der Mitte der Stadt...` |
| 1781 | `abstatten` | `Der König statten dem Land einen Besuch ab.` | subject-verb agreement error, should be `stattet` |
| 1884 | `bestimmt` | `Der certain Bescheid ist für die Reise erforderlich.` | stray English word `certain` inside a German sentence |
| 1959 | `Nahrungsmittel` | `Lebensmittel sind lebenswichtig.` | uses synonym `Lebensmittel`, never actually uses `Nahrungsmittel` |
| 931 | `ga` | *(see A — self-admitted no example)* | — |

### Also flagged, not clearly a bug — your call

- **Prepositional-contraction "words"**: ids 4, 10, 202, 596, 751, 851, 861,
  863, 921, 962, 1171, 1174, 1688, 1733, 1786 (`zu+dem`, `an das`, `bei dem`,
  `von dem`, etc.) — the bot created standalone vocabulary cards for
  preposition+article combinations, some with a broken `+` syntax (`zu+dem`
  instead of `zudem`/`zum`). Might be intentional (drilling case government)
  or might be text-parser noise from sentences like "Ich gehe zum Arzt" being
  split wrong. Worth deciding whether this category should exist at all.
- ids 811 / 1743: two duplicate `sie` entries with garbage lemmas
  (`sie (они в дательном падеже)`, `sie (Pronomen, Dativ)`) instead of a clean
  pronoun form — likely both should be merged/removed since `sie` is probably
  already a separate clean entry elsewhere.
- Nationality adjectives tagged as noun too (`rumänisch`, `türkisch`,
  `ungarisch`) — fine lowercase as adjectives, but the "noun" tag is
  misleading since the noun sense needs a different capitalized word.

### Proposed process once you confirm scope
1. `sqlite3` backup of `bot.db` on the NAS before any write.
2. Apply category B/C/D fixes as `UPDATE` statements (~15 rows, low risk,
   keeps learning history).
3. For category A/grey-area items, apply your delete/keep decision.
4. Re-run the same audit queries after to confirm zero regressions.

**Decisions (confirmed by user 2026-07-30):** delete all of category A
(429, 432, 804, 931, 1698), delete 1751 (`düsterstraße`), fix the category B
fragments instead of deleting (899→`kennenlernen`, 871→`fu`→`pfui`,
1754→`zanzen`→`Zahn`), delete all 15 prepositional-contraction entries, delete
the 2 duplicate malformed `sie` entries (811, 1743). Category C/D/E factual
fixes applied as proposed.

**Executed 2026-07-30** on the live NAS DB (backup taken first:
`/volume1/docker/anki-bot/data/bot.db.bak_20260730_090040`):
- Deleted 23 junk/contraction/duplicate entries + their `learning_progress` /
  `review_history` rows.
- Applied 14 `UPDATE` fixes for category C/D/E.
- 3 of the planned "fix the lemma" fragment fixes (899→`kennenlernen`,
  1754→`Zahn`, 1903→`feststellen`) hit `UNIQUE constraint failed: words.lemma`
  — turned out each one was a genuine near-duplicate of an *already-existing*
  clean entry the model had created earlier under a different surface form
  (id 218 `kennenlernen`, id 801 `Zahn`, id 1057 `feststellen`). Deleted the 3
  duplicates instead of renaming them.
- Word count: 2033 → 2007.

**Root cause of those 3 duplicates — checked the code, not a dedup bug:**
`WordRepository.add_words_to_user` (`src/core/database/repositories/word_repository.py:300-305`)
already does a case-insensitive check against the whole `words` table
(`WHERE LOWER(lemma) = LOWER(?)`) before inserting, and `words.lemma` has a
`UNIQUE` constraint — exact re-adds are correctly blocked. The duplicates
happened because OpenAI returned a *different surface form* for the same
underlying word on different occasions (infinitive vs. participle, a
hallucinated wrong word, or a blank lemma) — different strings can't be
caught by exact/case-insensitive matching. Fixed by adding explicit
lemma-canonicalization rules to both system prompts in
`src/word_processor.py` (`_get_system_prompt` / `_get_batch_system_prompt`):
lemma must always be infinitive/singular-nominative-capitalized/base form,
must never be empty, `part_of_speech` must be a single clean value from a
fixed list, and preposition+article contractions must never be treated as
standalone words. This won't fix already-stored bad rows but should stop new
ones of this kind.

## 5. Study by part of speech

Status: **implemented**

First cut used an arg-based `/study_pos <part_of_speech>`. User explicitly
disliked having to pick a value ("не нравится что команды надо еще както
выбирать хочу плоские команды") — redone as flat, argument-free commands
matching the existing `/study_verbs` pattern: `/study_nouns`,
`/study_adjectives`, `/study_adverbs`, `/study_pronouns`,
`/study_prepositions`, `/study_conjunctions`, `/study_numerals`,
`/study_interjections`. Each is a thin wrapper around a shared
`CommandHandlers._study_pos(update, context, part_of_speech)` helper.
Matches `LOWER(part_of_speech) LIKE LOWER(?) || '%'` (prefix match) so
multi-tagged values like "adjective/verb (Partizip II)" are still found
under "adjective". New repo method
`WordRepository.get_words_by_part_of_speech` +
`DatabaseManager.get_words_by_part_of_speech`. Tests:
`tests/test_study_pos_feature.py`.

## 6. Topic/category-based study ("rubrics")

Status: **implemented (level rubric + common-verbs rubric)**

- Added a `level` column to `words` (migration in
  `src/core/database/connection.py::_run_migrations`, runs automatically on
  next bot startup — no manual DB surgery needed). OpenAI system prompts
  (`src/word_processor.py`) now also return a CEFR level estimate
  (A1/A2/B1/B2/C1/C2) for every newly processed word, stored end-to-end
  (`ProcessedWord.level` → `words_data["level"]` in `bot_handler.py` →
  `WordRepository.add_words_to_user`/`create_word`).
- Same flat-command redo as item 5: `/study_a1`, `/study_a2`, `/study_b1`,
  `/study_b2`, `/study_c1`, `/study_c2` (no argument), each a thin wrapper
  around `CommandHandlers._study_level(update, context, level)`.
  **Existing 2007 words have `level = NULL`** — this only tags words added
  from now on; retroactively classifying old words would need a separate
  bulk OpenAI pass over the whole DB (extra cost/time), not done here.
- `/study_common_verbs` — a curated, hardcoded list of ~90 of the most
  frequent German verbs (`COMMON_VERBS` in
  `src/core/handlers/command_handlers.py`, standard DaF/Goethe-Institut
  frequency list) intersected with the user's own words
  (`WordRepository.get_words_by_lemma_set`). Deliberately NOT AI-generated
  per-word popularity, to avoid the same kind of hallucination risk found in
  item 4. Already argument-free, no redo needed.
- Tests: `tests/test_study_level_feature.py`.
- Not done: arbitrary free-form topic tagging (e.g. "travel", "food") beyond
  level + common-verbs — would need its own tagging scheme; not requested
  with that level of detail, can be added later if wanted.
