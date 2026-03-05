#!/usr/bin/env python3
"""
Импорт данных из CSV (папка data/) в базу market.db (та же, что у бота в main.py).
Очищает таблицы каталога и атрибутов, затем заполняет их из CSV.
Использует только стандартную библиотеку (csv, sqlite3).
"""

import csv
import os
import sqlite3
import sys

# Та же БД, что в main.py
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import database

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
DB_PATH = database.DB_NAME


def detect_separator(filepath: str) -> str:
    with open(filepath, "r", encoding="utf-8-sig") as f:
        first = f.readline()
    return ";" if first.count(";") > first.count(",") else ","


def ensure_attribute_tables(conn: sqlite3.Connection) -> None:
    """Создать таблицы атрибутов в market.db, если их ещё нет."""
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS attribute_definitions (
            attribute_id INTEGER PRIMARY KEY,
            attribute_name TEXT,
            data_type TEXT,
            unit TEXT,
            description TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS attribute_values (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            attribute_name TEXT,
            value TEXT,
            label TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS category_attribute_map (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT,
            attribute_name TEXT
        )
    """)
    conn.commit()


def clear_tables(conn: sqlite3.Connection) -> None:
    """Очистить каталог и зависимые таблицы, затем таблицы атрибутов."""
    c = conn.cursor()
    # Порядок: от зависимых к каталогу
    c.execute("DELETE FROM messages")
    c.execute("DELETE FROM reviews")
    c.execute("DELETE FROM deals")
    c.execute("DELETE FROM offers")
    c.execute("DELETE FROM catalog")
    c.execute("DELETE FROM attribute_values")
    c.execute("DELETE FROM category_attribute_map")
    c.execute("DELETE FROM attribute_definitions")
    conn.commit()
    print("  Таблицы catalog, offers, deals, messages, reviews и атрибуты очищены.")


def import_catalog(conn: sqlite3.Connection) -> int:
    """Импорт товаров из data/products.csv в catalog."""
    path = os.path.join(DATA_DIR, "products.csv")
    if not os.path.isfile(path):
        print(f"  Файл не найден: {path}")
        return 0

    sep = detect_separator(path)
    c = conn.cursor()
    count = 0
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter=sep)
        for row in reader:
            product_id = (row.get("product_id") or row.get("\ufeffproduct_id", "")).strip()
            category = (row.get("category") or "").strip()
            family = (row.get("family") or "").strip()
            model_name = (row.get("model_name") or "").strip()
            generation = (row.get("generation") or "").strip()
            form_factor = (row.get("form_factor") or "").strip()
            is_active = 1
            if "is_active" in row and str(row["is_active"]).strip() in ("0", ""):
                is_active = 0

            if not product_id or not model_name:
                continue

            memory = generation or form_factor or ""
            sku = f"SKU-{product_id}"
            try:
                c.execute("""
                    INSERT INTO catalog (category, brand, model, memory, color, sku, is_active)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (category, family, model_name, memory, "", sku, is_active))
                count += 1
            except sqlite3.IntegrityError:
                pass  # дубликат sku
    conn.commit()
    return count


def import_attributes(conn: sqlite3.Connection) -> dict:
    """Импорт attribute_definitions, attribute_values, category_attribute_map из data/."""
    c = conn.cursor()
    counts = {}

    # attribute_definitions.csv
    path = os.path.join(DATA_DIR, "attribute_definitions.csv")
    if os.path.isfile(path):
        sep = detect_separator(path)
        with open(path, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f, delimiter=sep)
            for row in reader:
                aid = row.get("attribute_id") or row.get("\ufeffattribute_id")
                name = (row.get("attribute_name") or "").strip()
                dtype = (row.get("data_type") or "").strip()
                unit = (row.get("unit") or "").strip()
                desc = (row.get("description") or "").strip()
                try:
                    c.execute(
                        "INSERT INTO attribute_definitions (attribute_id, attribute_name, data_type, unit, description) VALUES (?, ?, ?, ?, ?)",
                        (int(aid) if aid else 0, name, dtype, unit, desc),
                    )
                except (ValueError, sqlite3.IntegrityError):
                    pass
        conn.commit()
        counts["attribute_definitions"] = c.execute("SELECT COUNT(*) FROM attribute_definitions").fetchone()[0]

    # attribute_values.csv
    path = os.path.join(DATA_DIR, "attribute_values.csv")
    if os.path.isfile(path):
        sep = detect_separator(path)
        with open(path, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f, delimiter=sep)
            for row in reader:
                aname = (row.get("attribute_name") or row.get("\ufeffattribute_name") or "").strip()
                value = (row.get("value") or "").strip()
                label = (row.get("label") or "").strip()
                if aname:
                    c.execute(
                        "INSERT INTO attribute_values (attribute_name, value, label) VALUES (?, ?, ?)",
                        (aname, value, label),
                    )
        conn.commit()
        counts["attribute_values"] = c.execute("SELECT COUNT(*) FROM attribute_values").fetchone()[0]

    # category_attribute_map.csv
    path = os.path.join(DATA_DIR, "category_attribute_map.csv")
    if os.path.isfile(path):
        sep = detect_separator(path)
        with open(path, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f, delimiter=sep)
            for row in reader:
                cat = (row.get("category") or row.get("\ufeffcategory") or "").strip()
                aname = (row.get("attribute_name") or "").strip()
                if cat and aname:
                    c.execute(
                        "INSERT INTO category_attribute_map (category, attribute_name) VALUES (?, ?)",
                        (cat, aname),
                    )
        conn.commit()
        counts["category_attribute_map"] = c.execute("SELECT COUNT(*) FROM category_attribute_map").fetchone()[0]

    return counts


def main() -> None:
    if not os.path.isdir(DATA_DIR):
        print(f"Ошибка: папка {DATA_DIR} не найдена.")
        sys.exit(1)

    print(f"Подключение к {DB_PATH}...")
    conn = sqlite3.connect(DB_PATH)

    print("Создание таблиц атрибутов (если нет)...")
    ensure_attribute_tables(conn)

    print("Очистка старых данных...")
    clear_tables(conn)

    print("Импорт каталога из data/products.csv...")
    n_catalog = import_catalog(conn)
    print(f"  Импортировано записей в catalog: {n_catalog}")

    print("Импорт атрибутов из data/*.csv...")
    attr_counts = import_attributes(conn)
    for name, cnt in attr_counts.items():
        print(f"  {name}: {cnt}")

    conn.close()
    print("\nГотово. Данные из CSV загружены в market.db.")


if __name__ == "__main__":
    main()
