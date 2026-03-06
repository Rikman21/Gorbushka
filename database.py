import sqlite3
import logging
import sys
import os
from datetime import datetime

DB_NAME = os.path.join(os.path.dirname(os.path.abspath(__file__)), "market.db")

def init_db():
    """Инициализация базы данных для биржи"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Таблица пользователей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            telegram_id INTEGER UNIQUE NOT NULL,
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
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Таблица каталога (управляется админом)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS catalog (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            brand TEXT NOT NULL,
            model TEXT NOT NULL,
            memory TEXT,
            color TEXT,
            sku TEXT UNIQUE NOT NULL,
            is_active INTEGER DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Таблица предложений поставщиков
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS offers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            supplier_id INTEGER NOT NULL,
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
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (supplier_id) REFERENCES users(telegram_id),
            FOREIGN KEY (catalog_id) REFERENCES catalog(id)
        )
    ''')
    
    # Таблица сделок
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS deals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            buyer_id INTEGER NOT NULL,
            supplier_id INTEGER NOT NULL,
            offer_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            price INTEGER NOT NULL,
            total_price INTEGER NOT NULL,
            status TEXT DEFAULT 'created',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            closed_at DATETIME,
            FOREIGN KEY (buyer_id) REFERENCES users(telegram_id),
            FOREIGN KEY (supplier_id) REFERENCES users(telegram_id),
            FOREIGN KEY (offer_id) REFERENCES offers(id)
        )
    ''')
    
    # Таблица сообщений в чате сделки
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            deal_id INTEGER NOT NULL,
            sender_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            attachment_url TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (deal_id) REFERENCES deals(id),
            FOREIGN KEY (sender_id) REFERENCES users(telegram_id)
        )
    ''')
    
    # Таблица отзывов
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            deal_id INTEGER NOT NULL,
            supplier_id INTEGER NOT NULL,
            buyer_id INTEGER NOT NULL,
            rating INTEGER NOT NULL,
            comment TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (deal_id) REFERENCES deals(id),
            FOREIGN KEY (supplier_id) REFERENCES users(telegram_id),
            FOREIGN KEY (buyer_id) REFERENCES users(telegram_id)
        )
    ''')
    
    # Таблица заявок на регистрацию поставщика
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS supplier_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER NOT NULL,
            company_name TEXT NOT NULL,
            city TEXT NOT NULL,
            phone TEXT NOT NULL,
            status TEXT DEFAULT 'new',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (telegram_id) REFERENCES users(telegram_id)
        )
    ''')

    # Таблица запросов цены (для скрытых прайсов)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS price_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            offer_id INTEGER NOT NULL,
            buyer_id INTEGER NOT NULL,
            supplier_id INTEGER NOT NULL,
            quantity INTEGER DEFAULT 1,
            status TEXT DEFAULT 'pending',
            buyer_price INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            responded_at DATETIME,
            FOREIGN KEY (offer_id) REFERENCES offers(id),
            FOREIGN KEY (buyer_id) REFERENCES users(telegram_id),
            FOREIGN KEY (supplier_id) REFERENCES users(telegram_id)
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_price_requests_supplier ON price_requests(supplier_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_price_requests_buyer ON price_requests(buyer_id)')
    
    # Индексы для быстрого поиска
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_offers_supplier ON offers(supplier_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_offers_catalog ON offers(catalog_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_deals_buyer ON deals(buyer_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_deals_supplier ON deals(supplier_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_messages_deal ON messages(deal_id)')

    # Миграции: добавить колонки если не существуют
    for migration in [
        'ALTER TABLE users ADD COLUMN role_selected INTEGER DEFAULT 0',
        'ALTER TABLE offers ADD COLUMN price_hidden INTEGER DEFAULT 0',
    ]:
        try:
            cursor.execute(migration)
        except sqlite3.OperationalError:
            pass

    conn.commit()
    conn.close()
    logging.info("База данных инициализирована")
    # Заполнить каталог если он пустой
    _seed_catalog_if_empty()


def _seed_catalog_if_empty():
    """Заполняет каталог товарами если он пустой."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM catalog")
    count = cursor.fetchone()[0]
    conn.close()
    if count == 0:
        try:
            # Добавляем директорию скрипта в sys.path для работы в systemd
            script_dir = os.path.dirname(os.path.abspath(__file__))
            if script_dir not in sys.path:
                sys.path.insert(0, script_dir)
            import seed_catalog
            conn2 = sqlite3.connect(DB_NAME)
            added, _ = seed_catalog.seed(conn2)
            conn2.close()
            logging.info(f"Каталог заполнен: {added} товаров")
        except Exception as e:
            logging.warning(f"Не удалось заполнить каталог: {e}")

