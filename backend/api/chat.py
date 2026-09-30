"""
AI 对话 API 路由
提供 SSE 流式对话和模型列表查询
采用两阶段流水线：轻量模型提取意图 + 主力模型生成回答
"""
import json as json_module
import logging
import re
from typing import Optional, AsyncGenerator, List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from database import get_db
from models.user import User
from models.book import Book
from auth.middleware import get_current_user
from auth.book_context import get_current_book
from services.model_router import ModelRouter
from services.api_key_service import ApiKeyService
from services.key_encryption import KeyEncryptionService
from services.memory_service import (
    extract_memories,
    store_memory,
    retrieve_relevant_memories,
    build_memory_context_prompt,
    get_conversation_memories,
    build_enhanced_context_prompt,
)
from config.settings import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["AI对话"])


# ========== 请求/响应模型 ==========

class ChatMessage(BaseModel):
    """历史消息"""
    role: str = Field(..., description="角色: user/assistant")
    content: str = Field(..., description="消息内容")


class ChatRequest(BaseModel):
    """对话请求体"""
    message: str = Field(..., min_length=1, description="用户消息")
    history: List[ChatMessage] = Field(default_factory=list, description="历史消息列表")
    model_preference: Optional[str] = Field(
        default="auto", description="模型偏好: auto/ollama/external"
    )
    provider_code: Optional[str] = Field(None, description="外部提供商代码")
    model_name: Optional[str] = Field(None, description="模型名称")
    enable_web_search: bool = Field(default=False, description="是否启用联网搜索")
    enable_rag: bool = Field(default=True, description="是否启用知识库检索增强")


# ========== 意图提取 Prompt（轻量模型用） ==========

_INTENT_EXTRACTION_SYSTEM_PROMPT = """你是一个意图分类器，负责分析用户输入并输出结构化结果。

请分析用户消息，判断其意图类型，并提取关键参数。输出必须是严格的 JSON 格式，不要包含任何其他文字。

## 核心区分原则

- **bookkeeping** = 用户想"做"一件事（录入、记录、创建凭证），是**写入操作**
- **非bookkeeping** = 用户想"问"一件事（查询、了解、分析），是**读取操作**

关键判断：用户是在"记一笔账"还是在"查一个数"？

## 意图类型

1. **bookkeeping** - 记账意图：用户想录入新凭证、记录财务交易（写入操作）
   典型特征：包含"录入/记/报销/支付/收款/发工资"等动作词 + 具体金额
   错误示例（这些不是bookkeeping！）：
   - 现在账上有多少现金 → chat
   - 这个月收入多少 → chat
   - 现金科目的余额是多少 → chat
   - 帮我看看上个月的利润 → chat

2. **rag** - 知识问答意图：用户想查询公司制度、财务规定、流程标准
   典型特征：问"怎么/如何/什么是/流程/标准/规定/制度"

3. **chat** - 普通对话/财务咨询：闲聊、查询账户余额、问报表数据、一般性财务问题

## Few-shot 示例

输入: 你好
输出: {"intent": "chat", "confidence": 0.95, "extracted_params": {}, "search_query": null, "reasoning": "问候语"}

输入: 录入凭证，销售商品5000元，已存入银行
输出: {"intent": "bookkeeping", "confidence": 0.95, "extracted_params": {"amount": "5000元", "date": null, "summary": "销售商品", "account_hints": ["银行存款", "主营业务收入"]}, "search_query": null, "reasoning": "明确的录入凭证指令+金额"}

输入: 报销差旅费300元
输出: {"intent": "bookkeeping", "confidence": 0.90, "extracted_params": {"amount": "300元", "date": null, "summary": "报销差旅费", "account_hints": ["管理费用", "库存现金"]}, "search_query": null, "reasoning": "报销动作+金额"}

输入: 公司的报销流程是什么
输出: {"intent": "rag", "confidence": 0.90, "extracted_params": {}, "search_query": "报销流程 报销制度 报销标准", "reasoning": "询问公司制度流程"}

输入: 现在账上有多少现金
输出: {"intent": "chat", "confidence": 0.90, "extracted_params": {}, "search_query": null, "reasoning": "查询余额，是读取操作不是写入"}

输入: 差旅费标准是多少
输出: {"intent": "rag", "confidence": 0.85, "extracted_params": {}, "search_query": "差旅费标准 差旅报销标准", "reasoning": "询问公司费用标准"}

输入: 这个月利润怎么样
输出: {"intent": "chat", "confidence": 0.85, "extracted_params": {}, "search_query": null, "reasoning": "查询经营数据，是读取操作"}

输入: 什么是借贷记账法
输出: {"intent": "chat", "confidence": 0.80, "extracted_params": {}, "search_query": null, "reasoning": "概念性问题，一般财务咨询"}

输入: 支付工资50000元
输出: {"intent": "bookkeeping", "confidence": 0.90, "extracted_params": {"amount": "50000元", "date": null, "summary": "支付工资", "account_hints": ["应付职工薪酬", "银行存款"]}, "search_query": null, "reasoning": "支付动作+明确金额"}

输入: 审批权限是怎么规定的
输出: {"intent": "rag", "confidence": 0.85, "extracted_params": {}, "search_query": "审批权限 审批制度 审批规定", "reasoning": "询问公司制度规定"}

## 输出格式

```json
{
  "intent": "bookkeeping|rag|chat",
  "confidence": 0.0-1.0,
  "extracted_params": {
    "amount": "提取到的金额（字符串，如'5000元'），无则为null",
    "date": "提取到的日期（YYYY-MM-DD），无则为null",
    "summary": "业务摘要（如'销售商品'），无则为null",
    "account_hints": ["可能涉及的科目名称列表"]
  },
  "search_query": "优化后的RAG检索查询词（仅rag意图需要），无则为null",
  "reasoning": "分类理由（一句话）"
}
```

## 特别注意
- 查询余额、查报表、问"有多少/是多少" → 一定是 chat，不是 bookkeeping
- 只有明确包含"录入/记录/记/报销/支付"等动作词 + 金额的才是 bookkeeping
- 含"制度/流程/标准/规定/审批"等词 + 疑问词 → rag
- 不确定时，优先判断为 chat（保守策略）
- confidence 要如实反映判断的确定性，不要一律给 0.9"""


