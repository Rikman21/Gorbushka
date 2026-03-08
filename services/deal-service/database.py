import os
import asyncpg
from datetime import datetime

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
            CREATE TABLE IF NOT EXISTS deals (
                id SERIAL PRIMARY KEY,
                buyer_id BIGINT NOT NULL,
                supplier_id BIGINT NOT NULL,
                offer_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL,
                price INTEGER NOT NULL,
                total_price INTEGER NOT NULL,
                status TEXT DEFAULT 'created',
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW(),
                closed_at TIMESTAMP
            )
        ''')
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id SERIAL PRIMARY KEY,
                deal_id INTEGER NOT NULL,
                sender_id BIGINT NOT NULL,
                message TEXT NOT NULL,
                attachment_url TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            )
        ''')
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS reviews (
                id SERIAL PRIMARY KEY,
                deal_id INTEGER NOT NULL,
                supplier_id BIGINT NOT NULL,
                buyer_id BIGINT NOT NULL,
                rating INTEGER NOT NULL,
                comment TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            )
        ''')
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS price_requests (
                id SERIAL PRIMARY KEY,
                offer_id INTEGER NOT NULL,
                buyer_id BIGINT NOT NULL,
                supplier_id BIGINT NOT NULL,
                quantity INTEGER DEFAULT 1,
                status TEXT DEFAULT 'pending',
                buyer_price INTEGER,
                created_at TIMESTAMP DEFAULT NOW(),
                responded_at TIMESTAMP
            )
        ''')
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS buyer_requests (
                id SERIAL PRIMARY KEY,
                buyer_id BIGINT NOT NULL,
                model TEXT NOT NULL,
                memory TEXT DEFAULT '',
                color TEXT DEFAULT '',
                quantity INTEGER DEFAULT 1,
                max_price INTEGER,
                comment TEXT,
                status TEXT DEFAULT 'open',
                created_at TIMESTAMP DEFAULT NOW()
            )
        ''')
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS buyer_request_responses (
                id SERIAL PRIMARY KEY,
                request_id INTEGER NOT NULL,
                supplier_id BIGINT NOT NULL,
                price INTEGER NOT NULL,
                comment TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            )
        ''')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_deals_buyer ON deals(buyer_id)')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_deals_supplier ON deals(supplier_id)')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_messages_deal ON messages(deal_id)')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_price_requests_supplier ON price_requests(supplier_id)')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_price_requests_buyer ON price_requests(buyer_id)')

        # Fix sequences after migration data
        for table, seq in [
            ('deals', 'deals_id_seq'),
            ('messages', 'messages_id_seq'),
            ('reviews', 'reviews_id_seq'),
            ('price_requests', 'price_requests_id_seq'),
            ('buyer_requests', 'buyer_requests_id_seq'),
            ('buyer_request_responses', 'buyer_request_responses_id_seq'),
        ]:
            max_id = await conn.fetchval(f'SELECT COALESCE(MAX(id), 0) FROM {table}')
            if max_id > 0:
                await conn.execute(f"SELECT setval('{seq}', {max_id})")


async def close_db():
    global pool
    if pool:
        await pool.close()


# ==================== DEALS ====================

async def create_deal(buyer_id, supplier_id, offer_id, quantity, price):
    total_price = quantity * price
    async with pool.acquire() as conn:
        row = await conn.fetchrow('''
            INSERT INTO deals (buyer_id, supplier_id, offer_id, quantity, price, total_price, status)
            VALUES ($1, $2, $3, $4, $5, $6, 'created') RETURNING id
        ''', buyer_id, supplier_id, offer_id, quantity, price, total_price)
        return row['id']


async def update_deal_status(deal_id, status):
    async with pool.acquire() as conn:
        if status == 'closed':
            await conn.execute('''
                UPDATE deals SET status = $1, updated_at = NOW(), closed_at = NOW() WHERE id = $2
            ''', status, deal_id)
        else:
            await conn.execute('''
                UPDATE deals SET status = $1, updated_at = NOW() WHERE id = $2
            ''', status, deal_id)


async def get_deal(deal_id):
    async with pool.acquire() as conn:
        row = await conn.fetchrow('''
            SELECT
                d.*,
                c.model, c.memory, c.color,
                ub.username as buyer_username, ub.company_name as buyer_company,
                us.username as supplier_username, us.company_name as supplier_company
            FROM deals d
            JOIN offers o ON d.offer_id = o.id
            JOIN catalog c ON o.catalog_id = c.id
            JOIN users ub ON d.buyer_id = ub.telegram_id
            JOIN users us ON d.supplier_id = us.telegram_id
            WHERE d.id = $1
        ''', deal_id)
        return dict(row) if row else None


