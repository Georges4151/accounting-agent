"""
数据备份与恢复 API
提供数据库备份文件的创建、下载、恢复和删除功能
"""
import logging
import os
import shutil
import zipfile
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db, engine
from models.user import User
from auth.middleware import get_current_user, require_permission

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/backup", tags=["数据备份"])

# 备份文件存储目录
BACKUP_DIR = Path(__file__).resolve().parent.parent / "backups"


def _ensure_backup_dir():
    """确保备份目录存在"""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)


def _get_db_path() -> Path:
    """获取数据库文件路径"""
    from config.settings import settings
    db_url = settings.DATABASE_URL
    # 从 sqlite+aiosqlite:///xxx.db 提取路径
    if "///" in db_url:
        db_path = db_url.split("///", 1)[1]
        return Path(db_path) if Path(db_path).is_absolute() else Path(__file__).resolve().parent.parent / db_path
    return Path(__file__).resolve().parent.parent / "accounting.db"


def _get_backup_file_size(filepath: Path) -> str:
    """获取文件大小的可读表示"""
    size_bytes = filepath.stat().st_size
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


@router.post("/create", summary="创建备份")
async def create_backup(
    current_user: User = Depends(require_permission("report:export")),
    db: AsyncSession = Depends(get_db),
):
    """创建数据库备份，导出数据库文件为zip压缩包"""
    _ensure_backup_dir()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"backup_{timestamp}.zip"
    backup_path = BACKUP_DIR / backup_filename

    db_path = _get_db_path()

    if not db_path.exists():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"数据库文件不存在: {db_path}",
        )

    try:
        # 先执行 WAL checkpoint 确保所有数据写入主文件
        async with engine.begin() as conn:
            await conn.execute(text("PRAGMA wal_checkpoint(TRUNCATE)"))

        # 创建 zip 压缩包
        with zipfile.ZipFile(backup_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(db_path, db_path.name)

        file_size = _get_backup_file_size(backup_path)
        logger.info(f"用户 {current_user.username} 创建了数据库备份: {backup_filename} ({file_size})")

        return {
            "message": "备份创建成功",
            "filename": backup_filename,
            "size": file_size,
            "created_at": timestamp,
        }
    except Exception as e:
        logger.error(f"创建备份失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建备份失败: {str(e)}",
        )


@router.get("/list", summary="备份列表")
async def list_backups(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取所有备份文件列表"""
    _ensure_backup_dir()

    backups = []
    if BACKUP_DIR.exists():
        for f in sorted(BACKUP_DIR.glob("backup_*.zip"), key=lambda x: x.stat().st_mtime, reverse=True):
            stat = f.stat()
            backups.append({
                "filename": f.name,
                "size": _get_backup_file_size(f),
                "size_bytes": stat.st_size,
                "created_at": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
            })

    return {"items": backups, "total": len(backups)}


@router.get("/download/{filename}", summary="下载备份文件")
async def download_backup(
    filename: str,
    current_user: User = Depends(get_current_user),
):
    """下载指定的备份文件"""
    _ensure_backup_dir()

    # 安全检查：防止路径遍历攻击
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="无效的文件名")

    backup_path = BACKUP_DIR / filename
    if not backup_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="备份文件不存在")

    logger.info(f"用户 {current_user.username} 下载备份文件: {filename}")
    return FileResponse(
        path=str(backup_path),
        filename=filename,
        media_type="application/zip",
    )


@router.post("/restore", summary="上传备份文件恢复数据")
async def restore_backup(
    file: UploadFile = File(..., description="备份文件 (.zip)"),
    current_user: User = Depends(require_permission("voucher:delete")),
    db: AsyncSession = Depends(get_db),
):
    """上传备份文件并恢复数据库"""
    if not file.filename or not file.filename.endswith(".zip"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请上传 .zip 格式的备份文件",
        )

    _ensure_backup_dir()

    db_path = _get_db_path()
    temp_dir = BACKUP_DIR / "temp_restore"

    try:
        # 创建临时目录
        temp_dir.mkdir(parents=True, exist_ok=True)

        # 保存上传的文件
        content = await file.read()
        temp_zip = temp_dir / "restore.zip"
        with open(temp_zip, "wb") as f:
            f.write(content)

        # 解压
        with zipfile.ZipFile(temp_zip, "r") as zf:
            db_filename = None
            for name in zf.namelist():
                if name.endswith(".db"):
                    db_filename = name
                    break
            if not db_filename:
                # 尝试查找任何 .db 文件
                files = zf.namelist()
                if not files:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="备份文件中没有找到数据库文件",
                    )
                db_filename = files[0]

            zf.extract(db_filename, temp_dir)

        # 关闭所有数据库连接
        await engine.dispose()

        # 备份当前数据库（以防恢复失败）
        backup_of_current = BACKUP_DIR / f"pre_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        with zipfile.ZipFile(backup_of_current, "w", zipfile.ZIP_DEFLATED) as zf:
            if db_path.exists():
                zf.write(db_path, db_path.name)

        # 替换数据库文件
        extracted_db = temp_dir / db_filename
        shutil.copy2(extracted_db, db_path)

        logger.info(f"用户 {current_user.username} 恢复了数据库备份: {file.filename}")

        return {
            "message": "数据恢复成功，请重启服务以使更改生效",
            "backup_filename": file.filename,
            "pre_restore_backup": backup_of_current.name,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"恢复备份失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"恢复备份失败: {str(e)}",
        )
    finally:
        # 清理临时文件
        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)


@router.delete("/{filename}", summary="删除备份")
async def delete_backup(
    filename: str,
    current_user: User = Depends(require_permission("voucher:delete")),
):
    """删除指定的备份文件"""
    _ensure_backup_dir()

    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="无效的文件名")

    backup_path = BACKUP_DIR / filename
    if not backup_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="备份文件不存在")

    try:
        backup_path.unlink()
        logger.info(f"用户 {current_user.username} 删除了备份文件: {filename}")
        return {"message": "备份文件已删除"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除备份失败: {str(e)}",
        )