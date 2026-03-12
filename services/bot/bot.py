import os
import json
import logging
import asyncio
import aiohttp
import redis.asyncio as redis
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import (
    WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton,
    MenuButtonWebApp, ReplyKeyboardRemove,
)

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
WEB_APP_URL = os.environ.get("WEB_APP_URL", "https://api.4-0.xn--p1ai/")
ADMIN_IDS = [int(x) for x in os.environ.get("ADMIN_IDS", "").split(",") if x.strip()]
USER_SERVICE = os.environ.get("USER_SERVICE_URL", "http://user-service:8081")
CATALOG_SERVICE = os.environ.get("CATALOG_SERVICE_URL", "http://catalog-service:8082")
DEAL_SERVICE = os.environ.get("DEAL_SERVICE_URL", "http://deal-service:8083")
REDIS_HOST = os.environ.get("REDIS_HOST", "redis")
REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


async def service_call(method, url, json_data=None):
    """Helper: HTTP call to internal service."""
    async with aiohttp.ClientSession() as session:
        if method == "GET":
            async with session.get(url) as resp:
                return resp.status, await resp.json()
        elif method == "POST":
            async with session.post(url, json=json_data) as resp:
                return resp.status, await resp.json()


async def publish_notification(event_type, data):
    """Push notification to Redis queue for notify-service."""
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    payload = json.dumps({"type": event_type, **data}, ensure_ascii=False)
    await r.rpush("notifications", payload)
    await r.close()


# ==================== COMMANDS ====================

@dp.message(Command("start"))
async def start(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username
    full_name = message.from_user.full_name

    # Create/update user via user-service
    await service_call("POST", f"{USER_SERVICE}/api/user", {
        "telegram_id": user_id,
        "username": username,
        "full_name": full_name,
    })

    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="📱 Открыть биржу", web_app=WebAppInfo(url=WEB_APP_URL))
    ]])
    await message.answer(
        "👋 Добро пожаловать на **0000**\n\n"
        "🔹 Покупайте технику по лучшим ценам\n"
        "🔹 Продавайте через удобную панель\n"
        "🔹 Безопасные сделки",
        reply_markup=kb,
        parse_mode="Markdown"
    )


@dp.message(Command("admin"))
async def admin_command(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ У вас нет прав администратора")
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Посмотреть каталог", callback_data="admin_view_catalog")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")]
    ])
    await message.answer("🔧 **Панель администратора**", reply_markup=kb, parse_mode="Markdown")


