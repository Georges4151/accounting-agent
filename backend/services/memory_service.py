"""
AI 跨会话记忆服务
提供记忆提取、存储、检索和管理功能
"""
import json
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

from sqlalchemy import select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from models.ai_memory import AIMemory
from models.conversation_memory import ConversationMemory
from models.conversation import Conversation, Message

logger = logging.getLogger(__name__)


async def _call_ai_for_extraction(messages_text: str) -> List[Dict[str, Any]]:
    """使用 AI 从对话中提取关键记忆

    Args:
        messages_text: 对话文本（截断后的用户和助手对话）

    Returns:
        提取的记忆列表，每项包含 key, value, type, importance
    """
    from langchain_core.messages import SystemMessage, HumanMessage
    from langchain_ollama import ChatOllama
    from config.settings import settings

    system_prompt = """你是一个记忆提取器，负责从对话中提取关于用户的重要信息。请分析以下对话，提取关键事实。

提取规则：
1. 财务偏好：用户喜欢什么记账方式、科目偏好、报表格式偏好等
2. 公司/行业上下文：用户所在公司、行业、业务特点等
3. 经常问的问题/主题：用户反复提到的话题
4. 个人偏好：用户表达的任何偏好或习惯

输出必须是严格的 JSON 数组格式，每个记忆包含：
- key: 记忆关键词（简短标题）
- value: 记忆内容（一句话描述）
- type: 类型（preference/knowledge/context）
- importance: 重要性 0-10（数字）

如果对话中没有值得记住的信息，返回空数组 []。

示例输出：
[
  {"key": "公司行业", "value": "用户在一家科技制造企业工作", "type": "context", "importance": 7},
  {"key": "报表偏好", "value": "用户偏好按月度生成利润表", "type": "preference", "importance": 6}
]"""

    try:
        import httpx
        model_name = None
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{settings.OLLAMA_BASE_URL}/api/tags")
            if resp.status_code == 200:
                models = [m["name"] for m in resp.json().get("models", [])]
                candidates = ["qwen2.5:1.5b", "qwen2.5:0.5b", "qwen3:0.6b"]
                for candidate in candidates:
                    if candidate in models:
                        model_name = candidate
                        break
                if not model_name and models:
                    model_name = sorted(models, key=len)[0]

        if not model_name:
            logger.warning("无可用轻量模型，跳过记忆提取")
            return []

        llm = ChatOllama(
            model=model_name,
            base_url=settings.OLLAMA_BASE_URL,
            temperature=0.0,
            timeout=15,
            num_predict=256,
        )
        response = await llm.ainvoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"请从以下对话中提取关键信息：\n\n{messages_text}"),
        ])
        response_text = response.content if hasattr(response, "content") else str(response)

        json_text = response_text.strip()
        if "```json" in json_text:
            json_text = json_text.split("```json")[1].split("```")[0].strip()
        elif "```" in json_text:
            json_text = json_text.split("```")[1].split("```")[0].strip()

        result = json.loads(json_text)
        if isinstance(result, list):
            return result
        return []
    except Exception as e:
        logger.warning(f"AI 记忆提取失败: {e}")
        return []


