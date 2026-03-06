"""
Автоматическое тестирование всех API-эндпоинтов бота.
Запуск: python test_api.py
Запуск с другим адресом: python test_api.py http://45.131.43.120:8080
"""
import sys
import json
import time
import urllib.request
import urllib.error

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8080"

BUYER_ID  = 999001   # тестовый покупатель
SUPPLIER_ID = 999002  # тестовый поставщик
ADMIN_ID  = 464896073

passed = 0
failed = 0
results = []


def req(method, path, body=None, expect_status=200):
    url = BASE + path
    data = json.dumps(body).encode() if body else None
    headers = {"Content-Type": "application/json"}
    rq = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(rq, timeout=10) as resp:
            status = resp.status
            text = resp.read().decode()
            try:
                return status, json.loads(text)
            except Exception:
                return status, text
    except urllib.error.HTTPError as e:
        text = e.read().decode()
        try:
            return e.code, json.loads(text)
        except Exception:
            return e.code, text
    except Exception as ex:
        return 0, str(ex)


def check(name, ok, detail=""):
    global passed, failed
    icon = "OK" if ok else "FAIL"
    msg = f"  [{icon}] {name}"
    if not ok and detail:
        msg += f"\n       -> {detail}"
    results.append((ok, name, detail))
    if ok:
        passed += 1
    else:
        failed += 1
    print(msg)


def test(name, method, path, body=None, expect_status=200, expect_key=None, expect_value=None):
    status, resp = req(method, path, body, expect_status)
    ok = (status == expect_status)
    detail = f"status={status}, body={str(resp)[:200]}"
    if ok and expect_key:
        if isinstance(resp, dict):
            ok = resp.get(expect_key) == expect_value if expect_value is not None else expect_key in resp
        elif isinstance(resp, list):
            ok = True  # list response, key check skipped
    check(name, ok, detail if not ok else "")
    return resp if status == expect_status else None


# ─────────────────────────────────────────
print(f"\n=== API TESTS  {BASE} ===\n")

# 1. Health
print("[ HEALTH ]")
test("GET /health", "GET", "/health", expect_status=200)

# 2. Каталог
print("\n[ CATALOG ]")
catalog = test("GET /api/catalog (с офферами)", "GET", "/api/catalog", expect_status=200)
check("Catalog возвращает список", isinstance(catalog, list), str(type(catalog)))

all_cat = test("GET /api/catalog?all=1 (все товары)", "GET", "/api/catalog?all=1", expect_status=200)
check("Catalog?all=1 не пустой", isinstance(all_cat, list) and len(all_cat) > 0,
      f"len={len(all_cat) if isinstance(all_cat, list) else 'N/A'}")

if isinstance(all_cat, list) and all_cat:
    first = all_cat[0]
    check("Catalog item has model field", "model" in first, str(first))
    CATALOG_ID = first["id"]
    CATALOG_MODEL = first.get("model", "")
    CATALOG_MEMORY = first.get("memory", "")
    CATALOG_COLOR  = first.get("color", "")
else:
    CATALOG_ID = None
    CATALOG_MODEL = "iPhone 16"
    CATALOG_MEMORY = "128GB"
    CATALOG_COLOR  = "Black"

# Offers for catalog item
if CATALOG_ID:
    test(f"GET /api/catalog/{CATALOG_ID}/offers", "GET", f"/api/catalog/{CATALOG_ID}/offers", expect_status=200)

# 3. Пользователи
print("\n[ USERS ]")
test("GET /api/user?telegram_id=BUYER", "GET", f"/api/user?telegram_id={BUYER_ID}", expect_status=200)
test("POST /api/user/role (buyer)", "POST", "/api/user/role",
     body={"telegram_id": BUYER_ID, "role": "buyer"}, expect_status=200)
test("POST /api/user/role (supplier)", "POST", "/api/user/role",
     body={"telegram_id": SUPPLIER_ID, "role": "supplier"}, expect_status=200)

# 4. Офферы поставщика
print("\n[ SUPPLIER OFFERS ]")
# Создать оффер через model/memory/color
new_offer = test("POST /api/supplier/offers (model+color)", "POST", "/api/supplier/offers",
    body={
        "telegram_id": SUPPLIER_ID,
        "model": CATALOG_MODEL,
        "memory": CATALOG_MEMORY,
        "color": CATALOG_COLOR,
        "price": 99900,
        "quantity": 10,
        "condition": "new",
        "comment": "test offer"
    }, expect_status=200)
offer_id = None
if isinstance(new_offer, dict) and new_offer.get("ok"):
    offer_id = new_offer.get("offer_id")
    check("Оффер создан, offer_id получен", offer_id is not None, str(new_offer))
