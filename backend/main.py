"""
企业财务智能助手 - FastAPI 应用入口
基于 LangChain + Ollama 的公司内部财务助手系统
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

from config.settings import settings
from database import engine, Base, async_session_maker
from models import *  # noqa: 确保所有模型被导入
from models.user import User
from auth.jwt_handler import JWTHandler

# ========== 日志配置 ==========
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


async def seed_default_admin():
    """创建默认管理员账号（如果不存在）"""
    async with async_session_maker() as session:
        result = await session.execute(select(User).where(User.username == "admin"))
        existing = result.scalar_one_or_none()
        if existing:
            logger.info("管理员账号已存在，跳过初始化")
            return

        admin = User(
            username="admin",
            real_name="系统管理员",
            password_hash=JWTHandler.hash_password("admin123"),
            role="admin",
            department="技术部",
            is_active=True,
        )
        session.add(admin)
        await session.commit()
        # logger.info("✅ 默认管理员账号已创建: admin / admin123")


async def seed_default_book():
    """创建默认账套并迁移现有数据（如果不存在）"""
    from models.book import Book, BookMember
    from models.voucher import Account, Voucher
    from models.invoice import Invoice
    from models.voucher_template import VoucherTemplate
    from models.tax import TaxRecord, TaxDeadline, TaxSummary
    from models.budget import Budget

    async with async_session_maker() as session:
        result = await session.execute(select(Book).where(Book.is_default == True))
        existing = result.scalar_one_or_none()
        if existing:
            logger.info("默认账套已存在，跳过初始化")
            return

        # 查找 admin 用户
        admin_result = await session.execute(select(User).where(User.username == "admin"))
        admin_user = admin_result.scalar_one_or_none()

        if admin_user is None:
            logger.warning("未找到管理员用户，跳过默认账套创建")
            return

        book = Book(
            name="默认账套",
            code="DEFAULT",
            company_name="默认公司",
            description="系统自动创建的默认账套",
            fiscal_year_start=1,
            fiscal_year_end=12,
            currency="CNY",
            decimal_places=2,
            status="active",
            is_default=True,
            created_by=admin_user.id,
        )
        session.add(book)
        await session.flush()

        # 为默认账套创建标准科目
        from api.book import STANDARD_ACCOUNTS
        for code, name, atype, direction in STANDARD_ACCOUNTS:
            session.add(Account(
                account_code=code,
                account_name=name,
                account_type=atype,
                balance_direction=direction,
                book_id=book.id,
                is_active=True,
            ))

        # 将所有现有管理员添加到默认账套
        user_result = await session.execute(select(User).where(User.is_active == True))
        users = user_result.scalars().all()
        for user in users:
            session.add(BookMember(
                book_id=book.id,
                user_id=user.id,
                role="admin" if user.role == "admin" else "viewer",
                is_active=True,
            ))

        # 迁移现有数据到默认账套
        try:
            # 迁移凭证
            voucher_result = await session.execute(
                select(Voucher).where(Voucher.book_id == None)
            )
            vouchers = voucher_result.scalars().all()
            for v in vouchers:
                v.book_id = book.id

            # 迁移科目（不含 book_id 的）
            account_result = await session.execute(
                select(Account).where(Account.book_id == None)
            )
            accounts = account_result.scalars().all()
            for acc in accounts:
                acc.book_id = book.id

            # 迁移发票
            invoice_result = await session.execute(
                select(Invoice).where(Invoice.book_id == None)
            )
            invoices = invoice_result.scalars().all()
            for inv in invoices:
                inv.book_id = book.id

            # 迁移凭证模板
            template_result = await session.execute(
                select(VoucherTemplate).where(VoucherTemplate.book_id == None)
            )
            templates = template_result.scalars().all()
            for t in templates:
                t.book_id = book.id

            # 迁移税务记录
            try:
                tax_result = await session.execute(
                    select(TaxRecord).where(TaxRecord.book_id == None)
                )
                for tr in tax_result.scalars().all():
                    tr.book_id = book.id
            except Exception:
                pass

            try:
                deadline_result = await session.execute(
                    select(TaxDeadline).where(TaxDeadline.book_id == None)
                )
                for td in deadline_result.scalars().all():
                    td.book_id = book.id
            except Exception:
                pass

            try:
                summary_result = await session.execute(
                    select(TaxSummary).where(TaxSummary.book_id == None)
                )
                for ts in summary_result.scalars().all():
                    ts.book_id = book.id
            except Exception:
                pass

            # 迁移预算
            try:
                budget_result = await session.execute(
                    select(Budget).where(Budget.book_id == None)
                )
                for b in budget_result.scalars().all():
                    b.book_id = book.id
            except Exception:
                pass
        except Exception as e:
            logger.warning(f"数据迁移过程中出现警告: {e}")

        await session.commit()
        logger.info(f"✅ 默认账套已创建: {book.name} ({book.code})，已迁移 {len(vouchers)} 条凭证, {len(accounts)} 条科目")


def _migrate_archive_keys(conn):
    """迁移：为 archive_keys 表添加 usb_serial_hash 列（SQLite 兼容）"""
    from sqlalchemy import text
    # 检查列是否存在
    result = conn.execute(text("PRAGMA table_info(archive_keys)"))
    columns = [row[1] for row in result.fetchall()]
    if "usb_serial_hash" not in columns:
        conn.execute(text("ALTER TABLE archive_keys ADD COLUMN usb_serial_hash VARCHAR(128)"))
        conn.commit()
        logger.info("✅ archive_keys 表已添加 usb_serial_hash 列")


def _migrate_users_avatar(conn):
    """迁移：为 users 表添加 avatar 列（SQLite 兼容）"""
    from sqlalchemy import text
    result = conn.execute(text("PRAGMA table_info(users)"))
    columns = [row[1] for row in result.fetchall()]
    if "avatar" not in columns:
        conn.execute(text("ALTER TABLE users ADD COLUMN avatar VARCHAR(500)"))
        conn.commit()
        logger.info("✅ users 表已添加 avatar 列")


def _migrate_account_types(conn):
    """迁移：将 accounts 表的 account_type 从中文字符串改为英文"""
    from sqlalchemy import text
    migrations = [
        ("资产", "asset"),
        ("负债", "liability"),
        ("权益", "equity"),
        ("成本", "cost"),
        ("损益", "expense"),
    ]
    changed = 0
    for old, new in migrations:
        result = conn.execute(
            text("UPDATE accounts SET account_type = :new WHERE account_type = :old"),
            {"new": new, "old": old},
        )
        changed += result.rowcount
    # 收入类科目（credit 方向）应改为 revenue
    revenue_codes = ("6001", "6051", "6101", "6111", "6301")
    for code in revenue_codes:
        result = conn.execute(
            text("UPDATE accounts SET account_type = 'revenue' WHERE account_code = :code AND account_type = 'expense'"),
            {"code": code},
        )
        changed += result.rowcount
    if changed:
        conn.commit()
        logger.info(f"✅ 已迁移 {changed} 个科目的 account_type: 中文 → 英文")


def _migrate_voucher_type(conn):
    """迁移：为 vouchers 表添加 voucher_type、cashier_reviewed 等列（SQLite 兼容）"""
    from sqlalchemy import text
    result = conn.execute(text("PRAGMA table_info(vouchers)"))
    columns = [row[1] for row in result.fetchall()]
    
    migrations = [
        ("voucher_type", "VARCHAR(10) NOT NULL DEFAULT '记'"),
        ("cashier_reviewed", "BOOLEAN NOT NULL DEFAULT 0"),
        ("cashier_reviewed_by", "INTEGER REFERENCES users(id)"),
        ("cashier_reviewed_at", "DATETIME"),
    ]
    
    for col_name, col_def in migrations:
        if col_name not in columns:
            conn.execute(text(f"ALTER TABLE vouchers ADD COLUMN {col_name} {col_def}"))
            logger.info(f"✅ vouchers 表已添加 {col_name} 列")
    conn.commit()


def _migrate_voucher_items(conn):
    """迁移：为 voucher_items 表添加 cash_flow_tag、auxiliary_accounting 列"""
    from sqlalchemy import text
    result = conn.execute(text("PRAGMA table_info(voucher_items)"))
    columns = [row[1] for row in result.fetchall()]
    
    migrations = [
        ("cash_flow_tag", "VARCHAR(50)"),
        ("auxiliary_accounting", "TEXT"),
    ]
    
    for col_name, col_def in migrations:
        if col_name not in columns:
            conn.execute(text(f"ALTER TABLE voucher_items ADD COLUMN {col_name} {col_def}"))
            logger.info(f"✅ voucher_items 表已添加 {col_name} 列")
    conn.commit()


def _migrate_accounting_periods(conn):
    """迁移：创建 accounting_periods 表（如果不存在）"""
    from sqlalchemy import text
    # 检查表是否存在
    result = conn.execute(text(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='accounting_periods'"
    ))
    if result.fetchone() is None:
        conn.execute(text("""
            CREATE TABLE accounting_periods (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                book_id INTEGER NOT NULL REFERENCES books(id),
                period_year INTEGER NOT NULL,
                period_month INTEGER NOT NULL,
                status VARCHAR(20) NOT NULL DEFAULT 'open',
                closed_at DATETIME,
                closed_by INTEGER REFERENCES users(id),
                reopened_at DATETIME,
                reopened_by INTEGER REFERENCES users(id),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """))
        conn.commit()
        logger.info("✅ accounting_periods 表已创建")


def _migrate_reconciliation(conn):
    """迁移：创建 reconciliations 表（如果不存在）"""
    from sqlalchemy import text
    result = conn.execute(text(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='reconciliations'"
    ))
    if result.fetchone() is None:
        conn.execute(text("""
            CREATE TABLE reconciliations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reconciliation_type VARCHAR(20) NOT NULL,
                party_type VARCHAR(20) NOT NULL,
                party_name VARCHAR(200) NOT NULL,
                party_code VARCHAR(50),
                voucher_id INTEGER REFERENCES vouchers(id),
                voucher_item_id INTEGER REFERENCES voucher_items(id),
                invoice_no VARCHAR(100),
                amount NUMERIC(15, 2) NOT NULL,
                reconciled_amount NUMERIC(15, 2) DEFAULT 0,
                remaining_amount NUMERIC(15, 2) DEFAULT 0,
                due_date DATE,
                status VARCHAR(20) DEFAULT 'pending',
                notes TEXT,
                book_id INTEGER REFERENCES books(id),
                created_by INTEGER NOT NULL REFERENCES users(id),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """))
        conn.commit()
        logger.info("✅ reconciliations 表已创建")


def _migrate_currency(conn):
    """迁移：创建 currencies 和 exchange_rates 表（如果不存在）"""
    from sqlalchemy import text
    result = conn.execute(text(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='currencies'"
    ))
    if result.fetchone() is None:
        conn.execute(text("""
            CREATE TABLE currencies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code VARCHAR(10) NOT NULL UNIQUE,
                name VARCHAR(50) NOT NULL,
                symbol VARCHAR(10) NOT NULL,
                is_base BOOLEAN DEFAULT 0,
                status VARCHAR(20) DEFAULT 'active',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """))
        # 插入默认币种
        conn.execute(text("INSERT INTO currencies (code, name, symbol, is_base, status) VALUES ('CNY', '人民币', '¥', 1, 'active')"))
        conn.commit()
        logger.info("✅ currencies 表已创建")

    result = conn.execute(text(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='exchange_rates'"
    ))
    if result.fetchone() is None:
        conn.execute(text("""
            CREATE TABLE exchange_rates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                currency_code VARCHAR(10) NOT NULL REFERENCES currencies(code),
                rate_date DATE NOT NULL,
                rate NUMERIC(18, 8) NOT NULL,
                rate_type VARCHAR(20) DEFAULT 'middle',
                book_id INTEGER REFERENCES books(id),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """))
        conn.commit()
        logger.info("✅ exchange_rates 表已创建")


def _migrate_payroll(conn):
    """迁移：创建 salary_items 和 salary_records 表（如果不存在）"""
    from sqlalchemy import text
    result = conn.execute(text(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='salary_items'"
    ))
    if result.fetchone() is None:
        conn.execute(text("""
            CREATE TABLE salary_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR(100) NOT NULL,
                item_type VARCHAR(20) NOT NULL,
                formula TEXT,
                sort_order INTEGER DEFAULT 0,
                book_id INTEGER REFERENCES books(id),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """))
        conn.commit()
        logger.info("✅ salary_items 表已创建")

    result = conn.execute(text(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='salary_records'"
    ))
    if result.fetchone() is None:
        conn.execute(text("""
            CREATE TABLE salary_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_name VARCHAR(100) NOT NULL,
                employee_code VARCHAR(50),
                period VARCHAR(7) NOT NULL,
                salary_data JSON NOT NULL DEFAULT '{}',
                total_income NUMERIC(15, 2) DEFAULT 0,
                total_deduction NUMERIC(15, 2) DEFAULT 0,
                net_salary NUMERIC(15, 2) DEFAULT 0,
                status VARCHAR(20) DEFAULT 'draft',
                book_id INTEGER REFERENCES books(id),
                created_by INTEGER NOT NULL REFERENCES users(id),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """))
        conn.commit()
        logger.info("✅ salary_records 表已创建")


async def seed_default_templates():
    """创建默认凭证模板（如果不存在）"""
    from models.voucher_template import VoucherTemplate, VoucherTemplateItem
    from models.user import User

    async with async_session_maker() as session:
        result = await session.execute(select(VoucherTemplate).where(VoucherTemplate.is_default == True))
        existing = result.scalars().all()
        if existing:
            logger.info(f"默认凭证模板已存在 ({len(existing)} 个)，跳过初始化")
            return

        admin_result = await session.execute(select(User).where(User.username == "admin"))
        admin_user = admin_result.scalar_one_or_none()
        if not admin_user:
            return

        templates = [
            {
                "name": "采购付款",
                "description": "采购商品/原材料付款",
                "category": "支出",
                "items": [
                    {"account_code": "1401", "account_name": "材料采购", "description": "采购材料", "debit_amount": 10000, "credit_amount": 0, "sort_order": 1},
                    {"account_code": "2221", "account_name": "应交税费-应交增值税(进项税额)", "description": "进项税额", "debit_amount": 1300, "credit_amount": 0, "sort_order": 2},
                    {"account_code": "1002", "account_name": "银行存款", "description": "支付货款", "debit_amount": 0, "credit_amount": 11300, "sort_order": 3},
                ],
            },
            {
                "name": "销售收入",
                "description": "销售商品确认收入",
                "category": "收入",
                "items": [
                    {"account_code": "1002", "account_name": "银行存款", "description": "收到货款", "debit_amount": 11300, "credit_amount": 0, "sort_order": 1},
                    {"account_code": "6001", "account_name": "主营业务收入", "description": "销售收入", "debit_amount": 0, "credit_amount": 10000, "sort_order": 2},
                    {"account_code": "2221", "account_name": "应交税费-应交增值税(销项税额)", "description": "销项税额", "debit_amount": 0, "credit_amount": 1300, "sort_order": 3},
                ],
            },
            {
                "name": "内部转账",
                "description": "银行账户间转账",
                "category": "转账",
                "items": [
                    {"account_code": "1002", "account_name": "银行存款", "description": "转入", "debit_amount": 50000, "credit_amount": 0, "sort_order": 1},
                    {"account_code": "1002", "account_name": "银行存款", "description": "转出", "debit_amount": 0, "credit_amount": 50000, "sort_order": 2},
                ],
            },
            {
                "name": "费用报销",
                "description": "员工费用报销",
                "category": "支出",
                "items": [
                    {"account_code": "6602", "account_name": "管理费用", "description": "报销费用", "debit_amount": 2000, "credit_amount": 0, "sort_order": 1},
                    {"account_code": "1001", "account_name": "库存现金", "description": "支付报销款", "debit_amount": 0, "credit_amount": 2000, "sort_order": 2},
                ],
            },
            {
                "name": "计提工资",
                "description": "月末计提工资",
                "category": "其他",
                "items": [
                    {"account_code": "6602", "account_name": "管理费用-工资", "description": "管理部门工资", "debit_amount": 30000, "credit_amount": 0, "sort_order": 1},
                    {"account_code": "6401", "account_name": "主营业务成本-工资", "description": "生产部门工资", "debit_amount": 50000, "credit_amount": 0, "sort_order": 2},
                    {"account_code": "2211", "account_name": "应付职工薪酬", "description": "应付工资", "debit_amount": 0, "credit_amount": 80000, "sort_order": 3},
                ],
            },
            {
                "name": "固定资产折旧",
                "description": "计提本月折旧",
                "category": "其他",
                "items": [
                    {"account_code": "6602", "account_name": "管理费用-折旧费", "description": "计提折旧", "debit_amount": 5000, "credit_amount": 0, "sort_order": 1},
                    {"account_code": "1602", "account_name": "累计折旧", "description": "累计折旧", "debit_amount": 0, "credit_amount": 5000, "sort_order": 2},
                ],
            },
        ]

        for tmpl in templates:
            t = VoucherTemplate(
                name=tmpl["name"],
                description=tmpl["description"],
                category=tmpl["category"],
                is_default=True,
                created_by=admin_user.id,
            )
            session.add(t)
            await session.flush()

            for item in tmpl["items"]:
                ti = VoucherTemplateItem(
                    template_id=t.id,
                    account_code=item["account_code"],
                    account_name=item["account_name"],
                    description=item["description"],
                    debit_amount=item["debit_amount"],
                    credit_amount=item["credit_amount"],
                    sort_order=item["sort_order"],
                )
                session.add(ti)

        await session.commit()
        logger.info(f"✅ 已创建 {len(templates)} 个默认凭证模板")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info("🚀 企业财务智能助手启动中...")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("✅ 数据库表创建/检查完成")

        # 迁移：为 archive_keys 表添加 usb_serial_hash 列（如果不存在）
        async with engine.begin() as conn:
            await conn.run_sync(_migrate_archive_keys)
        # 迁移：为 users 表添加 avatar 列（如果不存在）
        async with engine.begin() as conn:
            await conn.run_sync(_migrate_users_avatar)
        # 迁移：将 accounts 表的 account_type 从中文字符串改为英文
        async with engine.begin() as conn:
            await conn.run_sync(_migrate_account_types)
        # 迁移：为 vouchers 表添加 voucher_type、cashier_reviewed 等列
        async with engine.begin() as conn:
            await conn.run_sync(_migrate_voucher_type)
        # 迁移：为 voucher_items 表添加 cash_flow_tag、auxiliary_accounting 列
        async with engine.begin() as conn:
            await conn.run_sync(_migrate_voucher_items)
        # 迁移：创建 accounting_periods 表
        async with engine.begin() as conn:
            await conn.run_sync(_migrate_accounting_periods)
        # 迁移：创建 reconciliations 表
        async with engine.begin() as conn:
            await conn.run_sync(_migrate_reconciliation)
        # 迁移：创建 currencies 和 exchange_rates 表
        async with engine.begin() as conn:
            await conn.run_sync(_migrate_currency)
        # 迁移：创建 salary_items 和 salary_records 表
        async with engine.begin() as conn:
            await conn.run_sync(_migrate_payroll)
        logger.info("✅ 数据库迁移检查完成")

        # 初始化默认管理员账号
        await seed_default_admin()

        # 初始化默认账套并迁移数据
        await seed_default_book()

        # 初始化默认凭证模板
        await seed_default_templates()
    except Exception as e:
        logger.warning(f"⚠️  数据库初始化警告: {e}")
        logger.warning("请确保数据库已启动且 DATABASE_URL 配置正确")

    # 启动知识库自动更新调度器（后台任务）
    try:
        from services.knowledge_scheduler import startup_scheduler
        await startup_scheduler(interval_hours=24)
        logger.info("✅ 知识库自动更新调度器已启动")
    except Exception as e:
        logger.warning(f"⚠️  知识库调度器启动失败: {e}")

    # 自动计提当月折旧（后台任务）
    try:
        from datetime import datetime
        from models.book import Book
        from api.fixed_asset import _run_depreciation_for_book
        current_month = datetime.now().strftime("%Y-%m")
        async with async_session_maker() as session:
            result = await session.execute(select(Book).where(Book.status == "active"))
            active_books = result.scalars().all()
            for book in active_books:
                try:
                    dep_result = await _run_depreciation_for_book(
                        book_id=book.id,
                        period=current_month,
                        current_user_id=1,  # 系统自动执行，使用 admin
                        db=session,
                        skip_existing=True,
                    )
                    if dep_result.get("depreciated", 0) > 0:
                        logger.info(
                            f"✅ 自动计提折旧完成: 账套={book.name}, 期间={current_month}, "
                            f"计提{dep_result['depreciated']}项, 跳过{dep_result['skipped']}项"
                        )
                except Exception as e:
                    logger.warning(f"⚠️  账套 {book.name} 自动计提折旧失败: {e}")
        logger.info("✅ 自动计提折旧检查完成")
    except Exception as e:
        logger.warning(f"⚠️  自动计提折旧失败: {e}")

    yield

    # 关闭时：释放资源
    logger.info("🛑 应用正在关闭...")
    await engine.dispose()
    logger.info("✅ 数据库连接已释放")


# ========== 创建 FastAPI 应用 ==========
app = FastAPI(
    title="企业财务智能助手",
    description="基于 LangChain + Ollama 的公司内部财务助手系统，提供智能记账、报表分析、税务计算等功能",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    redirect_slashes=False,  # 禁用尾斜杠重定向，避免307丢失Authorization头
)

# ========== CORS 中间件 ==========
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ========== 审计日志中间件 ==========
from auth.middleware import AuditLogMiddleware
app.add_middleware(AuditLogMiddleware)

# ========== 上传目录挂载 ==========
import os
UPLOADS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
os.makedirs(os.path.join(UPLOADS_DIR, "avatars"), exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")

# ========== 注册 API 路由 ==========
from api.auth import router as auth_router
from api.users import router as users_router
from api.api_key import router as api_key_router
from api.chat import router as chat_router
from api.voucher import router as voucher_router
from api.voucher_template import router as voucher_template_router
from api.report import router as report_router
from api.knowledge import router as knowledge_router
from api.conversation import router as conversation_router
from api.invoice import router as invoice_router
from api.audit import router as audit_router
from api.import_export import router as import_export_router
from api.dashboard import router as dashboard_router
from api.memory import router as memory_router
from api.knowledge_scheduler import router as knowledge_scheduler_router
from api.tax import router as tax_router
from api.budget import router as budget_router
from api.book import router as book_router
from api.bank import router as bank_router
from api.fixed_asset import router as fixed_asset_router
from api.notification import router as notification_router
from api.suggestion import router as suggestion_router
from api.anomaly import router as anomaly_router
from api.archive_key import router as archive_key_router
from api.system_setting import router as system_setting_router
from api.period_close import router as period_close_router
from api.reconciliation import router as reconciliation_router
from api.backup import router as backup_router
from api.currency import router as currency_router
from api.payroll import router as payroll_router

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(api_key_router)
app.include_router(chat_router)
app.include_router(voucher_router)
app.include_router(voucher_template_router)
app.include_router(report_router)
app.include_router(knowledge_router)
app.include_router(conversation_router)
app.include_router(invoice_router)
app.include_router(audit_router)
app.include_router(import_export_router)
app.include_router(dashboard_router)
app.include_router(memory_router)
app.include_router(knowledge_scheduler_router)
app.include_router(budget_router)
app.include_router(tax_router)
app.include_router(book_router)
app.include_router(bank_router)
app.include_router(fixed_asset_router)
app.include_router(notification_router)
app.include_router(suggestion_router)
app.include_router(anomaly_router)
app.include_router(archive_key_router)
app.include_router(system_setting_router)
app.include_router(period_close_router)
app.include_router(reconciliation_router)
app.include_router(backup_router)
app.include_router(currency_router)
app.include_router(payroll_router)


# ========== 根路径 ==========
@app.get("/", tags=["系统"])
async def root():
    """API 根路径"""
    return {
        "message": "企业财务智能助手 API",
        "version": "1.0.0",
        "docs": "/docs",
    }


@app.get("/health", tags=["系统"])
async def health_check():
    """健康检查端点"""
    return {"status": "healthy", "version": "1.0.0"}


# ========== 启动入口 ==========
if __name__ == "__main__":
    import uvicorn

    logger.info("启动企业财务智能助手服务...")
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_excludes=["*.db", "docs/*", "__pycache__/*"],
        log_level="info",
    )