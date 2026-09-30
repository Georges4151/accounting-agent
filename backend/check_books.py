import asyncio
from database import async_session_maker
from models.book import Book
from sqlalchemy import select

async def main():
    async with async_session_maker() as db:
        result = await db.execute(
            select(Book.id, Book.name, Book.status, Book.is_default)
            .order_by(Book.id)
        )
        rows = result.all()
        for r in rows:
            print(f'ID={r.id} | {r.name} | status={r.status} | is_default={r.is_default}')

asyncio.run(main())