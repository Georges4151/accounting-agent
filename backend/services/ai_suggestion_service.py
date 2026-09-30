"""
AI 智能建议服务
提供科目分类建议和异常检测，支持历史学习
"""
import json
import logging
import re
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def suggest_account_code(
    description: str,
    amount: float,
    db: AsyncSession,
    user_id: int,
    book_id: Optional[int] = None,
) -> dict:
    """根据交易描述和金额，AI 智能推荐最合适的科目编码

    优先级：历史记录 > AI模型 > 规则匹配

    Args:
        description: 交易描述/摘要
        amount: 交易金额
        db: 数据库会话
        user_id: 用户ID
        book_id: 账套ID

    Returns:
        {"account_code": "6602", "account_name": "管理费用", "confidence": 0.85, "reason": "..."}
    """
    from models.voucher import Account

    # 获取可用科目
    query = select(Account).where(Account.is_active == True)
    if book_id:
        query = query.where(Account.book_id == book_id)
    result = await db.execute(query)
    accounts = result.scalars().all()

    if not accounts:
        return {
            "account_code": "",
            "account_name": "无可用科目",
            "confidence": 0,
            "reason": "系统中没有可用科目",
            "source": "error"
        }

    # 1. 优先使用历史学习
    history_result = await _history_based_suggest(description, amount, db, book_id, accounts)
    if history_result and history_result.get("confidence", 0) >= 0.85:
        return history_result

    # 2. 尝试 AI 模型
    accounts_text = "\n".join(
        f"  {acc.account_code} {acc.account_name}（{acc.account_type}）"
        for acc in accounts
    )

    try:
        from services.model_router import ModelRouter
        from services.api_key_service import ApiKeyService
        from services.key_encryption import KeyEncryptionService

        model_router = ModelRouter(db, ApiKeyService(db, KeyEncryptionService()))
        llm = await model_router.get_llm(user_id, temperature=0.0)

        from langchain_core.messages import SystemMessage, HumanMessage

        # 如果有历史记录，加入提示
        history_hint = ""
        if history_result:
            history_hint = f"\n\n历史参考：用户之前类似交易使用过「{history_result['account_code']} {history_result['account_name']}」（{history_result.get('reason', '')}），请优先考虑。"

        system_prompt = f"""你是一个专业会计助手。根据用户描述的交易内容和金额，推荐最合适的会计科目。

可用的会计科目：
{accounts_text}
{history_hint}

请根据交易描述，推荐最合适的科目编码和名称。只返回 JSON，不要其他文字。

返回格式：
{{"account_code": "科目编码", "account_name": "科目名称", "confidence": 0.85, "reason": "推荐理由（简短）"}}

规则：
1. 科目编码必须从上述列表中选择
2. 考虑交易描述的关键词匹配
3. 金额大小可以作为参考（大额交易可能涉及固定资产等）
4. confidence 表示推荐置信度，0-1之间"""

        user_message = f"交易描述：{description}\n交易金额：{amount}元\n请推荐最合适的会计科目。"

        response = await llm.ainvoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message),
        ])
        response_text = response.content if hasattr(response, "content") else str(response)

        json_text = response_text.strip()
        if "```json" in json_text:
            json_text = json_text.split("```json")[1].split("```")[0].strip()
        elif "```" in json_text:
            json_text = json_text.split("```")[1].split("```")[0].strip()

        ai_result = json.loads(json_text)

        # 合并历史置信度
        if history_result and ai_result.get("account_code") == history_result.get("account_code"):
            ai_result["confidence"] = min(ai_result.get("confidence", 0.7) + 0.1, 0.98)
            ai_result["reason"] = f"AI+历史: {ai_result.get('reason', '')}"
        ai_result["source"] = "ai"
        return ai_result

    except Exception as e:
        logger.warning(f"AI科目建议失败: {e}")

    # 3. 降级：历史 > 规则
    if history_result:
        return history_result

    return _rule_based_suggest(description, amount, accounts)


