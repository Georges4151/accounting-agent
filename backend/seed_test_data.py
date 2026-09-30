"""生成测试数据，用于测试图表和统计功能"""
import asyncio
import random
from datetime import date, timedelta

from database import async_session_maker
from models.voucher import Account, Voucher, VoucherItem
from models.book import Book
from sqlalchemy import select, update, delete


# 中文 → 英文 account_type 映射
TYPE_MIGRATION = {
    "资产": "asset",
    "负债": "liability",
    "权益": "equity",
    "成本": "cost",
    "损益": "expense",  # 默认 expense，credit 方向的收入类需要单独处理
}

# 收入类科目编码（credit 方向，应归为 revenue）
REVENUE_CODES = {"6001", "6051", "6101", "6111", "6301"}


# 各月收入数据（模拟一家公司1-8月的业务）
MONTHLY_DATA = [
    # (月份, 主营业务收入, 其他业务收入, 销售费用, 管理费用, 财务费用, 主营业务成本, 工资)
    ("2026-01", 85000, 3000, 12000, 18000, 1500, 42000, 35000),
    ("2026-02", 72000, 2500, 10500, 16500, 1300, 36000, 35000),
    ("2026-03", 98000, 4000, 15000, 20000, 1800, 50000, 38000),
    ("2026-04", 105000, 5000, 16000, 22000, 2000, 53000, 38000),
    ("2026-05", 112000, 5500, 17000, 23000, 2100, 56000, 40000),
    ("2026-06", 125000, 6000, 18500, 25000, 2300, 62000, 40000),
    ("2026-07", 138000, 6500, 20000, 27000, 2500, 68000, 42000),
    ("2026-08", 150000, 7000, 22000, 29000, 2700, 75000, 42000),
]

VOUCHER_NO_COUNTER = 1000


def _next_voucher_no():
    global VOUCHER_NO_COUNTER
    VOUCHER_NO_COUNTER += 1
    return f"PZ-{VOUCHER_NO_COUNTER}"


