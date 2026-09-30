"""
AI 记忆 API 路由
提供记忆的 CRUD 操作
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from database import get_db
from models.user import User
from auth.middleware import get_current_user
from services.memory_service import (
    get_all_memories,
    update_memory_importance,
    delete_memory,
    delete_all_conversation_memories,
    get_conversation_memory_count,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/memories", tags=["AI记忆"])


class UpdateImportanceRequest(BaseModel):
    importance: float = Field(..., ge=0, le=10, description="重要性 0-10")


@router.get("", summary="获取记忆列表")
async def list_memories(
    memory_type: Optional[str] = Query(None, description="记忆类型过滤"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户的所有记忆（包括 AIMemory 和 ConversationMemory）"""
    ai_memories = await get_all_memories(db, current_user.id, memory_type)
    # 同时获取 ConversationMemory
    from services.memory_service import get_conversation_memories as get_cm
    cm_memories = await get_cm(db, current_user.id, memory_type)
    # 合并去重
    result = list(ai_memories)
    existing_keys = {m["memory_key"] for m in result}
    for cm in cm_memories:
        if cm["memory_key"] not in existing_keys:
            result.append(cm)
    return result


@router.delete("/clear", summary="清除所有记忆")
async def clear_all_memories(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """清除当前用户的所有记忆"""
    from models.ai_memory import AIMemory
    from sqlalchemy import delete as sa_delete

    # 删除 AIMemory
    result1 = await db.execute(
        sa_delete(AIMemory).where(AIMemory.user_id == current_user.id)
    )
    # 删除 ConversationMemory
    count2 = await delete_all_conversation_memories(db, current_user.id)
    await db.commit()
    count1 = result1.rowcount
    total = count1 + count2
    return {"message": f"已清除 {total} 条记忆", "count": total}


@router.patch("/{memory_id}/importance", summary="更新记忆重要性")
async def set_importance(
    memory_id: int,
    req: UpdateImportanceRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新一条记忆的重要性"""
    memory = await update_memory_importance(
        db, memory_id, current_user.id, req.importance
    )
    if not memory:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="记忆不存在")
    return {"message": "已更新", "importance": memory.importance}


@router.delete("/{memory_id}", summary="删除记忆")
async def remove_memory(
    memory_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除一条记忆"""
    success = await delete_memory(db, memory_id, current_user.id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="记忆不存在")
    return {"message": "记忆已删除"}