"""
RAG（检索增强生成）知识库服务
基于 ChromaDB 向量数据库，提供文档索引和语义检索
"""
import os
import re
import uuid
import time
import logging
from typing import List, Dict, Any, Optional, Tuple

import chromadb
from chromadb.config import Settings as ChromaSettings
from chromadb.api.types import EmbeddingFunction, Embeddings

import fitz  # PyMuPDF，PDF 文本提取能力远超 PyPDF2/pypdf

from langchain_ollama import OllamaEmbeddings
from langchain_community.document_loaders import Docx2txtLoader, TextLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from config.settings import settings

logger = logging.getLogger(__name__)

# 查询缓存：key=查询文本, value=(timestamp, results)
_search_cache: Dict[str, tuple] = {}
_CACHE_MAX_SIZE = 100
_CACHE_TTL = 300  # 缓存有效期 5 分钟

# 表格检测正则：匹配包含多个 | 或 制表符的行（Markdown表格 / TSV）
_TABLE_ROW_PATTERN = re.compile(r'\|.*\|.*\|')  # Markdown 表格行
_TABLE_SEPARATOR_PATTERN = re.compile(r'\|[\s\-:]+\|')  # 表格分隔行

# 会导致 bge-m3 等 embedding 模型返回 NaN 的特殊字符
_NAN_TRIGGER_CHARS = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f\u200b-\u200f\u2028-\u202f\ufeff\ufff0-\uffff]')
# 非中文/英文/数字/常用标点的字符（emoji、特殊符号等）
_SPECIAL_SYMBOL_PATTERN = re.compile(r'[^\u4e00-\u9fff\u3000-\u303f\uff00-\uffefa-zA-Z0-9\s\.\,\;\:\!\?\-\+\=\(\)\[\]\{\}\/\\@#\$%\^&\*\_\~\`\|\"\'\<\>\n\r]')


def _clean_chunk_content(text: str) -> str:
    """清理 chunk 内容：移除导致 embedding NaN 的字符，规范化空白"""
    # 1. 移除控制字符和零宽字符（会导致 NaN）
    text = _NAN_TRIGGER_CHARS.sub(' ', text)
    # 2. 将特殊符号替换为空格（⚠ ✓ ° 等）
    text = _SPECIAL_SYMBOL_PATTERN.sub(' ', text)
    # 3. 合并连续空白
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    # 4. 去除首尾空白
    return text.strip()


def _merge_short_chunks(chunks: List[str], min_len: int = 50) -> List[str]:
    """合并过短的 chunk 到相邻 chunk，避免孤立标题/碎片"""
    if len(chunks) <= 1:
        return chunks

    merged = []
    buffer = ""

    for c in chunks:
        c = c.strip()
        if not c:
            continue

        if len(c) < min_len:
            # 短 chunk 合并到 buffer
            buffer = (buffer + "\n" + c).strip() if buffer else c
        else:
            if buffer:
                # 将 buffer 合并到当前 chunk 前面
                c = (buffer + "\n" + c).strip()
                buffer = ""
            merged.append(c)

    # 最后剩余的 buffer 追加到最后一个 chunk
    if buffer and merged:
        merged[-1] = (merged[-1] + "\n" + buffer).strip()
    elif buffer:
        merged.append(buffer)

    return merged


def _split_table_columns(line: str) -> List[str]:
    """将表格行拆分为列，支持多种分隔符（与 _detect_columnar_table 检测逻辑一致）

    按优先级尝试：多空格 → 制表符 → 单空格
    返回拆分后的非空列列表
    """
    stripped = line.strip()
    # 1. 多空格分隔（2个及以上连续空格）
    parts = re.split(r'\s{2,}', stripped)
    parts = [p.strip() for p in parts if p.strip()]
    if len(parts) >= 2:
        return parts
    # 2. 制表符分隔（常见于 docx 表格提取）
    parts = [p.strip() for p in stripped.split('\t') if p.strip()]
    if len(parts) >= 2:
        return parts
    # 3. 单空格分隔（需要至少 3 列才认为是表格）
    parts = stripped.split()
    if len(parts) >= 3:
        return parts
    return [stripped] if stripped else []


