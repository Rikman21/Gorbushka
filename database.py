import sqlite3

# Создаем подключение к файлу базы данных
def get_connection():
    return sqlite3.connect('market.db')

# 1. Создаем таблицу (вызывается один раз при старте)
def init_db():
    conn = get_connection()
    c = conn.cursor()
    # Создаем таблицу: ID продавца, Имя, Товар, Цена
    c.execute('''
        CREATE TABLE IF NOT EXISTS offers (
            user_id INTEGER,
            username TEXT,
            product_name TEXT,
            price INTEGER
        )
    ''')
    conn.commit()
    conn.close()

# 2. Добавляем или обновляем цену
def add_offer(user_id, username, product_name, price):
    conn = get_connection()
    c = conn.cursor()
    
    # Сначала удаляем старую цену этого продавца на этот же товар (чтобы не дублировать)
    c.execute("DELETE FROM offers WHERE user_id = ? AND product_name = ?", (user_id, product_name))
    
    # Записываем новую цену
    c.execute("INSERT INTO offers (user_id, username, product_name, price) VALUES (?, ?, ?, ?)", 
              (user_id, username, product_name, price))
    
    conn.commit()
    conn.close()
    print(f"💾 В БАЗУ ЗАПИСАНО: {product_name} от {username} за {price}")

# 3. Получить все предложения по товару (пригодится позже)
def get_offers_by_product(product_name):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT user_id, username, price FROM offers WHERE product_name = ?", (product_name,))
    results = c.fetchall()
    conn.close()
    return results

# ... (код выше оставляем без изменений)

# 4. ДОСТАТЬ ВСЕ ПРЕДЛОЖЕНИЯ (Для отправки в WebApp)
def get_all_offers():
    conn = get_connection()
    c = conn.cursor()
    # Берем: id продавца, имя, товар, цену
    c.execute("SELECT user_id, username, product_name, price FROM offers")
    rows = c.fetchall()
    conn.close()
    
    # Превращаем в красивый список, понятный для JavaScript
    results = []
    for row in rows:
        results.append({
            "id": row[0],
            "username": row[1],
            "product": row[2],
            "price": row[3]
        })
    return results