# ==================== USERS ====================

def create_or_update_user(telegram_id, username=None, full_name=None):
    """Создать или обновить пользователя"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO users (telegram_id, username, full_name)
        VALUES (?, ?, ?)
        ON CONFLICT(telegram_id) DO UPDATE SET
            username = excluded.username,
            full_name = excluded.full_name
    ''', (telegram_id, username, full_name))
    conn.commit()
    conn.close()

def get_user(telegram_id):
    """Получить данные пользователя"""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE telegram_id = ?', (telegram_id,))
    user = cursor.fetchone()
    conn.close()
    return dict(user) if user else None

def update_user_supplier_info(telegram_id, company_name, city, phone):
    """Обновить информацию поставщика"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE users SET 
            is_supplier = 1,
            company_name = ?,
            city = ?,
            phone = ?
        WHERE telegram_id = ?
    ''', (company_name, city, phone, telegram_id))
    conn.commit()
    conn.close()


def create_supplier_request(telegram_id, company_name, city, phone):
    """Создать заявку на поставщика (статус pending). Поставщик назначается после одобрения админом."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO supplier_requests (telegram_id, company_name, city, phone, status)
        VALUES (?, ?, ?, ?, 'pending')
    ''', (telegram_id, company_name, city, phone))
    conn.commit()
    conn.close()


def get_latest_supplier_request(telegram_id):
    """Получить последнюю заявку поставщика по telegram_id."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        'SELECT * FROM supplier_requests WHERE telegram_id = ? ORDER BY id DESC LIMIT 1',
        (telegram_id,),
    )
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def approve_supplier_request(telegram_id):
    """Одобрить заявку: обновить users (is_supplier, company_name, city, phone) и статус заявки."""
    req = get_latest_supplier_request(telegram_id)
    if not req:
        return False
    if req.get("status") == "approved":
        return True
    update_user_supplier_info(telegram_id, req["company_name"], req["city"], req["phone"])
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE supplier_requests SET status = 'approved' WHERE id = ?", (req["id"],))
    conn.commit()
    conn.close()
    return True


def reject_supplier_request(telegram_id):
    """Отклонить последнюю заявку поставщика."""
    req = get_latest_supplier_request(telegram_id)
    if not req:
        return False
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE supplier_requests SET status = 'rejected' WHERE id = ?", (req["id"],))
    conn.commit()
    conn.close()
    return True


# ==================== CATALOG ====================

def add_catalog_item(category, brand, model, memory, color, sku):
    """Добавить товар в каталог (только админ)"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO catalog (category, brand, model, memory, color, sku)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (category, brand, model, memory, color, sku))
        conn.commit()
        conn.close()
        return True, "Товар добавлен в каталог"
    except sqlite3.IntegrityError:
        conn.close()
        return False, "Товар с таким SKU уже существует"

