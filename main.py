import asyncio
import logging
import json
import os
import sqlite3
from aiohttp import web
from io import BytesIO

import pandas as pd

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import WebAppInfo, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

import database

# Корень проекта (рядом с main.py и index.html)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

TOKEN = "8451254918:AAHDJ8yIwQ44Stn7vT_s1mmxLDVYwfXUuJU"
WEB_APP_URL = "https://rikman21.github.io/Gorbushka/"
ADMIN_IDS = [210419, 464896073]

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher()

# ==================== API СЕРВЕР ====================

async def index_page(request):
    """Главная страница — отдаём index.html"""
    return web.FileResponse(os.path.join(BASE_DIR, "index.html"))

async def health_check(request):
    """Проверка API (например для /health)"""
    return web.Response(text="Gorbushka API v2.0")

async def get_offers_api(request):
    """API: Получить предложения с фильтрами для биржи"""
    filters = {}
    if request.query.get('model'):
        filters['model'] = request.query.get('model')
    if request.query.get('memory'):
        filters['memory'] = request.query.get('memory')
    if request.query.get('condition'):
        filters['condition'] = request.query.get('condition')
    try:
        if request.query.get('min_price'):
            filters['min_price'] = int(request.query.get('min_price'))
        if request.query.get('max_price'):
            filters['max_price'] = int(request.query.get('max_price'))
    except ValueError:
        pass
    if request.query.get('in_stock'):
        filters['in_stock'] = True
    if request.query.get('verified'):
        filters['verified'] = True
    
    offers = database.get_offers(filters)
    return web.json_response(offers, headers={
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type"
    })


async def get_offer_by_id_api(request):
    """API: Одно предложение по ID GET /api/offers/{id}."""
    offer_id = request.match_info.get("id")
    if not offer_id:
        return web.json_response({"error": "id required"}, status=400, headers=CORS_HEADERS)
    try:
        offer_id = int(offer_id)
    except ValueError:
        return web.json_response({"error": "Invalid id"}, status=400, headers=CORS_HEADERS)
    offer = database.get_offer_by_id(offer_id)
    if not offer:
        return web.json_response({"error": "Offer not found"}, status=404, headers=CORS_HEADERS)
    return web.json_response(offer, headers=CORS_HEADERS)

async def get_catalog_api(request):
    """API: Каталог. По умолчанию — только товары с предложениями (min_price, max_price, offers_count).
    ?all=1 — полный каталог: все поля (id, category, brand, model, memory, color, sku, ...) для каскадного выбора."""
    filters = {}
    if request.query.get('category'):
        filters['category'] = request.query.get('category')
    if request.query.get('model'):
        filters['model'] = request.query.get('model')
    if request.query.get('memory'):
        filters['memory'] = request.query.get('memory')
    if request.query.get('all') == '1':
        catalog = database.get_catalog(filters)
        # для полного каталога без агрегации
        for item in catalog:
            item.setdefault('min_price', None)
            item.setdefault('max_price', None)
            item.setdefault('offers_count', 0)
    else:
        catalog = database.get_catalog_with_offers(filters)
    return web.json_response(catalog, headers={
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type"
    })


async def get_catalog_offers_api(request):
    """API: Предложения по товару GET /api/catalog/{id}/offers."""
    catalog_id = request.match_info.get("id")
    if not catalog_id:
        return web.json_response({"error": "id required"}, status=400, headers=CORS_HEADERS)
    try:
        catalog_id = int(catalog_id)
    except ValueError:
        return web.json_response({"error": "Invalid id"}, status=400, headers=CORS_HEADERS)
    offers = database.get_catalog_offers(catalog_id)
    return web.json_response(offers, headers=CORS_HEADERS)

async def get_user_api(request):
    """API: Получить данные пользователя"""
    telegram_id = request.query.get('telegram_id')
    if not telegram_id:
        return web.json_response({'error': 'telegram_id required'}, status=400)
    
    user = database.get_user(int(telegram_id))
    return web.json_response(user or {}, headers={
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type"
    })

async def get_deals_api(request):
    """API: Получить сделки пользователя"""
    telegram_id = request.query.get('telegram_id')
    status_filter = request.query.get('status')
    
    if not telegram_id:
        return web.json_response({'error': 'telegram_id required'}, status=400)
    
    deals = database.get_user_deals(int(telegram_id), status_filter)
    return web.json_response(deals, headers={
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type"
    })

async def get_deal_api(request):
    """API: Получить сделку по ID"""
    deal_id = request.query.get('deal_id')
    if not deal_id:
        return web.json_response({'error': 'deal_id required'}, status=400)
    
    deal = database.get_deal(int(deal_id))
    if not deal:
        return web.json_response({'error': 'Deal not found'}, status=404)
    
    # Добавляем сообщения
    messages = database.get_deal_messages(int(deal_id))
    deal['messages'] = messages
    
    return web.json_response(deal, headers={
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type"
    })

async def get_supplier_profile_api(request):
    """API: Получить профиль поставщика"""
    supplier_id = request.query.get('supplier_id')
    if not supplier_id:
        return web.json_response({'error': 'supplier_id required'}, status=400)
    
    user = database.get_user(int(supplier_id))
    if not user:
        return web.json_response({'error': 'Supplier not found'}, status=404)
    
    # Добавляем предложения и отзывы
    offers = database.get_supplier_offers(int(supplier_id))
    reviews = database.get_supplier_reviews(int(supplier_id))
    
    user['offers'] = offers
    user['reviews'] = reviews
    
    return web.json_response(user, headers={
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type"
    })

async def get_supplier_offers_api(request):
    """API: Список предложений поставщика (GET ?telegram_id=)."""
    telegram_id = request.query.get("telegram_id")
    if not telegram_id:
        return web.json_response({"error": "telegram_id required"}, status=400, headers=CORS_HEADERS)
    try:
        offers = database.get_supplier_offers(int(telegram_id))
    except ValueError:
        return web.json_response({"error": "Invalid telegram_id"}, status=400, headers=CORS_HEADERS)
    return web.json_response(offers, headers=CORS_HEADERS)

