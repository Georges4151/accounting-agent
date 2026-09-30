"""
知识库管理 API 路由
提供文档上传、删除、搜索和索引管理功能
"""
import os
import logging
import shutil
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query, Form
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from database import get_db
from models.user import User
from models.knowledge_doc import KnowledgeDoc
from auth.middleware import get_current_user
from services.rag_service import KnowledgeBaseService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/knowledge", tags=["知识库管理"])

# 上传文件存储目录
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "docs", "uploads")

# 允许的文件类型
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md", ".csv"}


# ========== 请求/响应模型 ==========

class SearchRequest(BaseModel):
    """搜索请求体"""
    query: str = Field(..., min_length=1, description="搜索查询")
    top_k: int = Field(default=5, ge=1, le=20, description="返回结果数量")
    category: Optional[str] = Field(None, description="分类过滤")


class DocumentItem(BaseModel):
    """文档列表项"""
    id: int
    title: str
    category: str
    file_type: str
    file_size: int
    chunk_count: int
    is_indexed: bool
    uploaded_by: int
    created_at: str | None
    updated_at: str | None

    class Config:
        from_attributes = True


# ========== 辅助函数 ==========

def _ensure_upload_dir():
    """确保上传目录存在"""
    os.makedirs(UPLOAD_DIR, exist_ok=True)


def _is_allowed_file(filename: str) -> bool:
    """检查文件类型是否允许"""
    ext = os.path.splitext(filename)[1].lower()
    return ext in ALLOWED_EXTENSIONS


# ========== API 端点 ==========
# 注意: 静态路径必须放在动态参数路径之前

@router.post("/search", summary="测试搜索")
async def search_knowledge(
    search_req: SearchRequest,
    current_user: User = Depends(get_current_user),
):
    """测试知识库搜索，不经过 LLM，直接返回检索结果"""
    try:
        kb_service = KnowledgeBaseService()
        results = kb_service.search(
            query=search_req.query,
            top_k=search_req.top_k,
            category=search_req.category,
        )
        return {"results": results}
    except Exception as e:
        logger.error(f"知识库搜索失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"搜索失败: {str(e)}",
        )


@router.get("/stats", summary="索引统计")
async def get_stats(
    current_user: User = Depends(get_current_user),
):
    """获取知识库索引统计信息"""
    try:
        kb_service = KnowledgeBaseService()
        stats = kb_service.get_index_stats()
        return stats
    except Exception as e:
        logger.error(f"获取索引统计失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取统计信息失败: {str(e)}",
        )


@router.get("/categories", summary="获取文档分类列表")
async def get_categories(
    current_user: User = Depends(get_current_user),
):
    """获取知识库中所有文档的分类列表"""
    try:
        kb_service = KnowledgeBaseService()
        categories = kb_service.get_categories()
        return {"categories": categories}
    except Exception as e:
        logger.error(f"获取分类列表失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取分类列表失败: {str(e)}",
        )