def get_catalog(filters=None):
    """Получить каталог с фильтрами (все товары)"""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    query = 'SELECT * FROM catalog WHERE is_active = 1'
    params = []
    
    if filters:
        if filters.get('category'):
            query += ' AND category = ?'
            params.append(filters['category'])
        if filters.get('model'):
            query += ' AND model LIKE ?'
            params.append(f"%{filters['model']}%")
        if filters.get('memory'):
            query += ' AND memory = ?'
            params.append(filters['memory'])
    
    cursor.execute(query, params)
    items = cursor.fetchall()
    conn.close()
    return [dict(item) for item in items]


def get_catalog_with_offers(filters=None):
    """Каталог только тех товаров, у которых есть хотя бы одно активное предложение.
    Для каждого: min_price, max_price, offers_count."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    query = '''
        SELECT
            c.id, c.category, c.brand, c.model, c.memory, c.color, c.sku, c.is_active, c.created_at,
            MIN(o.price) AS min_price,
            MAX(o.price) AS max_price,
            COUNT(o.id) AS offers_count
        FROM catalog c
        INNER JOIN offers o ON o.catalog_id = c.id AND o.is_visible = 1 AND o.is_available = 1
        WHERE c.is_active = 1
    '''
    params = []
    if filters:
        if filters.get('category'):
            query += ' AND c.category = ?'
            params.append(filters['category'])
        if filters.get('model'):
            query += ' AND c.model LIKE ?'
            params.append(f"%{filters['model']}%")
        if filters.get('memory'):
            query += ' AND c.memory = ?'
            params.append(filters['memory'])
    query += ' GROUP BY c.id HAVING COUNT(o.id) > 0 ORDER BY c.brand, c.model'
    cursor.execute(query, params)
    items = cursor.fetchall()
    conn.close()
    return [dict(item) for item in items]


def get_catalog_offers(catalog_id):
    """Все активные предложения по товару (для экрана детального просмотра)."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('''
        SELECT
            o.id, o.price, o.quantity, o.moq, o.condition, o.delivery_days, o.warranty_months,
            u.telegram_id AS supplier_id, u.company_name, u.full_name, u.rating, u.deals_count, u.city
        FROM offers o
        JOIN users u ON o.supplier_id = u.telegram_id
        WHERE o.catalog_id = ? AND o.is_visible = 1 AND o.is_available = 1
        ORDER BY o.price ASC
    ''', (catalog_id,))
    offers = cursor.fetchall()
    conn.close()
    return [dict(offer) for offer in offers]

def search_catalog(query):
    """Поиск в каталоге"""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM catalog 
        WHERE is_active = 1 AND (model LIKE ? OR sku LIKE ?)
        LIMIT 20
    ''', (f"%{query}%", f"%{query}%"))
    items = cursor.fetchall()
    conn.close()
    return [dict(item) for item in items]


def find_catalog_by_model_memory_color(model, memory, color):
    """Найти id в каталоге по model, memory, color. Пустые строки и NULL считаются равными. Возвращает id или None."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    m = (model or '').strip()
    mem = (memory or '').strip()
    c = (color or '').strip()
    cursor.execute('''
        SELECT id FROM catalog
        WHERE is_active = 1 AND trim(COALESCE(model,'')) = ? AND trim(COALESCE(memory,'')) = ? AND trim(COALESCE(color,'')) = ?
        LIMIT 1
    ''', (m, mem, c))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None


def get_catalog_all_for_template():
    """Все товары каталога для экспорта шаблона: brand, model, memory, color."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT brand, model, memory, color FROM catalog WHERE is_active = 1 ORDER BY brand, model, memory, color')
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def find_catalog_by_brand_model_memory_color(brand, model, memory, color):
    """Найти id в каталоге по brand, model, memory, color. Возвращает id или None."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    b = (brand or '').strip()
    m = (model or '').strip()
    mem = (memory or '').strip()
    c = (color or '').strip()
    cursor.execute('''
        SELECT id FROM catalog
        WHERE is_active = 1 AND trim(COALESCE(brand,'')) = ? AND trim(COALESCE(model,'')) = ? AND trim(COALESCE(memory,'')) = ? AND trim(COALESCE(color,'')) = ?
        LIMIT 1
    ''', (b, m, mem, c))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None


def get_offer_by_supplier_and_catalog(supplier_id, catalog_id):
    """Предложение поставщика по catalog_id. Возвращает dict или None."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM offers WHERE supplier_id = ? AND catalog_id = ?', (supplier_id, catalog_id))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def _find_catalog_id_cursor(cursor, model, memory, color):
    """Найти id в каталоге по model, memory, color (для импорта в транзакции)."""
    m = (model or '').strip()
    mem = (memory or '').strip()
    c = (color or '').strip()
    cursor.execute('''
        SELECT id FROM catalog
        WHERE is_active = 1 AND trim(COALESCE(model,'')) = ? AND trim(COALESCE(memory,'')) = ? AND trim(COALESCE(color,'')) = ?
        LIMIT 1
    ''', (m, mem, c))
    row = cursor.fetchone()
    return row[0] if row else None


