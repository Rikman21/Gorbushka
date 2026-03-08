import os
import logging
import json
from aiohttp import web
import database

logging.basicConfig(level=logging.INFO)

ADMIN_IDS = [int(x) for x in os.environ.get("ADMIN_IDS", "").split(",") if x.strip()]

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, DELETE, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
}


def json_serial(obj):
    """Сериализация datetime для JSON."""
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


# ==================== ENDPOINTS ====================

async def health(request):
    return web.Response(text="user-service OK")


async def get_user_api(request):
    telegram_id = request.query.get('telegram_id')
    if not telegram_id:
        return json_response({'error': 'telegram_id required'}, status=400)
    user = await database.get_user(int(telegram_id))
    return json_response(user or {})


async def post_user_api(request):
    data = await request.json()
    telegram_id = data.get("telegram_id")
    if not telegram_id:
        return json_response({"error": "telegram_id required"}, status=400)
    await database.create_or_update_user(
        int(telegram_id),
        data.get("username"),
        data.get("full_name"),
    )
    return json_response({"ok": True})


async def post_user_role_api(request):
    data = await request.json()
    telegram_id = data.get("telegram_id")
    role = data.get("role")
    if not telegram_id or role not in ("buyer", "supplier"):
        return json_response({"error": "Required: telegram_id, role (buyer|supplier)"}, status=400)
    telegram_id = int(telegram_id)
    if telegram_id not in ADMIN_IDS:
        user = await database.get_user(telegram_id)
        if user and user.get("role_selected"):
            return json_response({"error": "Роль уже выбрана."}, status=403)
    await database.set_user_role(telegram_id, role)
    return json_response({"ok": True})


async def post_notifications_toggle_api(request):
    data = await request.json()
    telegram_id = data.get("telegram_id")
    enabled = data.get("enabled")
    if telegram_id is None or enabled is None:
        return json_response({"error": "Required: telegram_id, enabled"}, status=400)
    await database.set_notifications_enabled(int(telegram_id), bool(enabled))
    return json_response({"ok": True})


async def post_become_supplier_api(request):
    data = await request.json()
    telegram_id = data.get("telegram_id")
    company_name = (data.get("company_name") or "").strip()
    city = (data.get("city") or "").strip()
    phone = (data.get("phone") or "").strip()
    if not telegram_id or not company_name or not city or not phone:
        return json_response({"error": "Required: telegram_id, company_name, city, phone"}, status=400)
    await database.create_supplier_request(int(telegram_id), company_name, city, phone)
    return json_response({"ok": True, "message": "Заявка отправлена"})


async def get_supplier_profile_api(request):
    supplier_id = request.query.get('supplier_id')
    if not supplier_id:
        return json_response({'error': 'supplier_id required'}, status=400)
    supplier_id = int(supplier_id)
    user = await database.get_user(supplier_id)
    if not user:
        return json_response({'error': 'Supplier not found'}, status=404)
    reviews = await database.get_supplier_reviews(supplier_id)
    user['reviews'] = reviews
    return json_response(user)


async def get_supplier_stats_api(request):
    telegram_id = request.query.get("telegram_id")
    if not telegram_id:
        return json_response({"error": "telegram_id required"}, status=400)
    stats = await database.get_supplier_stats(int(telegram_id))
    return json_response(stats)


async def get_admin_users_api(request):
    admin_id = request.query.get("admin_id")
    try:
        if not admin_id or int(admin_id) not in ADMIN_IDS:
            return json_response({"error": "Нет прав"}, status=403)
    except ValueError:
        return json_response({"error": "Нет прав"}, status=403)
    users = await database.get_all_users()
    return json_response(users)


async def post_admin_user_role_api(request):
    data = await request.json()
    try:
        admin_id = int(data.get("admin_id", 0))
    except (TypeError, ValueError):
        admin_id = 0
    if admin_id not in ADMIN_IDS:
        return json_response({"error": "Нет прав"}, status=403)
    telegram_id = data.get("telegram_id")
    role = data.get("role")
    if not telegram_id or role not in ("buyer", "supplier"):
        return json_response({"error": "Required: telegram_id, role"}, status=400)
    await database.set_user_role(int(telegram_id), role)
    return json_response({"ok": True})


async def delete_admin_user_api(request):
    user_id = request.match_info.get("id")
    admin_id = request.query.get("admin_id")
    try:
        if not admin_id or int(admin_id) not in ADMIN_IDS:
            return json_response({"error": "Нет прав"}, status=403)
        if not user_id:
            return json_response({"error": "id required"}, status=400)
        await database.delete_user(int(user_id))
    except ValueError:
        return json_response({"error": "Нет прав"}, status=403)
    return json_response({"ok": True})


async def get_admin_supplier_requests_api(request):
    admin_id = request.query.get("admin_id")
    try:
        if not admin_id or int(admin_id) not in ADMIN_IDS:
            return json_response({"error": "Нет прав"}, status=403)
    except ValueError:
        return json_response({"error": "Нет прав"}, status=403)
    rows = await database.get_admin_supplier_requests()
    return json_response(rows)


# Internal API for other services
async def get_suppliers_with_notifications_api(request):
    ids = await database.get_suppliers_with_notifications()
    return json_response(ids)


async def internal_approve_supplier(request):
    data = await request.json()
    telegram_id = data.get("telegram_id")
    result = await database.approve_supplier_request(int(telegram_id))
    return json_response({"ok": result})


async def internal_reject_supplier(request):
    data = await request.json()
    telegram_id = data.get("telegram_id")
    result = await database.reject_supplier_request(int(telegram_id))
    return json_response({"ok": result})


# ==================== APP ====================

async def on_startup(app):
    await database.init_db()
    logging.info("user-service: DB initialized")


async def on_cleanup(app):
    await database.close_db()


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
    # Public API
    app.router.add_get("/api/user", get_user_api)
    app.router.add_post("/api/user", post_user_api)
    app.router.add_post("/api/user/role", post_user_role_api)
    app.router.add_post("/api/user/notifications", post_notifications_toggle_api)
    app.router.add_post("/api/become_supplier", post_become_supplier_api)
    app.router.add_get("/api/supplier", get_supplier_profile_api)
    app.router.add_get("/api/supplier/stats", get_supplier_stats_api)
    # Admin
    app.router.add_get("/api/admin/users", get_admin_users_api)
    app.router.add_post("/api/admin/user/role", post_admin_user_role_api)
    app.router.add_delete("/api/admin/user/{id}", delete_admin_user_api)
    app.router.add_get("/api/admin/supplier_requests", get_admin_supplier_requests_api)
    # Internal (service-to-service)
    app.router.add_get("/internal/suppliers_with_notifications", get_suppliers_with_notifications_api)
    app.router.add_post("/internal/approve_supplier", internal_approve_supplier)
    app.router.add_post("/internal/reject_supplier", internal_reject_supplier)

    return app


if __name__ == "__main__":
    port = int(os.environ.get("USER_SERVICE_PORT", 8081))
    web.run_app(create_app(), host="0.0.0.0", port=port)
