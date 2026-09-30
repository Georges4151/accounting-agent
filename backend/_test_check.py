import sys; sys.path.insert(0, '.')
import asyncio
from database import async_session_maker
from sqlalchemy import select
from models.knowledge_doc import KnowledgeDoc

async def check():
    async with async_session_maker() as db:
        r = await db.execute(select(KnowledgeDoc))
        docs = r.scalars().all()
        for d in docs:
            print(f'id={d.id} title={d.title} cat={d.category} path={d.file_path}')

asyncio.run(check())