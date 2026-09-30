import sys; sys.path.insert(0, '.')
from services.rag_service import KnowledgeBaseService

kb = KnowledgeBaseService()
all_data = kb._collection.get()

# 找有问题的chunk：包含多行数字或表格特征的
for i, (doc, meta) in enumerate(zip(all_data['documents'], all_data['metadatas'])):
    lines = doc.split('\n')
    # 检查是否有类似表格的行（多行都以数字开头或包含对齐的空格）
    num_lines = sum(1 for l in lines if l.strip() and any(c.isdigit() for c in l[:20]))
    if num_lines >= 3 and len(lines) >= 3:
        print(f'--- chunk {i} (file={meta.get("filename","?")}, len={len(doc)}) ---')
        print(doc[:500])
        print()
        if i > 8:
            break