def _get_offer_cursor(cursor, supplier_id, catalog_id):
    """Получить предложение по supplier_id и catalog_id (в рамках одной транзакции)."""
    cursor.execute('SELECT id, price, quantity FROM offers WHERE supplier_id = ? AND catalog_id = ?', (supplier_id, catalog_id))
    return cursor.fetchone()


def import_offers_batch(telegram_id, rows):
    """
    Импорт офферов из списка строк в одной транзакции.
    rows: list of dicts с ключами model, memory, color, price, quantity (brand опционально).
    Поиск товара в catalog по Model, Memory, Color.
    Возвращает (success_count, error_count).
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    success_count = 0
    error_count = 0
    try:
        cursor.execute("BEGIN TRANSACTION")
        for idx, row in enumerate(rows, start=1):
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
            product_id = _find_catalog_id_cursor(cursor, model, memory, color)
            print(f"Строка {idx}: Товар ID = {product_id}")
            if not product_id:
                error_count += 1
                continue
            existing = _get_offer_cursor(cursor, telegram_id, product_id)
            if existing:
                cursor.execute(
                    "UPDATE offers SET price = ?, quantity = ?, updated_at = ? WHERE id = ?",
                    (price, quantity, datetime.now(), existing[0])
                )
            else:
                cursor.execute('''
                    INSERT INTO offers (supplier_id, catalog_id, price, quantity, moq, condition, delivery_days, warranty_months, comment)
                    VALUES (?, ?, ?, ?, 1, 'new', 0, 12, NULL)
                ''', (telegram_id, product_id, price, quantity))
            success_count += 1
        conn.commit()
    except Exception as e:
        conn.rollback()
        logging.exception("import_offers_batch")
        print("[import_offers_batch] error:", str(e))
        raise
    finally:
        conn.close()
    return success_count, error_count


# ==================== OFFERS ====================

def create_offer(supplier_id, catalog_id, price, quantity, moq, condition, delivery_days, warranty_months, comment=None):
    """Создать предложение от поставщика"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO offers (
            supplier_id, catalog_id, price, quantity, moq, condition,
            delivery_days, warranty_months, comment
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (supplier_id, catalog_id, price, quantity, moq, condition, delivery_days, warranty_months, comment))
    offer_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return offer_id

