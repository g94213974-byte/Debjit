#!/usr/bin/env python3
# mass_bot_v10.py - FINAL (মাল্টি API - নো লগআউট)

import os
import sys
import json
import asyncio
import random
import logging
import threading
import time
from datetime import datetime, timedelta
from telethon import TelegramClient
from telethon.errors import FloodWaitError, SessionPasswordNeededError, AuthKeyUnregisteredError, UserDeactivatedError
from telethon.tl.functions.messages import GetDialogsRequest
from telethon.tl.types import InputPeerEmpty
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# ====== Flask HTTP ======
from flask import Flask

flask_app = Flask(__name__)

@flask_app.route("/")
def home():
    return "Bot is alive and running 24/7!"

@flask_app.route("/health")
def health():
    return "OK"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

flask_thread = threading.Thread(target=run_flask, daemon=True)
flask_thread.start()
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# ====== কন্ট্রোল বট ======
BOT_TOKEN = "8875386448:AAH2RMJixaVOyLPZkYJayh3WcGVrc5octnA"
OWNER_ID = 8001816524

# ====== ★★★ মাল্টি API ID/HASH লিস্ট (প্রাথমিক) ★★★ ======
# বট চালানোর পর বট থেকেই পরিবর্তন/যোগ/ডিলিট করতে পারবে
API_CREDENTIALS = {
    "api1": {"id": 34124317, "hash": "b6a4101c735dda0625454c22b579d702"},
    "api2": {"id": 37362415, "hash": "88f99afa3b9a81adce62267b701e7b9f"},
    "api3": {"id": 36952100, "hash": "21c793e15e6ceef225eeb83e5727d446"},
}
DEFAULT_API = "api1"
# ============================================================

DATA_FILE = "bot_data.json"
SESSIONS_DIR = "sessions"

running_tasks = {}
accounts_data = {}
blocked_users = []
allowed_users = []
pending_otp = {}
account_stats = {}
account_health = {}

MESSAGE = "𝟭𝟬 𝗠𝗜𝗡 𝗩𝗖 ₹𝟰𝟵 𝗕𝗔𝗕𝗬😘"
MIN_INTERVAL = 1
MAX_INTERVAL = 2
CYCLE_WAIT = 15
EXCLUDED_GROUPS = ["Admin Group", "Private Chat"]

SESSION_REFRESH_INTERVAL = 180
MAX_RETRIES = 10
KEEP_ALIVE_INTERVAL = 60


# ============================================================
# হেল্পার: API ক্রেডেনশিয়াল বের করা
# ============================================================

def get_api_creds(session_name):
    if session_name in accounts_data:
        api_key = accounts_data[session_name].get('api_key', DEFAULT_API)
    else:
        api_key = DEFAULT_API
    if api_key not in API_CREDENTIALS:
        api_key = DEFAULT_API
    return API_CREDENTIALS[api_key]["id"], API_CREDENTIALS[api_key]["hash"]

def get_api_key_name(session_name):
    if session_name in accounts_data:
        return accounts_data[session_name].get('api_key', DEFAULT_API)
    return DEFAULT_API


# ============================================================
# ডাটা সেভ/লোড
# ============================================================

def load_data():
    global accounts_data, blocked_users, allowed_users, MESSAGE, MIN_INTERVAL, MAX_INTERVAL, CYCLE_WAIT, account_stats, account_health, API_CREDENTIALS, DEFAULT_API
    
    default_data = {
        'accounts': {},
        'blocked_users': [],
        'allowed_users': [],
        'account_stats': {},
        'account_health': {},
        'api_credentials': {k: {"id": v["id"], "hash": v["hash"]} for k, v in API_CREDENTIALS.items()},
        'default_api': DEFAULT_API,
        'settings': {
            'message': MESSAGE,
            'min_interval': MIN_INTERVAL,
            'max_interval': MAX_INTERVAL,
            'cycle_wait': CYCLE_WAIT
        }
    }
    
    if not os.path.exists(DATA_FILE):
        save_data(default_data)
        return default_data
    
    try:
        with open(DATA_FILE, 'r') as f:
            data = json.load(f)
        
        if not isinstance(data, dict): data = default_data
        
        accounts_data = data.get('accounts', {})
        if not isinstance(accounts_data, dict): accounts_data = {}
        blocked_users = data.get('blocked_users', [])
        if not isinstance(blocked_users, list): blocked_users = []
        allowed_users = data.get('allowed_users', [])
        if not isinstance(allowed_users, list): allowed_users = []
        account_stats = data.get('account_stats', {})
        if not isinstance(account_stats, dict): account_stats = {}
        account_health = data.get('account_health', {})
        if not isinstance(account_health, dict): account_health = {}
        
        saved_apis = data.get('api_credentials', {})
        if saved_apis:
            API_CREDENTIALS.clear()
            for k, v in saved_apis.items():
                API_CREDENTIALS[k] = {"id": v.get("id", 0), "hash": v.get("hash", "")}
        
        saved_default = data.get('default_api', DEFAULT_API)
        if saved_default in API_CREDENTIALS:
            DEFAULT_API = saved_default
        
        settings = data.get('settings', {})
        if not isinstance(settings, dict): settings = {}
        MESSAGE = settings.get('message', MESSAGE)
        MIN_INTERVAL = settings.get('min_interval', MIN_INTERVAL)
        MAX_INTERVAL = settings.get('max_interval', MAX_INTERVAL)
        CYCLE_WAIT = settings.get('cycle_wait', CYCLE_WAIT)
        
        return data
    except:
        save_data(default_data)
        return default_data