# ========== 意图提取（LLM 驱动） ==========

async def _extract_intent_with_llm(message: str) -> Dict[str, Any]:
    """使用轻量模型提取用户意图和结构化参数

    优先使用 Ollama 轻量模型，失败时回退到关键词匹配

    Returns:
        {
            "intent": "bookkeeping|rag|chat",
            "confidence": float,
            "extracted_params": {...},
            "search_query": str|None,
            "reasoning": str,
            "source": "llm"|"keyword_fallback"
        }
    """
    from langchain_core.messages import SystemMessage, HumanMessage
    from langchain_ollama import ChatOllama

    # 尝试获取轻量模型
    lightweight_model = None
    try:
        import httpx
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{settings.OLLAMA_BASE_URL}/api/tags")
            if resp.status_code == 200:
                models = [m["name"] for m in resp.json().get("models", [])]
                # 优先选择小模型：qwen2.5:1.5b > qwen2.5:0.5b > 任意含1.5b/0.5b的模型
                candidates = [
                    "qwen2.5:1.5b", "qwen2.5:0.5b", "qwen3:0.6b",
                    "llama3.2:1b", "phi3:mini",
                ]
                for candidate in candidates:
                    if candidate in models:
                        lightweight_model = candidate
                        break
                # 如果以上都没有，取最小的模型（按名称排序的启发式）
                if not lightweight_model and models:
                    lightweight_model = sorted(models, key=len)[0]
    except Exception as e:
        logger.warning(f"获取轻量模型列表失败: {e}")

    if not lightweight_model:
        logger.info("无可用轻量模型，回退到关键词匹配")
        return _keyword_fallback_intent(message)

    logger.info(f"使用轻量模型提取意图: {lightweight_model}")

    try:
        llm = ChatOllama(
            model=lightweight_model,
            base_url=settings.OLLAMA_BASE_URL,
            temperature=0.0,
            timeout=15,
            num_predict=256,  # 限制输出长度，加快响应
        )
        response = await llm.ainvoke([
            SystemMessage(content=_INTENT_EXTRACTION_SYSTEM_PROMPT),
            HumanMessage(content=f"请分析以下用户消息的意图：\n\n{message}"),
        ])
        response_text = response.content if hasattr(response, "content") else str(response)

        # 解析 JSON
        json_text = response_text.strip()
        if "```json" in json_text:
            json_text = json_text.split("```json")[1].split("```")[0].strip()
        elif "```" in json_text:
            json_text = json_text.split("```")[1].split("```")[0].strip()

        result = json_module.loads(json_text)
        result["source"] = "llm"
        logger.info(
            f"LLM 意图提取: intent={result.get('intent')}, "
            f"confidence={result.get('confidence')}"
        )
        return result

    except Exception as e:
        logger.warning(f"LLM 意图提取失败: {e}，回退到关键词匹配")
        return _keyword_fallback_intent(message)


