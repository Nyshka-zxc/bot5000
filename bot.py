import vk_api
from vk_api.longpoll import VkLongPoll, VkEventType
from vk_api.utils import get_random_id
from vk_api import VkUpload
import requests
import sqlite3
import random
import time
import datetime
import re
import json
import os
import io
import math
import sys
import subprocess
import secrets
import threading
import textwrap
from PIL import Image, ImageDraw, ImageFont, ImageOps

# ================= КОНФИГУРАЦИЯ =================
USER_TOKEN = 'vk1.a.-skjA_qahwjDiig9rqTCTv37LhrNZxdmNvpJpfU0CSMvz-glB0brCdw1VkLk6ZVLOYPsL7h5b7kYORIS5ga5NKHCNFKoRYgU1hV_RgWXjUqaFjl2M5d2i-lwtiGmGYRLV-pvf-6b7_27ztOgrRC67z2Fys0NNJcXtIlltt2tDVfUSe-X3uj5d_ilHghBh2LLxd2ae1INY5CesZwxG-nukQ'
WEATHER_API_KEY = 'ac9cd4dc68922ec268a27655f9e03af2'
OWNER_ID = 1116380571
ADMIN_IDS = [1116380571]  # Добавьте сюда ID других доверенных администраторов, если нужно
DEFAULT_PREFIX = '/'
DB_FILE = 'bot.db'
IMAGES_DIR = 'images'
TEMPLATES_DIR = 'templates'

# ===== НАСТРОЙКИ GPT API =====
GPT_API_KEY = 'sk-RLbhraB12P6rLJjEFTZyjzzlLEOXbEKg'
GPT_API_URL = "https://routerai.ru/api/v1/chat/completions"
GPT_MODEL = "gpt-3.5-turbo"

# ===== API ДЛЯ КУРСОВ ВАЛЮТ =====
EXCHANGE_API_KEY = '10f01d7c62ada0e2dc550445'

BAD_WORDS = ['мат', 'хуй', 'пизда', 'бля', 'сука', 'говно', 'мудак', 'нахуй', 'пидр', 'еблан']

ANECDOTES = [
    "Штирлиц склонился над картой СССР. Его неудержимо рвало на родину.",
    "Купил мужик шляпу, а она ему как раз.",
    "Один друг спрашивает другого: - Ты чего такой грустный? - Да вот, жена уехала. - А чего грустить? - Так я ее люблю!",
    "Объявление: Продам котят. Не дорого. Дорого только корм для них.",
    "Парадокс: в России два беды - дураки и дороги. Но если их соединить, получатся выборы."
]

# ================= ИНИЦИАЛИЗАЦИЯ VK =================
vk_session = vk_api.VkApi(token=USER_TOKEN)
vk = vk_session.get_api()
uploader = VkUpload(vk_session)
longpoll = VkLongPoll(vk_session)

# Добавляем глобальную блокировку для защиты от гонки потоков
vk_lock = threading.Lock()