async def post_supplier_offers_api(request):
    """API: Добавить предложение.
    Принимает JSON: telegram_id, price, quantity
    и либо product_id (catalog_id), либо model+memory+color для поиска в каталоге."""
    if request.method == "OPTIONS":
        return web.Response(headers=CORS_HEADERS)
    try:
        data = await request.json()
    except Exception as e:
        print("[post_supplier_offers] Invalid JSON:", str(e))
        return web.json_response({"ok": False, "error": "Invalid JSON: " + str(e)}, status=400, headers=CORS_HEADERS)
    telegram_id = data.get("telegram_id")
    product_id = data.get("product_id")
    price = data.get("price")
    quantity = data.get("quantity")
    if telegram_id is None or price is None:
        return web.json_response(
            {"ok": False, "error": "Required: telegram_id, price"},
            status=400,
            headers=CORS_HEADERS,
        )
    try:
        telegram_id = int(telegram_id)
        price = int(price)
        quantity = int(quantity) if quantity is not None else 0
    except (TypeError, ValueError) as e:
        print("[post_supplier_offers] Bad types:", str(e))
        return web.json_response(
            {"ok": False, "error": "telegram_id, price must be numbers"},
            status=400,
            headers=CORS_HEADERS,
        )
    # Определяем catalog_id: по product_id или по model/memory/color
    if product_id is not None:
        try:
            catalog_id = int(product_id)
        except (TypeError, ValueError):
            return web.json_response({"ok": False, "error": "product_id must be a number"}, status=400, headers=CORS_HEADERS)
    else:
        model = (data.get("model") or "").strip()
        memory = (data.get("memory") or "").strip()
        color = (data.get("color") or "").strip()
        if not model:
            return web.json_response({"ok": False, "error": "Required: product_id or model"}, status=400, headers=CORS_HEADERS)
        catalog_id = database.find_catalog_by_brand_model_memory_color("Apple", model, memory, color)
        if not catalog_id:
            # Попробуем добавить товар в каталог автоматически
            ok, msg = database.add_catalog_item("iPhone" if "iPhone" in model else "Apple", "Apple", model, memory, color,
                                                 f"{model}-{memory}-{color}".upper().replace(" ", "-")[:80])
            if ok:
                catalog_id = database.find_catalog_by_brand_model_memory_color("Apple", model, memory, color)
        if not catalog_id:
            return web.json_response({"ok": False, "error": f"Товар '{model}' не найден в каталоге"}, status=404, headers=CORS_HEADERS)
    if price < 0:
        return web.json_response({"ok": False, "error": "price must be >= 0"}, status=400, headers=CORS_HEADERS)
    if quantity < 0:
        quantity = 0
    comment = (data.get("comment") or "").strip() or None
    condition = data.get("condition") or "new"
    try:
        offer_id = database.create_offer(
            supplier_id=telegram_id,
            catalog_id=catalog_id,
            price=price,
            quantity=quantity,
            moq=1,
            condition=condition,
            delivery_days=0,
            warranty_months=12,
            comment=comment,
        )
    except sqlite3.IntegrityError as e:
        print("[post_supplier_offers] DB IntegrityError:", str(e))
        logging.exception("post_supplier_offers")
        return web.json_response(
            {"ok": False, "error": "Ошибка БД (возможно, товар не найден в каталоге или дубликат): " + str(e)},
            status=400,
            headers=CORS_HEADERS,
        )
    except Exception as e:
        print("[post_supplier_offers] DB error:", str(e))
        logging.exception("post_supplier_offers")
        return web.json_response(
            {"ok": False, "error": "Ошибка сохранения: " + str(e)},
            status=500,
            headers=CORS_HEADERS,
        )
    return web.json_response({"ok": True, "id": offer_id}, headers=CORS_HEADERS)

async def delete_supplier_offer_api(request):
    """API: Удалить предложение (DELETE /api/supplier/offers/{id}?telegram_id=)."""
    offer_id = request.match_info.get("id")
    telegram_id = request.query.get("telegram_id")
    if not offer_id or not telegram_id:
        return web.json_response({"error": "id and telegram_id required"}, status=400, headers=CORS_HEADERS)
    try:
        offer_id = int(offer_id)
        telegram_id = int(telegram_id)
    except ValueError:
        return web.json_response({"error": "id and telegram_id must be numbers"}, status=400, headers=CORS_HEADERS)
    if not database.delete_offer(offer_id, telegram_id):
        return web.json_response({"error": "Offer not found or access denied"}, status=404, headers=CORS_HEADERS)
    return web.json_response({"ok": True}, headers=CORS_HEADERS)


async def get_supplier_template_api(request):
    """API: Скачать прайс-лист — все товары каталога (Brand, Model, Memory, Color, Price, Quantity). Price и Quantity пустые/0."""
    rows = database.get_catalog_all_for_template()
    # Явно создаём DataFrame с колонками Brand, Model, Memory, Color, Price, Quantity
    data = []
    for r in rows:
        data.append({
            "Brand": (r.get("brand") or "").strip(),
            "Model": (r.get("model") or "").strip(),
            "Memory": (r.get("memory") or "").strip(),
            "Color": (r.get("color") or "").strip(),
            "Price": 0,
            "Quantity": 0,
        })
    df = pd.DataFrame(data, columns=["Brand", "Model", "Memory", "Color", "Price", "Quantity"])
    buf = BytesIO()
    df.to_excel(buf, index=False, engine="openpyxl")
    buf.seek(0)
    return web.Response(
        body=buf.read(),
        headers={
            "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "Content-Disposition": 'attachment; filename="template.xlsx"',
        },
    )