def save_data(data=None):
    if data is None:
        data = {
            'accounts': accounts_data,
            'blocked_users': blocked_users,
            'allowed_users': allowed_users,
            'account_stats': account_stats,
            'account_health': account_health,
            'api_credentials': {k: {"id": v["id"], "hash": v["hash"]} for k, v in API_CREDENTIALS.items()},
            'default_api': DEFAULT_API,
            'settings': {
                'message': MESSAGE,
                'min_interval': MIN_INTERVAL,
                'max_interval': MAX_INTERVAL,
                'cycle_wait': CYCLE_WAIT
            }
        }
    try:
        with open(DATA_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    except:
        pass


# ============================================================
# ইউজার চেক
# ============================================================

async def is_user_allowed(user_id):
    if user_id == OWNER_ID: return True
    if user_id in blocked_users: return False
    if not allowed_users: return True
    return user_id in allowed_users


# ============================================================
# লগআউট প্রিভেনশন ইঞ্জিন
# ============================================================

async def keep_session_alive(session_name):
    while True:
        try:
            if session_name not in accounts_data:
                break
            if session_name in running_tasks and not running_tasks[session_name].done():
                await asyncio.sleep(SESSION_REFRESH_INTERVAL)
                continue
            
            session_file = f"{SESSIONS_DIR}/{session_name}.session"
            if not os.path.exists(session_file):
                break
            
            api_id, api_hash = get_api_creds(session_name)
            client = TelegramClient(session_file.replace('.session', ''), api_id, api_hash)
            await client.connect()
            
            if await client.is_user_authorized():
                me = await client.get_me()
                if me:
                    await client.get_dialogs(limit=1)
                    logger.info(f"🔄 [{session_name}] Session রিফ্রেশ: {me.first_name} (API: {get_api_key_name(session_name)})")
                    account_health[session_name] = {
                        'status': 'ok',
                        'user': me.first_name,
                        'last_check': datetime.now().isoformat()
                    }
                    save_data()
                else:
                    logger.warning(f"[{session_name}] ইউজার নেই!")
                    account_health[session_name] = {'status': 'no_user', 'last_check': datetime.now().isoformat()}
                    save_data()
            else:
                logger.warning(f"[{session_name}] Session অথরাইজড না!")
                account_health[session_name] = {'status': 'session_expired', 'last_check': datetime.now().isoformat()}
                save_data()
                try:
                    os.remove(session_file)
                    logger.info(f"[{session_name}] নষ্ট session মুছে ফেলা হয়েছে")
                except:
                    pass
                break
            
            await client.disconnect()
            await asyncio.sleep(SESSION_REFRESH_INTERVAL)
        except Exception as e:
            logger.error(f"[{session_name}] Session রিফ্রেশ error: {e}")
            await asyncio.sleep(30)


async def check_account_health(session_name):
    if session_name not in accounts_data:
        return False
    session_file = f"{SESSIONS_DIR}/{session_name}.session"
    if not os.path.exists(session_file):
        logger.warning(f"[{session_name}] Session ফাইল নেই!")
        return False
    
    api_id, api_hash = get_api_creds(session_name)
    
    for attempt in range(MAX_RETRIES):
        try:
            client = TelegramClient(session_file.replace('.session', ''), api_id, api_hash)
            await client.connect()
            if not await client.is_user_authorized():
                logger.warning(f"[{session_name}] Session মেয়াদ শেষ!")
                try:
                    os.remove(session_file)
                except:
                    pass
                await client.disconnect()
                return False
            try:
                me = await client.get_me()
                if me:
                    await client.get_dialogs(limit=1)
                    logger.info(f"✅ [{session_name}] হেলথ OK: {me.first_name}")
                    account_health[session_name] = {
                        'status': 'ok',
                        'user': me.first_name,
                        'last_check': datetime.now().isoformat()
                    }
                    save_data()
                    await client.disconnect()
                    return True
            except (AuthKeyUnregisteredError, UserDeactivatedError) as e:
                logger.warning(f"[{session_name}] একাউন্ট ডিএকটিভেটেড: {e}")
                try:
                    os.remove(session_file)
                except:
                    pass
                await client.disconnect()
                return False
            except Exception as e:
                logger.warning(f"[{session_name}] get_me error: {e}")
            await client.disconnect()
        except Exception as e:
            logger.error(f"[{session_name}] হেলথ চেক error (attempt {attempt+1}): {e}")
            await asyncio.sleep(5)
    return False


async def health_check_all():
    while True:
        try:
            for sn in list(accounts_data.keys()):
                if sn not in running_tasks or running_tasks[sn].done():
                    await check_account_health(sn)
                await asyncio.sleep(2)
            await asyncio.sleep(SESSION_REFRESH_INTERVAL)
        except Exception as e:
            logger.error(f"হেলথ চেক error: {e}")
            await asyncio.sleep(30)


# ============================================================
# বট হ্যান্ডলার
# ============================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    if not await is_user_allowed(user_id):
        await update.message.reply_text("❌ আপনি অনুমোদিত নন!")
        return
    
    if user_id != OWNER_ID:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📊 স্ট্যাটাস", callback_data='user_status')]
        ])
        await update.message.reply_text(f"👋 স্বাগতম {user.first_name}!", reply_markup=keyboard)
        return
    
    running = sum(1 for sn in running_tasks if sn in running_tasks and not running_tasks[sn].done())
    total = len(accounts_data)
    healthy = sum(1 for sn in accounts_data if account_health.get(sn, {}).get('status') == 'ok')
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 অ্যাকাউন্ট", callback_data='accounts')],
        [InlineKeyboardButton("⚙️ সেটিংস", callback_data='settings')],
        [InlineKeyboardButton("🔐 API কী ম্যানেজ", callback_data='api_manage')],
        [InlineKeyboardButton("🔒 ইউজার", callback_data='user_manage')],
        [InlineKeyboardButton("▶️ সব চালু", callback_data='start_all')],
        [InlineKeyboardButton("⏹️ সব বন্ধ", callback_data='stop_all')],
        [InlineKeyboardButton("🩺 হেলথ চেক", callback_data='health_check')],
        [InlineKeyboardButton(f"📊 স্ট্যাটাস ({running}/{total})", callback_data='status')]
    ])
    
    api_count = len(API_CREDENTIALS)
    
    await update.message.reply_text(
        f"🤖 *ম্যাসেজিং বট v10 - মাল্টি API*\n\n"
        f"🔐 API কী: `{api_count}টি` (ডিফল্ট: `{DEFAULT_API}`)\n"
        f"🛡️ লগআউট প্রোটেকশন ✅\n"
        f"⚡ {MIN_INTERVAL}-{MAX_INTERVAL}s · সাইকেল {CYCLE_WAIT}s\n"
        f"📊 চলছে: {running}/{total} · হেলদি: {healthy}\n\n"
        f"অ্যাকাউন্ট যোগ করে OTP দিন 🚀\n\n"
        f"🔐 **API ম্যানেজ** বাটন থেকে API ID/HASH যোগ/পরিবর্তন/ডিলিট করতে পারো!",
        parse_mode='Markdown', reply_markup=keyboard
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    if not await is_user_allowed(user_id): return
    
    data = query.data
    
    if data == 'user_status':
        running = sum(1 for sn in running_tasks if sn in running_tasks and not running_tasks[sn].done())
        healthy = sum(1 for sn in accounts_data if account_health.get(sn, {}).get('status') == 'ok')
        await query.edit_message_text(f"📊 চলছে: {running}/{len(accounts_data)} | হেলদি: {healthy}")
        return
    
    if user_id != OWNER_ID: return
    
    if data == 'accounts':
        await show_accounts(query)
    elif data == 'add_account':
        context.user_data['awaiting_input'] = 'add_account'
        api_list_text = '\n'.join([f"`{k}` — ID: `{v['id']}`" for k, v in API_CREDENTIALS.items()])
        await query.edit_message_text(
            f"📱 *একাউন্ট যোগ (মোট: {len(accounts_data)}টি)*\n\n"
            "ফরম্যাট:\n"
            "`নাম,ফোন_নম্বর`\n\n"
            "উদাহরণ:\n"
            "`acc1,+8801712345678`\n"
            "`acc2,+8801712345679`\n\n"
            f"🔐 উপলব্ধ API কী:\n{api_list_text}\n\n"
            f"⚠️ ডিফল্ট API (`{DEFAULT_API}`) ইউজ হবে।\n"
            f"একাউন্ট ভিউতে গিয়ে API পরিবর্তন করতে পারো।\n\n"
            "'বাতিল' বাতিল করতে।",
            parse_mode='Markdown'
        )
    elif data == 'add_bulk':
        context.user_data['awaiting_input'] = 'add_bulk'
        await query.edit_message_text(
            f"📱 *একসাথে যোগ*\n\n"
            "প্রতি লাইনে:\n"
            "`নাম,ফোন`\n\n"
            "উদাহরণ:\n"
            "```\n"
            "acc1,+8801712345678\n"
            "acc2,+8801712345679\n"
            "acc3,+8801712345680\n"
            "```\n\n"
            "🔐 ডিফল্ট API {DEFAULT_API} ইউজ হবে।\n"
            "পরে API পরিবর্তন করতে পারো।\n\n"
            "'বাতিল' বাতিল।",
            parse_mode='Markdown'
        )
    elif data.startswith('view_'):
        sn = data.replace('view_', '')
        context.user_data['last_viewed'] = sn
        await view_account(query, sn)
    elif data.startswith('delete_'):
        sn = data.replace('delete_', '')
        await delete_account(query, sn)
    elif data.startswith('toggle_'):
        sn = data.replace('toggle_', '')
        await toggle_account(query, sn)
    elif data == 'send_otp':
        sn = context.user_data.get('last_viewed', '')
        if sn and sn in accounts_data:
            await send_otp_process(query, sn)
        else:
            await query.edit_message_text("❌ একাউন্ট সিলেক্ট করুন!")
    elif data == 'settings':
        await show_settings(query)
    elif data == 'edit_message':
        context.user_data['awaiting_input'] = 'edit_message'
        await query.edit_message_text(f"✏️ নতুন ম্যাসেজ:\nবর্তমান: `{MESSAGE}`", parse_mode='Markdown')
    elif data == 'edit_interval':
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"📉 মিন ({MIN_INTERVAL}s)", callback_data='edit_min'),
             InlineKeyboardButton(f"📈 ম্যাক্স ({MAX_INTERVAL}s)", callback_data='edit_max')],
            [InlineKeyboardButton(f"🔄 সাইকেল ({CYCLE_WAIT}s)", callback_data='edit_cycle')],
            [InlineKeyboardButton("⚡ প্রিসেট স্পিড", callback_data='preset_speed')],
            [InlineKeyboardButton("🔙 ফিরে", callback_data='settings')]
        ])
        await query.edit_message_text(f"⚙️ *ইন্টারভাল*\n\nবর্তমান: মিন {MIN_INTERVAL}s · ম্যাক্স {MAX_INTERVAL}s · সাইকেল {CYCLE_WAIT}s", parse_mode='Markdown', reply_markup=kb)
    elif data in ['edit_min', 'edit_max', 'edit_cycle']:
        context.user_data['awaiting_input'] = data
        labels = {'edit_min': 'মিনিমাম', 'edit_max': 'ম্যাক্সিমাম', 'edit_cycle': 'সাইকেল'}
        vals = {'edit_min': MIN_INTERVAL, 'edit_max': MAX_INTERVAL, 'edit_cycle': CYCLE_WAIT}
        await query.edit_message_text(f"✏️ *{labels[data]}*\nবর্তমান: `{vals[data]}`s\n\nনতুন মান (সেকেন্ড):", parse_mode='Markdown')
    elif data == 'preset_speed':
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🚀 আল্ট্রা (১/২সে · সাইকেল ১০সে)", callback_data='speed_ultra')],
            [InlineKeyboardButton("⚡ সুপার (২/৪সে · সাইকেল ২০সে)", callback_data='speed_super')],
            [InlineKeyboardButton("🔥 ফাস্ট (৩/৫সে · সাইকেল ৩০সে)", callback_data='speed_fast')],
            [InlineKeyboardButton("⏩ নরমাল (৫/১০সে · সাইকেল ৬০সে)", callback_data='speed_normal')],
            [InlineKeyboardButton("🔙 ফিরে", callback_data='edit_interval')]
        ])
        await query.edit_message_text("⚡ *প্রিসেট স্পিড*\n\nএকটি সিলেক্ট করুন:", parse_mode='Markdown', reply_markup=kb)
    elif data == 'speed_ultra':
        set_speed(1, 2, 10); await query.answer("✅ !"); await show_settings(query)
    elif data == 'speed_super':
        set_speed(2, 4, 20); await query.answer("✅ !"); await show_settings(query)
    elif data == 'speed_fast':
        set_speed(3, 5, 30); await query.answer("✅ !"); await show_settings(query)
    elif data == 'speed_normal':
        set_speed(5, 10, 60); await query.answer("✅ !"); await show_settings(query)
    elif data == 'start_all':
        await start_all_accounts(query)
    elif data == 'stop_all':
        await stop_all_accounts(query)
    elif data == 'status':
        await show_status(query)
    elif data == 'health_check':
        await health_check_button(query)
    elif data == 'user_manage':
        await show_user_management(query)
    
    # ====== API ম্যানেজমেন্ট ======
    elif data == 'api_manage':
        await show_api_management(query)
    elif data == 'add_api':
        context.user_data['awaiting_input'] = 'add_api'
        await query.edit_message_text(
            "🔐 *নতুন API কী যোগ*\n\n"
            "ফরম্যাট:\n"
            "`কী_নাম,API_ID,API_HASH`\n\n"
            "উদাহরণ:\n"
            "`api4,123456,abc123def456...`\n\n"
            "⚠️ কী_নাম ইউনিক হতে হবে (যেমন: api1, api2, main, backup ইত্যাদি)\n"
            "'বাতিল' বাতিল করতে।",
            parse_mode='Markdown'
        )
    elif data.startswith('delapi_'):
        api_key = data.replace('delapi_', '')
        if api_key in API_CREDENTIALS:
            del API_CREDENTIALS[api_key]
            if DEFAULT_API == api_key:
                if API_CREDENTIALS:
                    global DEFAULT_API
                    DEFAULT_API = list(API_CREDENTIALS.keys())[0]
            save_data()
            await query.answer(f"✅ `{api_key}` ডিলিট!")
        await show_api_management(query)
    elif data.startswith('setdef_'):
        api_key = data.replace('setdef_', '')
        if api_key in API_CREDENTIALS:
            global DEFAULT_API
            DEFAULT_API = api_key
            save_data()
            await query.answer(f"✅ ডিফল্ট `{api_key}`!")
        await show_api_management(query)
    elif data.startswith('setaccapi_'):
        parts = data.replace('setaccapi_', '').split('_', 1)
        if len(parts) == 2:
            api_key, sn = parts
            if sn in accounts_data and api_key in API_CREDENTIALS:
                accounts_data[sn]['api_key'] = api_key
                save_data()
                await query.answer(f"✅ `{sn}` → `{api_key}`!")
            else:
                await query.answer("❌ ব্যর্থ!")
        sn = context.user_data.get('last_viewed', '')
        if sn:
            await view_account(query, sn)
        else:
            await show_accounts(query)
    
    elif data in ['add_blocked_user', 'add_allowed_user', 'remove_blocked_user', 'remove_allowed_user']:
        labels = {
            'add_blocked_user': '🔒 ব্লক করতে আইডি:',
            'add_allowed_user': '✅ অনুমতি দিতে আইডি:',
            'remove_blocked_user': '🔓 আনব্লক করতে আইডি:',
            'remove_allowed_user': '❌ অনুমতি সরাতে আইডি:'
        }
        context.user_data['awaiting_input'] = data
        await query.edit_message_text(labels[data])
    elif data == 'toggle_mode':
        if allowed_users: allowed_users.clear(); await query.answer("✅ সবাই!")
        else:
            if OWNER_ID not in allowed_users: allowed_users.append(OWNER_ID)
            await query.answer("✅ শুধু অনুমতি!")
        save_data()
        await show_user_management(query)
    elif data == 'back':
        running = sum(1 for sn in running_tasks if sn in running_tasks and not running_tasks[sn].done())
        total = len(accounts_data)
        healthy = sum(1 for sn in accounts_data if account_health.get(sn, {}).get('status') == 'ok')
        api_count = len(API_CREDENTIALS)
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("👥 অ্যাকাউন্ট", callback_data='accounts')],
            [InlineKeyboardButton("⚙️ সেটিংস", callback_data='settings')],
            [InlineKeyboardButton("🔐 API কী", callback_data='api_manage')],
            [InlineKeyboardButton("🔒 ইউজার", callback_data='user_manage')],
            [InlineKeyboardButton("▶️ সব চালু", callback_data='start_all')],
            [InlineKeyboardButton("⏹️ সব বন্ধ", callback_data='stop_all')],
            [InlineKeyboardButton("🩺 হেলথ চেক", callback_data='health_check')],
            [InlineKeyboardButton(f"📊 স্ট্যাটাস ({running}/{total})", callback_data='status')]
        ])
        await query.edit_message_text(
            f"🤖 *ম্যাসেজিং বট v10 - মাল্টি API*\n"
            f"🔐 {api_count}টি API · ডিফল্ট `{DEFAULT_API}`\n"
            f"🛡️ নো লগআউট · হেলদি: {healthy} · চলছে: {running}/{total}\n"
            f"⚡ {MIN_INTERVAL}-{MAX_INTERVAL}s · সাইকেল {CYCLE_WAIT}s",
            parse_mode='Markdown', reply_markup=kb
        )


