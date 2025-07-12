# Planned Features

This document outlines the planned features for the Anki Bot project, organized by priority and implementation complexity.

## Overview

The following features have been identified to improve user experience, system reliability, and functionality:

1. ~~**Rate Limiting for /add Command** (High Priority)~~ ✅ **COMPLETED**
2. **Study Reminder Notifications** (High Priority)
3. **Unprocessed Words Reporting** (Medium Priority)
4. **Improved Difficulty Rating Buttons** (Medium Priority)

---

## ~~1. 🚫 Rate Limiting for /add Command~~ ✅ **COMPLETED**

### **Problem:** ✅ **SOLVED**
~~Users can send multiple `/add` commands simultaneously, leading to parallel processing and API limit overuse.~~

### **Implementation:** ✅ **COMPLETED**

#### ✅ **1.1 User Lock Management System**
- ✅ Created `UserLockManager` class in `src/core/locks/`
- ✅ In-memory storage `Dict[user_id, LockInfo]`
- ✅ Lock structure with `locked_at`, `operation`, `lock_id`

#### ✅ **1.2 Integration in bot_handler.py**
- ✅ Added lock check in `_process_text_for_user()`
- ✅ Lock user before processing starts
- ✅ Unlock after completion (success/error)
- ✅ Show message "⏳ Обработка уже выполняется!"

#### ✅ **1.3 Exception Handling**
- ✅ `try/finally` block for guaranteed unlock
- ✅ Lock timeout (5 minutes) for stuck operations
- ✅ Periodic cleanup task with asyncio

#### ✅ **1.4 User Interface**
- ✅ Message on duplicate `/add` attempt with operation details
- ✅ Progress indicator in original message
- ✅ Completion notification

**Status: FULLY IMPLEMENTED AND TESTED ✅**

---

## 2. 🔔 Study Reminder Notifications

### **Problem:**
Users forget to review words regularly, no automatic reminders exist.

### **Implementation Plan:**

#### **2.1 Reminder System**
- Create `ReminderManager` class in `src/core/reminders/`
- Use `asyncio` task scheduler
- Store settings in `user_settings` table

#### **2.2 Database Schema**
- Add `user_settings` table:
  ```sql
  CREATE TABLE user_settings (
      user_id INTEGER PRIMARY KEY,
      reminder_enabled BOOLEAN DEFAULT TRUE,
      reminder_time TIME DEFAULT '20:00',
      timezone TEXT DEFAULT 'Europe/Moscow',
      last_reminder_sent TIMESTAMP,
      FOREIGN KEY (user_id) REFERENCES users(id)
  );
  ```

#### **2.3 Reminder Logic**
- Daily check: are there words due for review?
- Send reminder at configured time
- Conditions: `due_words > 0` + `last_study > 24h`
- Skip if user already studied today

#### **2.4 User Settings**
- `/settings` command with inline buttons:
  - 🔔 Enable/disable reminders
  - ⏰ Set time (list selection)
  - 🌍 Choose timezone
- Save in `user_settings`

#### **2.5 Reminder Messages**
- Personalized texts:
  - "📚 You have 15 words ready for review!"
  - "🎯 Time to study! Press /study"
- Inline button "Start studying" → `/study`
- "Remind later" button → postpone 2 hours

#### **2.6 Technical Implementation**
- Background task `asyncio.create_task()` in `BotHandler`
- Minute-by-minute time check for each user
- Group by timezones for optimization
- Graceful shutdown on bot stop

---

## 3. 📝 Unprocessed Words Reporting

### **Problem:**
Words like 'banane' are missing from OpenAI batch responses, but users don't know about this. Information about failed processing is lost.

### **Implementation Plan:**

#### **3.1 Response Structure**
- Change `process_text()` return type to:
  ```python
  @dataclass
  class ProcessingResult:
      processed_words: List[ProcessedWord]
      failed_words: List[str]
      total_attempted: int
      success_rate: float
  ```

#### **3.2 Failed Words Tracking**
- In `process_words_batch()` collect words not returned in JSON
- In `_parse_batch_openai_response()` compare input vs output words
- Log missing words as `failed_words`

#### **3.3 Bot Handler Updates**
- Modify `_process_text_for_user()` to work with `ProcessingResult`
- Show user summary:
  ```
  ✅ Added: 8 words
  ⚠️ Failed to process: banane, oranges
  📊 Success rate: 80%
  ```

#### **3.4 User Interface**
- Add "Try again" button for failed words
- Option to reprocess only problematic words
- Save failed words list for subsequent attempts

#### **3.5 Logging and Analytics**
- Separate log level for failed words
- Collect statistics on failed word frequency
- Pattern analysis (which word types fail more often)

---

## 4. 🔘 Improved Difficulty Rating Buttons

### **Problem:**
Current difficulty buttons are hard to read with short card text. Users struggle to understand button meanings.