def _detect_columnar_table(lines: List[str], start_idx: int) -> Optional[int]:
    """检测从 start_idx 开始的列式表格，返回表格结束行索引

    列式表格特征：连续多行有相同的列数（空格或制表符分隔），
    常见于 docx/pdf 表格提取后的纯文本。
    """
    if start_idx >= len(lines) - 1:
        return None

    # 需要至少 3 行连续，且列数 >= 2 且一致
    consecutive = 0
    prev_cols = 0
    for j in range(start_idx, min(start_idx + 15, len(lines))):
        line = lines[j].strip()
        if not line:
            if consecutive >= 3:
                return j
            break
        cols = len(_split_table_columns(line))
        if cols >= 2:
            if prev_cols == 0 or cols == prev_cols or abs(cols - prev_cols) <= 1:
                consecutive += 1
                prev_cols = cols
            elif consecutive >= 3:
                return j
            else:
                break
        else:
            if consecutive >= 3:
                return j
            break

    if consecutive >= 3:
        return min(start_idx + consecutive, len(lines))
    return None


def _format_table_chunk(lines: List[str]) -> str:
    """将检测到的表格行格式化为 Markdown 表格

    使用 _split_table_columns 统一拆分逻辑，支持多空格、制表符、单空格分隔
    """
    if not lines:
        return ""
    rows = []
    for line in lines:
        parts = _split_table_columns(line)
        if parts:
            rows.append(parts)
    if len(rows) < 2:
        return "\n".join(lines)
    max_cols = max(len(r) for r in rows)
    for r in rows:
        while len(r) < max_cols:
            r.append("")
    md_lines = []
    md_lines.append("| " + " | ".join(rows[0]) + " |")
    md_lines.append("|" + "|".join([" --- " for _ in range(max_cols)]) + "|")
    for row in rows[1:]:
        md_lines.append("| " + " | ".join(row) + " |")
    return "\n".join(md_lines)


def _is_table_content(text: str) -> bool:
    """检测文本是否包含表格内容"""
    lines = text.strip().split("\n")
    if len(lines) < 2:
        return False
    # 至少两行匹配表格行模式
    table_rows = sum(1 for line in lines if _TABLE_ROW_PATTERN.match(line))
    return table_rows >= 2