def update_offer(offer_id, **kwargs):
    """Обновить предложение"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    fields = []
    values = []
    for key, value in kwargs.items():
        if key in ['price', 'quantity', 'moq', 'condition', 'delivery_days', 'warranty_months', 'is_available', 'is_visible', 'price_hidden', 'comment']:
            fields.append(f"{key} = ?")
            values.append(value)
    
    if fields:
        fields.append("updated_at = ?")
        values.append(datetime.now())
        values.append(offer_id)
        
        query = f"UPDATE offers SET {', '.join(fields)} WHERE id = ?"
        cursor.execute(query, values)
        conn.commit()
    
    conn.close()

def get_offers(filters=None):
    """Получить предложения с фильтрами для биржи"""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
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
    
    if filters:
        if filters.get('model'):
            query += ' AND c.model LIKE ?'
            params.append(f"%{filters['model']}%")
        if filters.get('memory'):
            query += ' AND c.memory = ?'
            params.append(filters['memory'])
        if filters.get('condition'):
            query += ' AND o.condition = ?'
            params.append(filters['condition'])
        if filters.get('min_price'):
            query += ' AND o.price >= ?'
            params.append(filters['min_price'])
        if filters.get('max_price'):
            query += ' AND o.price <= ?'
            params.append(filters['max_price'])
        if filters.get('in_stock'):
            query += ' AND o.quantity > 0'
        if filters.get('verified'):
            query += ' AND u.is_verified = 1'
    
    query += ' ORDER BY o.price ASC'
    
    cursor.execute(query, params)
    offers = cursor.fetchall()
    conn.close()
    return [dict(offer) for offer in offers]

def get_offer_by_id(offer_id):
    """Получить предложение по ID (с данными каталога и поставщика)"""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('''
        SELECT 
            o.*,
            c.model, c.memory, c.color, c.brand,
            u.company_name, u.rating, u.deals_count, u.city
        FROM offers o
        JOIN catalog c ON o.catalog_id = c.id
        JOIN users u ON o.supplier_id = u.telegram_id
        WHERE o.id = ? AND o.is_visible = 1 AND o.is_available = 1
    ''', (offer_id,))
    offer = cursor.fetchone()
    conn.close()
    return dict(offer) if offer else None

def get_supplier_offers(supplier_id):
    """Получить все предложения поставщика"""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('''
        SELECT o.*, c.brand, c.model, c.memory, c.color
        FROM offers o
        JOIN catalog c ON o.catalog_id = c.id
        WHERE o.supplier_id = ?
        ORDER BY o.created_at DESC
    ''', (supplier_id,))
    offers = cursor.fetchall()
    conn.close()
    return [dict(offer) for offer in offers]

def delete_offer(offer_id, supplier_id):
    """Удалить предложение"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM offers WHERE id = ? AND supplier_id = ?', (offer_id, supplier_id))
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0

# ==================== DEALS ====================

def create_deal(buyer_id, supplier_id, offer_id, quantity, price):
    """Создать сделку"""
    total_price = quantity * price
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO deals (buyer_id, supplier_id, offer_id, quantity, price, total_price, status)
        VALUES (?, ?, ?, ?, ?, ?, 'created')
    ''', (buyer_id, supplier_id, offer_id, quantity, price, total_price))
    deal_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return deal_id

def update_deal_status(deal_id, status):
    """Обновить статус сделки"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    if status == 'closed':
        cursor.execute('''
            UPDATE deals SET status = ?, updated_at = ?, closed_at = ?
            WHERE id = ?
        ''', (status, datetime.now(), datetime.now(), deal_id))
    else:
        cursor.execute('''
            UPDATE deals SET status = ?, updated_at = ?
            WHERE id = ?
        ''', (status, datetime.now(), deal_id))
    
    conn.commit()
    conn.close()

def get_deal(deal_id):
    """Получить сделку по ID"""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('''
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
        WHERE d.id = ?
    ''', (deal_id,))
    deal = cursor.fetchone()
    conn.close()
    return dict(deal) if deal else None

def get_user_deals(telegram_id, status_filter=None):
    """Получить сделки пользователя"""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    query = '''
        SELECT 
            d.*,
            c.model, c.memory, c.color,
            CASE 
                WHEN d.buyer_id = ? THEN u.company_name
                ELSE ub.company_name
            END as counterparty
        FROM deals d
        JOIN offers o ON d.offer_id = o.id
        JOIN catalog c ON o.catalog_id = c.id
        LEFT JOIN users u ON d.supplier_id = u.telegram_id
        LEFT JOIN users ub ON d.buyer_id = ub.telegram_id
        WHERE (d.buyer_id = ? OR d.supplier_id = ?)
    '''
    params = [telegram_id, telegram_id, telegram_id]
    
    if status_filter:
        query += ' AND d.status = ?'
        params.append(status_filter)
    
    query += ' ORDER BY d.created_at DESC'
    
    cursor.execute(query, params)
    deals = cursor.fetchall()
    conn.close()
    return [dict(deal) for deal in deals]

# ==================== MESSAGES ====================

def add_message(deal_id, sender_id, message, attachment_url=None):
    """Добавить сообщение в чат сделки"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO messages (deal_id, sender_id, message, attachment_url)
        VALUES (?, ?, ?, ?)
    ''', (deal_id, sender_id, message, attachment_url))
    message_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return message_id