@router.post("/rebuild", summary="重建索引")
async def rebuild_index(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """重建知识库索引"""
    try:
        kb_service = KnowledgeBaseService()

        # 查询数据库中所有文档的分类，构建 file_path → category 映射
        result = await db.execute(select(KnowledgeDoc))
        docs = result.scalars().all()
        category_map = {doc.file_path: doc.category for doc in docs if doc.file_path and doc.category}

        total_chunks = kb_service.rebuild_index(category_map=category_map)

        # 更新数据库中的文档索引状态
        result = await db.execute(select(KnowledgeDoc))
        docs = result.scalars().all()

        # 获取 ChromaDB 中各文档的 chunk 数量
        stats = kb_service.get_index_stats()
        # 通过 source 统计每个文件的 chunk 数
        try:
            all_data = kb_service._collection.get()
            file_chunk_counts: dict[str, int] = {}
            if all_data and all_data.get("metadatas"):
                for meta in all_data["metadatas"]:
                    src = meta.get("source", "")
                    if src:
                        file_chunk_counts[src] = file_chunk_counts.get(src, 0) + 1
        except Exception:
            file_chunk_counts = {}

        for doc in docs:
            if doc.file_path and doc.file_path in file_chunk_counts:
                doc.chunk_count = file_chunk_counts[doc.file_path]
                doc.is_indexed = True
            else:
                doc.chunk_count = 0
                doc.is_indexed = False
        await db.commit()

        logger.info(f"索引重建完成，共 {total_chunks} 个 chunk")
        return {"message": "索引重建完成", "total_chunks": total_chunks}
    except Exception as e:
        logger.error(f"重建索引失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"重建索引失败: {str(e)}",
        )


@router.post("/upload", summary="上传文档")
async def upload_document(
    file: UploadFile = File(...),
    category: Optional[str] = Form(None, description="文档分类"),
    title: Optional[str] = Form(None, description="文档标题"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """上传文档到知识库，自动索引"""
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="文件名不能为空",
        )

    if not _is_allowed_file(file.filename):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的文件类型，仅支持: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    # 使用默认分类
    doc_category = category or "未分类"

    _ensure_upload_dir()

    # 保存文件到磁盘
    safe_filename = file.filename.replace("\\", "/").split("/")[-1]
    file_path = os.path.join(UPLOAD_DIR, safe_filename)

    # 如果文件已存在，添加序号
    base, ext = os.path.splitext(safe_filename)
    counter = 1
    while os.path.exists(file_path):
        file_path = os.path.join(UPLOAD_DIR, f"{base}_{counter}{ext}")
        safe_filename = f"{base}_{counter}{ext}"
        counter += 1

    try:
        content = await file.read()
        file_size = len(content)
        with open(file_path, "wb") as f:
            f.write(content)
    except Exception as e:
        logger.error(f"保存文件失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"文件保存失败: {str(e)}",
        )

    # 确定文档标题
    doc_title = title or os.path.splitext(file.filename)[0]
    ext_lower = os.path.splitext(file.filename)[1].lower().lstrip(".")

    # 写入数据库记录
    try:
        doc = KnowledgeDoc(
            title=doc_title,
            category=doc_category,
            file_path=file_path,
            file_type=ext_lower,
            file_size=file_size,
            chunk_count=0,
            is_indexed=False,
            uploaded_by=current_user.id,
        )
        db.add(doc)
        await db.commit()
        await db.refresh(doc)
        doc_id = str(doc.id)
    except Exception as e:
        logger.error(f"写入数据库失败: {e}")
        # 清理已保存的文件
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"数据库写入失败: {str(e)}",
        )

    # 添加到 ChromaDB 索引
    try:
        kb_service = KnowledgeBaseService()
        chunk_count = kb_service.add_document(
            file_path=file_path,
            category=doc_category,
            doc_id=doc_id,
        )

        # 更新数据库中的 chunk_count 和 is_indexed
        doc.chunk_count = chunk_count
        doc.is_indexed = True
        await db.commit()

        logger.info(f"文档上传并索引完成: {safe_filename}, doc_id={doc_id}, chunks={chunk_count}")
        return {
            "message": "文档上传并索引成功",
            "doc_id": doc.id,
            "chunk_count": chunk_count,
            "title": doc_title,
            "filename": safe_filename,
        }
    except Exception as e:
        logger.error(f"添加到索引失败: {e}")
        # 索引失败但文件已保存，更新状态
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"文档索引失败（文件已保存）: {str(e)}",
        )


@router.get("/documents", summary="文档列表")
async def list_documents(
    category: Optional[str] = Query(None, description="按分类过滤"),
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取知识库文档列表"""
    try:
        # 构建查询
        query = select(KnowledgeDoc)
        count_query = select(func.count(KnowledgeDoc.id))

        if category:
            query = query.where(KnowledgeDoc.category == category)
            count_query = count_query.where(KnowledgeDoc.category == category)

        # 获取总数
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        # 分页查询
        offset = (page - 1) * page_size
        query = query.order_by(KnowledgeDoc.created_at.desc()).offset(offset).limit(page_size)
        result = await db.execute(query)
        docs = result.scalars().all()

        documents = []
        for doc in docs:
            documents.append({
                "id": doc.id,
                "title": doc.title,
                "category": doc.category,
                "file_type": doc.file_type,
                "file_size": doc.file_size,
                "chunk_count": doc.chunk_count,
                "is_indexed": doc.is_indexed,
                "uploaded_by": doc.uploaded_by,
                "source_url": doc.source_url,
                "last_fetched_at": doc.last_fetched_at.isoformat() if doc.last_fetched_at else None,
                "is_stale": doc.is_stale,
                "version": doc.version,
                "created_at": doc.created_at.isoformat() if doc.created_at else None,
                "updated_at": doc.updated_at.isoformat() if doc.updated_at else None,
            })

        return {
            "documents": documents,
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    except Exception as e:
        logger.error(f"获取文档列表失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取文档列表失败: {str(e)}",
        )


@router.delete("/documents/{doc_id}", summary="删除文档")
async def delete_document(
    doc_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除知识库文档（同时删除文件、数据库记录和索引）"""
    try:
        # 查找文档记录
        result = await db.execute(
            select(KnowledgeDoc).where(KnowledgeDoc.id == doc_id)
        )
        doc = result.scalar_one_or_none()

        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="文档不存在",
            )

        # 从 ChromaDB 索引中删除
        try:
            kb_service = KnowledgeBaseService()
            kb_service.delete_document(str(doc_id))
        except Exception as e:
            logger.warning(f"从索引中删除文档失败: {e}")

        # 删除磁盘文件
        if doc.file_path and os.path.exists(doc.file_path):
            try:
                os.remove(doc.file_path)
                logger.info(f"已删除文件: {doc.file_path}")
            except Exception as e:
                logger.warning(f"删除文件失败: {e}")

        # 删除数据库记录
        await db.delete(doc)
        await db.commit()

        logger.info(f"文档 {doc_id} 已删除: {doc.title}")
        return {"message": f"文档 '{doc.title}' 已删除"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除文档失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除文档失败: {str(e)}",
        )