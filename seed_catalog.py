"""
Заполнение каталога Apple в PostgreSQL (catalog-service DB).
Запуск внутри контейнера:
  docker cp seed_catalog.py gorbushka-catalog-service-1:/app/
  docker exec gorbushka-catalog-service-1 python seed_catalog.py
Повторный запуск безопасен — ON CONFLICT (sku) DO NOTHING.
"""

import asyncio
import asyncpg
import os
import re

DATABASE_URL = (
    f"postgresql://{os.environ.get('POSTGRES_USER', 'gorbushka')}"
    f":{os.environ.get('POSTGRES_PASSWORD', 'Gorb_2024_Secure!')}"
    f"@{os.environ.get('POSTGRES_HOST', 'postgres')}"
    f":{os.environ.get('POSTGRES_PORT', '5432')}"
    f"/{os.environ.get('POSTGRES_DB', 'gorbushka')}"
)

# ============================================================
# Данные: модель → (варианты памяти/хранилища, варианты цвета)
# Для Mac: чип+RAM включён в название модели, memory = хранилище
# Для Watch: memory = вариант подключения (GPS / GPS+Cellular)
# ============================================================

IPHONE_DATA = {
    # iPhone 17
    "iPhone 17 Pro Max": (["256GB","512GB","1TB"],          ["Black Titanium","White Titanium","Natural Titanium","Desert Titanium"]),
    "iPhone 17 Pro":     (["128GB","256GB","512GB","1TB"],  ["Black Titanium","White Titanium","Natural Titanium","Desert Titanium"]),
    "iPhone Air":        (["128GB","256GB","512GB"],         ["Black","White","Sky Blue","Ultramarine","Pink"]),
    "iPhone 17":         (["128GB","256GB","512GB"],         ["Black","White","Sky Blue","Ultramarine","Pink"]),
    # iPhone 16
    "iPhone 16 Pro Max": (["256GB","512GB","1TB"],           ["Black Titanium","White Titanium","Natural Titanium","Desert Titanium"]),
    "iPhone 16 Pro":     (["128GB","256GB","512GB","1TB"],  ["Black Titanium","White Titanium","Natural Titanium","Desert Titanium"]),
    "iPhone 16 Plus":    (["128GB","256GB","512GB"],         ["Black","White","Pink","Teal","Ultramarine"]),
    "iPhone 16":         (["128GB","256GB","512GB"],         ["Black","White","Pink","Teal","Ultramarine"]),
    "iPhone 16e":        (["128GB","256GB","512GB"],         ["Black","White"]),
    # iPhone 15
    "iPhone 15 Pro Max": (["256GB","512GB","1TB"],           ["Black Titanium","White Titanium","Blue Titanium","Natural Titanium"]),
    "iPhone 15 Pro":     (["128GB","256GB","512GB","1TB"],  ["Black Titanium","White Titanium","Blue Titanium","Natural Titanium"]),
    "iPhone 15 Plus":    (["128GB","256GB","512GB"],         ["Black","Yellow","Pink","Green","Blue"]),
    "iPhone 15":         (["128GB","256GB","512GB"],         ["Black","Yellow","Pink","Green","Blue"]),
    # iPhone 14
    "iPhone 14 Pro Max": (["128GB","256GB","512GB","1TB"],  ["Space Black","Silver","Gold","Deep Purple"]),
    "iPhone 14 Pro":     (["128GB","256GB","512GB","1TB"],  ["Space Black","Silver","Gold","Deep Purple"]),
    "iPhone 14 Plus":    (["128GB","256GB","512GB"],         ["Midnight","Starlight","Blue","Purple","Yellow","Product Red"]),
    "iPhone 14":         (["128GB","256GB","512GB"],         ["Midnight","Starlight","Blue","Purple","Yellow","Product Red"]),
    # iPhone 13
    "iPhone 13 Pro Max": (["128GB","256GB","512GB","1TB"],  ["Alpine Green","Sierra Blue","Silver","Gold","Graphite"]),
    "iPhone 13 Pro":     (["128GB","256GB","512GB","1TB"],  ["Alpine Green","Sierra Blue","Silver","Gold","Graphite"]),
    "iPhone 13 mini":    (["128GB","256GB","512GB"],         ["Midnight","Starlight","Blue","Pink","Green","Product Red"]),
    "iPhone 13":         (["128GB","256GB","512GB"],         ["Midnight","Starlight","Blue","Pink","Green","Product Red"]),
    # iPhone 12
    "iPhone 12 Pro Max": (["128GB","256GB","512GB","1TB"],  ["Pacific Blue","Gold","Silver","Graphite"]),
    "iPhone 12 Pro":     (["128GB","256GB","512GB","1TB"],  ["Pacific Blue","Gold","Silver","Graphite"]),
    "iPhone 12":         (["64GB","128GB","256GB"],          ["Black","White","Blue","Green","Product Red","Purple"]),
    "iPhone 12 mini":    (["64GB","128GB","256GB"],          ["Black","White","Blue","Green","Product Red","Purple"]),
    # iPhone 11
    "iPhone 11 Pro Max": (["64GB","256GB","512GB"],          ["Midnight Green","Space Gray","Silver","Gold"]),
    "iPhone 11 Pro":     (["64GB","256GB","512GB"],          ["Midnight Green","Space Gray","Silver","Gold"]),
    "iPhone 11":         (["64GB","128GB","256GB"],          ["Black","White","Green","Yellow","Purple","Product Red"]),
    # iPhone SE
    "iPhone SE (3rd generation)": (["64GB","128GB","256GB"], ["Midnight","Starlight","Product Red"]),
    "iPhone SE (2nd generation)": (["64GB","128GB","256GB"], ["Black","White","Product Red"]),
}

