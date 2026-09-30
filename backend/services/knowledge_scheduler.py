"""
知识库自动更新调度服务
后台定期检查税务政策更新，更新知识库文档
"""
import logging
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

import httpx
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from models.knowledge_doc import KnowledgeDoc
from models.knowledge_update_log import KnowledgeUpdateLog
from database import async_session_maker

logger = logging.getLogger(__name__)

# 税务政策更新数据源
TAX_POLICY_SOURCES = [
    {
        "url": "https://www.chinatax.gov.cn/chinatax/n810341/n810755/index.html",
        "name": "国家税务总局-最新政策",
        "category": "税务政策",
    },
    {
        "url": "https://www.mof.gov.cn/zhengwuxinxi/caizhengxinwen/",
        "name": "财政部-财政新闻",
        "category": "财政政策",
    },
]

# 调度器状态
_scheduler_status: Dict[str, Any] = {
    "is_running": False,
    "last_run_at": None,
    "last_result": None,
    "next_run_at": None,
    "update_count": 0,
    "error_count": 0,
}

# 更新日志（内存缓存最近 50 条）
_update_logs: List[Dict[str, Any]] = []


def _add_log(source_url: str, status: str, new_docs_count: int = 0, error_message: str = None):
    """添加一条更新日志"""
    log = {
        "source_url": source_url,
        "status": status,
        "new_docs_count": new_docs_count,
        "error_message": error_message,
        "created_at": datetime.now().isoformat(),
    }
    _update_logs.insert(0, log)
    # 保留最近 50 条
    if len(_update_logs) > 50:
        _update_logs.pop()


async def _persist_log(
    source_url: str,
    status: str,
    new_docs_count: int = 0,
    error_message: str = None,
):
    """持久化更新日志到数据库"""
    try:
        async with async_session_maker() as db:
            log = KnowledgeUpdateLog(
                source_url=source_url,
                status=status,
                new_docs_count=new_docs_count,
                error_message=error_message,
            )
            db.add(log)
            await db.commit()
    except Exception as e:
        logger.warning(f"持久化更新日志失败: {e}")


async def fetch_tax_policy_updates() -> Dict[str, Any]:
    """从税务政策数据源获取更新

    使用 httpx 异步获取政策页面，提取新内容并存储到 KnowledgeDoc

    Returns:
        {"total_checked": int, "new_docs": int, "errors": int}
    """
    total_checked = 0
    new_docs = 0
    errors = 0

    for source in TAX_POLICY_SOURCES:
        total_checked += 1
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }
                resp = await client.get(source["url"], headers=headers)

                if resp.status_code != 200:
                    logger.warning(
                        f"获取 {source['name']} 失败: HTTP {resp.status_code}"
                    )
                    _add_log(source["url"], "failed", error_message=f"HTTP {resp.status_code}")
                    await _persist_log(source["url"], "failed", error_message=f"HTTP {resp.status_code}")
                    errors += 1
                    continue

                # 从 HTML 中提取标题和链接
                content = resp.text
                extracted = _extract_policy_links(content, source["url"])

                if not extracted:
                    _add_log(source["url"], "success", new_docs_count=0)
                    await _persist_log(source["url"], "success", new_docs_count=0)
                    continue

                # 检查是否已存在（通过 source_url 去重）
                stored_count = 0
                async with async_session_maker() as db:
                    for item in extracted[:5]:  # 最多存储 5 条新政策
                        exists = await _check_source_exists(db, item["url"])
                        if not exists:
                            doc = KnowledgeDoc(
                                title=item["title"],
                                category=source["category"],
                                file_path=f"remote://{item['url']}",
                                file_type="url",
                                file_size=0,
                                chunk_count=0,
                                is_indexed=False,
                                uploaded_by=1,  # 系统用户
                                source_url=item["url"],
                                last_fetched_at=func.now(),
                                is_stale=False,
                            )
                            db.add(doc)
                            stored_count += 1
                    await db.commit()

                new_docs += stored_count
                _add_log(source["url"], "success", new_docs_count=stored_count)
                await _persist_log(source["url"], "success", new_docs_count=stored_count)
                logger.info(
                    f"从 {source['name']} 提取 {len(extracted)} 条政策，新增 {stored_count} 条"
                )

        except httpx.TimeoutException:
            logger.warning(f"获取 {source['name']} 超时")
            _add_log(source["url"], "failed", error_message="请求超时")
            await _persist_log(source["url"], "failed", error_message="请求超时")
            errors += 1
        except Exception as e:
            logger.error(f"获取 {source['name']} 异常: {e}")
            _add_log(source["url"], "failed", error_message=str(e)[:500])
            await _persist_log(source["url"], "failed", error_message=str(e)[:500])
            errors += 1

    result = {
        "total_checked": total_checked,
        "new_docs": new_docs,
        "errors": errors,
    }
    _scheduler_status["last_result"] = result
    _scheduler_status["update_count"] += 1
    return result


