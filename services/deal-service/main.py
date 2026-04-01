import os
import json
import logging
import asyncio
import aiohttp
from aiohttp import web
import redis.asyncio as redis
import database

logging.basicConfig(level=logging.INFO)

ADMIN_IDS = [int(x) for x in os.environ.get("ADMIN_IDS", "").split(",") if x.strip()]
REDIS_HOST = os.environ.get("REDIS_HOST", "redis")
REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))
CATALOG_SERVICE = os.environ.get("CATALOG_SERVICE_URL", "http://catalog-service:8082")
USER_SERVICE = os.environ.get("USER_SERVICE_URL", "http://user-service:8081")

redis_client: redis.Redis = None

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, DELETE, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
}


def json_serial(obj):
    import datetime
    if isinstance(obj, (datetime.datetime, datetime.date)):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")


def json_response(data, **kwargs):
    return web.Response(
        body=json.dumps(data, default=json_serial, ensure_ascii=False),
        content_type="application/json",
        headers=CORS_HEADERS,
        **kwargs,
    )


async def publish_notification(event_type, data):
    """Publish notification event to Redis queue."""
    if redis_client:
        payload = json.dumps({"type": event_type, **data}, ensure_ascii=False)
        await redis_client.rpush("notifications", payload)


async def health(request):
    return web.Response(text="deal-service OK")


# ==================== DEALS ====================

async def get_deals_api(request):
    telegram_id = request.query.get('telegram_id')
    status_filter = request.query.get('status')
    if not telegram_id:
        return json_response({'error': 'telegram_id required'}, status=400)
    deals = await database.get_user_deals(int(telegram_id), status_filter)
    return json_response(deals)


async def get_deal_api(request):
    deal_id = request.query.get('deal_id')
    if not deal_id:
        return json_response({'error': 'deal_id required'}, status=400)
    deal = await database.get_deal(int(deal_id))
    if not deal:
        return json_response({'error': 'Deal not found'}, status=404)
    messages = await database.get_deal_messages(int(deal_id))
    deal['messages'] = messages
    return json_response(deal)


async def post_create_deal_api(request):
    data = await request.json()
    buyer_id = data.get("buyer_id")
    offer_id = data.get("offer_id")
    quantity = data.get("quantity", 1)
    if not buyer_id or not offer_id:
        return json_response({"error": "Required: buyer_id, offer_id"}, status=400)
    try:
        buyer_id = int(buyer_id)
        offer_id = int(offer_id)
        quantity = int(quantity)
    except (TypeError, ValueError):
        return json_response({"error": "Invalid types"}, status=400)

    # Get offer from catalog-service
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{CATALOG_SERVICE}/api/offers/{offer_id}") as resp:
            if resp.status != 200:
                return json_response({"error": "Offer not found"}, status=404)
            offer = await resp.json()

    supplier_id = offer['supplier_id']
    price = offer['price']
    deal_id = await database.create_deal(buyer_id, supplier_id, offer_id, quantity, price)

    # Notify supplier via Redis
    try:
        await publish_notification("new_deal", {
            "deal_id": deal_id,
            "supplier_id": supplier_id,
            "buyer_id": buyer_id,
            "model": offer.get('model', ''),
            "memory": offer.get('memory', ''),
            "color": offer.get('color', ''),
            "price": price,
            "quantity": quantity,
        })
    except Exception as e:
        logging.warning("Failed to publish new_deal notification: %s", e)
    return json_response({"ok": True, "deal_id": deal_id})