async def post_supplier_import_api(request):
    """API: Массовый импорт из Excel (multipart: telegram_id, file). Поиск по brand, model, memory, color."""
    if request.method == "OPTIONS":
        return web.Response(headers=CORS_HEADERS)
    try:
        reader = await request.multipart()
        telegram_id = None
        file_data = None
        async for part in reader:
            if part.name == "telegram_id":
                telegram_id = (await part.read()).decode().strip()
            elif part.name == "file" and part.filename:
                file_data = await part.read()
        if not telegram_id or not file_data:
            return web.json_response(
                {"success": False, "error": "Required: telegram_id and file"},
                status=400,
                headers=CORS_HEADERS,
            )
        telegram_id = int(telegram_id)
    except (ValueError, Exception) as e:
        print("[supplier_import] Parse multipart error:", str(e))
        logging.exception("supplier_import")
        return web.json_response(
            {"success": False, "error": str(e)},
            status=400,
            headers=CORS_HEADERS,
        )

    success = 0
    errors = 0
    try:
        df = pd.read_excel(BytesIO(file_data), engine="openpyxl")
    except Exception as e:
        print("[supplier_import] Excel read error:", str(e))
        logging.exception("supplier_import")
        return web.json_response(
            {"success": False, "error": "Файл не читается: " + str(e)},
            status=400,
            headers=CORS_HEADERS,
        )

    try:
        # Имена колонок — приводим к нижнему регистру для проверки
        raw_columns = list(df.columns)
        cols_lower = {str(c).strip().lower(): c for c in raw_columns}
        brand_col = cols_lower.get("brand")
        model_col = cols_lower.get("model")
        memory_col = cols_lower.get("memory")
        color_col = cols_lower.get("color")
        price_col = cols_lower.get("price")
        quantity_col = cols_lower.get("quantity")

        if not all([brand_col is not None, model_col is not None, memory_col is not None, color_col is not None, price_col is not None]):
            return web.json_response(
                {"success": False, "error": "В файле должны быть колонки: Brand, Model, Memory, Color, Price (Quantity — по желанию)"},
                status=400,
                headers=CORS_HEADERS,
            )

        rows_to_import = []
        for _, row in df.iterrows():
            try:
                brand = pd.Series(row).get(brand_col)
                model = pd.Series(row).get(model_col)
                memory = pd.Series(row).get(memory_col)
                color = pd.Series(row).get(color_col)
                price_val = pd.Series(row).get(price_col)
                qty_val = pd.Series(row).get(quantity_col) if quantity_col is not None else 0
            except Exception as e:
                print("[supplier_import] Row read error:", str(e))
                errors += 1
                continue
            if pd.isna(brand) and pd.isna(model) and pd.isna(memory) and pd.isna(color):
                continue
            model = "" if pd.isna(model) else str(model).strip()
            memory = "" if pd.isna(memory) else str(memory).strip()
            color = "" if pd.isna(color) else str(color).strip()
            try:
                price = int(float(price_val)) if not pd.isna(price_val) else 0
            except (TypeError, ValueError):
                errors += 1
                continue
            try:
                quantity = int(float(qty_val)) if not pd.isna(qty_val) else 0
            except (TypeError, ValueError):
                quantity = 0
            rows_to_import.append({"model": model, "memory": memory, "color": color, "price": price, "quantity": quantity})

        success, batch_errors = database.import_offers_batch(telegram_id, rows_to_import)
        errors += batch_errors
    except Exception as e:
        print("[supplier_import] Process rows error:", str(e))
        logging.exception("supplier_import")
        return web.json_response(
            {"success": False, "error": str(e)},
            status=500,
            headers=CORS_HEADERS,
        )

    msg = f"Импортировано: {success}, ошибок: {errors}"
    return web.json_response(
        {"success": True, "success_count": success, "errors": errors, "message": msg},
        headers=CORS_HEADERS,
    )


CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
}

async def post_user_role_api(request):
    """API: Установить роль пользователя (POST JSON: telegram_id, role)."""
    if request.method == "OPTIONS":
        return web.Response(headers=CORS_HEADERS)
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON"}, status=400, headers=CORS_HEADERS)
    telegram_id = data.get("telegram_id")
    role = data.get("role")
    if not telegram_id or role not in ("buyer", "supplier"):
        return web.json_response({"error": "Required: telegram_id, role (buyer|supplier)"}, status=400, headers=CORS_HEADERS)
    try:
        telegram_id = int(telegram_id)
    except (TypeError, ValueError):
        return web.json_response({"error": "Invalid telegram_id"}, status=400, headers=CORS_HEADERS)
    # Не-админы могут выбрать роль только один раз
    if telegram_id not in ADMIN_IDS:
        user = database.get_user(telegram_id)
        if user and user.get("role_selected"):
            return web.json_response({"error": "Роль уже выбрана. Для изменения обратитесь к администратору."}, status=403, headers=CORS_HEADERS)
    database.set_user_role(telegram_id, role)
    return web.json_response({"ok": True}, headers=CORS_HEADERS)


async def get_admin_users_api(request):
    """API: Все пользователи (только для админа, GET ?admin_id=)."""
    admin_id = request.query.get("admin_id")
    try:
        if not admin_id or int(admin_id) not in ADMIN_IDS:
            return web.json_response({"error": "Нет прав"}, status=403, headers=CORS_HEADERS)
    except ValueError:
        return web.json_response({"error": "Нет прав"}, status=403, headers=CORS_HEADERS)
    users = database.get_all_users()
    return web.json_response(users, headers=CORS_HEADERS)


async def post_admin_user_role_api(request):
    """API: Изменить роль пользователя (только для админа, POST JSON: admin_id, telegram_id, role)."""
    if request.method == "OPTIONS":
        return web.Response(headers=CORS_HEADERS)
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON"}, status=400, headers=CORS_HEADERS)
    try:
        admin_id = int(data.get("admin_id", 0))
    except (TypeError, ValueError):
        admin_id = 0
    if admin_id not in ADMIN_IDS:
        return web.json_response({"error": "Нет прав"}, status=403, headers=CORS_HEADERS)
    telegram_id = data.get("telegram_id")
    role = data.get("role")
    if not telegram_id or role not in ("buyer", "supplier"):
        return web.json_response({"error": "Required: telegram_id, role"}, status=400, headers=CORS_HEADERS)
    database.set_user_role(int(telegram_id), role)
    return web.json_response({"ok": True}, headers=CORS_HEADERS)


async def delete_admin_user_api(request):
    """API: Удалить пользователя с платформы (только для админа, DELETE /api/admin/user/{id}?admin_id=)."""
    user_id = request.match_info.get("id")
    admin_id = request.query.get("admin_id")
    try:
        if not admin_id or int(admin_id) not in ADMIN_IDS:
            return web.json_response({"error": "Нет прав"}, status=403, headers=CORS_HEADERS)
        if not user_id:
            return web.json_response({"error": "id required"}, status=400, headers=CORS_HEADERS)
        database.delete_user(int(user_id))
    except ValueError:
        return web.json_response({"error": "Нет прав"}, status=403, headers=CORS_HEADERS)
    return web.json_response({"ok": True}, headers=CORS_HEADERS)


