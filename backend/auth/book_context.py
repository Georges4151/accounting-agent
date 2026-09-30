"""
账套上下文模块
提供当前账套的提取和设置功能
"""
import logging
from typing import Optional

from fastapi import Depends, HTTPException, status, Request, Header, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.book import Book, BookMember
from models.user import User
from auth.middleware import get_current_user

logger = logging.getLogger(__name__)


async def _check_member_or_admin(db: AsyncSession, book_id: int, user: User) -> bool:
    """检查用户是否为账套成员或管理员"""
    if user.role == "admin":
        return True
    member_result = await db.execute(
        select(BookMember).where(
            BookMember.book_id == book_id,
            BookMember.user_id == user.id,
            BookMember.is_active == True,
        )
    )
    return member_result.scalar_one_or_none() is not None


async def get_current_book(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    x_book_id: Optional[int] = Header(None, alias="X-Book-ID"),
    book_id_query: Optional[int] = Query(None, description="账套ID", alias="book_id"),
) -> Book:
    """从请求中提取当前账套

    优先级：
    1. X-Book-ID 请求头
    2. book_id 查询参数
    3. 当前用户的默认账套
    4. 系统中第一个活跃账套
    """
    target_book_id = x_book_id or book_id_query

    if target_book_id:
        result = await db.execute(
            select(Book).where(Book.id == target_book_id)
        )
        book = result.scalar_one_or_none()
        if book is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"账套不存在或已归档: {target_book_id}",
            )
        # 验证用户是否有权访问该账套
        if not await _check_member_or_admin(db, target_book_id, current_user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权访问该账套",
            )
        return book

    # 返回用户有权限的默认账套
    result = await db.execute(
        select(Book).where(Book.is_default == True, Book.status == "active")
    )
    book = result.scalar_one_or_none()
    if book and await _check_member_or_admin(db, book.id, current_user):
        return book

    # 返回用户有权限的第一个活跃账套
    result = await db.execute(
        select(Book).where(Book.status == "active").order_by(Book.id)
    )
    books = result.scalars().all()
    for book in books:
        if await _check_member_or_admin(db, book.id, current_user):
            return book

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="无权查看账套，请联系管理员将您添加到账套成员中",
    )


async def get_current_book_id(
    current_book: Book = Depends(get_current_book),
) -> int:
    """获取当前账套ID的便捷依赖"""
    return current_book.id


async def require_book_admin(
    current_user: User = Depends(get_current_user),
    current_book: Book = Depends(get_current_book),
    db: AsyncSession = Depends(get_db),
) -> Book:
    """要求当前用户是当前账套的管理员"""
    member_result = await db.execute(
        select(BookMember).where(
            BookMember.book_id == current_book.id,
            BookMember.user_id == current_user.id,
            BookMember.role == "admin",
            BookMember.is_active == True,
        )
    )
    member = member_result.scalar_one_or_none()
    if member is None and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要账套管理员权限",
        )
    return current_book