# Глобальные структуры для self-bot'ов
user_sessions = {}   # user_id -> vk_api.VkApi
user_threads = {}    # user_id -> threading.Thread

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
        is_disabled INTEGER DEFAULT 0,
        herzog_expiry REAL DEFAULT 0,
        last_message_time REAL DEFAULT 0,
        warning_count INTEGER DEFAULT 0,
        birthday TEXT DEFAULT '',
        clan_id INTEGER DEFAULT NULL,
        poker_koins INTEGER DEFAULT 0
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
        name TEXT PRIMARY KEY,
        attachment TEXT
    );
    CREATE TABLE IF NOT EXISTS custom_shab (
        name TEXT PRIMARY KEY,
        text TEXT
    );
    CREATE TABLE IF NOT EXISTS chat_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER,
        user_id INTEGER,
        message TEXT,
        timestamp REAL
    );
    CREATE TABLE IF NOT EXISTS warnings (
        user_id INTEGER,
        chat_id INTEGER,
        count INTEGER DEFAULT 0,
        last_warning_time REAL,
        PRIMARY KEY (user_id, chat_id)
    );
    CREATE TABLE IF NOT EXISTS birthdays (
        user_id INTEGER PRIMARY KEY,
        birth_date TEXT,
        chat_id INTEGER
    );
    CREATE TABLE IF NOT EXISTS clans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,
        leader_id INTEGER,
        balance_btc INTEGER DEFAULT 0,
        balance_dofamin INTEGER DEFAULT 0,
        created_at REAL
    );
    CREATE TABLE IF NOT EXISTS clan_members (
        clan_id INTEGER,
        user_id INTEGER PRIMARY KEY,
        role TEXT DEFAULT 'member',
        joined_at REAL
    );
    CREATE TABLE IF NOT EXISTS command_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        command TEXT,
        args TEXT,
        chat_id INTEGER,
        timestamp REAL
    );
    CREATE TABLE IF NOT EXISTS banned_commands (
        command TEXT PRIMARY KEY,
        banned_by INTEGER,
        banned_at REAL
    );
    CREATE TABLE IF NOT EXISTS poker_state (
        id INTEGER PRIMARY KEY CHECK (id=1),
        rate REAL DEFAULT 0.001,
        last_update REAL DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS families (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,
        leader_id INTEGER,
        balance_btc INTEGER DEFAULT 0,
        balance_dofamin INTEGER DEFAULT 0,
        created_at REAL
    );
    CREATE TABLE IF NOT EXISTS family_members (
        family_id INTEGER,
        user_id INTEGER PRIMARY KEY,
        role TEXT DEFAULT 'member',
        joined_at REAL
    );
    CREATE TABLE IF NOT EXISTS marriages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user1 INTEGER,
        user2 INTEGER,
        created_at REAL,
        UNIQUE(user1),
        UNIQUE(user2)
    );
    ''')
    conn.commit()
    # Миграция, если таблица уже существовала без poker_koins
    try:
        cursor.execute('ALTER TABLE users ADD COLUMN poker_koins INTEGER DEFAULT 0')
        conn.commit()
    except:
        pass
    cursor.execute('INSERT OR IGNORE INTO poker_state (id, rate, last_update) VALUES (1, 0.001, ?)', (time.time(),))
    conn.commit()
    # Создание папок, если их нет
    os.makedirs(IMAGES_DIR, exist_ok=True)
    os.makedirs(os.path.join(IMAGES_DIR, 'tyan'), exist_ok=True)
    os.makedirs(os.path.join(IMAGES_DIR, 'legs'), exist_ok=True)
    os.makedirs(os.path.join(IMAGES_DIR, 'gort'), exist_ok=True)
    os.makedirs(TEMPLATES_DIR, exist_ok=True)

init_db()

# ================= ФУНКЦИИ ДЛЯ РАБОТЫ С БД =================
def db_get_user(user_id):
    cursor.execute('SELECT * FROM users WHERE user_id=?', (user_id,))
    return cursor.fetchone()

def db_create_user(user_id, access_token=None):
    if not db_get_user(user_id):
        role = 5 if user_id in ADMIN_IDS else 0
        cursor.execute('INSERT INTO users (user_id, access_token, role, registered_at) VALUES (?,?,?,?)',
                       (user_id, access_token, role, time.time()))
        conn.commit()
        cursor.execute('INSERT INTO history (user_id, action, timestamp) VALUES (?,?,?)', (user_id, 'Регистрация', time.time()))
        conn.commit()

def db_update_user(user_id, **kwargs):
    keys = ', '.join(f'{k}=?' for k in kwargs)
    values = list(kwargs.values()) + [user_id]
    cursor.execute(f'UPDATE users SET {keys} WHERE user_id=?', values)
    conn.commit()

def get_user_api(user_id):
    row = db_get_user(user_id)
    if not row or not row[1]:
        return None
    try:
        session = vk_api.VkApi(token=row[1])
        api = session.get_api()
        api.users.get(user_ids=user_id)  # проверка токена
        return api
    except:
        return None

def is_creator(user_id):
    return user_id in ADMIN_IDS or get_role(user_id) >= 5

def get_role(user_id):
    row = db_get_user(user_id)
    return row[2] if row else 0

def is_admin(user_id):
    return user_id in ADMIN_IDS or get_role(user_id) >= 4

def is_emperor(user_id):
    return user_id in ADMIN_IDS or get_role(user_id) >= 3

def is_prince(user_id):
    return user_id in ADMIN_IDS or get_role(user_id) >= 2

def is_elite(user_id):
    return user_id in ADMIN_IDS or get_role(user_id) >= 1

def get_reply_message(event):
    return getattr(event, 'reply_message', None)

def get_target_and_clean_args(event, args):
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
    field_map = {'dofamin': 8, 'steal': 9, 'prize': 10}
    last_time = row[field_map[action]]
    return (time.time() - last_time) >= cooldown_seconds

def update_cooldown(user_id, action):
    field_map = {'dofamin': 'last_dofamin_time', 'steal': 'last_steal_time', 'prize': 'last_prize_time'}
    db_update_user(user_id, **{field_map[action]: time.time()})

def send_message(peer_id, message, attachment=None):
    vk.messages.send(peer_id=peer_id, message=message, attachment=attachment, random_id=get_random_id())

def download_photo(url):
    response = requests.get(url)
    if response.status_code == 200:
        return response.content
    return None

def get_user_info(user_id, fields='photo_max_orig,status,counters,friend_status,online,sticker_count'):
    try:
        info = vk.users.get(user_ids=user_id, fields=fields)
        if info:
            return info[0]
    except:
        pass
    return None

def get_user_avatar(user_id):
    info = get_user_info(user_id, fields='photo_max_orig')
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
        photo = uploader.photo_messages(photo_path, peer_id=peer_id)[0]
        return f"photo{photo['owner_id']}_{photo['id']}"
    except Exception as e:
        print(f"Ошибка загрузки фото: {e}")
        return None

def upload_photo_bytes_to_vk(peer_id, photo_bytes, filename='photo.png'):
    import tempfile
    fd, tmp_path = tempfile.mkstemp(suffix='.png')
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(photo_bytes)
        return upload_photo_to_vk(peer_id, tmp_path)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

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

def log_command(user_id, command, args, chat_id):
    cursor.execute('INSERT INTO command_logs (user_id, command, args, chat_id, timestamp) VALUES (?,?,?,?,?)',
                   (user_id, command, ' '.join(args), chat_id, time.time()))
    conn.commit()

def get_command_logs(limit=20, since=None):
    if since:
        cursor.execute('SELECT user_id, command, args, chat_id, timestamp FROM command_logs WHERE timestamp >= ? ORDER BY timestamp DESC LIMIT ?', (since, limit))
    else:
        cursor.execute('SELECT user_id, command, args, chat_id, timestamp FROM command_logs ORDER BY timestamp DESC LIMIT ?', (limit,))
    return cursor.fetchall()

def is_command_banned(cmd):
    cursor.execute('SELECT 1 FROM banned_commands WHERE command=?', (cmd,))
    return cursor.fetchone() is not None

def ban_command(cmd, banned_by):
    cursor.execute('INSERT OR IGNORE INTO banned_commands (command, banned_by, banned_at) VALUES (?,?,?)', (cmd, banned_by, time.time()))
    conn.commit()

def unban_command(cmd):
    cursor.execute('DELETE FROM banned_commands WHERE command=?', (cmd,))
    conn.commit()

def looks_like_token(s):
    return isinstance(s, str) and len(s) > 80 and s.startswith('vk1.a.')

def extract_user_id_from_link(link):
    if not link:
        return None
    m = re.search(r'vk\.com/id(\d+)', link)
    if m:
        return int(m.group(1))
    m = re.search(r'vk\.com/([A-Za-z0-9_.]+)', link)
    if m:
        try:
            resolved = vk.utils.resolveScreenName(screen_name=m.group(1))
            if resolved and resolved.get('type') == 'user':
                return int(resolved['object_id'])
        except:
            pass
        try:
            info = vk.users.get(user_ids=m.group(1))
            if info:
                return info[0]['id']
        except:
            pass
    return None

def get_all_mentioned_ids(event, args):
    ids = []
    reply = get_reply_message(event)
    if reply:
        ids.append(reply['from_id'])
    text = event.text or ''
    for m in re.finditer(r'\[id(\d+)\|', text):
        ids.append(int(m.group(1)))
    for m in re.finditer(r'@id(\d+)', text):
        ids.append(int(m.group(1)))
    for arg in args:
        if 'vk.com/' in arg:
            uid = extract_user_id_from_link(arg)
            if uid:
                ids.append(uid)
    unique = []
    for i in ids:
        if i not in unique:
            unique.append(i)
    return unique

# ================= ФУНКЦИИ GPT =================
def ask_gpt(question, system_prompt="Вы - полезный ассистент в VK боте. Отвечайте кратко и по делу на русском языке."):
    if GPT_API_KEY == 'ВАШ_КЛЮЧ_OPENAI_API':
        return "❌ Ошибка: Не установлен API ключ GPT."
    try:
        headers = {"Authorization": f"Bearer {GPT_API_KEY}", "Content-Type": "application/json"}
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
        return "❌ Ошибка: Время ожидания истекло."
    except Exception as e:
        return f"❌ Ошибка при обращении к GPT: {str(e)}"

# ================= ФУНКЦИИ КУРСОВ ВАЛЮТ =================
def get_exchange_rate(from_currency, to_currency='RUB'):
    url = f"https://v6.exchangerate-api.com/v6/{EXCHANGE_API_KEY}/latest/{from_currency}"
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        if 'conversion_rates' in data:
            rate = data['conversion_rates'].get(to_currency)
            if rate:
                return rate
    except:
        pass
    return None

def get_crypto_price(symbol):
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={symbol}&vs_currencies=rub"
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        if symbol in data:
            return data[symbol]['rub']
    except:
        pass
    return None

# ================= POKER KOIN =================
def get_poker_rate():
    cursor.execute('SELECT rate, last_update FROM poker_state WHERE id=1')
    row = cursor.fetchone()
    if row:
        rate, last_update = row
        if time.time() - last_update > 3600:
            update_poker_rate()
            cursor.execute('SELECT rate FROM poker_state WHERE id=1')
            rate = cursor.fetchone()[0]
        return rate
    return 0.001

def update_poker_rate():
    cursor.execute('SELECT rate FROM poker_state WHERE id=1')
    row = cursor.fetchone()
    old = row[0] if row else 0.001
    change = random.uniform(-0.1, 0.1)
    new_rate = max(0.00001, old * (1 + change))
    cursor.execute('UPDATE poker_state SET rate=?, last_update=? WHERE id=1', (new_rate, time.time()))
    conn.commit()
    return new_rate

# ================= КЛАНЫ =================
def add_clan(name, leader_id):
    cursor.execute('INSERT INTO clans (name, leader_id, created_at) VALUES (?,?,?)', (name, leader_id, time.time()))
    conn.commit()
    clan_id = cursor.lastrowid
    cursor.execute('INSERT INTO clan_members (clan_id, user_id, role) VALUES (?,?,?)', (clan_id, leader_id, 'leader'))
    conn.commit()
    return clan_id

def get_clan_by_user(user_id):
    cursor.execute('SELECT clan_id FROM clan_members WHERE user_id=?', (user_id,))
    row = cursor.fetchone()
    return row[0] if row else None

def get_clan_info(clan_id):
    cursor.execute('SELECT * FROM clans WHERE id=?', (clan_id,))
    return cursor.fetchone()

def get_clan_members(clan_id):
    cursor.execute('SELECT user_id, role FROM clan_members WHERE clan_id=?', (clan_id,))
    return cursor.fetchall()

def join_clan(user_id, clan_id):
    cursor.execute('INSERT OR IGNORE INTO clan_members (clan_id, user_id, role) VALUES (?,?,?)', (clan_id, user_id, 'member'))
    conn.commit()

def leave_clan(user_id):
    cursor.execute('DELETE FROM clan_members WHERE user_id=?', (user_id,))
    conn.commit()

def get_all_clans():
    cursor.execute('SELECT id, name, leader_id, balance_btc, balance_dofamin FROM clans')
    return cursor.fetchall()

def update_clan_balance(clan_id, btc_add=0, dof_add=0):
    cursor.execute('UPDATE clans SET balance_btc = balance_btc + ?, balance_dofamin = balance_dofamin + ? WHERE id=?', (btc_add, dof_add, clan_id))
    conn.commit()

# ================= СЕМЬИ =================
def create_family(name, leader_id):
    if get_family_by_user(leader_id):
        return None
    cursor.execute('INSERT INTO families (name, leader_id, created_at) VALUES (?,?,?)', (name, leader_id, time.time()))
    conn.commit()
    fid = cursor.lastrowid
    cursor.execute('INSERT INTO family_members (family_id, user_id, role) VALUES (?,?,?)', (fid, leader_id, 'leader'))
    conn.commit()
    return fid

def get_family_by_user(user_id):
    cursor.execute('SELECT family_id FROM family_members WHERE user_id=?', (user_id,))
    row = cursor.fetchone()
    return row[0] if row else None

def get_family_info(fid):
    cursor.execute('SELECT * FROM families WHERE id=?', (fid,))
    return cursor.fetchone()

def get_family_members(fid):
    cursor.execute('SELECT user_id, role FROM family_members WHERE family_id=?', (fid,))
    return cursor.fetchall()

def join_family(user_id, fid):
    members = get_family_members(fid)
    if len(members) >= 6:
        return False
    cursor.execute('INSERT OR IGNORE INTO family_members (family_id, user_id, role) VALUES (?,?,?)', (fid, user_id, 'member'))
    conn.commit()
    return True

def leave_family(user_id):
    cursor.execute('DELETE FROM family_members WHERE user_id=?', (user_id,))
    conn.commit()

def delete_family(fid):
    cursor.execute('DELETE FROM families WHERE id=?', (fid,))
    cursor.execute('DELETE FROM family_members WHERE family_id=?', (fid,))
    conn.commit()

def get_all_families():
    cursor.execute('SELECT id, name, leader_id, balance_btc, balance_dofamin FROM families')
    return cursor.fetchall()

def update_family_balance(fid, btc=0, dof=0):
    cursor.execute('UPDATE families SET balance_btc = balance_btc + ?, balance_dofamin = balance_dofamin + ? WHERE id=?', (btc, dof, fid))
    conn.commit()

# ================= БРАКИ =================
def create_marriage(u1, u2):
    if get_marriage(u1) or get_marriage(u2):
        return False
    cursor.execute('INSERT INTO marriages (user1, user2, created_at) VALUES (?,?,?)', (u1, u2, time.time()))
    conn.commit()
    return True

def get_marriage(user_id):
    cursor.execute('SELECT * FROM marriages WHERE user1=? OR user2=?', (user_id, user_id))
    return cursor.fetchone()

def delete_marriage(user_id):
    cursor.execute('DELETE FROM marriages WHERE user1=? OR user2=?', (user_id, user_id))
    conn.commit()

def delete_marriage_pair(u1, u2):
    cursor.execute('DELETE FROM marriages WHERE (user1=? AND user2=?) OR (user1=? AND user2=?)', (u1, u2, u2, u1))
    conn.commit()

# ================= ДНИ РОЖДЕНИЯ =================
def get_birthday(user_id):
    cursor.execute('SELECT birth_date, chat_id FROM birthdays WHERE user_id=?', (user_id,))
    return cursor.fetchone()

def set_birthday(user_id, date, chat_id):
    cursor.execute('INSERT OR REPLACE INTO birthdays (user_id, birth_date, chat_id) VALUES (?,?,?)', (user_id, date, chat_id))
    conn.commit()

def get_today_birthdays():
    today = datetime.datetime.now().strftime('%d.%m')
    cursor.execute('SELECT user_id, chat_id FROM birthdays WHERE birth_date=?', (today,))
    return cursor.fetchall()

# ================= ИСТОРИЯ ЧАТА =================
def save_chat_message(chat_id, user_id, message):
    cursor.execute('INSERT INTO chat_history (chat_id, user_id, message, timestamp) VALUES (?,?,?,?)', (chat_id, user_id, message, time.time()))
    conn.commit()
    cursor.execute('DELETE FROM chat_history WHERE id IN (SELECT id FROM chat_history WHERE chat_id=? ORDER BY timestamp DESC LIMIT -1 OFFSET 1000)', (chat_id,))
    conn.commit()

def search_chat_history(chat_id, query):
    cursor.execute('SELECT user_id, message, timestamp FROM chat_history WHERE chat_id=? AND message LIKE ? ORDER BY timestamp DESC LIMIT 10', (chat_id, f'%{query}%'))
    return cursor.fetchall()

# ================= МОДЕРАЦИЯ =================
def check_moderation(user_id, chat_id, message):
    for word in BAD_WORDS:
        if word.lower() in message.lower():
            cursor.execute('INSERT INTO warnings (user_id, chat_id, count, last_warning_time) VALUES (?,?,1,?) ON CONFLICT(user_id, chat_id) DO UPDATE SET count=count+1, last_warning_time=?', (user_id, chat_id, time.time(), time.time()))
            conn.commit()
            cursor.execute('SELECT count FROM warnings WHERE user_id=? AND chat_id=?', (user_id, chat_id))
            count = cursor.fetchone()[0]
            if count >= 3:
                expires = time.time() + 86400
                cursor.execute('INSERT OR REPLACE INTO bans (user_id, reason, expires_at, banned_by) VALUES (?,?,?,?)', (user_id, 'Автоматический бан за мат (3 предупреждения)', expires, OWNER_ID))
                conn.commit()
                send_message(chat_id, f'⚠️ Пользователь {user_id} автоматически забанен за мат.')
            else:
                send_message(chat_id, f'⚠️ Предупреждение {count}/3. Не материтесь!')
            break
    row = db_get_user(user_id)
    if row:
        last_time = row[16]  # last_message_time
        if last_time and time.time() - last_time < 10:
            cursor.execute('SELECT COUNT(*) FROM chat_history WHERE user_id=? AND chat_id=? AND timestamp > ?', (user_id, chat_id, time.time()-10))
            cnt = cursor.fetchone()[0]
            if cnt > 5:
                expires = time.time() + 3600
                cursor.execute('INSERT OR REPLACE INTO bans (user_id, reason, expires_at, banned_by) VALUES (?,?,?,?)', (user_id, 'Автоматический бан за спам', expires, OWNER_ID))
                conn.commit()
                send_message(chat_id, f'⚠️ Пользователь {user_id} автоматически забанен за спам.')
        db_update_user(user_id, last_message_time=time.time())

# ================= ГЕНЕРАЦИЯ ИЗОБРАЖЕНИЙ =================
def generate_meme(text_top, text_bottom):
    template_path = get_random_image(TEMPLATES_DIR)
    if not template_path:
        return None
    img = Image.open(template_path)
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", size=40)
    except:
        font = ImageFont.load_default()
    img_w, img_h = img.size
    if text_top:
        draw.text((img_w/2, 20), text_top, fill='white', font=font, anchor='mt', stroke_width=2, stroke_fill='black')
    if text_bottom:
        draw.text((img_w/2, img_h-20), text_bottom, fill='white', font=font, anchor='mb', stroke_width=2, stroke_fill='black')
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return buf

def generate_profile_card(user_id):
    info = get_user_info(user_id)
    if not info:
        return None
    name = f"{info['first_name']} {info['last_name']}"
    avatar_url = info.get('photo_max_orig')
    avatar = None
    if avatar_url:
        avatar_data = download_photo(avatar_url)
        if avatar_data:
            avatar = Image.open(io.BytesIO(avatar_data)).resize((200, 200))
    card = Image.new('RGB', (600, 400), color=(30, 30, 40))
    draw = ImageDraw.Draw(card)
    try:
        font_big = ImageFont.truetype("arial.ttf", size=28)
        font_small = ImageFont.truetype("arial.ttf", size=18)
    except:
        font_big = ImageFont.load_default()
        font_small = ImageFont.load_default()
    draw.rectangle([10, 10, 590, 390], outline=(100, 100, 200), width=3)
    if avatar:
        card.paste(avatar, (30, 30))
    else:
        draw.ellipse([30, 30, 230, 230], outline=(200, 200, 200), width=2)
    row = db_get_user(user_id)
    role_names = {0: 'Участник', 1: 'Элита', 2: 'Князь', 3: 'Император', 4: 'Админ', 5: 'Создатель'}
    if row:
        btc = row[3]
        dof = row[4]
        stars = row[11]
        poker = row[20]
        role = role_names.get(row[2], 'Неизвестно')
        herzog = '👑 Да' if row[5] else ('⏳ Временно' if row[15] > time.time() else '❌ Нет')
        protection = '🛡️ Да' if row[6] else '❌ Нет'
        reg_ts = row[7]
        reg_str = datetime.datetime.fromtimestamp(reg_ts).strftime('%d.%m.%Y') if reg_ts else '—'
    else:
        btc = dof = stars = poker = 0
        role = 'Не зарегистрирован'
        herzog = protection = '❌'
        reg_str = '—'
    clan_id = get_clan_by_user(user_id)
    clan_name = 'Без клана'
    if clan_id:
        clan_info = get_clan_info(clan_id)
        clan_name = clan_info[1] if clan_info else 'Без клана'
    marriage = get_marriage(user_id)
    partner_name = 'Нет'
    if marriage:
        partner_id = marriage[1] if marriage[1] != user_id else marriage[2]
        p_info = get_user_info(partner_id)
        partner_name = f"{p_info['first_name']} {p_info['last_name']}" if p_info else str(partner_id)
    family_id = get_family_by_user(user_id)
    family_name = 'Нет'
    if family_id:
        fi = get_family_info(family_id)
        family_name = fi[1] if fi else 'Нет'

    draw.text((260, 40), name, fill=(255, 255, 255), font=font_big)
    draw.text((260, 90), f"Роль: {role}", fill=(200, 200, 200), font=font_small)
    draw.text((260, 130), f"💰 БТС: {btc}", fill=(255, 215, 0), font=font_small)
    draw.text((260, 170), f"🧪 Дофамин: {dof}", fill=(0, 255, 255), font=font_small)
    draw.text((260, 210), f"⭐ Звёзды: {stars}", fill=(255, 255, 0), font=font_small)
    draw.text((260, 250), f"🪙 PKR: {poker}", fill=(255, 200, 50), font=font_small)
    draw.text((260, 290), f"Герцог: {herzog}", fill=(255, 200, 150), font=font_small)
    draw.text((260, 330), f"Защита: {protection}", fill=(150, 255, 150), font=font_small)
    draw.text((260, 370), f"Клан: {clan_name}", fill=(200, 200, 255), font=font_small)
    draw.text((30, 250), f"Семья: {family_name}", fill=(200, 200, 255), font=font_small)
    draw.text((30, 290), f"Брак: {partner_name}", fill=(255, 180, 180), font=font_small)
    draw.text((30, 330), f"Регистрация: {reg_str}", fill=(150, 150, 150), font=font_small)
    buf = io.BytesIO()
    card.save(buf, format='PNG')
    buf.seek(0)
    return buf

def generate_quote_image(text):
    img = Image.new('RGB', (800, 400), color=(20, 20, 20))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", size=32)
    except:
        font = ImageFont.load_default()
    lines = textwrap.wrap(text, width=35)
    y = 50
    for line in lines:
        draw.text((400, y), line, fill=(255, 255, 255), font=font, anchor='mm')
        y += 40
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return buf

def generate_demotivator(text):
    img = Image.new('RGB', (600, 400), color=(0, 0, 0))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", size=40)
        small_font = ImageFont.truetype("arial.ttf", size=20)
    except:
        font = ImageFont.load_default()
        small_font = ImageFont.load_default()
    draw.rectangle([10, 10, 590, 390], outline=(255, 255, 255), width=3)
    draw.text((300, 150), text, fill=(255, 0, 0), font=font, anchor='mm')
    draw.text((300, 350), "Демотиватор", fill=(255, 255, 255), font=small_font, anchor='mm')
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return buf

# ================= ПЛАНИРОВЩИК =================
def birthday_checker():
    today_birthdays = get_today_birthdays()
    for user_id, chat_id in today_birthdays:
        try:
            user_info = get_user_info(user_id)
            name = f"{user_info['first_name']} {user_info['last_name']}" if user_info else str(user_id)
            send_message(chat_id, f"🎉 Сегодня день рождения у {name}! Поздравляем! 🎂")
        except:
            pass

def run_scheduler():
    while True:
        update_poker_rate()
        birthday_checker()
        time.sleep(3600)

scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
scheduler_thread.start()

# ================= ФУНКЦИЯ РАССЫЛКИ =================
def send_broadcast(message):
    cursor.execute('SELECT user_id FROM users WHERE is_disabled=0')
    users = cursor.fetchall()
    for u in users:
        try:
            vk.messages.send(peer_id=u[0], message=message, random_id=get_random_id())
            time.sleep(0.3)
        except:
            continue
# ================= SELF-BOT =================
def run_user_bot(user_id, token):
    """Запускает отдельный longpoll-поток для пользователя."""
    try:
        session = vk_api.VkApi(token=token)
        api = session.get_api()
        # Проверяем токен
        api.users.get(user_ids=user_id)
    except Exception as e:
        send_message(OWNER_ID, f"⚠️ Токен пользователя {user_id} невалиден: {e}")
        db_update_user(user_id, is_disabled=1, access_token=None)
        return

    user_sessions[user_id] = session
    print(f"Self-bot запущен для {user_id}")

    # Внутренняя функция обработки события self-bot
    def process_self_event(event):
        if not event.text:
            return
        # Определяем префикс (можно использовать из БД, но для простоты DEFAULT_PREFIX)
        prefix = DEFAULT_PREFIX  # или get_prefix(event.peer_id)
        if not event.text.startswith(prefix):
            return
        text = event.text[len(prefix):].strip()
        if not text:
            return
        parts = text.split()
        command = parts[0].lower()
        args = parts[1:]

        # Игнорируем команды, которые не должны выполняться в self-bot
        if command in ['restart', 'stop', 'запрет', 'разрешить', 'reg']:
            return

        # Добавляем ID владельца токена в событие, т.к. self-bot его не содержит
        event.user_id = user_id

        # Подменяем глобальные vk и uploader на сессию пользователя
        global vk, uploader
        old_vk, old_uploader = vk, uploader
        vk = api
        uploader = VkUpload(session)

        try:
            # Захватываем блокировку, чтобы не конфликтовать с основным ботом
            with vk_lock:
                process_command(event)
        except Exception as e:
            print(f"Ошибка в self-bot {user_id}: {e}")
            try:
                vk.messages.send(peer_id=event.peer_id, message=f"❌ Ошибка: {e}", random_id=get_random_id())
            except:
                pass
        finally:
            vk, uploader = old_vk, old_uploader

        # Проверка токена после команды
        try:
            api.users.get(user_ids=user_id)
        except Exception:
            send_message(OWNER_ID, f"⚠️ Токен пользователя {user_id} стал невалиден, self-bot остановлен.")
            db_update_user(user_id, is_disabled=1, access_token=None)
            user_sessions.pop(user_id, None)
            user_threads.pop(user_id, None)
            return

    # Запускаем longpoll для пользователя
    longpoll_user = VkLongPoll(session)
    print(f"Longpoll пользователя {user_id} запущен")
    for event in longpoll_user.listen():
        if event.type == VkEventType.MESSAGE_NEW:
            # Обрабатываем только исходящие сообщения (от самого пользователя)
            if not event.from_me:
                continue
            # Запускаем обработку в отдельном потоке, чтобы не блокировать longpoll
            threading.Thread(target=process_self_event, args=(event,), daemon=True).start()

def start_all_user_bots():
    """Запускает self-bot'ы для всех сохранённых пользователей с токенами."""
    # Локальное соединение, чтобы не конфликтовать с глобальным курсором
    local_conn = sqlite3.connect(DB_FILE)
    local_cursor = local_conn.cursor()
    local_cursor.execute(
        'SELECT user_id, access_token FROM users WHERE access_token IS NOT NULL AND is_disabled=0'
    )
    rows = local_cursor.fetchall()
    local_conn.close()

    for uid, token in rows:
        if uid not in user_threads or not user_threads[uid].is_alive():
            t = threading.Thread(target=run_user_bot, args=(uid, token), daemon=True)
            user_threads[uid] = t
            t.start()
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

    if command not in ['логи', 'запрет', 'разрешить']:
        log_command(user_id, command, args, chat_id)

    row = db_get_user(user_id)
    if not row:
        if user_id == OWNER_ID:
            db_create_user(user_id)
        elif command == 'reg':
            # Регистрация по токену обрабатывается здесь
            if len(args) < 1:
                if user_id == OWNER_ID:
                    send_message(event.peer_id, "Использование: /reg (токен)")
                return

            token = args[0]
            if not looks_like_token(token):
                if user_id == OWNER_ID:
                    send_message(event.peer_id, "❌ Неверный формат токена.")
                else:
                    send_message(OWNER_ID, f"⚠️ Пользователь {user_id} прислал неверный формат токена.")
                return

            # Проверяем токен и принадлежность
            try:
                session = vk_api.VkApi(token=token)
                api = session.get_api()
                token_info = api.users.get()[0]
                token_owner_id = token_info['id']
            except Exception as e:
                # Токен невалиден — уведомляем создателя, пользователю ничего
                send_message(OWNER_ID, f"⚠️ Пользователь {user_id} пытался зарегистрироваться с невалидным токеном: {e}")
                return

            if token_owner_id != user_id:
                # Чужой токен — уведомляем создателя, пользователю ничего
                send_message(OWNER_ID, f"⚠️ Пользователь {user_id} пытался использовать чужой токен (владелец {token_owner_id}).")
                return

            # Успешная регистрация
            db_create_user(user_id, access_token=token)

            # Запускаем self-bot
            if user_id in user_threads and user_threads[user_id].is_alive():
                user_sessions[user_id] = session
            else:
                t = threading.Thread(target=run_user_bot, args=(user_id, token), daemon=True)
                user_threads[user_id] = t
                t.start()

            # Отправляем подтверждение от имени пользователя
            try:
                api.messages.send(
                    peer_id=event.peer_id,
                    message="✅ Бот подключен к вашему аккаунту!",
                    random_id=get_random_id()
                )
            except Exception as e:
                send_message(OWNER_ID, f"⚠️ Не удалось отправить подтверждение пользователю {user_id}: {e}")
            return
        else:
            return

    if is_user_disabled(user_id) and not is_creator(user_id):
        send_message(event.peer_id, "⛔ Ваш доступ к боту отключён создателем.")
        return

    if not is_creator(user_id) and is_command_banned(command):
        send_message(event.peer_id, f"⛔ Команда '{command}' временно запрещена создателем.")
        return

    if command not in ['помощь', 'help', 'reg']:
        save_chat_message(chat_id, user_id, event.text)

    if event.from_chat:
        check_moderation(user_id, chat_id, event.text)

    # ===== ОБРАБОТКА КОМАНД =====
    if command == 'help':
        help_parts = [
            """📋 Список основных команд:
👤 /dox — открытая информация о человеке
🕵️ /doxelp — закрытая информация (Князь+)
📊 /стат — профиль в боте
🎰 /казино (ставка) (количество) — игра на БТС
💰 /выдатьбтс (ссылка/ответ) (кол-во) — выдать БТС (Админ+)
👑 /герцог — купить подписку Герцог (навсегда)
🎁 /выдгерцог — выдать Герцога (Админ+)
🧪 /дофамин — получить дофамин
🤫 /украстьдоф — украсть дофамин
🛡️ /защитадоф — купить защиту от кражи (500 БТС)
🖼️ /стикеры — посмотреть стикеры игрока
📨 /sp — отправить сообщение доверенным (или от вашего имени)
🚫 /unsp — убрать из доверенности
📩 /vls — отправить сообщение в ЛС
🤖 /ai (запрос) — спросить ИИ
🔗 /cc (ссылка) — сократить ссылку
➕ /+гс (название) — добавить ГС (ответьте на голосовое)
▶️ /гс (название) — воспроизвести ГС
📃 /гсы — список ГС
➖ /-гс (название) — удалить ГС
➕ /+шаб (название) (текст) — добавить шаблон
▶️ /шаб (название) — воспроизвести шаблон
📃 /шаблоны — список шаблонов
➖ /-шаб (название) — удалить шаблон
🔐 /подбор (0-10) — подбор паролей
📲 /+invaite — пригласить друзей в чат (использует ваш токен)
🛑 /-invaite — остановить приглашение
🔑 /password — подбор пароля
🌤️ /погода (город) — погода
🎱 /шар (вопрос) — магический шар
📝 /+описание (текст) — сменить статус VK (ваш, если сохранён токен)""",

            """🖼️ /аватарка — отправить аватар
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
📖 /helpr3 — команды ранга Император""",

            """🛒 /starshop — магазин за звёзды
🛒 /buy — купить товар (например: /buy бтс 100)
Новые товары: герцог_неделя, герцог_месяц

🏆 /топбтс — топ по БТС
🧪 /топдоф — топ по дофамину
👑 /герцоги — список обладателей Герцога
🛡️ /защищённые — список защищённых пользователей

🆕 Новые команды:
🪙 /монетка — подбросить монетку
📈 /курс USD (или EUR, BTC, PKR) — курс валюты
🎬 /мем (верхний текст) (нижний текст) — создать мем
🔍 /поиск (текст) — поиск в истории беседы
🏛️ /кланы создать (название) — создать клан
🏛️ /кланы вступить (название) — вступить в клан
🏛️ /кланы список — список всех кланов
🏛️ /кланы топ — топ кланов по балансу
🏛️ /кланы пополнить (сумма) — пополнить клановую казну
🎂 /др ДД.ММ — установить дату рождения
📋 /логи — показать последние команды (Админ+)
🚫 /запрет (команда) — запретить команду (только Создатель)
✅ /разрешить (команда) — разрешить команду (только Создатель)
🎨 /косметика — красивый профиль""",

            """👨‍👩‍👧‍👦 /семья (создать|вступить|выйти|список|инфо|пополнить) — семьи
💍 /жениться (ссылка/ответ) — вступить в брак
💔 /развестись — развестись
🔗 /свести (юзер1) (юзер2) — свести двух пользователей (Админ+)
💔 /развести (юзер1) (юзер2) — развести (Админ+)
🗑️ /удалитьсемью (создатель семьи) — удалить семью (Админ+)
🗑️ /удалитьклан (лидер клана) — удалить клан (Админ+)

🪙 Poker Koin:
/коин — баланс PKR
/купитькоин (кол-во) — купить PKR за BTC
/продатькоин (кол-во) — продать PKR за BTC
/+koin (кол-во) (ссылка/ответ) — выдать PKR (Админ+)
/-koin (кол-во) (ссылка/ответ) — забрать PKR (Админ+)
/alldelkoin — обнулить все PKR (Создатель)

🔧 Команды разработчика (Админ+):
🔄 /restart — перезапустить бота
🛑 /stop — остановить бота
🗑️ /сброс (токен/ID) — сбросить токен пользователя
🔍 /токен инфа (токен) — информация о токене
📨 /рассылка (текст) — массовая рассылка (Админ+)

🔧 Только для Создателя:
📋 /базаданных — список всех зарегистрированных пользователей
⛔ /отключение — отключить пользователя от бота
✅ /включение — включить пользователя обратно
➕ /+админ — назначить администратора
➖ /-админ — снять администратора"""
        ]

        for part in help_parts:
            send_message(event.peer_id, part)

    elif command == 'монетка':
        result = random.choice(['Орёл', 'Решка'])
        send_message(event.peer_id, f"🪙 Монетка подброшена! Выпал: **{result}**")

    elif command == 'курс':
        if not args:
            send_message(event.peer_id, "Использование: /курс USD (или EUR, BTC, PKR)")
            return
        currency = args[0].upper()
        if currency == 'BTC':
            price = get_crypto_price('bitcoin')
            if price:
                send_message(event.peer_id, f"💰 1 BTC = {price:.2f} RUB")
            else:
                send_message(event.peer_id, "❌ Не удалось получить курс биткоина.")
        elif currency == 'PKR':
            rate = get_poker_rate()
            send_message(event.peer_id, f"🪙 1 PKR = {rate:.6f} BTC")
        else:
            rate = get_exchange_rate(currency, 'RUB')
            if rate:
                send_message(event.peer_id, f"💰 1 {currency} = {rate:.2f} RUB")
            else:
                send_message(event.peer_id, "❌ Не удалось получить курс.")

    elif command == 'мем':
        if len(args) < 2:
            send_message(event.peer_id, "Использование: /мем (верхний текст) (нижний текст)")
            return
        text_top = args[0] if len(args) > 0 else ''
        text_bottom = args[1] if len(args) > 1 else ''
        buf = generate_meme(text_top, text_bottom)
        if not buf:
            send_message(event.peer_id, "❌ Нет шаблонов для мемов. Создайте папку templates и добавьте изображения.")
            return
        attachment = upload_photo_bytes_to_vk(event.peer_id, buf.getvalue(), 'meme.png')
        if attachment:
            send_message(event.peer_id, attachment=attachment)
        else:
            send_message(event.peer_id, "❌ Ошибка загрузки фото.")

    elif command == 'поиск':
        if not args:
            send_message(event.peer_id, "Использование: /поиск (текст)")
            return
        query = ' '.join(args)
        results = search_chat_history(chat_id, query)
        if not results:
            send_message(event.peer_id, "Ничего не найдено.")
            return
        msg = "🔍 Результаты поиска:\n"
        for uid, message, ts in results:
            user_info = get_user_info(uid)
            name = f"{user_info['first_name']} {user_info['last_name']}" if user_info else str(uid)
            time_str = datetime.datetime.fromtimestamp(ts).strftime('%H:%M')
            msg += f"{time_str} {name}: {message[:50]}...\n"
        send_message(event.peer_id, msg)

    elif command == 'рассылка':
        if not is_admin(user_id):
            send_message(event.peer_id, "⛔ Недостаточно прав.")
            return
        if not args:
            send_message(event.peer_id, "Использование: /рассылка (текст)")
            return
        msg = ' '.join(args)
        send_broadcast(msg)
        send_message(event.peer_id, "✅ Рассылка выполнена.")

    elif command == 'др':
        if len(args) < 1:
            send_message(event.peer_id, "Использование: /др ДД.ММ (например, /др 01.01)")
            return
        date = args[0]
        if not re.match(r'\d{2}\.\d{2}', date):
            send_message(event.peer_id, "❌ Неверный формат. Используйте ДД.ММ")
            return
        set_birthday(user_id, date, chat_id)
        send_message(event.peer_id, f"✅ Дата рождения сохранена: {date}.")

    elif command == 'кланы':
        if not args:
            send_message(event.peer_id, "Использование: /кланы (создать|вступить|список|топ|пополнить)")
            return
        subcmd = args[0].lower()
        if subcmd == 'создать':
            if len(args) < 2:
                send_message(event.peer_id, "Укажите название клана.")
                return
            name = ' '.join(args[1:])
            cursor.execute('SELECT id FROM clans WHERE name=?', (name,))
            if cursor.fetchone():
                send_message(event.peer_id, "❌ Клан с таким названием уже существует.")
                return
            if get_clan_by_user(user_id):
                send_message(event.peer_id, "❌ Вы уже состоите в клане.")
                return
            clan_id = add_clan(name, user_id)
            send_message(event.peer_id, f"✅ Клан '{name}' создан! Вы лидер.")
        elif subcmd == 'вступить':
            if len(args) < 2:
                send_message(event.peer_id, "Укажите название клана.")
                return
            name = ' '.join(args[1:])
            cursor.execute('SELECT id FROM clans WHERE name=?', (name,))
            row = cursor.fetchone()
            if not row:
                send_message(event.peer_id, "❌ Клан не найден.")
                return
            clan_id = row[0]
            if get_clan_by_user(user_id):
                send_message(event.peer_id, "❌ Вы уже в клане.")
                return
            join_clan(user_id, clan_id)
            send_message(event.peer_id, f"✅ Вы вступили в клан '{name}'.")
        elif subcmd == 'список':
            clans = get_all_clans()
            if not clans:
                send_message(event.peer_id, "Нет созданных кланов.")
                return
            msg = "🏛️ Список кланов:\n"
            for c in clans:
                msg += f"• {c[1]} (лидер: {c[2]}, БТС: {c[3]}, Дофамин: {c[4]})\n"
            send_message(event.peer_id, msg)
        elif subcmd == 'топ':
            clans = get_all_clans()
            if not clans:
                send_message(event.peer_id, "Нет кланов.")
                return
            clans_sorted = sorted(clans, key=lambda x: x[3]+x[4], reverse=True)
            msg = "🏆 Топ кланов:\n"
            for i, c in enumerate(clans_sorted[:10], 1):
                msg += f"{i}. {c[1]} — БТС: {c[3]}, Дофамин: {c[4]}\n"
            send_message(event.peer_id, msg)
        elif subcmd == 'пополнить':
            if len(args) < 2:
                send_message(event.peer_id, "Укажите сумму (БТС).")
                return
            try:
                amount = int(args[1])
                if amount <= 0:
                    raise ValueError
            except:
                send_message(event.peer_id, "❌ Неверная сумма.")
                return
            clan_id = get_clan_by_user(user_id)
            if not clan_id:
                send_message(event.peer_id, "❌ Вы не состоите в клане.")
                return
            row = db_get_user(user_id)
            if row[3] < amount:
                send_message(event.peer_id, f"❌ У вас недостаточно БТС (нужно {amount}).")
                return
            db_update_user(user_id, btc=row[3]-amount)
            update_clan_balance(clan_id, btc_add=amount)
            send_message(event.peer_id, f"✅ Вы пополнили клан на {amount} БТС.")
        else:
            send_message(event.peer_id, "Неизвестная подкоманда.")

    elif command == 'семья':
        if not args:
            send_message(event.peer_id, "Использование: /семья (создать|вступить|выйти|список|инфо|пополнить)")
            return
        sub = args[0].lower()
        if sub == 'создать':
            if len(args) < 2:
                send_message(event.peer_id, "Укажите название семьи.")
                return
            name = ' '.join(args[1:])
            if get_family_by_user(user_id):
                send_message(event.peer_id, "Вы уже в семье.")
                return
            fid = create_family(name, user_id)
            if fid:
                send_message(event.peer_id, f"✅ Семья '{name}' создана!")
            else:
                send_message(event.peer_id, "❌ Ошибка: вы уже состоите в семье.")
        elif sub == 'вступить':
            if len(args) < 2:
                send_message(event.peer_id, "Укажите название семьи.")
                return
            name = ' '.join(args[1:])
            cursor.execute('SELECT id FROM families WHERE name=?', (name,))
            row = cursor.fetchone()
            if not row:
                send_message(event.peer_id, "Семья не найдена.")
                return
            if get_family_by_user(user_id):
                send_message(event.peer_id, "Вы уже в семье.")
                return
            if not join_family(user_id, row[0]):
                send_message(event.peer_id, "Семья заполнена (максимум 6).")
                return
            send_message(event.peer_id, f"Вы вступили в семью '{name}'.")
        elif sub == 'выйти':
            leave_family(user_id)
            send_message(event.peer_id, "Вы вышли из семьи.")
        elif sub == 'список':
            families = get_all_families()
            if not families:
                send_message(event.peer_id, "Нет семей.")
                return
            msg = "👨‍👩‍👧‍👦 Семьи:\n"
            for f in families:
                msg += f"• {f[1]} (лидер: {f[2]}, BTC: {f[3]}, Допамин: {f[4]})\n"
            send_message(event.peer_id, msg)
        elif sub == 'инфо':
            fid = get_family_by_user(user_id)
            if not fid:
                send_message(event.peer_id, "Вы не в семье.")
                return
            info = get_family_info(fid)
            members = get_family_members(fid)
            msg = f"Семья: {info[1]}\nБаланс BTC: {info[3]}\nБаланс допамин: {info[4]}\nУчастники:\n"
            for uid, role in members:
                uinfo = get_user_info(uid)
                name = f"{uinfo['first_name']} {uinfo['last_name']}" if uinfo else str(uid)
                msg += f"• {name} ({role})\n"
            send_message(event.peer_id, msg)
        elif sub == 'пополнить':
            fid = get_family_by_user(user_id)
            if not fid:
                send_message(event.peer_id, "Вы не в семье.")
                return
            if len(args) < 2:
                send_message(event.peer_id, "Укажите сумму BTC.")
                return
            try:
                amount = int(args[1])
            except:
                send_message(event.peer_id, "Неверная сумма.")
                return
            row = db_get_user(user_id)
            if row[3] < amount:
                send_message(event.peer_id, "Недостаточно BTC.")
                return
            db_update_user(user_id, btc=row[3]-amount)
            update_family_balance(fid, btc=amount)
            send_message(event.peer_id, f"Вы пополнили семью на {amount} BTC.")


    elif command == 'жениться':
        target_id, _ = get_target_and_clean_args(event, args)
        if not target_id:
            send_message(event.peer_id, "Укажите пользователя ответом или ссылкой.")
            return
        if target_id == user_id:
            send_message(event.peer_id, "Нельзя жениться на себе.")
            return
        if get_marriage(user_id) or get_marriage(target_id):
            send_message(event.peer_id, "Кто-то уже состоит в браке.")
            return
        create_marriage(user_id, target_id)
        send_message(event.peer_id, f"💍 Вы теперь в браке с пользователем {target_id}!")

    elif command == 'развестись':
        if not get_marriage(user_id):
            send_message(event.peer_id, "Вы не в браке.")
            return
        delete_marriage(user_id)
        send_message(event.peer_id, "Вы развелись.")

    elif command == 'свести':
        if not is_admin(user_id):
            send_message(event.peer_id, "⛔ Только админ.")
            return
        ids = get_all_mentioned_ids(event, args)
        if len(ids) < 2:
            send_message(event.peer_id, "Использование: /свести (юзер1) (юзер2)")
            return
        u1, u2 = ids[0], ids[1]
        if get_marriage(u1) or get_marriage(u2):
            send_message(event.peer_id, "Один из них уже в браке.")
            return
        create_marriage(u1, u2)
        send_message(event.peer_id, f"💍 Пользователи {u1} и {u2} сведены.")

    elif command == 'развести':
        if not is_admin(user_id):
            send_message(event.peer_id, "⛔ Только админ.")
            return
        ids = get_all_mentioned_ids(event, args)
        if len(ids) >= 2:
            delete_marriage_pair(ids[0], ids[1])
            send_message(event.peer_id, f"Брак между {ids[0]} и {ids[1]} расторгнут.")
        elif len(ids) == 1:
            delete_marriage(ids[0])
            send_message(event.peer_id, f"Брак пользователя {ids[0]} расторгнут.")
        else:
            send_message(event.peer_id, "Укажите одного или двух пользователей.")

    elif command == 'коин':
        row = db_get_user(user_id)
        if not row:
            send_message(event.peer_id, "❌ Вы не зарегистрированы.")
            return
        rate = get_poker_rate()
        send_message(event.peer_id, f"🪙 Poker Koin\nКурс: 1 PKR = {rate:.6f} BTC\nВаш баланс: {row[20]} PKR\n\nКупить: /купитькоин (кол-во)\nПродать: /продатькоин (кол-во)")

    elif command == 'купитькоин':
        if len(args) < 1:
            send_message(event.peer_id, "Использование: /купитькоин (кол-во)")
            return
        try:
            amount = int(args[0])
            if amount <= 0:
                raise ValueError
        except:
            send_message(event.peer_id, "❌ Неверное количество.")
            return
        row = db_get_user(user_id)
        rate = get_poker_rate()
        cost = amount * rate
        if row[3] < cost:
            send_message(event.peer_id, f"❌ Недостаточно BTC. Нужно {cost:.6f} BTC.")
            return
        db_update_user(user_id, btc=row[3]-cost, poker_koins=row[20]+amount)
        send_message(event.peer_id, f"✅ Вы купили {amount} PKR за {cost:.6f} BTC.")

    elif command == 'продатькоин':
        if len(args) < 1:
            send_message(event.peer_id, "Использование: /продатькоин (кол-во)")
            return
        try:
            amount = int(args[0])
            if amount <= 0:
                raise ValueError
        except:
            send_message(event.peer_id, "❌ Неверное количество.")
            return
        row = db_get_user(user_id)
        if row[20] < amount:
            send_message(event.peer_id, "❌ Недостаточно PKR.")
            return
        rate = get_poker_rate()
        revenue = amount * rate
        db_update_user(user_id, poker_koins=row[20]-amount, btc=row[3]+revenue)
        send_message(event.peer_id, f"✅ Вы продали {amount} PKR за {revenue:.6f} BTC.")

    elif command == '+koin':
        if not is_admin(user_id):
            send_message(event.peer_id, "⛔ Недостаточно прав.")
            return
        target_id, clean_args = get_target_and_clean_args(event, args)
        if target_id is None:
            target_id = user_id
        if not clean_args:
            send_message(event.peer_id, "Использование: /+koin (кол-во) (ссылка/ответ)")
            return
        try:
            amount = int(clean_args[0])
            if amount <= 0:
                raise ValueError
        except:
            send_message(event.peer_id, "❌ Неверное количество.")
            return
        db_create_user(target_id)
        row = db_get_user(target_id)
        db_update_user(target_id, poker_koins=row[20]+amount)
        send_message(event.peer_id, f"✅ Выдано {amount} PKR пользователю {target_id}.")

    elif command == '-koin':
        if not is_admin(user_id):
            send_message(event.peer_id, "⛔ Недостаточно прав.")
            return
        target_id, clean_args = get_target_and_clean_args(event, args)
        if target_id is None:
            target_id = user_id
        if not clean_args:
            send_message(event.peer_id, "Использование: /-koin (кол-во) (ссылка/ответ)")
            return
        try:
            amount = int(clean_args[0])
        except:
            send_message(event.peer_id, "❌ Неверное количество.")
            return
        db_create_user(target_id)
        row = db_get_user(target_id)
        db_update_user(target_id, poker_koins=max(0, row[20]-amount))
        send_message(event.peer_id, f"✅ Списано {amount} PKR у пользователя {target_id}.")

    elif command == 'alldelkoin':
        if not is_creator(user_id):
            send_message(event.peer_id, "⛔ Только создатель.")
            return
        cursor.execute('UPDATE users SET poker_koins=0')
        conn.commit()
        send_message(event.peer_id, "✅ Все PKR обнулены.")

    elif command == 'dox':
        target_id, _ = get_target_and_clean_args(event, args)
        if not target_id:
            send_message(event.peer_id, "Укажите пользователя (ответом или ссылкой).")
            return
        info = get_user_info(target_id, fields='photo_max_orig,status,counters,friend_status,online,sticker_count')
        if not info:
            send_message(event.peer_id, "❌ Пользователь не найден.")
            return
        name = f"{info['first_name']} {info['last_name']}"
        user_id_str = str(target_id)
        msg = f"👤 Информация о {name}:\n"
        msg += f"ID: {user_id_str}\n"
        msg += f"Статус: {info.get('status', '')}\n"
        if 'counters' in info:
            msg += f"Подписчики: {info['counters'].get('followers', 'нет данных')}\n"
            msg += f"Друзья: {info['counters'].get('friends', 'нет данных')}\n"
            msg += f"Фотографии: {info['counters'].get('photos', 'нет данных')}\n"
        msg += f"Онлайн: {'Да' if info.get('online') else 'Нет'}\n"
        msg += f"Стикеры: {info.get('sticker_count', 'нет данных')}"
        send_message(event.peer_id, msg)

    elif command == 'doxelp':
        if not is_prince(user_id):
            send_message(event.peer_id, "⛔ Недостаточно прав (Князь+).")
            return
        target_id, _ = get_target_and_clean_args(event, args)
        if not target_id:
            send_message(event.peer_id, "Укажите пользователя.")
            return
        info = get_user_info(target_id, fields='photo_max_orig,status,counters,friend_status,online,sticker_count,last_seen')
        if not info:
            send_message(event.peer_id, "❌ Пользователь не найден.")
            return
        name = f"{info['first_name']} {info['last_name']}"
        msg = f"🕵️ Закрытая информация о {name}:\n"
        msg += f"ID: {target_id}\n"
        msg += f"Статус: {info.get('status', '')}\n"
        if 'last_seen' in info:
            last_seen = datetime.datetime.fromtimestamp(info['last_seen'].get('time', 0)).strftime('%d.%m.%Y %H:%M')
            msg += f"Последний визит: {last_seen}\n"
        if 'counters' in info:
            msg += f"Подписчики: {info['counters'].get('followers', 'нет данных')}\n"
            msg += f"Друзья: {info['counters'].get('friends', 'нет данных')}\n"
            msg += f"Фотографии: {info['counters'].get('photos', 'нет данных')}\n"
            msg += f"Видео: {info['counters'].get('videos', 'нет данных')}\n"
            msg += f"Аудио: {info['counters'].get('audios', 'нет данных')}\n"
        msg += f"Онлайн: {'Да' if info.get('online') else 'Нет'}\n"
        msg += f"Стикеры: {info.get('sticker_count', 'нет данных')}"
        send_message(event.peer_id, msg)

    elif command == 'стат':
        target_id, _ = get_target_and_clean_args(event, args)
        target_id = target_id or user_id
        row = db_get_user(target_id)
        if not row:
            send_message(event.peer_id, "❌ Пользователь не зарегистрирован в боте.")
            return
        info = get_user_info(target_id)
        name = f"{info['first_name']} {info['last_name']}" if info else str(target_id)
        role_names = {0: 'Участник', 1: 'Элита', 2: 'Князь', 3: 'Император', 4: 'Админ', 5: 'Создатель'}
        role = role_names.get(row[2], 'Неизвестно')
        herzog = '👑 Да' if row[5] else ('⏳ Временно' if row[15] > time.time() else '❌ Нет')
        protection = '🛡️ Да' if row[6] else '❌ Нет'
        clan_id = get_clan_by_user(target_id)
        clan_name = 'Без клана'
        if clan_id:
            clan_info = get_clan_info(clan_id)
            if clan_info:
                clan_name = clan_info[1]
        family_id = get_family_by_user(target_id)
        family_name = 'Без семьи'
        if family_id:
            fi = get_family_info(family_id)
            if fi:
                family_name = fi[1]
        marriage = get_marriage(target_id)
        partner = 'Нет'
        if marriage:
            partner_id = marriage[1] if marriage[1] != target_id else marriage[2]
            p_info = get_user_info(partner_id)
            partner = f"{p_info['first_name']} {p_info['last_name']}" if p_info else str(partner_id)
        msg = f"📊 Профиль {name}:\n"
        msg += f"ID: {target_id}\n"
        msg += f"Роль: {role}\n"
        msg += f"💰 БТС: {row[3]}\n"
        msg += f"🧪 Дофамин: {row[4]}\n"
        msg += f"⭐ Звёзды: {row[11]}\n"
        msg += f"🪙 PKR: {row[20]}\n"
        msg += f"Герцог: {herzog}\n"
        msg += f"Защита: {protection}\n"
        msg += f"Клан: {clan_name}\n"
        msg += f"Семья: {family_name}\n"
        msg += f"Брак: {partner}"
        send_message(event.peer_id, msg)

    elif command == 'казино':
        if len(args) < 2:
            send_message(event.peer_id, "Использование: /казино (ставка) (количество)")
            return
        try:
            bet = int(args[0])
            amount = int(args[1])
            if bet <= 0 or amount <= 0:
                raise ValueError
        except:
            send_message(event.peer_id, "❌ Неверные аргументы.")
            return
        row = db_get_user(user_id)
        if row[3] < amount:
            send_message(event.peer_id, f"❌ У вас недостаточно БТС (нужно {amount}).")
            return
        if random.random() < 0.5:
            win = amount * 2
            db_update_user(user_id, btc=row[3] + win - amount)
            send_message(event.peer_id, f"🎉 Вы выиграли! Получено {win} БТС. Текущий баланс: {row[3] + win - amount}")
        else:
            db_update_user(user_id, btc=row[3] - amount)
            send_message(event.peer_id, f"😞 Вы проиграли. Списано {amount} БТС. Текущий баланс: {row[3] - amount}")

    elif command == 'выдатьбтс':
        if not is_admin(user_id):
            send_message(event.peer_id, "⛔ Недостаточно прав (Админ+).")
            return
        target_id, clean_args = get_target_and_clean_args(event, args)
        if target_id is None:
            target_id = user_id
        if not clean_args:
            send_message(event.peer_id, "Использование: /выдатьбтс (ссылка/ответ) (кол-во)")
            return
        try:
            amount = int(clean_args[0])
            if amount <= 0:
                raise ValueError
        except:
            send_message(event.peer_id, "❌ Неверная сумма.")
            return
        db_create_user(target_id)
        row = db_get_user(target_id)
        db_update_user(target_id, btc=row[3] + amount)
        cursor.execute('INSERT INTO history (user_id, action, timestamp) VALUES (?,?,?)', (target_id, f'Выдано {amount} БТС админом {user_id}', time.time()))
        conn.commit()
        send_message(event.peer_id, f"✅ Выдано {amount} БТС пользователю {target_id}.")

    elif command == 'герцог':
        row = db_get_user(user_id)
        if row[5] or row[15] > time.time():
            send_message(event.peer_id, "❌ У вас уже есть Герцог.")
            return
        price = 10000
        if row[3] < price:
            send_message(event.peer_id, f"❌ Недостаточно БТС. Нужно {price} БТС.")
            return
        db_update_user(user_id, btc=row[3] - price, herzog=1)
        cursor.execute('INSERT INTO history (user_id, action, timestamp) VALUES (?,?,?)', (user_id, 'Куплен Герцог (навсегда)', time.time()))
        conn.commit()
        send_message(event.peer_id, f"✅ Поздравляем! Вы купили Герцога навсегда за {price} БТС.")

    elif command == 'выдгерцог':
        if not is_admin(user_id):
            send_message(event.peer_id, "⛔ Недостаточно прав.")
            return
        target_id, _ = get_target_and_clean_args(event, args)
        if not target_id:
            send_message(event.peer_id, "Укажите пользователя.")
            return
        db_create_user(target_id)
        db_update_user(target_id, herzog=1)
        send_message(event.peer_id, f"✅ Герцог выдан пользователю {target_id}.")

    elif command == 'дофамин':
        if not check_cooldown(user_id, 'dofamin', 1800):
            send_message(event.peer_id, "❌ Дофамин можно получать раз в 30 минут.")
            return
        gain = random.randint(10, 50)
        row = db_get_user(user_id)
        db_update_user(user_id, dofamin=row[4] + gain)
        update_cooldown(user_id, 'dofamin')
        send_message(event.peer_id, f"🧪 Вы получили {gain} дофамина. Всего: {row[4] + gain}")

    elif command == 'украстьдоф':
        if not check_cooldown(user_id, 'steal', 3600):
            send_message(event.peer_id, "❌ Кража доступна раз в час.")
            return
        target_id, _ = get_target_and_clean_args(event, args)
        if not target_id:
            send_message(event.peer_id, "Укажите жертву.")
            return
        target_row = db_get_user(target_id)
        if not target_row:
            send_message(event.peer_id, "❌ Пользователь не найден в боте.")
            return
        if target_row[6] == 1:
            send_message(event.peer_id, "🛡️ У жертвы есть защита!")
            return
        if target_row[4] <= 0:
            send_message(event.peer_id, "❌ У жертвы нет дофамина.")
            return
        steal_amount = min(random.randint(5, 20), target_row[4])
        if random.random() < 0.6:
            db_update_user(target_id, dofamin=target_row[4] - steal_amount)
            row = db_get_user(user_id)
            db_update_user(user_id, dofamin=row[4] + steal_amount)
            update_cooldown(user_id, 'steal')
            send_message(event.peer_id, f"🤫 Вы украли {steal_amount} дофамина!")
        else:
            send_message(event.peer_id, "❌ Кража не удалась.")
            update_cooldown(user_id, 'steal')

    elif command == 'защитадоф':
        row = db_get_user(user_id)
        if row[6] == 1:
            send_message(event.peer_id, "❌ У вас уже есть защита.")
            return
        if row[3] < 500:
            send_message(event.peer_id, "❌ Недостаточно БТС. Нужно 500 БТС.")
            return
        db_update_user(user_id, btc=row[3] - 500, protection=1)
        send_message(event.peer_id, "✅ Защита от кражи куплена!")

        elif command == 'стикеры':
        target_id, _ = get_target_and_clean_args(event, args)
        target_id = target_id or user_id
        info = get_user_info(target_id, fields='sticker_count')
        if info:
            send_message(event.peer_id, f"🖼️ У пользователя {target_id} стикеров: {info.get('sticker_count', 'нет данных')}")
        else:
            send_message(event.peer_id, "❌ Пользователь не найден.")

    elif command == 'sp':
        if not args:
            send_message(event.peer_id, "Использование: /sp (текст)")
            return
        message = ' '.join(args)
        row = db_get_user(user_id)
        if not row:
            send_message(event.peer_id, "❌ Вы не зарегистрированы.")
            return
        trusted = json.loads(row[12]) if row[12] else []
        if not trusted:
            send_message(event.peer_id, "❌ Список доверенных пуст. Добавьте через /sp.")
            return
        api = get_user_api(user_id)
        if api:
            for tid in trusted:
                try:
                    api.messages.send(peer_id=tid, message=message, random_id=get_random_id())
                except:
                    pass
            send_message(event.peer_id, f"✅ Сообщение отправлено {len(trusted)} доверенным от вашего имени.")
        else:
            for tid in trusted:
                send_message(tid, f"Сообщение от {user_id}: {message}")
            send_message(event.peer_id, f"✅ Сообщение отправлено {len(trusted)} доверенным от имени бота.")

    elif command == 'unsp':
        target_id, _ = get_target_and_clean_args(event, args)
        if not target_id:
            send_message(event.peer_id, "Укажите пользователя.")
            return
        row = db_get_user(user_id)
        trusted = json.loads(row[12]) if row else []
        if target_id in trusted:
            trusted.remove(target_id)
            db_update_user(user_id, trusted_ids=json.dumps(trusted))
            send_message(event.peer_id, f"✅ Пользователь {target_id} удалён из доверенных.")
        else:
            send_message(event.peer_id, "❌ Этот пользователь не в списке доверенных.")

    elif command == 'vls':
        target_id, clean_args = get_target_and_clean_args(event, args)
        if not target_id or not clean_args:
            send_message(event.peer_id, "Использование: /vls (ссылка/ответ) (текст)")
            return
        message = ' '.join(clean_args)
        try:
            vk.messages.send(peer_id=target_id, message=message, random_id=get_random_id())
            send_message(event.peer_id, f"✅ Сообщение отправлено пользователю {target_id}.")
        except:
            send_message(event.peer_id, "❌ Не удалось отправить сообщение.")

    elif command == 'ai':
        if not args:
            send_message(event.peer_id, "Использование: /ai (запрос)")
            return
        query = ' '.join(args)
        answer = ask_gpt(query)
        send_message(event.peer_id, answer)

    elif command == 'cc':
        if not args:
            send_message(event.peer_id, "Использование: /cc (ссылка)")
            return
        url = args[0]
        try:
            short = vk.utils.getShortLink(url=url)
            send_message(event.peer_id, f"🔗 Короткая ссылка: {short['short_url']}")
        except Exception as e:
            send_message(event.peer_id, f"❌ Ошибка: {e}")

    elif command == '+гс':
        if not args:
            send_message(event.peer_id, "Использование: /+гс (название) (ответьте на голосовое)")
            return
        name = ' '.join(args).lower()
        reply = get_reply_message(event)
        if not reply or 'attachments' not in reply:
            send_message(event.peer_id, "❌ Ответьте на голосовое сообщение, чтобы сохранить его.")
            return
        att = reply['attachments'][0]
        if att['type'] == 'audio_message':
            owner_id = att['audio_message']['owner_id']
            audio_id = att['audio_message']['id']
            attachment_str = f"audio_message{owner_id}_{audio_id}"
            cursor.execute('INSERT OR REPLACE INTO custom_gs (name, attachment) VALUES (?,?)', (name, attachment_str))
            conn.commit()
            send_message(event.peer_id, f"✅ ГС '{name}' сохранён.")
        else:
            send_message(event.peer_id, "❌ Это не голосовое сообщение.")

    elif command == 'гс':
        if not args:
            send_message(event.peer_id, "Использование: /гс (название)")
            return
        name = ' '.join(args).lower()
        cursor.execute('SELECT attachment FROM custom_gs WHERE name=?', (name,))
        row = cursor.fetchone()
        if not row:
            send_message(event.peer_id, "❌ ГС не найден.")
            return
        send_message(event.peer_id, attachment=row[0])

    elif command == 'гсы':
        cursor.execute('SELECT name FROM custom_gs')
        rows = cursor.fetchall()
        if not rows:
            send_message(event.peer_id, "Список ГС пуст.")
            return
        msg = "📃 Список ГС:\n" + '\n'.join([r[0] for r in rows])
        send_message(event.peer_id, msg)

    elif command == '-гс':
        if not args:
            send_message(event.peer_id, "Использование: /-гс (название)")
            return
        name = ' '.join(args).lower()
        cursor.execute('DELETE FROM custom_gs WHERE name=?', (name,))
        conn.commit()
        send_message(event.peer_id, f"✅ ГС '{name}' удалён.")

    elif command == '+шаб':
        if len(args) < 1:
            send_message(event.peer_id, "Использование: /+шаб (название) (текст)")
            return
        name = args[0].lower()
        text = ' '.join(args[1:])
        if not text:
            reply = get_reply_message(event)
            if reply and reply.get('text'):
                text = reply['text']
            else:
                send_message(event.peer_id, "Укажите текст шаблона: /+шаб название текст")
                return
        cursor.execute('INSERT OR REPLACE INTO custom_shab (name, text) VALUES (?,?)', (name, text))
        conn.commit()
        send_message(event.peer_id, f"✅ Шаблон '{name}' сохранён.")

    elif command == 'шаб':
        if not args:
            send_message(event.peer_id, "Использование: /шаб (название)")
            return
        name = args[0].lower()
        cursor.execute('SELECT text FROM custom_shab WHERE name=?', (name,))
        row = cursor.fetchone()
        if not row:
            send_message(event.peer_id, "❌ Шаблон не найден.")
            return
        send_message(event.peer_id, row[0])

    elif command == 'шаблоны':
        cursor.execute('SELECT name FROM custom_shab')
        rows = cursor.fetchall()
        if not rows:
            send_message(event.peer_id, "Список шаблонов пуст.")
            return
        msg = "📃 Список шаблонов:\n" + '\n'.join([r[0] for r in rows])
        send_message(event.peer_id, msg)

    elif command == '-шаб':
        if not args:
            send_message(event.peer_id, "Использование: /-шаб (название)")
            return
        name = args[0].lower()
        cursor.execute('DELETE FROM custom_shab WHERE name=?', (name,))
        conn.commit()
        send_message(event.peer_id, f"✅ Шаблон '{name}' удалён.")

    elif command == 'подбор':
        if not args:
            send_message(event.peer_id, "Использование: /подбор (длина 0-10)")
            return
        try:
            length = int(args[0])
            if length < 0 or length > 10:
                raise ValueError
        except:
            send_message(event.peer_id, "❌ Введите число от 0 до 10.")
            return
        chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
        password = ''.join(random.choice(chars) for _ in range(length))
        send_message(event.peer_id, f"🔐 Подобранный пароль: {password}")

    elif command == '+invaite':
        if not event.from_chat:
            send_message(event.peer_id, "❌ Команда работает только в беседе.")
            return
        api = get_user_api(user_id)
        if not api:
            send_message(event.peer_id, "❌ У вас не сохранён токен. Используйте /+токен.")
            return
        try:
            friends = api.friends.get(user_id=user_id)['items']
            for fid in friends:
                try:
                    api.messages.addChatUser(chat_id=chat_id, user_id=fid)
                    time.sleep(2)
                except:
                    continue
            send_message(event.peer_id, f"✅ Приглашено {len(friends)} друзей.")
        except Exception as e:
            send_message(event.peer_id, f"❌ Ошибка: {e}")

    elif command == '-invaite':
        send_message(event.peer_id, "🛑 Приглашение остановлено (заглушка).")

    elif command == 'password':
        chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*()_+'
        password = ''.join(random.choice(chars) for _ in range(12))
        send_message(event.peer_id, f"🔑 Надёжный пароль: {password}")

    elif command == 'погода':
        if not args:
            send_message(event.peer_id, "Использование: /погода (город)")
            return
        city = ' '.join(args)
        url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={WEATHER_API_KEY}&lang=ru&units=metric"
        try:
            response = requests.get(url, timeout=10)
            data = response.json()
            if data.get('main'):
                temp = data['main']['temp']
                desc = data['weather'][0]['description']
                send_message(event.peer_id, f"🌤️ Погода в {city}:\nТемпература: {temp}°C\nОписание: {desc}")
            else:
                send_message(event.peer_id, "❌ Город не найден.")
        except Exception as e:
            send_message(event.peer_id, f"❌ Ошибка: {e}")

    elif command == 'шар':
        if not args:
            send_message(event.peer_id, "Использование: /шар (вопрос)")
            return
        answers = ["Да", "Нет", "Возможно", "Спроси позже", "Определённо да", "Не рассчитывай"]
        send_message(event.peer_id, f"🎱 {random.choice(answers)}")

    elif command == '+описание':
        if not args:
            send_message(event.peer_id, "Использование: /+описание (текст)")
            return
        new_status = ' '.join(args)
        api = get_user_api(user_id)
        if api:
            try:
                api.status.set(text=new_status)
                send_message(event.peer_id, "✅ Статус VK обновлён (ваш аккаунт).")
            except Exception as e:
                send_message(event.peer_id, f"❌ Ошибка: {e}")
        else:
            if is_admin(user_id):
                try:
                    vk.status.set(text=new_status)
                    send_message(event.peer_id, "✅ Статус бота обновлён.")
                except Exception as e:
                    send_message(event.peer_id, f"❌ Ошибка: {e}")
            else:
                send_message(event.peer_id, "❌ У вас нет сохранённого токена. Сохраните его через /+токен.")

    elif command == 'аватарка':
        target_id, _ = get_target_and_clean_args(event, args)
        target_id = target_id or user_id
        avatar_url = get_user_avatar(target_id)
        if not avatar_url:
            send_message(event.peer_id, "❌ Не удалось получить аватар.")
            return
        photo_data = download_photo(avatar_url)
        if not photo_data:
            send_message(event.peer_id, "❌ Ошибка загрузки.")
            return
        attachment = upload_photo_bytes_to_vk(event.peer_id, photo_data, 'avatar.jpg')
        if attachment:
            send_message(event.peer_id, attachment=attachment)
        else:
            send_message(event.peer_id, "❌ Ошибка загрузки фото.")

    elif command == '-смс':
        if not is_admin(user_id) and user_id not in get_access_users():
            send_message(event.peer_id, "⛔ Недостаточно прав.")
            return
        target_id, clean_args = get_target_and_clean_args(event, args)
        if not target_id:
            send_message(event.peer_id, "Укажите пользователя (ответ/ссылка).")
            return
        try:
            count = int(clean_args[0]) if clean_args else 1
            if count < 1 or count > 100:
                raise ValueError
        except:
            send_message(event.peer_id, "❌ Неверное количество (1-100).")
            return
        try:
            messages = vk.messages.getHistory(peer_id=target_id, count=count)['items']
            for msg in messages:
                vk.messages.delete(message_ids=msg['id'], delete_for_all=1)
            send_message(event.peer_id, f"✅ Удалено {len(messages)} сообщений.")
        except Exception as e:
            send_message(event.peer_id, f"❌ Ошибка: {e}")

    elif command == 'цитата':
        reply = get_reply_message(event)
        if reply and reply.get('text'):
            text = reply['text']
        elif args:
            text = ' '.join(args)
        else:
            send_message(event.peer_id, "Использование: /цитата (текст) или ответьте на сообщение")
            return
        buf = generate_quote_image(text)
        attachment = upload_photo_bytes_to_vk(event.peer_id, buf.getvalue(), 'quote.png')
        if attachment:
            send_message(event.peer_id, attachment=attachment)
        else:
            send_message(event.peer_id, "❌ Ошибка загрузки фото.")

    elif command == 'демо':
        if not args:
            send_message(event.peer_id, "Использование: /демо (текст)")
            return
        text = ' '.join(args)
        buf = generate_demotivator(text)
        attachment = upload_photo_bytes_to_vk(event.peer_id, buf.getvalue(), 'demo.png')
        if attachment:
            send_message(event.peer_id, attachment=attachment)
        else:
            send_message(event.peer_id, "❌ Ошибка загрузки фото.")

    elif command == 'пинг':
        send_message(event.peer_id, "🏓 Понг!")

    elif command == 'тян':
        photo_path = get_random_image(os.path.join(IMAGES_DIR, 'tyan'))
        if not photo_path:
            send_message(event.peer_id, "❌ Нет фото. Добавьте в images/tyan.")
            return
        attachment = upload_photo_to_vk(event.peer_id, photo_path)
        if attachment:
            send_message(event.peer_id, attachment=attachment)
        else:
            send_message(event.peer_id, "❌ Ошибка загрузки фото. Убедитесь, что токен имеет право photos.")

    elif command == 'ножки':
        photo_path = get_random_image(os.path.join(IMAGES_DIR, 'legs'))
        if not photo_path:
            send_message(event.peer_id, "❌ Нет фото. Добавьте в images/legs.")
            return
        attachment = upload_photo_to_vk(event.peer_id, photo_path)
        if attachment:
            send_message(event.peer_id, attachment=attachment)
        else:
            send_message(event.peer_id, "❌ Ошибка загрузки фото. Убедитесь, что токен имеет право photos.")

    elif command == 'пикча':
        photo_path = get_random_image(os.path.join(IMAGES_DIR, 'gort'))
        if not photo_path:
            send_message(event.peer_id, "❌ Нет фото. Добавьте в images/gort.")
            return
        attachment = upload_photo_to_vk(event.peer_id, photo_path)
        if attachment:
            send_message(event.peer_id, attachment=attachment)
        else:
            send_message(event.peer_id, "❌ Ошибка загрузки фото. Убедитесь, что токен имеет право photos.")

    elif command == 'анекдот':
        send_message(event.peer_id, random.choice(ANECDOTES))

    elif command == 'префикс':
        if not args:
            send_message(event.peer_id, "Использование: /префикс (префикс)")
            return
        new_prefix = args[0]
        set_prefix(chat_id, new_prefix)
        send_message(event.peer_id, f"✅ Префикс изменён на '{new_prefix}'.")

    elif command == '+роль':
        if not is_creator(user_id):
            send_message(event.peer_id, "⛔ Только создатель.")
            return
        target_id, clean_args = get_target_and_clean_args(event, args)
        if not target_id or not clean_args:
            send_message(event.peer_id, "Использование: /+роль (ссылка/ответ) (0-4)")
            return
        try:
            role = int(clean_args[0])
            if role < 0 or role > 4:
                raise ValueError
        except:
            send_message(event.peer_id, "❌ Роль от 0 до 4.")
            return
        db_create_user(target_id)
        db_update_user(target_id, role=role)
        send_message(event.peer_id, f"✅ Роль {role} выдана пользователю {target_id}.")

    elif command == '-роль':
        if not is_creator(user_id):
            send_message(event.peer_id, "⛔ Только создатель.")
            return
        target_id, _ = get_target_and_clean_args(event, args)
        if not target_id:
            send_message(event.peer_id, "Укажите пользователя.")
            return
        db_create_user(target_id)
        db_update_user(target_id, role=0)
        send_message(event.peer_id, f"✅ Роль снята с пользователя {target_id}.")

    elif command == 'стафф':
        cursor.execute('SELECT user_id, role FROM users WHERE role > 0')
        rows = cursor.fetchall()
        if not rows:
            send_message(event.peer_id, "Список персонала пуст.")
            return
        role_names = {1: 'Элита', 2: 'Князь', 3: 'Император', 4: 'Админ', 5: 'Создатель'}
        msg = "👥 Персонал:\n"
        for uid, role in rows:
            info = get_user_info(uid)
            name = f"{info['first_name']} {info['last_name']}" if info else str(uid)
            msg += f"{name} — {role_names.get(role, 'Неизвестно')}\n"
        send_message(event.peer_id, msg)

    elif command == 'доступы':
        users = get_access_users()
        if not users:
            send_message(event.peer_id, "Список доступа пуст.")
            return
        msg = "🔐 Доступ к -смс:\n" + '\n'.join([str(u) for u in users])
        send_message(event.peer_id, msg)

    elif command == '+доступ':
        if not is_prince(user_id):
            send_message(event.peer_id, "⛔ Недостаточно прав (Князь+).")
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
            send_message(event.peer_id, "⛔ Недостаточно прав (Князь+).")
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
            send_message(event.peer_id, "❌ Команда только в беседе.")
            return
        if not is_admin(user_id):
            send_message(event.peer_id, "⛔ Недостаточно прав.")
            return
        target_id, _ = get_target_and_clean_args(event, args)
        if not target_id:
            send_message(event.peer_id, "Укажите пользователя.")
            return
        try:
            vk.messages.addChatUser(chat_id=chat_id, user_id=target_id)
            send_message(event.peer_id, f"✅ Пользователь {target_id} добавлен в беседу.")
        except Exception as e:
            send_message(event.peer_id, f"❌ Ошибка: {e}")

    elif command == 'кик':
        if not event.from_chat:
            send_message(event.peer_id, "❌ Команда только в беседе.")
            return
        if not is_admin(user_id):
            send_message(event.peer_id, "⛔ Недостаточно прав.")
            return
        target_id, _ = get_target_and_clean_args(event, args)
        if not target_id:
            send_message(event.peer_id, "Укажите пользователя.")
            return
        try:
            vk.messages.removeChatUser(chat_id=chat_id, user_id=target_id)
            send_message(event.peer_id, f"✅ Пользователь {target_id} исключён из беседы.")
        except Exception as e:
            send_message(event.peer_id, f"❌ Ошибка: {e}")

    elif command == 'реши':
        if not args:
            send_message(event.peer_id, "Использование: /реши (выражение)")
            return
        expression = ' '.join(args)
        allowed = set('0123456789+-*/().% ')
        if any(c not in allowed for c in expression):
            send_message(event.peer_id, "❌ Недопустимые символы в выражении.")
            return
        try:
            result = eval(expression)
            send_message(event.peer_id, f"🧮 {expression} = {result}")
        except:
            send_message(event.peer_id, "❌ Ошибка вычисления.")

    elif command == 'чистка':
        if not event.from_chat:
            send_message(event.peer_id, "❌ Команда только в беседе.")
            return
        try:
            count = int(args[0]) if args else 10
            if count < 1 or count > 100:
                raise ValueError
        except:
            send_message(event.peer_id, "❌ Неверное количество (1-100).")
            return
        try:
            history = vk.messages.getHistory(peer_id=event.peer_id, count=200)['items']
            to_delete = [m['id'] for m in history if m.get('from_id') == user_id][:count]
            for mid in to_delete:
                vk.messages.delete(message_ids=mid, delete_for_all=1)
            send_message(event.peer_id, f"✅ Удалено {len(to_delete)} ваших сообщений.")
        except Exception as e:
            send_message(event.peer_id, f"❌ Ошибка: {e}")

    elif command == 'приз':
        if not check_cooldown(user_id, 'prize', 7200):
            send_message(event.peer_id, "❌ Приз можно получать раз в 2 часа.")
            return
        prize = random.randint(1, 100)
        row = db_get_user(user_id)
        db_update_user(user_id, btc=row[3] + prize)
        update_cooldown(user_id, 'prize')
        send_message(event.peer_id, f"🎁 Вы получили {prize} БТС!")

    elif command == 'helpr1':
        send_message(event.peer_id, "📖 Команды Элиты:\n/doxelp — закрытая информация\n/стат — профиль\n/топбтс, /топдоф, /герцоги, /защищённые\n/коин, /купитькоин, /продатькоин\n/жениться, /развестись\n/семья (создать, вступить, выйти, список, инфо, пополнить)")

    elif command == 'helpr2':
        send_message(event.peer_id, "📖 Команды Князя:\n/doxelp — закрытая информация\n/+доступ — выдать доступ к -смс\n/-доступ — забрать доступ\n/выдатьбтс — выдать BTC\n/выдатьдоф — выдать дофамин\n/-дофамин — забрать дофамин\n/выдгерцог — выдать герцога\n/забгерцог — забрать герцога\n/стафф — персонал\n/доступы — список доступа\n/логи — логи команд\n/свести, /развести — браки\n/удалитьсемью, /удалитьклан\n/newreg — изменить дату регистрации")

    elif command == 'helpr3':
        send_message(event.peer_id, "📖 Команды Императора:\nВсе команды Князя +\n/блокировки, /баны — баны\n/рассылка — рассылка\n/restart, /stop\n/сброс — сбросить токен\n/токен инфа — проверить токен\n/курс (USD/EUR/BTC/PKR)\n/пикча, /тян, /ножки, /демо, /цитата")

    elif command == 'rcode':
        send_message(event.peer_id, "❌ Регистрация по коду отключена. Используйте /reg (токен).")

    elif command == 'codes':
        send_message(event.peer_id, "❌ Регистрация по коду отключена.")

    elif command == 'starshop':
        msg = "🛒 Магазин за звёзды:\n"
        msg += "1. 10 БТС — 1 звезда\n"
        msg += "2. 100 БТС — 5 звёзд\n"
        msg += "3. 250 БТС — 10 звёзд\n"
        msg += "4. Герцог на неделю — 20 звёзд\n"
        msg += "5. Герцог на месяц — 50 звёзд"
        send_message(event.peer_id, msg)

    elif command == 'buy':
        if not args:
            send_message(event.peer_id, "Использование: /buy (товар) (кол-во)")
            return
        item = args[0].lower()
        quantity = int(args[1]) if len(args) > 1 else 1
        row = db_get_user(user_id)
        if not row:
            send_message(event.peer_id, "❌ Вы не зарегистрированы.")
            return
        if item == 'бтс':
            if len(args) < 2:
                send_message(event.peer_id, "Укажите количество БТС.")
                return
            amount = int(args[1])
            price = amount // 10
            if row[11] < price:
                send_message(event.peer_id, f"❌ Недостаточно звёзд. Нужно {price}.")
                return
            db_update_user(user_id, stars=row[11]-price, btc=row[3]+amount)
            send_message(event.peer_id, f"✅ Вы купили {amount} БТС за {price} звёзд.")
        elif item == 'герцог_неделя':
            if row[11] < 20:
                send_message(event.peer_id, "❌ Недостаточно звёзд. Нужно 20.")
                return
            expiry = time.time() + 7*86400
            db_update_user(user_id, stars=row[11]-20, herzog_expiry=expiry)
            send_message(event.peer_id, "✅ Герцог на неделю активирован!")
        elif item == 'герцог_месяц':
            if row[11] < 50:
                send_message(event.peer_id, "❌ Недостаточно звёзд. Нужно 50.")
                return
            expiry = time.time() + 30*86400
            db_update_user(user_id, stars=row[11]-50, herzog_expiry=expiry)
            send_message(event.peer_id, "✅ Герцог на месяц активирован!")
        else:
            send_message(event.peer_id, "❌ Неизвестный товар.")

    elif command == 'топбтс':
        cursor.execute('SELECT user_id, btc FROM users WHERE btc > 0 ORDER BY btc DESC LIMIT 10')
        rows = cursor.fetchall()
        if not rows:
            send_message(event.peer_id, "Нет данных.")
            return
        msg = "🏆 Топ по БТС:\n"
        for i, (uid, btc) in enumerate(rows, 1):
            info = get_user_info(uid)
            name = f"{info['first_name']} {info['last_name']}" if info else str(uid)
            msg += f"{i}. {name} — {btc} БТС\n"
        send_message(event.peer_id, msg)

    elif command == 'топдоф':
        cursor.execute('SELECT user_id, dofamin FROM users WHERE dofamin > 0 ORDER BY dofamin DESC LIMIT 10')
        rows = cursor.fetchall()
        if not rows:
            send_message(event.peer_id, "Нет данных.")
            return
        msg = "🏆 Топ по дофамину:\n"
        for i, (uid, dof) in enumerate(rows, 1):
            info = get_user_info(uid)
            name = f"{info['first_name']} {info['last_name']}" if info else str(uid)
            msg += f"{i}. {name} — {dof} дофамина\n"
        send_message(event.peer_id, msg)

    elif command == 'герцоги':
        cursor.execute('SELECT user_id FROM users WHERE herzog=1 OR herzog_expiry > ?', (time.time(),))
        rows = cursor.fetchall()
        if not rows:
            send_message(event.peer_id, "Нет герцогов.")
            return
        msg = "👑 Герцоги:\n"
        for (uid,) in rows:
            info = get_user_info(uid)
            name = f"{info['first_name']} {info['last_name']}" if info else str(uid)
            msg += f"• {name}\n"
        send_message(event.peer_id, msg)

    elif command == 'защищённые':
        cursor.execute('SELECT user_id FROM users WHERE protection=1')
        rows = cursor.fetchall()
        if not rows:
            send_message(event.peer_id, "Нет защищённых.")
            return
        msg = "🛡️ Защищённые:\n"
        for (uid,) in rows:
            info = get_user_info(uid)
            name = f"{info['first_name']} {info['last_name']}" if info else str(uid)
            msg += f"• {name}\n"
        send_message(event.peer_id, msg)

    elif command == 'отключение':
        if not is_creator(user_id):
            send_message(event.peer_id, "⛔ Только создатель.")
            return
        target_id, _ = get_target_and_clean_args(event, args)
        if not target_id:
            send_message(event.peer_id, "Укажите пользователя.")
            return
        db_create_user(target_id)
        db_update_user(target_id, is_disabled=1)
        send_message(event.peer_id, f"✅ Пользователь {target_id} отключён.")

    elif command == 'включение':
        if not is_creator(user_id):
            send_message(event.peer_id, "⛔ Только создатель.")
            return
        target_id, _ = get_target_and_clean_args(event, args)
        if not target_id:
            send_message(event.peer_id, "Укажите пользователя.")
            return
        db_create_user(target_id)
        db_update_user(target_id, is_disabled=0)
        send_message(event.peer_id, f"✅ Пользователь {target_id} включён.")

    elif command == '+админ':
        if not is_creator(user_id):
            send_message(event.peer_id, "⛔ Только создатель.")
            return
        target_id, _ = get_target_and_clean_args(event, args)
        if not target_id:
            send_message(event.peer_id, "Укажите пользователя.")
            return
        db_create_user(target_id)
        db_update_user(target_id, role=4)
        send_message(event.peer_id, f"✅ Администратор назначен: {target_id}.")

    elif command == '-админ':
        if not is_creator(user_id):
            send_message(event.peer_id, "⛔ Только создатель.")
            return
        target_id, _ = get_target_and_clean_args(event, args)
        if not target_id:
            send_message(event.peer_id, "Укажите пользователя.")
            return
        db_create_user(target_id)
        db_update_user(target_id, role=0)
        send_message(event.peer_id, f"✅ Администратор снят: {target_id}.")

    elif command == 'базаданных':
        if not is_creator(user_id):
            send_message(event.peer_id, "⛔ Только создатель.")
            return
        cursor.execute('SELECT user_id, role, btc, dofamin, stars, poker_koins FROM users')
        rows = cursor.fetchall()
        if not rows:
            send_message(event.peer_id, "База данных пуста.")
            return
        msg = "📋 Зарегистрированные пользователи:\n"
        for uid, role, btc, dof, stars, pkr in rows:
            info = get_user_info(uid)
            name = f"{info['first_name']} {info['last_name']}" if info else str(uid)
            msg += f"{name} ({uid}) — роль {role}, БТС {btc}, дофамин {dof}, звёзды {stars}, PKR {pkr}\n"
        send_message(event.peer_id, msg)

    elif command == 'сброс':
        if not is_admin(user_id):
            send_message(event.peer_id, "⛔ Недостаточно прав.")
            return
        target_id, _ = get_target_and_clean_args(event, args)
        if not target_id:
            send_message(event.peer_id, "Укажите пользователя.")
            return
        db_create_user(target_id)
        db_update_user(target_id, access_token=None)
        if target_id in user_threads and user_threads[target_id].is_alive():
            user_sessions.pop(target_id, None)
            user_threads.pop(target_id, None)
        send_message(event.peer_id, f"✅ Токен пользователя {target_id} сброшен.")

    elif command == 'токен':
        if not args:
            send_message(event.peer_id, "Использование: /токен инфа (токен)")
            return
        if args[0].lower() == 'инфа':
            if len(args) < 2:
                send_message(event.peer_id, "Укажите токен.")
                return
            token = args[1]
            try:
                session = vk_api.VkApi(token=token)
                api = session.get_api()
                info = api.users.get()[0]
                send_message(event.peer_id, f"✅ Токен валиден. Принадлежит: {info['first_name']} {info['last_name']}")
            except Exception as e:
                send_message(event.peer_id, f"❌ Токен невалиден: {e}")
        else:
            send_message(event.peer_id, "Неизвестная подкоманда.")

    elif command == 'restart':
        if not is_admin(user_id):
            send_message(event.peer_id, "⛔ Недостаточно прав.")
            return
        send_message(event.peer_id, "🔄 Перезапуск...")
        os.execv(sys.executable, ['python'] + sys.argv)

    elif command == 'stop':
        if not is_admin(user_id):
            send_message(event.peer_id, "⛔ Недостаточно прав.")
            return
        send_message(event.peer_id, "🛑 Остановка бота...")
        sys.exit(0)

    elif command == 'выдатьдоф':
        if not is_admin(user_id):
            send_message(event.peer_id, "⛔ Недостаточно прав.")
            return
        target_id, clean_args = get_target_and_clean_args(event, args)
        if not target_id or not clean_args:
            send_message(event.peer_id, "Использование: /выдатьдоф (ссылка/ответ) (кол-во)")
            return
        try:
            amount = int(clean_args[0])
        except:
            send_message(event.peer_id, "❌ Неверная сумма.")
            return
        db_create_user(target_id)
        row = db_get_user(target_id)
        db_update_user(target_id, dofamin=row[4] + amount)
        send_message(event.peer_id, f"✅ Выдано {amount} дофамина.")

    elif command == '-дофамин':
        if not is_admin(user_id):
            send_message(event.peer_id, "⛔ Недостаточно прав.")
            return
        target_id, clean_args = get_target_and_clean_args(event, args)
        if not target_id or not clean_args:
            send_message(event.peer_id, "Использование: /-дофамин (ссылка/ответ) (кол-во)")
            return
        try:
            amount = int(clean_args[0])
        except:
            send_message(event.peer_id, "❌ Неверная сумма.")
            return
        row = db_get_user(target_id)
        if row:
            db_update_user(target_id, dofamin=max(0, row[4] - amount))
            send_message(event.peer_id, f"✅ Списано {amount} дофамина.")

    elif command == 'статвся':
        cursor.execute('SELECT COUNT(*), SUM(btc), SUM(dofamin), SUM(stars), SUM(poker_koins) FROM users')
        count, btc_sum, dof_sum, stars_sum, pkr_sum = cursor.fetchone()
        send_message(event.peer_id, f"📊 Общая статистика:\nПользователей: {count}\nБТС: {btc_sum or 0}\nДофамин: {dof_sum or 0}\nЗвёзды: {stars_sum or 0}\nPKR: {pkr_sum or 0}")

    elif command == 'givstar':
        if not is_admin(user_id):
            send_message(event.peer_id, "⛔ Недостаточно прав.")
            return
        target_id, clean_args = get_target_and_clean_args(event, args)
        if not target_id or not clean_args:
            send_message(event.peer_id, "Использование: /givstar (ссылка/ответ) (кол-во)")
            return
        try:
            amount = int(clean_args[0])
        except:
            send_message(event.peer_id, "❌ Неверная сумма.")
            return
        db_create_user(target_id)
        row = db_get_user(target_id)
        db_update_user(target_id, stars=row[11] + amount)
        send_message(event.peer_id, f"✅ Выдано {amount} звёзд.")

    elif command == '-kd':
        if not is_admin(user_id):
            send_message(event.peer_id, "⛔ Недостаточно прав.")
            return
        target_id, _ = get_target_and_clean_args(event, args)
        if target_id is None:
            target_id = user_id
        db_create_user(target_id)
        db_update_user(target_id, last_dofamin_time=0, last_steal_time=0, last_prize_time=0)
        send_message(event.peer_id, f"✅ Кулдауны сброшены для пользователя {target_id}.")

    elif command == '+токен':
        if not args:
            send_message(event.peer_id, "Использование: /+токен (токен)")
            return
        token = args[0]
        try:
            session = vk_api.VkApi(token=token)
            api = session.get_api()
            api.users.get(user_ids=user_id)
            db_create_user(user_id, access_token=token)
            db_update_user(user_id, access_token=token)
            if user_id in user_threads and user_threads[user_id].is_alive():
                user_sessions[user_id] = session
            else:
                t = threading.Thread(target=run_user_bot, args=(user_id, token), daemon=True)
                user_threads[user_id] = t
                t.start()
            send_message(event.peer_id, "✅ Токен сохранён, self-bot запущен.")
        except Exception as e:
            send_message(event.peer_id, f"❌ Ошибка: {e}")

    elif command == 'забгерцог':
        if not is_admin(user_id):
            send_message(event.peer_id, "⛔ Недостаточно прав.")
            return
        target_id, _ = get_target_and_clean_args(event, args)
        if not target_id:
            send_message(event.peer_id, "Укажите пользователя.")
            return
        db_create_user(target_id)
        db_update_user(target_id, herzog=0, herzog_expiry=0)
        send_message(event.peer_id, f"✅ Герцог убран у пользователя {target_id}.")

    elif command == 'история':
        target_id, _ = get_target_and_clean_args(event, args)
        target_id = target_id or user_id
        cursor.execute('SELECT action, timestamp FROM history WHERE user_id=? ORDER BY timestamp DESC LIMIT 10', (target_id,))
        rows = cursor.fetchall()
        if not rows:
            send_message(event.peer_id, "История пуста.")
            return
        msg = "📖 История действий:\n"
        for action, ts in rows:
            time_str = datetime.datetime.fromtimestamp(ts).strftime('%d.%m.%Y %H:%M')
            msg += f"{time_str} — {action}\n"
        send_message(event.peer_id, msg)

    elif command == 'чекбан':
        target_id, _ = get_target_and_clean_args(event, args)
        target_id = target_id or user_id
        cursor.execute('SELECT reason, expires_at, banned_by FROM bans WHERE user_id=? AND (expires_at > ? OR expires_at = 0)', (target_id, time.time()))
        row = cursor.fetchone()
        if row:
            reason, expiry, banned_by = row
            if expiry == 0:
                expiry_str = "навсегда"
            else:
                expiry_str = datetime.datetime.fromtimestamp(expiry).strftime('%d.%m.%Y %H:%M')
            send_message(event.peer_id, f"⛔ Пользователь забанен.\nПричина: {reason}\nДо: {expiry_str}\nКем: {banned_by}")
        else:
            send_message(event.peer_id, "✅ Бан не найден.")

    elif command == 'баны':
        if not is_admin(user_id):
            send_message(event.peer_id, "⛔ Недостаточно прав.")
            return
        cursor.execute('SELECT user_id, reason, expires_at, banned_by FROM bans WHERE expires_at > ? OR expires_at = 0', (time.time(),))
        rows = cursor.fetchall()
        if not rows:
            send_message(event.peer_id, "Нет активных банов.")
            return
        msg = "⛔ Список банов:\n"
        for uid, reason, expiry, by in rows:
            if expiry == 0:
                expiry_str = 'навсегда'
            else:
                expiry_str = datetime.datetime.fromtimestamp(expiry).strftime('%d.%m.%Y %H:%M')
            msg += f"{uid} — {reason} (до {expiry_str})\n"
        send_message(event.peer_id, msg)

    elif command == 'block':
        if not is_admin(user_id):
            send_message(event.peer_id, "⛔ Недостаточно прав.")
            return
        target_id, clean_args = get_target_and_clean_args(event, args)
        if not target_id:
            send_message(event.peer_id, "Укажите пользователя.")
            return
        reason = ' '.join(clean_args[1:]) if len(clean_args) > 1 else 'Нарушение правил'
        duration = 0
        if clean_args:
            try:
                hours = int(clean_args[0])
                duration = time.time() + hours*3600
            except:
                pass
        cursor.execute('INSERT OR REPLACE INTO bans (user_id, reason, expires_at, banned_by) VALUES (?,?,?,?)', (target_id, reason, duration, user_id))
        conn.commit()
        send_message(event.peer_id, f"✅ Пользователь {target_id} заблокирован.")

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
        if not target_id:
            send_message(event.peer_id, "Укажите пользователя.")
            return
        db_create_user(target_id)
        db_update_user(target_id, protection=1)
        send_message(event.peer_id, f"✅ Защита выдана пользователю {target_id}.")

    elif command == 'чек':
        row = db_get_user(user_id)
        if not row:
            send_message(event.peer_id, "❌ Вы не зарегистрированы.")
            return
        send_message(event.peer_id, f"📊 Ваш баланс:\nБТС: {row[3]}\nДофамин: {row[4]}\nЗвёзды: {row[11]}\nPKR: {row[20]}")

    elif command == 'логи':
        if not is_admin(user_id):
            send_message(event.peer_id, "⛔ Недостаточно прав.")
            return
        limit = 20
        since = None
        if args:
            try:
                hours = float(args[0])
                since = time.time() - hours * 3600
                limit = 100
            except:
                limit = 20
        logs = get_command_logs(limit=limit, since=since)
        if not logs:
            send_message(event.peer_id, "Нет записей.")
            return
        msg = "📋 Последние команды:\n"
        for uid, cmd, args_str, cid, ts in logs:
            time_str = datetime.datetime.fromtimestamp(ts).strftime('%d.%m %H:%M')
            user_info = get_user_info(uid)
            name = f"{user_info['first_name']} {user_info['last_name']}" if user_info else str(uid)
            msg += f"{time_str} {name}: /{cmd} {args_str[:30]}\n"
            if len(msg) > 3500:
                send_message(event.peer_id, msg)
                msg = ""
        if msg:
            send_message(event.peer_id, msg)

    elif command == 'запрет':
        if not is_creator(user_id):
            send_message(event.peer_id, "⛔ Только создатель может запрещать команды.")
            return
        if not args:
            send_message(event.peer_id, "Использование: /запрет (команда)")
            return
        cmd = args[0].lower()
        if is_command_banned(cmd):
            send_message(event.peer_id, f"❌ Команда '{cmd}' уже запрещена.")
            return
        ban_command(cmd, user_id)
        send_message(event.peer_id, f"✅ Команда '{cmd}' запрещена.")

    elif command == 'разрешить':
        if not is_creator(user_id):
            send_message(event.peer_id, "⛔ Только создатель может разрешать команды.")
            return
        if not args:
            send_message(event.peer_id, "Использование: /разрешить (команда)")
            return
        cmd = args[0].lower()
        if not is_command_banned(cmd):
            send_message(event.peer_id, f"❌ Команда '{cmd}' не запрещена.")
            return
        unban_command(cmd)
        send_message(event.peer_id, f"✅ Команда '{cmd}' разрешена.")

    elif command == 'косметика':
        target_id, _ = get_target_and_clean_args(event, args)
        target_id = target_id or user_id
        buf = generate_profile_card(target_id)
        if not buf:
            send_message(event.peer_id, "❌ Не удалось создать карточку.")
            return
        attachment = upload_photo_bytes_to_vk(event.peer_id, buf.getvalue(), 'profile.png')
        if attachment:
            send_message(event.peer_id, "🎨 Ваш красивый профиль:", attachment=attachment)
        else:
            send_message(event.peer_id, "❌ Ошибка загрузки фото. Нужен токен с правом photos.")

    elif command == 'newreg':
        if not is_admin(user_id):
            send_message(event.peer_id, "⛔ Недостаточно прав.")
            return
        target_id, clean_args = get_target_and_clean_args(event, args)
        if target_id is None and len(clean_args) >= 2:
            target_id = extract_user_id_from_link(clean_args[1])
        if not target_id:
            send_message(event.peer_id, "Укажите пользователя ответом, ссылкой или упоминанием.")
            return
        if not clean_args:
            send_message(event.peer_id, "Использование: /newreg ДД.ММ.ГГГГ (ссылка) или ответьте на сообщение.")
            return
        date_str = clean_args[0]
        try:
            reg_ts = datetime.datetime.strptime(date_str, '%d.%m.%Y').timestamp()
        except:
            send_message(event.peer_id, "❌ Неверный формат даты. Используйте ДД.ММ.ГГГГ")
            return
        db_create_user(target_id)
        db_update_user(target_id, registered_at=reg_ts)
        send_message(event.peer_id, f"✅ Дата регистрации пользователя {target_id} изменена на {date_str}.")

    elif command == 'удалитьсемью':
        if not is_admin(user_id):
            send_message(event.peer_id, "⛔ Недостаточно прав.")
            return
        target_id, _ = get_target_and_clean_args(event, args)
        if not target_id:
            send_message(event.peer_id, "Укажите пользователя — создателя семьи.")
            return
        fid = get_family_by_user(target_id)
        if not fid:
            send_message(event.peer_id, "Пользователь не в семье.")
            return
        delete_family(fid)
        send_message(event.peer_id, f"Семья пользователя {target_id} удалена.")

    elif command == 'удалитьклан':
        if not is_admin(user_id):
            send_message(event.peer_id, "⛔ Недостаточно прав.")
            return
        target_id, _ = get_target_and_clean_args(event, args)
        if not target_id:
            send_message(event.peer_id, "Укажите пользователя — лидера клана.")
            return
        clan_id = get_clan_by_user(target_id)
        if not clan_id:
            send_message(event.peer_id, "Пользователь не в клане.")
            return
        cursor.execute('DELETE FROM clans WHERE id=?', (clan_id,))
        cursor.execute('DELETE FROM clan_members WHERE clan_id=?', (clan_id,))
        conn.commit()
        send_message(event.peer_id, f"Клан пользователя {target_id} удалён.")

    else:
        send_message(event.peer_id, "Неизвестная команда. Введите /help для списка.")


# ================= ЗАПУСК ОСНОВНОГО БОТА =================
print("Основной бот запущен. Ожидание сообщений...")
# Запускаем self-bot'ы для ранее зарегистрированных пользователей
start_all_user_bots()

for event in longpoll.listen():
    if event.type == VkEventType.MESSAGE_NEW:
        # Игнорируем исходящие сообщения (самого бота)
        if event.from_me:
            continue

        user_id = event.user_id

        # Обрабатываем только сообщения от создателя и администраторов
        if user_id in ADMIN_IDS or user_id == OWNER_ID:
            try:
                with vk_lock:
                    process_command(event)
            except Exception as e:
                print(f"Ошибка: {e}")
                send_message(OWNER_ID, f"❌ Ошибка: {e}")
            continue

        # Для остальных — только команда /reg (начинается с префикса)
        text = event.text or ''
        prefix = get_prefix(event.peer_id)  # можно использовать DEFAULT_PREFIX или БД
        if text.startswith(prefix):
            parts = text[len(prefix):].strip().split()
            if parts and parts[0].lower() == 'reg':
                try:
                    with vk_lock:
                        process_command(event)
                except Exception as e:
                    print(f"Ошибка при регистрации: {e}")
                    # Не отправляем пользователю, только логируем
