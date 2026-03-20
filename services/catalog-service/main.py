import os
import logging
import json
from io import BytesIO
from aiohttp import web
import pandas as pd
import database

logging.basicConfig(level=logging.INFO)

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, PUT, PATCH, DELETE, OPTIONS",
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


async def health(request):
    return web.Response(text="catalog-service OK")


async def get_catalog_api(request):
    filters = {}
    if request.query.get('category'):
        filters['category'] = request.query.get('category')
    if request.query.get('model'):
        filters['model'] = request.query.get('model')
    if request.query.get('memory'):
        filters['memory'] = request.query.get('memory')
    viewer_id = None
    try:
        if request.query.get('viewer_id'):
            viewer_id = int(request.query.get('viewer_id'))
    except ValueError:
        pass
    if request.query.get('all') == '1':
        catalog = await database.get_catalog(filters)
        for item in catalog:
            item.setdefault('min_price', None)
            item.setdefault('max_price', None)
            item.setdefault('offers_count', 0)
    else:
        catalog = await database.get_catalog_with_offers(filters, viewer_id=viewer_id)
    return json_response(catalog)


async def get_catalog_offers_api(request):
    catalog_id = request.match_info.get("id")
    if not catalog_id:
        return json_response({"error": "id required"}, status=400)
    try:
        catalog_id = int(catalog_id)
    except ValueError:
        return json_response({"error": "Invalid id"}, status=400)
    offers = await database.get_catalog_offers(catalog_id)
    return json_response(offers)


async def get_offers_api(request):
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
    offers = await database.get_offers(filters)
    return json_response(offers)


async def get_offer_by_id_api(request):
    offer_id = request.match_info.get("id")
    if not offer_id:
        return json_response({"error": "id required"}, status=400)
    try:
        offer_id = int(offer_id)
    except ValueError:
        return json_response({"error": "Invalid id"}, status=400)
    offer = await database.get_offer_by_id(offer_id)
    if not offer:
        return json_response({"error": "Offer not found"}, status=404)
    return json_response(offer)


async def get_supplier_offers_api(request):
    telegram_id = request.query.get("telegram_id")
    if not telegram_id:
        return json_response({"error": "telegram_id required"}, status=400)
    try:
        offers = await database.get_supplier_offers(int(telegram_id))
    except ValueError:
        return json_response({"error": "Invalid telegram_id"}, status=400)
    return json_response(offers)


async def post_supplier_offers_api(request):
    try:
        data = await request.json()
    except Exception as e:
        return json_response({"ok": False, "error": "Invalid JSON: " + str(e)}, status=400)
    telegram_id = data.get("telegram_id")
    product_id = data.get("product_id")
    price = data.get("price")
    quantity = data.get("quantity")
    if telegram_id is None or price is None:
        return json_response({"ok": False, "error": "Required: telegram_id, price"}, status=400)
    try:
        telegram_id = int(telegram_id)
        price = int(price)
        quantity = int(quantity) if quantity is not None else 0
    except (TypeError, ValueError) as e:
        return json_response({"ok": False, "error": "telegram_id, price must be numbers"}, status=400)

    if product_id is not None:
        try:
            catalog_id = int(product_id)
        except (TypeError, ValueError):
            return json_response({"ok": False, "error": "product_id must be a number"}, status=400)
    else:
        model = (data.get("model") or "").strip()
        memory = (data.get("memory") or "").strip()
        color = (data.get("color") or "").strip()
        if not model:
            return json_response({"ok": False, "error": "Required: product_id or model"}, status=400)
        catalog_id = await database.find_catalog_by_brand_model_memory_color("Apple", model, memory, color)
        if not catalog_id:
            ok, msg = await database.add_catalog_item(
                "iPhone" if "iPhone" in model else "Apple", "Apple", model, memory, color,
                f"{model}-{memory}-{color}".upper().replace(" ", "-")[:80]
            )
            if ok:
                catalog_id = await database.find_catalog_by_brand_model_memory_color("Apple", model, memory, color)
        if not catalog_id:
            return json_response({"ok": False, "error": f"Товар '{model}' не найден"}, status=404)

    if price < 0:
        return json_response({"ok": False, "error": "price must be >= 0"}, status=400)
    if quantity < 0:
        quantity = 0
    comment = (data.get("comment") or "").strip() or None
    condition = data.get("condition") or "new"
    try:
        offer_id = await database.create_offer(
            supplier_id=telegram_id, catalog_id=catalog_id, price=price,
            quantity=quantity, moq=1, condition=condition,
            delivery_days=0, warranty_months=12, comment=comment,
        )
    except Exception as e:
        logging.exception("post_supplier_offers")
        return json_response({"ok": False, "error": str(e)}, status=500)
    return json_response({"ok": True, "id": offer_id})


