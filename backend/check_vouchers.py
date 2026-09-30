import asyncio
from database import async_session_maker
from models.voucher import Voucher, VoucherItem
from sqlalchemy import select, func

async def main():
    async with async_session_maker() as db:
        # Check voucher count by book_id
        result = await db.execute(
            select(Voucher.book_id, func.count(Voucher.id), func.min(Voucher.voucher_date), func.max(Voucher.voucher_date))
            .group_by(Voucher.book_id)
            .order_by(Voucher.book_id)
        )
        rows = result.all()
        for r in rows:
            print(f'book_id={r[0]} | voucher count={r[1]} | date range: {r[2]} ~ {r[3]}')
        
        # Check voucher status distribution
        result2 = await db.execute(
            select(Voucher.status, func.count(Voucher.id))
            .group_by(Voucher.status)
        )
        rows2 = result2.all()
        print('\nStatus distribution:')
        for r in rows2:
            print(f'  {r[0]}: {r[1]}')

asyncio.run(main())