import asyncio
from database import async_session_maker
from models.voucher import Account
from sqlalchemy import select

async def main():
    async with async_session_maker() as db:
        result = await db.execute(
            select(Account.account_code, Account.account_name, Account.account_type, Account.book_id)
            .where(Account.is_active == True)
            .order_by(Account.account_code)
        )
        rows = result.all()
        for r in rows:
            print(f'{r.account_code} | {r.account_name} | {r.account_type} | book_id={r.book_id}')
        print(f'\nTotal: {len(rows)} accounts')

asyncio.run(main())