async def seed_test_data():
    async with async_session_maker() as db:
        # 1. 获取第一个活跃账套
        book_result = await db.execute(
            select(Book).where(Book.status == "active").limit(1)
        )
        book = book_result.scalar_one_or_none()
        if not book:
            print("❌ 未找到活跃账套，请先创建账套")
            return

        # 获取管理员用户
        from models.user import User
        user_result = await db.execute(
            select(User).where(User.role == "admin").limit(1)
        )
        admin_user = user_result.scalar_one_or_none()
        if not admin_user:
            print("❌ 未找到管理员用户")
            return

        book_id = book.id
        user_id = admin_user.id

        # 2. 迁移所有现有科目 account_type 从中文到英文
        accounts_result = await db.execute(select(Account))
        all_accounts = accounts_result.scalars().all()
        migrated = 0
        for acc in all_accounts:
            if acc.account_type in TYPE_MIGRATION:
                new_type = TYPE_MIGRATION[acc.account_type]
                if acc.account_code in REVENUE_CODES:
                    new_type = "revenue"
                acc.account_type = new_type
                migrated += 1
        if migrated > 0:
            await db.flush()
            print(f"🔄 已迁移 {migrated} 个科目的 account_type: 中文 → 英文")

        # 3. 检查并初始化科目
        result = await db.execute(
            select(Account).where(Account.book_id == book_id).limit(1)
        )
        if not result.scalar_one_or_none():
            print("📋 当前账套无科目，初始化标准科目...")
            from seed_accounts import STANDARD_ACCOUNTS
            for code, name, atype, direction in STANDARD_ACCOUNTS:
                db.add(Account(
                    account_code=code,
                    account_name=name,
                    account_type=atype,
                    balance_direction=direction,
                    is_active=True,
                    book_id=book_id,
                ))
            await db.flush()
            print(f"✅ 已创建 {len(STANDARD_ACCOUNTS)} 个科目")

        # 4. 删除旧的测试凭证并重新生成
        await db.execute(
            delete(VoucherItem).where(
                VoucherItem.voucher_id.in_(
                    select(Voucher.id).where(Voucher.book_id == book_id)
                )
            )
        )
        await db.execute(
            delete(Voucher).where(Voucher.book_id == book_id)
        )
        await db.flush()
        print(f"🗑️ 已清理旧测试凭证")

        print(f"📊 开始生成测试数据 (账套: {book.name}, 用户: {admin_user.username})")

        total_vouchers = 0

        for month_data in MONTHLY_DATA:
            month_str, revenue, other_revenue, selling_exp, admin_exp, fin_exp, cost, salary = month_data
            month_date = date.fromisoformat(month_str + "-01")

            # 获取当月随机天数
            days_in_month = [d for d in range(1, 29)]
            random.shuffle(days_in_month)

            def random_date():
                day = days_in_month.pop()
                return date(month_date.year, month_date.month, min(day, 28))

            # --- 凭证1：主营业务收入 ---
            v1 = Voucher(
                voucher_no=_next_voucher_no(),
                voucher_date=random_date(),
                summary=f"{month_date.month}月主营业务收入",
                status="reviewed",
                book_id=book_id,
                created_by=user_id,
            )
            db.add(v1)
            await db.flush()
            db.add(VoucherItem(voucher_id=v1.id, account_code="1002", account_name="银行存款", description="销售收款", debit_amount=revenue, credit_amount=0))
            db.add(VoucherItem(voucher_id=v1.id, account_code="6001", account_name="主营业务收入", description="销售收入", debit_amount=0, credit_amount=revenue))
            total_vouchers += 1

            # --- 凭证2：其他业务收入 ---
            v2 = Voucher(
                voucher_no=_next_voucher_no(),
                voucher_date=random_date(),
                summary=f"{month_date.month}月其他业务收入",
                status="reviewed",
                book_id=book_id,
                created_by=user_id,
            )
            db.add(v2)
            await db.flush()
            db.add(VoucherItem(voucher_id=v2.id, account_code="1002", account_name="银行存款", description="其他收入", debit_amount=other_revenue, credit_amount=0))
            db.add(VoucherItem(voucher_id=v2.id, account_code="6051", account_name="其他业务收入", description="其他业务收入", debit_amount=0, credit_amount=other_revenue))
            total_vouchers += 1

            # --- 凭证3：主营业务成本 ---
            v3 = Voucher(
                voucher_no=_next_voucher_no(),
                voucher_date=random_date(),
                summary=f"{month_date.month}月主营业务成本",
                status="reviewed",
                book_id=book_id,
                created_by=user_id,
            )
            db.add(v3)
            await db.flush()
            db.add(VoucherItem(voucher_id=v3.id, account_code="6401", account_name="主营业务成本", description="销售成本结转", debit_amount=cost, credit_amount=0))
            db.add(VoucherItem(voucher_id=v3.id, account_code="1405", account_name="库存商品", description="结转销售成本", debit_amount=0, credit_amount=cost))
            total_vouchers += 1

            # --- 凭证4：销售费用 ---
            v4 = Voucher(
                voucher_no=_next_voucher_no(),
                voucher_date=random_date(),
                summary=f"{month_date.month}月销售费用",
                status="reviewed",
                book_id=book_id,
                created_by=user_id,
            )
            db.add(v4)
            await db.flush()
            selling_items = [
                ("1002", "银行存款", "广告费", selling_exp * 0.4),
                ("1002", "银行存款", "运输费", selling_exp * 0.3),
                ("1002", "银行存款", "差旅费", selling_exp * 0.3),
            ]
            total_debit = 0
            for code, name, desc, amt in selling_items:
                rounded = round(amt, 2)
                db.add(VoucherItem(voucher_id=v4.id, account_code=code, account_name=name, description=desc, debit_amount=0, credit_amount=rounded))
                total_debit += rounded
            db.add(VoucherItem(voucher_id=v4.id, account_code="6601", account_name="销售费用", description="销售费用汇总", debit_amount=round(total_debit, 2), credit_amount=0))
            total_vouchers += 1

            # --- 凭证5：管理费用 ---
            v5 = Voucher(
                voucher_no=_next_voucher_no(),
                voucher_date=random_date(),
                summary=f"{month_date.month}月管理费用",
                status="reviewed",
                book_id=book_id,
                created_by=user_id,
            )
            db.add(v5)
            await db.flush()
            admin_items = [
                ("1002", "银行存款", "办公费", admin_exp * 0.25),
                ("1002", "银行存款", "水电费", admin_exp * 0.2),
                ("1002", "银行存款", "咨询费", admin_exp * 0.3),
                ("1002", "银行存款", "其他", admin_exp * 0.25),
            ]
            total_debit = 0
            for code, name, desc, amt in admin_items:
                rounded = round(amt, 2)
                db.add(VoucherItem(voucher_id=v5.id, account_code=code, account_name=name, description=desc, debit_amount=0, credit_amount=rounded))
                total_debit += rounded
            db.add(VoucherItem(voucher_id=v5.id, account_code="6602", account_name="管理费用", description="管理费用汇总", debit_amount=round(total_debit, 2), credit_amount=0))
            total_vouchers += 1

            # --- 凭证6：财务费用 ---
            v6 = Voucher(
                voucher_no=_next_voucher_no(),
                voucher_date=random_date(),
                summary=f"{month_date.month}月财务费用",
                status="reviewed",
                book_id=book_id,
                created_by=user_id,
            )
            db.add(v6)
            await db.flush()
            db.add(VoucherItem(voucher_id=v6.id, account_code="1002", account_name="银行存款", description="银行手续费", debit_amount=0, credit_amount=fin_exp))
            db.add(VoucherItem(voucher_id=v6.id, account_code="6603", account_name="财务费用", description="手续费", debit_amount=fin_exp, credit_amount=0))
            total_vouchers += 1

            # --- 凭证7：工资 ---
            v7 = Voucher(
                voucher_no=_next_voucher_no(),
                voucher_date=random_date(),
                summary=f"{month_date.month}月工资计提",
                status="posted",
                book_id=book_id,
                created_by=user_id,
            )
            db.add(v7)
            await db.flush()
            db.add(VoucherItem(voucher_id=v7.id, account_code="6602", account_name="管理费用", description="工资", debit_amount=salary * 0.7, credit_amount=0))
            db.add(VoucherItem(voucher_id=v7.id, account_code="6601", account_name="销售费用", description="工资", debit_amount=salary * 0.3, credit_amount=0))
            db.add(VoucherItem(voucher_id=v7.id, account_code="2211", account_name="应付职工薪酬", description="应付工资", debit_amount=0, credit_amount=salary))
            total_vouchers += 1

            # --- 凭证8：固定资产折旧 ---
            dep = 2500 + (month_date.month * 100)  # 逐月增加
            v8 = Voucher(
                voucher_no=_next_voucher_no(),
                voucher_date=random_date(),
                summary=f"{month_date.month}月固定资产折旧",
                status="posted",
                book_id=book_id,
                created_by=user_id,
            )
            db.add(v8)
            await db.flush()
            db.add(VoucherItem(voucher_id=v8.id, account_code="6602", account_name="管理费用", description="折旧费", debit_amount=dep, credit_amount=0))
            db.add(VoucherItem(voucher_id=v8.id, account_code="1602", account_name="累计折旧", description="计提折旧", debit_amount=0, credit_amount=dep))
            total_vouchers += 1

            await db.flush()

        await db.commit()
        print(f"✅ 已生成 {total_vouchers} 条测试凭证（8个月 × 8笔/月）")
        print(f"📅 覆盖月份: 2026-01 ~ 2026-08")
        print(f"📋 凭证状态: reviewed / posted")
        print(f"🎯 现在可以刷新仪表盘和报表页面查看数据")


if __name__ == "__main__":
    asyncio.run(seed_test_data())