async def _history_based_suggest(
    description: str,
    amount: float,
    db: AsyncSession,
    book_id: Optional[int] = None,
    accounts: list = None,
) -> Optional[dict]:
    """基于历史分录记录的科目建议

    从用户已有的凭证分录中查找相似描述，统计最常用的科目编码。
    """
    from models.voucher import VoucherItem, Voucher

    keywords = _extract_keywords(description)
    if not keywords:
        return None

    # 构建模糊匹配条件：任意关键词匹配
    conditions = []
    for kw in keywords:
        conditions.append(VoucherItem.description.like(f"%{kw}%"))

    query = (
        select(
            VoucherItem.account_code,
            VoucherItem.account_name,
            func.count(VoucherItem.id).label("usage_count"),
        )
        .join(Voucher, VoucherItem.voucher_id == Voucher.id)
        .where(func.or_(*conditions))
    )

    if book_id:
        query = query.where(Voucher.book_id == book_id)

    query = (
        query.group_by(VoucherItem.account_code, VoucherItem.account_name)
        .order_by(func.count(VoucherItem.id).desc())
        .limit(3)
    )

    try:
        result = await db.execute(query)
        rows = result.all()

        if not rows:
            return None

        # 取使用次数最多的科目
        top = rows[0]
        total_usage = sum(r.usage_count for r in rows)
        confidence = min(0.65 + (top.usage_count / max(total_usage, 1)) * 0.25, 0.92)

        # 验证科目在可用列表中
        if accounts:
            account_codes = {a.account_code for a in accounts}
            if top.account_code not in account_codes:
                # 如果历史科目不在当前可用列表中，尝试下一个
                for r in rows[1:]:
                    if r.account_code in account_codes:
                        return {
                            "account_code": r.account_code,
                            "account_name": r.account_name,
                            "confidence": min(0.65 + (r.usage_count / max(total_usage, 1)) * 0.2, 0.85),
                            "reason": f"历史记录（{r.usage_count}次）",
                            "source": "history",
                        }
                return None

        return {
            "account_code": top.account_code,
            "account_name": top.account_name,
            "confidence": confidence,
            "reason": f"历史记录匹配（{top.usage_count}次）",
            "source": "history",
        }
    except Exception as e:
        logger.warning(f"历史科目建议查询失败: {e}")
        return None


def _extract_keywords(description: str) -> list:
    """从描述中提取有意义的搜索关键词"""
    # 移除标点符号和常见停用词
    stopwords = {"的", "了", "是", "在", "和", "与", "及", "或", "等", "从", "到", "用", "为", "已", "将", "对", "由", "向", "于", "中", "上", "下", "这", "那", "该", "此", "元", "万", "千", "百"}
    cleaned = re.sub(r"[，。！？、；：""''（）【】《》\s,\.!\?;:'\"\(\)\[\]{}]", " ", description)
    words = cleaned.split()
    keywords = [w for w in words if len(w) >= 2 and w not in stopwords]
    return keywords[:5]  # 取前5个关键词


