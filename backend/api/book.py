"""
账套管理 API
提供账套的 CRUD、成员管理和切换功能
"""
import logging
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status, Query, Header
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from database import get_db
from models.user import User
from models.book import Book, BookMember
from models.voucher import Account
from models.opening_balance import OpeningBalance
from auth.middleware import get_current_user, require_permission

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/books", tags=["账套管理"])

# ========== 标准科目列表 ==========

STANDARD_ACCOUNTS = [
    ("1001", "库存现金", "asset", "debit"),
    ("1002", "银行存款", "asset", "debit"),
    ("1012", "其他货币资金", "asset", "debit"),
    ("1101", "交易性金融资产", "asset", "debit"),
    ("1121", "应收票据", "asset", "debit"),
    ("1122", "应收账款", "asset", "debit"),
    ("1123", "预付账款", "asset", "debit"),
    ("1131", "应收股利", "asset", "debit"),
    ("1132", "应收利息", "asset", "debit"),
    ("1221", "其他应收款", "asset", "debit"),
    ("1231", "坏账准备", "asset", "credit"),
    ("1401", "材料采购", "asset", "debit"),
    ("1402", "在途物资", "asset", "debit"),
    ("1403", "原材料", "asset", "debit"),
    ("1405", "库存商品", "asset", "debit"),
    ("1411", "周转材料", "asset", "debit"),
    ("1471", "存货跌价准备", "asset", "credit"),
    ("1501", "债权投资", "asset", "debit"),
    ("1511", "长期股权投资", "asset", "debit"),
    ("1601", "固定资产", "asset", "debit"),
    ("1602", "累计折旧", "asset", "credit"),
    ("1603", "固定资产减值准备", "asset", "credit"),
    ("1604", "在建工程", "asset", "debit"),
    ("1605", "工程物资", "asset", "debit"),
    ("1606", "固定资产清理", "asset", "debit"),
    ("1701", "无形资产", "asset", "debit"),
    ("1702", "累计摊销", "asset", "credit"),
    ("1801", "长期待摊费用", "asset", "debit"),
    ("1901", "待处理财产损溢", "asset", "debit"),
    ("2001", "短期借款", "liability", "credit"),
    ("2201", "应付票据", "liability", "credit"),
    ("2202", "应付账款", "liability", "credit"),
    ("2203", "预收账款", "liability", "credit"),
    ("2211", "应付职工薪酬", "liability", "credit"),
    ("2221", "应交税费", "liability", "credit"),
    ("2231", "应付利息", "liability", "credit"),
    ("2232", "应付股利", "liability", "credit"),
    ("2241", "其他应付款", "liability", "credit"),
    ("2501", "长期借款", "liability", "credit"),
    ("2502", "应付债券", "liability", "credit"),
    ("2701", "长期应付款", "liability", "credit"),
    ("2901", "递延所得税负债", "liability", "credit"),
    ("4001", "实收资本", "equity", "credit"),
    ("4002", "资本公积", "equity", "credit"),
    ("4101", "盈余公积", "equity", "credit"),
    ("4103", "本年利润", "equity", "credit"),
    ("4104", "利润分配", "equity", "credit"),
    ("5001", "生产成本", "cost", "debit"),
    ("5101", "制造费用", "cost", "debit"),
    ("5201", "劳务成本", "cost", "debit"),
    ("5301", "研发支出", "cost", "debit"),
    ("6001", "主营业务收入", "revenue", "credit"),
    ("6051", "其他业务收入", "revenue", "credit"),
    ("6101", "公允价值变动损益", "revenue", "credit"),
    ("6111", "投资收益", "revenue", "credit"),
    ("6301", "营业外收入", "revenue", "credit"),
    ("6401", "主营业务成本", "expense", "debit"),
    ("6402", "其他业务成本", "expense", "debit"),
    ("6403", "税金及附加", "expense", "debit"),
    ("6601", "销售费用", "expense", "debit"),
    ("6602", "管理费用", "expense", "debit"),
    ("6603", "财务费用", "expense", "debit"),
    ("6701", "资产减值损失", "expense", "debit"),
    ("6711", "营业外支出", "expense", "debit"),
    ("6801", "所得税费用", "expense", "debit"),
]


# ========== 请求/响应模型 ==========

class BookCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="账套名称")
    code: str = Field(..., min_length=1, max_length=50, description="账套编码")
    company_name: Optional[str] = Field(None, max_length=200, description="公司全称")
    tax_id: Optional[str] = Field(None, max_length=50, description="统一社会信用代码")
    description: Optional[str] = Field(None, description="描述")
    fiscal_year_start: int = Field(1, ge=1, le=12, description="会计年度起始月")
    fiscal_year_end: int = Field(12, ge=1, le=12, description="会计年度结束月")
    currency: str = Field("CNY", max_length=10, description="币种")
    decimal_places: int = Field(2, ge=0, le=4, description="小数位数")


class BookUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="账套名称")
    company_name: Optional[str] = Field(None, max_length=200, description="公司全称")
    tax_id: Optional[str] = Field(None, max_length=50, description="统一社会信用代码")
    description: Optional[str] = Field(None, description="描述")
    fiscal_year_start: Optional[int] = Field(None, ge=1, le=12, description="会计年度起始月")
    fiscal_year_end: Optional[int] = Field(None, ge=1, le=12, description="会计年度结束月")
    currency: Optional[str] = Field(None, max_length=10, description="币种")
    decimal_places: Optional[int] = Field(None, ge=0, le=4, description="小数位数")


class AddMemberRequest(BaseModel):
    user_id: int = Field(..., description="用户ID")


class BatchAddMembersRequest(BaseModel):
    mode: str = Field(..., description="添加模式: role / department / users")
    role: Optional[str] = Field(None, description="按系统角色筛选（mode=role时必填）")
    department: Optional[str] = Field(None, description="按部门筛选（mode=department时必填）")
    user_ids: Optional[List[int]] = Field(None, description="指定用户ID列表（mode=users时必填）")


class BookResponse(BaseModel):
    id: int
    name: str
    code: str
    description: Optional[str]
    company_name: Optional[str]
    tax_id: Optional[str]
    fiscal_year_start: int
    fiscal_year_end: int
    currency: str
    decimal_places: int
    status: str
    is_default: bool
    created_by: int
    created_at: Optional[str]
    member_count: int = 0

    class Config:
        from_attributes = True


class BookMemberResponse(BaseModel):
    id: int
    book_id: int
    user_id: int
    username: str = ""
    real_name: str = ""
    role: str
    is_active: bool
    created_at: Optional[str]

    class Config:
        from_attributes = True


# ========== 辅助函数 ==========

async def _check_book_admin(db: AsyncSession, book_id: int, user: User) -> bool:
    """检查用户是否为指定账套的管理员（使用URL路径中的book_id，而非X-Book-ID头）"""
    if user.role == "admin":
        return True
    member_result = await db.execute(
        select(BookMember).where(
            BookMember.book_id == book_id,
            BookMember.user_id == user.id,
            BookMember.role == "admin",
            BookMember.is_active == True,
        )
    )
    return member_result.scalar_one_or_none() is not None


async def _seed_accounts_for_book(db: AsyncSession, book_id: int):
    """为新账套创建默认科目"""
    # 先检查是否已有该账套的科目
    from sqlalchemy import select, func
    result = await db.execute(
        select(func.count()).select_from(Account).where(Account.book_id == book_id)
    )
    count = result.scalar()
    if count > 0:
        return  # 该账套已有科目，跳过

    for code, name, atype, direction in STANDARD_ACCOUNTS:
        account = Account(
            account_code=code,
            account_name=name,
            account_type=atype,
            balance_direction=direction,
            book_id=book_id,
            is_active=True,
        )
        db.add(account)


# ========== API 端点 ==========