async def delete_supplier_offer_api(request):
    offer_id = request.match_info.get("id")
    telegram_id = request.query.get("telegram_id")
    if not offer_id or not telegram_id:
        return json_response({"error": "id and telegram_id required"}, status=400)
    try:
        offer_id = int(offer_id)
        telegram_id = int(telegram_id)
    except ValueError:
        return json_response({"error": "id and telegram_id must be numbers"}, status=400)
    if not await database.delete_offer(offer_id, telegram_id):
        return json_response({"error": "Offer not found or access denied"}, status=404)
    return json_response({"ok": True})


async def patch_supplier_offer_api(request):
    offer_id = request.match_info.get("id")
    data = await request.json()
    telegram_id = data.get("telegram_id")
    if not offer_id or not telegram_id:
        return json_response({"error": "Required: offer_id, telegram_id"}, status=400)
    try:
        offer_id = int(offer_id)
        telegram_id = int(telegram_id)
    except (TypeError, ValueError):
        return json_response({"error": "Invalid types"}, status=400)
    async with database.pool.acquire() as conn:
        row = await conn.fetchrow(
            'SELECT id FROM offers WHERE id = $1 AND supplier_id = $2', offer_id, telegram_id
        )
    if not row:
        return json_response({"error": "Offer not found or access denied"}, status=404)
    updates = {}
    for field in ['price', 'quantity']:
        if field in data and data[field] is not None:
            updates[field] = int(data[field])
    if not updates:
        return json_response({"error": "Nothing to update"}, status=400)
    await database.update_offer(offer_id, **updates)
    return json_response({"ok": True})


async def post_toggle_price_api(request):
    offer_id = request.match_info.get("id")
    data = await request.json()
    telegram_id = data.get("telegram_id")
    if not offer_id or not telegram_id:
        return json_response({"error": "Required: offer_id, telegram_id"}, status=400)
    try:
        offer_id = int(offer_id)
        telegram_id = int(telegram_id)
    except (TypeError, ValueError):
        return json_response({"error": "Invalid types"}, status=400)
    async with database.pool.acquire() as conn:
        row = await conn.fetchrow(
            'SELECT price_hidden FROM offers WHERE id = $1 AND supplier_id = $2', offer_id, telegram_id
        )
    if not row:
        return json_response({"error": "Offer not found"}, status=404)
    new_hidden = 0 if row['price_hidden'] else 1
    await database.update_offer(offer_id, price_hidden=new_hidden)
    return json_response({"ok": True, "price_hidden": new_hidden})


ADMIN_IDS = [int(x) for x in os.environ.get("ADMIN_IDS", "").split(",") if x.strip()]


async def get_admin_catalog_api(request):
    admin_id = request.query.get("admin_id")
    try:
        if not admin_id or int(admin_id) not in ADMIN_IDS:
            return json_response({"error": "Нет прав"}, status=403)
    except ValueError:
        return json_response({"error": "Нет прав"}, status=403)
    items = await database.get_all_catalog_items()
    return json_response(items)


async def post_admin_catalog_api(request):
    data = await request.json()
    admin_id = data.get("admin_id")
    try:
        if not admin_id or int(admin_id) not in ADMIN_IDS:
            return json_response({"error": "Нет прав"}, status=403)
    except (TypeError, ValueError):
        return json_response({"error": "Нет прав"}, status=403)
    category = (data.get("category") or "").strip()
    brand = (data.get("brand") or "Apple").strip()
    model = (data.get("model") or "").strip()
    memory = (data.get("memory") or "").strip()
    color = (data.get("color") or "").strip()
    if not category or not model:
        return json_response({"error": "Required: category, model"}, status=400)
    sku = f"{model}-{memory}-{color}".upper().replace(" ", "-")[:80]
    ok, msg = await database.add_catalog_item(category, brand, model, memory, color, sku)
    if not ok:
        return json_response({"error": msg}, status=409)
    return json_response({"ok": True, "message": msg})