def set_speed(min_s, max_s, cycle_s):
    global MIN_INTERVAL, MAX_INTERVAL, CYCLE_WAIT
    MIN_INTERVAL = min_s
    MAX_INTERVAL = max_s
    CYCLE_WAIT = cycle_s
    save_data()


# ============================================================
# API ম্যানেজমেন্ট ইউআই
# ============================================================

async def show_api_management(query):
    text = "🔐 *API কী ম্যানেজ*\n\n"
    text += "বট থেকেই API ID/HASH যোগ/পরিবর্তন/ডিলিট করতে পারো!\n\n"
    
    for k, v in API_CREDENTIALS.items():
        is_default = "⭐ " if k == DEFAULT_API else ""
        text += f"{is_default}`{k}` → ID: `{v['id']}`, HASH: `{v['hash'][:8]}...`\n"
    
    text += f"\nমোট: `{len(API_CREDENTIALS)}`টি API কী"
    text += f"\nডিফল্ট: `{DEFAULT_API}`"
    
    kb = []
    kb.append([InlineKeyboardButton("➕ নতুন API যোগ", callback_data='add_api')])
    
    for k in API_CREDENTIALS.keys():
        row = []
        if k != DEFAULT_API:
            row.append(InlineKeyboardButton(f"⭐ ডিফল্ট সেট", callback_data=f'setdef_{k}'))
        if len(API_CREDENTIALS) > 1:
            row.append(InlineKeyboardButton(f"🗑️ {k}", callback_data=f'delapi_{k}'))
        if row:
            kb.append(row)
    
    kb.append([InlineKeyboardButton("🔙 ফিরে", callback_data='back')])
    
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb))