async def post_deal_status_api(request):
    deal_id = request.match_info.get("id")
    data = await request.json()
    user_id = data.get("user_id")
    new_status = data.get("status")
    if not deal_id or not user_id or not new_status:
        return json_response({"error": "Required: deal_id, user_id, status"}, status=400)
    try:
        deal_id = int(deal_id)
        user_id = int(user_id)
    except (TypeError, ValueError):
        return json_response({"error": "Invalid types"}, status=400)
    deal = await database.get_deal(deal_id)
    if not deal:
        return json_response({"error": "Deal not found"}, status=404)
    if deal['buyer_id'] != user_id and deal['supplier_id'] != user_id and user_id not in ADMIN_IDS:
        return json_response({"error": "Нет прав"}, status=403)
    await database.update_deal_status(deal_id, new_status)

    # Notify via Redis
    await publish_notification("deal_status", {
        "deal_id": deal_id,
        "status": new_status,
        "buyer_id": deal['buyer_id'],
        "supplier_id": deal['supplier_id'],
        "buyer_username": deal.get('buyer_username', ''),
        "supplier_username": deal.get('supplier_username', ''),
        "model": deal.get('model', ''),
        "memory": deal.get('memory', ''),
        "color": deal.get('color', ''),
        "user_id": user_id,
    })
    return json_response({"ok": True})


async def get_admin_deals_api(request):
    admin_id = request.query.get("admin_id")
    try:
        if not admin_id or int(admin_id) not in ADMIN_IDS:
            return json_response({"error": "Нет прав"}, status=403)
    except ValueError:
        return json_response({"error": "Нет прав"}, status=403)
    deals = await database.get_all_deals()
    return json_response(deals)


# ==================== PRICE REQUESTS ====================

async def post_price_request_api(request):
    data = await request.json()
    offer_id = data.get("offer_id")
    buyer_id = data.get("buyer_id")
    quantity = data.get("quantity", 1)
    if not offer_id or not buyer_id:
        return json_response({"error": "Required: offer_id, buyer_id"}, status=400)
    try:
        offer_id = int(offer_id)
        buyer_id = int(buyer_id)
        quantity = int(quantity)
    except (TypeError, ValueError):
        return json_response({"error": "Invalid types"}, status=400)

    async with aiohttp.ClientSession() as session:
        async with session.get(f"{CATALOG_SERVICE}/api/offers/{offer_id}") as resp:
            if resp.status != 200:
                return json_response({"error": "Offer not found"}, status=404)
            offer = await resp.json()

    supplier_id = offer['supplier_id']
    request_id = await database.create_price_request(offer_id, buyer_id, supplier_id, quantity)

    await publish_notification("price_request", {
        "request_id": request_id,
        "supplier_id": supplier_id,
        "buyer_id": buyer_id,
        "model": offer.get('model', ''),
        "memory": offer.get('memory', ''),
        "color": offer.get('color', ''),
        "quantity": quantity,
    })

    # Start 10 min timer
    asyncio.create_task(price_request_timer(request_id, supplier_id, buyer_id))
    return json_response({"ok": True, "id": request_id})


async def price_request_timer(request_id, supplier_id, buyer_id):
    await asyncio.sleep(600)
    req = await database.get_price_request(request_id)
    if req and req['status'] == 'pending':
        await database.expire_price_request(request_id)
        await publish_notification("price_request_expired", {
            "request_id": request_id,
            "supplier_id": supplier_id,
            "buyer_id": buyer_id,
        })


async def get_price_requests_api(request):
    supplier_id = request.query.get("supplier_id")
    if not supplier_id:
        return json_response({"error": "supplier_id required"}, status=400)
    requests_list = await database.get_pending_price_requests(int(supplier_id))
    return json_response(requests_list)


async def get_buyer_price_requests_api(request):
    buyer_id = request.query.get("buyer_id")
    if not buyer_id:
        return json_response({"error": "buyer_id required"}, status=400)
    requests_list = await database.get_buyer_price_requests(int(buyer_id))
    return json_response(requests_list)


