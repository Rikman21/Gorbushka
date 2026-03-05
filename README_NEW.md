# Биржа Горбушка - Инструкция по запуску

## Что изменилось

Приложение полностью переделано в **биржу товаров Apple** с системой сделок между покупателями и поставщиками.

### Основные функции:

1. **Биржа** - поиск и фильтрация предложений от поставщиков
2. **Каталог** - структурированный каталог товаров (управляется админом)
3. **Сделки** - система безопасных сделок с чатом и статусами
4. **Профили поставщиков** - рейтинг, отзывы, история сделок
5. **Панель поставщика** - управление предложениями и ценами

---

## Быстрый старт

### 1. Инициализация базы данных

```bash
python
>>> import database
>>> database.init_db()
>>> exit()
```

Это создаст новую структуру БД с таблицами:
- `users` - пользователи
- `catalog` - каталог товаров
- `offers` - предложения поставщиков
- `deals` - сделки
- `messages` - сообщения в чате сделки
- `reviews` - отзывы

### 2. Добавление товаров в каталог (только админ)

Запустите бота и используйте команды:

```
/admin
/add_catalog iPhone|Apple|iPhone 16 Pro Max|256GB|Черный титан|IP16PM256BT
/add_catalog iPhone|Apple|iPhone 16 Pro|256GB|Синий титан|IP16P256ST
/add_catalog iPhone|Apple|iPhone 15|128GB|Черный|IP15128B
```

Формат: `Категория|Бренд|Модель|Память|Цвет|SKU`

### 3. Настройка API адреса в index.html

В `index.html` найдите строку (около 293):

```javascript
const API_BASE = urlParams.get('api') || 'https://your-server.com';
```

Замените на адрес вашего сервера:
```javascript
const API_BASE = urlParams.get('api') || 'https://gorbushka.example.com';
```

Или используйте ngrok для тестирования:
```bash
ngrok http 8080
# Замените на полученный URL: https://xxxx.ngrok-free.app
```

### 4. Запуск бота

```bash
python main.py
```

Бот запустится на порту 8080 и будет обрабатывать:
- Telegram сообщения
- API запросы от WebApp

---

## Роли и возможности

### Покупатель (по умолчанию)

- Просмотр предложений на бирже
- Фильтрация по модели, памяти, состоянию, цене
- Создание сделок
- Общение с поставщиком в чате сделки
- Просмотр профилей поставщиков
- Оставление отзывов

### Поставщик

Для регистрации: Профиль → Стать поставщиком

После регистрации доступно:
- Добавление предложений на биржу
- Управление ценами и наличием
- Получение заявок от покупателей
- Управление сделками (подтверждение, статусы)
- Профиль с рейтингом и отзывами

### Администратор

Команды в Telegram:
- `/admin` - панель администратора
- `/add_catalog` - добавить товар в каталог

---

## Структура API

Все API endpoints доступны по адресу `http://127.0.0.1:8080/api/`:

### GET /api/offers
Получить предложения с фильтрами

Параметры:
- `model` - фильтр по модели
- `memory` - фильтр по памяти
- `condition` - новый/ref/б/у
- `min_price`, `max_price` - диапазон цен
- `in_stock` - только в наличии
- `verified` - только проверенные поставщики

### GET /api/catalog
Получить каталог товаров

### GET /api/user?telegram_id=XXX
Получить данные пользователя

### GET /api/deals?telegram_id=XXX&status=created
Получить сделки пользователя

### GET /api/deal?deal_id=XXX
Получить детали сделки с сообщениями

### GET /api/supplier?supplier_id=XXX
Получить профиль поставщика с предложениями и отзывами

---

## Работа с WebApp (из index.html)

### Создание сделки
```javascript
tg.sendData('CREATE_DEAL|offer_id|quantity');
```

### Подтверждение сделки (поставщик)
```javascript
tg.sendData('CONFIRM_DEAL|deal_id');
```

### Обновление статуса сделки
```javascript
tg.sendData('UPDATE_DEAL_STATUS|deal_id|status');
```

Статусы: `created`, `confirmed`, `in_progress`, `ready`, `closed`, `cancelled`