async def post_create_deal_api(request):
    """API: Создать сделку (POST JSON: buyer_id, offer_id, quantity)."""
    if request.method == "OPTIONS":
        return web.Response(headers=CORS_HEADERS)
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON"}, status=400, headers=CORS_HEADERS)
    buyer_id = data.get("buyer_id")
    offer_id = data.get("offer_id")
    quantity = data.get("quantity", 1)
    if not buyer_id or not offer_id:
        return web.json_response({"error": "Required: buyer_id, offer_id"}, status=400, headers=CORS_HEADERS)
    try:
        buyer_id = int(buyer_id)
        offer_id = int(offer_id)
        quantity = int(quantity)
    except (TypeError, ValueError):
        return web.json_response({"error": "Invalid types"}, status=400, headers=CORS_HEADERS)
    offer = database.get_offer_by_id(offer_id)
    if not offer:
        return web.json_response({"error": "Offer not found"}, status=404, headers=CORS_HEADERS)
    supplier_id = offer['supplier_id']
    price = offer['price']
    deal_id = database.create_deal(buyer_id, supplier_id, offer_id, quantity, price)
    buyer_user = database.get_user(buyer_id)
    buyer_name = (buyer_user and (buyer_user.get('username') or buyer_user.get('full_name'))) or 'Покупатель'
    try:
        await bot.send_message(
            supplier_id,
            f"🔔 Новая сделка #{deal_id}\n\n"
            f"📦 {offer.get('model','')} {offer.get('memory','')} {offer.get('color','')}\n"
            f"💰 {price:,} ₽ × {quantity} шт\n"
            f"👤 Покупатель: {buyer_name}\n\n"
            f"Откройте биржу для подтверждения"
        )
    except Exception as e:
        logging.warning("Не удалось уведомить поставщика о сделке: %s", e)
    return web.json_response({"ok": True, "deal_id": deal_id}, headers=CORS_HEADERS)


async def post_price_request_api(request):
    """API: Запросить цену (POST JSON: offer_id, buyer_id, quantity)."""
    if request.method == "OPTIONS":
        return web.Response(headers=CORS_HEADERS)
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON"}, status=400, headers=CORS_HEADERS)
    offer_id = data.get("offer_id")
    buyer_id = data.get("buyer_id")
    quantity = data.get("quantity", 1)
    if not offer_id or not buyer_id:
        return web.json_response({"error": "Required: offer_id, buyer_id"}, status=400, headers=CORS_HEADERS)
    try:
        offer_id = int(offer_id)
        buyer_id = int(buyer_id)
        quantity = int(quantity)
    except (TypeError, ValueError):
        return web.json_response({"error": "Invalid types"}, status=400, headers=CORS_HEADERS)
    offer = database.get_offer_by_id(offer_id)
    if not offer:
        return web.json_response({"error": "Offer not found"}, status=404, headers=CORS_HEADERS)
    supplier_id = offer['supplier_id']
    request_id = database.create_price_request(offer_id, buyer_id, supplier_id, quantity)
    # Уведомляем поставщика
    buyer_user = database.get_user(buyer_id)
    buyer_name = (buyer_user and (buyer_user.get('company_name') or buyer_user.get('full_name'))) or 'Покупатель'
    try:
        await bot.send_message(
            supplier_id,
            f"💬 Запрос цены #{request_id}\n\n"
            f"📦 {offer.get('model','')} {offer.get('memory','')} {offer.get('color','')}\n"
            f"🔢 Количество: {quantity} шт\n"
            f"👤 Покупатель: {buyer_name}\n\n"
            f"⏰ У вас 10 минут чтобы ответить в приложении"
        )
    except Exception as e:
        logging.warning("Не удалось уведомить поставщика: %s", e)
    # Запускаем таймер 10 минут
    asyncio.create_task(price_request_timer(request_id, supplier_id, buyer_id))
    return web.json_response({"ok": True, "id": request_id}, headers=CORS_HEADERS)


async def price_request_timer(request_id, supplier_id, buyer_id):
    """Таймер 10 минут для запроса цены."""
    await asyncio.sleep(600)
    req = database.get_price_request(request_id)
    if req and req['status'] == 'pending':
        database.expire_price_request(request_id)
        try:
            await bot.send_message(buyer_id, "⏰ Поставщик не ответил на запрос цены за 10 минут. Попробуйте другого поставщика.")
        except Exception:
            pass
        try:
            await bot.send_message(supplier_id, "⚠️ Запрос цены истёк — покупатель не дождался ответа.")
        except Exception:
            pass


async def get_price_requests_api(request):
    """API: Входящие запросы цены для поставщика (GET ?supplier_id=)."""
    supplier_id = request.query.get("supplier_id")
    if not supplier_id:
        return web.json_response({"error": "supplier_id required"}, status=400, headers=CORS_HEADERS)
    try:
        requests_list = database.get_pending_price_requests(int(supplier_id))
    except ValueError:
        return web.json_response({"error": "Invalid supplier_id"}, status=400, headers=CORS_HEADERS)
    return web.json_response(requests_list, headers=CORS_HEADERS)


async def get_buyer_price_requests_api(request):
    """API: Запросы цены покупателя (GET ?buyer_id=)."""
    buyer_id = request.query.get("buyer_id")
    if not buyer_id:
        return web.json_response({"error": "buyer_id required"}, status=400, headers=CORS_HEADERS)
    try:
        requests_list = database.get_buyer_price_requests(int(buyer_id))
    except ValueError:
        return web.json_response({"error": "Invalid buyer_id"}, status=400, headers=CORS_HEADERS)
    return web.json_response(requests_list, headers=CORS_HEADERS)