# ============================================================
# অ্যাকাউন্ট ইউআই
# ============================================================

async def show_accounts(query):
    if not accounts_data:
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ যোগ", callback_data='add_account')],
            [InlineKeyboardButton("📋 একসাথে", callback_data='add_bulk')],
            [InlineKeyboardButton("🔙 ফিরে", callback_data='back')]
        ])
        await query.edit_message_text(
            f"📭 *কোন অ্যাকাউন্ট নেই*\n\n"
            f"🔐 মোট API: `{len(API_CREDENTIALS)}`টি · ডিফল্ট: `{DEFAULT_API}`\n"
            f"অ্যাকাউন্ট যোগ করে OTP দিন 🚀",
            parse_mode='Markdown', reply_markup=kb
        )
        return
    
    text = f"👥 *একাউন্ট ({len(accounts_data)}টি)*\n\n"
    text += f"🔐 মোট API: `{len(API_CREDENTIALS)}`টি · ডিফল্ট: `{DEFAULT_API}`\n\n"
    
    for sn in accounts_data:
        ok = sn in running_tasks and not running_tasks[sn].done()
        sf = f"{SESSIONS_DIR}/{sn}.session"
        hs = os.path.exists(sf)
        
        if ok: icon, st = '🟢', 'চালু'
        elif hs: icon, st = '🟡', 'লগইন'
        else: icon, st = '🔴', 'লগইন করেনি'
        
        api_key = accounts_data[sn].get('api_key', DEFAULT_API)
        sent = account_stats.get(sn, {}).get('sent', 0)
        text += f"{icon} `{sn}` — {st} · API: `{api_key}` (পাঠিয়েছে: {sent})\n"
    
    running = sum(1 for sn in running_tasks if sn in running_tasks and not running_tasks[sn].done())
    text += f"\n📊 চলছে: {running}/{len(accounts_data)}"
    
    kb = []
    for sn in list(accounts_data.keys())[:10]:
        kb.append([InlineKeyboardButton(f"👁️ {sn}", callback_data=f'view_{sn}')])
    
    kb.append([InlineKeyboardButton("➕ যোগ", callback_data='add_account'), InlineKeyboardButton("📋 বাল্ক", callback_data='add_bulk')])
    kb.append([InlineKeyboardButton("🔙 ফিরে", callback_data='back')])
    
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb))


async def view_account(query, sn):
    if sn not in accounts_data:
        await query.edit_message_text("❌ নেই!")
        return
    
    acc = accounts_data[sn]
    ok = sn in running_tasks and not running_tasks[sn].done()
    sf = f"{SESSIONS_DIR}/{sn}.session"
    hs = os.path.exists(sf)
    
    if ok: st = "✅ চালু"
    elif hs: st = "🟡 লগইন (বন্ধ)"
    else: st = "🔴 লগইন করেনি"
    
    api_key = acc.get('api_key', DEFAULT_API)
    api_id, api_hash = get_api_creds(sn)
    
    health = account_health.get(sn, {})
    h_status = health.get('status', 'unknown')
    h_user = health.get('user', 'N/A')
    h_last = health.get('last_check', 'N/A')
    
    stats = account_stats.get(sn, {})
    sent = stats.get('sent', 0)
    last_sent = stats.get('last_sent', 'N/A')
    groups_found = stats.get('groups', 0)
    
    text = f"📱 *{sn}*\n"
    text += f"স্ট্যাটাস: {st}\n"
    text += f"🩺 হেলথ: {h_status} | ইউজার: {h_user}\n"
    text += f"ফোন: `{acc['phone']}`\n"
    text += f"🔐 API কী: `{api_key}` (ID: `{api_id}`)\n"
    text += f"পাঠিয়েছে: {sent}টি\n"
    text += f"শেষবার: {last_sent}\n"
    text += f"গ্রুপ: {groups_found}টি\n"
    text += f"শেষ হেলথ: {h_last}\n"
    
    but = []
    
    if ok:
        but.append([InlineKeyboardButton("⏹️ বন্ধ", callback_data=f'toggle_{sn}')])
    elif hs:
        but.append([InlineKeyboardButton("▶️ চালু", callback_data=f'toggle_{sn}')])
    else:
        but.append([InlineKeyboardButton("📱 OTP পাঠান", callback_data='send_otp')])
    
    # API পরিবর্তন বাটন
    api_row = []
    for ak in API_CREDENTIALS.keys():
        if ak != api_key:
            api_row.append(InlineKeyboardButton(f"🔐 {ak}", callback_data=f'setaccapi_{ak}_{sn}'))
    if api_row:
        but.append(api_row)
    
    but.append([InlineKeyboardButton("🗑️ ডিলিট", callback_data=f'delete_{sn}')])
    but.append([InlineKeyboardButton("🔙 ফিরে", callback_data='accounts')])
    
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(but))