### Добавление предложения
```javascript
tg.sendData('ADD_OFFER|catalog_id|price|quantity|moq|condition|delivery_days|warranty_months|comment');
```

### Обновление предложения
```javascript
tg.sendData('UPDATE_OFFER|offer_id|field|value');
```

Поля: `price`, `quantity`, `is_available`, `is_visible`

### Отправка сообщения в чат сделки
```javascript
tg.sendData('SEND_MESSAGE|deal_id|message_text');
```

### Добавление отзыва
```javascript
tg.sendData('ADD_REVIEW|deal_id|supplier_id|rating|comment');
```

---

## Тестирование

### 1. Создание тестовых данных

```python
import database

# Создать пользователя-поставщика
database.create_or_update_user(464896073, "seller1", "Продавец 1")
database.update_user_supplier_info(464896073, "Магазин Техники", "Москва", "+79991234567")

# Добавить товары в каталог
database.add_catalog_item("iPhone", "Apple", "iPhone 16 Pro Max", "256GB", "Черный титан", "IP16PM256BT")
database.add_catalog_item("iPhone", "Apple", "iPhone 15", "128GB", "Черный", "IP15128B")

# Создать предложение
database.create_offer(
    supplier_id=464896073,
    catalog_id=1,
    price=120000,
    quantity=5,
    moq=1,
    condition="new",
    delivery_days=0,
    warranty_months=12,
    comment="Оригинал, в наличии"
)
```

### 2. Проверка API

```bash
# Проверить предложения
curl http://127.0.0.1:8080/api/offers

# Проверить каталог
curl http://127.0.0.1:8080/api/catalog

# Проверить пользователя
curl http://127.0.0.1:8080/api/user?telegram_id=464896073
```

### 3. Тестирование в Telegram

1. Запустите бота: `/start`
2. Откройте биржу
3. Просмотрите предложения
4. Создайте сделку
5. Проверьте чат и статусы

---

## Развертывание на сервере

### Вариант 1: Nginx + systemd

1. Скопируйте файлы на сервер
2. Установите зависимости: `pip install -r requirements.txt`
3. Настройте Nginx (прокси на порт 8080)
4. Создайте systemd сервис
5. Настройте SSL (Let's Encrypt)

Подробнее см. `SETUP_INSTRUCTIONS.md`

### Вариант 2: Docker (рекомендуется)

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 8080
CMD ["python", "main.py"]
```

```bash
docker build -t gorbushka-bot .
docker run -p 8080:8080 -v ./market.db:/app/market.db gorbushka-bot
```

---

## Настройка GitHub Pages

1. Обновите `index.html` с правильным `API_BASE`
2. Закоммитьте и запушьте на GitHub
3. Включите GitHub Pages в настройках репозитория
4. Обновите `WEB_APP_URL` в `main.py`

---

## Отладка

### Проблемы с загрузкой данных

1. Проверьте, что бот запущен: `curl http://127.0.0.1:8080/`
2. Проверьте CORS заголовки в ответах API
3. Откройте консоль браузера в Telegram (Desktop: View → Developer Tools)
4. Проверьте, что `API_BASE` указан правильно

### Проблемы с сделками

1. Проверьте, что пользователь зарегистрирован в БД
2. Проверьте наличие предложения в таблице `offers`
3. Проверьте логи бота: смотрите вывод в консоли

### Проблемы с отображением

1. Очистите кеш GitHub Pages (может занять до 10 минут)
2. Добавьте параметр версии к URL: `?v=2`
3. Проверьте, что все статические ресурсы загружены

---

## Следующие шаги

1. **Массовое добавление каталога** - импорт из Excel
2. **Уведомления** - push-уведомления о статусах сделок
3. **Поиск** - полнотекстовый поиск по каталогу
4. **Аналитика** - статистика для поставщиков
5. **Платежи** - интеграция с платежными системами
6. **Избранное** - сохранение предложений
7. **Подписка** - тарифы для поставщиков

---

## Поддержка

При возникновении проблем:

1. Проверьте логи бота
2. Проверьте консоль браузера
3. Проверьте структуру БД: `sqlite3 market.db ".schema"`
4. Создайте issue на GitHub с описанием проблемы

---

## Лицензия

MIT
