import asyncio
import logging
import json
import urllib.parse
import time
import os
from aiohttp import web
from openpyxl import Workbook
from io import BytesIO

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import WebAppInfo, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile

import database 

TOKEN = "8516086910:AAFugoM9-OjnOOJFT3flpcyUOhh4P9alxSY"
WEB_APP_URL = "https://rikman21.github.io/Gorbushka/" 

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- ФЕЙКОВЫЙ СЕРВЕР ---
async def health_check(request): return web.Response(text="Alive")
async def start_dummy_server():
    port = int(os.environ.get("PORT", 8080))
    app = web.Application()
    app.router.add_get('/', health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

# --- ЛОГИКА EXCEL ---
@dp.message(Command("template"))
async def send_template(message: types.Message):
    # 1. Берем товары из базы
    products = database.get_catalog_for_excel()
    
    # 2. Создаем Excel
    wb = Workbook()
    ws = wb.active
    ws.title = "Прайс-лист"
    
    # Заголовки
    headers = ["SKU (Не менять!)", "Модель", "Память", "Цвет", "Сим", "ВАША ЦЕНА (Рубли)"]
    ws.append(headers)
    
    # Данные
    for p in products:
        # p = (sku, model, mem, col, sim)
        row = list(p) + [""] # Добавляем пустую колонку для цены
        ws.append(row)
        
    # 3. Сохраняем в память (не на диск)
    file_stream = BytesIO()
    wb.save(file_stream)
    file_stream.seek(0)
    
    # 4. Отправляем
    document = BufferedInputFile(file_stream.read(), filename="Gorbushka_Price_Template.xlsx")
    await message.answer_document(document, caption="📉 **Ваш шаблон для цен**\n\n1. Скачайте файл.\n2. Проставьте цены в последнем столбце.\n3. Отправьте файл мне обратно (Скоро заработает).")

# --- СТАРТ ---
@dp.message(Command("start"))
async def start(message: types.Message):
    user_id = message.from_user.id
    # Берем цены из базы (уже по новой схеме)
    offers_list = database.get_all_offers_for_web()
    
    offers_json = json.dumps(offers_list)
    offers_encoded = urllib.parse.quote(offers_json)
    timestamp = int(time.time())
    
    full_url = f"{WEB_APP_URL}?data={offers_encoded}&ver={timestamp}&uid={user_id}"

    kb = [
        [KeyboardButton(text="📱 ОТКРЫТЬ МАРКЕТ", web_app=WebAppInfo(url=full_url))]
    ]
    markup = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    
    await message.answer(
        "👋 Привет! \n\n🛒 **Покупатель:** Жми кнопку внизу.\n📦 **Продавец:** Скачай шаблон цен командой /template", 
        reply_markup=markup
    )

# ... (Остальной код заказов REQ_BUY оставляем пока старый, он работает) ...
# ВАЖНО: Код handle_webapp я пока сократил, так как мы меняем базу.
# Сейчас главное - проверить скачивание файла.

async def main():
    database.init_db()
    await start_dummy_server()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
