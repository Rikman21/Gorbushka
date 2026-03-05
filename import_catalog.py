"""
Импорт каталога товаров из CSV файлов в shop.db.
Обрабатывает разделители: запятая или точка с запятой. Кодировка: UTF-8.
"""

import sqlite3
import os
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).parent / "data"
DB_PATH = Path(__file__).parent / "shop.db"

# Конфигурация CSV файлов: имя файла -> (имя таблицы, схема SQL)
CSV_CONFIG = {
    "apple_catalog_mvp.csv": (
        "apple_catalog_mvp",
        """
        CREATE TABLE apple_catalog_mvp (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT,
            subcategory TEXT,
            product_family TEXT,
            model TEXT,
            generation TEXT,
            size TEXT,
            chipset TEXT,
            launch_year TEXT,
            is_current TEXT,
            notes TEXT
        )
        """,
    ),
    "attribute_definitions.csv": (
        "attribute_definitions",
        """
        CREATE TABLE attribute_definitions (
            attribute_id INTEGER PRIMARY KEY,
            attribute_name TEXT,
            data_type TEXT,
            unit TEXT,
            description TEXT
        )
        """,
    ),
    "attribute_values.csv": (
        "attribute_values",
        """
        CREATE TABLE attribute_values (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            attribute_name TEXT,
            value TEXT,
            label TEXT
        )
        """,
    ),
    "category_attribute_map.csv": (
        "category_attribute_map",
        """
        CREATE TABLE category_attribute_map (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT,
            attribute_name TEXT
        )
        """,
    ),
    "products.csv": (
        "products",
        """
        CREATE TABLE products (
            product_id INTEGER PRIMARY KEY,
            category TEXT,
            family TEXT,
            model_name TEXT,
            generation TEXT,
            form_factor TEXT,
            is_active INTEGER,
            notes TEXT
        )
        """,
    ),
}


def detect_separator(filepath: Path) -> str:
    """Определяет разделитель CSV: запятая или точка с запятой."""
    with open(filepath, "r", encoding="utf-8") as f:
        first_line = f.readline()
    return ";" if first_line.count(";") > first_line.count(",") else ","


def read_csv_safe(filepath: Path) -> pd.DataFrame:
    """Читает CSV с автоопределением разделителя и кодировкой UTF-8."""
    sep = detect_separator(filepath)
    return pd.read_csv(filepath, sep=sep, encoding="utf-8", dtype=str, keep_default_na=False)


def init_db(conn: sqlite3.Connection, config: dict) -> None:
    """Создаёт таблицы, если их нет."""
    cursor = conn.cursor()
    for filename, (table_name, create_sql) in config.items():
        cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
        cursor.execute(create_sql.strip())
    conn.commit()


def insert_dataframe(conn: sqlite3.Connection, df: pd.DataFrame, table_name: str) -> int:
    """Записывает DataFrame в таблицу. Возвращает количество вставленных строк."""
    df.to_sql(table_name, conn, if_exists="append", index=False, method="multi")
    return len(df)


def main() -> None:
    if not DATA_DIR.exists():
        print(f"Ошибка: папка {DATA_DIR} не найдена")
        return

    print("Подключение к shop.db...")
    conn = sqlite3.connect(DB_PATH)

    # Создаём таблицы (DROP IF EXISTS + CREATE)
    print("Создание таблиц...")
    init_db(conn, CSV_CONFIG)

    total_rows = 0
    for filename, (table_name, _) in CSV_CONFIG.items():
        filepath = DATA_DIR / filename
        if not filepath.exists():
            print(f"  Пропуск {filename}: файл не найден")
            continue

        print(f"  Загрузка {filename} -> {table_name}...", end=" ")
        try:
            df = read_csv_safe(filepath)
        except Exception as e:
            print(f"Ошибка чтения: {e}")
            continue

        # Приведение типов для products и attribute_definitions
        if table_name == "products":
            if "product_id" in df.columns:
                df["product_id"] = pd.to_numeric(df["product_id"], errors="coerce").fillna(0).astype(int)
            if "is_active" in df.columns:
                df["is_active"] = pd.to_numeric(df["is_active"], errors="coerce").fillna(0).astype(int)
        elif table_name == "attribute_definitions":
            if "attribute_id" in df.columns:
                df["attribute_id"] = pd.to_numeric(df["attribute_id"], errors="coerce").fillna(0).astype(int)

        n = insert_dataframe(conn, df, table_name)
        total_rows += n
        print(f"{n} строк")

    conn.commit()
    conn.close()
    print(f"\nГотово. Всего импортировано {total_rows} строк.")


if __name__ == "__main__":
    main()
