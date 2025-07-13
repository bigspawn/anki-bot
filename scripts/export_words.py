#!/usr/bin/env python3
"""
Export words data from production database to JSON
"""

import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path


def export_words_data(db_path: str, output_path: str) -> bool:
    """Export all words and learning progress data to JSON"""
    try:
        # Connect to database
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row  # Return rows as dictionaries
        
        print(f"📖 Exporting words data from {db_path}")
        
        # Export words
        cursor = conn.execute("SELECT * FROM words ORDER BY id")
        words = [dict(row) for row in cursor.fetchall()]
        print(f"  📝 Found {len(words)} words")
        
        # Export users (current schema uses telegram_id as PK)
        cursor = conn.execute("SELECT * FROM users ORDER BY telegram_id")
        users = [dict(row) for row in cursor.fetchall()]
        print(f"  👥 Found {len(users)} users")
        
        # Export learning progress (current schema uses telegram_id)
        cursor = conn.execute("""
            SELECT * FROM learning_progress 
            ORDER BY id
        """)
        learning_progress = [dict(row) for row in cursor.fetchall()]
        print(f"  📊 Found {len(learning_progress)} learning progress records")
        
        # Export review history (current schema uses telegram_id)
        cursor = conn.execute("""
            SELECT * FROM review_history 
            ORDER BY id
        """)
        review_history = [dict(row) for row in cursor.fetchall()]
        print(f"  📈 Found {len(review_history)} review history records")
        
        # Create export data structure
        export_data = {
            "export_info": {
                "exported_at": datetime.now().isoformat(),
                "database_path": db_path,
                "script_version": "2.0",
                "schema_version": "telegram_id_only"
            },
            "words": words,
            "users": users,
            "learning_progress": learning_progress,
            "review_history": review_history,
            "statistics": {
                "total_words": len(words),
                "total_users": len(users),
                "total_progress_records": len(learning_progress),
                "total_review_records": len(review_history)
            }
        }
        
        # Save to JSON file
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False, default=str)
        
        print(f"✅ Successfully exported data to {output_path}")
        print(f"📊 Export summary:")
        print(f"   • Words: {len(words)}")
        print(f"   • Users: {len(users)}")
        print(f"   • Learning progress: {len(learning_progress)}")
        print(f"   • Review history: {len(review_history)}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Export failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main export function"""
    if len(sys.argv) != 3:
        print("Usage: python export_words.py <database_path> <output_json_path>")
        print("Example: python export_words.py data/bot_prod.db data/bot_words_prod.json")
        sys.exit(1)
    
    db_path = sys.argv[1]
    output_path = sys.argv[2]
    
    # Check if database exists
    if not Path(db_path).exists():
        print(f"❌ Database file not found: {db_path}")
        sys.exit(1)
    
    print(f"🚀 Starting export from {db_path} to {output_path}")
    
    if export_words_data(db_path, output_path):
        print("🎉 Export completed successfully!")
        sys.exit(0)
    else:
        print("💥 Export failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()