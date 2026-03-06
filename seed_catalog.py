"""
Заполнение каталога market.db из data/products.csv + заданных вариантов памяти/цвета.
Запускать один раз: python seed_catalog.py
Повторный запуск безопасен — дубликаты пропускаются по уникальному SKU.
"""

import sqlite3
import re
from pathlib import Path

DB_PATH = Path(__file__).parent / "market.db"

# ============================================================
# Данные: модель → (варианты памяти, варианты цвета)
# ============================================================

IPHONE_DATA = {
    # --- iPhone 17 ---
    "iPhone 17 Pro":     (["128GB","256GB","512GB","1TB"], ["Black Titanium","White Titanium","Natural Titanium","Desert Titanium"]),
    "iPhone 17 Pro Max": (["256GB","512GB","1TB"],          ["Black Titanium","White Titanium","Natural Titanium","Desert Titanium"]),
    "iPhone Air":        (["128GB","256GB","512GB"],         ["Black","White","Sky Blue","Ultramarine","Pink"]),
    "iPhone 17":         (["128GB","256GB","512GB"],         ["Black","White","Sky Blue","Ultramarine","Pink"]),
    # --- iPhone 16 ---
    "iPhone 16 Pro":     (["128GB","256GB","512GB","1TB"],  ["Black Titanium","White Titanium","Natural Titanium","Desert Titanium"]),
    "iPhone 16 Pro Max": (["256GB","512GB","1TB"],           ["Black Titanium","White Titanium","Natural Titanium","Desert Titanium"]),
    "iPhone 16":         (["128GB","256GB","512GB"],         ["Black","White","Pink","Teal","Ultramarine"]),
    "iPhone 16 Plus":    (["128GB","256GB","512GB"],         ["Black","White","Pink","Teal","Ultramarine"]),
    "iPhone 16e":        (["128GB","256GB","512GB"],         ["Black","White"]),
    # --- iPhone 15 ---
    "iPhone 15 Pro":     (["128GB","256GB","512GB","1TB"],  ["Black Titanium","White Titanium","Blue Titanium","Natural Titanium"]),
    "iPhone 15 Pro Max": (["256GB","512GB","1TB"],           ["Black Titanium","White Titanium","Blue Titanium","Natural Titanium"]),
    "iPhone 15":         (["128GB","256GB","512GB"],         ["Black","Yellow","Pink","Green","Blue"]),
    "iPhone 15 Plus":    (["128GB","256GB","512GB"],         ["Black","Yellow","Pink","Green","Blue"]),
    # --- iPhone 14 ---
    "iPhone 14 Pro":     (["128GB","256GB","512GB","1TB"],  ["Space Black","Silver","Gold","Deep Purple"]),
    "iPhone 14 Pro Max": (["128GB","256GB","512GB","1TB"],  ["Space Black","Silver","Gold","Deep Purple"]),
    "iPhone 14":         (["128GB","256GB","512GB"],         ["Midnight","Starlight","Blue","Purple","Yellow","Product Red"]),
    "iPhone 14 Plus":    (["128GB","256GB","512GB"],         ["Midnight","Starlight","Blue","Purple","Yellow","Product Red"]),
    # --- iPhone 13 ---
    "iPhone 13 Pro":     (["128GB","256GB","512GB","1TB"],  ["Alpine Green","Sierra Blue","Silver","Gold","Graphite"]),
    "iPhone 13 Pro Max": (["128GB","256GB","512GB","1TB"],  ["Alpine Green","Sierra Blue","Silver","Gold","Graphite"]),
    "iPhone 13":         (["128GB","256GB","512GB"],         ["Midnight","Starlight","Blue","Pink","Green","Product Red"]),
    "iPhone 13 mini":    (["128GB","256GB","512GB"],         ["Midnight","Starlight","Blue","Pink","Green","Product Red"]),
    # --- iPhone 12 ---
    "iPhone 12 Pro":     (["128GB","256GB","512GB","1TB"],  ["Pacific Blue","Gold","Silver","Graphite"]),
    "iPhone 12 Pro Max": (["128GB","256GB","512GB","1TB"],  ["Pacific Blue","Gold","Silver","Graphite"]),
    "iPhone 12":         (["64GB","128GB","256GB"],          ["Black","White","Blue","Green","Product Red","Purple"]),
    "iPhone 12 mini":    (["64GB","128GB","256GB"],          ["Black","White","Blue","Green","Product Red","Purple"]),
    # --- iPhone 11 ---
    "iPhone 11 Pro":     (["64GB","256GB","512GB"],          ["Midnight Green","Space Gray","Silver","Gold"]),
    "iPhone 11 Pro Max": (["64GB","256GB","512GB"],          ["Midnight Green","Space Gray","Silver","Gold"]),
    "iPhone 11":         (["64GB","128GB","256GB"],          ["Black","White","Green","Yellow","Purple","Product Red"]),
    # --- SE ---
    "iPhone SE (3rd generation)": (["64GB","128GB","256GB"], ["Midnight","Starlight","Product Red"]),
    "iPhone SE (2nd generation)": (["64GB","128GB","256GB"], ["Black","White","Product Red"]),
}

