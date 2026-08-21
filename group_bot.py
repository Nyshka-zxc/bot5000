import vk_api
from vk_api.longpoll import VkBotLongPoll, VkBotEventType
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
from vk_api.utils import get_random_id
import sqlite3
import time
import datetime
import re
import json
import secrets

# ================= КОНФИГУРАЦИЯ =================
GROUP_TOKEN = 'vk1.a.j43kauMNXAtsOInVslnUOkgub4N7zs4g5G0SP4yY_fS8uyyAp9XmJhQ-T7gWpGVlSq3by1kzsXdl3X9yd4DueZK-gtj9xS_hpN6vregip7Y5JiYrevGbKPAoroytCyFYYTTfYJpk_BzkuInzXHm5jSdYY6irEF6eT5ADApQa9awmbdU9-ZDlm5SDt5sa0mVVWKEPG83KWa0uIDHtuYcnDA'  # замените на реальный токен
GROUP_ID = 240961509  # замените на ID сообщества

DB_FILE = 'bot.db'  # общая база со страничным ботом

REVIEWS_LINK = 'https://vk.com/topic-123456789_12345678'  # ссылка на отзывы
IDEAS_LINK = 'https://vk.com/topic-123456789_12345679'    # ссылка на идеи

ADMIN_IDS = [1116380571]  # ID владельца/создателя
OWNER_ID = 1116380571

# Инициализация
vk_session = vk_api.VkApi(token=GROUP_TOKEN)
vk = vk_session.get_api()
longpoll = VkBotLongPoll(vk_session, group_id=GROUP_ID)

# Подключение к базе данных
conn = sqlite3.connect(DB_FILE, check_same_thread=False)
conn.execute("PRAGMA journal_mode=WAL")
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

# Вспомогательные функции
def db_get_user(user_id):
    cursor.execute('SELECT * FROM users WHERE user_id=?', (user_id,))
    return cursor.fetchone()

def db_create_user(user_id, access_token=None, role=0):
    if not db_get_user(user_id):
        cursor.execute('INSERT INTO users (user_id, access_token, role, registered_at) VALUES (?,?,?,?)',
                       (user_id, access_token, role, time.time()))
        conn.commit()
        return True
    return False

def db_update_user(user_id, **kwargs):
    keys = ', '.join(f'{k}=?' for k in kwargs)
    values = list(kwargs.values()) + [user_id]
    cursor.execute(f'UPDATE users SET {keys} WHERE user_id=?', values)
    conn.commit()

def get_role(user_id):
    row = db_get_user(user_id)
    return row[2] if row else 0

def is_admin(user_id):
    return user_id in ADMIN_IDS or get_role(user_id) >= 4

def is_creator(user_id):
    return user_id in ADMIN_IDS or get_role(user_id) >= 5

def generate_reg_code(role=0, uses=1, creator_id=None):
    code = secrets.token_hex(4).upper()
    cursor.execute('INSERT INTO reg_codes (code, role, uses, created_by, created_at) VALUES (?,?,?,?,?)',
                   (code, role, uses, creator_id, time.time()))
    conn.commit()
    return code

# ========== КЛАВИАТУРЫ ==========
def get_start_keyboard():
    """Клавиатура приветствия (выбор способа регистрации + ссылки)"""
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button("📝  Регистрация по коду", color=VkKeyboardColor.PRIMARY)
keyboard.add_line()
    keyboard.add_button("🔑  Регистрация по токену", color=VkKeyboardColor.POSITIVE)
    keyboard.add_line()
    keyboard.add_button("💬  Отзывы", color=VkKeyboardColor.SECONDARY)
    keyboard.add_button("💡  Идеи", color=VkKeyboardColor.SECONDARY)
    keyboard.add_line()
    keyboard.add_button("📋 Помощь", color=VkKeyboardColor.PRIMARY)
    return keyboard.get_keyboard()