@router.get("", summary="获取账套列表")
async def list_books(
    include_archived: bool = Query(False, description="是否包含已归档的账套"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户有权访问的账套列表"""
    # 查询用户所属的账套
    member_query = select(BookMember.book_id).where(
        BookMember.user_id == current_user.id,
        BookMember.is_active == True,
    )
    member_result = await db.execute(member_query)
    book_ids = [row[0] for row in member_result.all()]

    # 管理员可以看到所有账套
    if current_user.role == "admin":
        book_ids = []

    query = select(Book)
    if not include_archived:
        query = query.where(Book.status == "active")
    if book_ids:
        query = query.where(Book.id.in_(book_ids))

    query = query.order_by(Book.is_default.desc(), Book.id)
    result = await db.execute(query)
    books = result.scalars().all()

    items = []
    for book in books:
        # 统计成员数
        count_result = await db.execute(
            select(func.count(BookMember.id)).where(
                BookMember.book_id == book.id,
                BookMember.is_active == True,
            )
        )
        member_count = count_result.scalar() or 0

        items.append(BookResponse(
            id=book.id,
            name=book.name,
            code=book.code,
            description=book.description,
            company_name=book.company_name,
            tax_id=book.tax_id,
            fiscal_year_start=book.fiscal_year_start,
            fiscal_year_end=book.fiscal_year_end,
            currency=book.currency,
            decimal_places=book.decimal_places,
            status=book.status,
            is_default=book.is_default,
            created_by=book.created_by,
            created_at=book.created_at.isoformat() if book.created_at else None,
            member_count=member_count,
        ))

    return {"books": items}


@router.post("", summary="创建账套")
async def create_book(
    book_data: BookCreate,
    current_user: User = Depends(require_permission("admin")),
    db: AsyncSession = Depends(get_db),
):
    """创建新账套（仅管理员）"""
    # 检查编码是否已存在
    result = await db.execute(select(Book).where(Book.code == book_data.code))
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="账套编码已存在",
        )

    book = Book(
        name=book_data.name,
        code=book_data.code,
        company_name=book_data.company_name,
        tax_id=book_data.tax_id,
        description=book_data.description,
        fiscal_year_start=book_data.fiscal_year_start,
        fiscal_year_end=book_data.fiscal_year_end,
        currency=book_data.currency,
        decimal_places=book_data.decimal_places,
        status="active",
        is_default=False,
        created_by=current_user.id,
    )
    db.add(book)
    await db.flush()

    # 自动创建默认科目
    await _seed_accounts_for_book(db, book.id)

    # 自动添加创建者为管理员
    member = BookMember(
        book_id=book.id,
        user_id=current_user.id,
        role="admin",
        is_active=True,
    )
    db.add(member)

    await db.commit()
    await db.refresh(book)

    logger.info(f"用户 {current_user.username} 创建了账套: {book.name} ({book.code})")

    return {
        "message": "账套创建成功",
        "book": BookResponse(
            id=book.id,
            name=book.name,
            code=book.code,
            description=book.description,
            company_name=book.company_name,
            tax_id=book.tax_id,
            fiscal_year_start=book.fiscal_year_start,
            fiscal_year_end=book.fiscal_year_end,
            currency=book.currency,
            decimal_places=book.decimal_places,
            status=book.status,
            is_default=book.is_default,
            created_by=book.created_by,
            created_at=book.created_at.isoformat() if book.created_at else None,
            member_count=1,
        ),
    }


@router.put("/{book_id}", summary="更新账套")
async def update_book(
    book_id: int,
    book_data: BookUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新账套信息"""
    # 权限检查：使用URL路径中的book_id
    if not await _check_book_admin(db, book_id, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要账套管理员权限",
        )

    result = await db.execute(select(Book).where(Book.id == book_id))
    book = result.scalar_one_or_none()
    if book is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="账套不存在")

    update_data = book_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(book, key, value)

    await db.commit()
    logger.info(f"用户 {current_user.username} 更新了账套: {book.name}")
    return {"message": "账套更新成功"}


@router.delete("/{book_id}", summary="归档账套")
async def archive_book(
    book_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    x_archive_token: str | None = Header(None, alias="X-Archive-Token"),
):
    """归档账套（软删除，需要 USB 密钥验证）"""
    from api.archive_key import _verify_token

    # 权限检查：使用URL路径中的book_id
    if not await _check_book_admin(db, book_id, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要账套管理员权限",
        )

    # USB 密钥验证
    if not x_archive_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="归档操作需要密钥验证，请插入 U 盘并提供密钥文件",
        )
    payload = _verify_token(x_archive_token, "archive")
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="密钥验证失败：令牌无效或已过期，请重新验证密钥文件",
        )

    result = await db.execute(select(Book).where(Book.id == book_id))
    book = result.scalar_one_or_none()
    if book is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="账套不存在")

    if book.is_default:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能归档默认账套",
        )

    book.status = "archived"
    await db.commit()
    logger.info(f"用户 {current_user.username} 通过密钥验证归档了账套: {book.name}")
    return {"message": "账套已归档"}


# ========== 成员管理 ==========