async def post_respond_price_request_api(request):
    data = await request.json()
    request_id = data.get("request_id")
    price = data.get("price")
    supplier_id = data.get("supplier_id")
    if not request_id or not price or not supplier_id:
        return json_response({"error": "Required: request_id, price, supplier_id"}, status=400)
    try:
        request_id = int(request_id)
        price = int(price)
        supplier_id = int(supplier_id)
    except (TypeError, ValueError):
        return json_response({"error": "Invalid types"}, status=400)
    req = await database.get_price_request(request_id)
    if not req:
        return json_response({"error": "Request not found"}, status=404)
    if req['supplier_id'] != supplier_id:
        return json_response({"error": "Нет прав"}, status=403)
    if req['status'] != 'pending':
        return json_response({"error": "Запрос уже обработан"}, status=400)
    await database.respond_price_request(request_id, price)

    await publish_notification("price_response", {
        "buyer_id": req['buyer_id'],
        "supplier_id": supplier_id,
        "model": req.get('model', ''),
        "memory": req.get('memory', ''),
        "color": req.get('color', ''),
        "price": price,
    })
    return json_response({"ok": True})


# ==================== PRICE REQUEST ACCEPT/REJECT ====================

async def post_accept_price_request_api(request):
    req_id = request.match_info.get("id")
    try:
        req_id = int(req_id)
    except (TypeError, ValueError):
        return json_response({"error": "Invalid id"}, status=400)
    data = await request.json()
    buyer_id = data.get("buyer_id")
    if not buyer_id:
        return json_response({"error": "buyer_id required"}, status=400)

    req = await database.get_price_request(req_id)
    if not req or req['status'] != 'responded':
        return json_response({"error": "Request not found or not responded"}, status=404)
    if req['buyer_id'] != int(buyer_id):
        return json_response({"error": "Not your request"}, status=403)

    await database.accept_price_request(req_id)

    # Notify supplier with buyer's contact
    try:
        await publish_notification("price_accepted", {
            "supplier_id": req['supplier_id'],
            "buyer_id": req['buyer_id'],
            "buyer_username": req.get('buyer_username', ''),
            "buyer_name": req.get('buyer_name', ''),
            "model": req.get('model', ''),
            "memory": req.get('memory', ''),
            "color": req.get('color', ''),
            "price": req.get('buyer_price', 0),
        })
    except Exception as e:
        logging.warning("Failed to publish price_accepted: %s", e)
    return json_response({"ok": True})


async def post_reject_price_request_api(request):
    req_id = request.match_info.get("id")
    try:
        req_id = int(req_id)
    except (TypeError, ValueError):
        return json_response({"error": "Invalid id"}, status=400)
    data = await request.json()
    buyer_id = data.get("buyer_id")
    if not buyer_id:
        return json_response({"error": "buyer_id required"}, status=400)

    req = await database.get_price_request(req_id)
    if not req or req['status'] != 'responded':
        return json_response({"error": "Request not found or not responded"}, status=404)
    if req['buyer_id'] != int(buyer_id):
        return json_response({"error": "Not your request"}, status=403)

    await database.reject_price_request(req_id)

    try:
        await publish_notification("price_rejected", {
            "supplier_id": req['supplier_id'],
            "model": req.get('model', ''),
            "memory": req.get('memory', ''),
            "color": req.get('color', ''),
            "price": req.get('buyer_price', 0),
        })
    except Exception as e:
        logging.warning("Failed to publish price_rejected: %s", e)
    return json_response({"ok": True})


# ==================== REVIEWS ====================

async def post_add_review_api(request):
    data = await request.json()
    deal_id = data.get("deal_id")
    supplier_id = data.get("supplier_id")
    buyer_id = data.get("buyer_id")
    rating = data.get("rating")
    comment = data.get("comment")
    author_role = data.get("author_role", "buyer")
    if not all([deal_id, supplier_id, buyer_id, rating]):
        return json_response({"error": "Required: deal_id, supplier_id, buyer_id, rating"}, status=400)
    if author_role not in ('buyer', 'supplier'):
        return json_response({"error": "author_role must be buyer or supplier"}, status=400)
    try:
        await database.add_review(int(deal_id), int(supplier_id), int(buyer_id), int(rating), comment, author_role)
    except Exception as e:
        return json_response({"error": str(e)}, status=500)
    return json_response({"ok": True})


