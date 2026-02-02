import asyncio
import logging
import json
import urllib.parse
import time
import os # <--- НУЖНО ДЛЯ RENDER
from aiohttp import web # <--- БИБЛИОТЕКА ДЛЯ "САЙТА"

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import WebAppInfo, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

import database 

# !!! ВАЖНО: Если Render не видит токен, вставьте его прямо сюда в кавычки !!!
TOKEN = "8516086910:AAFugoM9-OjnOOJFT3flpcyUOhh4P9alxSY"
WEB_APP_URL = "https://rikman21.github.io/Gorbushka/" 

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- 🎭 ФЕЙКОВЫЙ САЙТ ДЛЯ RENDER ---
async def health_check(request):
    return web.Response(text="Bot is alive!")

async def start_dummy_server():
    # Render сам скажет, какой порт слушать. Если нет - берем 8080
    port = int(os.environ.get("PORT", 8080))
    
    app = web.Application()
    app.router.add_get('/', health_check)
    app.router.add_get('/health', health_check)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"🌍 Фейковый сайт запущен на порту {port}")

# --- ЛОГИКА БОТА ---
@dp.message(Command("start"))
async def start(message: types.Message):
    user_id = message.from_user.id
    offers_list = database.get_all_offers()
    offers_json = json.dumps(offers_list)
    offers_encoded = urllib.parse.quote(offers_json)
    
    timestamp = int(time.time())
    full_url = f"{WEB_APP_URL}?data={offers_encoded}&ver={timestamp}&uid={user_id}"

    kb = [
        [KeyboardButton(text="📱 ОТКРЫТЬ МАРКЕТ", web_app=WebAppInfo(url=full_url))]
    ]
    markup = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    
    await message.answer(
        "👇 Нажимайте кнопку внизу для входа:", 
        reply_markup=markup
    )

@dp.message(F.web_app_data)
async def handle_webapp(message: types.Message):
    data = message.web_app_data.data
    user_id = message.chat.id
    username = message.from_user.username or "Клиент"

    if data.startswith("REQ_BUY"):
        parts = data.split("|")
        seller_id = int(parts[1])
        product_name = parts[3]
        price = parts[4]

        await message.answer(f"⏳ Запрос отправлен продавцу...")
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ В наличии", callback_data=f"confirm_{user_id}")],
            [InlineKeyboardButton(text="❌ Нет", callback_data=f"reject_{seller_id}")]
        ])
        try:
            await bot.send_message(seller_id, f"🔔 <b>ЗАКАЗ!</b>\n\n📦 {product_name}\n💰 {price}р\n👤 @{username}\n\nВ наличии?", reply_markup=kb, parse_mode="HTML")
        except:
            await message.answer("Ошибка: Продавец не найден.")

    elif data.startswith("NEW_PRICE"):
        parts = data.split("|")
        product_name = parts[1]
        price_str = parts[2]
        try:
            price = int(price_str)
            database.add_offer(user_id, username, product_name, price)
            await message.answer(f"💾 Цена сохранена в базу!\n{product_name} — {price}р")
        except ValueError:
            await message.answer("Ошибка цены!")

@dp.callback_query(F.data.startswith("confirm_"))
async def confirm_order(callback: types.CallbackQuery):
    buyer_id = int(callback.data.split("_")[1])
    seller_username = callback.from_user.username
    await callback.message.edit_text(f"✅ Подтверждено!", reply_markup=None)
    await bot.send_message(buyer_id, f"🎉 Продавец подтвердил!\nКонтакт: @{seller_username}")

@dp.callback_query(F.data.startswith("reject_"))
async def reject_order(callback: types.CallbackQuery):
    await callback.message.edit_text(f"🚫 Отказ.", reply_markup=None)

async def main():
    database.init_db()
    
    # Сначала запускаем фейковый сайт
    await start_dummy_server()
    
    print("🚀 БОТ ЗАПУЩЕН! (Теперь Render будет доволен)")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
