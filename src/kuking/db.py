import ssl
import asyncpg
from typing import Optional, List
from kuking.config import settings

_pool: Optional[asyncpg.Pool] = None

def get_ssl_context() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx

async def init_db_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        # asyncpg memerlukan penanganan URL tanpa parameter sslmode jika context diberikan manual
        clean_url = settings.SUPABASE_DB_URL.split("?")[0]
        _pool = await asyncpg.create_pool(
            dsn=clean_url,
            ssl=get_ssl_context(),
            min_size=1,
            max_size=4,
            command_timeout=15.0
        )
    return _pool

async def get_user_pantry(pool: asyncpg.Pool, user_id: int) -> List[str]:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT ingredient_name FROM user_pantry WHERE telegram_user_id = $1 ORDER BY updated_at DESC",
            user_id
        )
        return [r["ingredient_name"] for r in rows]

async def save_expenses_and_pantry(pool: asyncpg.Pool, user_id: int, items: list) -> List[str]:
    added_to_pantry = []
    async with pool.acquire() as conn:
        async with conn.transaction():
            for item in items:
                await conn.execute(
                    """
                    INSERT INTO expenses (telegram_user_id, item_name, category, quantity_note, amount_idr)
                    VALUES ($1, $2, $3, $4, $5)
                    """,
                    user_id, item.item_name, item.category, item.quantity_note, item.amount_idr
                )
                if item.is_pantry_item:
                    await conn.execute(
                        """
                        INSERT INTO user_pantry (telegram_user_id, ingredient_name, updated_at)
                        VALUES ($1, $2, NOW())
                        ON CONFLICT (telegram_user_id, ingredient_name)
                        DO UPDATE SET updated_at = NOW()
                        """,
                        user_id, item.item_name.lower().strip()
                    )
                    added_to_pantry.append(item.item_name)
    return added_to_pantry