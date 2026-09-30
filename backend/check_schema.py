"""全面检查数据库 schema 与模型定义的一致性"""
import sqlite3, os, sys, importlib, inspect

# 添加项目路径
sys.path.insert(0, os.path.dirname(__file__))

conn = sqlite3.connect("accounting.db")

# 获取所有表的列
cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [row[0] for row in cursor.fetchall()]

db_schema = {}
for table in tables:
    cursor = conn.execute(f"PRAGMA table_info({table})")
    db_schema[table] = [row[1] for row in cursor.fetchall()]

# 模型列映射
model_columns = {
    "users": ["username", "real_name", "password_hash", "role", "department", "email",
              "is_active", "last_login", "login_ip", "login_attempts", "locked_until",
              "two_factor_enabled", "totp_secret", "token_version", "id", "created_at", "updated_at"],
    "api_providers": ["id", "name", "base_url", "api_key", "is_active", "created_at", "updated_at"],
    "accounts": ["id", "account_code", "account_name", "parent_code", "account_type",
                 "balance_direction", "is_active", "book_id", "created_at", "updated_at"],
    "audit_logs": ["id", "user_id", "username", "action", "resource_type", "resource_id",
                   "detail", "ip_address", "created_at"],
    "user_api_keys": ["id", "user_id", "api_provider_id", "api_key", "is_active", "created_at", "updated_at"],
    "vouchers": ["id", "voucher_number", "voucher_date", "status", "summary", "total_debit",
                 "total_credit", "book_id", "created_by", "reviewed_by", "reviewed_at",
                 "created_at", "updated_at"],
    "voucher_items": ["id", "voucher_id", "account_code", "account_name", "summary",
                      "debit_amount", "credit_amount", "sort_order", "created_at", "updated_at"],
    "conversations": ["id", "user_id", "title", "model_preference", "book_id", "last_message_at",
                      "created_at", "updated_at"],
    "messages": ["id", "conversation_id", "role", "content", "token_count", "created_at"],
    "invoices": ["id", "type", "number", "date", "amount", "buyer", "seller", "details",
                 "raw_text", "image_path", "status", "book_id", "uploaded_by", "created_at", "updated_at"],
    "books": ["id", "name", "description", "fiscal_year_start", "fiscal_year_end", "currency",
              "is_default", "status", "created_by", "created_at", "updated_at"],
    "book_members": ["id", "book_id", "user_id", "role", "is_active", "joined_at", "created_at"],
    "ai_memories": ["id", "book_id", "memory_type", "content", "embedding", "importance",
                    "source", "expires_at", "created_at", "updated_at"],
    "conversation_memories": ["id", "conversation_id", "summary", "key_entities", "created_at"],
    "knowledge_docs": ["id", "title", "category", "file_path", "file_type", "file_size",
                       "chunk_count", "is_indexed", "uploaded_by", "version",
                       "previous_version_id", "is_archived", "source_url", "last_fetched_at",
                       "is_stale", "created_at", "updated_at"],
    "knowledge_update_logs": ["id", "doc_id", "action", "details", "performed_by", "created_at"],
    "api_key_usage_logs": ["id", "api_key_id", "user_id", "operation", "request_count",
                           "token_count", "created_at"],
    "voucher_templates": ["id", "name", "description", "category", "book_id", "created_by",
                          "created_at", "updated_at"],
    "voucher_template_items": ["id", "template_id", "account_code", "account_name", "summary",
                               "debit_formula", "credit_formula", "sort_order", "created_at", "updated_at"],
    "budgets": ["id", "book_id", "name", "category", "period_type", "period_start", "period_end",
                "amount", "used_amount", "alert_threshold", "status", "created_by", "created_at", "updated_at"],
    "budget_alerts": ["id", "budget_id", "alert_type", "message", "is_read", "created_at"],
    "budget_notes": ["id", "budget_id", "content", "created_by", "created_at", "updated_at"],
    "tax_records": ["id", "book_id", "tax_type", "period", "taxable_amount", "tax_rate",
                    "tax_amount", "paid_amount", "status", "created_by", "created_at", "updated_at"],
    "tax_deadlines": ["id", "book_id", "tax_type", "period", "deadline_date", "status",
                      "reminded", "created_at", "updated_at"],
    "tax_summaries": ["id", "book_id", "period", "total_tax", "total_paid", "total_unpaid",
                      "created_at", "updated_at"],
}

missing = []
for table, expected_cols in model_columns.items():
    if table in db_schema:
        actual_cols = db_schema[table]
        for col in expected_cols:
            if col not in actual_cols:
                missing.append(f"{table}.{col}")
                print(f"MISSING: {table}.{col}")

if missing:
    print(f"\nTotal missing columns: {len(missing)}")
    for m in missing:
        print(f"  {m}")
else:
    print("\nAll columns are in sync!")

conn.close()