async def delete_admin_catalog_api(request):
    item_id = request.match_info.get("id")
    admin_id = request.query.get("admin_id")
    try:
        if not admin_id or int(admin_id) not in ADMIN_IDS:
            return json_response({"error": "Нет прав"}, status=403)
        item_id = int(item_id)
    except (TypeError, ValueError):
        return json_response({"error": "Нет прав"}, status=403)
    ok, msg = await database.delete_catalog_item(item_id)
    if not ok:
        return json_response({"error": msg}, status=400)
    return json_response({"ok": True})


async def patch_admin_catalog_toggle_api(request):
    item_id = request.match_info.get("id")
    data = await request.json()
    admin_id = data.get("admin_id")
    try:
        if not admin_id or int(admin_id) not in ADMIN_IDS:
            return json_response({"error": "Нет прав"}, status=403)
        item_id = int(item_id)
    except (TypeError, ValueError):
        return json_response({"error": "Нет прав"}, status=403)
    await database.toggle_catalog_item(item_id)
    return json_response({"ok": True})


async def get_supplier_template_api(request):
    rows = await database.get_catalog_all_for_template()
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
            return json_response({"success": False, "error": "Required: telegram_id and file"}, status=400)
        telegram_id = int(telegram_id)
    except (ValueError, Exception) as e:
        return json_response({"success": False, "error": str(e)}, status=400)

    try:
        df = pd.read_excel(BytesIO(file_data), engine="openpyxl")
    except Exception as e:
        return json_response({"success": False, "error": "Файл не читается: " + str(e)}, status=400)

    errors = 0
    try:
        raw_columns = list(df.columns)
        cols_lower = {str(c).strip().lower(): c for c in raw_columns}
        brand_col = cols_lower.get("brand")
        model_col = cols_lower.get("model")
        memory_col = cols_lower.get("memory")
        color_col = cols_lower.get("color")
        price_col = cols_lower.get("price")
        quantity_col = cols_lower.get("quantity")

        if not all([brand_col is not None, model_col is not None, memory_col is not None, color_col is not None, price_col is not None]):
            return json_response({"success": False, "error": "В файле должны быть колонки: Brand, Model, Memory, Color, Price"}, status=400)

        rows_to_import = []
        for _, row in df.iterrows():
            try:
                model = row.get(model_col)
                memory = row.get(memory_col)
                color = row.get(color_col)
                price_val = row.get(price_col)
                qty_val = row.get(quantity_col) if quantity_col is not None else 0
            except Exception:
                errors += 1
                continue
            if pd.isna(model) and pd.isna(memory) and pd.isna(color):
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

        success, batch_errors = await database.import_offers_batch(telegram_id, rows_to_import)
        errors += batch_errors
    except Exception as e:
        logging.exception("supplier_import")
        return json_response({"success": False, "error": str(e)}, status=500)

    return json_response({"success": True, "success_count": success, "errors": errors,
                          "message": f"Импортировано: {success}, ошибок: {errors}"})


# ==================== APP ====================

async def on_startup(app):
    await database.init_db()
    logging.info("catalog-service: DB initialized")


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
    app.router.add_get("/api/catalog", get_catalog_api)
    app.router.add_get("/api/catalog/{id}/offers", get_catalog_offers_api)
    app.router.add_get("/api/offers", get_offers_api)
    app.router.add_get("/api/offers/{id}", get_offer_by_id_api)
    app.router.add_get("/api/supplier/offers", get_supplier_offers_api)
    app.router.add_post("/api/supplier/offers", post_supplier_offers_api)
    app.router.add_delete("/api/supplier/offers/{id}", delete_supplier_offer_api)
    app.router.add_patch("/api/supplier/offers/{id}", patch_supplier_offer_api)
    app.router.add_post("/api/supplier/offers/{id}/toggle_price", post_toggle_price_api)
    app.router.add_get("/api/admin/catalog", get_admin_catalog_api)
    app.router.add_post("/api/admin/catalog", post_admin_catalog_api)
    app.router.add_delete("/api/admin/catalog/{id}", delete_admin_catalog_api)
    app.router.add_patch("/api/admin/catalog/{id}/toggle", patch_admin_catalog_toggle_api)
    app.router.add_get("/api/supplier/template", get_supplier_template_api)
    app.router.add_post("/api/supplier/import", post_supplier_import_api)

    return app


if __name__ == "__main__":
    port = int(os.environ.get("CATALOG_SERVICE_PORT", 8082))
    web.run_app(create_app(), host="0.0.0.0", port=port)