def _rule_based_suggest(description: str, amount: float, accounts) -> dict:
    """基于规则的科目建议（降级方案）"""
    rules = {
        "销售": ("6001", "主营业务收入"),
        "收入": ("6001", "主营业务收入"),
        "采购": ("1405", "库存商品"),
        "工资": ("2211", "应付职工薪酬"),
        "报销": ("6602", "管理费用"),
        "差旅": ("6602", "管理费用"),
        "办公": ("6602", "管理费用"),
        "水电": ("6602", "管理费用"),
        "租金": ("6602", "管理费用"),
        "维修": ("6602", "管理费用"),
        "税费": ("2221", "应交税费"),
        "借款": ("2001", "短期借款"),
        "存款": ("1002", "银行存款"),
        "现金": ("1001", "库存现金"),
        "固定资产": ("1601", "固定资产"),
        "折旧": ("1602", "累计折旧"),
        "餐饮": ("6602", "管理费用"),
        "快递": ("6602", "管理费用"),
        "运费": ("6601", "销售费用"),
        "广告": ("6601", "销售费用"),
        "利息": ("6603", "财务费用"),
        "手续费": ("6603", "财务费用"),
        "服务": ("6001", "主营业务收入"),
        "咨询": ("6001", "主营业务收入"),
        "培训": ("6602", "管理费用"),
        "招待": ("6602", "管理费用"),
        "交通": ("6602", "管理费用"),
        "通讯": ("6602", "管理费用"),
        "印刷": ("6602", "管理费用"),
        "物业": ("6602", "管理费用"),
        "社保": ("2211", "应付职工薪酬"),
        "公积金": ("2211", "应付职工薪酬"),
        "分红": ("4104", "利润分配"),
        "投资": ("1511", "长期股权投资"),
        "贷款": ("2001", "短期借款"),
        "还款": ("2001", "短期借款"),
        "退款": ("1002", "银行存款"),
        "押金": ("2241", "其他应付款"),
        "保证金": ("2241", "其他应付款"),
        "预付款": ("1123", "预付账款"),
        "预收款": ("2203", "预收账款"),
        "捐赠": ("6711", "营业外支出"),
        "罚款": ("6711", "营业外支出"),
        "盘盈": ("6301", "营业外收入"),
        "盘亏": ("6711", "营业外支出"),
    }

    # 验证科目是否在可用列表中
    account_codes = {a.account_code for a in accounts} if accounts else set()

    for keyword, (code, name) in rules.items():
        if keyword in description:
            if account_codes and code not in account_codes:
                continue
            return {
                "account_code": code,
                "account_name": name,
                "confidence": 0.7,
                "reason": f"关键词匹配: {keyword}",
                "source": "rule",
            }

    # 根据金额大小给出辅助判断
    if amount >= 50000:
        default_code = "1601"
        default_name = "固定资产"
        default_reason = "大额交易，建议检查是否为固定资产"
    elif amount >= 10000:
        default_code = "6602"
        default_name = "管理费用"
        default_reason = "中等金额，默认推荐管理费用"
    else:
        default_code = "6602"
        default_name = "管理费用"
        default_reason = "默认推荐，请人工确认"

    # 确保默认科目在可用列表中
    if account_codes and default_code not in account_codes:
        for code in ["6602", "6601", "6603", "6001", "1405"]:
            if code in account_codes:
                acct = next((a for a in accounts if a.account_code == code), None)
                return {
                    "account_code": code,
                    "account_name": acct.account_name if acct else code,
                    "confidence": 0.25,
                    "reason": "默认推荐",
                    "source": "rule",
                }

    return {
        "account_code": default_code,
        "account_name": default_name,
        "confidence": 0.3,
        "reason": default_reason,
        "source": "rule",
    }


async def suggest_summary(
    account_code: str,
    partial_text: str = "",
    db: AsyncSession = None,
    book_id: Optional[int] = None,
    limit: int = 5,
) -> list:
    """根据科目代码，从历史分录中推荐常用摘要

    Args:
        account_code: 科目代码
        partial_text: 用户已输入的摘要片段（用于过滤）
        db: 数据库会话
        book_id: 账套ID
        limit: 返回建议数量

    Returns:
        [{ "summary": "支付办公用品费", "usage_count": 15, "relevance": 0.95 }, ...]
    """
    from models.voucher import VoucherItem, Voucher

    if not account_code:
        return []

    # 查询该科目下使用过的摘要及使用次数
    query = (
        select(
            VoucherItem.description,
            func.count(VoucherItem.id).label("usage_count"),
        )
        .join(Voucher, VoucherItem.voucher_id == Voucher.id)
        .where(VoucherItem.account_code == account_code)
    )

    if book_id:
        query = query.where(Voucher.book_id == book_id)

    query = (
        query.group_by(VoucherItem.description)
        .order_by(func.count(VoucherItem.id).desc())
        .limit(50)
    )

    try:
        result = await db.execute(query)
        rows = result.all()

        if not rows:
            return []

        suggestions = []
        for desc, count in rows:
            if not desc or not desc.strip():
                continue

            # 计算相关性：如果用户已输入部分文字，匹配度越高越靠前
            relevance = 1.0
            if partial_text and partial_text.strip():
                pt = partial_text.strip().lower()
                dt = desc.strip().lower()
                if pt == dt:
                    relevance = 1.0
                elif dt.startswith(pt):
                    relevance = 0.9
                elif pt in dt:
                    relevance = 0.7
                else:
                    continue  # 不匹配则跳过

            # 使用频率加权
            freq_weight = min(count / max(r[1] for r in rows), 1.0)
            final_score = relevance * 0.6 + freq_weight * 0.4

            suggestions.append({
                "summary": desc.strip(),
                "usage_count": count,
                "relevance": round(final_score, 2),
            })

        # 按综合得分排序
        suggestions.sort(key=lambda x: x["relevance"], reverse=True)
        return suggestions[:limit]

    except Exception as e:
        logger.warning(f"摘要建议查询失败: {e}")
        return []