def get_main_keyboard():
    """Главная клавиатура с основными действиями"""
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button("📋 Помощь", color=VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button("📝  Регистрация по коду", color=VkKeyboardColor.PRIMARY)
    keyboard.add_button("🔑  Регистрация по токену", color=VkKeyboardColor.POSITIVE)
    keyboard.add_line()
    keyboard.add_button("💬  Отзывы", color=VkKeyboardColor.SECONDARY)
    keyboard.add_button("💡  Идеи", color=VkKeyboardColor.SECONDARY)
    return keyboard.get_keyboard()

# Отправка сообщения
def send_message(peer_id, message, keyboard=None):
    vk.messages.send(
        peer_id=peer_id,
        message=message,
        random_id=get_random_id(),
        keyboard=keyboard
    )

# ========== ОБРАБОТЧИК ==========
def process_event(event):
    if event.type != VkBotEventType.MESSAGE_NEW:
        return

    message = event.object.message
    user_id = message['from_id']
    peer_id = message['peer_id']
    text = message.get('text', '').strip()
    payload = message.get('payload')

    # Обработка нажатия кнопки "start" (если используется)
    if payload:
        try:
            payload_data = json.loads(payload) if isinstance(payload, str) else payload
            if payload_data.get('command') == 'start':
                send_message(peer_id,
                    "👋  Привет! Я бот этого сообщества.\n\n"
                    "Выберите действие:",
                    keyboard=get_start_keyboard()
                )
                return
        except:
            pass

    # Если нет текста, но есть нажатие кнопки (payload) - обработали выше, иначе выходим
    if not text:
        return

    # Приветствие по текстовым командам
    if text.lower() in ['начать', 'start', 'старт', 'привет']:
        send_message(peer_id,
            "👋  Привет! Я бот этого сообщества.\n\n"
            "Выберите действие:",
            keyboard=get_start_keyboard()
        )
        return

    # Обработка текстовых кнопок
    if text == "📋 Помощь" or text == "Помощь":
        send_help(peer_id)
        return
    if text == "📝  Регистрация по коду":
        send_message(peer_id, "Введите код регистрации в формате:\n/rcode <код>\nили\n/reg <код>")
        return
    if text == "🔑  Регистрация по токену":
        send_message(peer_id, "Отправьте ваш токен в формате:\n/reg <токен>")
        return
    if text == "💬  Отзывы":
        send_message(peer_id, f"💬  Оставить отзыв о боте можно здесь:\n{REVIEWS_LINK}")
        return
    if text == "💡  Идеи":
        send_message(peer_id, f"💡  Предложить идею для бота можно здесь:\n{IDEAS_LINK}")
        return

    # Команды с префиксом '/'
    if not text.startswith('/'):
        return

    parts = text[1:].split()
    command = parts[0].lower()
    args = parts[1:]

    # ===== /help =====
    if command == 'help':
        send_help(peer_id)
        return

    # ===== /отзывы =====
    if command == 'отзывы':
        send_message(peer_id, f"💬  Оставить отзыв о боте можно здесь:\n{REVIEWS_LINK}")
        return

    # ===== /идеи =====
    if command == 'идеи':
        send_message(peer_id, f"💡  Предложить идею для бота можно здесь:\n{IDEAS_LINK}")
        return

    # ===== /rcode (регистрация по коду или создание кода админом) =====
    if command == 'rcode':
        # Админ может создать код: /rcode <роль> [кол-во]
        if is_admin(user_id) and args:
            try:
                role = int(args[0])
                if role not in (0,1,2,3,4):
                    raise ValueError
                uses = 1
if len(args) >= 2:
                    uses = int(args[1])
                    if uses < 1:
                        raise ValueError
                code = generate_reg_code(role, uses, user_id)
                send_message(peer_id, f"✅ Код регистрации создан: {code}\nРоль: {role}, использований: {uses}")
                return
            except:
                pass  # если не число, возможно это код для регистрации

        # Регистрация по коду
        if args:
            code = args[0]
            cursor.execute('SELECT role, uses FROM reg_codes WHERE code=?', (code,))
            code_row = cursor.fetchone()
            if code_row:
                role = code_row[0]
                uses = code_row[1]
                if not db_get_user(user_id):
                    db_create_user(user_id, role=role)
                else:
                    db_update_user(user_id, role=role)
                if uses > 1:
                    cursor.execute('UPDATE reg_codes SET uses=? WHERE code=?', (uses-1, code))
                else:
                    cursor.execute('DELETE FROM reg_codes WHERE code=?', (code,))
                conn.commit()
                send_message(peer_id, f"✅ Регистрация прошла успешно! Ваша роль: {role}")
            else:
                send_message(peer_id, "❌ Неверный код регистрации.")
        else:
            send_message(peer_id, "Использование: /rcode <код> для регистрации или /rcode <роль> <кол-во> для создания кода (только админ).")
        return

    # ===== /reg (регистрация по токену или по коду) =====
    if command == 'reg':
        if not args:
            send_message(peer_id, "Использование:\n/reg <токен> — регистрация по токену\n/reg <код> — регистрация по коду")
            return

        value = args[0]
        if value.startswith('vk1.a.') or len(value) > 50:
            # Токен
            if not db_get_user(user_id):
                db_create_user(user_id, access_token=value, role=0)
            else:
                db_update_user(user_id, access_token=value)
            send_message(peer_id, "✅ Регистрация по токену прошла успешно! Токен сохранён.")
        else:
            # Код
            cursor.execute('SELECT role, uses FROM reg_codes WHERE code=?', (value,))
            code_row = cursor.fetchone()
            if code_row:
                role = code_row[0]
                uses = code_row[1]
                if not db_get_user(user_id):
                    db_create_user(user_id, role=role)
                else:
                    db_update_user(user_id, role=role)
                if uses > 1:
                    cursor.execute('UPDATE reg_codes SET uses=? WHERE code=?', (uses-1, value))
                else:
                    cursor.execute('DELETE FROM reg_codes WHERE code=?', (value,))
                conn.commit()
                send_message(peer_id, f"✅ Регистрация по коду прошла успешно! Ваша роль: {role}")
            else:
                send_message(peer_id, "❌ Неверный код регистрации.")
        return

    # Неизвестная команда
    send_message(peer_id, "❓ Неизвестная команда. Используйте /help для списка.")

def send_help(peer_id):
    help_text = (
        "📋 Список команд:\n\n"
        "🔑  Регистрация:\n"
        "/rcode <код> — регистрация по коду\n"
        "/reg <токен> — регистрация по токену\n"
        "/reg <код> — регистрация по коду (альтернатива)\n\n"
        "ℹ️  Информация:\n"
        "/help — эта справка\n"
        "/отзывы — ссылка на обсуждение отзывов\n"
        "/идеи — ссылка на обсуждение идей\n\n"
        "👨‍💼  Для администраторов:\n"
        "/rcode <роль> [кол-во] — создать код регистрации\n\n"
        "Вы также можете использовать кнопки ниже."
    )
    send_message(peer_id, help_text, keyboard=get_main_keyboard())

# ========== ЗАПУСК ==========
print("Бот сообщества запущен. Ожидание сообщений...")
for event in longpoll.listen():
    try:
        process_event(event)
    except Exception as e:
        print(f"Ошибка: {e}")
14:03
try:
            if event.type == VkBotEventType.MESSAGE_NEW:
                send_message(event.object.message['peer_id'], f"⚠️  Произошла ошибка: {e}")
        except:
            pass