async def send_otp_process(query, sn):
    if sn not in accounts_data:
        await query.edit_message_text("❌ নেই!")
        return
    
    acc = accounts_data[sn]
    phone = acc['phone']
    api_id, api_hash = get_api_creds(sn)
    
    await query.edit_message_text(
        f"📱 *OTP পাঠানো হচ্ছে...*\n\n"
        f"ফোন: `{phone}`\n"
        f"🔐 API ID: `{api_id}`\n"
        f"API কী: `{get_api_key_name(sn)}`\n"
        f"অপেক্ষা করুন...",
        parse_mode='Markdown'
    )
    
    try:
        client = TelegramClient(f"{SESSIONS_DIR}/{sn}", api_id, api_hash)
        await client.connect()
        
        if await client.is_user_authorized():
            me = await client.get_me()
            account_health[sn] = {'status': 'ok', 'user': me.first_name, 'last_check': datetime.now().isoformat()}
            save_data()
            await query.edit_message_text(
                f"✅ *ইতিমধ্যে লগইন!*\n\n"
                f"একাউন্ট: `{sn}`\n"
                f"ব্যবহারকারী: {me.first_name}\n"
                f"API কী: `{get_api_key_name(sn)}`\n\n"
                f"এখন ▶️ চালু করুন।",
                parse_mode='Markdown'
            )
            await client.disconnect()
            return
        
        result = await client.send_code_request(phone)
        
        pending_otp[sn] = {
            'client': client,
            'phone': phone,
            'phone_code_hash': result.phone_code_hash,
            'api_key': get_api_key_name(sn),
            'api_id': api_id,
            'api_hash': api_hash
        }
        
        await query.edit_message_text(
            f"✅ *OTP পাঠানো হয়েছে!*\n\n"
            f"একাউন্ট: `{sn}`\n"
            f"ফোন: `{phone}`\n"
            f"🔐 API: `{get_api_key_name(sn)}` (ID: `{api_id}`)\n\n"
            f"📩 কোড এসেছে টেলিগ্রাম অ্যাপে\n"
            f"লিখুন: `otp_{sn} 12345`",
            parse_mode='Markdown'
        )
        
    except Exception as e:
        await query.edit_message_text(f"❌ OTP ব্যর্থ: {e}")


async def delete_account(query, sn):
    if sn in running_tasks and not running_tasks[sn].done():
        running_tasks[sn].cancel()
        if sn in running_tasks: del running_tasks[sn]
    
    if sn in accounts_data: del accounts_data[sn]
    if sn in account_stats: del account_stats[sn]
    if sn in account_health: del account_health[sn]
    save_data()
    
    sf = f"{SESSIONS_DIR}/{sn}.session"
    if os.path.exists(sf): os.remove(sf)
    
    if sn in pending_otp:
        try: await pending_otp[sn]['client'].disconnect()
        except: pass
        del pending_otp[sn]
    
    await query.answer(f"✅ `{sn}` ডিলিট!")
    await show_accounts(query)


async def toggle_account(query, sn):
    if sn not in accounts_data:
        await query.answer("❌ নেই!")
        return
    
    sf = f"{SESSIONS_DIR}/{sn}.session"
    if not os.path.exists(sf):
        await query.answer("❌ আগে OTP দিন!")
        return
    
    if sn in running_tasks and not running_tasks[sn].done():
        running_tasks[sn].cancel()
        if sn in running_tasks: del running_tasks[sn]
        await query.answer("⏹️ বন্ধ!")
    else:
        health_ok = await check_account_health(sn)
        if not health_ok:
            await query.answer("❌ Session নষ্ট! আবার OTP দিন।")
            await view_account(query, sn)
            return
        
        running_tasks[sn] = asyncio.create_task(run_account_keep_alive(sn))
        await query.answer("▶️ চালু!")
    
    await asyncio.sleep(2)
    await show_accounts(query)


async def show_settings(query):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ ম্যাসেজ", callback_data='edit_message')],
        [InlineKeyboardButton("⏱️ ইন্টারভাল", callback_data='edit_interval')],
        [InlineKeyboardButton("🔙 ফিরে", callback_data='back')]
    ])
    
    api_count = len(API_CREDENTIALS)
    
    await query.edit_message_text(
        f"⚙️ *সেটিংস*\n\n"
        f"📝 ম্যাসেজ: `{MESSAGE}`\n"
        f"⏱️ মিন: `{MIN_INTERVAL}`s\n"
        f"⏱️ ম্যাক্স: `{MAX_INTERVAL}`s\n"
        f"🔄 সাইকেল: `{CYCLE_WAIT}`s\n"
        f"🔐 API কী: `{api_count}টি` · ডিফল্ট: `{DEFAULT_API}`",
        parse_mode='Markdown', reply_markup=kb
    )


async def show_user_management(query):
    mode = "🔓 সবাই" if not allowed_users else "🔒 শুধু অনুমতি"
    text = f"🔒 *ইউজার*\n\nমোড: {mode}\n\n🚫 ব্লক:\n"
    text += '\n'.join(f'• `{u}`' for u in blocked_users) if blocked_users else '• নেই'
    text += "\n\n✅ অনুমতি:\n"
    text += '\n'.join(f'• `{u}`' for u in allowed_users) if allowed_users else '• সবাই'
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔒 ব্লক", callback_data='add_blocked_user'),
         InlineKeyboardButton("🔓 আনব্লক", callback_data='remove_blocked_user')],
        [InlineKeyboardButton("✅ অনুমতি", callback_data='add_allowed_user'),
         InlineKeyboardButton("❌ সরান", callback_data='remove_allowed_user')],
        [InlineKeyboardButton("🔄 মোড", callback_data='toggle_mode')],
        [InlineKeyboardButton("🔙 ফিরে", callback_data='back')]
    ])
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=kb)


async def start_all_accounts(query):
    if not accounts_data:
        await query.edit_message_text("❌ নেই!")
        return
    
    c = 0
    errors = []
    
    for sn in accounts_data:
        sf = f"{SESSIONS_DIR}/{sn}.session"
        if not os.path.exists(sf):
            errors.append(f"{sn}: লগইন করেনি")
            continue
        
        health_ok = await check_account_health(sn)
        if not health_ok:
            errors.append(f"{sn}: session নষ্ট")
            continue
        
        if sn not in running_tasks or running_tasks[sn].done():
            running_tasks[sn] = asyncio.create_task(run_account_keep_alive(sn))
            c += 1
    
    reply = f"✅ {c} টি চালু!\n"
    if errors:
        reply += "\n❌ ব্যর্থ:\n" + '\n'.join(errors)
    
    await query.answer(f"✅ {c} চালু!")
    await query.edit_message_text(reply)


