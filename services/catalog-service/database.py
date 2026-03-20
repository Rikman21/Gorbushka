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
            CREATE TABLE IF NOT EXISTS catalog (
                id SERIAL PRIMARY KEY,
                category TEXT NOT NULL,
                brand TEXT NOT NULL,
                model TEXT NOT NULL,
                memory TEXT,
                color TEXT,
                sku TEXT UNIQUE NOT NULL,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT NOW()
            )
        ''')
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS offers (
                id SERIAL PRIMARY KEY,
                supplier_id BIGINT NOT NULL,
                catalog_id INTEGER NOT NULL REFERENCES catalog(id),
                price INTEGER NOT NULL,
                quantity INTEGER DEFAULT 0,
                moq INTEGER DEFAULT 1,
                condition TEXT DEFAULT 'new',
                delivery_days INTEGER DEFAULT 0,
                warranty_months INTEGER DEFAULT 12,
                is_available INTEGER DEFAULT 1,
                is_visible INTEGER DEFAULT 1,
                price_hidden INTEGER DEFAULT 0,
                comment TEXT,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        ''')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_offers_supplier ON offers(supplier_id)')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_offers_catalog ON offers(catalog_id)')

        # Fix sequences after migration data
        for table, seq in [
            ('catalog', 'catalog_id_seq'),
            ('offers', 'offers_id_seq'),
        ]:
            max_id = await conn.fetchval(f'SELECT COALESCE(MAX(id), 0) FROM {table}')
            if max_id > 0:
                await conn.execute(f"SELECT setval('{seq}', {max_id})")


async def close_db():
    global pool
    if pool:
        await pool.close()


async def get_catalog(filters=None):
    async with pool.acquire() as conn:
        query = 'SELECT * FROM catalog WHERE is_active = 1'
        params = []
        idx = 1
        if filters:
            if filters.get('category'):
                query += f' AND category = ${idx}'
                params.append(filters['category'])
                idx += 1
            if filters.get('model'):
                query += f' AND model LIKE ${idx}'
                params.append(f"%{filters['model']}%")
                idx += 1
            if filters.get('memory'):
                query += f' AND memory = ${idx}'
                params.append(filters['memory'])
                idx += 1
        rows = await conn.fetch(query, *params)
        return [dict(r) for r in rows]


async def get_catalog_with_offers(filters=None, viewer_id=None):
    async with pool.acquire() as conn:
        query = '''
            SELECT
                c.id, c.category, c.brand, c.model, c.memory, c.color, c.sku, c.is_active, c.created_at,
                MIN(CASE WHEN o.price_hidden = 0 THEN o.price END) AS min_price,
                MAX(CASE WHEN o.price_hidden = 0 THEN o.price END) AS max_price,
                COUNT(o.id) AS offers_count
            FROM catalog c
            INNER JOIN offers o ON o.catalog_id = c.id AND o.is_visible = 1 AND o.is_available = 1
            INNER JOIN users u ON o.supplier_id = u.telegram_id AND u.sales_paused = 0
            WHERE c.is_active = 1
        '''
        params = []
        idx = 1
        if filters:
            if filters.get('category'):
                query += f' AND c.category = ${idx}'
                params.append(filters['category'])
                idx += 1
            if filters.get('model'):
                query += f' AND c.model LIKE ${idx}'
                params.append(f"%{filters['model']}%")
                idx += 1
            if filters.get('memory'):
                query += f' AND c.memory = ${idx}'
                params.append(filters['memory'])
                idx += 1
        if viewer_id:
            query += f''' AND o.supplier_id NOT IN (
                SELECT blocked_id FROM user_blocks WHERE blocker_id = ${idx}
                UNION
                SELECT blocker_id FROM user_blocks WHERE blocked_id = ${idx}
            )'''
            params.append(viewer_id)
            idx += 1
        query += ' GROUP BY c.id, c.category, c.brand, c.model, c.memory, c.color, c.sku, c.is_active, c.created_at HAVING COUNT(o.id) > 0 ORDER BY c.category, c.brand, c.model'
        rows = await conn.fetch(query, *params)
        return [dict(r) for r in rows]


