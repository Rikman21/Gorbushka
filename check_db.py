"""
Проверка содержимого shop.db: список таблиц, количество строк, пример данных.
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "shop.db"


def main():
    if not DB_PATH.exists():
        print(f"Файл {DB_PATH} не найден.")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Список таблиц
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    )
    tables = [row[0] for row in cur.fetchall()]
    print("Таблицы в shop.db:")
    print("-" * 40)
    for t in tables:
        cur.execute(f"SELECT COUNT(*) FROM [{t}]")
        n = cur.fetchone()[0]
        print(f"  {t}: {n} записей")
    print()

    # Главная таблица товаров: 'base' или иначе products / apple_catalog_mvp
    main_candidates = ["base", "products", "apple_catalog_mvp"]
    main_table = None
    for name in main_candidates:
        if name in tables:
            main_table = name
            break

    if not main_table:
        print("Таблица для примера (base/products/apple_catalog_mvp) не найдена.")
        conn.close()
        return

    print(f"Первые 2 строки из таблицы '{main_table}':")
    print("-" * 40)
    cur.execute(f"SELECT * FROM [{main_table}] LIMIT 2")
    rows = cur.fetchall()
    for i, row in enumerate(rows, 1):
        print(f"  --- Строка {i} ---")
        for key in row.keys():
            print(f"    {key}: {row[key]}")
    print()

    conn.close()
    print("Готово.")


if __name__ == "__main__":
    main()