def get_deal_messages(deal_id):
    """Получить сообщения сделки"""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('''
        SELECT m.*, u.username, u.company_name
        FROM messages m
        JOIN users u ON m.sender_id = u.telegram_id
        WHERE m.deal_id = ?
        ORDER BY m.created_at ASC
    ''', (deal_id,))
    messages = cursor.fetchall()
    conn.close()
    return [dict(msg) for msg in messages]

# ==================== REVIEWS ====================

def add_review(deal_id, supplier_id, buyer_id, rating, comment=None):
    """Добавить отзыв о поставщике"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO reviews (deal_id, supplier_id, buyer_id, rating, comment)
        VALUES (?, ?, ?, ?, ?)
    ''', (deal_id, supplier_id, buyer_id, rating, comment))
    
    # Обновляем рейтинг поставщика
    cursor.execute('''
        UPDATE users SET 
            rating = (SELECT AVG(rating) FROM reviews WHERE supplier_id = ?),
            deals_count = deals_count + 1
        WHERE telegram_id = ?
    ''', (supplier_id, supplier_id))
    
    conn.commit()
    conn.close()

def set_user_role(telegram_id, role):
    """Установить роль пользователя. role: 'buyer' или 'supplier'."""
    is_supplier = 1 if role == 'supplier' else 0
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    # Гарантируем существование пользователя перед обновлением
    cursor.execute('INSERT OR IGNORE INTO users (telegram_id) VALUES (?)', (telegram_id,))
    cursor.execute(
        'UPDATE users SET is_supplier = ?, role_selected = 1 WHERE telegram_id = ?',
        (is_supplier, telegram_id)
    )
    conn.commit()
    conn.close()


def get_all_users(limit=500):
    """Получить всех пользователей (для админа)."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('''
        SELECT telegram_id, username, full_name, is_supplier, is_verified,
               role_selected, rating, deals_count, company_name, city, created_at
        FROM users ORDER BY created_at DESC LIMIT ?
    ''', (limit,))
    users = cursor.fetchall()
    conn.close()
    return [dict(u) for u in users]


def delete_user(telegram_id):
    """Удалить пользователя и его предложения с платформы."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM offers WHERE supplier_id = ?', (telegram_id,))
    cursor.execute('DELETE FROM users WHERE telegram_id = ?', (telegram_id,))
    conn.commit()
    conn.close()


def get_all_deals(limit=200):
    """Получить все сделки (для админа)."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('''
        SELECT d.*,
            c.model, c.memory, c.color,
            ub.username as buyer_username, ub.full_name as buyer_name,
            us.username as supplier_username, us.company_name as supplier_company
        FROM deals d
        JOIN offers o ON d.offer_id = o.id
        JOIN catalog c ON o.catalog_id = c.id
        JOIN users ub ON d.buyer_id = ub.telegram_id
        JOIN users us ON d.supplier_id = us.telegram_id
        ORDER BY d.created_at DESC LIMIT ?
    ''', (limit,))
    deals = cursor.fetchall()
    conn.close()
    return [dict(d) for d in deals]


def get_supplier_stats(supplier_id):
    """Статистика поставщика: всего сделок, % подтверждённых, % отменённых."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
            SUM(CASE WHEN status IN ('rejected','cancelled') THEN 1 ELSE 0 END) as cancelled
        FROM deals WHERE supplier_id = ?
    ''', (supplier_id,))
    row = cursor.fetchone()
    conn.close()
    total = row[0] or 0
    completed = row[1] or 0
    cancelled = row[2] or 0
    confirmed_rate = round(completed / total * 100) if total > 0 else 0
    cancel_rate = round(cancelled / total * 100) if total > 0 else 0
    return {'total': total, 'completed': completed, 'cancelled': cancelled,
            'confirmed_rate': confirmed_rate, 'cancel_rate': cancel_rate}


