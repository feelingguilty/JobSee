import sqlite3

def upgrade_db():
    conn = sqlite3.connect('jobsee.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute("ALTER TABLE jobs ADD COLUMN match_score INTEGER;")
        print("✅ Added match_score column.")
    except sqlite3.OperationalError as e:
        print(f"Column match_score might already exist: {e}")

    try:
        cursor.execute("ALTER TABLE jobs ADD COLUMN match_reason TEXT;")
        print("✅ Added match_reason column.")
    except sqlite3.OperationalError as e:
        print(f"Column match_reason might already exist: {e}")

    conn.commit()
    conn.close()

if __name__ == "__main__":
    upgrade_db()
