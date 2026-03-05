# Развёртывание бота на VPS (пошагово)

## Что нужно заранее

- **IP сервера** (например: `123.45.67.89`)
- **Логин** (часто `root`)
- **Пароль** от сервера

---

## Шаг 1. Подключиться к серверу из Cursor по SSH

1. В Cursor нажмите **Ctrl+Shift+P** (или F1) — откроется панель команд.
2. Введите: **Remote-SSH: Connect to Host** и выберите эту команду.
3. Вверху появится строка ввода. Напишите:
   ```text
   root@123.45.67.89
   ```
   (подставьте свой логин и IP вместо `root` и `123.45.67.89`).
4. Нажмите Enter. Cursor может спросить тип сервера — выберите **Linux**.
5. Введите **пароль** от сервера, когда попросит.
6. Откроется новое окно Cursor, подключённое к серверу. Слева в проводнике будет **Remote** — это папки на сервере, не на вашем ПК.

Если команды **Remote-SSH** нет, установите расширение **Remote - SSH** (Microsoft) в Cursor: вкладка Extensions (Ctrl+Shift+X) → поиск "Remote SSH" → Install.

---

## Шаг 2. Перенести файлы проекта на сервер

### Вариант А: Перетаскивание (проще для начала)

1. В подключённом к серверу окне Cursor откройте проводник слева (иконка папок).
2. Нажмите **Open Folder** и создайте/выберите папку на сервере, например: `/home/root/bot` или `/opt/bot`.
   - Чтобы создать папку в терминале сервера: **Terminal → New Terminal**, затем:
     ```bash
     mkdir -p /home/root/bot
     cd /home/root/bot
     ```
   - Потом в Cursor: **File → Open Folder** и укажите `/home/root/bot`.
3. На своём компьютере откройте папку с ботом (локально). Перетащите в окно Cursor (в проводник Remote) нужные файлы:
   - `main.py`
   - `database.py`
   - `index.html`
   - `requirements.txt`
   - папку `data` (если нужна)
   - файлы `import_catalog.py`, `check_db.py` и т.д., если используете.

Файл `market.db` можно не копировать — на сервере база создастся при первом запуске (или скопируйте, если хотите перенести данные).

### Вариант Б: Через Git

1. На своём ПК залейте проект в GitHub/GitLab (если ещё не сделали).
2. На сервере в терминале (в Cursor уже подключены к серверу):
   ```bash
   cd /home/root
   git clone https://github.com/ВАШ_ЛОГИН/ВАШ_РЕПОЗИТОРИЙ.git bot
   cd bot
   ```
   Подставьте свою ссылку на репозиторий.

Дальнейшие шаги выполняются **в терминале на сервере** (в том же окне Cursor, где вы подключены по SSH).

---

## Шаг 3. Установить Python и библиотеки на сервере

В терминале Cursor (на сервере) выполните по очереди.

**Установка Python 3 и pip (на Ubuntu/Debian):**

```bash
sudo apt update
sudo apt install -y python3 python3-pip
```

**Перейти в папку проекта** (если не в ней):

```bash
cd /home/root/bot
```

(или тот путь, куда вы положили файлы: `/opt/bot` и т.д.)

**Установить зависимости из requirements.txt:**

```bash
pip3 install -r requirements.txt
```

Если выдаст ошибку прав, попробуйте:

```bash
pip3 install --user -r requirements.txt
```

**Проверка запуска бота вручную:**

```bash
python3 main.py
```

Должны появиться строки вроде «API сервер запущен», «Бот запущен». Остановить — **Ctrl+C**. Дальше настроим автозапуск через systemd.

---

## Шаг 4. Автозапуск бота (systemd): при перезагрузке и при падении

### 4.1. Создать файл сервиса

В Cursor на сервере создайте файл (в папке проекта или в домашней):

**Файл:** `bot.service`

Содержимое (подставьте свой путь к папке бота и имя пользователя):

```ini
[Unit]
Description=Telegram Bot Gorbushka
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/home/root/bot
ExecStart=/usr/bin/python3 main.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

- Замените **`/home/root/bot`** на реальный путь к папке, где лежат `main.py` и `requirements.txt`.
- Если бот запускаете не под `root`, замените **`User=root`** на своего пользователя (например `User=ubuntu`).

### 4.2. Подключить сервис и включить автозапуск

В терминале на сервере:

**Скопировать сервис в systemd** (нужен полный путь к файлу `bot.service`):

```bash
sudo cp /home/root/bot/bot.service /etc/systemd/system/
```

**Перезагрузить список сервисов:**

```bash
sudo systemctl daemon-reload
```

**Включить автозапуск при перезагрузке сервера:**

```bash
sudo systemctl enable bot
```

**Запустить бота сейчас:**

```bash
sudo systemctl start bot
```

**Проверить, что бот работает:**

```bash
sudo systemctl status bot
```

Должно быть **active (running)**. Выход из статуса: клавиша **q**.

**Полезные команды потом:**

| Действие              | Команда                    |
|-----------------------|----------------------------|
| Остановить бота       | `sudo systemctl stop bot`   |
| Перезапустить бота    | `sudo systemctl restart bot` |
| Смотреть логи бота    | `sudo journalctl -u bot -f` |
| Выход из логов        | Ctrl+C                     |

После этого бот будет сам запускаться при перезагрузке VPS и перезапускаться, если упадёт (через 5 секунд).

---

## Краткий чек-лист

1. Подключиться по SSH в Cursor (Remote-SSH: Connect to Host → `root@IP`).
2. Открыть папку на сервере (например `/home/root/bot`) или склонировать Git.
3. Перенести файлы (перетаскиванием или Git).
4. Установить Python и зависимости: `apt install python3 python3-pip`, `pip3 install -r requirements.txt`.
5. Создать `bot.service`, скопировать в `/etc/systemd/system/`.
6. Выполнить: `daemon-reload` → `enable bot` → `start bot` → `status bot`.

Готово.
