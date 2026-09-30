"""
知识库自动更新调度 API
提供手动触发更新、状态查询和日志查看
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from database import get_db
from models.user import User
from auth.middleware import get_current_user
from services.knowledge_scheduler import (
    run_scheduled_update,
    get_scheduler_status,
    get_update_logs,
    fetch_tax_policy_updates,
    check_knowledge_staleness,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/knowledge/scheduler", tags=["知识库自动更新"])


class SchedulerStatusResponse(BaseModel):
    is_running: bool
    last_run_at: Optional[str] = None
    next_run_at: Optional[str] = None
    update_count: int = 0
    error_count: int = 0
    last_result: Optional[dict] = None


@router.post("/trigger", summary="手动触发更新")
async def trigger_update(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
):
    """手动触发知识库自动更新（获取政策更新 + 检查过期）"""
    # 使用 BackgroundTasks 异步执行，不阻塞响应
    background_tasks.add_task(run_scheduled_update)
    logger.info(f"用户 {current_user.username} 手动触发知识库更新")
    return {"message": "知识库更新任务已触发", "status": "started"}


@router.get("/status", summary="获取调度器状态")
async def scheduler_status(
    current_user: User = Depends(get_current_user),
):
    """获取知识库自动更新调度器的当前状态"""
    return get_scheduler_status()


@router.get("/logs", summary="获取更新日志")
async def scheduler_logs(
    limit: int = Query(default=10, ge=1, le=50, description="返回日志数量"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取知识库更新日志（内存最近日志 + 数据库持久化日志）"""
    from models.knowledge_update_log import KnowledgeUpdateLog

    # 获取内存中的最近日志
    recent_logs = get_update_logs(limit)

    # 也从数据库查询持久化日志
    result = await db.execute(
        select(KnowledgeUpdateLog)
        .order_by(KnowledgeUpdateLog.created_at.desc())
        .limit(limit)
    )
    db_logs = result.scalars().all()

    db_logs_list = [
        {
            "id": log.id,
            "source_url": log.source_url,
            "status": log.status,
            "new_docs_count": log.new_docs_count,
            "error_message": log.error_message,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        }
        for log in db_logs
    ]

    return {
        "recent_logs": recent_logs,
        "persisted_logs": db_logs_list,
    }


@router.post("/fetch-policies", summary="仅获取政策更新")
async def fetch_policies(
    current_user: User = Depends(get_current_user),
):
    """仅执行政策更新获取（不检查过期）"""
    try:
        result = await fetch_tax_policy_updates()
        return result
    except Exception as e:
        logger.error(f"获取政策更新失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取政策更新失败: {str(e)}",
        )


@router.post("/check-staleness", summary="检查文档过期")
async def check_staleness(
    current_user: User = Depends(get_current_user),
):
    """检查并标记过期文档"""
    try:
        result = await check_knowledge_staleness()
        return result
    except Exception as e:
        logger.error(f"检查文档过期失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"检查文档过期失败: {str(e)}",
        )