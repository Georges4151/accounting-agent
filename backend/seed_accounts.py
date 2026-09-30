"""快速初始化标准科目表"""
import asyncio
from database import async_session_maker
from models.voucher import Account
from sqlalchemy import select

STANDARD_ACCOUNTS = [
    # 资产类
    ("1001", "库存现金", "asset", "debit"),
    ("1002", "银行存款", "asset", "debit"),
    ("1012", "其他货币资金", "asset", "debit"),
    ("1101", "交易性金融资产", "asset", "debit"),
    ("1121", "应收票据", "asset", "debit"),
    ("1122", "应收账款", "asset", "debit"),
    ("1123", "预付账款", "asset", "debit"),
    ("1131", "应收股利", "asset", "debit"),
    ("1132", "应收利息", "asset", "debit"),
    ("1221", "其他应收款", "asset", "debit"),
    ("1231", "坏账准备", "asset", "credit"),
    ("1401", "材料采购", "asset", "debit"),
    ("1402", "在途物资", "asset", "debit"),
    ("1403", "原材料", "asset", "debit"),
    ("1405", "库存商品", "asset", "debit"),
    ("1411", "周转材料", "asset", "debit"),
    ("1471", "存货跌价准备", "asset", "credit"),
    ("1501", "债权投资", "asset", "debit"),
    ("1511", "长期股权投资", "asset", "debit"),
    ("1601", "固定资产", "asset", "debit"),
    ("1602", "累计折旧", "asset", "credit"),
    ("1603", "固定资产减值准备", "asset", "credit"),
    ("1604", "在建工程", "asset", "debit"),
    ("1605", "工程物资", "asset", "debit"),
    ("1606", "固定资产清理", "asset", "debit"),
    ("1701", "无形资产", "asset", "debit"),
    ("1702", "累计摊销", "asset", "credit"),
    ("1801", "长期待摊费用", "asset", "debit"),
    ("1901", "待处理财产损溢", "asset", "debit"),

    # 负债类
    ("2001", "短期借款", "liability", "credit"),
    ("2201", "应付票据", "liability", "credit"),
    ("2202", "应付账款", "liability", "credit"),
    ("2203", "预收账款", "liability", "credit"),
    ("2211", "应付职工薪酬", "liability", "credit"),
    ("2221", "应交税费", "liability", "credit"),
    ("2231", "应付利息", "liability", "credit"),
    ("2232", "应付股利", "liability", "credit"),
    ("2241", "其他应付款", "liability", "credit"),
    ("2501", "长期借款", "liability", "credit"),
    ("2502", "应付债券", "liability", "credit"),
    ("2701", "长期应付款", "liability", "credit"),
    ("2901", "递延所得税负债", "liability", "credit"),

    # 权益类
    ("4001", "实收资本", "equity", "credit"),
    ("4002", "资本公积", "equity", "credit"),
    ("4101", "盈余公积", "equity", "credit"),
    ("4103", "本年利润", "equity", "credit"),
    ("4104", "利润分配", "equity", "credit"),

    # 成本类
    ("5001", "生产成本", "cost", "debit"),
    ("5101", "制造费用", "cost", "debit"),
    ("5201", "劳务成本", "cost", "debit"),
    ("5301", "研发支出", "cost", "debit"),

    # 损益类 - 收入 (credit方向)
    ("6001", "主营业务收入", "revenue", "credit"),
    ("6051", "其他业务收入", "revenue", "credit"),
    ("6101", "公允价值变动损益", "revenue", "credit"),
    ("6111", "投资收益", "revenue", "credit"),
    ("6301", "营业外收入", "revenue", "credit"),

    # 损益类 - 费用 (debit方向)
    ("6401", "主营业务成本", "expense", "debit"),
    ("6402", "其他业务成本", "expense", "debit"),
    ("6403", "税金及附加", "expense", "debit"),
    ("6601", "销售费用", "expense", "debit"),
    ("6602", "管理费用", "expense", "debit"),
    ("6603", "财务费用", "expense", "debit"),
    ("6701", "资产减值损失", "expense", "debit"),
    ("6711", "营业外支出", "expense", "debit"),
    ("6801", "所得税费用", "expense", "debit"),
]


async def seed_accounts():
    async with async_session_maker() as db:
        # 检查是否已存在
        result = await db.execute(select(Account).limit(1))
        if result.scalar_one_or_none():
            print("科目表已存在，跳过初始化")
            return

        for code, name, atype, direction in STANDARD_ACCOUNTS:
            db.add(Account(
                account_code=code,
                account_name=name,
                account_type=atype,
                balance_direction=direction,
                is_active=True,
            ))

        await db.commit()
        print(f"已初始化 {len(STANDARD_ACCOUNTS)} 个会计科目")


if __name__ == "__main__":
    asyncio.run(seed_accounts())