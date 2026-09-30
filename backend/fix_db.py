import sqlite3
conn = sqlite3.connect("accounting.db")

def add_col(table, col, col_type):
    cursor = conn.execute(f"PRAGMA table_info({table})")
    cols = [row[1] for row in cursor.fetchall()]
    if col not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}")
        print(f"Added {table}.{col}")
    else:
        print(f"Skip {table}.{col} (exists)")

# conversations
add_col("conversations", "summary", "TEXT")
add_col("conversations", "topic_tags", "VARCHAR(500)")
add_col("conversations", "memory_keywords", "TEXT")
add_col("conversations", "memory_summary", "TEXT")
add_col("conversations", "last_accessed", "DATETIME")

# Check for voucher issues
cursor = conn.execute("PRAGMA table_info(vouchers)")
cols = [row[1] for row in cursor.fetchall()]
print("\nvouchers columns:", cols)

conn.commit()
conn.close()
print("Done")