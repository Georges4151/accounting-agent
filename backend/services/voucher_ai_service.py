"""
AI 凭证生成共享服务
从 voucher.py 的 ai-generate 端点提取核心逻辑，供 chat.py 和 voucher.py 共用
"""
import json
import logging
from datetime import date, datetime
from typing import Dict, Any, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.user import User
from models.voucher import Voucher, VoucherItem, Account

logger = logging.getLogger(__name__)


def _generate_voucher_no() -> str:
    """生成凭证号"""
    now = datetime.now()
    return f"PZ-{now.strftime('%Y%m%d')}-{now.strftime('%H%M%S')}{now.microsecond // 1000:03d}"


async def generate_voucher_by_ai(
    description: str,
    current_user: User,
    db: AsyncSession,
    voucher_date: Optional[str] = None,
    book_id: Optional[int] = None,
) -> Dict[str, Any]:
    """使用 AI 根据自然语言描述生成记账凭证

    Args:
        description: 用户自然语言描述
        current_user: 当前用户
        db: 数据库会话
        voucher_date: 可选的凭证日期 YYYY-MM-DD
        book_id: 可选的账套ID

    Returns:
        生成的凭证数据字典，包含 voucher 和 items 信息

    Raises:
        ValueError: 参数校验失败
        RuntimeError: AI 调用失败
    """
    logger.info(f"用户 {current_user.username} 请求AI生成凭证: {description}")

    # 1. 获取可用科目列表
    query = select(Account).where(Account.is_active == True)
    if book_id:
        query = query.where(Account.book_id == book_id)
    query = query.order_by(Account.account_code)
    result = await db.execute(query)
    accounts = result.scalars().all()
    if not accounts:
        raise ValueError("系统中没有可用的会计科目，请先初始化科目表")

    accounts_text = "\n".join(
        f"  {acc.account_code} {acc.account_name}（{acc.account_type}，余额方向: {acc.balance_direction}）"
        for acc in accounts
    )

    # 2. 获取 LLM 实例
    from services.model_router import ModelRouter
    from services.api_key_service import ApiKeyService
    from services.key_encryption import KeyEncryptionService

    model_router = ModelRouter(db, ApiKeyService(db, KeyEncryptionService()))
    try:
        llm = await model_router.get_llm(current_user.id, temperature=0.1)
    except ValueError as e:
        raise ValueError(str(e))
    except Exception as e:
        logger.error(f"获取 LLM 失败: {e}")
        raise RuntimeError("无法连接到 AI 模型，请确保 Ollama 服务已启动")

    # 3. 构建 prompt
    today = voucher_date or date.today().isoformat()
    system_prompt = f"""你是一个专业会计，请根据用户的自然语言描述生成记账凭证。

当前日期: {today}

可用的会计科目（必须从以下科目中选择）：
{accounts_text}

请根据用户描述，生成符合《企业会计准则》的记账凭证。

## Few-shot 示例

示例1: 用户说"销售商品5000元，已存入银行"
输出:
```json
{{
  "voucher_date": "{today}",
  "summary": "销售商品",
  "items": [
    {{
      "account_code": "1002",
      "account_name": "银行存款",
      "description": "销售商品收款",
      "debit_amount": 5000,
      "credit_amount": 0
    }},
    {{
      "account_code": "6001",
      "account_name": "主营业务收入",
      "description": "销售商品收入",
      "debit_amount": 0,
      "credit_amount": 5000
    }}
  ]
}}
```

示例2: 用户说"报销差旅费300元，现金支付"
输出:
```json
{{
  "voucher_date": "{today}",
  "summary": "报销差旅费",
  "items": [
    {{
      "account_code": "6602",
      "account_name": "管理费用",
      "description": "差旅费报销",
      "debit_amount": 300,
      "credit_amount": 0
    }},
    {{
      "account_code": "1001",
      "account_name": "库存现金",
      "description": "现金支付差旅费",
      "debit_amount": 0,
      "credit_amount": 300
    }}
  ]
}}
```

示例3: 用户说"支付本月工资50000元，银行转账"
输出:
```json
{{
  "voucher_date": "{today}",
  "summary": "支付本月工资",
  "items": [
    {{
      "account_code": "2211",
      "account_name": "应付职工薪酬",
      "description": "支付工资",
      "debit_amount": 50000,
      "credit_amount": 0
    }},
    {{
      "account_code": "1002",
      "account_name": "银行存款",
      "description": "银行转账支付工资",
      "debit_amount": 0,
      "credit_amount": 50000
    }}
  ]
}}
```

## 输出格式

严格遵循以下 JSON 格式：
```json
{{
  "voucher_date": "YYYY-MM-DD",
  "summary": "凭证摘要",
  "items": [
    {{
      "account_code": "科目编码",
      "account_name": "科目名称",
      "description": "分录描述",
      "debit_amount": 借方金额,
      "credit_amount": 贷方金额
    }}
  ]
}}
```

## 规则
1. 必须确保借贷平衡（借方合计 = 贷方合计）
2. 科目编码和名称必须从上方的科目列表中选择，不得编造
3. 金额必须精确提取用户描述中的数字，不要带千位分隔符，不要四舍五入
4. 每笔分录的借方和贷方金额不能同时 > 0
5. 凭证日期使用当前日期 {today}
6. 如果用户提到了具体金额（如"5000元"），必须在分录中使用该金额
7. 参考上面的 few-shot 示例来理解科目选择逻辑
8. 只输出 JSON，不要其他文字"""

    user_message = f"请根据以下描述生成记账凭证（注意：必须使用描述中提到的具体金额）：{description}"

    # 4. 调用 LLM
    from langchain_core.messages import SystemMessage, HumanMessage

    try:
        response = await llm.ainvoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message),
        ])
        response_text = response.content if hasattr(response, "content") else str(response)
    except Exception as e:
        logger.error(f"LLM 调用失败: {e}")
        raise RuntimeError(f"AI 模型调用失败: {str(e)}")

    # 5. 解析 JSON
    try:
        json_text = response_text.strip()
        if "```json" in json_text:
            json_text = json_text.split("```json")[1].split("```")[0].strip()
        elif "```" in json_text:
            json_text = json_text.split("```")[1].split("```")[0].strip()

        voucher_data = json.loads(json_text)
    except (json.JSONDecodeError, IndexError) as e:
        logger.error(f"解析 AI 响应失败: {response_text[:500]}")
        raise RuntimeError(f"AI 返回格式异常，请重试。原始响应: {response_text[:300]}")

    # 6. 验证数据
    items = voucher_data.get("items", [])
    if len(items) < 2:
        raise ValueError("AI 生成的分录不足，至少需要 2 条分录")

    total_debit = sum(item.get("debit_amount", 0) for item in items)
    total_credit = sum(item.get("credit_amount", 0) for item in items)
    if total_debit == 0 and total_credit == 0:
        raise ValueError('AI 未正确提取金额，请用更明确的表述（如"销售收入5000元"）重试')
    if abs(total_debit - total_credit) > 0.01:
        raise ValueError(
            f"AI 生成的凭证借贷不平衡: 借方={total_debit}, 贷方={total_credit}"
        )

    # 7. 验证科目有效性
    valid_codes = {acc.account_code for acc in accounts}
    for item in items:
        if item["account_code"] not in valid_codes:
            raise ValueError(
                f"AI 使用了无效科目编码: {item['account_code']}，请重试"
            )

    # 8. 创建凭证
    voucher_date = voucher_data.get("voucher_date", today)
    try:
        parsed_date = date.fromisoformat(voucher_date)
    except ValueError:
        parsed_date = date.today()

    voucher = Voucher(
        voucher_no=_generate_voucher_no(),
        voucher_date=parsed_date,
        summary=voucher_data.get("summary", description[:50]),
        status="draft",
        created_by=current_user.id,
    )
    db.add(voucher)
    await db.flush()

    for item_data in items:
        item = VoucherItem(
            voucher_id=voucher.id,
            account_code=item_data["account_code"],
            account_name=item_data["account_name"],
            description=item_data.get("description", ""),
            debit_amount=item_data.get("debit_amount", 0),
            credit_amount=item_data.get("credit_amount", 0),
        )
        db.add(item)

    await db.commit()
    await db.refresh(voucher)
    logger.info(
        f"AI 为用户 {current_user.username} 生成了凭证 {voucher.voucher_no}，"
        f"共 {len(items)} 条分录"
    )

    # 返回结果数据
    return {
        "id": voucher.id,
        "voucher_no": voucher.voucher_no,
        "voucher_date": voucher.voucher_date.isoformat(),
        "summary": voucher.summary,
        "status": voucher.status,
        "created_by": voucher.created_by,
        "reviewed_by": voucher.reviewed_by,
        "posted_at": voucher.posted_at.isoformat() if voucher.posted_at else None,
        "created_at": voucher.created_at.isoformat() if voucher.created_at else None,
        "items": [
            {
                "id": i.id,
                "account_code": i.account_code,
                "account_name": i.account_name,
                "description": i.description,
                "debit_amount": float(i.debit_amount),
                "credit_amount": float(i.credit_amount),
            }
            for i in voucher.items
        ],
    }