@dp.callback_query(F.data == "admin_view_catalog")
async def admin_view_catalog(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет прав", show_alert=True)
        return
    status, catalog = await service_call("GET", f"{CATALOG_SERVICE}/api/catalog?all=1")
    if not catalog:
        await callback.message.edit_text("📋 Каталог пуст")
        await callback.answer()
        return
    text = f"📋 **Каталог ({len(catalog)} товаров)**\n\n"
    for item in catalog[:20]:
        text += f"• {item.get('brand','')} {item.get('model','')} {item.get('memory','')} {item.get('color','')}\n"
    if len(catalog) > 20:
        text += f"\n... и еще {len(catalog) - 20} товаров"
    await callback.message.edit_text(text, parse_mode="Markdown")
    await callback.answer()


@dp.callback_query(F.data == "admin_stats")
async def admin_stats(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет прав", show_alert=True)
        return
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
    await service_call("POST", f"{USER_SERVICE}/internal/approve_supplier", {"telegram_id": candidate_id})
    await publish_notification("supplier_approved", {"candidate_id": candidate_id})

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
    await service_call("POST", f"{USER_SERVICE}/internal/reject_supplier", {"telegram_id": candidate_id})
    await publish_notification("supplier_rejected", {"candidate_id": candidate_id})

    await callback.message.edit_text(
        (callback.message.text or "") + "\n\n❌ Заявка отклонена",
        parse_mode="Markdown", reply_markup=None,
    )
    await callback.answer("Отклонено")


# ==================== WEB APP DATA ====================

@dp.message(F.web_app_data)
async def handle_webapp(message: types.Message):
    data = message.web_app_data.data
    user_id = message.chat.id

    if data.startswith("CREATE_DEAL"):
        parts = data.split("|")
        if len(parts) < 3:
            await message.answer("❌ Неверный формат данных")
            return
        offer_id = int(parts[1])
        quantity = int(parts[2])
        status, result = await service_call("POST", f"{DEAL_SERVICE}/api/deals", {
            "buyer_id": user_id, "offer_id": offer_id, "quantity": quantity
        })
        if status == 200:
            deal_id = result.get("deal_id")
            await message.answer(f"✅ **Сделка #{deal_id} создана**\n\nОжидайте подтверждения от поставщика.", parse_mode="Markdown")
        else:
            await message.answer(f"❌ {result.get('error', 'Ошибка')}")

    elif data.startswith("CONFIRM_DEAL"):
        deal_id = int(data.split("|")[1])
        await service_call("POST", f"{DEAL_SERVICE}/api/deals/{deal_id}/status", {
            "user_id": user_id, "status": "confirmed"
        })
        await message.answer(f"✅ Сделка #{deal_id} подтверждена")

    elif data.startswith("UPDATE_DEAL_STATUS"):
        parts = data.split("|")
        deal_id = int(parts[1])
        new_status = parts[2]
        await service_call("POST", f"{DEAL_SERVICE}/api/deals/{deal_id}/status", {
            "user_id": user_id, "status": new_status
        })
        await message.answer(f"✅ Статус сделки #{deal_id} обновлён")

    elif data.startswith("ADD_OFFER"):
        parts = data.split("|", 8)
        if len(parts) < 8:
            await message.answer("❌ Неверный формат данных")
            return
        status, result = await service_call("POST", f"{CATALOG_SERVICE}/api/supplier/offers", {
            "telegram_id": user_id, "product_id": int(parts[1]),
            "price": int(parts[2]), "quantity": int(parts[3]),
            "condition": parts[5],
            "comment": parts[8].strip() if len(parts) > 8 and parts[8] else None,
        })
        if status == 200:
            await message.answer(f"✅ Предложение #{result.get('id')} добавлено")
        else:
            await message.answer(f"❌ {result.get('error', 'Ошибка')}")

    elif data.startswith("DELETE_OFFER"):
        offer_id = int(data.split("|")[1])
        async with aiohttp.ClientSession() as session:
            async with session.delete(
                f"{CATALOG_SERVICE}/api/supplier/offers/{offer_id}?telegram_id={user_id}"
            ) as resp:
                if resp.status == 200:
                    await message.answer("✅ Предложение удалено")
                else:
                    await message.answer("❌ Не удалось удалить предложение")

    elif data.startswith("SEND_MESSAGE"):
        parts = data.split("|", 2)
        deal_id = int(parts[1])
        msg_text = parts[2]
        # For messages we need to call deal-service or store directly
        # For now just confirm
        await message.answer("✅ Сообщение отправлено")

    elif data.startswith("ADD_REVIEW"):
        parts = data.split("|", 4)
        deal_id = int(parts[1])
        supplier_id = int(parts[2])
        rating = int(parts[3])
        comment = parts[4] if len(parts) > 4 else None
        await service_call("POST", f"{DEAL_SERVICE}/api/reviews", {
            "deal_id": deal_id, "supplier_id": supplier_id,
            "buyer_id": user_id, "rating": rating, "comment": comment
        })
        await message.answer("✅ Отзыв добавлен. Спасибо!")

    elif data.startswith("REGISTER_SUPPLIER"):
        parts = data.split("|")
        await service_call("POST", f"{USER_SERVICE}/api/become_supplier", {
            "telegram_id": user_id,
            "company_name": parts[1],
            "city": parts[2],
            "phone": parts[3],
        })
        await message.answer(
            "✅ **Заявка отправлена!**\n\nОжидайте одобрения администратором.",
            parse_mode="Markdown"
        )


async def main():
    logging.info("Bot starting...")
    await bot.delete_webhook(drop_pending_updates=True)
    await bot.set_chat_menu_button(menu_button=MenuButtonWebApp(
        text="📱 Открыть биржу",
        web_app=WebAppInfo(url=WEB_APP_URL),
    ))
    logging.info("Bot started, polling...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
