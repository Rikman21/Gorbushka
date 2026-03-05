"""
Скрипт для добавления тестовых данных в базу
Запустите: python test_data.py
"""

import database

def add_test_data():
    print("🔄 Инициализация базы данных...")
    database.init_db()
    
    print("\n📱 Добавление товаров в каталог...")
    
    # iPhone
    catalog_items = [
        ("iPhone", "Apple", "iPhone 16 Pro Max", "256GB", "Черный титан", "IP16PM256BT"),
        ("iPhone", "Apple", "iPhone 16 Pro Max", "512GB", "Синий титан", "IP16PM512ST"),
        ("iPhone", "Apple", "iPhone 16 Pro", "256GB", "Черный титан", "IP16P256BT"),
        ("iPhone", "Apple", "iPhone 16", "128GB", "Черный", "IP16_128B"),
        ("iPhone", "Apple", "iPhone 15 Pro Max", "256GB", "Натуральный титан", "IP15PM256NT"),
        ("iPhone", "Apple", "iPhone 15", "128GB", "Синий", "IP15_128BL"),
        
        # iPad
        ("iPad", "Apple", "iPad Pro 13", "256GB", "Серый космос", "IPADP13_256SG"),
        ("iPad", "Apple", "iPad Air 11", "128GB", "Синий", "IPADA11_128B"),
        
        # Watch
        ("Watch", "Apple", "Apple Watch Series 10", "46mm", "Черный", "AW10_46B"),
        ("Watch", "Apple", "Apple Watch Ultra 2", "49mm", "Титан", "AWU2_49T"),
        
        # Mac
        ("Mac", "Apple", "MacBook Pro 16", "512GB", "Серый космос", "MBP16_512SG"),
        ("Mac", "Apple", "MacBook Air 15", "256GB", "Полночь", "MBA15_256MN"),
    ]
    
    for item in catalog_items:
        success, msg = database.add_catalog_item(*item)
        print(f"  {msg}: {item[2]} {item[3]} {item[4]}")
    
    print("\n👤 Создание тестовых пользователей...")
    
    # Поставщик 1
    database.create_or_update_user(464896073, "seller1", "Александр")
    database.update_user_supplier_info(464896073, "TechMarket", "Москва", "+79991234567")
    print("  ✅ Поставщик: TechMarket (Москва)")
    
    # Поставщик 2
    database.create_or_update_user(111111111, "seller2", "Магазин Техники")
    database.update_user_supplier_info(111111111, "GadgetStore", "Санкт-Петербург", "+79997654321")
    print("  ✅ Поставщик: GadgetStore (Санкт-Петербург)")
    
    # Покупатель
    database.create_or_update_user(222222222, "buyer1", "Покупатель")
    print("  ✅ Покупатель")
    
    print("\n💼 Добавление предложений...")
    
    offers = [
        # Поставщик 1
        (464896073, 1, 125000, 3, 1, "new", 0, 12, "Оригинал Apple, в наличии"),
        (464896073, 2, 135000, 2, 1, "new", 0, 12, "Официальная гарантия"),
        (464896073, 3, 110000, 5, 1, "new", 0, 12, None),
        (464896073, 7, 95000, 2, 1, "new", 1, 12, "Под заказ 1-2 дня"),
        
        # Поставщик 2
        (111111111, 1, 123000, 10, 2, "new", 0, 12, "Оптом дешевле"),
        (111111111, 4, 85000, 15, 1, "new", 0, 12, "Большой выбор цветов"),
        (111111111, 5, 118000, 5, 1, "ref", 0, 6, "Как новый, гарантия 6 мес"),
        (111111111, 9, 48000, 8, 1, "new", 0, 12, None),
    ]
    
    for offer in offers:
        offer_id = database.create_offer(*offer)
        print(f"  ✅ Предложение #{offer_id} добавлено")
    
    print("\n✅ Тестовые данные добавлены!")
    print("\nТеперь можно:")
    print("1. Запустить бота: python main.py")
    print("2. Открыть /start в Telegram")
    print("3. Просмотреть предложения на бирже")
    
    # Статистика
    catalog = database.get_catalog()
    offers_all = database.get_offers()
    
    print(f"\n📊 Статистика:")
    print(f"  Товаров в каталоге: {len(catalog)}")
    print(f"  Предложений на бирже: {len(offers_all)}")
    print(f"  Поставщиков: 2")

if __name__ == "__main__":
    add_test_data()