async def post_respond_price_request_api(request):
    """API: Ответить на запрос цены (POST JSON: request_id, price, supplier_id)."""
    if request.method == "OPTIONS":
        return web.Response(headers=CORS_HEADERS)
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON"}, status=400, headers=CORS_HEADERS)
    request_id = data.get("request_id")
    price = data.get("price")
    supplier_id = data.get("supplier_id")
    if not request_id or not price or not supplier_id:
        return web.json_response({"error": "Required: request_id, price, supplier_id"}, status=400, headers=CORS_HEADERS)
    try:
        request_id = int(request_id)
        price = int(price)
        supplier_id = int(supplier_id)
    except (TypeError, ValueError):
        return web.json_response({"error": "Invalid types"}, status=400, headers=CORS_HEADERS)
    req = database.get_price_request(request_id)
    if not req:
        return web.json_response({"error": "Request not found"}, status=404, headers=CORS_HEADERS)
    if req['supplier_id'] != supplier_id:
        return web.json_response({"error": "Нет прав"}, status=403, headers=CORS_HEADERS)
    if req['status'] != 'pending':
        return web.json_response({"error": "Запрос уже обработан"}, status=400, headers=CORS_HEADERS)
    database.respond_price_request(request_id, price)
    # Уведомляем покупателя
    supplier_user = database.get_user(supplier_id)
    supplier_name = (supplier_user and (supplier_user.get('company_name') or supplier_user.get('full_name'))) or 'Поставщик'
    try:
        await bot.send_message(
            req['buyer_id'],
            f"💰 Получена цена!\n\n"
            f"📦 {req.get('model','')} {req.get('memory','')} {req.get('color','')}\n"
            f"💵 Цена: {price:,} ₽ за шт\n"
            f"🏢 Поставщик: {supplier_name}\n\n"
            f"Откройте приложение для подтверждения покупки"
        )
    except Exception as e:
        logging.warning("Не удалось уведомить покупателя: %s", e)
    return web.json_response({"ok": True}, headers=CORS_HEADERS)


async def post_deal_status_api(request):
    """API: Обновить статус сделки (POST /api/deals/{id}/status, JSON: {user_id, status})."""
    if request.method == "OPTIONS":
        return web.Response(headers=CORS_HEADERS)
    deal_id = request.match_info.get("id")
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON"}, status=400, headers=CORS_HEADERS)
    user_id = data.get("user_id")
    new_status = data.get("status")
    if not deal_id or not user_id or not new_status:
        return web.json_response({"error": "Required: deal_id, user_id, status"}, status=400, headers=CORS_HEADERS)
    try:
        deal_id = int(deal_id)
        user_id = int(user_id)
    except (TypeError, ValueError):
        return web.json_response({"error": "Invalid types"}, status=400, headers=CORS_HEADERS)
    deal = database.get_deal(deal_id)
    if not deal:
        return web.json_response({"error": "Deal not found"}, status=404, headers=CORS_HEADERS)
    # Проверка прав: покупатель или поставщик сделки
    if deal['buyer_id'] != user_id and deal['supplier_id'] != user_id and user_id not in ADMIN_IDS:
        return web.json_response({"error": "Нет прав"}, status=403, headers=CORS_HEADERS)
    database.update_deal_status(deal_id, new_status)
    # Обмен контактами при подтверждении
    if new_status == 'confirmed':
        buyer_user = database.get_user(deal['buyer_id'])
        supplier_user = database.get_user(deal['supplier_id'])
        supplier_username = supplier_user.get('username') if supplier_user else None
        buyer_username = buyer_user.get('username') if buyer_user else None
        if supplier_username:
            kb = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="💬 Открыть чат", url=f"https://t.me/{supplier_username}")
            ]])
            try:
                await bot.send_message(
                    deal['buyer_id'],
                    f"✅ Сделка #{deal_id} подтверждена!\n"
                    f"📦 {deal.get('model','')} {deal.get('memory','')} {deal.get('color','')}\n"
                    f"🏢 Поставщик: @{supplier_username}",
                    reply_markup=kb
                )
            except Exception:
                pass
        if buyer_username:
            kb2 = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="💬 Открыть чат", url=f"https://t.me/{buyer_username}")
            ]])
            try:
                await bot.send_message(
                    deal['supplier_id'],
                    f"✅ Вы подтвердили сделку #{deal_id}!\n"
                    f"📦 {deal.get('model','')} {deal.get('memory','')} {deal.get('color','')}\n"
                    f"👤 Покупатель: @{buyer_username}",
                    reply_markup=kb2
                )
            except Exception:
                pass
    # Уведомления о других статусах
    elif new_status == 'rejected':
        counterparty_id = deal['buyer_id'] if user_id == deal['supplier_id'] else deal['supplier_id']
        try:
            await bot.send_message(counterparty_id, f"❌ Сделка #{deal_id} отклонена.")
        except Exception:
            pass
    elif new_status == 'completed':
        try:
            await bot.send_message(
                deal['buyer_id'],
                f"🎉 Сделка #{deal_id} завершена! Оцените поставщика в приложении."
            )
        except Exception:
            pass
    return web.json_response({"ok": True}, headers=CORS_HEADERS)


async def get_supplier_stats_api(request):
    """API: Статистика поставщика (GET ?telegram_id=)."""
    telegram_id = request.query.get("telegram_id")
    if not telegram_id:
        return web.json_response({"error": "telegram_id required"}, status=400, headers=CORS_HEADERS)
    try:
        stats = database.get_supplier_stats(int(telegram_id))
    except ValueError:
        return web.json_response({"error": "Invalid telegram_id"}, status=400, headers=CORS_HEADERS)
    return web.json_response(stats, headers=CORS_HEADERS)


async def get_admin_deals_api(request):
    """API: Все сделки (только для админа, GET ?admin_id=)."""
    admin_id = request.query.get("admin_id")
    try:
        if not admin_id or int(admin_id) not in ADMIN_IDS:
            return web.json_response({"error": "Нет прав"}, status=403, headers=CORS_HEADERS)
    except ValueError:
        return web.json_response({"error": "Нет прав"}, status=403, headers=CORS_HEADERS)
    deals = database.get_all_deals()
    return web.json_response(deals, headers=CORS_HEADERS)


async def get_admin_supplier_requests_api(request):
    """API: Заявки поставщиков на верификацию (только для админа, GET ?admin_id=)."""
    admin_id = request.query.get("admin_id")
    try:
        if not admin_id or int(admin_id) not in ADMIN_IDS:
            return web.json_response({"error": "Нет прав"}, status=403, headers=CORS_HEADERS)
    except ValueError:
        return web.json_response({"error": "Нет прав"}, status=403, headers=CORS_HEADERS)
    conn = __import__('sqlite3').connect(database.DB_NAME)
    conn.row_factory = __import__('sqlite3').Row
    cursor = conn.cursor()
    cursor.execute('''
        SELECT sr.*, u.username, u.full_name
        FROM supplier_requests sr
        LEFT JOIN users u ON sr.telegram_id = u.telegram_id
        ORDER BY sr.created_at DESC LIMIT 100
    ''')
    rows = cursor.fetchall()
    conn.close()
    return web.json_response([dict(r) for r in rows], headers=CORS_HEADERS)


