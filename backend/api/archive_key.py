"""
归档密钥管理 API
USB 密钥文件生成、验证，用于敏感操作（如账套归档）的安全验证
"""
import hashlib
import json
import logging
import secrets
import subprocess
import time
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from config.settings import settings
from database import get_db
from models.user import User
from models.archive_key import ArchiveKey
from auth.middleware import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/archive-key", tags=["归档密钥"])

# 验证令牌有效期（秒）
TOKEN_TTL = 300  # 5 分钟


def _get_fernet():
    """获取 Fernet 加密实例"""
    from cryptography.fernet import Fernet
    return Fernet(settings.KEY_ENCRYPTION_KEY.encode())


def _create_verification_token(operation: str, book_id: int | None = None) -> str:
    """创建验证令牌"""
    payload = {
        "operation": operation,
        "book_id": book_id,
        "exp": int(time.time()) + TOKEN_TTL,
    }
    fernet = _get_fernet()
    return fernet.encrypt(json.dumps(payload).encode()).decode()


def _verify_token(token: str, operation: str) -> dict | None:
    """验证令牌，成功返回 payload，失败返回 None"""
    try:
        fernet = _get_fernet()
        payload = json.loads(fernet.decrypt(token.encode()).decode())
        if payload.get("operation") != operation:
            return None
        if payload.get("exp", 0) < int(time.time()):
            return None
        return payload
    except Exception:
        return None


class KeyStatusResponse(BaseModel):
    """密钥状态"""
    exists: bool
    key_label: str | None = None
    usb_bound: bool = False
    created_at: str | None = None
    last_used_at: str | None = None


class VerifyResponse(BaseModel):
    """验证结果"""
    success: bool
    token: str | None = None
    expires_in: int = TOKEN_TTL
    message: str


