import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import WebAppInfo, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

# --- НАСТРОЙКИ ---
TOKEN = "8516086910:AAFugoM9-OjnOOJFT3flpcyUOhh4P9alxSY"
WEB_APP_URL = "https://rikman21.github.io/Gorbushka/"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- СТАРТ (Используем ту самую КНОПКУ, которая работает!) ---
@dp.message(Command("start"))
async def start(message: types.Message):
    # Создаем большую кнопку внизу
    kb = [
        [KeyboardButton(text="📱 ОТКРЫТЬ ГОРБУШКУ", web_app=WebAppInfo(url=WEB_APP_URL))]
    ]
    keyboard = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    
    await message.answer(
        "👋 Добро пожаловать!\nНажмите кнопку внизу, чтобы войти в маркет.", 
        reply_markup=keyboard
    )

# --- ОБРАБОТКА ДАННЫХ ИЗ ПРИЛОЖЕНИЯ ---
@dp.message(F.web_app_data)
async def handle_webapp(message: types.Message):
    data = message.web_app_data.data
    buyer_id = message.chat.id
    buyer_username = message.from_user.username or "Клиент"

    print(f"📦 Пришло: {data}") # Контроль в терминале

    # ЛОГИКА 1: Покупатель хочет купить (REQ_BUY)
    if data.startswith("REQ_BUY"):
        # Разбираем: REQ_BUY | ID_Продавца | Имя | Товар | Цена
        try:
            parts = data.split("|")
            seller_id = int(parts[1])
            product_name = parts[3]
            price = parts[4]

            # 1. Пишем Покупателю
            await message.answer(f"⏳ Запрос отправлен продавцу. Ждем подтверждения...")

            # 2. Пишем Продавцу (Вам)
            # Создаем кнопки Да/Нет
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✅ В наличии (Продать)", callback_data=f"confirm_{buyer_id}")],
                [InlineKeyboardButton(text="❌ Нет (Скрыть)", callback_data=f"reject_{seller_id}")]
            ])
            
            await bot.send_message(
                chat_id=seller_id,
                text=f"🔔 <b>НОВЫЙ ЗАКАЗ!</b>\n\n📦 Товар: {product_name}\n💰 Цена: {price}р\n👤 Покупатель: @{buyer_username}\n\nТовар в наличии?",
                reply_markup=kb,
                parse_mode="HTML"
            )
        except Exception as e:
            print(f"Ошибка: {e}")
            await message.answer("Ошибка передачи данных продавцу.")

    # ЛОГИКА 2: Продавец ставит цену (NEW_PRICE)
    elif data.startswith("NEW_PRICE"):
        parts = data.split("|")
        product = parts[1]
        price = parts[2]
        await message.answer(f"✅ Прайс обновлен!\n{product} — {price}р")

# --- ОБРАБОТКА НАЖАТИЯ КНОПОК ПРОДАВЦОМ ---

@dp.callback_query(F.data.startswith("confirm_"))
async def confirm_order(callback: types.CallbackQuery):
    buyer_id = int(callback.data.split("_")[1])
    seller_username = callback.from_user.username

    # Уведомляем продавца
    await callback.message.edit_text(f"✅ Вы подтвердили сделку!\nОжидайте сообщения от покупателя.", reply_markup=None)
    
    # Отправляем контакт покупателю
    await bot.send_message(
        chat_id=buyer_id,
        text=f"🎉 <b>Продавец подтвердил наличие!</b>\n\nПишите ему сюда: https://t.me/{seller_username}\nДоговоритесь об оплате и доставке.",
        parse_mode="HTML"
    )

@dp.callback_query(F.data.startswith("reject_"))
async def reject_order(callback: types.CallbackQuery):
    await callback.message.edit_text(f"🚫 Вы отказали. Товар временно скрыт.", reply_markup=None)

async def main():
    print("🚀 ГОРБУШКА ЗАПУЩЕНА!")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())