async def stop_all_accounts(query):
    c = 0
    for sn in list(running_tasks.keys()):
        if not running_tasks[sn].done():
            running_tasks[sn].cancel()
            if sn in running_tasks: del running_tasks[sn]
            c += 1
    await query.answer(f"⏹️ {c} বন্ধ!")
    await query.edit_message_text(f"⏹️ {c} টি বন্ধ!")


async def health_check_button(query):
    await query.edit_message_text("🩺 *হেলথ চেক চলছে...*\n\nসব একাউন্ট চেক করা হচ্ছে...", parse_mode='Markdown')
    
    ok_count = 0
    fail_count = 0
    
    for sn in list(accounts_data.keys()):
        result = await check_account_health(sn)
        if result: ok_count += 1
        else: fail_count += 1
        await asyncio.sleep(1)
    
    running = sum(1 for sn in running_tasks if sn in running_tasks and not running_tasks[sn].done())
    
    text = f"🩺 *হেলথ চেক সম্পন্ন*\n\n✅ ভালো: {ok_count}\n❌ নষ্ট: {fail_count}\n▶️ চলছে: {running}\n\n"
    if fail_count > 0:
        text += "🔴 নষ্ট একাউন্টে আবার OTP দিন।\n"
    
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 ফিরে", callback_data='back')]])
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=kb)


async def show_status(query):
    text = "📊 *স্ট্যাটাস*\n\n"
    
    if not accounts_data:
        text += "❌ কোনো অ্যাকাউন্ট নেই"
    else:
        r, l, h = 0, 0, 0
        ts = 0
        
        for sn in accounts_data:
            ok = sn in running_tasks and not running_tasks[sn].done()
            hs = os.path.exists(f"{SESSIONS_DIR}/{sn}.session")
            health_ok = account_health.get(sn, {}).get('status') == 'ok'
            api_key = accounts_data[sn].get('api_key', DEFAULT_API)
            
            sent = account_stats.get(sn, {}).get('sent', 0)
            ts += sent
            
            if ok:
                text += f"🟢 `{sn}` (API: `{api_key}`, পাঠিয়েছে: {sent})\n"; r += 1
                if hs: l += 1
                if health_ok: h += 1
            elif hs:
                text += f"🟡 `{sn}` (API: `{api_key}`, পাঠিয়েছে: {sent})\n"; l += 1
                if health_ok: h += 1
            else:
                text += f"🔴 `{sn}` (API: `{api_key}`)\n"
        
        text += f"\nমোট: {len(accounts_data)}টি"
        text += f"\nলগইন: {l}টি | চলছে: {r}টি | হেলদি: {h}টি"
        text += f"\nমোট পাঠিয়েছে: {ts}"
    
    text += f"\n\n📝 `{MESSAGE}`"
    text += f"\n⏱️ `{MIN_INTERVAL}`-`{MAX_INTERVAL}`s | 🔄 `{CYCLE_WAIT}`s"
    text += f"\n🔐 API কী: `{len(API_CREDENTIALS)}`টি · ডিফল্ট: `{DEFAULT_API}`"
    
    await query.edit_message_text(text, parse_mode='Markdown')