# ========== 关键词匹配降级方案 ==========

_BOOKKEEPING_KEYWORDS = [
    "录入凭证", "记账", "生成凭证", "做凭证", "记一笔",
    "创建凭证", "帮我录入", "帮我记", "帮我生成凭证",
    "录入", "记录", "记下", "帮我记录", "帮我做",
    "报销", "付款", "收款", "发工资", "交税", "缴税", "纳税",
    "提现", "存款", "转账", "汇款",
    "计提", "折旧", "摊销", "预提", "待摊",
    "结转", "费用报销", "冲销", "核销",
    "借:", "贷:", "借方", "贷方",
    "借：", "贷：",
]

_AMOUNT_PATTERN = re.compile(r'[\d,]+\.?\d*\s*[元块]')
_ACCOUNTING_TERMS = re.compile(
    r'(销售|采购|购买|支付|收到|收入|支出|费用|成本|工资|租金|利息|'
    r'税费|折旧|摊销|应收|应付|预收|预付|库存|商品|材料|办公|差旅|'
    r'招待|维修|运输|广告|咨询|服务|劳务|借款|贷款|投资|分红|利润)'
)

_RAG_DOMAIN_KEYWORDS = [
    "制度", "规定", "政策", "流程", "标准", "规范", "要求",
    "差旅", "审批", "权限", "发票",
    "会计准则", "财务制度", "内控", "审计", "风险", "合规",
    "税务", "报销", "费用",
]

_RAG_QUESTION_KEYWORDS = [
    "怎么", "如何", "什么是", "什么", "哪些", "有什么",
    "可以吗", "行不行", "能不能", "是否", "需要",
    "公司", "企业", "部门", "员工", "领导",
]


def _keyword_fallback_intent(message: str) -> Dict[str, Any]:
    """关键词匹配降级方案（LLM 不可用时的备用方案）"""
    msg_lower = message.lower().strip()

    # 1. 记账意图检测
    is_bookkeeping = False
    for kw in _BOOKKEEPING_KEYWORDS:
        if kw in msg_lower:
            is_bookkeeping = True
            break
    if not is_bookkeeping:
        has_amount = bool(_AMOUNT_PATTERN.search(message))
        has_accounting_term = bool(_ACCOUNTING_TERMS.search(message))
        if has_amount and has_accounting_term and len(message) < 100:
            is_bookkeeping = True

    # 2. RAG 意图检测
    has_domain = any(kw in msg_lower for kw in _RAG_DOMAIN_KEYWORDS)
    has_question = any(kw in msg_lower for kw in _RAG_QUESTION_KEYWORDS)
    is_rag = has_domain and (has_question or len(message) > 3)

    # 3. 冲突裁决：如果同时命中记账和RAG，优先看疑问词
    if is_bookkeeping and is_rag and has_question:
        # 有明确疑问词的问题，优先走 RAG（如"报销流程是什么"）
        is_bookkeeping = False

    if is_bookkeeping:
        amount_match = _AMOUNT_PATTERN.search(message)
        return {
            "intent": "bookkeeping",
            "confidence": 0.7,
            "extracted_params": {
                "amount": amount_match.group() if amount_match else None,
                "date": None,
                "summary": message[:50],
                "account_hints": [],
            },
            "search_query": None,
            "reasoning": "关键词匹配：命中记账关键词",
            "source": "keyword_fallback",
        }

    if is_rag:
        return {
            "intent": "rag",
            "confidence": 0.6,
            "extracted_params": {},
            "search_query": message,
            "reasoning": "关键词匹配：命中知识库领域关键词",
            "source": "keyword_fallback",
        }

    # 4. 默认聊天
    return {
        "intent": "chat",
        "confidence": 0.5,
        "extracted_params": {},
        "search_query": None,
        "reasoning": "关键词匹配：未命中特定意图",
        "source": "keyword_fallback",
    }


