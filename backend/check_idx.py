import sqlite3
conn = sqlite3.connect("accounting.db")
# Drop the UNIQUE constraint on account_code
# In SQLite, UNIQUE constraints are auto-named indexes
# We need to find and drop the index
cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='accounts'")
indexes = [row[0] for row in cursor.fetchall()]
print("Indexes:", indexes)

# The unique constraint index is auto-named sqlite_autoindex_accounts_1
# Let's try to drop it by recreating the table
# But first, let's just try to drop the index
try:
    conn.execute("DROP INDEX IF EXISTS sqlite_autoindex_accounts_1")
    print("Dropped unique index")
except Exception as e:
    print(f"Drop index error: {e}")

# Alternative: recreate table without UNIQUE constraint
conn.commit()
conn.close()