async def get_admin_reviews_api(request):
    admin_id = request.query.get("admin_id")
    try:
        if not admin_id or int(admin_id) not in ADMIN_IDS:
            return json_response({"error": "Нет прав"}, status=403)
    except ValueError:
        return json_response({"error": "Нет прав"}, status=403)
    reviews = await database.get_all_reviews()
    return json_response(reviews)


async def delete_review_api(request):
    admin_id = request.query.get("admin_id")
    try:
        if not admin_id or int(admin_id) not in ADMIN_IDS:
            return json_response({"error": "Нет прав"}, status=403)
    except ValueError:
        return json_response({"error": "Нет прав"}, status=403)
    review_id = int(request.match_info['id'])
    result = await database.delete_review(review_id)
    if not result:
        return json_response({"error": "Отзыв не найден"}, status=404)
    return json_response({"ok": True})


async def post_reply_review_api(request):
    review_id = int(request.match_info['id'])
    data = await request.json()
    user_id = data.get("user_id")
    reply_text = (data.get("reply_text") or "").strip()
    if not user_id or not reply_text:
        return json_response({"error": "user_id and reply_text required"}, status=400)
    try:
        await database.reply_to_review(review_id, reply_text)
    except Exception as e:
        return json_response({"error": str(e)}, status=500)
    return json_response({"ok": True})


async def get_user_reviews_api(request):
    telegram_id = request.query.get("telegram_id")
    if not telegram_id:
        return json_response({"error": "telegram_id required"}, status=400)
    reviews = await database.get_user_reviews(int(telegram_id))
    return json_response(reviews)


# ==================== BUYER REQUESTS ====================

async def get_buyer_requests_api(request):
    items = await database.get_open_buyer_requests()
    return json_response(items)


async def get_my_buyer_requests_api(request):
    buyer_id = request.query.get('buyer_id')
    if not buyer_id:
        return json_response({"error": "buyer_id required"}, status=400)
    items = await database.get_my_buyer_requests(int(buyer_id))
    return json_response(items)


async def post_buyer_request_api(request):
    data = await request.json()
    buyer_id = data.get("buyer_id")
    model = (data.get("model") or "").strip()
    if not buyer_id or not model:
        return json_response({"error": "Required: buyer_id, model"}, status=400)
    try:
        buyer_id = int(buyer_id)
    except (TypeError, ValueError):
        return json_response({"error": "Invalid buyer_id"}, status=400)

    memory = (data.get("memory") or "").strip()
    color = (data.get("color") or "").strip()
    quantity = int(data.get("quantity") or 1)
    max_price = int(data["max_price"]) if data.get("max_price") else None
    comment = (data.get("comment") or "").strip() or None

    req_id = await database.create_buyer_request(buyer_id, model, memory, color, quantity, max_price, comment)

    # Notify suppliers who have this product in stock
    try:
        item = f"{model}{(' ' + memory) if memory else ''}{(' ' + color) if color else ''}"
        text = f"🛒 Новый запрос от покупателя\n\n📱 {item}\nКол-во: {quantity} шт"
        if comment:
            text += f"\n💬 {comment}"
        # Get suppliers with matching offers
        params = f"model={model}"
        if memory:
            params += f"&memory={memory}"
        if color:
            params += f"&color={color}"
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{CATALOG_SERVICE}/internal/suppliers_by_model?{params}") as resp:
                supplier_ids = await resp.json() if resp.status == 200 else []
        await publish_notification("buyer_request", {"text": text, "supplier_ids": supplier_ids})
    except Exception as e:
        logging.warning("Failed to publish buyer_request notification: %s", e)
    return json_response({"ok": True, "id": req_id})