async def post_toggle_price_api(request):
    """API: Показать/скрыть цену оффера (POST /api/supplier/offers/{id}/toggle_price, JSON: {telegram_id})."""
    if request.method == "OPTIONS":
        return web.Response(headers=CORS_HEADERS)
    offer_id = request.match_info.get("id")
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON"}, status=400, headers=CORS_HEADERS)
    telegram_id = data.get("telegram_id")
    if not offer_id or not telegram_id:
        return web.json_response({"error": "Required: offer_id, telegram_id"}, status=400, headers=CORS_HEADERS)
    try:
        offer_id = int(offer_id)
        telegram_id = int(telegram_id)
    except (TypeError, ValueError):
        return web.json_response({"error": "Invalid types"}, status=400, headers=CORS_HEADERS)
    # Получаем текущее состояние оффера
    conn = __import__('sqlite3').connect(database.DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT price_hidden FROM offers WHERE id = ? AND supplier_id = ?', (offer_id, telegram_id))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return web.json_response({"error": "Offer not found or access denied"}, status=404, headers=CORS_HEADERS)
    new_hidden = 0 if row[0] else 1
    database.update_offer(offer_id, price_hidden=new_hidden)
    return web.json_response({"ok": True, "price_hidden": new_hidden}, headers=CORS_HEADERS)


async def post_add_review_api(request):
    """API: Добавить отзыв (POST JSON: deal_id, supplier_id, buyer_id, rating, comment)."""
    if request.method == "OPTIONS":
        return web.Response(headers=CORS_HEADERS)
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON"}, status=400, headers=CORS_HEADERS)
    deal_id = data.get("deal_id")
    supplier_id = data.get("supplier_id")
    buyer_id = data.get("buyer_id")
    rating = data.get("rating")
    comment = data.get("comment")
    if not all([deal_id, supplier_id, buyer_id, rating]):
        return web.json_response({"error": "Required: deal_id, supplier_id, buyer_id, rating"}, status=400, headers=CORS_HEADERS)
    try:
        database.add_review(int(deal_id), int(supplier_id), int(buyer_id), int(rating), comment)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500, headers=CORS_HEADERS)
    return web.json_response({"ok": True}, headers=CORS_HEADERS)


async def post_become_supplier_api(request):
    """API: Заявка на регистрацию поставщика (POST JSON: telegram_id, company_name, city, phone)."""
    if request.method == "OPTIONS":
        return web.Response(headers=CORS_HEADERS)
    try:
        data = await request.json()
    except Exception as e:
        return web.json_response(
            {"error": "Invalid JSON", "detail": str(e)},
            status=400,
            headers=CORS_HEADERS,
        )
    telegram_id = data.get("telegram_id")
    company_name = (data.get("company_name") or "").strip()
    city = (data.get("city") or "").strip()
    phone = (data.get("phone") or "").strip()
    if not telegram_id or not company_name or not city or not phone:
        return web.json_response(
            {"error": "Required: telegram_id, company_name, city, phone"},
            status=400,
            headers=CORS_HEADERS,
        )
    try:
        database.create_supplier_request(int(telegram_id), company_name, city, phone)
    except Exception as e:
        logging.exception("become_supplier")
        return web.json_response(
            {"error": str(e)},
            status=500,
            headers=CORS_HEADERS,
        )
    user = database.get_user(int(telegram_id))
    username = (user and user.get("username")) or "—"
    full_name = (user and user.get("full_name")) or "—"
    text = (
        "🆕 **Новая заявка поставщика**\n\n"
        f"👤 ID: `{telegram_id}`\n"
        f"📛 Имя: {full_name}\n"
        f"📱 @{username}\n"
        f"🏢 Компания: {company_name}\n"
        f"📍 Город: {city}\n"
        f"📞 Телефон: {phone}"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Одобрить", callback_data=f"approve_supplier_{telegram_id}")],
        [InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_supplier_{telegram_id}")],
    ])
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text, parse_mode="Markdown", reply_markup=kb)
        except Exception as e:
            logging.warning("Не удалось отправить уведомление админу %s: %s", admin_id, e)
    return web.json_response({"ok": True, "message": "Заявка отправлена"}, headers=CORS_HEADERS)

async def start_server():
    port = int(os.environ.get("PORT", 8080))
    app = web.Application()
    
    # Главная страница — index.html
    app.router.add_get("/", index_page)
    # Статика (CSS/JS): /static/ → папка static в корне бота
    static_dir = os.path.join(BASE_DIR, "static")
    os.makedirs(static_dir, exist_ok=True)
    app.router.add_static("/static/", static_dir, name="static")
    app.router.add_get("/health", health_check)
    app.router.add_get('/api/offers', get_offers_api)
    app.router.add_get('/api/offers/{id}', get_offer_by_id_api)
    app.router.add_get('/api/catalog', get_catalog_api)
    app.router.add_get('/api/catalog/{id}/offers', get_catalog_offers_api)
    app.router.add_get('/api/user', get_user_api)
    app.router.add_get('/api/deals', get_deals_api)
    app.router.add_get('/api/deal', get_deal_api)
    app.router.add_get('/api/supplier', get_supplier_profile_api)
    app.router.add_get('/api/supplier/offers', get_supplier_offers_api)
    app.router.add_post('/api/supplier/offers', post_supplier_offers_api)
    app.router.add_route("OPTIONS", "/api/supplier/offers", post_supplier_offers_api)
    app.router.add_delete('/api/supplier/offers/{id}', delete_supplier_offer_api)
    app.router.add_get('/api/supplier/template', get_supplier_template_api)
    app.router.add_post('/api/supplier/import', post_supplier_import_api)
    app.router.add_route("OPTIONS", "/api/supplier/import", post_supplier_import_api)
    app.router.add_post('/api/become_supplier', post_become_supplier_api)
    app.router.add_route("OPTIONS", "/api/become_supplier", post_become_supplier_api)
    app.router.add_post('/api/user/role', post_user_role_api)
    app.router.add_route("OPTIONS", "/api/user/role", post_user_role_api)
    app.router.add_get('/api/admin/users', get_admin_users_api)
    app.router.add_post('/api/admin/user/role', post_admin_user_role_api)
    app.router.add_route("OPTIONS", "/api/admin/user/role", post_admin_user_role_api)
    app.router.add_delete('/api/admin/user/{id}', delete_admin_user_api)
    # Create deal via API
    app.router.add_post('/api/deals', post_create_deal_api)
    app.router.add_route("OPTIONS", "/api/deals", post_create_deal_api)
    # Price requests
    app.router.add_post('/api/price_request', post_price_request_api)
    app.router.add_route("OPTIONS", "/api/price_request", post_price_request_api)
    app.router.add_get('/api/price_requests', get_price_requests_api)
    app.router.add_get('/api/buyer/price_requests', get_buyer_price_requests_api)
    app.router.add_post('/api/price_request/respond', post_respond_price_request_api)
    app.router.add_route("OPTIONS", "/api/price_request/respond", post_respond_price_request_api)
    # Deal status + reviews
    app.router.add_post('/api/deals/{id}/status', post_deal_status_api)
    app.router.add_route("OPTIONS", "/api/deals/{id}/status", post_deal_status_api)
    app.router.add_post('/api/reviews', post_add_review_api)
    app.router.add_route("OPTIONS", "/api/reviews", post_add_review_api)
    # Supplier stats + toggle price
    app.router.add_get('/api/supplier/stats', get_supplier_stats_api)
    app.router.add_post('/api/supplier/offers/{id}/toggle_price', post_toggle_price_api)
    app.router.add_route("OPTIONS", "/api/supplier/offers/{id}/toggle_price", post_toggle_price_api)
    # Admin deals + supplier requests
    app.router.add_get('/api/admin/deals', get_admin_deals_api)
    app.router.add_get('/api/admin/supplier_requests', get_admin_supplier_requests_api)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logging.info(f"API сервер запущен на порту {port}")