async def get_catalog_offers(catalog_id):
    async with pool.acquire() as conn:
        rows = await conn.fetch('''
            SELECT
                o.id, o.price, o.quantity, o.moq, o.condition, o.delivery_days, o.warranty_months,
                o.price_hidden,
                u.telegram_id AS supplier_id, u.company_name, u.full_name, u.rating, u.deals_count, u.city
            FROM offers o
            JOIN users u ON o.supplier_id = u.telegram_id
            WHERE o.catalog_id = $1 AND o.is_visible = 1 AND o.is_available = 1
            ORDER BY o.price ASC
        ''', catalog_id)
        return [dict(r) for r in rows]


async def get_offers(filters=None):
    async with pool.acquire() as conn:
        query = '''
            SELECT
                o.*,
                c.model, c.memory, c.color, c.brand,
                u.company_name, u.rating, u.deals_count, u.city
            FROM offers o
            JOIN catalog c ON o.catalog_id = c.id
            JOIN users u ON o.supplier_id = u.telegram_id
            WHERE o.is_visible = 1 AND o.is_available = 1
        '''
        params = []
        idx = 1
        if filters:
            if filters.get('model'):
                query += f' AND c.model LIKE ${idx}'
                params.append(f"%{filters['model']}%")
                idx += 1
            if filters.get('memory'):
                query += f' AND c.memory = ${idx}'
                params.append(filters['memory'])
                idx += 1
            if filters.get('condition'):
                query += f' AND o.condition = ${idx}'
                params.append(filters['condition'])
                idx += 1
            if filters.get('min_price'):
                query += f' AND o.price >= ${idx}'
                params.append(filters['min_price'])
                idx += 1
            if filters.get('max_price'):
                query += f' AND o.price <= ${idx}'
                params.append(filters['max_price'])
                idx += 1
            if filters.get('in_stock'):
                query += ' AND o.quantity > 0'
            if filters.get('verified'):
                query += ' AND u.is_verified = 1'
        query += ' ORDER BY o.price ASC'
        rows = await conn.fetch(query, *params)
        return [dict(r) for r in rows]


async def get_offer_by_id(offer_id):
    async with pool.acquire() as conn:
        row = await conn.fetchrow('''
            SELECT
                o.*,
                c.model, c.memory, c.color, c.brand,
                u.company_name, u.rating, u.deals_count, u.city
            FROM offers o
            JOIN catalog c ON o.catalog_id = c.id
            JOIN users u ON o.supplier_id = u.telegram_id
            WHERE o.id = $1 AND o.is_visible = 1 AND o.is_available = 1
        ''', offer_id)
        return dict(row) if row else None


async def get_supplier_offers(supplier_id):
    async with pool.acquire() as conn:
        rows = await conn.fetch('''
            SELECT o.*, c.brand, c.model, c.memory, c.color, c.category
            FROM offers o
            JOIN catalog c ON o.catalog_id = c.id
            WHERE o.supplier_id = $1
            ORDER BY o.created_at DESC
        ''', supplier_id)
        return [dict(r) for r in rows]


async def create_offer(supplier_id, catalog_id, price, quantity, moq, condition, delivery_days, warranty_months, comment=None):
    async with pool.acquire() as conn:
        row = await conn.fetchrow('''
            INSERT INTO offers (supplier_id, catalog_id, price, quantity, moq, condition, delivery_days, warranty_months, comment)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9) RETURNING id
        ''', supplier_id, catalog_id, price, quantity, moq, condition, delivery_days, warranty_months, comment)
        return row['id']


async def update_offer(offer_id, **kwargs):
    allowed = ['price', 'quantity', 'moq', 'condition', 'delivery_days', 'warranty_months',
               'is_available', 'is_visible', 'price_hidden', 'comment']
    fields = []
    values = []
    idx = 1
    for key, value in kwargs.items():
        if key in allowed:
            fields.append(f"{key} = ${idx}")
            values.append(value)
            idx += 1
    if fields:
        fields.append(f"updated_at = NOW()")
        values.append(offer_id)
        query = f"UPDATE offers SET {', '.join(fields)} WHERE id = ${idx}"
        async with pool.acquire() as conn:
            await conn.execute(query, *values)


async def delete_offer(offer_id, supplier_id):
    async with pool.acquire() as conn:
        result = await conn.execute(
            'DELETE FROM offers WHERE id = $1 AND supplier_id = $2', offer_id, supplier_id
        )
        return result == 'DELETE 1'