### **Current State:**
```
Again | Hard | Good | Easy
```

### **Proposed Solution: Colored Symbols + Text**
```
🔴 Снова | 🟡 Сложно | 🟢 Хорошо | 🔵 Легко
```

### **Implementation Plan:**

#### **4.1 Button Updates**
- Replace in `create_difficulty_buttons()` in `utils.py`:
  ```python
  buttons = [
      ("🔴 Снова", "again"),
      ("🟡 Сложно", "hard"), 
      ("🟢 Хорошо", "good"),
      ("🔵 Легко", "easy")
  ]
  ```

#### **4.2 Adaptive Design**
- Short buttons for narrow screens:
  ```python
  if len(card_text) < 50:  # Short text
      buttons = [("🔴", "again"), ("🟡", "hard"), ("🟢", "good"), ("🔵", "easy")]
  else:  # Long text
      buttons = [("🔴 Снова", "again"), ("🟡 Сложно", "hard"), 
                ("🟢 Хорошо", "good"), ("🔵 Легко", "easy")]
  ```

#### **4.3 User Hints**
- Show hint on first use:
  ```
  🔴 Снова (забыл) | 🟡 Сложно (с трудом) | 🟢 Хорошо (помню) | 🔵 Легко (знаю точно)
  ```

#### **4.4 User Settings**
- Add button style choice in `/settings`:
  - 🎨 Classic (text)
  - 🌈 Colored (emoji + text)  
  - 🎯 Minimal (emoji only)
  - 🔢 Numeric (numbers)

---

---

## 5. 🐛 Fix Word Count Discrepancy

### **Problem:**
Word count discrepancy in processing results. Example: extracted 45 words, but only 36 added + 2 existing = 38 total, missing 7 words.

### **Implementation Plan:**
- Investigate word count discrepancy in batch processing
- Ensure proper tracking of failed/skipped words
- Fix any logging inconsistencies
- Add validation that input word count equals output word count

---

## 6. 👥 Fix Multi-User Word Isolation

### **Problem:**
При многопользовательском использовании новые и существующие добавленные слова от нового пользователя не появляются в его списке изучения. Слова одного пользователя могут быть видны другому пользователю, что нарушает изоляцию данных.

### **Implementation Plan:**

#### **6.1 Investigate Current Word Isolation**
- Analyze database schema for user-word relationships
- Check if words are properly associated with user_id
- Identify where word isolation breaks down in the codebase

#### **6.2 Write Multi-User Isolation Tests**
- Create test scenarios with multiple users
- Test word addition isolation (user A words not visible to user B)
- Test study session isolation
- Test word statistics isolation
- Test existing word detection per user

#### **6.3 Fix Database Queries**
- Ensure all word queries include user_id filtering
- Fix word retrieval in study sessions
- Fix word statistics calculations
- Fix existing word detection logic

#### **6.4 Test Cases to Implement**
```python
def test_multi_user_word_isolation():
    # User A adds words
    # User B adds same words
    # Verify each user sees only their own words
    
def test_study_session_isolation():
    # User A has words due for review
    # User B starts study session
    # Verify User B doesn't see User A's words
    
def test_word_statistics_isolation():
    # Multiple users have different progress
    # Verify statistics are user-specific
```

#### **6.5 Database Schema Verification**
- Ensure proper foreign key relationships
- Verify user_id is present in all relevant tables
- Check indexes for performance with user filtering

---

## Implementation Priority

1. **Multi-User Word Isolation** - Critical security/data isolation issue
2. ~~**Rate Limiting for /add** - Critical for system stability~~ ✅ **COMPLETED**
3. **Study Reminders** - Major UX improvement
4. **Unprocessed Words Reporting** - User transparency
5. **Difficulty Button Improvements** - UX enhancement
6. **Fix Word Count Discrepancy** - Data integrity fix

## Success Metrics

- **Multi-User Isolation**: 100% data isolation between users
- ~~**Rate Limiting**: Zero concurrent `/add` operations per user~~ ✅ **ACHIEVED**
- **Reminders**: 30%+ increase in daily active users
- **Failed Words**: 100% transparency on processing failures
- **Button UX**: Improved user satisfaction with study interface

## Technical Considerations

- All features should maintain backward compatibility
- Database migrations must be incremental and reversible
- User settings should have sensible defaults
- Error handling must be comprehensive
- Performance impact should be minimal

---

## ✅ Completed Features

### 🚫 Rate Limiting for /add Command *(Completed: 2025-07-12)*
- **Implementation**: UserLockManager with 5-minute timeout, async cleanup
- **Integration**: Full bot_handler integration with try/finally guarantees
- **Testing**: 13 comprehensive tests covering all scenarios
- **Result**: Zero concurrent operations per user, improved system stability
- **Additional Fix**: Case-insensitive word detection (herr vs Herr issue)

---

*This document will be updated as features are implemented and new requirements are identified.*