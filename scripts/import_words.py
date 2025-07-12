#!/usr/bin/env python3
"""
Import words data from JSON to new database schema with telegram_id
"""

import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path


def import_words_data(json_path: str, db_path: str) -> bool:
    """Import words and learning progress data from JSON to new database schema"""
    try:
        # Load JSON data
        print(f"📖 Loading data from {json_path}")
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        words = data.get('words', [])
        users = data.get('users', [])
        learning_progress = data.get('learning_progress', [])
        review_history = data.get('review_history', [])
        
        print(f"  📝 Loaded {len(words)} words")
        print(f"  👥 Loaded {len(users)} users")
        print(f"  📊 Loaded {len(learning_progress)} learning progress records")
        print(f"  📈 Loaded {len(review_history)} review history records")
        
        # Connect to new database
        print(f"🔗 Connecting to database {db_path}")
        conn = sqlite3.connect(db_path)
        
        # Initialize new schema (create tables with telegram_id as PK)
        print("🏗️  Initializing database schema...")
        
        # Import the database connection class to initialize schema
        import sys
        import os
        sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        from src.core.database.connection import DatabaseConnection
        db_manager = DatabaseConnection(db_path)
        db_manager.init_database()
        print("  ✅ Database schema initialized")
        
        # Import users (convert to new schema with telegram_id as PK)
        print("👥 Importing users...")
        user_count = 0
        for user in users:
            try:
                conn.execute("""
                    INSERT OR REPLACE INTO users 
                    (telegram_id, first_name, last_name, username, created_at, updated_at, is_active)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    user['telegram_id'],
                    user['first_name'],
                    user.get('last_name'),
                    user.get('username'),
                    user.get('created_at', datetime.now().isoformat()),
                    user.get('updated_at', datetime.now().isoformat()),
                    user.get('is_active', 1)
                ))
                user_count += 1
            except Exception as e:
                print(f"  ⚠️  Failed to import user {user.get('telegram_id', 'unknown')}: {e}")
        
        print(f"  ✅ Imported {user_count} users")
        
        # Import words
        print("📝 Importing words...")
        word_count = 0
        for word in words:
            try:
                conn.execute("""
                    INSERT OR REPLACE INTO words 
                    (id, lemma, part_of_speech, article, translation, example, 
                     additional_forms, confidence, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    word['id'],
                    word['lemma'],
                    word['part_of_speech'],
                    word.get('article'),
                    word['translation'],
                    word['example'],
                    word.get('additional_forms'),
                    word.get('confidence', 1.0),
                    word.get('created_at', datetime.now().isoformat()),
                    word.get('updated_at', datetime.now().isoformat())
                ))
                word_count += 1
            except Exception as e:
                print(f"  ⚠️  Failed to import word {word.get('lemma', 'unknown')}: {e}")
        
        print(f"  ✅ Imported {word_count} words")
        
        # Import learning progress (convert user_id to telegram_id)
        print("📊 Importing learning progress...")
        progress_count = 0
        for progress in learning_progress:
            try:
                conn.execute("""
                    INSERT OR REPLACE INTO learning_progress 
                    (telegram_id, word_id, repetitions, easiness_factor, interval_days,
                     next_review_date, last_reviewed, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    progress['telegram_id'],  # Use telegram_id from JOIN
                    progress['word_id'],
                    progress['repetitions'],
                    progress['easiness_factor'],
                    progress['interval_days'],
                    progress.get('next_review_date'),
                    progress.get('last_reviewed'),
                    progress.get('created_at', datetime.now().isoformat()),
                    progress.get('updated_at', datetime.now().isoformat())
                ))
                progress_count += 1
            except Exception as e:
                print(f"  ⚠️  Failed to import progress record: {e}")
        
        print(f"  ✅ Imported {progress_count} learning progress records")
        
        # Import review history (convert user_id to telegram_id)
        print("📈 Importing review history...")
        history_count = 0
        for review in review_history:
            try:
                conn.execute("""
                    INSERT OR REPLACE INTO review_history 
                    (telegram_id, word_id, rating, response_time_ms, reviewed_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    review['telegram_id'],  # Use telegram_id from JOIN
                    review['word_id'],
                    review['rating'],
                    review.get('response_time_ms', 0),
                    review.get('reviewed_at', datetime.now().isoformat())
                ))
                history_count += 1
            except Exception as e:
                print(f"  ⚠️  Failed to import review record: {e}")
        
        print(f"  ✅ Imported {history_count} review history records")
        
        # Commit all changes
        conn.commit()
        conn.close()
        
        print(f"✅ Successfully imported data to {db_path}")
        print(f"📊 Import summary:")
        print(f"   • Users: {user_count}")
        print(f"   • Words: {word_count}")
        print(f"   • Learning progress: {progress_count}")
        print(f"   • Review history: {history_count}")
        
        return True
        
    except Exception as e:
        print(f"❌ Import failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main import function"""
    if len(sys.argv) != 3:
        print("Usage: python import_words.py <input_json_path> <database_path>")
        print("Example: python import_words.py data/bot_words_prod.json data/bot_new.db")
        sys.exit(1)
    
    json_path = sys.argv[1]
    db_path = sys.argv[2]
    
    # Check if JSON file exists
    if not Path(json_path).exists():
        print(f"❌ JSON file not found: {json_path}")
        sys.exit(1)
    
    print(f"🚀 Starting import from {json_path} to {db_path}")
    
    if import_words_data(json_path, db_path):
        print("🎉 Import completed successfully!")
        sys.exit(0)
    else:
        print("💥 Import failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()