import vk_api
from vk_api.longpoll import VkLongPoll, VkEventType
from vk_api.utils import get_random_id
import requests
import sqlite3
import random
import time
import datetime
import re
import json
import os
from PIL import Image, ImageDraw, ImageFont
import io
import math
import sys
import subprocess
import secrets  # для генерации кодов

# ================= КОНФИГУРАЦИЯ =================
USER_TOKEN = 'vk1.a.-skjA_qahwjDiig9rqTCTv37LhrNZxdmNvpJpfU0CSMvz-glB0brCdw1VkLk6ZVLOYPsL7h5b7kYORIS5ga5NKHCNFKoRYgU1hV_RgWXjUqaFjl2M5d2i-lwtiGmGYRLV-pvf-6b7_27ztOgrRC67z2Fys0NNJcXtIlltt2tDVfUSe-X3uj5d_ilHghBh2LLxd2ae1INY5CesZwxG-nukQ'
WEATHER_API_KEY = 'ac9cd4dc68922ec268a27655f9e03af2'
OWNER_ID = 1116380571
ADMIN_IDS = [1116380571]
DEFAULT_PREFIX = '/'
DB_FILE = 'bot.db'
IMAGES_DIR = 'images'

# ===== НАСТРОЙКИ GPT API =====
GPT_API_KEY = 'sk-RLbhraB12P6rLJjEFTZyjzzlLEOXbEKg'
GPT_API_URL = "https://api.openai.com/v1/chat/completions"
GPT_MODEL = "gpt-3.5-turbo"

ANECDOTES = [
    "Штирлиц склонился над картой СССР. Его неудержимо рвало на родину.",
    "Купил мужик шляпу, а она ему как раз.",
    "Один друг спрашивает другого: - Ты чего такой грустный? - Да вот, жена уехала. - А чего грустить? - Так я ее люблю!",
    "Объявление: Продам котят. Не дорого. Дорого только корм для них.",
    "Парадокс: в России два беды - дураки и дороги. Но если их соединить, получатся выборы."
]
# ================================================

# Функция для обращения к GPT
def ask_gpt(question, system_prompt="Вы - полезный ассистент в VK боте. Отвечайте кратко и по делу на русском языке."):
    if GPT_API_KEY == 'ВАШ_КЛЮЧ_OPENAI_API':
        return "❌ Ошибка: Не установлен API ключ GPT. Добавьте ваш ключ в переменную GPT_API_KEY"
    try:
        headers = {
            "Authorization": f"Bearer {GPT_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": GPT_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question}
            ],
            "max_tokens": 500,
            "temperature": 0.7
        }
        response = requests.post(GPT_API_URL, headers=headers, json=payload, timeout=30)
        if response.status_code == 200:
            result = response.json()
            return result['choices'][0]['message']['content']
        elif response.status_code == 401:
            return "❌ Ошибка: Неверный API ключ"
        elif response.status_code == 429:
            return "❌ Ошибка: Превышен лимит запросов. Попробуйте позже."
        else:
            return f"❌ Ошибка API: {response.status_code} - {response.text[:200]}"
    except requests.exceptions.Timeout:
        return "❌ Ошибка: Время ожидания истекло. Попробуйте еще раз."
    except Exception as e:
        return f"❌ Ошибка при обращении к GPT: {str(e)}"

# Инициализация VK
vk_session = vk_api.VkApi(token=USER_TOKEN)
vk = vk_session.get_api()
longpoll = VkLongPoll(vk_session)

# Владелец бота (независимо от токена)
OWNER_ID = 1116380571
ADMIN_IDS = [OWNER_ID]

# ID владельца токена (для проверки, на чьей странице работает бот)
try:
    token_owner_info = vk.users.get()[0]
    TOKEN_OWNER_ID = token_owner_info['id']
except Exception as e:
    print(f"Не удалось получить информацию о владельце токена: {e}")
    TOKEN_OWNER_ID = OWNER_ID

# ================= БАЗА ДАННЫХ =================
conn = sqlite3.connect(DB_FILE, check_same_thread=False)
cursor = conn.cursor()