async def get_buyer_request_responses_api(request):
    req_id = request.match_info.get("id")
    try:
        req_id = int(req_id)
    except (TypeError, ValueError):
        return json_response({"error": "Invalid id"}, status=400)
    items = await database.get_buyer_request_responses(req_id)
    return json_response(items)


async def post_buyer_request_respond_api(request):
    req_id = request.match_info.get("id")
    try:
        req_id = int(req_id)
    except (TypeError, ValueError):
        return json_response({"error": "Invalid id"}, status=400)
    data = await request.json()
    supplier_id = data.get("supplier_id")
    price = data.get("price")
    if not supplier_id or not price:
        return json_response({"error": "Required: supplier_id, price"}, status=400)
    try:
        supplier_id = int(supplier_id)
        price = int(price)
    except (TypeError, ValueError):
        return json_response({"error": "Invalid types"}, status=400)
    await database.create_buyer_request_response(
        request_id=req_id, supplier_id=supplier_id, price=price,
        comment=(data.get("comment") or "").strip() or None,
    )
    # Notify buyer
    br = await database.get_buyer_request_by_id(req_id)
    if br:
        item = f"{br['model']}{(' ' + br['memory']) if br.get('memory') else ''}{(' ' + br['color']) if br.get('color') else ''}"
        await publish_notification("buyer_request_response", {
            "buyer_id": br['buyer_id'],
            "supplier_id": supplier_id,
            "item": item,
            "price": price,
        })
    return json_response({"ok": True})


async def post_buyer_request_close_api(request):
    req_id = request.match_info.get("id")
    try:
        req_id = int(req_id)
    except (TypeError, ValueError):
        return json_response({"error": "Invalid id"}, status=400)
    data = await request.json()
    buyer_id = data.get("buyer_id")
    if not buyer_id:
        return json_response({"error": "buyer_id required"}, status=400)
    await database.close_buyer_request(req_id, int(buyer_id))
    return json_response({"ok": True})


# ==================== BUYER REQUEST RESPONSE ACCEPT/REJECT ====================

async def post_accept_buyer_response_api(request):
    resp_id = request.match_info.get("resp_id")
    try:
        resp_id = int(resp_id)
    except (TypeError, ValueError):
        return json_response({"error": "Invalid id"}, status=400)
    data = await request.json()
    buyer_id = data.get("buyer_id")
    if not buyer_id:
        return json_response({"error": "buyer_id required"}, status=400)

    resp = await database.get_buyer_request_response_by_id(resp_id)
    if not resp:
        return json_response({"error": "Response not found"}, status=404)
    if resp['buyer_id'] != int(buyer_id):
        return json_response({"error": "Not your request"}, status=403)

    await database.accept_buyer_request_response(resp_id)

    try:
        await publish_notification("buyer_response_accepted", {
            "supplier_id": resp['supplier_id'],
            "buyer_id": resp['buyer_id'],
            "buyer_username": resp.get('buyer_username', ''),
            "buyer_name": resp.get('buyer_name', ''),
            "model": resp.get('model', ''),
            "memory": resp.get('memory', ''),
            "color": resp.get('color', ''),
            "price": resp['price'],
        })
        await publish_notification("buyer_response_accepted_buyer", {
            "buyer_id": resp['buyer_id'],
            "supplier_id": resp['supplier_id'],
            "supplier_username": resp.get('supplier_username', ''),
            "supplier_name": resp.get('supplier_name', ''),
            "supplier_company": resp.get('supplier_company', ''),
            "model": resp.get('model', ''),
            "memory": resp.get('memory', ''),
            "color": resp.get('color', ''),
            "price": resp['price'],
        })
    except Exception as e:
        logging.warning("Failed to publish buyer_response_accepted: %s", e)
    return json_response({"ok": True})