# ==================== TELEGRAM BOT ====================

@dp.message(Command("start"))
async def start(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username
    full_name = message.from_user.full_name
    
    # Создаём или обновляем пользователя
    database.create_or_update_user(user_id, username, full_name)
    
    full_url = f"{WEB_APP_URL}?v=6&uid={user_id}"
    kb = [[KeyboardButton(text="📱 ОТКРЫТЬ БИРЖУ", web_app=WebAppInfo(url=full_url))]]
    
    await message.answer(
        "👋 Добро пожаловать на **0000**\n\n"
        "🔹 Покупайте технику по лучшим ценам\n"
        "🔹 Продавайте через удобную панель\n"
        "🔹 Безопасные сделки \n\n"
        "Нажмите кнопку ниже, чтобы начать:",
        reply_markup=ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True),
        parse_mode="Markdown"
    )

@dp.message(F.web_app_data)
async def handle_webapp(message: types.Message):
    data = message.web_app_data.data
    user_id = message.chat.id
    username = message.from_user.username or "Пользователь"
    
    # CREATE_DEAL|offer_id|quantity
    if data.startswith("CREATE_DEAL"):
        parts = data.split("|")
        if len(parts) < 3:
            await message.answer("❌ Ошибка: неверный формат данных")
            return
        
        offer_id = int(parts[1])
        quantity = int(parts[2])
        
        # Получаем предложение
        offer = database.get_offer_by_id(offer_id)
        if not offer:
            await message.answer("❌ Предложение не найдено")
            return
        
        supplier_id = offer['supplier_id']
        price = offer['price']
        
        # Создаём сделку
        deal_id = database.create_deal(user_id, supplier_id, offer_id, quantity, price)
        
        # Уведомляем поставщика
        try:
            await bot.send_message(
                supplier_id,
                f"🔔 **Новая сделка #{deal_id}**\n\n"
                f"📦 {offer['model']} {offer['memory']} {offer['color']}\n"
                f"💰 {price:,} ₽ × {quantity} шт = {price * quantity:,} ₽\n"
                f"👤 Покупатель: @{username}\n\n"
                f"Откройте биржу для подтверждения",
                parse_mode="Markdown"
            )
        except:
            pass
        
        await message.answer(
            f"✅ **Сделка #{deal_id} создана**\n\n"
            f"Ожидайте подтверждения от поставщика.\n"
            f"Вы получите уведомление, когда статус изменится.",
            parse_mode="Markdown"
        )
        return
    
    # CONFIRM_DEAL|deal_id
    elif data.startswith("CONFIRM_DEAL"):
        deal_id = int(data.split("|")[1])
        database.update_deal_status(deal_id, 'confirmed')
        
        deal = database.get_deal(deal_id)
        buyer_id = deal['buyer_id']
        
        try:
            await bot.send_message(
                buyer_id,
                f"✅ Сделка #{deal_id} подтверждена поставщиком!\n\nОткройте биржу для общения.",
                parse_mode="Markdown"
            )
        except:
            pass
        
        await message.answer(f"✅ Сделка #{deal_id} подтверждена")
        return
    
    # UPDATE_DEAL_STATUS|deal_id|status
    elif data.startswith("UPDATE_DEAL_STATUS"):
        parts = data.split("|")
        deal_id = int(parts[1])
        status = parts[2]
        
        database.update_deal_status(deal_id, status)
        await message.answer(f"✅ Статус сделки #{deal_id} обновлён")
        return
    
    # ADD_OFFER|catalog_id|price|quantity|moq|condition|delivery_days|warranty_months[|comment]
    elif data.startswith("ADD_OFFER"):
        parts = data.split("|", 8)
        if len(parts) < 8:
            await message.answer("❌ Ошибка: неверный формат данных")
            return
        
        catalog_id = int(parts[1])
        price = int(parts[2])
        quantity = int(parts[3])
        moq = int(parts[4])
        condition = parts[5]
        delivery_days = int(parts[6])
        warranty_months = int(parts[7])
        comment = parts[8].strip() if len(parts) > 8 and parts[8] else None
        
        offer_id = database.create_offer(
            user_id, catalog_id, price, quantity, moq,
            condition, delivery_days, warranty_months, comment
        )
        
        await message.answer(f"✅ Предложение #{offer_id} добавлено в биржу")
        return
    
    # UPDATE_OFFER|offer_id|field|value
    elif data.startswith("UPDATE_OFFER"):
        parts = data.split("|")
        offer_id = int(parts[1])
        field = parts[2]
        value = parts[3]
        
        # Преобразуем значение в нужный тип
        if field in ['price', 'quantity', 'moq', 'delivery_days', 'warranty_months']:
            value = int(value)
        elif field in ['is_available', 'is_visible']:
            value = int(value)
        
        database.update_offer(offer_id, **{field: value})
        await message.answer(f"✅ Предложение обновлено")
        return
    
    # DELETE_OFFER|offer_id
    elif data.startswith("DELETE_OFFER"):
        offer_id = int(data.split("|")[1])
        success = database.delete_offer(offer_id, user_id)
        
        if success:
            await message.answer("✅ Предложение удалено")
        else:
            await message.answer("❌ Не удалось удалить предложение")
        return
    
    # SEND_MESSAGE|deal_id|message
    elif data.startswith("SEND_MESSAGE"):
        parts = data.split("|", 2)
        deal_id = int(parts[1])
        msg_text = parts[2]
        
        database.add_message(deal_id, user_id, msg_text)
        
        # Уведомляем собеседника
        deal = database.get_deal(deal_id)
        counterparty_id = deal['supplier_id'] if deal['buyer_id'] == user_id else deal['buyer_id']
        
        try:
            await bot.send_message(
                counterparty_id,
                f"💬 Новое сообщение в сделке #{deal_id}\n\n{msg_text}",
                parse_mode="Markdown"
            )
        except:
            pass
        
        return
    
    # ADD_REVIEW|deal_id|supplier_id|rating|comment
    elif data.startswith("ADD_REVIEW"):
        parts = data.split("|", 4)
        deal_id = int(parts[1])
        supplier_id = int(parts[2])
        rating = int(parts[3])
        comment = parts[4] if len(parts) > 4 else None
        
        database.add_review(deal_id, supplier_id, user_id, rating, comment)
        await message.answer("✅ Отзыв добавлен. Спасибо!")
        return
    
    # REGISTER_SUPPLIER|company_name|city|phone
    elif data.startswith("REGISTER_SUPPLIER"):
        parts = data.split("|")
        company_name = parts[1]
        city = parts[2]
        phone = parts[3]
        
        database.update_user_supplier_info(user_id, company_name, city, phone)
        await message.answer(
            "✅ **Вы зарегистрированы как поставщик!**\n\n"
            "Теперь вы можете добавлять предложения на биржу.",
            parse_mode="Markdown"
        )
        return