def _build_rag_system_prompt(rag_context: str) -> str:
    """构建包含 RAG 上下文的 system prompt，强制结构化输出 + 引用格式"""
    return f"""你是一个企业制度顾问，负责基于知识库文档回答用户问题。

以下是知识库中检索到的相关文档内容：

{rag_context}

## 回答规则

1. **严格基于文档**：只能使用上述文档中明确出现的内容，不得编造或推测
2. **缺失数据标记**：如果文档中某处数字缺失或不明确（如显示为"%"），必须标注为【文档未明确】，不得自行补全
3. **引用来源**：每条关键信息末尾标注【来源：文档名称】
4. **文档不足时**：明确告知"根据现有知识库文档，未找到相关信息"

## 排版要求

- **使用结构化格式**：优先使用表格、编号列表、分点说明
- **关键数字加粗**：将金额、比例、日期等关键数字用**加粗**标出
- **层次分明**：先用一句话总结，再分点展开，最后总结
- **简洁精炼**：删除冗余表述，直击要点

## 格式示例

### 结款方式

根据文档规定，结款分三个阶段：【来源：磋商文件.pdf】

| 阶段 | 时间节点 | 支付比例 | 说明 |
|------|---------|---------|------|
| 1 | 签订合同后 | **【文档未明确】** | 预付款 |
| 2 | 工程量完成【文档未明确】%时 | **【文档未明确】** | 进度款 |
| 3 | 竣工验收合格后 | 剩余尾款 | 尾款 |

> 注意：文档中部分百分比数字缺失，请以实际签署的合同为准。

### 报销流程

报销需经过以下步骤：【来源：财务制度.docx】

1. 员工填写《报销申请单》，附发票原件
2. 部门经理审批（金额超过**500元**需总监加签）
3. 财务审核票据真实性
4. 出纳付款（每月**15日**和**30日**统一处理）

---

请严格按照以上格式要求回答用户问题。"""


def _get_rag_context(message: str, min_score: float = 0.3) -> Optional[str]:
    """从知识库检索相关文档上下文，过滤低相关度结果

    Args:
        message: 检索查询词
        min_score: 最低相关度阈值，低于此值的结果被过滤
    """
    try:
        from services.rag_service import KnowledgeBaseService

        kb_service = KnowledgeBaseService()
        results = kb_service.search(message, top_k=5)

        if not results:
            return None

        # 过滤低相关度结果
        filtered = [r for r in results if r.get("score", 0) >= min_score]
        if not filtered:
            logger.info(f"RAG 检索结果全部低于阈值 {min_score}，返回空")
            return None

        context_parts = []
        for i, r in enumerate(filtered, 1):
            context_parts.append(
                f"【文档{i}】{r['filename']}（相关度: {r['score']:.2%}）\n{r['content']}"
            )
        return "\n\n---\n\n".join(context_parts)

    except Exception as e:
        logger.warning(f"RAG 检索失败: {e}")
        return None


def _build_messages_with_history(
    history: List[ChatMessage],
    current_message: str,
    system_prompt: Optional[str] = None,
) -> list:
    """将历史消息和当前消息组装为 LangChain messages 列表

    Args:
        history: 历史消息列表
        current_message: 当前用户消息
        system_prompt: 可选的 system prompt

    Returns:
        LangChain messages 列表
    """
    from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

    messages = []

    if system_prompt:
        messages.append(SystemMessage(content=system_prompt))

    # 取最近 20 条历史消息（10 轮对话），避免上下文过长
    recent_history = history[-20:] if len(history) > 20 else history

    for msg in recent_history:
        if msg.role == "user":
            messages.append(HumanMessage(content=msg.content))
        elif msg.role == "assistant":
            messages.append(AIMessage(content=msg.content))

    # 添加当前用户消息
    messages.append(HumanMessage(content=current_message))

    return messages