# ============================================================
# টেক্সট হ্যান্ডলার
# ============================================================

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    if not await is_user_allowed(user_id): return
    
    # ====== OTP কোড ======
    if text.startswith('otp_') and user_id == OWNER_ID:
        parts = text.split(' ', 1)
        if len(parts) == 2:
            sn = parts[0].replace('otp_', '')
            code = parts[1].strip()
            
            if sn in pending_otp:
                login_data = pending_otp[sn]
                client = login_data['client']
                phone = login_data['phone']
                phone_code_hash = login_data['phone_code_hash']
                api_key = login_data.get('api_key', DEFAULT_API)
                
                await update.message.reply_text("⏳ ভেরিফাই করা হচ্ছে...")
                
                try:
                    user = await client.sign_in(phone=phone, code=code, phone_code_hash=phone_code_hash)
                    me = await client.get_me()
                    logger.info(f"✅ [{sn}] OTP লগইন! {me.first_name} (API: {api_key})")
                    
                    account_health[sn] = {'status': 'ok', 'user': me.first_name, 'last_check': datetime.now().isoformat()}
                    save_data()
                    del pending_otp[sn]
                    
                    asyncio.create_task(keep_session_alive(sn))
                    
                    await update.message.reply_text(
                        f"✅ *লগইন সফল!*\n\n"
                        f"একাউন্ট: `{sn}`\n"
                        f"ব্যবহারকারী: {me.first_name}\n"
                        f"🔐 API কী: `{api_key}`\n"
                        f"🛡️ অটো লগআউট প্রোটেকশন চালু ✅\n\n"
                        f"এখন ▶️ চালু করুন 🚀",
                        parse_mode='Markdown'
                    )
                    
                except SessionPasswordNeededError:
                    context.user_data['awaiting_input'] = f'2fa_{sn}'
                    await update.message.reply_text("🔑 *2FA পাসওয়ার্ড লাগবে!*\n\nপাসওয়ার্ড দিন:", parse_mode='Markdown')
                except Exception as e:
                    logger.error(f"[{sn}] OTP error: {e}")
                    await update.message.reply_text(f"❌ OTP ভুল: {e}\n\nআবার OTP পাঠান।")
                    try: await client.disconnect()
                    except: pass
                    if sn in pending_otp: del pending_otp[sn]
                return
            else:
                await update.message.reply_text("❌ OTP সেশন নেই! আবার OTP পাঠান।")
                return
    
    # ====== 2FA ======
    awaiting = context.user_data.get('awaiting_input')
    
    if awaiting and awaiting.startswith('2fa_') and user_id == OWNER_ID:
        sn = awaiting.replace('2fa_', '')
        if sn in pending_otp:
            client = pending_otp[sn]['client']
            api_key = pending_otp[sn].get('api_key', DEFAULT_API)
            await update.message.reply_text("⏳ 2FA ভেরিফাই করা হচ্ছে...")
            try:
                user = await client.sign_in(password=text)
                me = await client.get_me()
                account_health[sn] = {'status': 'ok', 'user': me.first_name, 'last_check': datetime.now().isoformat()}
                save_data()
                del pending_otp[sn]
                context.user_data['awaiting_input'] = None
                
                asyncio.create_task(keep_session_alive(sn))
                
                await update.message.reply_text(
                    f"✅ *2FA লগইন সফল!*\n\n"
                    f"একাউন্ট: `{sn}`\n"
                    f"ব্যবহারকারী: {me.first_name}\n"
                    f"🔐 API কী: `{api_key}`\n"
                    f"🛡️ অটো লগআউট প্রোটেকশন চালু ✅\n\n"
                    f"এখন ▶️ চালু করুন 🚀",
                    parse_mode='Markdown'
                )
            except Exception as e:
                await update.message.reply_text(f"❌ ভুল: {e}")
            return
    
    # ====== বাকি ইনপুট ======
    if user_id != OWNER_ID: return
    if not awaiting: return
    
    global MESSAGE, MIN_INTERVAL, MAX_INTERVAL, CYCLE_WAIT, DEFAULT_API
    
    if awaiting == 'add_account':
        if text.lower() == 'বাতিল':
            context.user_data['awaiting_input'] = None
            await update.message.reply_text("✅ বাতিল")
            return
        
        parts = text.split(',')
        if len(parts) != 2:
            await update.message.reply_text(
                "❌ ফরম্যাট: `নাম,ফোন`\nযেমন: `acc1,+8801712345678`",
                parse_mode='Markdown'
            )
            return
        
        sn, phone = parts[0].strip(), parts[1].strip()
        
        if not phone.startswith('+'):
            await update.message.reply_text("❌ ফোন + দিয়ে শুরু হবে!", parse_mode='Markdown')
            return
        
        if sn in accounts_data:
            await update.message.reply_text("❌ এই নামে আগে আছে!")
            return
        
        accounts_data[sn] = {'phone': phone, 'api_key': DEFAULT_API}
        os.makedirs(SESSIONS_DIR, exist_ok=True)
        save_data()
        context.user_data['awaiting_input'] = None
        
        await update.message.reply_text(
            f"✅ *যোগ! ({len(accounts_data)}টি)*\n\n"
            f"নাম: `{sn}`\n"
            f"ফোন: `{phone}`\n"
            f"🔐 API কী: `{DEFAULT_API}`\n\n"
            f"এখন OTP পাঠান লগইন করতে।\n"
            f"/start করুন",
            parse_mode='Markdown'
        )
    
    elif awaiting == 'add_bulk':
        if text.lower() == 'বাতিল':
            context.user_data['awaiting_input'] = None
            await update.message.reply_text("✅ বাতিল")
            return
        
        lines = text.strip().split('\n')
        added = 0
        errors = []
        
        for line in lines:
            line = line.strip()
            if not line: continue
            
            parts = line.split(',')
            if len(parts) != 2:
                errors.append(f"❌ ফরম্যাট: {line}")
                continue
            
            sn, phone = parts[0].strip(), parts[1].strip()
            
            if not phone.startswith('+'):
                errors.append(f"❌ {sn}: ফোন")
                continue
            
            if sn in accounts_data:
                errors.append(f"❌ {sn}: আগে আছে")
                continue
            
            accounts_data[sn] = {'phone': phone, 'api_key': DEFAULT_API}
            added += 1
        
        os.makedirs(SESSIONS_DIR, exist_ok=True)
        save_data()
        context.user_data['awaiting_input'] = None
        
        reply = f"✅ {added} টি যোগ! (মোট: {len(accounts_data)}টি)\n\n"
        if errors:
            reply += "ত্রুটি:\n" + '\n'.join(errors) + '\n\n'
        reply += "এখন OTP দিন প্রতিটি একাউন্টের জন্য।\n/start করুন"
        
        await update.message.reply_text(reply)
    
    elif awaiting == 'edit_message':
        MESSAGE = text
        save_data()
        context.user_data['awaiting_input'] = None
        await update.message.reply_text(f"✅ *আপডেট!*\n\n`{MESSAGE}`", parse_mode='Markdown')
    
    elif awaiting in ['edit_min', 'edit_max', 'edit_cycle']:
        if not text.isdigit() or int(text) < 1:
            await update.message.reply_text("❌ ১ বা তার বেশি দিন!"); return
        v = int(text)
        if awaiting == 'edit_min' and v >= MAX_INTERVAL:
            await update.message.reply_text(f"❌ মিন {MAX_INTERVAL} এর কম!"); return
        if awaiting == 'edit_max' and v <= MIN_INTERVAL:
            await update.message.reply_text(f"❌ ম্যাক্স {MIN_INTERVAL} এর বেশি!"); return
        if awaiting == 'edit_min': MIN_INTERVAL = v
        elif awaiting == 'edit_max': MAX_INTERVAL = v
        elif awaiting == 'edit_cycle': CYCLE_WAIT = v
        save_data()
        context.user_data['awaiting_input'] = None
        names = {'edit_min': 'মিন', 'edit_max': 'ম্যাক্স', 'edit_cycle': 'সাইকেল'}
        await update.message.reply_text(f"✅ *{names[awaiting]}*\n`{v}`s", parse_mode='Markdown')
    
    # ====== API যোগ করা (বট থেকেই) ======
    elif awaiting == 'add_api':
        if text.lower() == 'বাতিল':
            context.user_data['awaiting_input'] = None
            await update.message.reply_text("✅ বাতিল")
            return
        
        parts = text.split(',')
        if len(parts) != 3:
            await update.message.reply_text(
                "❌ ফরম্যাট: `কী_নাম,API_ID,API_HASH`\nযেমন: `api4,123456,abcdef...`",
                parse_mode='Markdown'
            )
            return
        
        key_name, api_id_str, api_hash = parts[0].strip(), parts[1].strip(), parts[2].strip()
        
        if not api_id_str.isdigit():
            await update.message.reply_text("❌ API_ID সংখ্যা হতে হবে!")
            return
        
        if key_name in API_CREDENTIALS:
            await update.message.reply_text("❌ এই নামে আগে আছে! ভিন্ন নাম দিন।")
            return
        
        API_CREDENTIALS[key_name] = {"id": int(api_id_str), "hash": api_hash}
        save_data()
        context.user_data['awaiting_input'] = None
        
        total = len(API_CREDENTIALS)
        await update.message.reply_text(
            f"✅ *API কী যোগ!*\n\n"
            f"নাম: `{key_name}`\n"
            f"ID: `{api_id_str}`\n"
            f"HASH: `{api_hash[:8]}...`\n"
            f"মোট API: `{total}`টি\n\n"
            f"এখন অ্যাকাউন্ট যোগ করে OTP দিন 🚀\n"
            f"একাউনেন্ট ভিউতে গিয়ে API পরিবর্তন করতে পারো।",
            parse_mode='Markdown'
        )
    
    elif awaiting == 'add_blocked_user':
        if not text.isdigit(): await update.message.reply_text("❌ সংখ্যা!"); return
        uid = int(text)
        if uid == OWNER_ID: await update.message.reply_text("❌ ওনারকে না!"); return
        if uid not in blocked_users: blocked_users.append(uid); save_data()
        await update.message.reply_text(f"🔒 `{uid}` ব্লক!", parse_mode='Markdown')
        context.user_data['awaiting_input'] = None
    
    elif awaiting == 'add_allowed_user':
        if not text.isdigit(): await update.message.reply_text("❌ সংখ্যা!"); return
        uid = int(text)
        if uid not in allowed_users: allowed_users.append(uid); save_data()
        await update.message.reply_text(f"✅ `{uid}` অনুমতি!", parse_mode='Markdown')
        context.user_data['awaiting_input'] = None
    
    elif awaiting == 'remove_blocked_user':
        if not text.isdigit(): await update.message.reply_text("❌ সংখ্যা!"); return
        uid = int(text)
        if uid in blocked_users: blocked_users.remove(uid); save_data()
        await update.message.reply_text(f"🔓 `{uid}` আনব্লক!", parse_mode='Markdown')
        context.user_data['awaiting_input'] = None
    
    elif awaiting == 'remove_allowed_user':
        if not text.isdigit(): await update.message.reply_text("❌ সংখ্যা!"); return
        uid = int(text)
        if uid == OWNER_ID: await update.message.reply_text("❌ ওনারকে না!"); return
        if uid in allowed_users: allowed_users.remove(uid); save_data()
        await update.message.reply_text(f"❌ `{uid}` সরানো!", parse_mode='Markdown')
        context.user_data['awaiting_input'] = None


