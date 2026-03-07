"""
Миграция данных из SQLite (market.db) в PostgreSQL.

Использование:
    1. Поместите market.db рядом с этим файлом
    2. Убедитесь, что PostgreSQL запущен (docker-compose up -d postgres)
    3. pip install asyncpg
    4. python migrate.py

Можно указать переменные окружения:
    POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD
"""

import os
import sys
import sqlite3
import asyncio
import asyncpg

SQLITE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "market.db")

PG_HOST = os.environ.get("POSTGRES_HOST", "localhost")
PG_PORT = int(os.environ.get("POSTGRES_PORT", 5432))
PG_DB = os.environ.get("POSTGRES_DB", "gorbushka")
PG_USER = os.environ.get("POSTGRES_USER", "gorbushka")
PG_PASS = os.environ.get("POSTGRES_PASSWORD", "Gorb_2024_Secure!")


async def migrate():
    if not os.path.exists(SQLITE_PATH):
        print(f"SQLite файл не найден: {SQLITE_PATH}")
        sys.exit(1)

    print(f"Подключаемся к SQLite: {SQLITE_PATH}")
    lite = sqlite3.connect(SQLITE_PATH)
    lite.row_factory = sqlite3.Row

    print(f"Подключаемся к PostgreSQL: {PG_USER}@{PG_HOST}:{PG_PORT}/{PG_DB}")
    pg = await asyncpg.connect(
        host=PG_HOST, port=PG_PORT, database=PG_DB,
        user=PG_USER, password=PG_PASS,
    )

    # ============ Создаём таблицы ============
    print("Создаём таблицы...")
    await pg.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            telegram_id BIGINT UNIQUE NOT NULL,
            username TEXT,
            full_name TEXT,
            phone TEXT,
            company_name TEXT,
            city TEXT,
            is_supplier INTEGER DEFAULT 0,
            is_verified INTEGER DEFAULT 0,
            role_selected INTEGER DEFAULT 0,
            rating REAL DEFAULT 0.0,
            deals_count INTEGER DEFAULT 0,
            notifications_enabled INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT NOW()
        )
    ''')
    await pg.execute('''
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
    await pg.execute('''
        CREATE TABLE IF NOT EXISTS offers (
            id SERIAL PRIMARY KEY,
            supplier_id BIGINT NOT NULL,
            catalog_id INTEGER NOT NULL,
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
    await pg.execute('''
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
    await pg.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id SERIAL PRIMARY KEY,
            deal_id INTEGER NOT NULL,
            sender_id BIGINT NOT NULL,
            message TEXT NOT NULL,
            attachment_url TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        )
    ''')
    await pg.execute('''
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
    await pg.execute('''
        CREATE TABLE IF NOT EXISTS supplier_requests (
            id SERIAL PRIMARY KEY,
            telegram_id BIGINT NOT NULL,
            company_name TEXT NOT NULL,
            city TEXT NOT NULL,
            phone TEXT NOT NULL,
            status TEXT DEFAULT 'new',
            created_at TIMESTAMP DEFAULT NOW()
        )
    ''')
    await pg.execute('''
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
    await pg.execute('''
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
    await pg.execute('''
        CREATE TABLE IF NOT EXISTS buyer_request_responses (
            id SERIAL PRIMARY KEY,
            request_id INTEGER NOT NULL,
            supplier_id BIGINT NOT NULL,
            price INTEGER NOT NULL,
            comment TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        )
    ''')

    # ============ Миграция данных ============

    # users
    rows = lite.execute('SELECT * FROM users').fetchall()
    print(f"Мигрируем users: {len(rows)} записей")
    for r in rows:
        notif = 1
        try:
            notif = r['notifications_enabled']
        except (IndexError, KeyError):
            pass
        await pg.execute('''
            INSERT INTO users (telegram_id, username, full_name, phone, company_name, city,
                is_supplier, is_verified, role_selected, rating, deals_count, notifications_enabled, created_at)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)
            ON CONFLICT (telegram_id) DO NOTHING
        ''', r['telegram_id'], r['username'], r['full_name'], r['phone'],
             r['company_name'], r['city'], r['is_supplier'], r['is_verified'],
             r['role_selected'] if 'role_selected' in r.keys() else 0,
             r['rating'], r['deals_count'], notif, r['created_at'])

    # catalog
    rows = lite.execute('SELECT * FROM catalog').fetchall()
    print(f"Мигрируем catalog: {len(rows)} записей")
    for r in rows:
        await pg.execute('''
            INSERT INTO catalog (id, category, brand, model, memory, color, sku, is_active, created_at)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
            ON CONFLICT (sku) DO NOTHING
        ''', r['id'], r['category'], r['brand'], r['model'], r['memory'],
             r['color'], r['sku'], r['is_active'], r['created_at'])
    # Fix catalog sequence
    max_cat = lite.execute('SELECT MAX(id) FROM catalog').fetchone()[0] or 0
    if max_cat > 0:
        await pg.execute(f"SELECT setval('catalog_id_seq', {max_cat})")

    # offers
    rows = lite.execute('SELECT * FROM offers').fetchall()
    print(f"Мигрируем offers: {len(rows)} записей")
    for r in rows:
        ph = 0
        try:
            ph = r['price_hidden']
        except (IndexError, KeyError):
            pass
        await pg.execute('''
            INSERT INTO offers (id, supplier_id, catalog_id, price, quantity, moq, condition,
                delivery_days, warranty_months, is_available, is_visible, price_hidden, comment, created_at, updated_at)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15)
            ON CONFLICT DO NOTHING
        ''', r['id'], r['supplier_id'], r['catalog_id'], r['price'], r['quantity'],
             r['moq'], r['condition'], r['delivery_days'], r['warranty_months'],
             r['is_available'], r['is_visible'], ph, r['comment'],
             r['created_at'], r['updated_at'])
    max_off = lite.execute('SELECT MAX(id) FROM offers').fetchone()[0] or 0
    if max_off > 0:
        await pg.execute(f"SELECT setval('offers_id_seq', {max_off})")

    # deals
    rows = lite.execute('SELECT * FROM deals').fetchall()
    print(f"Мигрируем deals: {len(rows)} записей")
    for r in rows:
        await pg.execute('''
            INSERT INTO deals (id, buyer_id, supplier_id, offer_id, quantity, price, total_price,
                status, created_at, updated_at, closed_at)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
            ON CONFLICT DO NOTHING
        ''', r['id'], r['buyer_id'], r['supplier_id'], r['offer_id'], r['quantity'],
             r['price'], r['total_price'], r['status'], r['created_at'], r['updated_at'], r['closed_at'])
    max_deal = lite.execute('SELECT MAX(id) FROM deals').fetchone()[0] or 0
    if max_deal > 0:
        await pg.execute(f"SELECT setval('deals_id_seq', {max_deal})")

    # messages
    rows = lite.execute('SELECT * FROM messages').fetchall()
    print(f"Мигрируем messages: {len(rows)} записей")
    for r in rows:
        await pg.execute('''
            INSERT INTO messages (id, deal_id, sender_id, message, attachment_url, created_at)
            VALUES ($1,$2,$3,$4,$5,$6) ON CONFLICT DO NOTHING
        ''', r['id'], r['deal_id'], r['sender_id'], r['message'], r['attachment_url'], r['created_at'])

    # reviews
    rows = lite.execute('SELECT * FROM reviews').fetchall()
    print(f"Мигрируем reviews: {len(rows)} записей")
    for r in rows:
        await pg.execute('''
            INSERT INTO reviews (id, deal_id, supplier_id, buyer_id, rating, comment, created_at)
            VALUES ($1,$2,$3,$4,$5,$6,$7) ON CONFLICT DO NOTHING
        ''', r['id'], r['deal_id'], r['supplier_id'], r['buyer_id'], r['rating'], r['comment'], r['created_at'])

    # supplier_requests
    rows = lite.execute('SELECT * FROM supplier_requests').fetchall()
    print(f"Мигрируем supplier_requests: {len(rows)} записей")
    for r in rows:
        await pg.execute('''
            INSERT INTO supplier_requests (id, telegram_id, company_name, city, phone, status, created_at)
            VALUES ($1,$2,$3,$4,$5,$6,$7) ON CONFLICT DO NOTHING
        ''', r['id'], r['telegram_id'], r['company_name'], r['city'], r['phone'], r['status'], r['created_at'])

    # price_requests
    rows = lite.execute('SELECT * FROM price_requests').fetchall()
    print(f"Мигрируем price_requests: {len(rows)} записей")
    for r in rows:
        await pg.execute('''
            INSERT INTO price_requests (id, offer_id, buyer_id, supplier_id, quantity, status, buyer_price, created_at, responded_at)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9) ON CONFLICT DO NOTHING
        ''', r['id'], r['offer_id'], r['buyer_id'], r['supplier_id'], r['quantity'],
             r['status'], r['buyer_price'], r['created_at'], r['responded_at'])

    # buyer_requests
    try:
        rows = lite.execute('SELECT * FROM buyer_requests').fetchall()
        print(f"Мигрируем buyer_requests: {len(rows)} записей")
        for r in rows:
            await pg.execute('''
                INSERT INTO buyer_requests (id, buyer_id, model, memory, color, quantity, max_price, comment, status, created_at)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10) ON CONFLICT DO NOTHING
            ''', r['id'], r['buyer_id'], r['model'], r['memory'], r['color'],
                 r['quantity'], r['max_price'], r['comment'], r['status'], r['created_at'])
    except Exception as e:
        print(f"buyer_requests: {e}")

    # buyer_request_responses
    try:
        rows = lite.execute('SELECT * FROM buyer_request_responses').fetchall()
        print(f"Мигрируем buyer_request_responses: {len(rows)} записей")
        for r in rows:
            await pg.execute('''
                INSERT INTO buyer_request_responses (id, request_id, supplier_id, price, comment, created_at)
                VALUES ($1,$2,$3,$4,$5,$6) ON CONFLICT DO NOTHING
            ''', r['id'], r['request_id'], r['supplier_id'], r['price'], r['comment'], r['created_at'])
    except Exception as e:
        print(f"buyer_request_responses: {e}")

    # Индексы
    await pg.execute('CREATE INDEX IF NOT EXISTS idx_offers_supplier ON offers(supplier_id)')
    await pg.execute('CREATE INDEX IF NOT EXISTS idx_offers_catalog ON offers(catalog_id)')
    await pg.execute('CREATE INDEX IF NOT EXISTS idx_deals_buyer ON deals(buyer_id)')
    await pg.execute('CREATE INDEX IF NOT EXISTS idx_deals_supplier ON deals(supplier_id)')
    await pg.execute('CREATE INDEX IF NOT EXISTS idx_messages_deal ON messages(deal_id)')
    await pg.execute('CREATE INDEX IF NOT EXISTS idx_price_requests_supplier ON price_requests(supplier_id)')
    await pg.execute('CREATE INDEX IF NOT EXISTS idx_price_requests_buyer ON price_requests(buyer_id)')

    await pg.close()
    lite.close()
    print("\n✅ Миграция завершена успешно!")


if __name__ == "__main__":
    asyncio.run(migrate())