@dp.message(Command("admin"))
async def admin_command(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ У вас нет прав администратора")
        return
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить в каталог", callback_data="admin_add_catalog")],
        [InlineKeyboardButton(text="📋 Посмотреть каталог", callback_data="admin_view_catalog")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")]
    ])
    
    await message.answer("🔧 **Панель администратора**", reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data == "admin_add_catalog")
async def admin_add_catalog(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет прав", show_alert=True)
        return
    await callback.message.edit_text(
        "➕ **Добавление в каталог**\n\n"
        "Отправьте команду:\n"
        "`/add_catalog Категория|Бренд|Модель|Память|Цвет|SKU`\n\n"
        "Пример:\n"
        "`/add_catalog iPhone|Apple|iPhone 16 Pro Max|256GB|Черный титан|IP16PM256BT`",
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.message(Command("add_catalog"))
async def add_catalog(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    try:
        parts = message.text.split(" ", 1)[1].split("|")
        if len(parts) != 6:
            await message.answer("❌ Неверный формат. Используйте:\n`/add_catalog Категория|Бренд|Модель|Память|Цвет|SKU`", parse_mode="Markdown")
            return
        
        category, brand, model, memory, color, sku = [p.strip() for p in parts]
        success, msg = database.add_catalog_item(category, brand, model, memory, color, sku)
        
        if success:
            await message.answer(f"✅ {msg}\n\nSKU: `{sku}`", parse_mode="Markdown")
        else:
            await message.answer(f"❌ {msg}")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")

@dp.callback_query(F.data == "admin_view_catalog")
async def admin_view_catalog(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет прав", show_alert=True)
        return
    catalog = database.get_catalog()
    
    if not catalog:
        await callback.message.edit_text("📋 Каталог пуст")
        await callback.answer()
        return
    
    text = f"📋 **Каталог ({len(catalog)} товаров)**\n\n"
    for item in catalog[:20]:
        text += f"• {item['brand']} {item['model']} {item['memory']} {item['color']}\n  SKU: `{item['sku']}`\n\n"
    
    if len(catalog) > 20:
        text += f"... и еще {len(catalog) - 20} товаров"
    
    await callback.message.edit_text(text, parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data == "admin_stats")
async def admin_stats(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет прав", show_alert=True)
        return
    # Тут можно добавить статистику по сделкам, пользователям и т.д.
    await callback.message.edit_text("📊 **Статистика**\n\n(В разработке)")
    await callback.answer()


@dp.callback_query(F.data.startswith("approve_supplier_"))
async def callback_approve_supplier(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет прав", show_alert=True)
        return
    try:
        candidate_id = int(callback.data.replace("approve_supplier_", ""))
    except ValueError:
        await callback.answer("Неверные данные", show_alert=True)
        return
    if not database.approve_supplier_request(candidate_id):
        await callback.answer("Заявка не найдена", show_alert=True)
        return
    try:
        await bot.send_message(
            candidate_id,
            "✅ Поздравляем! Ваша заявка одобрена. Перезагрузите приложение.",
        )
    except Exception as e:
        logging.warning("Не удалось отправить сообщение кандидату %s: %s", candidate_id, e)
    admin_name = callback.from_user.full_name or callback.from_user.username or "Админ"
    new_text = (callback.message.text or "") + f"\n\n✅ Заявка одобрена админом {admin_name}"
    await callback.message.edit_text(new_text, parse_mode="Markdown", reply_markup=None)
    await callback.answer("Одобрено")


@dp.callback_query(F.data.startswith("reject_supplier_"))
async def callback_reject_supplier(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет прав", show_alert=True)
        return
    try:
        candidate_id = int(callback.data.replace("reject_supplier_", ""))
    except ValueError:
        await callback.answer("Неверные данные", show_alert=True)
        return
    database.reject_supplier_request(candidate_id)
    try:
        await bot.send_message(
            candidate_id,
            "❌ К сожалению, ваша заявка отклонена.",
        )
    except Exception as e:
        logging.warning("Не удалось отправить сообщение кандидату %s: %s", candidate_id, e)
    await callback.message.edit_text(
        (callback.message.text or "") + "\n\n❌ Заявка отклонена",
        parse_mode="Markdown",
        reply_markup=None,
    )
    await callback.answer("Отклонено")


async def main():
    database.init_db()
    await start_server()
    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("Бот запущен")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