# ==================== PRICE REQUESTS ====================

def create_price_request(offer_id, buyer_id, supplier_id, quantity=1):
    """Создать запрос цены."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO price_requests (offer_id, buyer_id, supplier_id, quantity)
        VALUES (?, ?, ?, ?)
    ''', (offer_id, buyer_id, supplier_id, quantity))
    request_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return request_id


def get_price_request(request_id):
    """Получить запрос цены по ID."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('''
        SELECT pr.*,
            c.model, c.memory, c.color,
            ub.username as buyer_username, ub.full_name as buyer_name,
            us.company_name as supplier_company
        FROM price_requests pr
        JOIN offers o ON pr.offer_id = o.id
        JOIN catalog c ON o.catalog_id = c.id
        JOIN users ub ON pr.buyer_id = ub.telegram_id
        JOIN users us ON pr.supplier_id = us.telegram_id
        WHERE pr.id = ?
    ''', (request_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def respond_price_request(request_id, price):
    """Поставщик отвечает ценой."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE price_requests SET status = 'responded', buyer_price = ?, responded_at = ?
        WHERE id = ?
    ''', (price, datetime.now(), request_id))
    conn.commit()
    conn.close()


def expire_price_request(request_id):
    """Истёк таймер запроса цены."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE price_requests SET status = 'expired' WHERE id = ?", (request_id,))
    conn.commit()
    conn.close()


def cancel_price_request(request_id):
    """Отмена запроса цены покупателем."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE price_requests SET status = 'cancelled' WHERE id = ?", (request_id,))
    conn.commit()
    conn.close()


def get_pending_price_requests(supplier_id):
    """Входящие запросы цены для поставщика."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('''
        SELECT pr.*,
            c.model, c.memory, c.color,
            ub.username as buyer_username, ub.full_name as buyer_name
        FROM price_requests pr
        JOIN offers o ON pr.offer_id = o.id
        JOIN catalog c ON o.catalog_id = c.id
        JOIN users ub ON pr.buyer_id = ub.telegram_id
        WHERE pr.supplier_id = ? AND pr.status = 'pending'
        ORDER BY pr.created_at DESC
    ''', (supplier_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_buyer_price_requests(buyer_id):
    """Все запросы цены покупателя."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('''
        SELECT pr.*,
            c.model, c.memory, c.color,
            us.company_name as supplier_company, us.username as supplier_username
        FROM price_requests pr
        JOIN offers o ON pr.offer_id = o.id
        JOIN catalog c ON o.catalog_id = c.id
        JOIN users us ON pr.supplier_id = us.telegram_id
        WHERE pr.buyer_id = ?
        ORDER BY pr.created_at DESC
    ''', (buyer_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_supplier_reviews(supplier_id):
    """Получить отзывы о поставщике"""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('''
        SELECT r.*, u.username, u.company_name, d.created_at as deal_date
        FROM reviews r
        JOIN users u ON r.buyer_id = u.telegram_id
        JOIN deals d ON r.deal_id = d.id
        WHERE r.supplier_id = ?
        ORDER BY r.created_at DESC
    ''', (supplier_id,))
    reviews = cursor.fetchall()
    conn.close()
    return [dict(review) for review in reviews]
