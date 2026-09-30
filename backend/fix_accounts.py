"""Recreate accounts table without UNIQUE constraint on account_code"""
import sqlite3

conn = sqlite3.connect("accounting.db")

# 1. Create new table without UNIQUE constraint
conn.execute("""
CREATE TABLE accounts_new (
    account_code VARCHAR(50) NOT NULL,
    account_name VARCHAR(100) NOT NULL,
    account_type VARCHAR(50) NOT NULL,
    parent_code VARCHAR(50),
    is_active BOOLEAN NOT NULL,
    balance_direction VARCHAR(10) NOT NULL,
    id INTEGER NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    book_id INTEGER,
    PRIMARY KEY (id)
)
""")

# 2. Copy data
conn.execute("INSERT INTO accounts_new SELECT * FROM accounts")

# 3. Drop old table
conn.execute("DROP TABLE accounts")

# 4. Rename new table
conn.execute("ALTER TABLE accounts_new RENAME TO accounts")

conn.commit()
conn.close()
print("Done - accounts table recreated without UNIQUE constraint")