# ========== 默认 system prompt（普通对话） ==========
_DEFAULT_SYSTEM_PROMPT = """你是一个专业的财务智能助手，可以帮助用户解答财务问题、分析数据、生成凭证等。

请遵循以下规则：
1. 用中文回答，保持专业、准确
2. 如果用户提到之前的对话内容，请结合上下文理解
3. 涉及财务计算时，确保数字准确
4. 如果问题超出你的能力范围，请诚实告知"""


# ========== 分层模型调用配置 ==========

class IntentConfig:
    """意图级别的模型调用参数"""
    def __init__(self, temperature: float, max_retries: int, system_prompt: str = ""):
        self.temperature = temperature
        self.max_retries = max_retries
        self.system_prompt = system_prompt


# 不同意图的模型参数：记账需要确定性，RAG需要准确性，聊天可以灵活
_INTENT_CONFIG = {
    "bookkeeping": IntentConfig(temperature=0.0, max_retries=2),
    "rag": IntentConfig(temperature=0.1, max_retries=1),
    "chat": IntentConfig(temperature=0.3, max_retries=0),
}


def _get_intent_config(intent: str) -> IntentConfig:
    """获取意图对应的模型配置"""
    return _INTENT_CONFIG.get(intent, _INTENT_CONFIG["chat"])


# 意图置信度阈值：低于此值则反问用户确认
_CONFIDENCE_THRESHOLD = 0.7


# ========== API 端点 ==========

