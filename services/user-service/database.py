import os
import asyncpg

DATABASE_URL = (
    f"postgresql://{os.environ.get('POSTGRES_USER', 'gorbushka')}"
    f":{os.environ.get('POSTGRES_PASSWORD', 'Gorb_2024_Secure!')}"
    f"@{os.environ.get('POSTGRES_HOST', 'postgres')}"
    f":{os.environ.get('POSTGRES_PORT', '5432')}"
    f"/{os.environ.get('POSTGRES_DB', 'gorbushka')}"
)

pool: asyncpg.Pool = None


async def init_db():
    global pool
    pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
    async with pool.acquire() as conn:
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                telegram_id BIGINT UNIQUE NOT NULL,
                username TEXT,
                full_name TEXT,
                phone TEXT,
                company_name TEXT,
                city TEXT,
                is_verified INTEGER DEFAULT 0,
                is_blocked INTEGER DEFAULT 0,
                rating REAL DEFAULT 0.0,
                deals_count INTEGER DEFAULT 0,
                notifications_enabled INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT NOW()
            )
        ''')
        await conn.execute('''
            ALTER TABLE users ADD COLUMN IF NOT EXISTS is_blocked INTEGER DEFAULT 0
        ''')
        await conn.execute('''
            ALTER TABLE users ADD COLUMN IF NOT EXISTS sales_paused INTEGER DEFAULT 0
        ''')
        await conn.execute('''
            ALTER TABLE users ADD COLUMN IF NOT EXISTS role TEXT DEFAULT NULL
        ''')
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS user_blocks (
                id SERIAL PRIMARY KEY,
                blocker_id BIGINT NOT NULL,
                blocked_id BIGINT NOT NULL,
                created_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(blocker_id, blocked_id)
            )
        ''')

        # Fix sequences after migration data
        for table, seq in [
            ('users', 'users_id_seq'),
        ]:
            max_id = await conn.fetchval(f'SELECT COALESCE(MAX(id), 0) FROM {table}')
            if max_id > 0:
                await conn.execute(f"SELECT setval('{seq}', {max_id})")


async def close_db():
    global pool
    if pool:
        await pool.close()


async def create_or_update_user(telegram_id, username=None, full_name=None):
    async with pool.acquire() as conn:
        await conn.execute('''
            INSERT INTO users (telegram_id, username, full_name)
            VALUES ($1, $2, $3)
            ON CONFLICT(telegram_id) DO UPDATE SET
                username = EXCLUDED.username,
                full_name = EXCLUDED.full_name
        ''', telegram_id, username, full_name)


async def get_user(telegram_id):
    async with pool.acquire() as conn:
        row = await conn.fetchrow('SELECT * FROM users WHERE telegram_id = $1', telegram_id)
        return dict(row) if row else None


async def set_notifications_enabled(telegram_id, enabled):
    async with pool.acquire() as conn:
        await conn.execute(
            'UPDATE users SET notifications_enabled = $1 WHERE telegram_id = $2',
            1 if enabled else 0, telegram_id
        )


async def get_users_with_notifications():
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT telegram_id FROM users WHERE notifications_enabled = 1 AND role = 'supplier'"
        )
        return [r['telegram_id'] for r in rows]


async def get_all_users(limit=500):
    async with pool.acquire() as conn:
        rows = await conn.fetch('''
            SELECT telegram_id, username, full_name, is_verified, is_blocked,
                   rating, deals_count, company_name, city, created_at
            FROM users ORDER BY created_at DESC LIMIT $1
        ''', limit)
        return [dict(r) for r in rows]


async def set_sales_paused(telegram_id, paused):
    async with pool.acquire() as conn:
        await conn.execute(
            'UPDATE users SET sales_paused = $1 WHERE telegram_id = $2',
            1 if paused else 0, telegram_id
        )


async def block_user_peer(blocker_id, blocked_id):
    async with pool.acquire() as conn:
        await conn.execute('''
            INSERT INTO user_blocks (blocker_id, blocked_id)
            VALUES ($1, $2) ON CONFLICT DO NOTHING
        ''', blocker_id, blocked_id)


async def unblock_user_peer(blocker_id, blocked_id):
    async with pool.acquire() as conn:
        await conn.execute(
            'DELETE FROM user_blocks WHERE blocker_id = $1 AND blocked_id = $2',
            blocker_id, blocked_id
        )


async def get_blocked_ids(telegram_id):
    async with pool.acquire() as conn:
        rows = await conn.fetch('''
            SELECT blocked_id AS other_id FROM user_blocks WHERE blocker_id = $1
            UNION
            SELECT blocker_id AS other_id FROM user_blocks WHERE blocked_id = $1
        ''', telegram_id)
        return [r['other_id'] for r in rows]


async def set_user_role(telegram_id, role):
    async with pool.acquire() as conn:
        result = await conn.execute(
            'UPDATE users SET role = $1 WHERE telegram_id = $2 AND role IS NULL',
            role, telegram_id
        )
        return 'UPDATE 1' in result


async def get_users_bulk(telegram_ids):
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            'SELECT telegram_id, username, full_name, company_name FROM users WHERE telegram_id = ANY($1::bigint[])',
            telegram_ids
        )
        return [dict(r) for r in rows]


async def set_user_blocked(telegram_id, blocked):
    async with pool.acquire() as conn:
        await conn.execute(
            'UPDATE users SET is_blocked = $1 WHERE telegram_id = $2',
            1 if blocked else 0, telegram_id
        )


async def delete_user(telegram_id):
    async with pool.acquire() as conn:
        await conn.execute('DELETE FROM offers WHERE supplier_id = $1', telegram_id)
        await conn.execute('DELETE FROM users WHERE telegram_id = $1', telegram_id)


async def get_supplier_stats(supplier_id):
    async with pool.acquire() as conn:
        row = await conn.fetchrow('''
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                SUM(CASE WHEN status IN ('rejected','cancelled') THEN 1 ELSE 0 END) as cancelled
            FROM deals WHERE supplier_id = $1
        ''', supplier_id)
    total = row['total'] or 0
    completed = row['completed'] or 0
    cancelled = row['cancelled'] or 0
    confirmed_rate = round(completed / total * 100) if total > 0 else 0
    cancel_rate = round(cancelled / total * 100) if total > 0 else 0
    return {'total': total, 'completed': completed, 'cancelled': cancelled,
            'confirmed_rate': confirmed_rate, 'cancel_rate': cancel_rate}


async def get_supplier_reviews(supplier_id):
    async with pool.acquire() as conn:
        rows = await conn.fetch('''
            SELECT r.*, u.username, u.company_name, d.created_at as deal_date
            FROM reviews r
            JOIN users u ON r.buyer_id = u.telegram_id
            JOIN deals d ON r.deal_id = d.id
            WHERE r.supplier_id = $1
            ORDER BY r.created_at DESC
        ''', supplier_id)
        return [dict(r) for r in rows]
