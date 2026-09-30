"""
对话管理 API 路由
提供对话的 CRUD 和消息持久化
"""
import logging
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func, update
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from database import get_db
from models.user import User
from models.conversation import Conversation, Message
from auth.middleware import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/conversations", tags=["对话管理"])


# ========== 请求/响应模型 ==========

class MessageResponse(BaseModel):
    id: int
    role: str
    content: str
    created_at: str

    class Config:
        from_attributes = True


class ConversationResponse(BaseModel):
    id: int
    title: str
    created_at: str
    updated_at: str
    message_count: int = 0

    class Config:
        from_attributes = True


class ConversationDetailResponse(ConversationResponse):
    messages: List[MessageResponse] = []


class CreateConversationRequest(BaseModel):
    title: Optional[str] = "新对话"


class AddMessageRequest(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str = Field(..., min_length=1)


class UpdateConversationRequest(BaseModel):
    title: Optional[str] = None


# ========== API 端点 ==========

@router.get("", response_model=List[ConversationResponse], summary="获取对话列表")
async def list_conversations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户的所有对话，按更新时间倒序"""
    # 子查询统计消息数量，避免懒加载触发 MissingGreenlet
    count_subq = (
        select(func.count(Message.id))
        .where(Message.conversation_id == Conversation.id)
        .correlate(Conversation)
        .scalar_subquery()
        .label("message_count")
    )
    result = await db.execute(
        select(Conversation, count_subq)
        .where(Conversation.user_id == current_user.id)
        .order_by(Conversation.updated_at.desc())
    )
    rows = result.all()
    return [
        ConversationResponse(
            id=c.id,
            title=c.title,
            created_at=c.created_at.isoformat(),
            updated_at=c.updated_at.isoformat(),
            message_count=count,
        )
        for c, count in rows
    ]


@router.post("", response_model=ConversationResponse, summary="创建新对话")
async def create_conversation(
    data: CreateConversationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建新的对话会话"""
    conv = Conversation(title=data.title or "新对话", user_id=current_user.id)
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return ConversationResponse(
        id=conv.id,
        title=conv.title,
        created_at=conv.created_at.isoformat(),
        updated_at=conv.updated_at.isoformat(),
        message_count=0,
    )


@router.get("/{conv_id}", response_model=ConversationDetailResponse, summary="获取对话详情")
async def get_conversation(
    conv_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取指定对话的详细信息，包含所有消息"""
    result = await db.execute(
        select(Conversation)
        .options(selectinload(Conversation.messages))
        .where(
            Conversation.id == conv_id,
            Conversation.user_id == current_user.id,
        )
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="对话不存在")

    return ConversationDetailResponse(
        id=conv.id,
        title=conv.title,
        created_at=conv.created_at.isoformat(),
        updated_at=conv.updated_at.isoformat(),
        message_count=len(conv.messages) if conv.messages else 0,
        messages=[
            MessageResponse(
                id=m.id,
                role=m.role,
                content=m.content,
                created_at=m.created_at.isoformat(),
            )
            for m in conv.messages
        ],
    )


@router.put("/{conv_id}", response_model=ConversationResponse, summary="更新对话")
async def update_conversation(
    conv_id: int,
    data: UpdateConversationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新对话标题"""
    result = await db.execute(
        select(Conversation)
        .options(selectinload(Conversation.messages))
        .where(
            Conversation.id == conv_id,
            Conversation.user_id == current_user.id,
        )
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="对话不存在")

    if data.title is not None:
        conv.title = data.title
    await db.commit()
    await db.refresh(conv)

    return ConversationResponse(
        id=conv.id,
        title=conv.title,
        created_at=conv.created_at.isoformat(),
        updated_at=conv.updated_at.isoformat(),
        message_count=len(conv.messages) if conv.messages else 0,
    )


@router.delete("/{conv_id}", summary="删除对话")
async def delete_conversation(
    conv_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除指定对话及其所有消息"""
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conv_id,
            Conversation.user_id == current_user.id,
        )
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="对话不存在")

    await db.delete(conv)
    await db.commit()
    return {"message": "对话已删除"}


@router.post("/{conv_id}/messages", response_model=MessageResponse, summary="添加消息")
async def add_message(
    conv_id: int,
    data: AddMessageRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """向指定对话添加一条消息"""
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conv_id,
            Conversation.user_id == current_user.id,
        )
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="对话不存在")

    msg = Message(conversation_id=conv_id, role=data.role, content=data.content)
    db.add(msg)

    # 手动更新对话的 updated_at（消息添加不会自动触发 onupdate）
    await db.execute(
        update(Conversation)
        .where(Conversation.id == conv_id)
        .values(updated_at=func.now())
    )

    # 如果对话标题还是默认的，用第一条用户消息作为标题
    if conv.title == "新对话" and data.role == "user":
        title = data.content[:30] + ("..." if len(data.content) > 30 else "")
        await db.execute(
            update(Conversation)
            .where(Conversation.id == conv_id)
            .values(title=title)
        )

    await db.commit()
    await db.refresh(msg)

    return MessageResponse(
        id=msg.id,
        role=msg.role,
        content=msg.content,
        created_at=msg.created_at.isoformat(),
    )