def format_voucher_to_markdown(voucher_data: Dict[str, Any]) -> str:
    """将凭证数据格式化为可读的 Markdown 文本（供聊天界面展示）

    Args:
        voucher_data: generate_voucher_by_ai 返回的凭证数据

    Returns:
        Markdown 格式的凭证展示文本
    """
    total_debit = sum(item["debit_amount"] for item in voucher_data["items"])
    total_credit = sum(item["credit_amount"] for item in voucher_data["items"])

    lines = [
        f"## 已生成记账凭证",
        f"",
        f"**凭证号**: {voucher_data['voucher_no']}",
        f"**日期**: {voucher_data['voucher_date']}",
        f"**摘要**: {voucher_data['summary']}",
        f"**状态**: 草稿",
        f"",
        f"| 科目编码 | 科目名称 | 摘要 | 借方金额 | 贷方金额 |",
        f"|---------|---------|------|---------|---------|",
    ]

    for item in voucher_data["items"]:
        debit = f"{item['debit_amount']:,.2f}" if item["debit_amount"] > 0 else ""
        credit = f"{item['credit_amount']:,.2f}" if item["credit_amount"] > 0 else ""
        lines.append(
            f"| {item['account_code']} | {item['account_name']} | {item['description']} | {debit} | {credit} |"
        )

    lines.append(f"| **合计** | | | **{total_debit:,.2f}** | **{total_credit:,.2f}** |")
    lines.append(f"")
    lines.append(f"借贷平衡，凭证已保存为草稿。可在「凭证管理」中查看和编辑。")

    return "\n".join(lines)