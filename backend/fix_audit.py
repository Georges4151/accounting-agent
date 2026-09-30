"""补充修复 audit_logs 缺失列"""
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

add_col("audit_logs", "user_agent", "VARCHAR(255)")
add_col("audit_logs", "status", "VARCHAR(10) DEFAULT 'success'")
add_col("audit_logs", "operation_category", "VARCHAR(50)")
add_col("audit_logs", "affected_resource_id", "INTEGER")
add_col("audit_logs", "request_body", "TEXT")
add_col("audit_logs", "response_status", "INTEGER")

conn.commit()
conn.close()
print("Done")