def _get_usb_drive_serials() -> list[dict]:
    """内部函数：检测已连接的 USB 存储设备，返回序列号列表"""
    drives = []
    try:
        ps_cmd = (
            'Get-PhysicalDisk | Where-Object {$_.BusType -eq "USB"} | '
            'Select-Object SerialNumber, FriendlyName, @{N="SizeGB";E={[math]::Round($_.Size/1GB,1)}} | '
            'ConvertTo-Json'
        )
        result = subprocess.run(
            ['powershell', '-NoProfile', '-Command', ps_cmd],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0 and result.stdout.strip():
            disks = json.loads(result.stdout)
            if isinstance(disks, dict):
                disks = [disks]

            volume_map = {}
            try:
                vol_result = subprocess.run(
                    ['powershell', '-NoProfile', '-Command',
                     'Get-Partition | Where-Object {$_.Type -eq "IFS"} | '
                     'Select-Object @{N="Serial";E={(Get-PhysicalDisk -DeviceNumber $_.DiskNumber).SerialNumber}}, @{N="Drive";E={$_.DriveLetter + ":"}} | '
                     'ConvertTo-Json'],
                    capture_output=True, text=True, timeout=10
                )
                if vol_result.returncode == 0 and vol_result.stdout.strip():
                    volumes = json.loads(vol_result.stdout)
                    if isinstance(volumes, dict):
                        volumes = [volumes]
                    for v in volumes:
                        serial = (v.get("Serial") or "").strip()
                        if serial:
                            volume_map[serial] = v.get("Drive", "")
            except Exception:
                pass

            for disk in disks:
                serial = (disk.get("SerialNumber") or "").strip()
                if not serial:
                    continue
                drives.append({
                    "serial_number": serial,
                    "friendly_name": disk.get("FriendlyName", "USB 存储设备"),
                    "size_gb": disk.get("SizeGB"),
                    "drive_letter": volume_map.get(serial, ""),
                })
    except subprocess.TimeoutExpired:
        logger.warning("USB 设备检测超时")
    except Exception as e:
        logger.warning(f"USB 设备检测失败: {e}")

    return drives


@router.get("/status", summary="查询密钥状态")
async def get_key_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """查询当前是否有活跃的归档密钥"""
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅管理员可查看密钥状态")

    result = await db.execute(
        select(ArchiveKey).where(ArchiveKey.is_active == True).order_by(ArchiveKey.created_at.desc())
    )
    key = result.scalars().first()

    if not key:
        return KeyStatusResponse(exists=False)

    return KeyStatusResponse(
        exists=True,
        key_label=key.key_label,
        usb_bound=key.usb_serial_hash is not None,
        created_at=key.created_at.isoformat() if key.created_at else None,
        last_used_at=key.last_used_at.isoformat() if key.last_used_at else None,
    )


@router.get("/usb-drives", summary="检测已连接的 USB 存储设备")
async def detect_usb_drives(
    current_user: User = Depends(get_current_user),
):
    """
    自动检测当前系统已连接的 USB 存储设备（Windows）
    返回设备列表，包含序列号、型号、容量、盘符等信息
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅管理员可检测 USB 设备")

    drives = _get_usb_drive_serials()
    return {"drives": drives}


@router.post("/generate", summary="生成归档密钥文件")
async def generate_key(
    key_label: str = "默认密钥",
    usb_serial: str | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    生成新的归档密钥文件（.key 格式）
    密钥文件是加密的，需保存到 U 盘用于后续归档验证

    参数：
    - key_label: 密钥标签
    - usb_serial: U 盘序列号（可选，用于绑定密钥到特定 U 盘）

    注意：生成新密钥后，旧密钥将自动失效
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅管理员可生成密钥")

    # 生成随机密钥
    raw_key = secrets.token_hex(32)
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

    # U 盘序列号哈希
    usb_serial_hash = None
    if usb_serial:
        usb_serial = usb_serial.strip().upper()
        if usb_serial:
            usb_serial_hash = hashlib.sha256(usb_serial.encode()).hexdigest()

    # 将旧密钥标记为失效
    old_keys = await db.execute(
        select(ArchiveKey).where(ArchiveKey.is_active == True)
    )
    for old in old_keys.scalars().all():
        old.is_active = False

    # 保存新密钥哈希
    db.add(ArchiveKey(
        key_hash=key_hash,
        usb_serial_hash=usb_serial_hash,
        key_label=key_label,
        is_active=True,
        created_by=current_user.id,
    ))
    await db.commit()

    # 加密密钥文件内容（将序列号也嵌入密钥文件）
    file_payload = json.dumps({
        "key": raw_key,
        "usb_serial": usb_serial or "",
    })
    fernet = _get_fernet()
    encrypted_key = fernet.encrypt(file_payload.encode())

    logger.info(
        f"管理员 {current_user.username} 生成了新的归档密钥: {key_label}"
        + (f"，已绑定U盘序列号" if usb_serial_hash else "")
    )

    return Response(
        content=encrypted_key,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f"attachment; filename=archive_key_{datetime.now().strftime('%Y%m%d')}.key"
        },
    )


@router.post("/verify", summary="验证归档密钥文件")
async def verify_key(
    operation: str = "archive",
    book_id: int | None = None,
    key_file: UploadFile = File(..., description="从 U 盘上传的 .key 密钥文件"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    验证上传的密钥文件是否有效

    支持的操作类型（operation）：
    - archive: 账套归档

    参数：
    - key_file: 密钥文件

    如果密钥已绑定 U 盘，服务器会自动检测当前连接的 USB 设备序列号进行比对，
    序列号不会传输到前端。

    验证通过后返回一个有时效的令牌（token），用于后续敏感操作
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅管理员可验证密钥")

    # 读取上传文件
    file_content = await key_file.read()

    if not file_content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="密钥文件为空",
        )

    # 解密文件
    try:
        fernet = _get_fernet()
        file_payload = json.loads(fernet.decrypt(file_content).decode())
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="密钥文件无效：无法解密，请确认文件未被损坏",
        )

    # 兼容旧版密钥文件格式（纯文本密钥）
    if isinstance(file_payload, str):
        raw_key = file_payload
    else:
        raw_key = file_payload.get("key", "")

    # 哈希比对
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

    result = await db.execute(
        select(ArchiveKey).where(
            ArchiveKey.key_hash == key_hash,
            ArchiveKey.is_active == True,
        )
    )
    matched_key = result.scalar_one_or_none()

    if not matched_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="密钥验证失败：密钥不匹配或已失效",
        )

    # U 盘序列号校验 —— 服务端自动检测，不经过前端
    if matched_key.usb_serial_hash:
        usb_drives = _get_usb_drive_serials()
        if not usb_drives:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="此密钥已绑定 U 盘，但未检测到 USB 设备，请插入绑定的 U 盘后重试",
            )

        matched_usb = False
        for drive in usb_drives:
            drive_hash = hashlib.sha256(drive["serial_number"].strip().upper().encode()).hexdigest()
            if drive_hash == matched_key.usb_serial_hash:
                matched_usb = True
                logger.info(f"U 盘序列号匹配: {drive['friendly_name']} ({drive['drive_letter']})")
                break

        if not matched_usb:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="U 盘序列号不匹配：请使用绑定的 U 盘",
            )

    # 更新最后使用时间
    matched_key.last_used_at = datetime.now()
    await db.commit()

    # 生成验证令牌
    token = _create_verification_token(operation=operation, book_id=book_id)

    logger.info(
        f"管理员 {current_user.username} 验证归档密钥成功，"
        f"操作类型: {operation}, 账套ID: {book_id}"
        + (f"，U盘序列号已验证" if matched_key.usb_serial_hash else "")
    )

    return VerifyResponse(
        success=True,
        token=token,
        expires_in=TOKEN_TTL,
        message="密钥验证通过，请在 5 分钟内完成操作",
    )