IPAD_DATA = {
    "iPad Pro 11-inch":          (["256GB","512GB","1TB","2TB"],  ["Space Black","Silver"]),
    "iPad Pro 13-inch":          (["256GB","512GB","1TB","2TB"],  ["Space Black","Silver"]),
    "iPad Air 11-inch":          (["128GB","256GB","512GB","1TB"],["Blue","Starlight","Purple","Sky Blue","Green"]),
    "iPad Air 13-inch":          (["128GB","256GB","512GB","1TB"],["Blue","Starlight","Purple","Sky Blue","Green"]),
    "iPad (A16) 11-inch":        (["128GB","256GB"],               ["Blue","Pink","Yellow","Silver"]),
    "iPad mini 8.3-inch (A17 Pro)":(["128GB","256GB","512GB"],    ["Blue","Starlight","Purple","Pink"]),
}

MAC_DATA = {
    "MacBook Air 13-inch":  (["256GB","512GB","1TB","2TB"], ["Midnight","Starlight","Space Gray","Silver","Sky Blue","Stardust"]),
    "MacBook Air 15-inch":  (["256GB","512GB","1TB","2TB"], ["Midnight","Starlight","Space Gray","Silver","Sky Blue","Stardust"]),
    "MacBook Pro 14-inch":  (["512GB","1TB","2TB","4TB"],   ["Space Black","Silver"]),
    "MacBook Pro 16-inch":  (["512GB","1TB","2TB","4TB"],   ["Space Black","Silver"]),
    "iMac 24-inch":         (["256GB","512GB","1TB","2TB"], ["Silver","Pink","Blue","Green","Yellow","Orange","Purple"]),
    "Mac mini":             (["256GB","512GB","1TB","2TB"], ["Silver"]),
    "Mac Studio":           (["512GB","1TB","2TB","4TB"],   ["Silver"]),
    "Mac Pro":              (["1TB","2TB","4TB","8TB"],      ["Silver"]),
}

WATCH_DATA = {
    "Apple Watch Series 11":          (["GPS","GPS+Cellular"], ["Midnight","Starlight","Silver","Rose Gold","Black","Blue"]),
    "Apple Watch Ultra 3":             (["GPS+Cellular"],       ["Natural Titanium","Black Titanium"]),
    "Apple Watch SE (3rd generation)": (["GPS","GPS+Cellular"], ["Midnight","Starlight","Silver"]),
}