async def get_user_deals(telegram_id, status_filter=None):
    async with pool.acquire() as conn:
        query = '''
            SELECT
                d.*,
                c.model, c.memory, c.color,
                CASE
                    WHEN d.buyer_id = $1 THEN u.company_name
                    ELSE ub.company_name
                END as counterparty
            FROM deals d
            JOIN offers o ON d.offer_id = o.id
            JOIN catalog c ON o.catalog_id = c.id
            LEFT JOIN users u ON d.supplier_id = u.telegram_id
            LEFT JOIN users ub ON d.buyer_id = ub.telegram_id
            WHERE (d.buyer_id = $1 OR d.supplier_id = $1)
        '''
        params = [telegram_id]
        idx = 2
        if status_filter:
            query += f' AND d.status = ${idx}'
            params.append(status_filter)
        query += ' ORDER BY d.created_at DESC'
        rows = await conn.fetch(query, *params)
        return [dict(r) for r in rows]


async def get_all_deals(limit=200):
    async with pool.acquire() as conn:
        rows = await conn.fetch('''
            SELECT d.*,
                c.model, c.memory, c.color,
                ub.username as buyer_username, ub.full_name as buyer_name,
                us.username as supplier_username, us.company_name as supplier_company
            FROM deals d
            JOIN offers o ON d.offer_id = o.id
            JOIN catalog c ON o.catalog_id = c.id
            JOIN users ub ON d.buyer_id = ub.telegram_id
            JOIN users us ON d.supplier_id = us.telegram_id
            ORDER BY d.created_at DESC LIMIT $1
        ''', limit)
        return [dict(r) for r in rows]


# ==================== MESSAGES ====================

async def add_message(deal_id, sender_id, message, attachment_url=None):
    async with pool.acquire() as conn:
        row = await conn.fetchrow('''
            INSERT INTO messages (deal_id, sender_id, message, attachment_url)
            VALUES ($1, $2, $3, $4) RETURNING id
        ''', deal_id, sender_id, message, attachment_url)
        return row['id']


async def get_deal_messages(deal_id):
    async with pool.acquire() as conn:
        rows = await conn.fetch('''
            SELECT m.*, u.username, u.company_name
            FROM messages m
            JOIN users u ON m.sender_id = u.telegram_id
            WHERE m.deal_id = $1
            ORDER BY m.created_at ASC
        ''', deal_id)
        return [dict(r) for r in rows]


# ==================== REVIEWS ====================

async def add_review(deal_id, supplier_id, buyer_id, rating, comment=None):
    async with pool.acquire() as conn:
        await conn.execute('''
            INSERT INTO reviews (deal_id, supplier_id, buyer_id, rating, comment)
            VALUES ($1, $2, $3, $4, $5)
        ''', deal_id, supplier_id, buyer_id, rating, comment)
        await conn.execute('''
            UPDATE users SET
                rating = (SELECT AVG(rating) FROM reviews WHERE supplier_id = $1),
                deals_count = deals_count + 1
            WHERE telegram_id = $1
        ''', supplier_id)


# ==================== PRICE REQUESTS ====================

async def create_price_request(offer_id, buyer_id, supplier_id, quantity=1):
    async with pool.acquire() as conn:
        row = await conn.fetchrow('''
            INSERT INTO price_requests (offer_id, buyer_id, supplier_id, quantity)
            VALUES ($1, $2, $3, $4) RETURNING id
        ''', offer_id, buyer_id, supplier_id, quantity)
        return row['id']


async def get_price_request(request_id):
    async with pool.acquire() as conn:
        row = await conn.fetchrow('''
            SELECT pr.*,
                c.model, c.memory, c.color,
                ub.username as buyer_username, ub.full_name as buyer_name,
                us.company_name as supplier_company
            FROM price_requests pr
            JOIN offers o ON pr.offer_id = o.id
            JOIN catalog c ON o.catalog_id = c.id
            JOIN users ub ON pr.buyer_id = ub.telegram_id
            JOIN users us ON pr.supplier_id = us.telegram_id
            WHERE pr.id = $1
        ''', request_id)
        return dict(row) if row else None


