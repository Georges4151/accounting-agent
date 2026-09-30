"""
通知管理 API 路由
提供通知的查询、标记已读等功能
"""
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from database import get_db
from models.user import User
from models.notification import Notification
from auth.middleware import get_current_user, require_permission

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/notifications", tags=["通知管理"])


# ========== 响应模型 ==========

class NotificationResponse(BaseModel):
    """通知响应体"""
    id: int
    title: str
    content: str
    type: str
    category: str
    link: str | None = None
    is_read: bool
    read_at: str | None = None
    created_at: str | None = None

    class Config:
        from_attributes = True


class PaginatedNotificationResponse(BaseModel):
    """分页通知响应"""
    total: int
    page: int
    page_size: int
    items: list[NotificationResponse]


class UnreadCountResponse(BaseModel):
    """未读数量响应"""
    count: int


class SendNotificationRequest(BaseModel):
    """发送通知请求"""
    title: str = Field(..., min_length=1, max_length=200, description="通知标题")
    content: str = Field(..., min_length=1, description="通知内容")
    type: str = Field("info", description="info/warning/success/error")
    category: str = Field("system", description="system/voucher/invoice/approval/tax")
    link: str | None = Field(None, description="跳转链接")
    recipient_mode: str = Field("all", description="all / role / department / users")
    role: str | None = Field(None, description="按角色筛选时指定")
    department: str | None = Field(None, description="按部门筛选时指定")
    user_ids: list[int] | None = Field(None, description="指定用户ID列表")


# ========== 辅助函数 ==========

async def create_notification(
    db: AsyncSession,
    user_id: int,
    title: str,
    content: str,
    book_id: int | None = None,
    notif_type: str = "info",
    category: str = "system",
    link: str | None = None,
) -> Notification:
    """创建通知"""
    notification = Notification(
        user_id=user_id,
        book_id=book_id,
        title=title,
        content=content,
        type=notif_type,
        category=category,
        link=link,
    )
    db.add(notification)
    await db.flush()
    return notification


# ========== API 端点 ==========

@router.get("", response_model=PaginatedNotificationResponse, summary="获取通知列表")
async def list_notifications(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    unread_only: bool = Query(False, description="仅显示未读"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户的通知列表，支持分页和未读筛选"""
    query = select(Notification).where(Notification.user_id == current_user.id)
    count_query = select(func.count(Notification.id)).where(Notification.user_id == current_user.id)

    if unread_only:
        query = query.where(Notification.is_read == False)
        count_query = count_query.where(Notification.is_read == False)

    # 总数
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # 分页
    offset = (page - 1) * page_size
    query = query.order_by(Notification.created_at.desc()).offset(offset).limit(page_size)
    result = await db.execute(query)
    notifications = result.scalars().all()

    items = []
    for n in notifications:
        items.append(NotificationResponse(
            id=n.id,
            title=n.title,
            content=n.content,
            type=n.type,
            category=n.category,
            link=n.link,
            is_read=n.is_read,
            read_at=n.read_at.replace(tzinfo=timezone.utc).isoformat() if n.read_at else None,
            created_at=n.created_at.replace(tzinfo=timezone.utc).isoformat() if n.created_at else None,
        ))

    return PaginatedNotificationResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=items,
    )


@router.get("/unread-count", response_model=UnreadCountResponse, summary="获取未读数量")
async def get_unread_count(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户的未读通知数量"""
    result = await db.execute(
        select(func.count(Notification.id)).where(
            Notification.user_id == current_user.id,
            Notification.is_read == False,
        )
    )
    count = result.scalar() or 0
    return UnreadCountResponse(count=count)


@router.post("/read-all", summary="全部标记已读")
async def mark_all_as_read(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """标记当前用户的所有通知为已读"""
    result = await db.execute(
        select(Notification).where(
            Notification.user_id == current_user.id,
            Notification.is_read == False,
        )
    )
    unread_notifications = result.scalars().all()

    now = datetime.now(timezone.utc)
    for n in unread_notifications:
        n.is_read = True
        n.read_at = now

    await db.commit()
    logger.info(f"用户 {current_user.username} 标记了 {len(unread_notifications)} 条通知为已读")

    return {"message": f"已标记 {len(unread_notifications)} 条通知为已读", "count": len(unread_notifications)}


@router.post("/send", summary="管理员发送通知")
async def send_notification(
    req: SendNotificationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    管理员向指定用户发送通知

    支持四种发送模式：
    - all: 发送给所有活跃用户
    - role: 按角色筛选（需传 role 参数）
    - department: 按部门筛选（需传 department 参数）
    - users: 指定用户ID列表（需传 user_ids 参数）
    """
    # 权限检查
    if current_user.role not in ("admin", "accountant"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="仅管理员和会计可以发送通知",
        )

    # 查询目标用户
    query = select(User).where(User.is_active == True)

    if req.recipient_mode == "role":
        if not req.role:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="按角色发送时需指定 role 参数",
            )
        query = query.where(User.role == req.role)
    elif req.recipient_mode == "department":
        if not req.department:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="按部门发送时需指定 department 参数",
            )
        query = query.where(User.department == req.department)
    elif req.recipient_mode == "users":
        if not req.user_ids or len(req.user_ids) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="指定用户发送时需提供 user_ids 参数",
            )
        query = query.where(User.id.in_(req.user_ids))
    elif req.recipient_mode != "all":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的发送模式: {req.recipient_mode}",
        )

    result = await db.execute(query)
    target_users = result.scalars().all()

    if not target_users:
        return {"message": "没有符合条件的用户", "count": 0}

    # 批量创建通知
    for user in target_users:
        db.add(Notification(
            user_id=user.id,
            title=req.title,
            content=req.content,
            type=req.type,
            category=req.category,
            link=req.link,
        ))

    await db.commit()
    logger.info(
        f"管理员 {current_user.username} 发送通知: 模式={req.recipient_mode}, "
        f"标题={req.title}, 接收人数={len(target_users)}"
    )

    return {
        "message": f"通知已发送给 {len(target_users)} 位用户",
        "count": len(target_users),
    }


@router.post("/{notification_id}/read", summary="标记已读")
async def mark_as_read(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """标记单条通知为已读"""
    result = await db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == current_user.id,
        )
    )
    notification = result.scalar_one_or_none()
    if notification is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="通知不存在")

    notification.is_read = True
    notification.read_at = datetime.now(timezone.utc)
    await db.commit()

    return {"message": "已标记为已读"}