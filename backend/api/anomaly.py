"""
异常检测 API 路由
提供财务数据异常检测功能
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.user import User
from auth.middleware import get_current_user
from auth.book_context import get_current_book
from models.book import Book
from services.anomaly_detector import detect_anomalies

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/anomalies", tags=["异常检测"])


class AnomalyItem(BaseModel):
    """异常项"""
    type: str = Field(..., description="异常类型: imbalance/large_amount/duplicate/negative_amount")
    severity: str = Field(..., description="严重程度: high/medium/low")
    voucher_id: int = Field(..., description="凭证ID")
    voucher_no: str = Field(..., description="凭证号")
    message: str = Field(..., description="异常描述")
    detail: str = Field(..., description="详细信息")


class AnomalyResponse(BaseModel):
    """异常检测响应体"""
    anomalies: list[dict] = Field(..., description="异常列表")
    total: int = Field(..., description="异常总数")


@router.get("", response_model=AnomalyResponse)
async def get_anomalies(
    book_id: Optional[int] = Query(None, description="账套ID"),
    period: Optional[str] = Query(None, description="会计期间，如 2026-08"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_book: Book = Depends(get_current_book),
):
    """检测财务数据中的异常，包括借贷不平衡、金额异常、重复凭证等"""
    effective_book_id = book_id or (current_book.id if current_book else None)
    anomalies = await detect_anomalies(
        db=db,
        book_id=effective_book_id,
        period=period,
    )
    return {"anomalies": anomalies, "total": len(anomalies)}