IPAD_DATA = {
    # iPad Pro M4 — Wi-Fi и Wi-Fi+Cellular отдельно (разная цена)
    "iPad Pro 11-inch M4 Wi-Fi":          (["256GB","512GB","1TB","2TB"],   ["Space Black","Silver"]),
    "iPad Pro 11-inch M4 Wi-Fi+Cellular": (["256GB","512GB","1TB","2TB"],   ["Space Black","Silver"]),
    "iPad Pro 13-inch M4 Wi-Fi":          (["256GB","512GB","1TB","2TB"],   ["Space Black","Silver"]),
    "iPad Pro 13-inch M4 Wi-Fi+Cellular": (["256GB","512GB","1TB","2TB"],   ["Space Black","Silver"]),
    # iPad Air M3
    "iPad Air 11-inch M3":                (["128GB","256GB","512GB","1TB"], ["Blue","Starlight","Purple","Sky Blue","Green"]),
    "iPad Air 13-inch M3":                (["128GB","256GB","512GB","1TB"], ["Blue","Starlight","Purple","Sky Blue","Green"]),
    # iPad и iPad mini
    "iPad (A16) 11-inch":                 (["128GB","256GB","512GB"],       ["Blue","Pink","Yellow","Silver"]),
    "iPad mini (A17 Pro) 8.3-inch":       (["128GB","256GB","512GB"],       ["Blue","Starlight","Purple","Pink"]),
}

MAC_DATA = {
    # MacBook Neo — новинка 2026, чип A18 Pro
    "MacBook Neo 13-inch A18 Pro":        (["256GB","512GB"],              ["Silver","Blush","Citrus","Indigo"]),
    # MacBook Air M4
    "MacBook Air 13-inch M4":             (["256GB","512GB","1TB","2TB"],  ["Midnight","Starlight","Sky Blue","Rose Gold"]),
    "MacBook Air 15-inch M4":             (["256GB","512GB","1TB","2TB"],  ["Midnight","Starlight","Sky Blue","Rose Gold"]),
    # MacBook Pro 14-inch — 5 вариантов чипа
    "MacBook Pro 14-inch M4":             (["512GB","1TB","2TB"],          ["Space Black","Silver"]),
    "MacBook Pro 14-inch M4 Pro 24GB":    (["512GB","1TB","2TB"],          ["Space Black","Silver"]),
    "MacBook Pro 14-inch M4 Pro 48GB":    (["512GB","1TB","2TB"],          ["Space Black","Silver"]),
    "MacBook Pro 14-inch M4 Max 48GB":    (["512GB","1TB","2TB"],          ["Space Black","Silver"]),
    "MacBook Pro 14-inch M4 Max 128GB":   (["1TB","2TB"],                  ["Space Black","Silver"]),
    # MacBook Pro 16-inch — 4 варианта чипа
    "MacBook Pro 16-inch M4 Pro 24GB":    (["512GB","1TB","2TB"],          ["Space Black","Silver"]),
    "MacBook Pro 16-inch M4 Pro 48GB":    (["512GB","1TB","2TB"],          ["Space Black","Silver"]),
    "MacBook Pro 16-inch M4 Max 48GB":    (["512GB","1TB","2TB","4TB"],    ["Space Black","Silver"]),
    "MacBook Pro 16-inch M4 Max 128GB":   (["1TB","2TB","4TB"],            ["Space Black","Silver"]),
    # iMac M4
    "iMac 24-inch M4":                    (["256GB","512GB","1TB","2TB"],  ["Blue","Green","Pink","Silver","Orange","Purple","Yellow"]),
    # Mac mini — 3 варианта чипа
    "Mac mini M4":                        (["256GB","512GB","1TB","2TB"],  ["Silver"]),
    "Mac mini M4 Pro 24GB":               (["512GB","1TB","2TB"],          ["Silver"]),
    "Mac mini M4 Pro 48GB":               (["512GB","1TB","2TB"],          ["Silver"]),
    # Mac Studio — 4 варианта чипа
    "Mac Studio M4 Max 36GB":             (["512GB","1TB","2TB"],          ["Silver"]),
    "Mac Studio M4 Max 128GB":            (["1TB","2TB"],                  ["Silver"]),
    "Mac Studio M4 Ultra 80GB":           (["1TB","2TB","4TB"],            ["Silver"]),
    "Mac Studio M4 Ultra 192GB":          (["2TB","4TB"],                  ["Silver"]),
    # Mac Pro
    "Mac Pro M4 Ultra 192GB":             (["1TB","2TB","4TB","8TB"],      ["Silver"]),
}

