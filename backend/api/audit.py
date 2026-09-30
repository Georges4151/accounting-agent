"""
审计日志 API
提供审计日志的查询和筛选功能
"""
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select, func, desc, and_
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from auth.middleware import get_current_user
from auth.rbac import ROLE_PERMISSIONS
from models.user import User
from models.audit_log import AuditLog, AuditFieldChange

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/audit-logs", tags=["审计日志"])


class AuditLogResponse(BaseModel):
    id: int
    username: str
    action_type: str
    resource_type: str
    resource_id: Optional[int] = None
    detail: Optional[str] = None
    ip_address: str
    status: str
    created_at: Optional[str] = None
    operation_category: Optional[str] = None
    affected_resource_id: Optional[int] = None
    user_agent: Optional[str] = None
    response_status: Optional[int] = None


class AuditLogListResponse(BaseModel):
    items: list
    total: int
    page: int
    page_size: int


def _log_to_response(log: AuditLog) -> dict:
    """将 AuditLog ORM 对象转为前端期望的响应格式"""
    return {
        "id": log.id,
        "username": log.username,
        "action_type": log.action,
        "resource_type": log.resource,
        "resource_id": log.affected_resource_id,
        "detail": log.detail,
        "ip_address": log.ip_address,
        "status": log.status,
        "created_at": log.created_at.replace(tzinfo=timezone.utc).isoformat() if log.created_at else None,
        "operation_category": log.operation_category,
        "affected_resource_id": log.affected_resource_id,
        "user_agent": log.user_agent,
        "response_status": log.response_status,
    }


@router.get("", summary="查询审计日志")
async def list_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    username: Optional[str] = Query(None, description="按用户名筛选"),
    action_type: Optional[str] = Query(None, description="按操作类型筛选"),
    operation_category: Optional[str] = Query(None, description="按操作分类筛选"),
    start_time: Optional[str] = Query(None, description="开始时间 YYYY-MM-DD HH:mm:ss"),
    end_time: Optional[str] = Query(None, description="结束时间 YYYY-MM-DD HH:mm:ss"),
    status: Optional[str] = Query(None, description="按状态筛选: success/failure"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取审计日志列表，支持分页和多条件筛选"""
    # 权限检查：仅 admin 和 reviewer 可查看审计日志
    user_role = current_user.role
    allowed_roles = {"admin", "reviewer"}
    if user_role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="您没有查看审计日志的权限",
        )

    conditions = []

    if username:
        conditions.append(AuditLog.username.ilike(f"%{username}%"))
    if action_type:
        conditions.append(AuditLog.action == action_type)
    if operation_category:
        conditions.append(AuditLog.operation_category == operation_category)
    if status:
        conditions.append(AuditLog.status == status)
    if start_time:
        try:
            start_dt = datetime.fromisoformat(start_time)
            conditions.append(AuditLog.created_at >= start_dt)
        except (ValueError, TypeError):
            pass
    if end_time:
        try:
            end_dt = datetime.fromisoformat(end_time)
            conditions.append(AuditLog.created_at <= end_dt)
        except (ValueError, TypeError):
            pass

    where_clause = and_(*conditions) if conditions else None

    # 查询总数
    count_query = select(func.count(AuditLog.id))
    if where_clause is not None:
        count_query = count_query.where(where_clause)
    result = await db.execute(count_query)
    total = result.scalar() or 0

    # 查询列表
    query = select(AuditLog)
    if where_clause is not None:
        query = query.where(where_clause)
    query = query.order_by(desc(AuditLog.created_at)).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    logs = result.scalars().all()

    return {
        "items": [_log_to_response(log) for log in logs],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/stats", summary="审计日志统计")
async def get_audit_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取审计日志统计信息"""
    user_role = current_user.role
    if user_role not in {"admin", "reviewer"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="您没有查看审计日志的权限",
        )

    # 总日志数
    result = await db.execute(select(func.count(AuditLog.id)))
    total = result.scalar() or 0

    # 按操作类型统计
    result = await db.execute(
        select(AuditLog.action, func.count(AuditLog.id))
        .group_by(AuditLog.action)
    )
    action_stats = {row[0]: row[1] for row in result.all()}

    # 按状态统计
    result = await db.execute(
        select(AuditLog.status, func.count(AuditLog.id))
        .group_by(AuditLog.status)
    )
    status_stats = {row[0]: row[1] for row in result.all()}

    return {
        "total": total,
        "by_action": action_stats,
        "by_status": status_stats,
    }


@router.get("/{log_id}/field-changes", summary="查询审计日志的字段变更")
async def get_field_changes(
    log_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取指定审计日志的字段级变更记录"""
    user_role = current_user.role
    if user_role not in {"admin", "reviewer"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="您没有查看审计日志的权限",
        )

    # 检查日志是否存在
    log_result = await db.execute(select(AuditLog).where(AuditLog.id == log_id))
    log = log_result.scalar_one_or_none()
    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="审计日志不存在",
        )

    # 查询字段变更
    result = await db.execute(
        select(AuditFieldChange)
        .where(AuditFieldChange.audit_log_id == log_id)
        .order_by(AuditFieldChange.id)
    )
    changes = result.scalars().all()

    return {
        "log_id": log_id,
        "changes": [
            {
                "id": c.id,
                "field_name": c.field_name,
                "field_label": c.field_label or c.field_name,
                "old_value": c.old_value,
                "new_value": c.new_value,
            }
            for c in changes
        ],
    }


class RecordFieldChangeRequest(BaseModel):
    """记录字段变更请求"""
    log_id: int
    changes: list  # [{field_name, field_label, old_value, new_value}]


@router.post("/field-changes", summary="记录字段变更")
async def record_field_changes(
    body: RecordFieldChangeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """为审计日志记录字段级变更（内部使用）"""
    # 检查日志是否存在
    log_result = await db.execute(select(AuditLog).where(AuditLog.id == body.log_id))
    log = log_result.scalar_one_or_none()
    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="审计日志不存在",
        )

    for change in body.changes:
        fc = AuditFieldChange(
            audit_log_id=body.log_id,
            field_name=change.get("field_name", ""),
            field_label=change.get("field_label", ""),
            old_value=str(change.get("old_value", "")) if change.get("old_value") is not None else None,
            new_value=str(change.get("new_value", "")) if change.get("new_value") is not None else None,
        )
        db.add(fc)

    await db.flush()
    return {"message": f"已记录 {len(body.changes)} 条字段变更"}