# 导入所有模型类，确保 Alembic 能识别
from .base import BaseModel
from .user import User
from .book import Book, BookMember
from .api_key import ApiProvider, UserApiKey, ApiKeyUsageLog
from .voucher import Voucher, VoucherItem, Account
from .voucher_template import VoucherTemplate, VoucherTemplateItem
from .audit_log import AuditLog, AuditFieldChange
from .knowledge_doc import KnowledgeDoc
from .conversation import Conversation, Message
from .invoice import Invoice
from .ai_memory import AIMemory
from .conversation_memory import ConversationMemory
from .knowledge_update_log import KnowledgeUpdateLog
from .budget import Budget, BudgetAlert, BudgetNote
from .opening_balance import OpeningBalance
from .bank_statement import BankStatement
from .fixed_asset import FixedAsset, DepreciationRecord
from .tax import TaxRecord, TaxDeadline, TaxSummary
from .notification import Notification
from .archive_key import ArchiveKey
from .system_setting import SystemSetting
from .period_close import AccountingPeriod
from .currency import Currency, ExchangeRate
from .payroll import SalaryItem, SalaryRecord
from .reconciliation import Reconciliation