WATCH_DATA = {
    "Apple Watch Series 11 41mm":          (["GPS","GPS+Cellular"], ["Midnight","Starlight","Silver","Rose Gold","Black","Blue"]),
    "Apple Watch Series 11 45mm":          (["GPS","GPS+Cellular"], ["Midnight","Starlight","Silver","Rose Gold","Black","Blue"]),
    "Apple Watch Ultra 3 49mm":            (["GPS+Cellular"],       ["Natural Titanium","Black Titanium"]),
    "Apple Watch SE (3rd generation) 40mm":(["GPS","GPS+Cellular"], ["Midnight","Starlight","Silver"]),
    "Apple Watch SE (3rd generation) 44mm":(["GPS","GPS+Cellular"], ["Midnight","Starlight","Silver"]),
}

AIRPODS_DATA = {
    "AirPods 4":                 ([""], ["White"]),
    "AirPods 4 (ANC)":           ([""], ["White"]),
    "AirPods Pro 3":             ([""], ["White"]),
    "AirPods Pro 2":             ([""], ["White"]),
    "AirPods Max":               ([""], ["Midnight","Starlight","Blue","Purple","Orange"]),
    "AirPods (3rd generation)":  ([""], ["White"]),
    "AirPods (2nd generation)":  ([""], ["White"]),
}

TV_HOME_DATA = {
    "Apple TV 4K (Wi-Fi)":          ([""], ["Black"]),
    "Apple TV 4K (Wi-Fi+Ethernet)": ([""], ["Black"]),
    "HomePod":                       ([""], ["Midnight","White"]),
    "HomePod mini":                  ([""], ["Midnight","White","Yellow","Orange","Blue"]),
}

VISION_DATA = {
    "Apple Vision Pro": (["256GB","512GB","1TB"], ["Silver"]),
}

ACCESSORIES_DATA = {
    "AirTag":      (["1 Pack","4 Pack"], [""]),
}

CATEGORY_MAP = {
    **{k: "iPhone"      for k in IPHONE_DATA},
    **{k: "iPad"        for k in IPAD_DATA},
    **{k: "Mac"         for k in MAC_DATA},
    **{k: "Watch"       for k in WATCH_DATA},
    **{k: "AirPods"     for k in AIRPODS_DATA},
    **{k: "TV & Home"   for k in TV_HOME_DATA},
    **{k: "Vision"      for k in VISION_DATA},
    **{k: "Accessories" for k in ACCESSORIES_DATA},
}

ALL_DATA = {
    **IPHONE_DATA,
    **IPAD_DATA,
    **MAC_DATA,
    **WATCH_DATA,
    **AIRPODS_DATA,
    **TV_HOME_DATA,
    **VISION_DATA,
    **ACCESSORIES_DATA,
}


def make_sku(brand: str, model: str, memory: str, color: str) -> str:
    parts = [brand, model, memory, color]
    raw = "_".join(p for p in parts if p).lower().replace(" ", "_")
    raw = re.sub(r"[^a-z0-9_]+", "_", raw).strip("_")
    return raw[:80]


async def seed():
    print(f"Подключение к PostgreSQL...")
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        before = await conn.fetchval("SELECT COUNT(*) FROM catalog")
        print(f"Товаров до импорта: {before}")

        added = 0
        skipped = 0

        for model, (memories, colors) in ALL_DATA.items():
            category = CATEGORY_MAP[model]
            brand = "Apple"
            for memory in memories:
                for color in colors:
                    sku = make_sku(brand, model, memory, color)
                    result = await conn.execute(
                        """
                        INSERT INTO catalog (category, brand, model, memory, color, sku)
                        VALUES ($1, $2, $3, $4, $5, $6)
                        ON CONFLICT (sku) DO NOTHING
                        """,
                        category, brand, model,
                        memory if memory else None,
                        color if color else None,
                        sku
                    )
                    if result == "INSERT 0 1":
                        added += 1
                    else:
                        skipped += 1

        after = await conn.fetchval("SELECT COUNT(*) FROM catalog")
        print(f"Добавлено:  {added}")
        print(f"Пропущено (дубликаты): {skipped}")
        print(f"Итого в каталоге: {after}")
        print("Готово!")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(seed())
