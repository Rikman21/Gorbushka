import os
import json
import logging
import asyncio
import aiohttp
import redis.asyncio as redis
from aiogram import Bot

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
REDIS_HOST = os.environ.get("REDIS_HOST", "redis")
REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))
USER_SERVICE = os.environ.get("USER_SERVICE_URL", "http://user-service:8081")

bot = Bot(token=BOT_TOKEN)


async def get_users_with_notifications():
    """Get list of telegram_ids of users with notifications enabled."""
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(f"{USER_SERVICE}/internal/suppliers_with_notifications") as resp:
                if resp.status == 200:
                    return await resp.json()
        except Exception as e:
            logging.warning("Failed to get users: %s", e)
    return []


async def get_user_link(telegram_id):
    """Get user display name with @username link if available."""
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(f"{USER_SERVICE}/api/user?telegram_id={telegram_id}") as resp:
                if resp.status == 200:
                    user = await resp.json()
                    username = user.get("username")
                    name = user.get("company_name") or user.get("full_name") or str(telegram_id)
                    if username:
                        return f"{name} (@{username})"
                    return name
        except Exception as e:
            logging.warning("Failed to get user %s: %s", telegram_id, e)
    return str(telegram_id)


async def send_safe(chat_id, text, **kwargs):
    """Send message ignoring errors."""
    try:
        await bot.send_message(chat_id, text, **kwargs)
    except Exception as e:
        logging.warning("Failed to send to %s: %s", chat_id, e)