def _split_with_table_preservation(
    text: str, chunk_size: int = 1000, chunk_overlap: int = 150
) -> List[str]:
    """智能切分：保留表格完整性，段落边界优先

    策略：
    1. 扫描每一行，检测表格块（|...|...| 模式），表格作为独立 chunk
    2. 非表格文本以空行（段落边界）分隔，累积后按 chunk_size 切分
    3. 过长的段落再按句子边界（。！？；）切分
    4. 相邻 chunk 之间保留 chunk_overlap 长度的重叠文本
    5. 末尾合并短 chunk（<50字符），避免孤立标题/碎片
    """
    chunks = []
    lines = text.split("\n")
    i = 0
    current_paragraph: List[str] = []

    def flush_paragraph():
        """将累积的段落文本按 chunk_size 切分后加入 chunks"""
        nonlocal current_paragraph
        if not current_paragraph:
            return
        para_text = "\n".join(current_paragraph).strip()
        current_paragraph = []
        if para_text:
            sub_chunks = _split_text_by_boundaries(para_text, chunk_size, chunk_overlap)
            chunks.extend(sub_chunks)

    while i < len(lines):
        line = lines[i]

        # 检测表格行（Markdown 表格行 或 表格分隔行）
        if _TABLE_ROW_PATTERN.match(line.strip()) or _TABLE_SEPARATOR_PATTERN.match(line.strip()):
            # 先保存之前累积的段落文本
            flush_paragraph()

            # 收集完整表格（连续的表格式行）
            table_lines = [line]
            j = i + 1
            while j < len(lines):
                next_line = lines[j].strip()
                if _TABLE_ROW_PATTERN.match(next_line) or _TABLE_SEPARATOR_PATTERN.match(next_line):
                    table_lines.append(lines[j])
                    j += 1
                elif next_line == "":
                    # 空行视为表格结束
                    j += 1
                    break
                else:
                    break

            table_text = "\n".join(table_lines)
            if len(table_text) > chunk_size * 2:
                # 表格太大，拆半
                mid = len(table_lines) // 2
                chunks.append("\n".join(table_lines[:mid]))
                chunks.append("\n".join(table_lines[mid:]))
            else:
                chunks.append(table_text)
            i = j
            continue

        # 检测列式表格（空格对齐的列，常见于 docx/pdf 表格提取）
        table_end = _detect_columnar_table(lines, i)
        if table_end is not None:
            flush_paragraph()
            table_lines = [ln.strip() for ln in lines[i:table_end] if ln.strip()]
            table_chunk = _format_table_chunk(table_lines)
            if len(table_chunk) > chunk_size * 2:
                mid = len(table_lines) // 2
                chunks.append(_format_table_chunk(table_lines[:mid]))
                chunks.append(_format_table_chunk(table_lines[mid:]))
            else:
                chunks.append(table_chunk)
            i = table_end
            continue

        # 空行 → 段落边界
        if line.strip() == "":
            flush_paragraph()
            i += 1
            continue

        # 普通文本行，累积到当前段落
        current_paragraph.append(line)
        i += 1

    # 处理最后剩余的段落
    flush_paragraph()

    # 合并短 chunk，减少孤立碎片
    return _merge_short_chunks(chunks, min_len=50)


def _split_text_by_boundaries(
    text: str, chunk_size: int = 1000, chunk_overlap: int = 150
) -> List[str]:
    """按段落/句子边界切分普通文本，相邻 chunk 保留重叠

    先按双换行（段落）切分，再按句子边界（。！？；）切分过长段落
    """
    # 先按段落切分
    paragraphs = re.split(r'\n\s*\n', text)

    result: List[str] = []
    current_chunk = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        # 段落本身过长 → 按句子切分
        if len(para) > chunk_size:
            # 先保存当前累积的 chunk
            if current_chunk:
                result.append(current_chunk.strip())
                current_chunk = ""

            sentences = re.split(r'(?<=[。！？；])', para)
            for sent in sentences:
                sent = sent.strip()
                if not sent:
                    continue
                if len(current_chunk) + len(sent) > chunk_size and current_chunk:
                    result.append(current_chunk.strip())
                    # 重叠：保留上一段的末尾部分
                    if len(current_chunk) > chunk_overlap:
                        current_chunk = current_chunk[-chunk_overlap:] + "\n" + sent
                    else:
                        current_chunk = sent
                else:
                    current_chunk = (current_chunk + sent).strip() if current_chunk else sent
        else:
            # 段落不长，尝试合并到当前 chunk
            if len(current_chunk) + len(para) > chunk_size and current_chunk:
                result.append(current_chunk.strip())
                # 重叠部分
                if len(current_chunk) > chunk_overlap:
                    current_chunk = current_chunk[-chunk_overlap:] + "\n" + para
                else:
                    current_chunk = para
            else:
                current_chunk = (current_chunk + "\n" + para).strip() if current_chunk else para

    if current_chunk:
        result.append(current_chunk.strip())

    return [r for r in result if r]


def _extract_section_title(text: str) -> str:
    """提取文本中的章节标题（如'第X章'、'X.X'、'一、'等）"""
    patterns = [
        r'第[一二三四五六七八九十\d]+章\s*.+',
        r'第[一二三四五六七八九十\d]+节\s*.+',
        r'\d+[\.\、]\s*.+',
        r'[一二三四五六七八九十]+[、\．]\s*.+',
    ]
    for p in patterns:
        match = re.search(p, text)
        if match:
            return match.group().strip()
    return ""