async def extract_memories(messages: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    """从对话消息中提取关键记忆

    Args:
        messages: 对话消息列表，每项包含 role 和 content

    Returns:
        提取的记忆列表
    """
    if not messages:
        return []

    # 构建对话文本，只取最近 20 条消息，截断每条到 500 字符
    text_parts = []
    for msg in messages[-20:]:
        role = msg.get("role", "user")
        content = (msg.get("content", "") or "")[:500]
        label = "用户" if role == "user" else "助手"
        text_parts.append(f"{label}: {content}")

    messages_text = "\n".join(text_parts)

    if len(messages_text) < 50:
        return []

    memories = await _call_ai_for_extraction(messages_text)
    return memories


async def store_memory(
    db: AsyncSession,
    user_id: int,
    memory_key: str,
    memory_value: str,
    memory_type: str = "context",
    importance: float = 5.0,
) -> AIMemory:
    """存储一条记忆

    如果已存在相同 key 的记忆，则更新 value 和 importance
    """
    # 检查是否已存在
    result = await db.execute(
        select(AIMemory).where(
            AIMemory.user_id == user_id,
            AIMemory.memory_key == memory_key,
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        existing.memory_value = memory_value
        existing.memory_type = memory_type
        existing.importance = max(existing.importance, importance)
        await db.commit()
        await db.refresh(existing)
        return existing

    memory = AIMemory(
        user_id=user_id,
        memory_key=memory_key,
        memory_value=memory_value,
        memory_type=memory_type,
        importance=importance,
    )
    db.add(memory)
    await db.commit()
    await db.refresh(memory)
    return memory


async def retrieve_relevant_memories(
    db: AsyncSession,
    user_id: int,
    query: str = "",
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """检索与用户相关的记忆

    使用简单的关键词匹配进行语义搜索
    """
    result = await db.execute(
        select(AIMemory)
        .where(AIMemory.user_id == user_id)
        .order_by(AIMemory.importance.desc(), AIMemory.updated_at.desc())
        .limit(limit * 2)  # 多取一些用于过滤
    )
    memories = result.scalars().all()

    if not memories:
        return []

    # 简单关键词匹配评分
    scored = []
    query_lower = query.lower() if query else ""
    for m in memories:
        score = m.importance
        if query_lower:
            key_lower = m.memory_key.lower()
            value_lower = m.memory_value.lower()
            # 关键词匹配加分
            for word in query_lower.split():
                if word in key_lower:
                    score += 3
                if word in value_lower:
                    score += 2
        scored.append((m, score))

    # 按分数排序
    scored.sort(key=lambda x: x[1], reverse=True)

    result_list = []
    for m, _ in scored[:limit]:
        # 更新访问计数和最后访问时间
        m.access_count = (m.access_count or 0) + 1
        m.last_accessed = func.now()
        result_list.append({
            "id": m.id,
            "memory_key": m.memory_key,
            "memory_value": m.memory_value,
            "memory_type": m.memory_type,
            "importance": m.importance,
            "access_count": m.access_count + 1,
        })

    if result_list:
        await db.commit()

    return result_list


async def get_all_memories(
    db: AsyncSession,
    user_id: int,
    memory_type: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """获取用户的所有记忆"""
    query = select(AIMemory).where(AIMemory.user_id == user_id)
    if memory_type:
        query = query.where(AIMemory.memory_type == memory_type)
    query = query.order_by(AIMemory.importance.desc(), AIMemory.updated_at.desc())

    result = await db.execute(query)
    memories = result.scalars().all()

    return [
        {
            "id": m.id,
            "memory_key": m.memory_key,
            "memory_value": m.memory_value,
            "memory_type": m.memory_type,
            "importance": m.importance,
            "access_count": m.access_count or 0,
            "last_accessed": m.last_accessed.isoformat() if m.last_accessed else None,
            "created_at": m.created_at.isoformat() if m.created_at else None,
            "updated_at": m.updated_at.isoformat() if m.updated_at else None,
        }
        for m in memories
    ]


async def update_memory_importance(
    db: AsyncSession,
    memory_id: int,
    user_id: int,
    new_importance: float,
) -> Optional[AIMemory]:
    """更新记忆重要性"""
    result = await db.execute(
        select(AIMemory).where(
            AIMemory.id == memory_id,
            AIMemory.user_id == user_id,
        )
    )
    memory = result.scalar_one_or_none()
    if memory:
        memory.importance = max(0.0, min(10.0, new_importance))
        await db.commit()
        await db.refresh(memory)
    return memory


async def delete_memory(
    db: AsyncSession,
    memory_id: int,
    user_id: int,
) -> bool:
    """删除一条记忆"""
    result = await db.execute(
        select(AIMemory).where(
            AIMemory.id == memory_id,
            AIMemory.user_id == user_id,
        )
    )
    memory = result.scalar_one_or_none()
    if memory:
        await db.delete(memory)
        await db.commit()
        return True
    return False


async def decay_old_memories(db: AsyncSession, user_id: int) -> int:
    """衰减旧记忆的重要性：长时间未访问的记忆降低重要性"""
    result = await db.execute(
        select(AIMemory).where(
            AIMemory.user_id == user_id,
            AIMemory.access_count <= 1,
            AIMemory.importance > 1.0,
        )
    )
    memories = result.scalars().all()

    count = 0
    for m in memories:
        if m.last_accessed is None:
            m.importance = max(0.0, m.importance - 0.5)
            count += 1
        elif (datetime.utcnow() - m.last_accessed).days > 30:
            m.importance = max(0.0, m.importance - 1.0)
            count += 1

    if count > 0:
        await db.commit()

    return count


def build_memory_context_prompt(memories: List[Dict[str, Any]]) -> str:
    """构建包含记忆上下文的 system prompt 片段"""
    if not memories:
        return ""

    lines = ["\n## 关于用户的记忆\n"]
    for m in memories:
        mtype_label = {"preference": "偏好", "knowledge": "知识", "context": "上下文"}
        label = mtype_label.get(m.get("memory_type", ""), "信息")
        lines.append(f"- [{label}] {m.get('memory_key', '')}: {m.get('memory_value', '')}")

    return "\n".join(lines)


# ========== ConversationMemory CRUD ==========

async def get_conversation_memories(
    db: AsyncSession,
    user_id: int,
    memory_type: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """获取用户的所有对话记忆"""
    query = select(ConversationMemory).where(ConversationMemory.user_id == user_id)
    if memory_type:
        query = query.where(ConversationMemory.memory_type == memory_type)
    query = query.order_by(ConversationMemory.importance.desc(), ConversationMemory.updated_at.desc())

    result = await db.execute(query)
    memories = result.scalars().all()

    return [
        {
            "id": m.id,
            "memory_key": m.memory_key,
            "memory_value": m.memory_value,
            "memory_type": m.memory_type,
            "importance": m.importance,
            "last_recalled_at": m.last_recalled_at.isoformat() if m.last_recalled_at else None,
            "created_at": m.created_at.isoformat() if m.created_at else None,
            "updated_at": m.updated_at.isoformat() if m.updated_at else None,
        }
        for m in memories
    ]


async def get_conversation_memory_count(db: AsyncSession, user_id: int) -> int:
    """获取用户对话记忆数量"""
    result = await db.execute(
        select(func.count(ConversationMemory.id)).where(
            ConversationMemory.user_id == user_id
        )
    )
    return result.scalar() or 0


async def delete_all_conversation_memories(db: AsyncSession, user_id: int) -> int:
    """清除用户所有对话记忆"""
    result = await db.execute(
        delete(ConversationMemory).where(ConversationMemory.user_id == user_id)
    )
    await db.commit()
    return result.rowcount


# ========== 对话记忆提取与摘要 ==========

async def extract_memory_from_conversation(
    db: AsyncSession,
    conversation_id: int,
    user_id: int,
) -> Dict[str, Any]:
    """从对话中提取关键记忆并存储到 ConversationMemory

    Args:
        db: 数据库会话
        conversation_id: 对话ID
        user_id: 用户ID

    Returns:
        {"extracted": int, "stored": int, "memories": list}
    """
    # 获取对话消息
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
    )
    messages = result.scalars().all()

    if not messages:
        return {"extracted": 0, "stored": 0, "memories": []}

    # 构建消息列表
    msg_list = [{"role": m.role, "content": m.content} for m in messages]

    # 使用 AI 提取记忆
    extracted = await extract_memories(msg_list)

    if not extracted:
        return {"extracted": 0, "stored": 0, "memories": []}

    # 存储到 ConversationMemory
    stored_count = 0
    for item in extracted:
        key = item.get("key", "")
        value = item.get("value", "")
        mem_type = item.get("type", "context_hint")
        importance_raw = float(item.get("importance", 3.0))
        # 将 0-10 映射到 1-5
        importance = max(1, min(5, int(importance_raw / 2 + 0.5)))

        if not key or not value:
            continue

        # 检查是否已存在
        exist_result = await db.execute(
            select(ConversationMemory).where(
                ConversationMemory.user_id == user_id,
                ConversationMemory.memory_key == key,
            )
        )
        existing = exist_result.scalar_one_or_none()

        if existing:
            existing.memory_value = value
            existing.memory_type = mem_type
            existing.importance = max(existing.importance, importance)
        else:
            mem = ConversationMemory(
                user_id=user_id,
                memory_type=mem_type,
                memory_key=key,
                memory_value=value,
                importance=importance,
            )
            db.add(mem)

        stored_count += 1

    await db.commit()

    # 更新对话的 memory_keywords
    keywords = [item.get("key", "") for item in extracted if item.get("key")]
    await db.execute(
        update(Conversation)
        .where(Conversation.id == conversation_id)
        .values(memory_keywords=keywords)
    )
    await db.commit()

    logger.info(
        f"对话 {conversation_id} 记忆提取完成: 提取 {len(extracted)} 条, 存储 {stored_count} 条"
    )
    return {
        "extracted": len(extracted),
        "stored": stored_count,
        "memories": extracted,
    }


async def auto_summarize_conversation(
    db: AsyncSession,
    conversation_id: int,
) -> Optional[str]:
    """自动生成对话摘要

    当对话有 10+ 条消息时触发，使用 AI 生成摘要并存储到 conversation.memory_summary

    Args:
        db: 数据库会话
        conversation_id: 对话ID

    Returns:
        生成的摘要文本，或 None
    """
    # 获取对话消息
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
    )
    messages = result.scalars().all()

    if len(messages) < 10:
        return None

    # 构建对话文本
    text_parts = []
    for msg in messages[-30:]:  # 最多取最近30条
        role = "用户" if msg.role == "user" else "助手"
        content = (msg.content or "")[:300]
        text_parts.append(f"{role}: {content}")

    messages_text = "\n".join(text_parts)

    summary = await _call_ai_for_summarization(messages_text)

    if summary:
        await db.execute(
            update(Conversation)
            .where(Conversation.id == conversation_id)
            .values(memory_summary=summary)
        )
        await db.commit()
        logger.info(f"对话 {conversation_id} 摘要生成完成")

    return summary


async def _call_ai_for_summarization(messages_text: str) -> Optional[str]:
    """使用 AI 生成对话摘要"""
    from langchain_core.messages import SystemMessage, HumanMessage
    from langchain_ollama import ChatOllama
    from config.settings import settings

    system_prompt = """你是一个对话摘要生成器。请用2-3句话总结以下对话的主要内容，重点关注：
1. 用户的主要问题和需求
2. 涉及的财务/会计主题
3. 达成的结论或生成的凭证

只输出摘要文本，不要其他内容。"""

    try:
        import httpx
        model_name = None
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{settings.OLLAMA_BASE_URL}/api/tags")
            if resp.status_code == 200:
                models = [m["name"] for m in resp.json().get("models", [])]
                candidates = ["qwen2.5:1.5b", "qwen2.5:0.5b", "qwen3:0.6b"]
                for candidate in candidates:
                    if candidate in models:
                        model_name = candidate
                        break
                if not model_name and models:
                    model_name = sorted(models, key=len)[0]

        if not model_name:
            return None

        llm = ChatOllama(
            model=model_name,
            base_url=settings.OLLAMA_BASE_URL,
            temperature=0.0,
            timeout=15,
            num_predict=128,
        )
        response = await llm.ainvoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"请总结以下对话：\n\n{messages_text}"),
        ])
        return response.content.strip() if hasattr(response, "content") else str(response).strip()
    except Exception as e:
        logger.warning(f"AI 摘要生成失败: {e}")
        return None


# ========== 增强的上下文构建 ==========

def build_enhanced_context_prompt(
    memories: List[Dict[str, Any]],
    conversation_summary: Optional[str] = None,
) -> str:
    """构建增强的上下文 prompt，包含记忆和对话摘要

    Args:
        memories: 用户记忆列表
        conversation_summary: 当前对话摘要

    Returns:
        完整的上下文 prompt 片段
    """
    parts = []

    if memories:
        parts.append("\n## 关于用户的记忆\n")
        type_labels = {
            "user_preference": "偏好",
            "accounting_knowledge": "知识",
            "context_hint": "上下文",
            "preference": "偏好",
            "knowledge": "知识",
            "context": "上下文",
        }
        for m in memories:
            mtype = m.get("memory_type", "")
            label = type_labels.get(mtype, "信息")
            parts.append(
                f"- [{label}] {m.get('memory_key', '')}: {m.get('memory_value', '')}"
            )

    if conversation_summary:
        parts.append(f"\n## 当前对话摘要\n{conversation_summary}\n")

    return "\n".join(parts) if parts else ""