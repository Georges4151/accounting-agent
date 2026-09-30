"""
AI 智能建议 API 路由
提供科目编码智能推荐和摘要建议功能
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.user import User
from auth.middleware import get_current_user
from auth.book_context import get_current_book
from models.book import Book
from services.ai_suggestion_service import suggest_account_code, suggest_summary

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/suggestions", tags=["智能建议"])


class SuggestionRequest(BaseModel):
    """科目建议请求体"""
    description: str = Field(..., min_length=1, description="交易描述/摘要")
    amount: float = Field(default=0.0, description="交易金额")


class SuggestionResponse(BaseModel):
    """科目建议响应体"""
    account_code: str = Field(..., description="推荐科目编码")
    account_name: str = Field(..., description="推荐科目名称")
    confidence: float = Field(..., description="推荐置信度 0-1")
    reason: str = Field(..., description="推荐理由")
    source: Optional[str] = Field(None, description="建议来源: ai/rule")


class SummarySuggestionRequest(BaseModel):
    """摘要建议请求体"""
    account_code: str = Field(..., min_length=1, description="科目代码")
    partial_text: str = Field(default="", description="用户已输入的摘要片段")


class SummarySuggestionItem(BaseModel):
    """单条摘要建议"""
    summary: str = Field(..., description="建议的摘要文本")
    usage_count: int = Field(..., description="历史使用次数")
    relevance: float = Field(..., description="相关性得分 0-1")


class SummarySuggestionResponse(BaseModel):
    """摘要建议响应体"""
    suggestions: list[SummarySuggestionItem] = Field(default_factory=list, description="建议列表")


@router.post("/account-code", response_model=SuggestionResponse)
async def get_account_suggestion(
    req: SuggestionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_book: Book = Depends(get_current_book),
):
    """根据交易描述和金额，AI 智能推荐最合适的科目编码"""
    result = await suggest_account_code(
        description=req.description,
        amount=req.amount,
        db=db,
        user_id=current_user.id,
        book_id=current_book.id if current_book else None,
    )
    return result


@router.post("/summary", response_model=SummarySuggestionResponse)
async def get_summary_suggestion(
    req: SummarySuggestionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_book: Book = Depends(get_current_book),
):
    """根据科目代码，从历史分录中推荐常用摘要"""
    suggestions = await suggest_summary(
        account_code=req.account_code,
        partial_text=req.partial_text,
        db=db,
        book_id=current_book.id if current_book else None,
    )
    return {"suggestions": suggestions}