def _extract_table_content(text: str) -> Optional[str]:
    """从文本中提取表格内容，返回 Markdown 表格格式"""
    lines = text.strip().split("\n")
    table_lines = []
    for line in lines:
        if _TABLE_ROW_PATTERN.match(line) or _TABLE_SEPARATOR_PATTERN.match(line):
            table_lines.append(line)
    if len(table_lines) >= 2:
        return "\n".join(table_lines)
    return None


class PyMuPDFLoader:
    """基于 PyMuPDF (fitz) 的 PDF 加载器，替代 PyPDFLoader

    PyMuPDF 的文本提取质量远优于 PyPDF2/pypdf，尤其对表格中的数字提取。
    每页作为一个独立的 Document，保留 page 元数据。
    """

    def __init__(self, file_path: str):
        self._file_path = file_path
        self._filename = os.path.basename(file_path)

    def load(self) -> List[Document]:
        """加载 PDF，每页返回一个 Document"""
        docs = []
        try:
            pdf = fitz.open(self._file_path)
            for page_num in range(pdf.page_count):
                page = pdf[page_num]

                # 使用 "text" 模式提取（保留排版，比 blocks 模式更完整）
                page_text = page.get_text("text")

                if page_text.strip():
                    docs.append(Document(
                        page_content=page_text,
                        metadata={
                            "source": self._file_path,
                            "filename": self._filename,
                            "page": page_num,
                        }
                    ))
            pdf.close()
            logger.info(f"PyMuPDF 加载完成: {self._filename} ({len(docs)} 页)")
        except Exception as e:
            logger.error(f"PyMuPDF 加载 {self._filename} 失败: {e}")
            raise

        return docs


class OllamaEmbeddingFunction(EmbeddingFunction):
    """自定义 ChromaDB embedding function，包装 OllamaEmbeddings"""

    def __init__(self, model_name: str = "bge-m3", base_url: str = None):
        self._embeddings = OllamaEmbeddings(
            model=model_name,
            base_url=base_url or settings.OLLAMA_BASE_URL,
        )
        self._model_name = model_name

    def __call__(self, input: List[str]) -> Embeddings:
        """ChromaDB 要求的 embedding 接口"""
        return self._embeddings.embed_documents(input)