async def handle_notification(payload):
    """Process a single notification from Redis queue."""
    event_type = payload.get("type")

    if event_type == "new_deal":
        supplier_id = payload["supplier_id"]
        buyer_id = payload["buyer_id"]
        deal_id = payload["deal_id"]
        model = payload.get("model", "")
        memory = payload.get("memory", "")
        color = payload.get("color", "")
        price = payload.get("price", 0)
        quantity = payload.get("quantity", 1)
        buyer_link = await get_user_link(buyer_id)
        await send_safe(
            supplier_id,
            f"🔔 Новая сделка #{deal_id}\n\n"
            f"📦 {model} {memory} {color}\n"
            f"💰 {price:,} ₽ × {quantity} шт\n"
            f"👤 Покупатель: {buyer_link}\n\n"
            f"Откройте биржу для подтверждения"
        )

    elif event_type == "deal_status":
        status = payload["status"]
        deal_id = payload["deal_id"]
        buyer_id = payload["buyer_id"]
        supplier_id = payload["supplier_id"]
        user_id = payload.get("user_id")
        model = payload.get("model", "")
        memory = payload.get("memory", "")
        color = payload.get("color", "")
        buyer_username = payload.get("buyer_username", "")
        supplier_username = payload.get("supplier_username", "")

        if status == "confirmed":
            if supplier_username:
                await send_safe(
                    buyer_id,
                    f"✅ Сделка #{deal_id} подтверждена!\n"
                    f"📦 {model} {memory} {color}\n"
                    f"🏢 Поставщик: @{supplier_username}"
                )
            if buyer_username:
                await send_safe(
                    supplier_id,
                    f"✅ Вы подтвердили сделку #{deal_id}!\n"
                    f"📦 {model} {memory} {color}\n"
                    f"👤 Покупатель: @{buyer_username}"
                )
        elif status == "rejected":
            counterparty_id = buyer_id if user_id == supplier_id else supplier_id
            await send_safe(counterparty_id, f"❌ Сделка #{deal_id} отклонена.")
        elif status == "completed":
            await send_safe(buyer_id, f"🎉 Сделка #{deal_id} завершена! Оцените поставщика в приложении.")

    elif event_type == "price_request":
        supplier_id = payload["supplier_id"]
        buyer_id = payload["buyer_id"]
        request_id = payload["request_id"]
        model = payload.get("model", "")
        memory = payload.get("memory", "")
        color = payload.get("color", "")
        quantity = payload.get("quantity", 1)
        buyer_link = await get_user_link(buyer_id)
        await send_safe(
            supplier_id,
            f"💬 Запрос цены #{request_id}\n\n"
            f"📦 {model} {memory} {color}\n"
            f"🔢 Количество: {quantity} шт\n"
            f"👤 Покупатель: {buyer_link}\n\n"
            f"⏰ У вас 10 минут чтобы ответить в приложении"
        )

    elif event_type == "price_response":
        buyer_id = payload["buyer_id"]
        model = payload.get("model", "")
        memory = payload.get("memory", "")
        color = payload.get("color", "")
        price = payload.get("price", 0)
        await send_safe(
            buyer_id,
            f"💰 Получена цена!\n\n"
            f"📦 {model} {memory} {color}\n"
            f"💵 Цена: {price:,} ₽ за шт\n\n"
            f"Откройте приложение → Примите или отклоните цену"
        )

    elif event_type == "price_accepted":
        supplier_id = payload["supplier_id"]
        buyer_id = payload["buyer_id"]
        buyer_username = payload.get("buyer_username", "")
        buyer_name = payload.get("buyer_name", "")
        model = payload.get("model", "")
        memory = payload.get("memory", "")
        color = payload.get("color", "")
        price = payload.get("price", 0)
        contact = f"@{buyer_username}" if buyer_username else buyer_name or str(buyer_id)
        await send_safe(
            supplier_id,
            f"✅ Покупатель принял вашу цену!\n\n"
            f"📦 {model} {memory} {color}\n"
            f"💵 Цена: {price:,} ₽ за шт\n\n"
            f"👤 Контакт покупателя: {contact}\n"
            f"Свяжитесь для завершения сделки"
        )

    elif event_type == "price_rejected":
        supplier_id = payload["supplier_id"]
        model = payload.get("model", "")
        memory = payload.get("memory", "")
        color = payload.get("color", "")
        price = payload.get("price", 0)
        await send_safe(
            supplier_id,
            f"❌ Покупатель отклонил цену\n\n"
            f"📦 {model} {memory} {color}\n"
            f"💵 Цена была: {price:,} ₽ за шт"
        )

    elif event_type == "price_request_expired":
        buyer_id = payload["buyer_id"]
        supplier_id = payload["supplier_id"]
        await send_safe(buyer_id, "⏰ Поставщик не ответил на запрос цены за 10 минут.")
        await send_safe(supplier_id, "⚠️ Запрос цены истёк — покупатель не дождался ответа.")

    elif event_type == "buyer_request":
        text = payload.get("text", "")
        supplier_ids = await get_users_with_notifications()
        for sid in supplier_ids:
            await send_safe(sid, text)

    elif event_type == "buyer_request_response":
        buyer_id = payload["buyer_id"]
        item = payload.get("item", "")
        price = payload.get("price", 0)
        await send_safe(
            buyer_id,
            f"💰 Поставщик ответил на ваш запрос!\n\n"
            f"📱 {item}\n"
            f"💵 Цена: {price:,} ₽\n\n"
            f"Откройте приложение → Примите или отклоните"
        )

    elif event_type == "buyer_response_accepted":
        supplier_id = payload["supplier_id"]
        buyer_id = payload["buyer_id"]
        buyer_username = payload.get("buyer_username", "")
        buyer_name = payload.get("buyer_name", "")
        model = payload.get("model", "")
        memory = payload.get("memory", "")
        color = payload.get("color", "")
        price = payload.get("price", 0)
        contact = f"@{buyer_username}" if buyer_username else buyer_name or str(buyer_id)
        await send_safe(
            supplier_id,
            f"✅ Покупатель принял вашу цену!\n\n"
            f"📦 {model} {memory} {color}\n"
            f"💵 Цена: {price:,} ₽\n\n"
            f"👤 Контакт покупателя: {contact}\n"
            f"Свяжитесь для завершения сделки"
        )

    elif event_type == "buyer_response_rejected":
        supplier_id = payload["supplier_id"]
        model = payload.get("model", "")
        memory = payload.get("memory", "")
        color = payload.get("color", "")
        price = payload.get("price", 0)
        await send_safe(
            supplier_id,
            f"❌ Покупатель отклонил вашу цену\n\n"
            f"📦 {model} {memory} {color}\n"
            f"💵 Цена была: {price:,} ₽"
        )

    else:
        logging.warning("Unknown notification type: %s", event_type)


async def main():
    logging.info("notify-service: starting Redis consumer...")
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

    while True:
        try:
            result = await r.blpop("notifications", timeout=5)
            if result:
                _, raw = result
                try:
                    payload = json.loads(raw)
                    await handle_notification(payload)
                except json.JSONDecodeError as e:
                    logging.error("Invalid JSON in queue: %s", e)
                except Exception as e:
                    logging.exception("Error handling notification: %s", e)
        except redis.ConnectionError:
            logging.warning("Redis connection lost, reconnecting in 3s...")
            await asyncio.sleep(3)
        except Exception as e:
            logging.exception("Unexpected error: %s", e)
            await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(main())