def _extract_policy_links(html: str, base_url: str) -> List[Dict[str, str]]:
    """从 HTML 中提取政策链接

    Args:
        html: 页面 HTML 内容
        base_url: 基础 URL

    Returns:
        [{"title": str, "url": str}, ...]
    """
    import re

    results = []
    # 匹配 <a> 标签中的标题和链接
    pattern = re.compile(
        r'<a[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
        re.IGNORECASE | re.DOTALL,
    )

    for match in pattern.finditer(html):
        url = match.group(1)
        title_raw = match.group(2)

        # 清理 HTML 标签
        title = re.sub(r'<[^>]+>', '', title_raw).strip()

        # 过滤：只保留有意义的政策标题
        if not title or len(title) < 5:
            continue
        if not _is_policy_related(title):
            continue

        # 处理相对路径
        if url.startswith("/"):
            from urllib.parse import urljoin
            url = urljoin(base_url, url)
        elif not url.startswith("http"):
            continue

        results.append({"title": title, "url": url})

    return results


def _is_policy_related(title: str) -> bool:
    """判断标题是否与税务/财政政策相关"""
    keywords = [
        "税", "政策", "公告", "通知", "规定", "办法",
        "增值税", "所得税", "个税", "印花税", "减免",
        "优惠", "税率", "申报", "缴纳", "退税",
        "财政", "预算", "采购", "补贴",
    ]
    return any(kw in title for kw in keywords)


async def _check_source_exists(db: AsyncSession, source_url: str) -> bool:
    """检查某个来源 URL 是否已存在于知识库"""
    result = await db.execute(
        select(func.count(KnowledgeDoc.id)).where(
            KnowledgeDoc.source_url == source_url
        )
    )
    count = result.scalar() or 0
    return count > 0


async def check_knowledge_staleness() -> Dict[str, Any]:
    """检查知识库文档是否过时

    标记超过 30 天未更新的文档为 stale

    Returns:
        {"checked": int, "stale_count": int}
    """
    stale_threshold = datetime.now() - timedelta(days=30)

    async with async_session_maker() as db:
        # 查询 source_url 不为空且超过 30 天未获取的文档
        result = await db.execute(
            select(KnowledgeDoc).where(
                KnowledgeDoc.source_url.isnot(None),
                KnowledgeDoc.source_url != "",
                KnowledgeDoc.is_stale == False,
            )
        )
        docs = result.scalars().all()

        stale_count = 0
        for doc in docs:
            last_fetched = doc.last_fetched_at or doc.created_at
            if last_fetched and last_fetched < stale_threshold:
                doc.is_stale = True
                stale_count += 1

        # 同时检查没有 source_url 的文档（上传的文档），如果超过 30 天未更新
        result2 = await db.execute(
            select(KnowledgeDoc).where(
                (KnowledgeDoc.source_url.is_(None) | (KnowledgeDoc.source_url == "")),
                KnowledgeDoc.is_stale == False,
            )
        )
        docs2 = result2.scalars().all()

        for doc in docs2:
            last_updated = doc.updated_at or doc.created_at
            if last_updated and last_updated < stale_threshold:
                doc.is_stale = True
                stale_count += 1

        await db.commit()

    logger.info(f"知识库过期检查: 检查 {len(docs) + len(docs2)} 个文档, 标记 {stale_count} 个过期")
    return {"checked": len(docs) + len(docs2), "stale_count": stale_count}


async def run_scheduled_update():
    """执行定时更新任务（获取政策更新 + 检查过期）"""
    if _scheduler_status["is_running"]:
        logger.info("上一次更新任务仍在运行，跳过")
        return

    _scheduler_status["is_running"] = True
    _scheduler_status["last_run_at"] = datetime.now().isoformat()

    try:
        # 1. 获取政策更新
        fetch_result = await fetch_tax_policy_updates()
        logger.info(f"政策更新获取完成: {fetch_result}")

        # 2. 检查过期文档
        stale_result = await check_knowledge_staleness()
        logger.info(f"过期文档检查完成: {stale_result}")

        _scheduler_status["error_count"] = 0
    except Exception as e:
        logger.error(f"定时更新任务失败: {e}")
        _scheduler_status["error_count"] += 1
    finally:
        _scheduler_status["is_running"] = False
        # 设置下次运行时间（24小时后）
        _scheduler_status["next_run_at"] = (datetime.now() + timedelta(hours=24)).isoformat()


def get_scheduler_status() -> Dict[str, Any]:
    """获取调度器状态"""
    return {
        **_scheduler_status,
        "recent_logs": _update_logs[:10],  # 最近 10 条日志
    }


def get_update_logs(limit: int = 10) -> List[Dict[str, Any]]:
    """获取更新日志"""
    return _update_logs[:limit]


async def startup_scheduler(interval_hours: int = 24):
    """启动后台调度器（在 app lifespan 中调用）

    Args:
        interval_hours: 检查间隔（小时），默认 24 小时
    """
    logger.info(f"知识库自动更新调度器已启动，间隔 {interval_hours} 小时")

    async def _loop():
        # 启动后延迟 60 秒再执行首次检查
        await asyncio.sleep(60)
        while True:
            try:
                await run_scheduled_update()
            except Exception as e:
                logger.error(f"调度器执行异常: {e}")
            await asyncio.sleep(interval_hours * 3600)

    asyncio.create_task(_loop())
    logger.info("知识库自动更新后台任务已创建")