async def respond_price_request(request_id, price):
    async with pool.acquire() as conn:
        await conn.execute('''
            UPDATE price_requests SET status = 'responded', buyer_price = $1, responded_at = NOW()
            WHERE id = $2
        ''', price, request_id)


async def expire_price_request(request_id):
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE price_requests SET status = 'expired' WHERE id = $1", request_id
        )


async def accept_price_request(request_id):
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE price_requests SET status = 'accepted' WHERE id = $1 AND status = 'responded'",
            request_id,
        )


async def reject_price_request(request_id):
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE price_requests SET status = 'rejected' WHERE id = $1 AND status = 'responded'",
            request_id,
        )


async def get_pending_price_requests(supplier_id):
    async with pool.acquire() as conn:
        rows = await conn.fetch('''
            SELECT pr.*,
                c.model, c.memory, c.color,
                ub.username as buyer_username, ub.full_name as buyer_name
            FROM price_requests pr
            JOIN offers o ON pr.offer_id = o.id
            JOIN catalog c ON o.catalog_id = c.id
            JOIN users ub ON pr.buyer_id = ub.telegram_id
            WHERE pr.supplier_id = $1 AND pr.status = 'pending'
            ORDER BY pr.created_at DESC
        ''', supplier_id)
        return [dict(r) for r in rows]


async def get_buyer_price_requests(buyer_id):
    async with pool.acquire() as conn:
        rows = await conn.fetch('''
            SELECT pr.*,
                c.model, c.memory, c.color,
                us.company_name as supplier_company, us.username as supplier_username
            FROM price_requests pr
            JOIN offers o ON pr.offer_id = o.id
            JOIN catalog c ON o.catalog_id = c.id
            JOIN users us ON pr.supplier_id = us.telegram_id
            WHERE pr.buyer_id = $1
            ORDER BY pr.created_at DESC
        ''', buyer_id)
        return [dict(r) for r in rows]


# ==================== BUYER REQUESTS ====================

async def create_buyer_request(buyer_id, model, memory, color, quantity, max_price, comment):
    async with pool.acquire() as conn:
        row = await conn.fetchrow('''
            INSERT INTO buyer_requests (buyer_id, model, memory, color, quantity, max_price, comment)
            VALUES ($1, $2, $3, $4, $5, $6, $7) RETURNING id
        ''', buyer_id, model, memory or '', color or '', quantity, max_price, comment or None)
        return row['id']


async def get_open_buyer_requests():
    async with pool.acquire() as conn:
        rows = await conn.fetch('''
            SELECT br.*, u.username, u.company_name,
                (SELECT COUNT(*) FROM buyer_request_responses WHERE request_id = br.id) as response_count
            FROM buyer_requests br
            JOIN users u ON br.buyer_id = u.telegram_id
            WHERE br.status = 'open'
            ORDER BY br.created_at DESC
        ''')
        return [dict(r) for r in rows]


async def get_my_buyer_requests(buyer_id):
    async with pool.acquire() as conn:
        rows = await conn.fetch('''
            SELECT br.*,
                (SELECT COUNT(*) FROM buyer_request_responses WHERE request_id = br.id) as response_count
            FROM buyer_requests br
            WHERE br.buyer_id = $1
            ORDER BY br.created_at DESC
        ''', buyer_id)
        return [dict(r) for r in rows]


async def get_buyer_request_responses(request_id):
    async with pool.acquire() as conn:
        rows = await conn.fetch('''
            SELECT brr.*, u.username, u.company_name
            FROM buyer_request_responses brr
            JOIN users u ON brr.supplier_id = u.telegram_id
            WHERE brr.request_id = $1
            ORDER BY brr.price ASC
        ''', request_id)
        return [dict(r) for r in rows]


async def create_buyer_request_response(request_id, supplier_id, price, comment):
    async with pool.acquire() as conn:
        await conn.execute('''
            INSERT INTO buyer_request_responses (request_id, supplier_id, price, comment)
            VALUES ($1, $2, $3, $4)
        ''', request_id, supplier_id, price, comment or None)


async def close_buyer_request(request_id, buyer_id):
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE buyer_requests SET status='closed' WHERE id=$1 AND buyer_id=$2",
            request_id, buyer_id
        )


async def get_buyer_request_by_id(request_id):
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            'SELECT buyer_id, model, memory, color FROM buyer_requests WHERE id=$1', request_id
        )
        return dict(row) if row else None