async def find_catalog_by_brand_model_memory_color(brand, model, memory, color):
    async with pool.acquire() as conn:
        row = await conn.fetchrow('''
            SELECT id FROM catalog
            WHERE is_active = 1
              AND TRIM(COALESCE(brand,'')) = $1
              AND TRIM(COALESCE(model,'')) = $2
              AND TRIM(COALESCE(memory,'')) = $3
              AND TRIM(COALESCE(color,'')) = $4
            LIMIT 1
        ''', (brand or '').strip(), (model or '').strip(), (memory or '').strip(), (color or '').strip())
        return row['id'] if row else None


async def add_catalog_item(category, brand, model, memory, color, sku):
    async with pool.acquire() as conn:
        try:
            await conn.execute('''
                INSERT INTO catalog (category, brand, model, memory, color, sku)
                VALUES ($1, $2, $3, $4, $5, $6)
            ''', category, brand, model, memory, color, sku)
            return True, "Товар добавлен в каталог"
        except asyncpg.UniqueViolationError:
            return False, "Товар с таким SKU уже существует"


async def get_catalog_all_for_template():
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            'SELECT brand, model, memory, color FROM catalog WHERE is_active = 1 ORDER BY brand, model, memory, color'
        )
        return [dict(r) for r in rows]


async def get_all_catalog_items():
    async with pool.acquire() as conn:
        rows = await conn.fetch('''
            SELECT c.*, COUNT(o.id) AS offers_count
            FROM catalog c
            LEFT JOIN offers o ON o.catalog_id = c.id AND o.is_available = 1
            GROUP BY c.id
            ORDER BY c.category, c.brand, c.model, c.memory, c.color
        ''')
        return [dict(r) for r in rows]


async def toggle_catalog_item(item_id):
    async with pool.acquire() as conn:
        await conn.execute(
            'UPDATE catalog SET is_active = 1 - is_active WHERE id = $1', item_id
        )


async def delete_catalog_item(item_id):
    async with pool.acquire() as conn:
        offers_count = await conn.fetchval(
            'SELECT COUNT(*) FROM offers WHERE catalog_id = $1', item_id
        )
        if offers_count > 0:
            return False, f"Нельзя удалить — есть {offers_count} офферов"
        await conn.execute('DELETE FROM catalog WHERE id = $1', item_id)
        return True, "Удалено"


async def import_offers_batch(telegram_id, rows_data):
    success_count = 0
    error_count = 0
    async with pool.acquire() as conn:
        async with conn.transaction():
            for row in rows_data:
                model = (row.get("model") or "").strip()
                memory = (row.get("memory") or "").strip()
                color = (row.get("color") or "").strip()
                try:
                    price = int(float(row.get("price") or 0))
                except (TypeError, ValueError):
                    price = 0
                try:
                    quantity = int(float(row.get("quantity") or 0))
                except (TypeError, ValueError):
                    quantity = 0
                if price <= 0:
                    error_count += 1
                    continue
                cat_row = await conn.fetchrow('''
                    SELECT id FROM catalog
                    WHERE is_active = 1
                      AND TRIM(COALESCE(model,'')) = $1
                      AND TRIM(COALESCE(memory,'')) = $2
                      AND TRIM(COALESCE(color,'')) = $3
                    LIMIT 1
                ''', model, memory, color)
                if not cat_row:
                    error_count += 1
                    continue
                product_id = cat_row['id']
                existing = await conn.fetchrow(
                    'SELECT id FROM offers WHERE supplier_id = $1 AND catalog_id = $2',
                    telegram_id, product_id
                )
                if existing:
                    await conn.execute(
                        'UPDATE offers SET price = $1, quantity = $2, updated_at = NOW() WHERE id = $3',
                        price, quantity, existing['id']
                    )
                else:
                    await conn.execute('''
                        INSERT INTO offers (supplier_id, catalog_id, price, quantity, moq, condition, delivery_days, warranty_months)
                        VALUES ($1, $2, $3, $4, 1, 'new', 0, 12)
                    ''', telegram_id, product_id, price, quantity)
                success_count += 1
    return success_count, error_count