# ============================================================
# রান একাউন্ট (কিপ অ্যালাইভ + মাল্টি API)
# ============================================================

async def run_account_keep_alive(session_name):
    """কিপ-অ্যালাইভ + ম্যাসেজ পাঠানো (মাল্টি API)"""
    if session_name not in accounts_data:
        return
    
    acc = accounts_data[session_name]
    phone = acc['phone']
    api_key = acc.get('api_key', DEFAULT_API)
    api_id, api_hash = get_api_creds(session_name)
    session_file = f"{SESSIONS_DIR}/{session_name}.session"
    
    if not os.path.exists(session_file):
        logger.warning(f"[{session_name}] Session নেই!")
        return
    
    retry_count = 0
    
    while retry_count < MAX_RETRIES:
        try:
            client = TelegramClient(session_file.replace('.session', ''), api_id, api_hash)
            await client.connect()
            
            if not await client.is_user_authorized():
                try: os.remove(session_file)
                except: pass
                account_health[session_name] = {'status': 'session_expired', 'last_check': datetime.now().isoformat()}
                save_data()
                await client.disconnect()
                return False
            
            me = await client.get_me()
            logger.info(f"✅ [{session_name}] {me.first_name} শুরু (API: {api_key})")
            
            account_health[session_name] = {'status': 'ok', 'user': me.first_name, 'last_check': datetime.now().isoformat()}
            save_data()
            
            # গ্রুপ লিস্ট
            groups = []
            try:
                dialogs = await client(GetDialogsRequest(offset_date=None, offset_id=0, offset_peer=InputPeerEmpty(), limit=200, hash=0))
                for dialog in dialogs.dialogs:
                    try:
                        entity = await client.get_entity(dialog.peer)
                        if hasattr(entity, 'title') and entity.title not in EXCLUDED_GROUPS:
                            groups.append(entity)
                    except: pass
            except Exception as e:
                logger.error(f"[{session_name}] গ্রুপ error: {e}")
                await client.disconnect()
                return False
            
            if session_name not in account_stats:
                account_stats[session_name] = {'sent': 0, 'last_sent': 'N/A', 'groups': 0}
            account_stats[session_name]['groups'] = len(groups)
            save_data()
            
            if not groups:
                logger.warning(f"[{session_name}] কোনো গ্রুপ নেই!")
                await client.disconnect()
                return False
            
            retry_count = 0
            ping_counter = 0
            
            while True:
                for i, g in enumerate(groups):
                    try:
                        title = g.title if hasattr(g, 'title') else str(g.id)
                        await client.send_message(g, MESSAGE)
                        
                        if session_name not in account_stats:
                            account_stats[session_name] = {'sent': 0, 'last_sent': 'N/A', 'groups': len(groups)}
                        account_stats[session_name]['sent'] = account_stats[session_name].get('sent', 0) + 1
                        account_stats[session_name]['last_sent'] = datetime.now().strftime('%Y-%m-%d %H:%M')
                        save_data()
                        account_health[session_name]['last_check'] = datetime.now().isoformat()
                        
                        logger.info(f"[{session_name}] ✅ [{i+1}/{len(groups)}] {title}")
                        
                        ping_counter += 1
                        if ping_counter % 10 == 0:
                            try:
                                await client.get_dialogs(limit=1)
                                logger.info(f"[{session_name}] 📡 পিং OK")
                            except:
                                pass
                        
                    except FloodWaitError as e:
                        logger.warning(f"[{session_name}] ⏳ Flood {e.seconds}s")
                        await asyncio.sleep(e.seconds)
                        
                    except (AuthKeyUnregisteredError, UserDeactivatedError) as e:
                        logger.warning(f"[{session_name}] ❌ লগআউট: {e}")
                        account_health[session_name] = {'status': 'logged_out', 'last_check': datetime.now().isoformat()}
                        save_data()
                        await client.disconnect()
                        return False
                        
                    except Exception as e:
                        if 'connect' in str(e).lower() or 'disconnect' in str(e).lower():
                            retry_count += 1
                            if retry_count >= MAX_RETRIES:
                                await client.disconnect()
                                return False
                            await client.disconnect()
                            await asyncio.sleep(5)
                            break
                    
                    await asyncio.sleep(random.randint(MIN_INTERVAL, MAX_INTERVAL))
                else:
                    try:
                        await client.get_dialogs(limit=1)
                        logger.info(f"[{session_name}] 📡 সাইকেল পিং OK")
                    except:
                        pass
                    
                    await asyncio.sleep(CYCLE_WAIT)
                    retry_count = 0
                    continue
                break
            
        except asyncio.CancelledError:
            logger.info(f"[{session_name}] ⛔ বন্ধ")
            return
        except Exception as e:
            retry_count += 1
            if retry_count >= MAX_RETRIES:
                account_health[session_name] = {'status': 'error', 'error': str(e), 'last_check': datetime.now().isoformat()}
                save_data()
                return False
            await asyncio.sleep(10)


# ============================================================
# মেইন
# ============================================================

async def main():
    print("""
╔═══════════════════════════════════════════════════╗
║   📱 v10 - মাল্টি API ফাইনাল ভার্সন              ║
║   একসাথে ৩+ API ID/HASH · অটো কিপ-অ্যালাইভ      ║
║   বট থেকেই API ম্যানেজ করুন                      ║
╚═══════════════════════════════════════════════════╝
    """)
    
    print(f"\n🔐 মোট API: {len(API_CREDENTIALS)}টি")
    for k, v in API_CREDENTIALS.items():
        print(f"   {k} → ID: {v['id']}, HASH: {v['hash'][:8]}...")
    print(f"🛡️ লগআউট প্রোটেকশন: ✅ চালু\n")
    
    os.makedirs(SESSIONS_DIR, exist_ok=True)
    
    for f in os.listdir('.'):
        if f.endswith('.lock'):
            try: os.remove(f)
            except: pass
    
    load_data()
    logger.info(f"📊 {len(accounts_data)}টি অ্যাকাউন্ট লোড, {len(API_CREDENTIALS)}টি API কী")
    print(f"✅ {len(accounts_data)}টি অ্যাকাউন্ট, {len(API_CREDENTIALS)}টি API কী")
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    
    await app.initialize()
    await app.start()
    await app.updater.start_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
    
    # ব্যাকগ্রাউন্ড হেলথ চেক শুরু
    asyncio.create_task(health_check_all())
    
    port = os.environ.get("PORT", "10000")
    print(f"\n✅ চালু! Flask: {port}")
    print(f"✅ /start দিন কন্ট্রোল বটে")
    print(f"✅ মাল্টি API সাপোর্ট চালু! 🔐")
    
    try:
        while True:
            await asyncio.sleep(3600)
            running = sum(1 for sn in running_tasks if sn in running_tasks and not running_tasks[sn].done())
            healthy = sum(1 for sn in accounts_data if account_health.get(sn, {}).get('status') == 'ok')
            logger.info(f"জীবিত... {running}/{len(accounts_data)} চলছে · {healthy} হেলদি · API: {len(API_CREDENTIALS)}টি")
    except asyncio.CancelledError:
        pass
    finally:
        await app.updater.stop()
        await app.stop()
        await app.shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("⛔ বন্ধ")
    except Exception as e:
        logger.error(f"❌ fatal: {e}", exc_info=True)
        sys.exit(1)