elif isinstance(new_offer, dict):
    check("Оффер создан", False, str(new_offer))

# Список офферов поставщика
supplier_offers = test("GET /api/supplier/offers", "GET", f"/api/supplier/offers?telegram_id={SUPPLIER_ID}", expect_status=200)
check("Список офферов поставщика", isinstance(supplier_offers, list), str(type(supplier_offers)))
if isinstance(supplier_offers, list) and supplier_offers and not offer_id:
    offer_id = supplier_offers[-1]["id"]

# Toggle price hide
if offer_id:
    test("POST toggle_price", "POST", f"/api/supplier/offers/{offer_id}/toggle_price",
         body={"telegram_id": SUPPLIER_ID}, expect_status=200)
    test("POST toggle_price (обратно)", "POST", f"/api/supplier/offers/{offer_id}/toggle_price",
         body={"telegram_id": SUPPLIER_ID}, expect_status=200)

# 5. Офферы (публичный список)
print("\n[ PUBLIC OFFERS ]")
test("GET /api/offers", "GET", "/api/offers", expect_status=200)
if offer_id:
    test(f"GET /api/offers/{offer_id}", "GET", f"/api/offers/{offer_id}", expect_status=200)

# 6. Запросы цены
print("\n[ PRICE REQUESTS ]")
price_req = None
if offer_id:
    price_req = test("POST /api/price_request", "POST", "/api/price_request",
        body={"offer_id": offer_id, "buyer_id": BUYER_ID, "quantity": 2}, expect_status=200)

req_id = None
if isinstance(price_req, dict) and price_req.get("ok"):
    req_id = price_req.get("request_id")
    check("Price request создан", req_id is not None, str(price_req))

test("GET /api/price_requests (supplier)", "GET", f"/api/price_requests?supplier_id={SUPPLIER_ID}", expect_status=200)
test("GET /api/buyer/price_requests", "GET", f"/api/buyer/price_requests?buyer_id={BUYER_ID}", expect_status=200)

# Ответ поставщика на запрос
if req_id:
    test("POST /api/price_request/respond", "POST", "/api/price_request/respond",
         body={"request_id": req_id, "supplier_id": SUPPLIER_ID, "price": 89900}, expect_status=200)

# 7. Сделки
print("\n[ DEALS ]")
deal = test("POST /api/deals", "POST", "/api/deals",
    body={"buyer_id": BUYER_ID, "offer_id": offer_id or 1, "quantity": 1, "price": 99900},
    expect_status=200)

deal_id = None
if isinstance(deal, dict) and deal.get("ok"):
    deal_id = deal.get("deal_id")
    check("Сделка создана", deal_id is not None, str(deal))

test("GET /api/deals (buyer)", "GET", f"/api/deals?telegram_id={BUYER_ID}", expect_status=200)

if deal_id:
    test("POST /api/deals/{id}/status → confirmed", "POST", f"/api/deals/{deal_id}/status",
         body={"telegram_id": BUYER_ID, "status": "confirmed"}, expect_status=200)
    test("POST /api/deals/{id}/status → completed", "POST", f"/api/deals/{deal_id}/status",
         body={"telegram_id": BUYER_ID, "status": "completed"}, expect_status=200)

# 8. Отзывы
print("\n[ REVIEWS ]")
if deal_id:
    test("POST /api/reviews", "POST", "/api/reviews",
         body={"deal_id": deal_id, "reviewer_id": BUYER_ID, "rating": 5, "comment": "Отличный поставщик"},
         expect_status=200)

# 9. Профиль поставщика и статистика
print("\n[ SUPPLIER PROFILE ]")
test("GET /api/supplier", "GET", f"/api/supplier?telegram_id={SUPPLIER_ID}", expect_status=200)
test("GET /api/supplier/stats", "GET", f"/api/supplier/stats?telegram_id={SUPPLIER_ID}", expect_status=200)

# 10. Шаблон
print("\n[ TEMPLATE ]")
status, body = req("GET", "/api/supplier/template")
check("GET /api/supplier/template", status == 200, f"status={status}")

# 11. Админ
print("\n[ ADMIN ]")
test("GET /api/admin/deals", "GET", f"/api/admin/deals?admin_id={ADMIN_ID}", expect_status=200)
test("GET /api/admin/supplier_requests", "GET", f"/api/admin/supplier_requests?admin_id={ADMIN_ID}", expect_status=200)

# ─────────────────────────────────────────
print(f"\n{'='*40}")
print(f"  PASSED: {passed}   FAILED: {failed}   TOTAL: {passed+failed}")
print(f"{'='*40}")
if failed:
    print("\nПровалившиеся тесты:")
    for ok, name, detail in results:
        if not ok:
            print(f"  - {name}: {detail}")