async def post_reject_buyer_response_api(request):
    resp_id = request.match_info.get("resp_id")
    try:
        resp_id = int(resp_id)
    except (TypeError, ValueError):
        return json_response({"error": "Invalid id"}, status=400)
    data = await request.json()
    buyer_id = data.get("buyer_id")
    if not buyer_id:
        return json_response({"error": "buyer_id required"}, status=400)

    resp = await database.get_buyer_request_response_by_id(resp_id)
    if not resp:
        return json_response({"error": "Response not found"}, status=404)
    if resp['buyer_id'] != int(buyer_id):
        return json_response({"error": "Not your request"}, status=403)

    await database.reject_buyer_request_response(resp_id)

    try:
        await publish_notification("buyer_response_rejected", {
            "supplier_id": resp['supplier_id'],
            "model": resp.get('model', ''),
            "memory": resp.get('memory', ''),
            "color": resp.get('color', ''),
            "price": resp['price'],
        })
    except Exception as e:
        logging.warning("Failed to publish buyer_response_rejected: %s", e)
    return json_response({"ok": True})


# ==================== APP ====================

async def on_startup(app):
    global redis_client
    redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    await database.init_db()
    logging.info("deal-service: DB and Redis initialized")


async def on_cleanup(app):
    await database.close_db()
    if redis_client:
        await redis_client.close()


def create_app():
    @web.middleware
    async def cors_middleware(request, handler):
        if request.method == "OPTIONS":
            return web.Response(headers=CORS_HEADERS)
        try:
            resp = await handler(request)
        except Exception as e:
            logging.exception("Unhandled error in %s %s", request.method, request.path)
            resp = web.Response(
                body=json.dumps({"error": str(e)}, ensure_ascii=False),
                content_type="application/json",
                status=500,
            )
        resp.headers.update(CORS_HEADERS)
        return resp

    app = web.Application(middlewares=[cors_middleware])
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)

    app.router.add_get("/health", health)
    # Deals
    app.router.add_get("/api/deals", get_deals_api)
    app.router.add_get("/api/deal", get_deal_api)
    app.router.add_post("/api/deals", post_create_deal_api)
    app.router.add_post("/api/deals/{id}/status", post_deal_status_api)
    app.router.add_get("/api/admin/deals", get_admin_deals_api)
    # Price requests
    app.router.add_post("/api/price_request", post_price_request_api)
    app.router.add_get("/api/price_requests", get_price_requests_api)
    app.router.add_get("/api/buyer/price_requests", get_buyer_price_requests_api)
    app.router.add_post("/api/price_request/respond", post_respond_price_request_api)
    app.router.add_post("/api/price_request/{id}/accept", post_accept_price_request_api)
    app.router.add_post("/api/price_request/{id}/reject", post_reject_price_request_api)
    # Reviews
    app.router.add_post("/api/reviews", post_add_review_api)
    app.router.add_post("/api/reviews/{id}/reply", post_reply_review_api)
    app.router.add_get("/api/user/reviews", get_user_reviews_api)
    app.router.add_get("/api/admin/reviews", get_admin_reviews_api)
    app.router.add_delete("/api/admin/reviews/{id}", delete_review_api)
    # Buyer requests
    app.router.add_get("/api/buyer_requests", get_buyer_requests_api)
    app.router.add_get("/api/buyer_requests/my", get_my_buyer_requests_api)
    app.router.add_post("/api/buyer_requests", post_buyer_request_api)
    app.router.add_get("/api/buyer_requests/{id}/responses", get_buyer_request_responses_api)
    app.router.add_post("/api/buyer_requests/{id}/respond", post_buyer_request_respond_api)
    app.router.add_post("/api/buyer_requests/{id}/close", post_buyer_request_close_api)
    app.router.add_post("/api/buyer_requests/response/{resp_id}/accept", post_accept_buyer_response_api)
    app.router.add_post("/api/buyer_requests/response/{resp_id}/reject", post_reject_buyer_response_api)

    return app


if __name__ == "__main__":
    port = int(os.environ.get("DEAL_SERVICE_PORT", 8083))
    web.run_app(create_app(), host="0.0.0.0", port=port)