AIRPODS_DATA = {
    "AirPods Pro 3":              ([""],       ["White"]),
    "AirPods Pro 2":              ([""],       ["White"]),
    "AirPods 4":                  ([""],       ["White"]),
    "AirPods 4 (ANC)":            ([""],       ["White"]),
    "AirPods Max":                ([""],       ["Midnight","Starlight","Blue","Purple","Orange"]),
    "AirPods (3rd generation)":   ([""],       ["White"]),
    "AirPods (2nd generation)":   ([""],       ["White"]),
}

OTHER_DATA = {
    "Apple TV 4K":              (["Wi-Fi","Wi-Fi+Ethernet"], ["Black"]),
    "HomePod (2nd generation)": ([""],                       ["Midnight","White"]),
    "HomePod mini":             ([""],                       ["Midnight","White","Yellow","Orange","Blue"]),
    "AirTag":                   (["1 Pack","4 Pack"],        [""]),
    "Apple Vision Pro":         (["256GB","512GB","1TB"],    ["Silver"]),
    "Studio Display":           ([""],                       ["Silver"]),
    "Pro Display XDR":          ([""],                       ["Silver"]),
}

CATEGORY_MAP = {
    **{k: "iPhone" for k in IPHONE_DATA},
    **{k: "iPad" for k in IPAD_DATA},
    **{k: "Mac" for k in MAC_DATA},
    **{k: "Watch" for k in WATCH_DATA},
    **{k: "AirPods" for k in AIRPODS_DATA},
    **{k: "TV & Home" for k in OTHER_DATA},
}

BRAND_MAP = {
    **{k: "Apple" for k in IPHONE_DATA},
    **{k: "Apple" for k in IPAD_DATA},
    **{k: "Apple" for k in MAC_DATA},
    **{k: "Apple" for k in WATCH_DATA},
    **{k: "Apple" for k in AIRPODS_DATA},
    **{k: "Apple" for k in OTHER_DATA},
}

ALL_DATA = {**IPHONE_DATA, **IPAD_DATA, **MAC_DATA, **WATCH_DATA, **AIRPODS_DATA, **OTHER_DATA}


def make_sku(model: str, memory: str, color: str) -> str:
    """Генерирует уникальный SKU из модели, памяти и цвета."""
    parts = [model, memory, color]
    slug = "-".join(p for p in parts if p).upper()
    slug = re.sub(r"[^A-Z0-9]+", "-", slug).strip("-")
    return slug[:80]


def seed(conn: sqlite3.Connection) -> tuple[int, int]:
    """Заполняет таблицу catalog. Возвращает (добавлено, пропущено)."""
    cursor = conn.cursor()
    added = 0
    skipped = 0

    for model, (memories, colors) in ALL_DATA.items():
        category = CATEGORY_MAP.get(model, "Other")
        brand = BRAND_MAP.get(model, "Apple")
        for memory in memories:
            for color in colors:
                sku = make_sku(model, memory, color)
                try:
                    cursor.execute(
                        "INSERT INTO catalog (category, brand, model, memory, color, sku) VALUES (?,?,?,?,?,?)",
                        (category, brand, model, memory, color, sku),
                    )
                    added += 1
                except sqlite3.IntegrityError:
                    skipped += 1  # SKU уже существует

    conn.commit()
    return added, skipped


def main():
    print(f"Подключение к {DB_PATH}...")
    if not DB_PATH.exists():
        print("market.db не найдена — сначала запустите main.py чтобы создать БД")
        return

    conn = sqlite3.connect(DB_PATH)

    # Проверяем текущее состояние
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM catalog")
    before = cursor.fetchone()[0]
    print(f"Товаров в каталоге до импорта: {before}")

    added, skipped = seed(conn)

    cursor.execute("SELECT COUNT(*) FROM catalog")
    after = cursor.fetchone()[0]
    conn.close()

    print(f"Добавлено:  {added}")
    print(f"Пропущено (дубликаты): {skipped}")
    print(f"Итого в каталоге: {after}")
    print("Готово!")


if __name__ == "__main__":
    main()