class KnowledgeBaseService:
    """知识库管理服务，提供文档加载、索引和检索功能"""

    COLLECTION_NAME = "accounting_knowledge"

    def __init__(self):
        """初始化 ChromaDB 持久化客户端和 embedding function"""
        self._base_dir = os.path.dirname(os.path.dirname(__file__))
        self._chroma_path = os.path.join(self._base_dir, "docs", "chroma_db")
        self._doc_dir = os.path.join(self._base_dir, "docs", "uploads")

        self._embedding_fn = OllamaEmbeddingFunction(
            model_name="bge-m3",
            base_url=settings.OLLAMA_BASE_URL,
        )

        self._client = chromadb.PersistentClient(
            path=self._chroma_path,
            settings=ChromaSettings(anonymized_telemetry=False),
        )

        self._collection = self._client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            embedding_function=self._embedding_fn,
            metadata={"hnsw:space": "cosine"},
        )

        self._text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=150,
            separators=["\n\n", "\n", "。", "！", "？", "；", "，", " ", ""],
        )

    def _get_loader(self, file_path: str):
        """根据文件类型获取对应的文档加载器"""
        ext = os.path.splitext(file_path)[1].lower()
        if ext == ".pdf":
            return PyMuPDFLoader(file_path)
        elif ext == ".docx":
            return Docx2txtLoader(file_path)
        elif ext in (".txt", ".md", ".csv"):
            return TextLoader(file_path, encoding="utf-8")
        else:
            raise ValueError(f"不支持的文件类型: {ext}")

    def _get_file_type(self, file_path: str) -> str:
        """获取文件类型标识"""
        ext = os.path.splitext(file_path)[1].lower()
        return ext.lstrip(".")

    def _smart_split_documents(self, docs: List[Document]) -> List[Document]:
        """使用智能切分器处理文档列表，保留表格完整性和页面元数据

        对每个文档页面独立应用 _split_with_table_preservation，
        保留 source、filename、page 等元数据到每个 chunk
        """
        result: List[Document] = []
        for doc in docs:
            page_content = doc.page_content
            if not page_content or not page_content.strip():
                continue

            source = doc.metadata.get("source", "")
            filename = doc.metadata.get("filename", os.path.basename(source) if source else "")
            page = doc.metadata.get("page", 0)
            category = doc.metadata.get("category", "")
            doc_id = doc.metadata.get("doc_id", "")

            text_chunks = _split_with_table_preservation(
                page_content, chunk_size=1000, chunk_overlap=150
            )

            for tc in text_chunks:
                # 清理内容：移除特殊字符、规范化空白
                tc = _clean_chunk_content(tc)
                if not tc or len(tc) < 10:
                    continue
                meta = {
                    "source": source,
                    "filename": filename,
                    "page": page,
                }
                if category:
                    meta["category"] = category
                if doc_id:
                    meta["doc_id"] = doc_id

                result.append(Document(page_content=tc, metadata=meta))

        logger.info(
            f"智能切分: {len(docs)} 页 → {len(result)} 个 chunk "
            f"(chunk_size=1000, overlap=150)"
        )
        return result

    def load_and_index_documents(self, doc_dir: str, category_map: Dict[str, str] = None) -> int:
        """
        加载目录中的所有文档并构建 ChromaDB 索引

        Args:
            doc_dir: 文档目录路径
            category_map: 文件路径 → 分类名称的映射（用于重建索引时保留分类）

        Returns:
            索引的总 chunk 数量
        """
        all_docs: List[Document] = []
        supported_exts = {".pdf", ".docx", ".txt", ".md", ".csv"}
        # 规范化路径键，解决 Windows 上大小写不一致问题（如 E:\ vs e:\）
        cat_map = {os.path.normcase(k): v for k, v in (category_map or {}).items()}

        for root, _, files in os.walk(doc_dir):
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext not in supported_exts:
                    continue

                file_path = os.path.join(root, file)
                try:
                    loader = self._get_loader(file_path)
                    docs = loader.load()
                    category = cat_map.get(os.path.normcase(file_path), "")
                    for doc in docs:
                        doc.metadata["source"] = file_path
                        doc.metadata["filename"] = file
                        if category:
                            doc.metadata["category"] = category
                    all_docs.extend(docs)
                    logger.info(f"已加载文档: {file} ({len(docs)} 页)")
                except Exception as e:
                    logger.error(f"加载文档 {file} 失败: {e}")

        if not all_docs:
            logger.warning("未找到可索引的文档")
            return 0

        # 使用智能切分器（保留表格完整性 + 页面元数据）
        chunks = self._smart_split_documents(all_docs)
        logger.info(f"文档分割完成，共 {len(chunks)} 个 chunk")

        self._add_chunks_to_collection(chunks)
        logger.info(f"ChromaDB 索引构建完成，共 {len(chunks)} 个 chunk")

        return len(chunks)

    def _add_chunks_to_collection(self, chunks: List[Document]) -> None:
        """将文档块添加到 ChromaDB collection，分批处理避免超时"""
        if not chunks:
            return

        # 过滤无效 chunk：空内容、纯空白、过短（< 10 字符）
        valid_chunks = [
            c for c in chunks
            if c.page_content and len(c.page_content.strip()) >= 10
        ]
        if not valid_chunks:
            logger.warning("所有 chunk 均为空或过短，跳过添加")
            return

        skipped = len(chunks) - len(valid_chunks)
        if skipped > 0:
            logger.info(f"过滤掉 {skipped} 个无效 chunk（空/过短）")

        # 分批添加，每批最多 50 个，避免 Ollama embedding 超时/NaN
        batch_size = 50
        total_added = 0
        for batch_start in range(0, len(valid_chunks), batch_size):
            batch = valid_chunks[batch_start:batch_start + batch_size]
            ids = [str(uuid.uuid4()) for _ in batch]
            documents = [c.page_content for c in batch]
            metadatas = [c.metadata for c in batch]

            try:
                self._collection.add(
                    ids=ids,
                    documents=documents,
                    metadatas=metadatas,
                )
                total_added += len(batch)
                logger.debug(f"已添加 batch {batch_start//batch_size + 1}: {len(batch)} chunks")
            except Exception as e:
                # 如果整批失败，逐个添加以定位问题 chunk
                logger.warning(f"批量添加失败 ({len(batch)} chunks): {e}，尝试逐个添加")
                for c in batch:
                    try:
                        self._collection.add(
                            ids=[str(uuid.uuid4())],
                            documents=[c.page_content],
                            metadatas=[c.metadata],
                        )
                        total_added += 1
                    except Exception as inner_e:
                        logger.warning(
                            f"跳过问题 chunk (source={c.metadata.get('filename', '?')}, "
                            f"page={c.metadata.get('page', '?')}, len={len(c.page_content)}): {inner_e}"
                        )

        logger.info(f"ChromaDB 添加完成: {total_added}/{len(valid_chunks)} chunks")

    def search(self, query: str, top_k: int = 5, category: str = None) -> List[Dict[str, Any]]:
        """
        语义检索最相关的文档片段

        Args:
            query: 查询文本
            top_k: 返回结果数量
            category: 可选的分类过滤

        Returns:
            检索结果列表，包含 content、source、filename、score
        """
        # 缓存检查：相同查询在 TTL 内直接返回缓存结果
        cache_key = f"{query}|{top_k}|{category}"
        if cache_key in _search_cache:
            cached_time, cached_result = _search_cache[cache_key]
            if time.time() - cached_time < _CACHE_TTL:
                logger.debug(f"RAG 缓存命中: {query[:50]}")
                return cached_result
            else:
                del _search_cache[cache_key]

        where_filter = None
        if category:
            where_filter = {"category": category}

        try:
            results = self._collection.query(
                query_texts=[query],
                n_results=top_k,
                where=where_filter,
            )
        except Exception as e:
            logger.error(f"ChromaDB 查询失败: {e}")
            return []

        if not results or not results.get("ids") or not results["ids"][0]:
            return []

        output = []
        for i in range(len(results["ids"][0])):
            doc_id = results["ids"][0][i]
            document = results["documents"][0][i] if results["documents"] else ""
            metadata = results["metadatas"][0][i] if results["metadatas"] else {}
            distance = results["distances"][0][i] if results.get("distances") else 0.0

            # ChromaDB 返回的是距离值（越小越相关），转换为相似度分数
            similarity = 1.0 - float(distance) if distance else 1.0

            output.append({
                "content": document,
                "source": metadata.get("source", ""),
                "filename": metadata.get("filename", ""),
                "score": round(similarity, 4),
            })

        # 写入缓存（LRU 淘汰：超过上限时删除最旧的条目）
        if len(_search_cache) >= _CACHE_MAX_SIZE:
            oldest_key = min(_search_cache, key=lambda k: _search_cache[k][0])
            del _search_cache[oldest_key]
        _search_cache[cache_key] = (time.time(), output)

        return output

    def add_document(self, file_path: str, category: str, doc_id: str = None) -> int:
        """
        添加单个文档到索引

        Args:
            file_path: 文件路径
            category: 文档分类
            doc_id: 可选的文档唯一标识，用于后续删除

        Returns:
            新增的 chunk 数量
        """
        loader = self._get_loader(file_path)
        docs = loader.load()

        filename = os.path.basename(file_path)
        for doc in docs:
            doc.metadata["source"] = file_path
            doc.metadata["filename"] = filename
            doc.metadata["category"] = category
            if doc_id:
                doc.metadata["doc_id"] = doc_id

        chunks = self._smart_split_documents(docs)
        self._add_chunks_to_collection(chunks)
        logger.info(f"已添加文档 {file_path} 到索引，新增 {len(chunks)} 个 chunk")
        return len(chunks)

    def delete_document(self, doc_id: str) -> bool:
        """
        通过文档ID删除索引中的所有相关 chunk

        Args:
            doc_id: 文档唯一标识

        Returns:
            是否成功删除
        """
        try:
            # 查找所有包含该 doc_id 的 chunks
            existing = self._collection.get(
                where={"doc_id": doc_id},
            )
            if existing and existing.get("ids"):
                self._collection.delete(
                    where={"doc_id": doc_id},
                )
                logger.info(f"已从索引中删除文档 {doc_id}，共 {len(existing['ids'])} 个 chunk")
                return True
            else:
                logger.warning(f"未找到文档 {doc_id} 的索引条目")
                return False
        except Exception as e:
            logger.error(f"删除文档 {doc_id} 失败: {e}")
            return False

    def delete_document_by_source(self, file_path: str) -> bool:
        """
        通过文件路径删除索引中的所有相关 chunk

        Args:
            file_path: 文件路径（source）

        Returns:
            是否成功删除
        """
        try:
            existing = self._collection.get(
                where={"source": file_path},
            )
            if existing and existing.get("ids"):
                self._collection.delete(
                    where={"source": file_path},
                )
                logger.info(f"已从索引中删除文档 {file_path}，共 {len(existing['ids'])} 个 chunk")
                return True
            else:
                logger.warning(f"未找到文档 {file_path} 的索引条目")
                return False
        except Exception as e:
            logger.error(f"删除文档 {file_path} 失败: {e}")
            return False

    def get_index_stats(self) -> Dict[str, Any]:
        """获取索引统计信息"""
        try:
            count = self._collection.count()
            # 获取所有文档的元数据以统计分类和文档数
            all_data = self._collection.get()
            categories = set()
            file_paths = set()
            if all_data and all_data.get("metadatas"):
                for meta in all_data["metadatas"]:
                    if meta.get("category"):
                        categories.add(meta["category"])
                    if meta.get("source"):
                        file_paths.add(meta["source"])

            return {
                "initialized": True,
                "total_chunks": count,
                "total_documents": len(file_paths),
                "total_categories": len(categories),
                "categories": sorted(list(categories)),
                "index_path": self._chroma_path,
            }
        except Exception as e:
            logger.error(f"获取索引统计失败: {e}")
            return {
                "initialized": False,
                "total_chunks": 0,
                "total_documents": 0,
                "categories": [],
                "index_path": self._chroma_path,
                "error": str(e),
            }

    def rebuild_index(self, category_map: Dict[str, str] = None) -> int:
        """
        重建索引：删除现有 collection 后重新创建

        Args:
            category_map: 文件路径 → 分类名称的映射（用于保留数据库中的分类信息）

        Returns:
            重建后的 chunk 数量
        """
        try:
            self._client.delete_collection(name=self.COLLECTION_NAME)
            logger.info(f"已删除旧 collection: {self.COLLECTION_NAME}")
        except Exception as e:
            logger.warning(f"删除旧 collection 失败（可能不存在）: {e}")

        self._collection = self._client.create_collection(
            name=self.COLLECTION_NAME,
            embedding_function=self._embedding_fn,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(f"已创建新 collection: {self.COLLECTION_NAME}")

        # 重新索引 uploads 目录中的文档
        total = 0
        if os.path.exists(self._doc_dir):
            total = self.load_and_index_documents(self._doc_dir, category_map=category_map)
        return total

    def get_categories(self) -> List[str]:
        """获取所有文档分类列表"""
        try:
            all_data = self._collection.get()
            categories = set()
            if all_data and all_data.get("metadatas"):
                for meta in all_data["metadatas"]:
                    if meta.get("category"):
                        categories.add(meta["category"])
            return sorted(list(categories))
        except Exception as e:
            logger.error(f"获取分类列表失败: {e}")
            return []