def init_db():
    cursor.executescript('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        access_token TEXT,
        role INTEGER DEFAULT 0,
        btc INTEGER DEFAULT 0,
        dofamin INTEGER DEFAULT 0,
        herzog INTEGER DEFAULT 0,
        protection INTEGER DEFAULT 0,
        registered_at TIMESTAMP,
        last_dofamin_time REAL DEFAULT 0,
        last_steal_time REAL DEFAULT 0,
        last_prize_time REAL DEFAULT 0,
        stars INTEGER DEFAULT 0,
        trusted_ids TEXT DEFAULT '[]',
        prefix TEXT DEFAULT '/',
        is_disabled INTEGER DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS chat_prefixes (
        chat_id INTEGER PRIMARY KEY,
        prefix TEXT DEFAULT '/'
    );
    CREATE TABLE IF NOT EXISTS bans (
        user_id INTEGER,
        reason TEXT,
        expires_at REAL,
        banned_by INTEGER
    );
    CREATE TABLE IF NOT EXISTS access_cmds (
        user_id INTEGER PRIMARY KEY
    );
    CREATE TABLE IF NOT EXISTS history (
        user_id INTEGER,
        action TEXT,
        timestamp REAL
    );
    CREATE TABLE IF NOT EXISTS custom_gs (
        name TEXT PRIMARY KEY
    );
    CREATE TABLE IF NOT EXISTS custom_shab (
        name TEXT PRIMARY KEY
    );
    CREATE TABLE IF NOT EXISTS reg_codes (
        code TEXT PRIMARY KEY,
        role INTEGER DEFAULT 0,
        uses INTEGER DEFAULT 1,
        created_by INTEGER,
        created_at REAL
    );
    ''')
    conn.commit()

init_db()

def db_get_user(user_id):
    cursor.execute('SELECT * FROM users WHERE user_id=?', (user_id,))
    return cursor.fetchone()

def db_create_user(user_id, access_token=None):
    if not db_get_user(user_id):
        role = 5 if user_id in ADMIN_IDS else 0   # создатель получает роль 5
        cursor.execute('INSERT INTO users (user_id, access_token, role, registered_at) VALUES (?,?,?,?)',
                       (user_id, access_token, role, time.time()))
        conn.commit()

def db_update_user(user_id, **kwargs):
    keys = ', '.join(f'{k}=?' for k in kwargs)
    values = list(kwargs.values()) + [user_id]
    cursor.execute(f'UPDATE users SET {keys} WHERE user_id=?', values)
    conn.commit()

def db_get_trusted(user_id):
    row = db_get_user(user_id)
    if row and row[12]:
        try:
            return json.loads(row[12])
        except:
            return []
    return []

def db_add_trusted(user_id, trusted_id):
    trusted = db_get_trusted(user_id)
    if trusted_id not in trusted:
        trusted.append(trusted_id)
        db_update_user(user_id, trusted_ids=json.dumps(trusted))

def db_remove_trusted(user_id, trusted_id):
    trusted = db_get_trusted(user_id)
    if trusted_id in trusted:
        trusted.remove(trusted_id)
        db_update_user(user_id, trusted_ids=json.dumps(trusted))

def get_prefix(chat_id):
    cursor.execute('SELECT prefix FROM chat_prefixes WHERE chat_id=?', (chat_id,))
    row = cursor.fetchone()
    if row:
        return row[0]
    return DEFAULT_PREFIX

def set_prefix(chat_id, new_prefix):
    cursor.execute('INSERT OR REPLACE INTO chat_prefixes (chat_id, prefix) VALUES (?,?)', (chat_id, new_prefix))
    conn.commit()

def get_access_users():
    cursor.execute('SELECT user_id FROM access_cmds')
    return [row[0] for row in cursor.fetchall()]

def is_user_disabled(user_id):
    row = db_get_user(user_id)
    if row:
        return row[14] == 1
    return False

def generate_reg_code(role=0, uses=1, creator_id=None):
    """Генерирует уникальный код регистрации и сохраняет в БД."""
    code = secrets.token_hex(4).upper()  # 8 символов
    cursor.execute('INSERT INTO reg_codes (code, role, uses, created_by, created_at) VALUES (?,?,?,?,?)',
                   (code, role, uses, creator_id, time.time()))
    conn.commit()
    return code

# ================= ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =================
def is_creator(user_id):
    return user_id in ADMIN_IDS or get_role(user_id) >= 5

def get_role(user_id):
    row = db_get_user(user_id)
    return row[2] if row else 0

def is_admin(user_id):
    # роль 4 (Админ) и выше
    return user_id in ADMIN_IDS or get_role(user_id) >= 4

def is_emperor(user_id):
    return user_id in ADMIN_IDS or get_role(user_id) >= 3

def is_prince(user_id):
    return user_id in ADMIN_IDS or get_role(user_id) >= 2

def is_elite(user_id):
    return user_id in ADMIN_IDS or get_role(user_id) >= 1

def get_reply_message(event):
    """Безопасно получаем reply_message из события."""
    return getattr(event, 'reply_message', None)

def get_target_and_clean_args(event, args):
    """
    Возвращает (target_id, new_args).
    Если цель указана через ответ на сообщение, new_args = args.
    Если цель указана в тексте (упоминание), она удаляется из args.
    Если цель не указана, возвращает (None, args).
    """
    reply_msg = get_reply_message(event)
    if reply_msg:
        return reply_msg['from_id'], args
    text = event.text
    match = re.search(r'\[id(\d+)\|', text)
    if match:
        target_id = int(match.group(1))
        new_args = [arg for arg in args if not re.search(r'\[id\d+\|', arg) and not re.search(r'@id\d+', arg)]
        return target_id, new_args
    match = re.search(r'@id(\d+)', text)
    if match:
        target_id = int(match.group(1))
        new_args = [arg for arg in args if not re.search(r'\[id\d+\|', arg) and not re.search(r'@id\d+', arg)]
        return target_id, new_args
    return None, args

def check_cooldown(user_id, action, cooldown_seconds):
    row = db_get_user(user_id)
    if not row:
        return True
    field_map = {
        'dofamin': 8,
        'steal': 9,
        'prize': 10
    }
    last_time = row[field_map[action]]
    return (time.time() - last_time) >= cooldown_seconds

def update_cooldown(user_id, action):
    field_map = {
        'dofamin': 'last_dofamin_time',
        'steal': 'last_steal_time',
        'prize': 'last_prize_time'
    }
    db_update_user(user_id, **{field_map[action]: time.time()})

def send_message(peer_id, message, attachment=None):
    vk.messages.send(
        peer_id=peer_id,
        message=message,
        attachment=attachment,
        random_id=get_random_id()
    )

def download_photo(url):
    response = requests.get(url)
    if response.status_code == 200:
        return response.content
    return None

def get_user_info(user_id):
    try:
        info = vk.users.get(user_ids=user_id, fields='photo_max_orig,status,counters,friend_status,online')
        if info:
            return info[0]
    except:
        pass
    return None

def get_user_avatar(user_id):
    info = get_user_info(user_id)
    if info and 'photo_max_orig' in info:
        return info['photo_max_orig']
    return None

def get_random_image(folder_path):
    if os.path.isdir(folder_path):
        photos = [f for f in os.listdir(folder_path) if f.endswith(('.jpg', '.png', '.jpeg', '.gif'))]
        if photos:
            return os.path.join(folder_path, random.choice(photos))
    return None

def upload_photo_to_vk(peer_id, photo_path):
    try:
        upload = vk.photos.getMessagesUploadServer(peer_id=peer_id)['upload_url']
        with open(photo_path, 'rb') as f:
            response = requests.post(upload, files={'photo': f}).json()
        saved = vk.photos.saveMessagesPhoto(**response)[0]
        return f"photo{saved['owner_id']}_{saved['id']}"
    except Exception as e:
        print(f"Ошибка загрузки фото: {e}")
        return None

# ================= ОБРАБОТЧИК КОМАНД =================
def process_command(event):
    if not event.text:
        return
    chat_id = event.peer_id
    if event.from_chat:
        chat_id = event.chat_id
    prefix = get_prefix(chat_id)
    if not event.text.startswith(prefix):
        return
    text = event.text[len(prefix):].strip()
    if not text:
        return
    parts = text.split()
    command = parts[0].lower()
    args = parts[1:]

    user_id = event.user_id

    if TOKEN_OWNER_ID != OWNER_ID and user_id != OWNER_ID:
        return

    row = db_get_user(user_id)
    if not row:
        if user_id == OWNER_ID:
            db_create_user(user_id)
        elif command == 'reg':
            if len(args) >= 1:
                reg_code = args[0]
                cursor.execute('SELECT role, uses FROM reg_codes WHERE code=?', (reg_code,))
                code_row = cursor.fetchone()
                if code_row:
                    role = code_row[0]
                    uses = code_row[1]
                    db_create_user(user_id)
                    if user_id not in ADMIN_IDS:
                        db_update_user(user_id, role=role)
                    if uses > 1:
                        cursor.execute('UPDATE reg_codes SET uses=? WHERE code=?', (uses-1, reg_code))
                        conn.commit()
                    else:
                        cursor.execute('DELETE FROM reg_codes WHERE code=?', (reg_code,))
                        conn.commit()
                    send_message(event.peer_id, f"✅ Регистрация прошла успешно! Ваша роль: {role}")
                else:
                    send_message(event.peer_id, "❌ Неверный код регистрации.")
            else:
                send_message(event.peer_id, "Использование: /reg (код)")
            return
        else:
            return

    if is_user_disabled(user_id) and not is_creator(user_id):
        send_message(event.peer_id, "⛔ Ваш доступ к боту отключён создателем.")
        return

    # ===== ОБЩИЕ КОМАНДЫ =====
    if command == 'help':
        help_text = """
📋 Список команд:
👤 /dox — открытая информация о человеке
🕵️ /doxelp — закрытая информация (Князь+)
📊 /стат — профиль в боте
🎰 /казино (ставка) (количество) — игра на БТС
💰 /выдатьбтс (ссылка/ответ) (кол-во) — выдать БТС (Админ+)
👑 /герцог — купить подписку Герцог
🎁 /выдгерцог — выдать Герцога (Админ+)
🧪 /дофамин — получить дофамин
🤫 /украстьдоф — украсть дофамин
🛡️ /защитадоф — купить защиту от кражи (500 БТС)
🖼️ /стикеры — посмотреть стикеры игрока
📨 /sp — добавить в доверенность
🚫 /unsp — убрать из доверенности
📩 /vls — отправить сообщение в ЛС
🤖 /ai (запрос) — спросить ИИ
🔗 /cc (ссылка) — сократить ссылку
➕ /+гс (название) — добавить ГС
📃 /гсы — список ГС
➖ /-гс (название) — удалить ГС
➕ /+шаб (название) — добавить шаблон
📃 /шаблоны — список шаблонов
➖ /-шаб (название) — удалить шаблон
🔐 /подбор (0-10) — подбор паролей
📲 /+invite — пригласить друзей в чат
🛑 /-invite — остановить приглашение
🔑 /password — подбор пароля
🌤️ /погода (город) — погода
🎱 /шар (вопрос) — магический шар
📝 /+описание (текст) — сменить статус VK
🖼️ /аватарка — отправить аватар
🗑️ /-смс (ссылка/ответ) (кол-во) — удалить сообщения
💬 /цитата (фото+текст) — создать цитату
🖤 /демо (текст) — демотиватор
🏓 /пинг — проверка
🌸 /тян — фото тянки
🦵 /ножки — фото ножек
🖼️ /пикча — случайное фото из папки images/gort
😄 /анекдот — случайный анекдот
🔧 /префикс (префикс) — сменить префикс
⭐ /+роль (0-4) — выдать роль (только Создатель)
❌ /-роль — забрать роль (только Создатель)
👥 /стафф — список персонала
🔐 /доступы — список с доступом к -смс
➕ /+доступ — выдать доступ к -смс (Князь+)
➖ /-доступ — забрать доступ (Князь+)
➕ /добавить — добавить в беседу
👢 /кик — кикнуть из беседы
🧮 /реши (пример) — решить пример
🧹 /чистка (кол-во) — удалить свои сообщения
🎁 /приз — получить БТС (раз в 2 часа)
📖 /helpr1 — команды ранга Элита
📖 /helpr2 — команды ранга Князь
📖 /helpr3 — команды ранга Император
🔑 /reg (код) — регистрация по коду
🔑 /reg (токен) — сохранить токен (для зарегистрированных)
🔑 /rcode [роль] [кол-во] — создать код регистрации (Админ+)
📋 /codes — список активных кодов (Админ+)

🛒 /starshop — магазин за звёзды
🛒 /buy — купить товар (например: /buy бтс 100)

🏆 /топбтс — топ по БТС
🧪 /топдоф — топ по дофамину
👑 /герцоги — список обладателей Герцога
🛡️ /защищённые — список защищённых пользователей

🔧 Команды разработчика (Админ+):
🔄 /restart — перезапустить бота
🛑 /stop — остановить бота
🗑️ /сброс (токен/ID) — сбросить токен пользователя
🔍 /токен инфа (токен) — информация о токене

🔧 Только для Создателя:
📋 /базаданных — список всех зарегистрированных пользователей
⛔ /отключение — отключить пользователя от бота
✅ /включение — включить пользователя обратно
➕ /+админ — назначить администратора
➖ /-админ — снять администратора
"""
        send_message(event.peer_id, help_text)

    elif command == 'reg':
        if len(args) >= 1:
            token = args[0]
            db_update_user(user_id, access_token=token)
            send_message(event.peer_id, "✅ Токен сохранён. Теперь вы можете использовать закрытые функции.")
        else:
            send_message(event.peer_id, "Использование: /reg (токен)")

    elif command == 'rcode':
        if not is_admin(user_id):
            send_message(event.peer_id, "⛔ Недостаточно прав. Требуется роль Админ или выше.")
            return
        role = 0
        uses = 1
        if args:
            try:
                role = int(args[0])
                if role not in (0, 1, 2, 3, 4):
                    raise ValueError
            except:
                send_message(event.peer_id, "Роль должна быть 0,1,2,3,4.")
                return
        if len(args) >= 2:
            try:
                uses = int(args[1])
                if uses < 1:
                    raise ValueError
            except:
                send_message(event.peer_id, "Количество использований должно быть положительным числом.")
                return
        code = generate_reg_code(role, uses, user_id)
        send_message(event.peer_id, f"✅ Создан код регистрации: {code}\nРоль: {role}, использований: {uses}")

    elif command == 'codes':
        if not is_admin(user_id):
            send_message(event.peer_id, "⛔ Недостаточно прав. Требуется роль Админ или выше.")
            return
        cursor.execute('SELECT code, role, uses, created_by, created_at FROM reg_codes')
        rows = cursor.fetchall()
        if rows:
            message = "Активные коды регистрации:\n"
            for r in rows:
                message += f"Код: {r[0]}, Роль: {r[1]}, Осталось: {r[2]}, Создал: {r[3]}\n"
            send_message(event.peer_id, message)
        else:
            send_message(event.peer_id, "Нет активных кодов.")

    elif command == 'dox':
        target_id, _ = get_target_and_clean_args(event, args)
        target_id = target_id or user_id
        info = get_user_info(target_id)
        if info:
            counters = info.get('counters', {})
            friends = counters.get('friends', 0)
            followers = counters.get('followers', 0)
            photos = counters.get('photos', 0)
            status = info.get('status', '')
            online = 'Онлайн' if info.get('online') else 'Оффлайн'
            message = f"👤 {info['first_name']} {info['last_name']}\n"
            message += f"Статус: {status}\n"
            message += f"Друзья: {friends}\n"
            message += f"Подписчики: {followers}\n"
            message += f"Фотографии: {photos}\n"
            message += f"Статус: {online}"
            send_message(event.peer_id, message)
        else:
            send_message(event.peer_id, "Не удалось получить информацию.")

    elif command == 'doxelp':
        if not is_prince(user_id):
            send_message(event.peer_id, "⛔ Недостаточно прав.")
            return
        target_id, _ = get_target_and_clean_args(event, args)
        target_id = target_id or user_id
        send_message(event.peer_id, f"Закрытая информация о пользователе {target_id}:\nEmail: скрыт (нет доступа)\nСоцсети: не найдены")

    elif command == 'стат':
        target_id, _ = get_target_and_clean_args(event, args)
        target_id = target_id or user_id
        row = db_get_user(target_id)
        if row:
            reg_time = datetime.datetime.fromtimestamp(row[7]).strftime('%Y-%m-%d %H:%M') if row[7] else 'неизвестно'
            role_names = {0: 'Участник', 1: 'Элита', 2: 'Князь', 3: 'Император', 4: 'Админ', 5: 'Создатель'}
            role = role_names.get(row[2], 'Неизвестно')
            disabled = '🔴 Отключён' if row[14] else '✅ Активен'
            message = f"📊 Профиль пользователя {target_id}:\n"
            message += f"Зарегистрирован: {reg_time}\n"
            message += f"БТС: {row[3]}\n"
            message += f"Дофамин: {row[4]}\n"
            message += f"Герцог: {'Да' if row[5] else 'Нет'}\n"
            message += f"Защита: {'Да' if row[6] else 'Нет'}\n"
            message += f"Роль: {role}\n"
            message += f"Звёзды: {row[11]}\n"
            message += f"Статус: {disabled}"
            send_message(event.peer_id, message)
        else:
            send_message(event.peer_id, "Пользователь не зарегистрирован в боте.")

    elif command == 'казино':
        if len(args) < 2:
            send_message(event.peer_id, "Использование: /казино (ставка) (количество)")
            return
        try:
            stavka = args[0]
            amount = int(args[1])
            if amount <= 0:
                raise ValueError
        except:
            send_message(event.peer_id, "Неверный формат. Пример: /казино х2 100")
            return
        multipliers = {'х2': 2, 'х3': 3, 'х5': 5, 'х10': 10}
        if stavka not in multipliers:
            send_message(event.peer_id, "Доступные ставки: х2, х3, х5, х10")
            return
        row = db_get_user(user_id)
        if row[3] < amount:
            send_message(event.peer_id, "Недостаточно БТС.")
            return
        win = random.random() < 0.3
        if win:
            prize = amount * multipliers[stavka]
            db_update_user(user_id, btc=row[3] + prize)
            send_message(event.peer_id, f"🎉 Поздравляем! Вы выиграли {prize} БТС!")
        else:
            db_update_user(user_id, btc=row[3] - amount)
            send_message(event.peer_id, f"😞 Вы проиграли {amount} БТС.")

    elif command == 'выдатьбтс':
        if not is_admin(user_id):
            send_message(event.peer_id, "⛔ Недостаточно прав.")
            return
        target_id, cleaned_args = get_target_and_clean_args(event, args)
        if not target_id:
            send_message(event.peer_id, "Укажите пользователя.")
            return
        if not cleaned_args:
            send_message(event.peer_id, "Укажите количество.")
            return
        try:
            amount = int(cleaned_args[-1])
        except:
            send_message(event.peer_id, "Неверное количество.")
            return
        db_create_user(target_id)
        row = db_get_user(target_id)
        db_update_user(target_id, btc=row[3] + amount)
        send_message(event.peer_id, f"✅ Выдано {amount} БТС пользователю {target_id}.")

    elif command == 'герцог':
        row = db_get_user(user_id)
        cost = 1000
        if row[5]:
            send_message(event.peer_id, "Вы уже Герцог.")
            return
        if row[3] < cost:
            send_message(event.peer_id, f"Недостаточно БТС. Нужно {cost}.")
            return
        db_update_user(user_id, btc=row[3] - cost, herzog=1)
        send_message(event.peer_id, "👑 Поздравляем! Вы стали Герцогом!")

    elif command == 'выдгерцог':
        if not is_admin(user_id):
            send_message(event.peer_id, "⛔ Недостаточно прав.")
            return
        target_id, _ = get_target_and_clean_args(event, args)
        target_id = target_id or user_id
        db_create_user(target_id)
        db_update_user(target_id, herzog=1)
        send_message(event.peer_id, f"✅ Герцог выдан пользователю {target_id}.")

    elif command == 'дофамин':
        if not check_cooldown(user_id, 'dofamin', 900):
            send_message(event.peer_id, "Слишком часто. Попробуйте позже.")
            return
        amount = random.randint(1, 10)
        row = db_get_user(user_id)
        db_update_user(user_id, dofamin=row[4] + amount)
        update_cooldown(user_id, 'dofamin')
        send_message(event.peer_id, f"🧪 Вы получили {amount} дофамина!")

    elif command == 'украстьдоф':
        if not check_cooldown(user_id, 'steal', 1200):
            send_message(event.peer_id, "Слишком часто. Попробуйте позже.")
            return
        target_id, _ = get_target_and_clean_args(event, args)
        if not target_id or target_id == user_id:
            send_message(event.peer_id, "Укажите цель.")
            return
        row_target = db_get_user(target_id)
        if not row_target or row_target[4] <= 0:
            send_message(event.peer_id, "У цели нет дофамина.")
            return
        if row_target[6]:
            send_message(event.peer_id, "У цели есть защита! Кража не удалась.")
            return
        steal_amount = random.randint(1, min(10, row_target[4]))
        if random.random() < 0.6:
            db_update_user(target_id, dofamin=row_target[4] - steal_amount)
            row_user = db_get_user(user_id)
            db_update_user(user_id, dofamin=row_user[4] + steal_amount)
            send_message(event.peer_id, f"✅ Вы украли {steal_amount} дофамина!")
        else:
            send_message(event.peer_id, "❌ Вас поймали! Кража не удалась.")
        update_cooldown(user_id, 'steal')

    elif command == 'защитадоф':
        row = db_get_user(user_id)
        cost = 500
        if row[6]:
            send_message(event.peer_id, "У вас уже есть защита.")
            return
        if row[3] < cost:
            send_message(event.peer_id, f"Недостаточно БТС. Нужно {cost}.")
            return
        db_update_user(user_id, btc=row[3] - cost, protection=1)
        send_message(event.peer_id, "🛡 Вы купили защиту от кражи дофамина.")

    elif command == 'выдзащита':
        if not is_admin(user_id):
            send_message(event.peer_id, "⛔ Недостаточно прав.")
            return
        target_id, _ = get_target_and_clean_args(event, args)
        target_id = target_id or user_id
        db_create_user(target_id)
        db_update_user(target_id, protection=1)
        send_message(event.peer_id, f"✅ Защита выдана пользователю {target_id}.")

    elif command == 'стикеры':
        target_id, _ = get_target_and_clean_args(event, args)
        target_id = target_id or user_id
        send_message(event.peer_id, f"У пользователя {target_id} много стикеров (заглушка).")

    elif command == 'sp':
        if not args:
            send_message(event.peer_id, "Использование: /sp (сообщение) — отправить сообщение от имени бота")
            return
        target_id, cleaned_args = get_target_and_clean_args(event, args)
        msg = ' '.join(cleaned_args)
        if target_id:
            if target_id not in db_get_trusted(user_id) and not is_prince(user_id):
                send_message(event.peer_id, "⛔ Пользователь не в доверенности.")
                return
            try:
                vk.messages.send(peer_id=target_id, message=msg, random_id=get_random_id())
                send_message(event.peer_id, f"✅ Сообщение отправлено пользователю {target_id}.")
            except Exception as e:
                send_message(event.peer_id, f"❌ Не удалось отправить: {e}")
        else:
            trusted = db_get_trusted(user_id)
            if not trusted:
                send_message(event.peer_id, "У вас нет доверенных пользователей.")
                return
            for trusted_id in trusted:
                try:
                    vk.messages.send(peer_id=trusted_id, message=msg, random_id=get_random_id())
                    time.sleep(0.3)
                except:
                    continue
            send_message(event.peer_id, f"✅ Сообщение отправлено {len(trusted)} доверенным пользователям.")

    elif command == 'unsp':
        target_id, _ = get_target_and_clean_args(event, args)
        if not target_id:
            send_message(event.peer_id, "Укажите пользователя.")
            return
        db_remove_trusted(user_id, target_id)
        send_message(event.peer_id, f"✅ Пользователь {target_id} убран из доверенности.")

    elif command == 'vls':
        target_id, _ = get_target_and_clean_args(event, args)
        if not target_id:
            send_message(event.peer_id, "Укажите пользователя.")
            return
        if target_id not in db_get_trusted(user_id) and not is_prince(user_id):
            send_message(event.peer_id, "⛔ Пользователь не в доверенности.")
            return
        try:
            vk.messages.send(peer_id=target_id, message="Привет! Это сообщение от бота.", random_id=get_random_id())
            send_message(event.peer_id, f"✅ Сообщение отправлено пользователю {target_id}.")
        except Exception as e:
            send_message(event.peer_id, f"❌ Не удалось отправить: {e}")

    elif command == 'ai':
        query = ' '.join(args)
        if not query:
            send_message(event.peer_id, "Введите запрос.")
            return
        answer = ask_gpt(query)
        send_message(event.peer_id, answer)

    elif command == 'cc':
        if not args:
            send_message(event.peer_id, "Укажите ссылку.")
            return
        url = args[0]
        try:
            short = vk.utils.getShortLink(url=url)
            send_message(event.peer_id, f"Короткая ссылка: {short['short_url']}")
        except Exception as e:
            send_message(event.peer_id, f"Ошибка: {e}")

    elif command == '+гс':
        name = ' '.join(args)
        if not name:
            send_message(event.peer_id, "Укажите название.")
            return
        cursor.execute('INSERT OR IGNORE INTO custom_gs (name) VALUES (?)', (name,))
        conn.commit()
        send_message(event.peer_id, f"✅ ГС '{name}' добавлен.")

    elif command == 'гсы':
        cursor.execute('SELECT name FROM custom_gs')
        rows = cursor.fetchall()
        if rows:
            send_message(event.peer_id, "Список ГС:\n" + '\n'.join([r[0] for r in rows]))
        else:
            send_message(event.peer_id, "Список пуст.")

    elif command == '-гс':
        name = ' '.join(args)
        if not name:
            send_message(event.peer_id, "Укажите название.")
            return
        cursor.execute('DELETE FROM custom_gs WHERE name=?', (name,))
        conn.commit()
        send_message(event.peer_id, f"✅ ГС '{name}' удалён.")

    elif command == '+шаб':
        name = ' '.join(args)
        if not name:
            send_message(event.peer_id, "Укажите название шаблона.")
            return
        cursor.execute('INSERT OR IGNORE INTO custom_shab (name) VALUES (?)', (name,))
        conn.commit()
        send_message(event.peer_id, f"✅ Шаблон '{name}' добавлен.")

    elif command == 'шаблоны':
        cursor.execute('SELECT name FROM custom_shab')
        rows = cursor.fetchall()
        if rows:
            send_message(event.peer_id, "Шаблоны:\n" + '\n'.join([r[0] for r in rows]))
        else:
            send_message(event.peer_id, "Шаблонов нет.")

    elif command == '-шаб':
        name = ' '.join(args)
        if not name:
            send_message(event.peer_id, "Укажите название.")
            return
        cursor.execute('DELETE FROM custom_shab WHERE name=?', (name,))
        conn.commit()
        send_message(event.peer_id, f"✅ Шаблон '{name}' удалён.")

    elif command == 'подбор':
        if not args:
            send_message(event.peer_id, "Использование: /подбор (0-10)")
            return
        try:
            start, end = map(int, args[0].split('-'))
            if start > end:
                start, end = end, start
            passwords = [str(random.randint(start, end)) for _ in range(5)]
            send_message(event.peer_id, "Подобранные пароли:\n" + '\n'.join(passwords))
        except:
            send_message(event.peer_id, "Неверный формат. Пример: /подбор 0-10")

    elif command == '+invite':
        if not event.from_chat:
            send_message(event.peer_id, "Команда доступна только в беседе.")
            return
        try:
            friends = vk.friends.get(user_id=user_id, count=1000)['items']
            added = 0
            for friend_id in friends:
                try:
                    vk.messages.addChatUser(chat_id=event.chat_id, user_id=friend_id)
                    added += 1
                    time.sleep(0.3)
                except:
                    continue
            send_message(event.peer_id, f"✅ Приглашено друзей: {added}")
        except Exception as e:
            send_message(event.peer_id, f"Ошибка: {e}")

    elif command == '-invite':
        send_message(event.peer_id, "Приглашение остановлено.")

    elif command == 'password':
        send_message(event.peer_id, "🔐 Начинаю подбор пароля... (заглушка)")

    elif command == 'погода':
        if not args:
            send_message(event.peer_id, "Укажите город.")
            return
        city = ' '.join(args)
        url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={WEATHER_API_KEY}&units=metric&lang=ru"
        try:
            response = requests.get(url).json()
            if response.get('main'):
                temp = response['main']['temp']
                desc = response['weather'][0]['description']
                send_message(event.peer_id, f"Погода в {city}: {temp}°C, {desc}")
            else:
                send_message(event.peer_id, "Город не найден.")
        except Exception as e:
            send_message(event.peer_id, f"Ошибка: {e}")

    elif command == 'шар':
        if not args:
            send_message(event.peer_id, "Задайте вопрос.")
            return
        answers = ["Да", "Нет", "Возможно", "Спроси позже", "Точно да", "Точно нет", "Не сейчас"]
        send_message(event.peer_id, f"🎱 {random.choice(answers)}")

    elif command == '+описание':
        text = ' '.join(args)
        if not text:
            send_message(event.peer_id, "Укажите текст.")
            return
        try:
            vk.status.set(text=text)
            send_message(event.peer_id, "✅ Статус обновлён.")
        except Exception as e:
            send_message(event.peer_id, f"Ошибка: {e}")

    elif command == 'аватарка':
        target_id, _ = get_target_and_clean_args(event, args)
        target_id = target_id or user_id
        url = get_user_avatar(target_id)
        if url:
            send_message(event.peer_id, attachment=url)
        else:
            send_message(event.peer_id, "Не удалось получить аватар.")

    elif command == '-смс':
        if not is_prince(user_id) and user_id not in get_access_users():
            send_message(event.peer_id, "⛔ Недостаточно прав.")
            return
        target_id, cleaned_args = get_target_and_clean_args(event, args)
        if not target_id:
            send_message(event.peer_id, "Укажите пользователя.")
            return
        if cleaned_args:
            try:
                count = int(cleaned_args[-1])
            except:
                count = 1
        else:
            count = 1
        try:
            messages = vk.messages.getHistory(peer_id=event.peer_id, count=200)['items']
            deleted = 0
            for msg in messages:
                if msg['from_id'] == target_id and deleted < count:
                    vk.messages.delete(message_ids=msg['id'], delete_for_all=1)
                    deleted += 1
                    time.sleep(0.3)
            send_message(event.peer_id, f"✅ Удалено сообщений: {deleted}")
        except Exception as e:
            send_message(event.peer_id, f"Ошибка: {e}")

    elif command == 'цитата':
        photo_url = None
        reply_msg = get_reply_message(event)
        if reply_msg and 'attachments' in reply_msg:
            for att in reply_msg['attachments']:
                if att['type'] == 'photo':
                    photo_url = att['photo']['sizes'][-1]['url']
        if not photo_url:
            send_message(event.peer_id, "Прикрепите фото ответом.")
            return
        text = ' '.join(args)
        if not text:
            send_message(event.peer_id, "Укажите текст цитаты.")
            return
        img_data = download_photo(photo_url)
        if not img_data:
            send_message(event.peer_id, "Не удалось скачать фото.")
            return
        img = Image.open(io.BytesIO(img_data))
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("arial.ttf", size=20)
        except:
            font = ImageFont.load_default()
        draw.text((10, 10), text, fill='white', font=font)
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        upload = vk.photos.getMessagesUploadServer(peer_id=event.peer_id)['upload_url']
        response = requests.post(upload, files={'photo': ('quote.png', buf, 'image/png')}).json()
        saved = vk.photos.saveMessagesPhoto(**response)[0]
        attachment = f"photo{saved['owner_id']}_{saved['id']}"
        send_message(event.peer_id, attachment=attachment)

    elif command == 'демо':
        text = ' '.join(args)
        if not text:
            send_message(event.peer_id, "Укажите текст.")
            return
        img = Image.new('RGB', (600, 400), color='black')
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("arial.ttf", size=24)
        except:
            font = ImageFont.load_default()
        draw.text((50, 150), text, fill='white', font=font)
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        upload = vk.photos.getMessagesUploadServer(peer_id=event.peer_id)['upload_url']
        response = requests.post(upload, files={'photo': ('demo.png', buf, 'image/png')}).json()
        saved = vk.photos.saveMessagesPhoto(**response)[0]
        attachment = f"photo{saved['owner_id']}_{saved['id']}"
        send_message(event.peer_id, attachment=attachment)

    elif command == 'пинг':
        send_message(event.peer_id, "Понг!")

    elif command == 'пикча':
        folder = os.path.join(IMAGES_DIR, 'gort')
        photo_path = get_random_image(folder)
        if photo_path:
            attachment = upload_photo_to_vk(event.peer_id, photo_path)
            if attachment:
                send_message(event.peer_id, attachment=attachment)
            else:
                send_message(event.peer_id, "Не удалось загрузить фото.")
        else:
            send_message(event.peer_id, "Папка images/gort не найдена или пуста.")

    elif command == 'тян':
        folder = os.path.join(IMAGES_DIR, 'tyan')
        photo_path = get_random_image(folder)
        if photo_path:
            attachment = upload_photo_to_vk(event.peer_id, photo_path)
            if attachment:
                send_message(event.peer_id, attachment=attachment)
            else:
                send_message(event.peer_id, "Не удалось загрузить фото.")
        else:
            send_message(event.peer_id, "Папка с тянками не найдена или пуста. Создайте папку images/tyan и поместите туда фото.")

    elif command == 'ножки':
        folder = os.path.join(IMAGES_DIR, 'legs')
        photo_path = get_random_image(folder)
        if photo_path:
            attachment = upload_photo_to_vk(event.peer_id, photo_path)
            if attachment:
                send_message(event.peer_id, attachment=attachment)
            else:
                send_message(event.peer_id, "Не удалось загрузить фото.")
        else:
            send_message(event.peer_id, "Папка с ножками не найдена или пуста. Создайте папку images/legs и поместите туда фото.")

    elif command == 'анекдот':
        send_message(event.peer_id, random.choice(ANECDOTES))

    elif command == 'префикс':
        if not args:
            send_message(event.peer_id, "Укажите новый префикс.")
            return
        new_prefix = args[0]
        if event.from_chat:
            set_prefix(event.chat_id, new_prefix)
        else:
            db_update_user(user_id, prefix=new_prefix)
        send_message(event.peer_id, f"✅ Префикс изменён на '{new_prefix}'.")

    elif command == '+роль':
        if not is_creator(user_id):
            send_message(event.peer_id, "⛔ Только создатель может выдавать роли.")
            return
        target_id, cleaned_args = get_target_and_clean_args(event, args)
        if not target_id:
            send_message(event.peer_id, "Укажите пользователя.")
            return
        if not cleaned_args:
            send_message(event.peer_id, "Использование: /+роль (0-4) (ссылка/ответ)")
            return
        try:
            role = int(cleaned_args[0])
            if role not in (0, 1, 2, 3, 4):
                raise ValueError
        except:
            send_message(event.peer_id, "Роль должна быть 0,1,2,3,4.")
            return
        db_create_user(target_id)
        db_update_user(target_id, role=role)
        send_message(event.peer_id, f"✅ Пользователю {target_id} выдана роль {role}.")

    elif command == '-роль':
        if not is_creator(user_id):
            send_message(event.peer_id, "⛔ Только создатель может забирать роли.")
            return
        target_id, _ = get_target_and_clean_args(event, args)
        if not target_id:
            send_message(event.peer_id, "Укажите пользователя.")
            return
        db_create_user(target_id)
        db_update_user(target_id, role=0)
        send_message(event.peer_id, f"✅ У пользователя {target_id} забрана роль.")

    elif command == 'стафф':
        cursor.execute('SELECT user_id, role FROM users WHERE role > 0')
        rows = cursor.fetchall()
        if rows:
            message = "Персонал:\n"
            for r in rows:
                role_names = {1: 'Элита', 2: 'Князь', 3: 'Император', 4: 'Админ', 5: 'Создатель'}
                message += f"ID {r[0]} — {role_names.get(r[1], '?')}\n"
            send_message(event.peer_id, message)
        else:
            send_message(event.peer_id, "Персонала нет.")

    elif command == 'доступы':
        users = get_access_users()
        if users:
            send_message(event.peer_id, "Пользователи с доступом к -смс:\n" + '\n'.join([str(uid) for uid in users]))
        else:
            send_message(event.peer_id, "Список пуст.")

    elif command == '+доступ':
        if not is_prince(user_id):
            send_message(event.peer_id, "⛔ Недостаточно прав.")
            return
        target_id, _ = get_target_and_clean_args(event, args)
        if not target_id:
            send_message(event.peer_id, "Укажите пользователя.")
            return
        cursor.execute('INSERT OR IGNORE INTO access_cmds (user_id) VALUES (?)', (target_id,))
        conn.commit()
        send_message(event.peer_id, f"✅ Доступ выдан пользователю {target_id}.")

    elif command == '-доступ':
        if not is_prince(user_id):
            send_message(event.peer_id, "⛔ Недостаточно прав.")
            return
        target_id, _ = get_target_and_clean_args(event, args)
        if not target_id:
            send_message(event.peer_id, "Укажите пользователя.")
            return
        cursor.execute('DELETE FROM access_cmds WHERE user_id=?', (target_id,))
        conn.commit()
        send_message(event.peer_id, f"✅ Доступ забран у пользователя {target_id}.")

    elif command == 'добавить':
        if not event.from_chat:
            send_message(event.peer_id, "Команда доступна только в беседе.")
            return
        target_id, _ = get_target_and_clean_args(event, args)
        if not target_id:
            send_message(event.peer_id, "Укажите пользователя.")
            return
        try:
            vk.messages.addChatUser(chat_id=event.chat_id, user_id=target_id)
            send_message(event.peer_id, f"✅ Пользователь {target_id} добавлен в беседу.")
        except Exception as e:
            send_message(event.peer_id, f"Ошибка: {e}")

    elif command == 'кик':
        if not event.from_chat:
            send_message(event.peer_id, "Команда доступна только в беседе.")
            return
        target_id, _ = get_target_and_clean_args(event, args)
        if not target_id:
            send_message(event.peer_id, "Укажите пользователя.")
            return
        try:
            vk.messages.removeChatUser(chat_id=event.chat_id, user_id=target_id)
            send_message(event.peer_id, f"✅ Пользователь {target_id} исключён из беседы.")
        except Exception as e:
            send_message(event.peer_id, f"Ошибка: {e}")

    elif command == 'реши':
        expr = ' '.join(args)
        if not expr:
            send_message(event.peer_id, "Введите пример.")
            return
        try:
            result = eval(expr, {"__builtins__": None}, {"abs": abs, "round": round})
            send_message(event.peer_id, f"Результат: {result}")
        except Exception as e:
            send_message(event.peer_id, f"Ошибка: {e}")

    elif command == 'чистка':
        if not args:
            send_message(event.peer_id, "Укажите количество сообщений.")
            return
        try:
            count = int(args[0])
        except:
            send_message(event.peer_id, "Неверное количество.")
            return
        try:
            messages = vk.messages.getHistory(peer_id=event.peer_id, count=200)['items']
            deleted = 0
            for msg in messages:
                if msg['from_id'] == OWNER_ID:
                    vk.messages.delete(message_ids=msg['id'], delete_for_all=1)
                    deleted += 1
                    if deleted >= count:
                        break
                    time.sleep(0.3)
            send_message(event.peer_id, f"✅ Удалено своих сообщений: {deleted}")
        except Exception as e:
            send_message(event.peer_id, f"Ошибка: {e}")

    elif command == 'приз':
        if not check_cooldown(user_id, 'prize', 7200):
            send_message(event.peer_id, "Приз можно получать раз в 2 часа.")
            return
        prize = random.randint(0, 10000)
        row = db_get_user(user_id)
        db_update_user(user_id, btc=row[3] + prize)
        update_cooldown(user_id, 'prize')
        send_message(event.peer_id, f"🎁 Вы получили {prize} БТС!")

    elif command == 'helpr1':
        if is_elite(user_id):
            send_message(event.peer_id, """
            Команды ранга Элита:
            /чек — профиль игрока
            /история — нарушения игрока
            /чекбан — информация о бане
            /баны — банлист
            """)
        else:
            send_message(event.peer_id, "⛔ Недостаточно прав.")

    elif command == 'чек':
        if not is_elite(user_id):
            send_message(event.peer_id, "⛔ Недостаточно прав.")
            return
        target_id, _ = get_target_and_clean_args(event, args)
        target_id = target_id or user_id
        row = db_get_user(target_id)
        if row:
            send_message(event.peer_id, f"Профиль {target_id}: БТС={row[3]}, Дофамин={row[4]}, Роль={row[2]}")
        else:
            send_message(event.peer_id, "Пользователь не найден.")

    elif command == 'история':
        if not is_elite(user_id):
            send_message(event.peer_id, "⛔ Недостаточно прав.")
            return
        target_id, _ = get_target_and_clean_args(event, args)
        target_id = target_id or user_id
        cursor.execute('SELECT action, timestamp FROM history WHERE user_id=?', (target_id,))
        rows = cursor.fetchall()
        if rows:
            message = f"История нарушений {target_id}:\n"
            for r in rows:
                message += f"{datetime.datetime.fromtimestamp(r[1]).strftime('%Y-%m-%d %H:%M')} — {r[0]}\n"
            send_message(event.peer_id, message)
        else:
            send_message(event.peer_id, "История пуста.")

    elif command == 'чекбан':
        if not is_elite(user_id):
            send_message(event.peer_id, "⛔ Недостаточно прав.")
            return
        target_id, _ = get_target_and_clean_args(event, args)
        target_id = target_id or user_id
        cursor.execute('SELECT reason, expires_at, banned_by FROM bans WHERE user_id=?', (target_id,))
        row = cursor.fetchone()
        if row:
            expires = datetime.datetime.fromtimestamp(row[1]).strftime('%Y-%m-%d %H:%M') if row[1] else 'навсегда'
            send_message(event.peer_id, f"Бан пользователя {target_id}:\nПричина: {row[0]}\nИстекает: {expires}\nКем выдан: {row[2]}")
        else:
            send_message(event.peer_id, "Бан не найден.")

    elif command == 'баны':
        if not is_elite(user_id):
            send_message(event.peer_id, "⛔ Недостаточно прав.")
            return
        cursor.execute('SELECT user_id, reason, expires_at FROM bans')
        rows = cursor.fetchall()
        if rows:
            message = "Банлист:\n"
            for r in rows:
                expires = datetime.datetime.fromtimestamp(r[2]).strftime('%Y-%m-%d %H:%M') if r[2] else 'навсегда'
                message += f"ID {r[0]} — {r[1]} (до {expires})\n"
            send_message(event.peer_id, message)
        else:
            send_message(event.peer_id, "Банов нет.")

    elif command == 'helpr2':
        if is_prince(user_id):
            send_message(event.peer_id, """
            Команды ранга Князь:
            /block (пользователь) (0-15) (причина)
            /выдатьзащита (пользователь)
            /starshop
            /block (пользователь) (0-60) (причина)
            """)
        else:
            send_message(event.peer_id, "⛔ Недостаточно прав.")

    elif command == 'block':
        if not is_prince(user_id):
            send_message(event.peer_id, "⛔ Недостаточно прав.")
            return
        target_id, cleaned_args = get_target_and_clean_args(event, args)
        if not target_id:
            send_message(event.peer_id, "Укажите пользователя.")
            return
        if not cleaned_args:
            send_message(event.peer_id, "Укажите срок.")
            return
        duration_str = cleaned_args[0]
        reason = ' '.join(cleaned_args[1:]) if len(cleaned_args) > 1 else 'Без причины'
        try:
            duration = int(duration_str)
        except:
            send_message(event.peer_id, "Неверный срок.")
            return
        expires = time.time() + duration * 60 if duration != -1 else None
        cursor.execute('INSERT OR REPLACE INTO bans (user_id, reason, expires_at, banned_by) VALUES (?,?,?,?)',
                       (target_id, reason, expires, user_id))
        conn.commit()
        cursor.execute('INSERT INTO history (user_id, action, timestamp) VALUES (?,?,?)',
                       (target_id, f"Бан: {reason}", time.time()))
        conn.commit()
        send_message(event.peer_id, f"✅ Пользователь {target_id} заблокирован на {duration} минут.")

    elif command == 'unblock':
        if not is_admin(user_id):
            send_message(event.peer_id, "⛔ Недостаточно прав.")
            return
        target_id, _ = get_target_and_clean_args(event, args)
        if not target_id:
            send_message(event.peer_id, "Укажите пользователя.")
            return
        cursor.execute('DELETE FROM bans WHERE user_id=?', (target_id,))
        conn.commit()
        send_message(event.peer_id, f"✅ Пользователь {target_id} разблокирован.")

    elif command == 'выдатьзащита':
        if not is_admin(user_id):
            send_message(event.peer_id, "⛔ Недостаточно прав.")
            return
        target_id, _ = get_target_and_clean_args(event, args)
        target_id = target_id or user_id
        db_create_user(target_id)
        db_update_user(target_id, protection=1)
        send_message(event.peer_id, f"✅ Защита выдана пользователю {target_id}.")

    elif command == 'starshop':
        # Магазин модерации
        shop_text = """
🛒 Магазин за звёзды:
⭐ Ваши звёзды можно получить за нахождение багов или идеи для бота.

Товары:
👑 Герцог на неделю — 150 звёзд
🛡️ Защита на месяц — 350 звёзд
💰 БТС: 1 БТС = 5 звёзд
🧪 Дофамин: 5 дофамина = 1 звезда
📈 Повышение роли:
   • Участник → Элита: 7000 звёзд
   • Элита → Князь: 5000 звёзд
   • Князь → Император: 25000 звёзд
   • Император → Админ: 1000000 звёзд

Для покупки используйте /buy <товар> [количество]
Примеры:
/buy герцог
/buy защита
/buy бтс 10
/buy дофамин 5
/buy повышение
"""
        send_message(event.peer_id, shop_text)

    elif command == 'buy':
        # Покупка в магазине
        if not args:
            send_message(event.peer_id, "Использование: /buy <товар> [количество]")
            return
        item = args[0].lower()
        row = db_get_user(user_id)
        if not row:
            return
        stars = row[11]
        if item == 'герцог':
            cost = 150
            if stars < cost:
                send_message(event.peer_id, f"❌ Недостаточно звёзд. Нужно {cost}.")
                return
            db_update_user(user_id, stars=stars - cost, herzog=1)
            send_message(event.peer_id, "✅ Вы купили Герцога на неделю!")
        elif item == 'защита':
            cost = 350
            if stars < cost:
                send_message(event.peer_id, f"❌ Недостаточно звёзд. Нужно {cost}.")
                return
            db_update_user(user_id, stars=stars - cost, protection=1)
            send_message(event.peer_id, "✅ Вы купили защиту на месяц!")
        elif item == 'бтс':
            if len(args) < 2:
                send_message(event.peer_id, "Укажите количество БТС: /buy бтс <кол-во>")
                return
            try:
                amount = int(args[1])
                if amount <= 0:
                    raise ValueError
            except:
                send_message(event.peer_id, "Неверное количество.")
                return
            cost = amount * 5
            if stars < cost:
                send_message(event.peer_id, f"❌ Недостаточно звёзд. Нужно {cost}.")
                return
            db_update_user(user_id, stars=stars - cost, btc=row[3] + amount)
            send_message(event.peer_id, f"✅ Вы купили {amount} БТС за {cost} звёзд.")
        elif item == 'дофамин':
            if len(args) < 2:
                send_message(event.peer_id, "Укажите количество дофамина (кратно 5): /buy дофамин <кол-во>")
                return
            try:
                amount = int(args[1])
                if amount <= 0 or amount % 5 != 0:
                    raise ValueError
            except:
                send_message(event.peer_id, "Количество должно быть положительным и кратным 5.")
                return
            cost = amount // 5
            if stars < cost:
                send_message(event.peer_id, f"❌ Недостаточно звёзд. Нужно {cost}.")
                return
            db_update_user(user_id, stars=stars - cost, dofamin=row[4] + amount)
            send_message(event.peer_id, f"✅ Вы купили {amount} дофамина за {cost} звёзд.")
        elif item == 'повышение':
            current_role = row[2]
            role_prices = {
                0: (7000, 1, 'Элита'),
                1: (5000, 2, 'Князь'),
                2: (25000, 3, 'Император'),
                3: (1000000, 4, 'Админ')
            }
            if current_role >= 4:
                send_message(event.peer_id, "❌ Вы уже имеете максимальную роль, доступную для покупки.")
                return
            cost, new_role, role_name = role_prices[current_role]
            if stars < cost:
                send_message(event.peer_id, f"❌ Недостаточно звёзд. Нужно {cost}.")
                return
            db_update_user(user_id, stars=stars - cost, role=new_role)
            send_message(event.peer_id, f"✅ Поздравляем! Вы повышены до роли {role_name}!")
        else:
            send_message(event.peer_id, "❌ Неизвестный товар. Доступно: герцог, защита, бтс, дофамин, повышение.")

    elif command == 'топбтс':
        cursor.execute('SELECT user_id, btc FROM users ORDER BY btc DESC LIMIT 10')
        rows = cursor.fetchall()
        if rows:
            message = "🏆 Топ по БТС:\n"
            for i, r in enumerate(rows, 1):
                message += f"{i}. ID {r[0]} — {r[1]} БТС\n"
            send_message(event.peer_id, message)
        else:
            send_message(event.peer_id, "Нет данных.")

    elif command == 'топдоф':
        cursor.execute('SELECT user_id, dofamin FROM users ORDER BY dofamin DESC LIMIT 10')
        rows = cursor.fetchall()
        if rows:
            message = "🧪 Топ по дофамину:\n"
            for i, r in enumerate(rows, 1):
                message += f"{i}. ID {r[0]} — {r[1]} дофамина\n"
            send_message(event.peer_id, message)
        else:
            send_message(event.peer_id, "Нет данных.")

    elif command == 'герцоги':
        cursor.execute('SELECT user_id FROM users WHERE herzog=1')
        rows = cursor.fetchall()
        if rows:
            message = "👑 Обладатели Герцога:\n"
            for r in rows:
                message += f"• ID {r[0]}\n"
            send_message(event.peer_id, message)
        else:
            send_message(event.peer_id, "Никто не имеет Герцога.")

    elif command == 'защищённые':
        cursor.execute('SELECT user_id FROM users WHERE protection=1')
        rows = cursor.fetchall()
        if rows:
            message = "🛡️ Защищённые пользователи:\n"
            for r in rows:
                message += f"• ID {r[0]}\n"
            send_message(event.peer_id, message)
        else:
            send_message(event.peer_id, "Никто не имеет защиты.")

    elif command == '+админ':
        if not is_creator(user_id):
            send_message(event.peer_id, "⛔ Только создатель может назначать администраторов.")
            return
        target_id, _ = get_target_and_clean_args(event, args)
        if not target_id:
            send_message(event.peer_id, "Укажите пользователя.")
            return
        db_create_user(target_id)
        db_update_user(target_id, role=4)
        send_message(event.peer_id, f"✅ Пользователь {target_id} назначен администратором.")

    elif command == '-админ':
        if not is_creator(user_id):
            send_message(event.peer_id, "⛔ Только создатель может снимать администраторов.")
            return
        target_id, _ = get_target_and_clean_args(event, args)
        if not target_id:
            send_message(event.peer_id, "Укажите пользователя.")
            return
        db_create_user(target_id)
        db_update_user(target_id, role=0)
        send_message(event.peer_id, f"✅ Пользователь {target_id} снят с должности администратора.")

    elif command == 'helpr3':
        if is_admin(user_id):
            send_message(event.peer_id, """
            Команды ранга Админ+ (включая Императора и выше):
            /givstar — выдать звёзды
            /статвся — вся статистика
            /выдатьдоф — выдать дофамин
            /-kd — сбросить кулдауны
            /+токен — добавить токен
            /-дофамин — забрать дофамин
            /забгерцог — забрать герцога
            /rcode — создать код регистрации
            /codes — список кодов
            /забратьак — посмотреть токен пользователя
            /restart — перезапустить бота
            /stop — остановить бота
            /сброс — сбросить токен
            /токен инфа — проверить токен
            """)
        else:
            send_message(event.peer_id, "⛔ Недостаточно прав.")

    elif command == 'givstar':
        if not is_admin(user_id):
            send_message(event.peer_id, "⛔ Недостаточно прав.")
            return
        target_id, cleaned_args = get_target_and_clean_args(event, args)
        if not target_id:
            send_message(event.peer_id, "Укажите пользователя.")
            return
        if not cleaned_args:
            send_message(event.peer_id, "Укажите количество.")
            return
        try:
            stars = int(cleaned_args[-1])
        except:
            send_message(event.peer_id, "Неверное количество.")
            return
        db_create_user(target_id)
        row = db_get_user(target_id)
        db_update_user(target_id, stars=row[11] + stars)
        send_message(event.peer_id, f"✅ Выдано {stars} звёзд пользователю {target_id}.")

    elif command == 'статвся':
        if not is_admin(user_id):
            send_message(event.peer_id, "⛔ Недостаточно прав.")
            return
        cursor.execute('SELECT user_id, btc, dofamin, herzog, role, stars, is_disabled FROM users')
        rows = cursor.fetchall()
        if rows:
            message = "Вся статистика:\n"
            for r in rows:
                disabled = '🔴 Отключён' if r[6] else '✅ Активен'
                message += f"ID {r[0]}: БТС={r[1]}, Дофамин={r[2]}, Герцог={r[3]}, Роль={r[4]}, Звёзды={r[5]}, {disabled}\n"
            send_message(event.peer_id, message)
        else:
            send_message(event.peer_id, "Нет данных.")

    elif command == 'выдатьдоф':
        if not is_admin(user_id):
            send_message(event.peer_id, "⛔ Недостаточно прав.")
            return
        target_id, _ = get_target_and_clean_args(event, args)
        target_id = target_id or user_id
        db_create_user(target_id)
        row = db_get_user(target_id)
        amount = random.randint(1, 10)
        db_update_user(target_id, dofamin=row[4] + amount)
        send_message(event.peer_id, f"✅ Выдано {amount} дофамина пользователю {target_id}.")

    elif command == '-kd':
        if not is_admin(user_id):
            send_message(event.peer_id, "⛔ Недостаточно прав.")
            return
        cursor.execute('UPDATE users SET last_dofamin_time=0, last_steal_time=0, last_prize_time=0')
        conn.commit()
        send_message(event.peer_id, "✅ Кулдауны сброшены для всех.")

    elif command == '+токен':
        if not is_admin(user_id):
            send_message(event.peer_id, "⛔ Недостаточно прав.")
            return
        if not args:
            send_message(event.peer_id, "Укажите токен.")
            return
        token = args[0]
        db_update_user(user_id, access_token=token)
        send_message(event.peer_id, "✅ Токен сохранён.")

    elif command == '-дофамин':
        if not is_admin(user_id):
            send_message(event.peer_id, "⛔ Недостаточно прав.")
            return
        target_id, _ = get_target_and_clean_args(event, args)
        if not target_id:
            send_message(event.peer_id, "Укажите пользователя.")
            return
        row = db_get_user(target_id)
        if row and row[4] > 0:
            db_update_user(target_id, dofamin=row[4] - 1)
            send_message(event.peer_id, f"✅ Дофамин забран у пользователя {target_id}.")
        else:
            send_message(event.peer_id, "У пользователя нет дофамина.")

    elif command == 'забгерцог':
        if not is_admin(user_id):
            send_message(event.peer_id, "⛔ Недостаточно прав.")
            return
        target_id, _ = get_target_and_clean_args(event, args)
        if not target_id:
            send_message(event.peer_id, "Укажите пользователя.")
            return
        db_create_user(target_id)
        db_update_user(target_id, herzog=0)
        send_message(event.peer_id, f"✅ Герцог забран у пользователя {target_id}.")

    elif command == 'токен инфа' or command == 'токен_инфа':
        if not is_admin(user_id):
            send_message(event.peer_id, "⛔ Только администрация может использовать эту команду.")
            return
        if not args:
            send_message(event.peer_id, "Использование: /токен инфа (токен)")
            return
        token = args[0]
        try:
            test_vk = vk_api.VkApi(token=token)
            test_vk_session = test_vk.get_api()
            info = test_vk_session.users.get()[0]
            send_message(event.peer_id, f"📊 Информация о токене:\nID: {info['id']}\nИмя: {info['first_name']} {info['last_name']}\nТокен валидный.")
        except Exception as e:
            send_message(event.peer_id, f"❌ Токен недействителен или ошибка: {e}")

    elif command == 'базаданных':
        if not is_creator(user_id):
            send_message(event.peer_id, "⛔ Только создатель может просматривать базу данных.")
            return
        cursor.execute('SELECT user_id, access_token FROM users')
        rows = cursor.fetchall()
        if not rows:
            send_message(event.peer_id, "База данных пуста.")
            return
        message = "📋 База данных пользователей:\n"
        for i, r in enumerate(rows):
            token = r[1] if r[1] else "нет токена"
            message += f"{i+1}. ID: {r[0]}, Токен: {token}\n"
            if len(message) > 3500:
                send_message(event.peer_id, message)
                message = ""
        if message:
            send_message(event.peer_id, message)

    elif command == 'restart':
        if not is_admin(user_id):
            send_message(event.peer_id, "⛔ Только администрация может перезапускать бота.")
            return
        send_message(event.peer_id, "🔄 Бот перезапускается...")
        time.sleep(1)
        conn.commit()
        os.execv(sys.executable, ['python'] + sys.argv)

    elif command == 'stop':
        if not is_admin(user_id):
            send_message(event.peer_id, "⛔ Только администрация может остановить бота.")
            return
        send_message(event.peer_id, "🛑 Бот останавливается... Данные сохранены.")
        conn.commit()
        sys.exit(0)

    elif command == 'сброс' or command == 'сбросить':
        if not is_admin(user_id):
            send_message(event.peer_id, "⛔ Только администрация может сбрасывать токены.")
            return
        if len(args) < 1:
            send_message(event.peer_id, "Использование: /сброс (токен) или /сброс (айди пользователя)")
            return
        target = args[0]
        if target.isdigit():
            target_id = int(target)
            db_update_user(target_id, access_token=None)
            send_message(event.peer_id, f"✅ Токен пользователя {target_id} сброшен.")
        else:
            cursor.execute('SELECT user_id FROM users WHERE access_token=?', (target,))
            row = cursor.fetchone()
            if row:
                db_update_user(row[0], access_token=None)
                send_message(event.peer_id, f"✅ Токен пользователя {row[0]} сброшен.")
            else:
                send_message(event.peer_id, "❌ Токен не найден в базе данных.")

    elif command == 'отключение' or command == 'отключить':
        if not is_creator(user_id):
            send_message(event.peer_id, "⛔ Только создатель может отключать пользователей.")
            return
        target_id, _ = get_target_and_clean_args(event, args)
        if not target_id:
            send_message(event.peer_id, "Укажите пользователя (ответом или ссылкой).")
            return
        if target_id in ADMIN_IDS:
            send_message(event.peer_id, "⛔ Нельзя отключить создателя/администратора.")
            return
        db_create_user(target_id)
        db_update_user(target_id, is_disabled=1)
        send_message(event.peer_id, f"✅ Пользователь {target_id} отключён от бота. Все функции для него остановлены.")

    elif command == 'включение' or command == 'включить':
        if not is_creator(user_id):
            send_message(event.peer_id, "⛔ Только создатель может включать пользователей.")
            return
        target_id, _ = get_target_and_clean_args(event, args)
        if not target_id:
            send_message(event.peer_id, "Укажите пользователя (ответом или ссылкой).")
            return
        db_create_user(target_id)
        db_update_user(target_id, is_disabled=0)
        send_message(event.peer_id, f"✅ Пользователь {target_id} включён обратно в бота.")

    else:
        send_message(event.peer_id, "Неизвестная команда. Введите /help для списка.")

# ================= ЗАПУСК =================
print("Бот запущен. Ожидание сообщений...")
for event in longpoll.listen():
    if event.type == VkEventType.MESSAGE_NEW:
        try:
            process_command(event)
        except Exception as e:
            print(f"Ошибка: {e}")
            send_message(event.peer_id, f"Произошла ошибка: {e}")