@router.post("/stream", summary="SSE流式对话")
async def chat_stream(
    chat_request: ChatRequest,
    current_user: User = Depends(get_current_user),
    current_book: Book = Depends(get_current_book),
    db: AsyncSession = Depends(get_db),
):
    """SSE 流式对话接口

    两阶段流水线：
    阶段一：轻量模型提取意图 + 结构化参数
    阶段二：主力模型根据意图生成回答（记账/RAG/聊天）
    """
    # ===== 阶段一：意图提取（轻量模型 / 关键词降级） =====
    intent_result = await _extract_intent_with_llm(chat_request.message)
    intent = intent_result["intent"]
    confidence = intent_result.get("confidence", 0.5)
    extracted_params = intent_result.get("extracted_params", {})
    search_query = intent_result.get("search_query") or chat_request.message
    logger.info(
        f"意图提取完成: intent={intent}, confidence={confidence}, "
        f"source={intent_result.get('source')}, reasoning={intent_result.get('reasoning')}, "
        f"book={current_book.name}"
    )

    # ===== 低置信度时反问用户确认，避免误判 =====
    if confidence < _CONFIDENCE_THRESHOLD and intent_result.get("source") == "llm":
        logger.info(f"意图置信度过低({confidence})，反问用户确认")
        intent_labels = {"bookkeeping": "录入记账凭证", "rag": "查询公司制度", "chat": "财务咨询对话"}

        async def ask_clarification() -> AsyncGenerator[str, None]:
            msg = (
                f"data: 抱歉，我不太确定您的意图。请问您是想：\n"
                f"data: 1. {intent_labels.get('bookkeeping', '')} —— 请提供具体金额和业务描述\n"
                f"data: 2. {intent_labels.get('rag', '')} —— 请说明想了解的制度或流程\n"
                f"data: 3. {intent_labels.get('chat', '')} —— 直接说出您的问题\n\n"
            )
            for char in msg:
                yield char
            yield "data: [DONE]\n\n"

        return StreamingResponse(
            ask_clarification(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    config = _get_intent_config(intent)
    logger.info(f"模型参数: temperature={config.temperature}, max_retries={config.max_retries}")

    # ===== 阶段二：按意图路由到主力模型 =====
    model_router = ModelRouter(db, ApiKeyService(db, KeyEncryptionService()))

    # 始终获取主力 LLM（记账意图也需要，用于意图误判时的降级回退）
    try:
        llm = await model_router.get_llm(
            current_user.id,
            model_preference=chat_request.model_preference or "auto",
            provider_code=chat_request.provider_code,
            model_name=chat_request.model_name,
            temperature=config.temperature,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"获取 LLM 失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="无法连接到 AI 模型",
        )

    # ===== RAG 检索（仅 RAG 意图，使用优化后的检索词） =====
    rag_context = None
    if intent == "rag" and chat_request.enable_rag:
        logger.info(f"RAG 意图，使用优化检索词: {search_query}")
        rag_context = _get_rag_context(search_query)
        if rag_context:
            logger.info("RAG 检索完成，获取到相关文档")

    # ===== 记忆检索：注入用户上下文 =====
    memory_context = ""
    try:
        # 同时检索 AIMemory 和 ConversationMemory
        ai_memories = await retrieve_relevant_memories(
            db, current_user.id, chat_request.message
        )
        conv_memories = await get_conversation_memories(db, current_user.id)
        # 合并记忆，优先使用 AIMemory（更精确的向量匹配）
        all_memories = ai_memories or []
        existing_keys = {m["memory_key"] for m in all_memories}
        for cm in conv_memories:
            if cm["memory_key"] not in existing_keys:
                all_memories.append(cm)
        if all_memories:
            memory_context = build_enhanced_context_prompt(all_memories)
            logger.info(f"已加载 {len(all_memories)} 条用户记忆")
    except Exception as e:
        logger.warning(f"记忆检索失败: {e}")

    async def generate_response() -> AsyncGenerator[str, None]:
        """生成 SSE 流式响应"""
        try:
            if intent == "bookkeeping":
                async for chunk in _handle_bookkeeping_stream(
                    chat_request, current_user, db, config, llm, extracted_params, memory_context
                ):
                    yield chunk
            elif intent == "rag" and rag_context:
                async for chunk in _handle_rag_stream(
                    chat_request, llm, rag_context, config, memory_context
                ):
                    yield chunk
            else:
                async for chunk in _handle_chat_stream(chat_request, llm, memory_context):
                    yield chunk
        except Exception as e:
            logger.error(f"流式对话出错: {e}")
            yield f"data: [ERROR] {str(e)}\n\n"

    return StreamingResponse(
        generate_response(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/extract-memories", summary="从对话中提取记忆")
async def extract_conversation_memories(
    chat_request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """手动触发从对话中提取记忆"""
    all_messages = []
    for msg in chat_request.history:
        all_messages.append({"role": msg.role, "content": msg.content})
    all_messages.append({"role": "user", "content": chat_request.message})

    extracted = await extract_memories(all_messages)
    stored_count = 0
    for item in extracted:
        try:
            await store_memory(
                db,
                current_user.id,
                item.get("key", ""),
                item.get("value", ""),
                item.get("type", "context"),
                float(item.get("importance", 5.0)),
            )
            stored_count += 1
        except Exception as e:
            logger.warning(f"存储记忆失败: {e}")

    return {"extracted": len(extracted), "stored": stored_count, "memories": extracted}


async def _handle_bookkeeping_stream(
    chat_request: ChatRequest,
    current_user: User,
    db: AsyncSession,
    config: IntentConfig,
    llm,
    extracted_params: Dict[str, Any] = None,
    memory_context: str = "",
):
    """记账意图处理：AI 生成凭证 + 校验 + 自动重试
    如果首次尝试失败且原因是"分录不足"，说明可能意图误判，降级为聊天模式
    """
    from services.voucher_ai_service import generate_voucher_by_ai, format_voucher_to_markdown

    logger.info(f"检测到记账意图，开始AI生成凭证: {chat_request.message}")
    if extracted_params:
        logger.info(f"提取到的参数: {extracted_params}")

    last_error = None
    for attempt in range(config.max_retries + 1):
        try:
            voucher_data = await generate_voucher_by_ai(
                chat_request.message, current_user, db,
                voucher_date=extracted_params.get("date") if extracted_params else None,
            )
            markdown = format_voucher_to_markdown(voucher_data)
            for char in markdown:
                yield f"data: {char}\n\n"
            yield "data: [DONE]\n\n"
            return
        except ValueError as e:
            last_error = str(e)
            logger.warning(f"凭证生成第{attempt+1}次尝试失败: {last_error}")
            # "分录不足"通常意味着输入不是记账意图，直接降级到聊天
            if "分录不足" in last_error:
                logger.info("分录不足，可能意图误判，降级为聊天模式")
                yield f"data: 抱歉，我理解您可能不是要录入凭证。让我以对话方式回答您的问题：\n\n"
                async for chunk in _handle_chat_stream(chat_request, llm, memory_context):
                    yield chunk
                return
            if attempt < config.max_retries:
                continue  # 重试
        except RuntimeError as e:
            yield f"data: {str(e)}\n\n"
            yield "data: [DONE]\n\n"
            return

    # 所有重试都失败
    yield f"data: [校验失败] {last_error}，已重试{config.max_retries}次仍无法生成正确凭证。请用更明确的表述重试（如'销售收入5000元已存入银行'）。\n\n"
    yield "data: [DONE]\n\n"


async def _handle_rag_stream(
    chat_request: ChatRequest,
    llm,
    rag_context: str,
    config: IntentConfig,
    memory_context: str = "",
):
    """RAG 问答意图处理：知识库上下文 + 历史消息 + 质量校验"""
    system_prompt = _build_rag_system_prompt(rag_context)
    if memory_context:
        system_prompt += "\n" + memory_context
    messages = _build_messages_with_history(
        chat_request.history, chat_request.message, system_prompt
    )

    full_response = ""
    async for chunk in llm.astream(messages):
        content = chunk.content if hasattr(chunk, "content") else str(chunk)
        if content:
            full_response += content
            yield f"data: {content}\n\n"

    # ===== 第三层：RAG 质量校验 =====
    if config.max_retries > 0 and not _validate_rag_response(full_response, rag_context):
        logger.warning("RAG 回答未引用知识库，使用增强 prompt 重试")
        retry_system = _build_rag_system_prompt(rag_context) + "\n\n重要：你必须在回答中明确引用上述知识库文档的内容，并标注文档名称。"
        if memory_context:
            retry_system += "\n" + memory_context
        retry_messages = _build_messages_with_history(
            chat_request.history, chat_request.message, retry_system
        )
        full_response = ""
        async for chunk in llm.astream(retry_messages):
            content = chunk.content if hasattr(chunk, "content") else str(chunk)
            if content:
                full_response += content
                yield f"data: {content}\n\n"

    yield "data: [DONE]\n\n"


async def _handle_chat_stream(
    chat_request: ChatRequest,
    llm,
    memory_context: str = "",
):
    """普通对话意图处理"""
    system_prompt = _DEFAULT_SYSTEM_PROMPT
    if memory_context:
        system_prompt = _DEFAULT_SYSTEM_PROMPT + "\n" + memory_context
    messages = _build_messages_with_history(
        chat_request.history, chat_request.message, system_prompt
    )
    async for chunk in llm.astream(messages):
        content = chunk.content if hasattr(chunk, "content") else str(chunk)
        if content:
            yield f"data: {content}\n\n"
    yield "data: [DONE]\n\n"


def _validate_rag_response(response: str, rag_context: str) -> bool:
    """校验 RAG 回答质量：是否引用了知识库文档

    检查项：
    1. 是否包含【来源：文档名】引用标记
    2. 是否提到了知识库中的文档名
    """
    # 1. 检查【来源：】引用标记
    if "【来源：" in response or "【来源:" in response:
        return True

    # 2. 提取知识库中的文档名，检查回答中是否提及
    doc_names = []
    for line in rag_context.split("\n"):
        if line.startswith("【文档"):
            name = line.split("】")[1].split("（")[0].strip() if "】" in line else ""
            if name:
                doc_names.append(name)

    for name in doc_names:
        if name in response:
            return True

    return len(doc_names) == 0  # 如果没有文档名，也算通过


@router.get("/models", summary="获取可用模型列表")
async def get_models(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取本地和外部可用的 AI 模型列表"""
    model_router = ModelRouter(
        db,
        ApiKeyService(db, KeyEncryptionService()),
    )

    try:
        models = await model_router.get_available_models(current_user.id)
        return models
    except Exception as e:
        logger.error(f"获取模型列表失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取模型列表失败",
        )