@router.get("/{book_id}/members", summary="获取账套成员")
async def list_book_members(
    book_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取账套成员列表"""
    # 验证账套存在
    result = await db.execute(select(Book).where(Book.id == book_id))
    book = result.scalar_one_or_none()
    if book is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="账套不存在")

    member_query = (
        select(BookMember, User.username, User.real_name)
        .join(User, BookMember.user_id == User.id)
        .where(BookMember.book_id == book_id, BookMember.is_active == True)
        .order_by(BookMember.id)
    )
    member_result = await db.execute(member_query)
    rows = member_result.all()

    members = []
    for row in rows:
        member = row[0]
        members.append(BookMemberResponse(
            id=member.id,
            book_id=member.book_id,
            user_id=member.user_id,
            username=row[1],
            real_name=row[2],
            role=member.role,
            is_active=member.is_active,
            created_at=member.created_at.isoformat() if member.created_at else None,
        ))

    return {"members": members}


@router.post("/{book_id}/members", summary="添加账套成员")
async def add_book_member(
    book_id: int,
    member_data: AddMemberRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """添加成员到账套（账套角色跟随用户系统角色）"""
    # 权限检查：使用URL路径中的book_id
    if not await _check_book_admin(db, book_id, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要账套管理员权限",
        )

    # 验证用户存在
    user_result = await db.execute(select(User).where(User.id == member_data.user_id))
    user = user_result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

    # 检查是否已是成员
    existing = await db.execute(
        select(BookMember).where(
            BookMember.book_id == book_id,
            BookMember.user_id == member_data.user_id,
        )
    )
    existing_member = existing.scalar_one_or_none()
    if existing_member:
        if existing_member.is_active:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="该用户已是账套成员",
            )
        else:
            # 重新激活
            existing_member.is_active = True
            existing_member.role = user.role
            await db.commit()
            return {"message": "成员已重新激活"}

    member = BookMember(
        book_id=book_id,
        user_id=member_data.user_id,
        role=user.role,
        is_active=True,
    )
    db.add(member)
    await db.commit()

    logger.info(f"用户 {current_user.username} 添加了成员 {user.username} 到账套 {book_id}，角色: {user.role}")
    return {"message": "成员添加成功"}


@router.post("/{book_id}/members/batch", summary="批量添加账套成员")
async def batch_add_book_members(
    book_id: int,
    batch_data: BatchAddMembersRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """批量添加成员到账套（按角色/部门/用户列表，账套角色跟随用户系统角色）"""
    # 权限检查：使用URL路径中的book_id
    if not await _check_book_admin(db, book_id, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要账套管理员权限",
        )

    # 根据模式确定目标用户
    if batch_data.mode == "role":
        if not batch_data.role:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="按角色模式需要指定 role 参数")
        user_query = select(User).where(User.role == batch_data.role)
    elif batch_data.mode == "department":
        if not batch_data.department:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="按部门模式需要指定 department 参数")
        user_query = select(User).where(User.department == batch_data.department)
    elif batch_data.mode == "users":
        if not batch_data.user_ids:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="按用户模式需要指定 user_ids 列表")
        user_query = select(User).where(User.id.in_(batch_data.user_ids))
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"无效的模式: {batch_data.mode}，支持: role / department / users",
        )

    user_result = await db.execute(user_query)
    target_users = user_result.scalars().all()

    if not target_users:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到符合条件的用户")

    # 查询已有成员
    existing_result = await db.execute(
        select(BookMember.user_id).where(BookMember.book_id == book_id)
    )
    existing_user_ids = {row[0] for row in existing_result.all()}

    # 批量添加
    added_count = 0
    skipped_count = 0
    for user in target_users:
        if user.id in existing_user_ids:
            skipped_count += 1
            continue
        member = BookMember(
            book_id=book_id,
            user_id=user.id,
            role=user.role,
            is_active=True,
        )
        db.add(member)
        added_count += 1

    await db.commit()

    logger.info(
        f"用户 {current_user.username} 批量添加成员到账套 {book_id}: "
        f"模式={batch_data.mode}, 新增={added_count}, 跳过={skipped_count}"
    )
    return {
        "message": f"批量添加完成: 新增 {added_count} 人，跳过 {skipped_count} 人（已是成员）",
        "added": added_count,
        "skipped": skipped_count,
    }


@router.delete("/{book_id}/members/{user_id}", summary="移除账套成员")
async def remove_book_member(
    book_id: int,
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """移除账套成员"""
    # 权限检查：使用URL路径中的book_id
    if not await _check_book_admin(db, book_id, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要账套管理员权限",
        )

    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能移除自己",
        )

    result = await db.execute(
        select(BookMember).where(
            BookMember.book_id == book_id,
            BookMember.user_id == user_id,
        )
    )
    member = result.scalar_one_or_none()
    if member is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="成员不存在")

    member.is_active = False
    await db.commit()
    logger.info(f"用户 {current_user.username} 移除了成员 {user_id} 从账套 {book_id}")
    return {"message": "成员已移除"}


@router.post("/{book_id}/switch", summary="切换当前账套")
async def switch_book(
    book_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """切换当前活跃账套（返回账套信息，前端存储在本地）"""
    result = await db.execute(
        select(Book).where(Book.id == book_id)
    )
    book = result.scalar_one_or_none()
    if book is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="账套不存在")

    # 验证用户权限
    member_result = await db.execute(
        select(BookMember).where(
            BookMember.book_id == book_id,
            BookMember.user_id == current_user.id,
            BookMember.is_active == True,
        )
    )
    member = member_result.scalar_one_or_none()
    if member is None and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问该账套",
        )

    return {
        "book": BookResponse(
            id=book.id,
            name=book.name,
            code=book.code,
            description=book.description,
            company_name=book.company_name,
            tax_id=book.tax_id,
            fiscal_year_start=book.fiscal_year_start,
            fiscal_year_end=book.fiscal_year_end,
            currency=book.currency,
            decimal_places=book.decimal_places,
            status=book.status,
            is_default=book.is_default,
            created_by=book.created_by,
            created_at=book.created_at.isoformat() if book.created_at else None,
            member_count=0,
        ),
    }


# ========== 期初余额管理 ==========

class OpeningBalanceItem(BaseModel):
    account_code: str
    account_name: str
    opening_debit: float = 0
    opening_credit: float = 0


class BatchOpeningBalanceRequest(BaseModel):
    fiscal_year: int = Field(..., description="会计年度")
    items: list[OpeningBalanceItem]


class OpeningBalanceResponse(BaseModel):
    id: int
    account_code: str
    account_name: str
    opening_debit: float
    opening_credit: float
    fiscal_year: int


@router.get("/{book_id}/opening-balances")
async def get_opening_balances(
    book_id: int,
    fiscal_year: int = Query(..., description="会计年度"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取账套期初余额"""
    await _check_book_admin(db, book_id, current_user)

    result = await db.execute(
        select(OpeningBalance)
        .where(
            OpeningBalance.book_id == book_id,
            OpeningBalance.fiscal_year == fiscal_year,
        )
        .order_by(OpeningBalance.account_code)
    )
    balances = result.scalars().all()

    return {
        "fiscal_year": fiscal_year,
        "items": [
            OpeningBalanceResponse(
                id=b.id,
                account_code=b.account_code,
                account_name=b.account_name,
                opening_debit=b.opening_debit,
                opening_credit=b.opening_credit,
                fiscal_year=b.fiscal_year,
            )
            for b in balances
        ],
        "total_debit": sum(b.opening_debit for b in balances),
        "total_credit": sum(b.opening_credit for b in balances),
        "is_balanced": abs(sum(b.opening_debit for b in balances) - sum(b.opening_credit for b in balances)) < 0.01,
    }


@router.post("/{book_id}/opening-balances")
async def save_opening_balances(
    book_id: int,
    data: BatchOpeningBalanceRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """批量保存期初余额"""
    await _check_book_admin(db, book_id, current_user)

    # 删除该账套该年度的现有期初余额
    await db.execute(
        OpeningBalance.__table__.delete().where(
            OpeningBalance.book_id == book_id,
            OpeningBalance.fiscal_year == data.fiscal_year,
        )
    )

    # 批量插入
    for item in data.items:
        if item.opening_debit == 0 and item.opening_credit == 0:
            continue
        db.add(OpeningBalance(
            book_id=book_id,
            account_code=item.account_code,
            account_name=item.account_name,
            opening_debit=item.opening_debit,
            opening_credit=item.opening_credit,
            fiscal_year=data.fiscal_year,
        ))

    await db.commit()

    return {
        "message": "期初余额保存成功",
        "count": len([i for i in data.items if i.opening_debit != 0 or i.opening_credit != 0]),
    }


@router.get("/{book_id}/opening-balances/trial-balance")
async def check_trial_balance(
    book_id: int,
    fiscal_year: int = Query(..., description="会计年度"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """试算平衡检查"""
    await _check_book_admin(db, book_id, current_user)

    result = await db.execute(
        select(OpeningBalance).where(
            OpeningBalance.book_id == book_id,
            OpeningBalance.fiscal_year == fiscal_year,
        )
    )
    balances = result.scalars().all()

    total_debit = sum(b.opening_debit for b in balances)
    total_credit = sum(b.opening_credit for b in balances)
    diff = round(total_debit - total_credit, 2)

    return {
        "fiscal_year": fiscal_year,
        "total_debit": total_debit,
        "total_credit": total_credit,
        "difference": diff,
        "is_balanced": abs(diff) < 0.01,
        "item_count": len(balances),
    }