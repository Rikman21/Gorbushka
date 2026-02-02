import sqlite3
import logging

DB_NAME = "market.db"

# !!! ВАЖНО: ОСТАВЬТЕ ЗДЕСЬ ВАШ ПОЛНЫЙ СПИСОК INITIAL_PRODUCTS ИЗ 123 ТОВАРОВ !!!
# Я сократил его для краткости, но вы должны оставить полный.
INITIAL_PRODUCTS = [
    INITIAL_PRODUCTS = [
    ('16E-DP-001', 'iPhone 16e', '128 GB', 'Black', 'Dual Physical SIM'),
    ('16E-DP-002', 'iPhone 16e', '256 GB', 'Black', 'Dual Physical SIM'),
    ('16E-DP-003', 'iPhone 16e', '512 GB', 'Black', 'Dual Physical SIM'),
    ('16E-DP-004', 'iPhone 16e', '128 GB', 'White', 'Dual Physical SIM'),
    ('16E-DP-005', 'iPhone 16e', '256 GB', 'White', 'Dual Physical SIM'),
    ('16E-DP-006', 'iPhone 16e', '512 GB', 'White', 'Dual Physical SIM'),
    ('16E-PE-001', 'iPhone 16e', '128 GB', 'Black', 'Physical + eSIM'),
    ('16E-PE-002', 'iPhone 16e', '256 GB', 'Black', 'Physical + eSIM'),
    ('16E-PE-003', 'iPhone 16e', '512 GB', 'Black', 'Physical + eSIM'),
    ('16E-PE-004', 'iPhone 16e', '128 GB', 'White', 'Physical + eSIM'),
    ('16E-PE-005', 'iPhone 16e', '256 GB', 'White', 'Physical + eSIM'),
    ('16E-PE-006', 'iPhone 16e', '512 GB', 'White', 'Physical + eSIM'),
    ('16E-E-001', 'iPhone 16e', '128 GB', 'eSIM only', 'Black'), # Исправлено под структуру
    ('16-DP-001', 'iPhone 16', '128 GB', 'Black', 'Dual Physical SIM'),
    ('16-DP-002', 'iPhone 16', '256 GB', 'Black', 'Dual Physical SIM'),
    ('16-DP-003', 'iPhone 16', '512 GB', 'Black', 'Dual Physical SIM'),
    ('16-DP-004', 'iPhone 16', '128 GB', 'White', 'Dual Physical SIM'),
    ('16-DP-005', 'iPhone 16', '256 GB', 'White', 'Dual Physical SIM'),
    ('16-DP-006', 'iPhone 16', '512 GB', 'White', 'Dual Physical SIM'),
    ('16-DP-007', 'iPhone 16', '128 GB', 'Pink', 'Dual Physical SIM'),
    ('16-DP-008', 'iPhone 16', '256 GB', 'Pink', 'Dual Physical SIM'),
    ('16-DP-009', 'iPhone 16', '512 GB', 'Pink', 'Dual Physical SIM'),
    ('16-DP-010', 'iPhone 16', '128 GB', 'Teal', 'Dual Physical SIM'),
    ('16-DP-011', 'iPhone 16', '256 GB', 'Teal', 'Dual Physical SIM'),
    ('16-DP-012', 'iPhone 16', '512 GB', 'Teal', 'Dual Physical SIM'),
    ('16-DP-013', 'iPhone 16', '128 GB', 'Ultramarine', 'Dual Physical SIM'),
    ('16-DP-014', 'iPhone 16', '256 GB', 'Ultramarine', 'Dual Physical SIM'),
    ('16-DP-015', 'iPhone 16', '512 GB', 'Ultramarine', 'Dual Physical SIM'),
    ('16-PE-001', 'iPhone 16', '128 GB', 'Black', 'Physical + eSIM'),
    ('16-PE-002', 'iPhone 16', '256 GB', 'Black', 'Physical + eSIM'),
    ('16-PE-003', 'iPhone 16', '512 GB', 'Black', 'Physical + eSIM'),
    ('16-PE-004', 'iPhone 16', '128 GB', 'White', 'Physical + eSIM'),
    ('16-PE-005', 'iPhone 16', '256 GB', 'White', 'Physical + eSIM'),
    ('16-PE-006', 'iPhone 16', '512 GB', 'White', 'Physical + eSIM'),
    ('16-PE-007', 'iPhone 16', '128 GB', 'Pink', 'Physical + eSIM'),
    ('16-PE-008', 'iPhone 16', '256 GB', 'Pink', 'Physical + eSIM'),
    ('16-PE-009', 'iPhone 16', '512 GB', 'Pink', 'Physical + eSIM'),
    ('16-PE-010', 'iPhone 16', '128 GB', 'Teal', 'Physical + eSIM'),
    ('16-PE-011', 'iPhone 16', '256 GB', 'Teal', 'Physical + eSIM'),
    ('16-PE-012', 'iPhone 16', '512 GB', 'Teal', 'Physical + eSIM'),
    ('16-PE-013', 'iPhone 16', '128 GB', 'Ultramarine', 'Physical + eSIM'),
    ('16-PE-014', 'iPhone 16', '256 GB', 'Ultramarine', 'Physical + eSIM'),
    ('16-PE-015', 'iPhone 16', '512 GB', 'Ultramarine', 'Physical + eSIM'),
    ('16P-DP-001', 'iPhone 16 Plus', '128 GB', 'Black', 'Dual Physical SIM'),
    ('16P-DP-002', 'iPhone 16 Plus', '256 GB', 'Black', 'Dual Physical SIM'),
    ('16P-DP-003', 'iPhone 16 Plus', '512 GB', 'Black', 'Dual Physical SIM'),
    ('16P-DP-004', 'iPhone 16 Plus', '128 GB', 'White', 'Dual Physical SIM'),
    ('16P-DP-005', 'iPhone 16 Plus', '256 GB', 'White', 'Dual Physical SIM'),
    ('16P-DP-006', 'iPhone 16 Plus', '512 GB', 'White', 'Dual Physical SIM'),
    ('16P-DP-007', 'iPhone 16 Plus', '128 GB', 'Pink', 'Dual Physical SIM'),
    ('16P-DP-008', 'iPhone 16 Plus', '256 GB', 'Pink', 'Dual Physical SIM'),
    ('16P-DP-009', 'iPhone 16 Plus', '512 GB', 'Pink', 'Dual Physical SIM'),
    ('16P-DP-010', 'iPhone 16 Plus', '128 GB', 'Teal', 'Dual Physical SIM'),
    ('16P-DP-011', 'iPhone 16 Plus', '256 GB', 'Teal', 'Dual Physical SIM'),
    ('16P-DP-012', 'iPhone 16 Plus', '512 GB', 'Teal', 'Dual Physical SIM'),
    ('16P-DP-013', 'iPhone 16 Plus', '128 GB', 'Ultramarine', 'Dual Physical SIM'),
    ('16P-DP-014', 'iPhone 16 Plus', '256 GB', 'Ultramarine', 'Dual Physical SIM'),
    ('16P-DP-015', 'iPhone 16 Plus', '512 GB', 'Ultramarine', 'Dual Physical SIM'),
    ('16P-PE-001', 'iPhone 16 Plus', '128 GB', 'Black', 'Physical + eSIM'),
    ('16P-PE-002', 'iPhone 16 Plus', '256 GB', 'Black', 'Physical + eSIM'),
    ('16P-PE-003', 'iPhone 16 Plus', '512 GB', 'Black', 'Physical + eSIM'),
    ('16P-PE-004', 'iPhone 16 Plus', '128 GB', 'White', 'Physical + eSIM'),
    ('16P-PE-005', 'iPhone 16 Plus', '256 GB', 'White', 'Physical + eSIM'),
    ('16P-PE-006', 'iPhone 16 Plus', '512 GB', 'White', 'Physical + eSIM'),
    ('16P-PE-007', 'iPhone 16 Plus', '128 GB', 'Pink', 'Physical + eSIM'),
    ('16P-PE-008', 'iPhone 16 Plus', '256 GB', 'Pink', 'Physical + eSIM'),
    ('16P-PE-009', 'iPhone 16 Plus', '512 GB', 'Pink', 'Physical + eSIM'),
    ('16P-PE-010', 'iPhone 16 Plus', '128 GB', 'Teal', 'Physical + eSIM'),
    ('16P-PE-011', 'iPhone 16 Plus', '256 GB', 'Teal', 'Physical + eSIM'),
    ('16P-PE-012', 'iPhone 16 Plus', '512 GB', 'Teal', 'Physical + eSIM'),
    ('16P-PE-013', 'iPhone 16 Plus', '128 GB', 'Ultramarine', 'Physical + eSIM'),
    ('16P-PE-014', 'iPhone 16 Plus', '256 GB', 'Ultramarine', 'Physical + eSIM'),
    ('16P-PE-015', 'iPhone 16 Plus', '512 GB', 'Ultramarine', 'Physical + eSIM'),
    ('16PR-DP-001', 'iPhone 16 Pro', '128 GB', 'Black Titanium', 'Dual Physical SIM'),
    ('16PR-DP-002', 'iPhone 16 Pro', '256 GB', 'Black Titanium', 'Dual Physical SIM'),
    ('16PR-DP-003', 'iPhone 16 Pro', '512 GB', 'Black Titanium', 'Dual Physical SIM'),
    ('16PR-DP-004', 'iPhone 16 Pro', '1 TB', 'Black Titanium', 'Dual Physical SIM'),
    ('16PR-DP-005', 'iPhone 16 Pro', '128 GB', 'White Titanium', 'Dual Physical SIM'),
    ('16PR-DP-006', 'iPhone 16 Pro', '256 GB', 'White Titanium', 'Dual Physical SIM'),
    ('16PR-DP-007', 'iPhone 16 Pro', '512 GB', 'White Titanium', 'Dual Physical SIM'),
    ('16PR-DP-008', 'iPhone 16 Pro', '1 TB', 'White Titanium', 'Dual Physical SIM'),
    ('16PR-DP-009', 'iPhone 16 Pro', '128 GB', 'Natural Titanium', 'Dual Physical SIM'),
    ('16PR-DP-010', 'iPhone 16 Pro', '256 GB', 'Natural Titanium', 'Dual Physical SIM'),
    ('16PR-DP-011', 'iPhone 16 Pro', '512 GB', 'Natural Titanium', 'Dual Physical SIM'),
    ('16PR-DP-012', 'iPhone 16 Pro', '1 TB', 'Natural Titanium', 'Dual Physical SIM'),
    ('16PR-DP-013', 'iPhone 16 Pro', '128 GB', 'Desert Titanium', 'Dual Physical SIM'),
    ('16PR-DP-014', 'iPhone 16 Pro', '256 GB', 'Desert Titanium', 'Dual Physical SIM'),
    ('16PR-DP-015', 'iPhone 16 Pro', '512 GB', 'Desert Titanium', 'Dual Physical SIM'),
    ('16PR-DP-016', 'iPhone 16 Pro', '1 TB', 'Desert Titanium', 'Dual Physical SIM'),
    ('16PR-PE-001', 'iPhone 16 Pro', '128 GB', 'Black Titanium', 'Physical + eSIM'),
    ('16PR-PE-002', 'iPhone 16 Pro', '256 GB', 'Black Titanium', 'Physical + eSIM'),
    ('16PR-PE-003', 'iPhone 16 Pro', '512 GB', 'Black Titanium', 'Physical + eSIM'),
    ('16PR-PE-004', 'iPhone 16 Pro', '1 TB', 'Black Titanium', 'Physical + eSIM'),
    ('16PR-PE-005', 'iPhone 16 Pro', '128 GB', 'White Titanium', 'Physical + eSIM'),
    ('16PR-PE-006', 'iPhone 16 Pro', '256 GB', 'White Titanium', 'Physical + eSIM'),
    ('16PR-PE-007', 'iPhone 16 Pro', '512 GB', 'White Titanium', 'Physical + eSIM'),
    ('16PR-PE-008', 'iPhone 16 Pro', '1 TB', 'White Titanium', 'Physical + eSIM'),
    ('16PR-PE-009', 'iPhone 16 Pro', '128 GB', 'Natural Titanium', 'Physical + eSIM'),
    ('16PR-PE-010', 'iPhone 16 Pro', '256 GB', 'Natural Titanium', 'Physical + eSIM'),
    ('16PR-PE-011', 'iPhone 16 Pro', '512 GB', 'Natural Titanium', 'Physical + eSIM'),
    ('16PR-PE-012', 'iPhone 16 Pro', '1 TB', 'Natural Titanium', 'Physical + eSIM'),
    ('16PR-PE-013', 'iPhone 16 Pro', '128 GB', 'Desert Titanium', 'Physical + eSIM'),
    ('16PR-PE-014', 'iPhone 16 Pro', '256 GB', 'Desert Titanium', 'Physical + eSIM'),
    ('16PR-PE-015', 'iPhone 16 Pro', '512 GB', 'Desert Titanium', 'Physical + eSIM'),
    ('16PR-PE-016', 'iPhone 16 Pro', '1 TB', 'Desert Titanium', 'Physical + eSIM'),
    ('16PM-DP-001', 'iPhone 16 Pro Max', '256 GB', 'Black Titanium', 'Dual Physical SIM'),
    ('16PM-DP-002', 'iPhone 16 Pro Max', '512 GB', 'Black Titanium', 'Dual Physical SIM'),
    ('16PM-DP-003', 'iPhone 16 Pro Max', '1 TB', 'Black Titanium', 'Dual Physical SIM'),
    ('16PM-DP-004', 'iPhone 16 Pro Max', '256 GB', 'White Titanium', 'Dual Physical SIM'),
    ('16PM-DP-005', 'iPhone 16 Pro Max', '512 GB', 'White Titanium', 'Dual Physical SIM'),
    ('16PM-DP-006', 'iPhone 16 Pro Max', '1 TB', 'White Titanium', 'Dual Physical SIM'),
    ('16PM-DP-007', 'iPhone 16 Pro Max', '256 GB', 'Natural Titanium', 'Dual Physical SIM'),
    ('16PM-DP-008', 'iPhone 16 Pro Max', '512 GB', 'Natural Titanium', 'Dual Physical SIM'),
    ('16PM-DP-009', 'iPhone 16 Pro Max', '1 TB', 'Natural Titanium', 'Dual Physical SIM'),
    ('16PM-DP-010', 'iPhone 16 Pro Max', '256 GB', 'Desert Titanium', 'Dual Physical SIM'),
    ('16PM-DP-011', 'iPhone 16 Pro Max', '512 GB', 'Desert Titanium', 'Dual Physical SIM'),
    ('16PM-DP-012', 'iPhone 16 Pro Max', '1 TB', 'Desert Titanium', 'Dual Physical SIM'),
    ('16PM-PE-001', 'iPhone 16 Pro Max', '256 GB', 'Black Titanium', 'Physical + eSIM'),
    ('16PM-PE-002', 'iPhone 16 Pro Max', '512 GB', 'Black Titanium', 'Physical + eSIM'),
    ('16PM-PE-003', 'iPhone 16 Pro Max', '1 TB', 'Black Titanium', 'Physical + eSIM'),
    ('16PM-PE-004', 'iPhone 16 Pro Max', '256 GB', 'White Titanium', 'Physical + eSIM'),
    ('16PM-PE-005', 'iPhone 16 Pro Max', '512 GB', 'White Titanium', 'Physical + eSIM'),
    ('16PM-PE-006', 'iPhone 16 Pro Max', '1 TB', 'White Titanium', 'Physical + eSIM'),
    ('16PM-PE-007', 'iPhone 16 Pro Max', '256 GB', 'Natural Titanium', 'Physical + eSIM'),
    ('16PM-PE-008', 'iPhone 16 Pro Max', '512 GB', 'Natural Titanium', 'Physical + eSIM'),
    ('16PM-PE-009', 'iPhone 16 Pro Max', '1 TB', 'Natural Titanium', 'Physical + eSIM'),
    ('16PM-PE-010', 'iPhone 16 Pro Max', '256 GB', 'Desert Titanium', 'Physical + eSIM'),
    ('16PM-PE-011', 'iPhone 16 Pro Max', '512 GB', 'Desert Titanium', 'Physical + eSIM'),
    ('16PM-PE-012', 'iPhone 16 Pro Max', '1 TB', 'Desert Titanium', 'Physical + eSIM')
]

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            sku TEXT PRIMARY KEY,
            model TEXT,
            memory TEXT,
            color TEXT,
            sim TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS offers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            seller_id INTEGER,
            seller_username TEXT,
            sku TEXT,
            price INTEGER,
            FOREIGN KEY(sku) REFERENCES products(sku)
        )
    ''')

    cursor.execute('SELECT count(*) FROM products')
    count = cursor.fetchone()[0]
    if count == 0:
        try:
            cursor.executemany('INSERT OR IGNORE INTO products (sku, model, memory, color, sim) VALUES (?, ?, ?, ?, ?)', INITIAL_PRODUCTS)
        except:
            pass
        conn.commit()
    
    conn.commit()
    conn.close()

# --- ФУНКЦИИ ---

def get_catalog_for_excel():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT sku, model, memory, color, sim FROM products ORDER BY model, memory, color')
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_all_offers_for_web():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    # ДОБАВИЛ o.seller_id В ЗАПРОС 👇
    query = '''
        SELECT o.id, o.seller_username, p.model || ' ' || p.memory || ' ' || p.color || ' ' || p.sim as full_name, o.price, o.sku, o.seller_id
        FROM offers o
        JOIN products p ON o.sku = p.sku
    '''
    cursor.execute(query)
    results = []
    for row in cursor.fetchall():
        results.append({
            "id": row[0],
            "username": row[1],
            "product": row[2],
            "price": row[3],
            "sku": row[4],
            "seller_id": row[5] # Передаем ID продавца на сайт
        })
    conn.close()
    return results

def update_prices_from_excel(user_id, username, price_list):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    updated_count = 0
    
    for sku, price in price_list:
        cursor.execute('DELETE FROM offers WHERE seller_id = ? AND sku = ?', (user_id, sku))
        if price is not None and price > 0:
            cursor.execute('INSERT INTO offers (seller_id, seller_username, sku, price) VALUES (?, ?, ?, ?)', 
                           (user_id, username, sku, price))
            updated_count += 1
            
    conn.commit()
    conn.close()
    return updated_count

# --- НОВАЯ ФУНКЦИЯ УДАЛЕНИЯ ---
def delete_offer_by_sku(seller_id, sku):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM offers WHERE seller_id = ? AND sku = ?', (seller_id, sku))
    conn.commit()
    conn.close()




