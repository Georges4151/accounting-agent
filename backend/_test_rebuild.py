import sys; sys.path.insert(0, '.')
import logging; logging.basicConfig(level=logging.WARNING)

from services.rag_service import KnowledgeBaseService

# 模拟 API 传入的分类映射
category_map = {
    r'E:\agent\accounting_agent\backend\docs\uploads\新建 DOCX 文档_2.docx': '财务',
    r'E:\agent\accounting_agent\backend\docs\uploads\textbook_part1.docx': '分列',
    r'E:\agent\accounting_agent\backend\docs\uploads\发售版磋商文件-廊坊市第五中学运动场改造项目.pdf': '招标',
    r'E:\agent\accounting_agent\backend\docs\uploads\新建 DOCX 文档.docx': '招标',
}

kb = KnowledgeBaseService()
print('rebuilding with category_map...')
result = kb.rebuild_index(category_map=category_map)
print(f'DONE: {result} chunks')

# 检查分类
all_data = kb._collection.get()
cats = {}
for meta in all_data.get('metadatas') or []:
    cat = meta.get('category', '')
    if cat:
        cats[cat] = cats.get(cat, 0) + 1
print(f'Categories: {cats}')

# 检查表格检测
for i, (doc, meta) in enumerate(zip(all_data['documents'], all_data['metadatas'])):
    if doc.startswith('| ') and '|' in doc[2:]:
        print(f'\n--- Table chunk {i} (file={meta.get("filename","?")}) ---')
        print(doc[:300])
        if i > 5:
            break