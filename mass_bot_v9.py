#!/usr/bin/env python3
# mass_bot_v9.py - পার্মানেন্ট সেশন (কোন লগআউট নাই)

import os
import sys
import json
import asyncio
import random
import logging
import threading
from datetime import datetime
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import FloodWaitError, SessionPasswordNeededError, AuthKeyUnregisteredError, UserDeactivatedError, PhoneCodeInvalidError, PhoneCodeExpiredError
from telethon.tl.functions.messages import GetDialogsRequest
from telethon.tl.types import InputPeerEmpty
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from flask import Flask

# ====== Flask HTTP Keep-Alive ======
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
# ===================================

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', handlers=[logging.StreamHandler(sys.stdout)])
logger = logging.getLogger(__name__)

# ====== আপনার BOT TOKEN এবং OWNER ID বসান ======
BOT_TOKEN = "8875386448:AAH2RMJixaVOyLPZkYJayh3WcGVrc5octnA"
OWNER_ID = 8001816524
# ================================================

# ============================================================
# 🔥 আপনার 3 টি API ID / HASH এখানে সেট করুন 🔥
# ============================================================
PRESET_API_CREDENTIALS = [
    {"api_id": 34124317, "api_hash": "b6a4101c735dda0625454c22b579d702"},
    {"api_id": 37362415, "api_hash": "88f99afa3b9a81adce62267b701e7b9f"},
    {"api_id": 36952100, "api_hash": "21c793e15e6ceef225eeb83e5727d446"},
]
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
api_cred_index = {}
SESSION_STRINGS = {}

MESSAGE = "𝟭𝟬 𝗠𝗜𝗡 𝗩𝗖 ₹𝟰𝟵 𝗕𝗔𝗕𝗬😘"
MIN_INTERVAL = 1
MAX_INTERVAL = 2
CYCLE_WAIT = 15
MAX_ACCOUNTS = 999999
EXCLUDED_GROUPS = ["Admin Group", "Private Chat"]
SESSION_REFRESH_INTERVAL = 300
AUTO_RECONNECT = True
MAX_RETRIES = 5
_next_api_index = 0


def get_next_api_credentials():
    global _next_api_index
    cred = PRESET_API_CREDENTIALS[_next_api_index % len(PRESET_API_CREDENTIALS)]
    _next_api_index += 1
    return cred


def load_data():
    global accounts_data, blocked_users, allowed_users, MESSAGE, MIN_INTERVAL, MAX_INTERVAL, CYCLE_WAIT, account_stats, account_health, api_cred_index, SESSION_STRINGS
    default_data = {
        'accounts': {}, 'blocked_users': [], 'allowed_users': [], 'account_stats': {}, 'account_health': {}, 'api_cred_index': {},
        'session_strings': {},
        'settings': {'message': MESSAGE, 'min_interval': MIN_INTERVAL, 'max_interval': MAX_INTERVAL, 'cycle_wait': CYCLE_WAIT}
    }
    if not os.path.exists(DATA_FILE):
        save_data(default_data)
        return default_data
    try:
        with open(DATA_FILE, 'r') as f:
            data = json.load(f)
        if not isinstance(data, dict):
            data = default_data
        accounts_data = data.get('accounts', {}) or {}
        blocked_users = data.get('blocked_users', []) or []
        allowed_users = data.get('allowed_users', []) or []
        account_stats = data.get('account_stats', {}) or {}
        account_health = data.get('account_health', {}) or {}
        api_cred_index = data.get('api_cred_index', {}) or {}
        SESSION_STRINGS = data.get('session_strings', {}) or {}
        settings = data.get('settings', {}) or {}
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
            'accounts': accounts_data, 'blocked_users': blocked_users, 'allowed_users': allowed_users,
            'account_stats': account_stats, 'account_health': account_health, 'api_cred_index': api_cred_index,
            'session_strings': SESSION_STRINGS,
            'settings': {'message': MESSAGE, 'min_interval': MIN_INTERVAL, 'max_interval': MAX_INTERVAL, 'cycle_wait': CYCLE_WAIT}
        }
    try:
        with open(DATA_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    except:
        pass


async def is_user_allowed(user_id):
    if user_id == OWNER_ID:
        return True
    if user_id in blocked_users:
        return False
    if not allowed_users:
        return True
    return user_id in allowed_users


async def check_and_fix_account(session_name):
    if session_name not in accounts_data:
        return False
    acc = accounts_data[session_name]
    for attempt in range(MAX_RETRIES):
        try:
            session_file = f"{SESSIONS_DIR}/{session_name}.session"
            if os.path.exists(session_file):
                client = TelegramClient(session_file.replace('.session', ''), acc['api_id'], acc['api_hash'])
            elif session_name in SESSION_STRINGS and SESSION_STRINGS[session_name]:
                client = TelegramClient(StringSession(SESSION_STRINGS[session_name]), acc['api_id'], acc['api_hash'])
            else:
                return False
            await client.connect()
            if not await client.is_user_authorized():
                await client.disconnect()
                return False
            try:
                me = await client.get_me()
                if me:
                    try:
                        SESSION_STRINGS[session_name] = client.session.save()
                        save_data()
                        if not os.path.exists(session_file):
                            client.session.save()
                    except:
                        pass
                    account_health[session_name] = {'status': 'ok', 'user': me.first_name, 'last_check': datetime.now().isoformat()}
                    save_data()
                    await client.disconnect()
                    return True
            except (AuthKeyUnregisteredError, UserDeactivatedError):
                await client.disconnect()
                return False
            await client.disconnect()
        except Exception as e:
            logger.error(f"[{session_name}] check error (attempt {attempt+1}): {e}")
            await asyncio.sleep(5)
    return False


async def health_check_all_accounts():
    while True:
        try:
            for sn in list(accounts_data.keys()):
                if sn not in running_tasks or running_tasks[sn].done():
                    await check_and_fix_account(sn)
                await asyncio.sleep(2)
            await asyncio.sleep(SESSION_REFRESH_INTERVAL)
        except Exception as e:
            logger.error(f"Health check error: {e}")
            await asyncio.sleep(60)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not await is_user_allowed(user_id):
        await update.message.reply_text("❌ আপনি অনুমোদিত নন!")
        return
    if user_id != OWNER_ID:
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("📊 স্ট্যাটাস", callback_data='user_status')]])
        await update.message.reply_text(f"👋 স্বাগতম {update.effective_user.first_name}!", reply_markup=kb)
        return
    running = sum(1 for sn in running_tasks if sn in running_tasks and not running_tasks[sn].done())
    total = len(accounts_data)
    healthy = sum(1 for sn in accounts_data if account_health.get(sn, {}).get('status') == 'ok')
    session_files = [f for f in os.listdir(SESSIONS_DIR) if f.endswith('.session')] if os.path.exists(SESSIONS_DIR) else []
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 অ্যাকাউন্ট", callback_data='accounts')],
        [InlineKeyboardButton("⚙️ সেটিংস", callback_data='settings')],
        [InlineKeyboardButton("🔒 ইউজার", callback_data='user_manage')],
        [InlineKeyboardButton("▶️ সব চালু", callback_data='start_all')],
        [InlineKeyboardButton("⏹️ সব বন্ধ", callback_data='stop_all')],
        [InlineKeyboardButton("🩺 হেলথ চেক", callback_data='health_check')],
        [InlineKeyboardButton(f"📊 স্ট্যাটাস ({running}/{total})", callback_data='status')]
    ])
    await update.message.reply_text(
        f"🤖 *ম্যাসেজিং বট v9*\n\n"
        f"🔥 আনলিমিটেড অ্যাকাউন্ট\n"
        f"🔑 {len(PRESET_API_CREDENTIALS)}টি প্রি-সেট API\n"
        f"⚡ {MIN_INTERVAL}-{MAX_INTERVAL}s · সাইকেল {CYCLE_WAIT}s\n"
        f"📊 চলছে: {running}/{total} | হেলদি: {healthy}\n"
        f"💾 .session ফাইল: {len(session_files)}টি\n"
        f"🔑 StringSession: {len(SESSION_STRINGS)}টি",
        parse_mode='Markdown', reply_markup=kb
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if not await is_user_allowed(user_id):
        return
    data = query.data
    if data == 'user_status':
        running = sum(1 for sn in running_tasks if sn in running_tasks and not running_tasks[sn].done())
        total = len(accounts_data)
        await query.edit_message_text(f"📊 বট সক্রিয় | চলছে: {running}/{total}")
        return
    if user_id != OWNER_ID:
        return
    if data == 'accounts':
        await show_accounts(query)
    elif data == 'add_account':
        context.user_data['awaiting_input'] = 'add_account'
        await query.edit_message_text(
            f"📱 *একাউন্ট যোগ (মোট: {len(accounts_data)}টি)*\n\n"
            f"🔑 প্রি-সেট API অটো ব্যবহার হবে\n\n"
            "ফরম্যাট:\n`নাম,ফোন`\n\n"
            "উদাহরণ:\n`acc1,+8801712345678`\n\n"
            "'বাতিল' বাতিল করতে।",
            parse_mode='Markdown'
        )
    elif data == 'add_bulk':
        context.user_data['awaiting_input'] = 'add_bulk'
        await query.edit_message_text(
            f"📱 *একসাথে যোগ*\n\n"
            "প্রতি লাইনে:\n`নাম,ফোন`\n\n"
            "```\nacc1,+8801712345678\nacc2,+8801712345679\n```\n\n"
            "শুধু নাম ও ফোন! API ID/HASH লাগবে না।\n'বাতিল' বাতিল।",
            parse_mode='Markdown'
        )
    elif data == 'view_api_creds':
        text = "🔑 *প্রি-সেট API*\n\n"
        for i, cred in enumerate(PRESET_API_CREDENTIALS, 1):
            count = sum(1 for v in api_cred_index.values() if v == i-1)
            text += f"• সেট {i}: `ID: {cred['api_id']}` | {count}টি একাউন্ট\n"
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 ফিরে", callback_data='accounts')]])
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=kb)
    elif data.startswith('view_'):
        sn = data.replace('view_', '')
        context.user_data['last_viewed'] = sn
        await view_account(query, sn)
    elif data.startswith('delete_'):
        await delete_account(query, data.replace('delete_', ''))
    elif data.startswith('toggle_'):
        await toggle_account(query, data.replace('toggle_', ''))
    elif data == 'send_otp':
        sn = context.user_data.get('last_viewed', '')
        if sn and sn in accounts_data:
            await send_otp_process(query, sn)
        else:
            await query.edit_message_text("❌ একাউন্ট সিলেক্ট করুন!")
    elif data == 'renew_session':
        sn = context.user_data.get('last_viewed', '')
        if sn and sn in accounts_data:
            await renew_session_process(query, sn)
        else:
            await query.edit_message_text("❌ একাউন্ট সিলেক্ট করুন!")
    elif data.startswith('enter_otp_'):
        sn = data.replace('enter_otp_', '')
        context.user_data['awaiting_input'] = f'otp_code_{sn}'
        await query.edit_message_text(
            f"🔢 *OTP দিন*\n\nএকাউন্ট: `{sn}`\n\n"
            f"টেলিগ্রাম অ্যাপে যে **5 ডিজিটের কোড** এসেছে, সেটি লিখুন:\n\n"
            f"যেমন: `12345`\n\n"
            f"'বাতিল' লিখে বাতিল করুন।",
            parse_mode='Markdown'
        )
    elif data.startswith('enter_2fa_'):
        sn = data.replace('enter_2fa_', '')
        context.user_data['awaiting_input'] = f'2fa_code_{sn}'
        await query.edit_message_text(
            f"🔑 *2FA পাসওয়ার্ড দিন*\n\nএকাউন্ট: `{sn}`\n\n'বাতিল' বাতিল করুন।",
            parse_mode='Markdown'
        )
    elif data.startswith('cancel_otp_'):
        sn = data.replace('cancel_otp_', '')
        if sn in pending_otp:
            try:
                await pending_otp[sn]['client'].disconnect()
            except:
                pass
            del pending_otp[sn]
        await query.edit_message_text(f"❌ OTP বাতিল!\n\nএকাউন্ট: `{sn}`", parse_mode='Markdown')
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
        await query.edit_message_text(
            f"⚙️ *ইন্টারভাল*\n\nমিন {MIN_INTERVAL}s · ম্যাক্স {MAX_INTERVAL}s · সাইকেল {CYCLE_WAIT}s",
            parse_mode='Markdown', reply_markup=kb
        )
    elif data in ['edit_min', 'edit_max', 'edit_cycle']:
        context.user_data['awaiting_input'] = data
        labels = {'edit_min': 'মিনিমাম', 'edit_max': 'ম্যাক্সিমাম', 'edit_cycle': 'সাইকেল'}
        vals = {'edit_min': MIN_INTERVAL, 'edit_max': MAX_INTERVAL, 'edit_cycle': CYCLE_WAIT}
        await query.edit_message_text(
            f"✏️ *{labels[data]}*\nবর্তমান: `{vals[data]}`s\n\nনতুন মান লিখুন:",
            parse_mode='Markdown'
        )
    elif data == 'preset_speed':
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🚀 আল্ট্রা (১/২সে · ১০সে)", callback_data='speed_ultra')],
            [InlineKeyboardButton("⚡ সুপার (২/৪সে · ২০সে)", callback_data='speed_super')],
            [InlineKeyboardButton("🔥 ফাস্ট (৩/৫সে · ৩০সে)", callback_data='speed_fast')],
            [InlineKeyboardButton("⏩ নরমাল (৫/১০সে · ৬০সে)", callback_data='speed_normal')],
            [InlineKeyboardButton("🔙 ফিরে", callback_data='edit_interval')]
        ])
        await query.edit_message_text("⚡ *প্রিসেট স্পিড*", parse_mode='Markdown', reply_markup=kb)
    elif data == 'speed_ultra':
        set_speed(1, 2, 10)
        await query.answer("✅ আল্ট্রা!")
        await show_settings(query)
    elif data == 'speed_super':
        set_speed(2, 4, 20)
        await query.answer("✅ সুপার!")
        await show_settings(query)
    elif data == 'speed_fast':
        set_speed(3, 5, 30)
        await query.answer("✅ ফাস্ট!")
        await show_settings(query)
    elif data == 'speed_normal':
        set_speed(5, 10, 60)
        await query.answer("✅ নরমাল!")
        await show_settings(query)
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
    elif data in ['add_blocked_user', 'add_allowed_user', 'remove_blocked_user', 'remove_allowed_user']:
        labels = {
            'add_blocked_user': '🔒 ব্লক আইডি:',
            'add_allowed_user': '✅ অনুমতি আইডি:',
            'remove_blocked_user': '🔓 আনব্লক আইডি:',
            'remove_allowed_user': '❌ সরান আইডি:'
        }
        context.user_data['awaiting_input'] = data
        await query.edit_message_text(labels[data])
    elif data == 'toggle_mode':
        if allowed_users:
            allowed_users.clear()
            await query.answer("✅ সবাই পারবে!")
        else:
            if OWNER_ID not in allowed_users:
                allowed_users.append(OWNER_ID)
            await query.answer("✅ শুধু অনুমতিপ্রাপ্ত!")
        save_data()
        await show_user_management(query)
    elif data == 'back':
        running = sum(1 for sn in running_tasks if sn in running_tasks and not running_tasks[sn].done())
        total = len(accounts_data)
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("👥 অ্যাকাউন্ট", callback_data='accounts')],
            [InlineKeyboardButton("⚙️ সেটিংস", callback_data='settings')],
            [InlineKeyboardButton("🔒 ইউজার", callback_data='user_manage')],
            [InlineKeyboardButton("▶️ সব চালু", callback_data='start_all')],
            [InlineKeyboardButton("⏹️ সব বন্ধ", callback_data='stop_all')],
            [InlineKeyboardButton("🩺 হেলথ চেক", callback_data='health_check')],
            [InlineKeyboardButton(f"📊 স্ট্যাটাস ({running}/{total})", callback_data='status')]
        ])
        await query.edit_message_text(
            f"🤖 *ম্যাসেজিং বট v9* | {running}/{total} চলছে",
            parse_mode='Markdown', reply_markup=kb
        )


def set_speed(min_s, max_s, cycle_s):
    global MIN_INTERVAL, MAX_INTERVAL, CYCLE_WAIT
    MIN_INTERVAL = min_s
    MAX_INTERVAL = max_s
    CYCLE_WAIT = cycle_s
    save_data()


async def show_accounts(query):
    total = len(accounts_data)
    if not accounts_data:
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ একক যোগ", callback_data='add_account'),
             InlineKeyboardButton("📋 একসাথে", callback_data='add_bulk')],
            [InlineKeyboardButton("🔙 ফিরে", callback_data='back')]
        ])
        await query.edit_message_text(
            "📭 *কোন অ্যাকাউন্ট নেই*\n\n"
            "🔑 প্রি-সেট API অটো ব্যবহার হবে।\nশুধু নাম ও ফোন দিন!",
            parse_mode='Markdown', reply_markup=kb
        )
        return
    text = f"👥 *একাউন্ট (মোট: {total}টি)*\n🔑 {len(PRESET_API_CREDENTIALS)}টি প্রি-সেট API\n\n"
    for sn in list(accounts_data.keys())[:10]:
        ok = sn in running_tasks and not running_tasks[sn].done()
        hs = sn in SESSION_STRINGS and SESSION_STRINGS[sn]
        has_file = os.path.exists(f"{SESSIONS_DIR}/{sn}.session") if os.path.exists(SESSIONS_DIR) else False
        if ok:
            icon = '🟢'
        elif hs or has_file:
            icon = '🟡'
        else:
            icon = '🔴'
        sent = account_stats.get(sn, {}).get('sent', 0)
        cred_idx = api_cred_index.get(sn, 0)
        text += f"{icon} `{sn}` (পাঠিয়েছে: {sent}) [API{cred_idx+1}]\n"
    accounts_list = list(accounts_data.keys())
    kb = []
    for sn in accounts_list[:5]:
        kb.append([InlineKeyboardButton(f"👁️ {sn}", callback_data=f'view_{sn}')])
    kb.append([InlineKeyboardButton("➕ যোগ", callback_data='add_account'),
               InlineKeyboardButton("📋 বাল্ক", callback_data='add_bulk')])
    kb.append([InlineKeyboardButton("🔑 API সেট দেখুন", callback_data='view_api_creds')])
    kb.append([InlineKeyboardButton("🔙 ফিরে", callback_data='back')])
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb))


async def view_account(query, sn):
    if sn not in accounts_data:
        await query.edit_message_text("❌ নেই!")
        return
    acc = accounts_data[sn]
    ok = sn in running_tasks and not running_tasks[sn].done()
    hs = sn in SESSION_STRINGS and SESSION_STRINGS[sn]
    has_file = os.path.exists(f"{SESSIONS_DIR}/{sn}.session") if os.path.exists(SESSIONS_DIR) else False
    if ok:
        st = "✅ চালু"
    elif hs or has_file:
        st = "🟡 লগইন করা (বন্ধ)"
    else:
        st = "🔴 লগইন করেনি"
    cred_idx = api_cred_index.get(sn, 0)
    cred = PRESET_API_CREDENTIALS[cred_idx] if cred_idx < len(PRESET_API_CREDENTIALS) else PRESET_API_CREDENTIALS[0]
    stats = account_stats.get(sn, {})
    text = f"📱 *{sn}*\n"
    text += f"স্ট্যাটাস: {st}\n"
    text += f"ফোন: `{acc['phone']}`\n"
    text += f"🔑 API সেট: {cred_idx+1} (ID: `{cred['api_id']}`)\n"
    text += f"💾 .session ফাইল: {'✅ আছে' if has_file else '❌ নেই'}\n"
    text += f"🔑 StringSession: {'✅ আছে' if hs else '❌ নেই'}\n"
    text += f"পাঠিয়েছে: {stats.get('sent', 0)}টি\n"
    text += f"গ্রুপ: {stats.get('groups', 0)}টি\n"
    but = []
    if ok:
        but.append([InlineKeyboardButton("⏹️ বন্ধ", callback_data=f'toggle_{sn}')])
    elif hs or has_file:
        but.append([InlineKeyboardButton("▶️ চালু", callback_data=f'toggle_{sn}')])
    else:
        but.append([InlineKeyboardButton("📱 OTP পাঠান", callback_data='send_otp')])
    if (hs or has_file) and not ok:
        but.append([InlineKeyboardButton("🔄 Session রিনিউ", callback_data='renew_session')])
    but.append([InlineKeyboardButton("🗑️ ডিলিট", callback_data=f'delete_{sn}')])
    but.append([InlineKeyboardButton("🔙 ফিরে", callback_data='accounts')])
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(but))


async def send_otp_process(query, sn):
    if sn not in accounts_data:
        await query.edit_message_text("❌ নেই!")
        return
    acc = accounts_data[sn]
    phone = acc['phone']
    api_id = acc['api_id']
    api_hash = acc['api_hash']
    await query.edit_message_text(
        f"📱 *OTP পাঠানো হচ্ছে...*\n\n"
        f"ফোন: `{phone}`\n"
        f"অপেক্ষা করুন... ⏳",
        parse_mode='Markdown'
    )
    try:
        if sn in pending_otp:
            try:
                await pending_otp[sn]['client'].disconnect()
            except:
                pass
            del pending_otp[sn]
        os.makedirs(SESSIONS_DIR, exist_ok=True)
        session_path = f"{SESSIONS_DIR}/{sn}"
        client = TelegramClient(session_path, api_id, api_hash)
        logger.info(f"[{sn}] .session ফাইল ব্যবহার করা হচ্ছে: {session_path}.session")
        await client.connect()
        if await client.is_user_authorized():
            try:
                me = await client.get_me()
                logger.info(f"[{sn}] ইতিমধ্যে লগইন! {me.first_name}")
                try:
                    SESSION_STRINGS[sn] = client.session.save()
                    save_data()
                except:
                    pass
                account_health[sn] = {'status': 'ok', 'user': me.first_name, 'last_check': datetime.now().isoformat()}
                save_data()
                await client.disconnect()
                await query.edit_message_text(
                    f"✅ *ইতিমধ্যে লগইন!*\n\n"
                    f"একাউন্ট: `{sn}`\n"
                    f"ব্যবহারকারী: {me.first_name}\n"
                    f"💾 `.session` ফাইল: `{sn}.session` ✅\n\n"
                    f"এখন ▶️ চালু করুন।",
                    parse_mode='Markdown'
                )
                return
            except:
                pass
        logger.info(f"[{sn}] send_code_request পাঠানো হচ্ছে...")
        result = await client.send_code_request(phone)
        phone_code_hash = result.phone_code_hash
        logger.info(f"[{sn}] OTP পাঠানো হয়েছে! hash={phone_code_hash}")
        pending_otp[sn] = {
            'client': client,
            'phone': phone,
            'phone_code_hash': phone_code_hash,
            'api_id': api_id,
            'api_hash': api_hash,
            'session_path': session_path
        }
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔢 OTP দিন", callback_data=f'enter_otp_{sn}')],
            [InlineKeyboardButton("🔑 2FA (যদি থাকে)", callback_data=f'enter_2fa_{sn}')],
            [InlineKeyboardButton("❌ বাতিল", callback_data=f'cancel_otp_{sn}')]
        ])
        await query.edit_message_text(
            f"✅ *OTP পাঠানো হয়েছে!*\n\n"
            f"একাউন্ট: `{sn}`\n"
            f"ফোন: `{phone}`\n"
            f"🔑 API সেট: {api_cred_index.get(sn, 0)+1}\n\n"
            f"📩 টেলিগ্রাম অ্যাপে **5 ডিজিটের** কোড এসেছে\n"
            f"🔽 নিচের বাটনে ক্লিক করে কোড লিখুন:\n\n"
            f"💾 *এটি `.session` ফাইল ব্যবহার করবে*\n"
            f"⚠️ *এই session আর কখনো লগআউট হবে না!*",
            parse_mode='Markdown', reply_markup=kb
        )
    except FloodWaitError as e:
        await query.edit_message_text(
            f"⏳ *Flood Wait!*\n\nTelegram বলছে `{e.seconds}` সেকেন্ড অপেক্ষা করুন।\n\n{e.seconds//60} মিনিট পর আবার চেষ্টা করুন।",
            parse_mode='Markdown'
        )
    except Exception as e:
        error_msg = str(e)
        logger.error(f"[{sn}] OTP error: {error_msg}")
        await query.edit_message_text(
            f"❌ *OTP ব্যর্থ!*\n\nত্রুটি: `{error_msg[:200]}`\n\n৫ মিনিট পর আবার চেষ্টা করুন।",
            parse_mode='Markdown'
        )


async def renew_session_process(query, sn):
    if sn not in accounts_data:
        await query.edit_message_text("❌ নেই!")
        return
    await query.edit_message_text(f"🔄 *Session রিনিউ করা হচ্ছে...*\n\nএকাউন্ট: `{sn}`", parse_mode='Markdown')
    result = await check_and_fix_account(sn)
    if result:
        await query.edit_message_text(f"✅ *Session রিনিউ সফল!*\n\nএকাউন্ট: `{sn}`\nএখন ▶️ চালু করুন।", parse_mode='Markdown')
    else:
        await query.edit_message_text(f"❌ *Session রিনিউ ব্যর্থ!*\n\n`{sn}`\nআবার OTP দিন।", parse_mode='Markdown')


async def delete_account(query, sn):
    if sn in running_tasks and not running_tasks[sn].done():
        running_tasks[sn].cancel()
        del running_tasks[sn]
    for d in [accounts_data, account_stats, account_health, api_cred_index, SESSION_STRINGS]:
        if sn in d:
            del d[sn]
    save_data()
    sf = f"{SESSIONS_DIR}/{sn}.session"
    if os.path.exists(sf):
        os.remove(sf)
    if sn in pending_otp:
        try:
            await pending_otp[sn]['client'].disconnect()
        except:
            pass
        del pending_otp[sn]
    await query.answer("✅ ডিলিট!")
    await show_accounts(query)


async def toggle_account(query, sn):
    if sn not in accounts_data:
        await query.answer("❌ নেই!")
        return
    has_file = os.path.exists(f"{SESSIONS_DIR}/{sn}.session") if os.path.exists(SESSIONS_DIR) else False
    has_string_session = sn in SESSION_STRINGS and SESSION_STRINGS[sn]
    if not has_file and not has_string_session:
        await query.answer("❌ আগে OTP দিন! ভিউ > OTP পাঠান")
        return
    if sn in running_tasks and not running_tasks[sn].done():
        running_tasks[sn].cancel()
        del running_tasks[sn]
        await query.answer("⏹️ বন্ধ!")
    else:
        health_ok = await check_and_fix_account(sn)
        if not health_ok:
            await query.answer("❌ Session নষ্ট! আবার OTP দিন.")
            await view_account(query, sn)
            return
        running_tasks[sn] = asyncio.create_task(run_account_with_health(sn))
        await query.answer("▶️ চালু!")
    await asyncio.sleep(2)
    await show_accounts(query)


async def show_settings(query):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ ম্যাসেজ", callback_data='edit_message')],
        [InlineKeyboardButton("⏱️ ইন্টারভাল", callback_data='edit_interval')],
        [InlineKeyboardButton("🔙 ফিরে", callback_data='back')]
    ])
    await query.edit_message_text(
        f"⚙️ *সেটিংস*\n\n📝 ম্যাসেজ: `{MESSAGE}`\n⏱️ মিন: `{MIN_INTERVAL}`s · ম্যাক্স: `{MAX_INTERVAL}`s\n🔄 সাইকেল: `{CYCLE_WAIT}`s\n🔑 প্রি-সেট API: {len(PRESET_API_CREDENTIALS)}টি\n💾 Session টাইপ: `.session` ফাইল + StringSession",
        parse_mode='Markdown', reply_markup=kb
    )


async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    if not await is_user_allowed(user_id):
        return
    awaiting = context.user_data.get('awaiting_input')
    
    # OTP CODE INPUT
    if awaiting and awaiting.startswith('otp_code_') and user_id == OWNER_ID:
        sn = awaiting.replace('otp_code_', '')
        if text.lower() == 'বাতিল':
            if sn in pending_otp:
                try:
                    await pending_otp[sn]['client'].disconnect()
                except:
                    pass
                del pending_otp[sn]
            context.user_data['awaiting_input'] = None
            await update.message.reply_text("❌ OTP বাতিল!")
            return
        code = text.strip()
        if sn not in pending_otp:
            await update.message.reply_text("❌ OTP সেশন নেই! আবার OTP পাঠান দিয়ে শুরু করুন।")
            context.user_data['awaiting_input'] = None
            return
        login_data = pending_otp[sn]
        client = login_data['client']
        phone = login_data['phone']
        phone_code_hash = login_data['phone_code_hash']
        await update.message.reply_text("⏳ ভেরিফাই করা হচ্ছে... অপেক্ষা করুন...")
        try:
            await client.sign_in(phone=phone, code=code, phone_code_hash=phone_code_hash)
            me = await client.get_me()
            logger.info(f"✅ [{sn}] লগইন সফল! {me.first_name}")
            try:
                client.session.save()
                logger.info(f"✅ [{sn}] .session ফাইল সেভ হয়েছে!")
                SESSION_STRINGS[sn] = client.session.save()
                save_data()
                logger.info(f"✅ [{sn}] StringSession সেভ হয়েছে!")
            except Exception as e:
                logger.error(f"[{sn}] Session save error: {e}")
            await client.disconnect()
            account_health[sn] = {'status': 'ok', 'user': me.first_name, 'last_check': datetime.now().isoformat()}
            save_data()
            if sn in pending_otp:
                del pending_otp[sn]
            context.user_data['awaiting_input'] = None
            session_file_path = f"{SESSIONS_DIR}/{sn}.session"
            file_exists = os.path.exists(session_file_path)
            await update.message.reply_text(
                f"✅ *লগইন সফল!*\n\nএকাউন্ট: `{sn}`\nব্যবহারকারী: {me.first_name}\n💾 `.session` ফাইল: `{'✅' if file_exists else '❌'} {sn}.session`\n\nএখন 👁️ ভিউ → ▶️ চালু করুন 🚀\n⚠️ *এই session আর কখনো লগআউট হবে না!*",
                parse_mode='Markdown'
            )
        except SessionPasswordNeededError:
            context.user_data['awaiting_input'] = f'2fa_code_{sn}'
            await update.message.reply_text("🔑 *2FA পাসওয়ার্ড দিন:*", parse_mode='Markdown')
        except PhoneCodeInvalidError:
            await update.message.reply_text("❌ OTP ভুল! আবার চেষ্টা করুন। 'OTP দিন' এ ক্লিক করে নতুন কোড লিখুন।")
        except PhoneCodeExpiredError:
            await update.message.reply_text("❌ OTP মেয়াদ শেষ! আবার 'OTP পাঠান' দিয়ে নতুন কোড নিন।")
        except Exception as e:
            await update.message.reply_text(f"❌ ত্রুটি: {str(e)[:200]}")
            if sn in pending_otp:
                del pending_otp[sn]
            context.user_data['awaiting_input'] = None
        return
    
    # 2FA PASSWORD INPUT
    if awaiting and awaiting.startswith('2fa_code_') and user_id == OWNER_ID:
        sn = awaiting.replace('2fa_code_', '')
        if text.lower() == 'বাতিল':
            if sn in pending_otp:
                try:
                    await pending_otp[sn]['client'].disconnect()
                except:
                    pass
                del pending_otp[sn]
            context.user_data['awaiting_input'] = None
            await update.message.reply_text("❌ 2FA বাতিল!")
            return
        password = text.strip()
        if sn in pending_otp:
            client = pending_otp[sn]['client']
            await update.message.reply_text("⏳ ভেরিফাই করা হচ্ছে...")
            try:
                await client.sign_in(password=password)
                me = await client.get_me()
                try:
                    client.session.save()
                    SESSION_STRINGS[sn] = client.session.save()
                    save_data()
                except:
                    pass
                account_health[sn] = {'status': 'ok', 'user': me.first_name, 'last_check': datetime.now().isoformat()}
                save_data()
                if sn in pending_otp:
                    try:
                        await pending_otp[sn]['client'].disconnect()
                    except:
                        pass
                    del pending_otp[sn]
                context.user_data['awaiting_input'] = None
                await update.message.reply_text(f"✅ *2FA লগইন সফল!*\n\nএকাউন্ট: `{sn}`\nব্যবহারকারী: {me.first_name}\n\nএখন ▶️ চালু করুন 🚀", parse_mode='Markdown')
            except Exception as e:
                await update.message.reply_text(f"❌ 2FA ভুল: {e}\n\nআবার চেষ্টা করুন।")
            return
        else:
            await update.message.reply_text("❌ সেশন নেই!")
            context.user_data['awaiting_input'] = None
            return
    
    if user_id != OWNER_ID:
        return
    if not awaiting:
        return
    
    global MESSAGE, MIN_INTERVAL, MAX_INTERVAL, CYCLE_WAIT
    
    if awaiting == 'add_account':
        if text.lower() == 'বাতিল':
            context.user_data['awaiting_input'] = None
            await update.message.reply_text("✅ বাতিল")
            return
        parts = text.split(',')
        if len(parts) != 2:
            await update.message.reply_text("❌ ফরম্যাট: `নাম,ফোন`\nযেমন: `acc1,+8801712345678`", parse_mode='Markdown')
            return
        sn, phone = parts[0].strip(), parts[1].strip()
        if not phone.startswith('+'):
            await update.message.reply_text("❌ ফোন + দিয়ে শুরু হবে!")
            return
        if sn in accounts_data:
            await update.message.reply_text("❌ এই নামে আগে আছে!")
            return
        cred = get_next_api_credentials()
        actual_idx = (_next_api_index - 1) % len(PRESET_API_CREDENTIALS)
        accounts_data[sn] = {'phone': phone, 'api_id': cred['api_id'], 'api_hash': cred['api_hash']}
        api_cred_index[sn] = actual_idx
        os.makedirs(SESSIONS_DIR, exist_ok=True)
        save_data()
        context.user_data['awaiting_input'] = None
        await update.message.reply_text(
            f"✅ *যোগ! (মোট: {len(accounts_data)}টি)*\n\nনাম: `{sn}`\nফোন: `{phone}`\n🔑 API সেট: {actual_idx+1} (ID: `{cred['api_id']}`)\n\nএখন অ্যাকাউন্ট > ভিউ > OTP পাঠান এ ক্লিক করুন।\nতারপর ওই নম্বরে আসা OTP বটে লিখে দিন।\n💾 *`.session` ফাইল সেভ হবে - লগআউট হবে না!*\n/start করুন",
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
            if not line:
                continue
            parts = line.split(',')
            if len(parts) != 2:
                errors.append(f"❌ ফরম্যাট: {line}")
                continue
            sn, phone = parts[0].strip(), parts[1].strip()
            if not phone.startswith('+'):
                errors.append(f"❌ {sn}: ফোন ফরম্যাট")
                continue
            if sn in accounts_data:
                errors.append(f"❌ {sn}: আগে আছে")
                continue
            cred = get_next_api_credentials()
            actual_idx = (_next_api_index - 1) % len(PRESET_API_CREDENTIALS)
            accounts_data[sn] = {'phone': phone, 'api_id': cred['api_id'], 'api_hash': cred['api_hash']}
            api_cred_index[sn] = actual_idx
            added += 1
        os.makedirs(SESSIONS_DIR, exist_ok=True)
        save_data()
        context.user_data['awaiting_input'] = None
        reply = f"✅ {added} টি যোগ! (মোট: {len(accounts_data)}টি)\n\n"
        if errors:
            reply += "ত্রুটি:\n" + '\n'.join(errors) + '\n\n'
        reply += "/start করুন"
        await update.message.reply_text(reply)
    elif awaiting == 'edit_message':
        MESSAGE = text
        save_data()
        context.user_data['awaiting_input'] = None
        await update.message.reply_text(f"✅ *আপডেট!*\n\n`{MESSAGE}`", parse_mode='Markdown')
    elif awaiting in ['edit_min', 'edit_max', 'edit_cycle']:
        if not text.isdigit() or int(text) < 1:
            await update.message.reply_text("❌ ১ বা তার বেশি দিন!")
            return
        v = int(text)
        if awaiting == 'edit_min':
            if v >= MAX_INTERVAL:
                await update.message.reply_text(f"❌ মিন {MAX_INTERVAL} এর কম হবে!")
                return
            MIN_INTERVAL = v
        elif awaiting == 'edit_max':
            if v <= MIN_INTERVAL:
                await update.message.reply_text(f"❌ ম্যাক্স {MIN_INTERVAL} এর বেশি হবে!")
                return
            MAX_INTERVAL = v
        elif awaiting == 'edit_cycle':
            CYCLE_WAIT = v
        save_data()
        context.user_data['awaiting_input'] = None
        names = {'edit_min': 'মিন', 'edit_max': 'ম্যাক্স', 'edit_cycle': 'সাইকেল'}
        await update.message.reply_text(f"✅ *{names[awaiting]}*\n`{v}`s", parse_mode='Markdown')
    elif awaiting == 'add_blocked_user':
        if not text.isdigit():
            await update.message.reply_text("❌ সংখ্যা দিন!")
            return
        uid = int(text)
        if uid == OWNER_ID:
            await update.message.reply_text("❌ ওনারকে না!")
            return
        if uid not in blocked_users:
            blocked_users.append(uid)
            save_data()
        await update.message.reply_text(f"🔒 `{uid}` ব্লক!", parse_mode='Markdown')
        context.user_data['awaiting_input'] = None
    elif awaiting == 'add_allowed_user':
        if not text.isdigit():
            await update.message.reply_text("❌ সংখ্যা দিন!")
            return
        uid = int(text)
        if uid not in allowed_users:
            allowed_users.append(uid)
            save_data()
        await update.message.reply_text(f"✅ `{uid}` অনুমতি!", parse_mode='Markdown')
        context.user_data['awaiting_input'] = None
    elif awaiting == 'remove_blocked_user':
        if not text.isdigit():
            await update.message.reply_text("❌ সংখ্যা দিন!")
            return
        uid = int(text)
        if uid in blocked_users:
            blocked_users.remove(uid)
            save_data()
        await update.message.reply_text(f"🔓 `{uid}` আনব্লক!", parse_mode='Markdown')
        context.user_data['awaiting_input'] = None
    elif awaiting == 'remove_allowed_user':
        if not text.isdigit():
            await update.message.reply_text("❌ সংখ্যা দিন!")
            return
        uid = int(text)
        if uid == OWNER_ID:
            await update.message.reply_text("❌ ওনারকে না!")
            return
        if uid in allowed_users:
            allowed_users.remove(uid)
            save_data()
        await update.message.reply_text(f"❌ `{uid}` সরানো!", parse_mode='Markdown')
        context.user_data['awaiting_input'] = None


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
        has_file = os.path.exists(f"{SESSIONS_DIR}/{sn}.session") if os.path.exists(SESSIONS_DIR) else False
        has_string_session = sn in SESSION_STRINGS and SESSION_STRINGS[sn]
        if not has_file and not has_string_session:
            errors.append(f"{sn}: লগইন করেনি")
            continue
        health_ok = await check_and_fix_account(sn)
        if not health_ok:
            errors.append(f"{sn}: session নষ্ট")
            continue
        if sn not in running_tasks or running_tasks[sn].done():
            running_tasks[sn] = asyncio.create_task(run_account_with_health(sn))
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
            del running_tasks[sn]
            c += 1
    await query.answer(f"⏹️ {c} বন্ধ!")
    await query.edit_message_text(f"⏹️ {c} টি বন্ধ!")


async def health_check_button(query):
    await query.edit_message_text("🩺 *হেলথ চেক চলছে...*", parse_mode='Markdown')
    ok_count = 0
    fail_count = 0
    for sn in list(accounts_data.keys()):
        if await check_and_fix_account(sn):
            ok_count += 1
        else:
            fail_count += 1
        await asyncio.sleep(1)
    running = sum(1 for sn in running_tasks if sn in running_tasks and not running_tasks[sn].done())
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 ফিরে", callback_data='back')]])
    await query.edit_message_text(
        f"🩺 *হেলথ চেক*\n\n✅ ভালো: {ok_count}\n❌ নষ্ট: {fail_count}\n▶️ চলছে: {running}",
        parse_mode='Markdown', reply_markup=kb
    )


async def show_status(query):
    text = "📊 *স্ট্যাটাস*\n\n"
    if not accounts_data:
        text += "❌ কোনো অ্যাকাউন্ট নেই"
    else:
        r = l = h = ts = 0
        api_counts = [0] * len(PRESET_API_CREDENTIALS)
        for sn in accounts_data:
            ok = sn in running_tasks and not running_tasks[sn].done()
            has_file = os.path.exists(f"{SESSIONS_DIR}/{sn}.session") if os.path.exists(SESSIONS_DIR) else False
            hs = sn in SESSION_STRINGS and SESSION_STRINGS[sn]
            health_ok = account_health.get(sn, {}).get('status') == 'ok'
            sent = account_stats.get(sn, {}).get('sent', 0)
            ts += sent
            ci = api_cred_index.get(sn, 0)
            if ci < len(api_counts):
                api_counts[ci] += 1
            if ok:
                text += f"🟢 `{sn}` ({sent}) 💾{'✅' if has_file else '❌'}\n"
                r += 1
                if hs:
                    l += 1
                if health_ok:
                    h += 1
            elif hs or has_file:
                text += f"🟡 `{sn}` ({sent}) 💾{'✅' if has_file else '❌'}\n"
                l += 1
                if health_ok:
                    h += 1
            else:
                text += f"🔴 `{sn}`\n"
        text += f"\nমোট: {len(accounts_data)}টি | চলছে: {r}টি | হেলদি: {h}টি"
        text += f"\nমোট পাঠিয়েছে: {ts}"
        text += "\n🔑 API বিতরণ:"
        for i, c in enumerate(api_counts):
            text += f"\n   সেট {i+1}: {c}টি"
    text += f"\n\n📝 `{MESSAGE}`\n⏱️ `{MIN_INTERVAL}`-`{MAX_INTERVAL}`s | 🔄 `{CYCLE_WAIT}`s"
    await query.edit_message_text(text, parse_mode='Markdown')


async def run_account_with_health(session_name):
    if session_name not in accounts_data:
        return
    acc = accounts_data[session_name]
    api_id = acc['api_id']
    api_hash = acc['api_hash']
    retry_count = 0
    while retry_count < MAX_RETRIES:
        try:
            session_path = f"{SESSIONS_DIR}/{session_name}"
            session_file = f"{session_path}.session"
            if os.path.exists(session_file):
                client = TelegramClient(session_path, api_id, api_hash)
                logger.info(f"[{session_name}] .session ফাইল ব্যবহার করা হচ্ছে")
            elif session_name in SESSION_STRINGS and SESSION_STRINGS[session_name]:
                client = TelegramClient(StringSession(SESSION_STRINGS[session_name]), api_id, api_hash)
                logger.info(f"[{session_name}] StringSession ব্যবহার করা হচ্ছে (ফলব্যাক)")
            else:
                logger.error(f"[{session_name}] কোনো session পাওয়া যায়নি!")
                return
            await client.connect()
            if not await client.is_user_authorized():
                if session_name in SESSION_STRINGS:
                    del SESSION_STRINGS[session_name]
                    save_data()
                try:
                    sf = f"{SESSIONS_DIR}/{session_name}.session"
                    if os.path.exists(sf):
                        os.remove(sf)
                except:
                    pass
                account_health[session_name] = {'status': 'session_expired', 'last_check': datetime.now().isoformat()}
                save_data()
                await client.disconnect()
                logger.warning(f"[{session_name}] Session expired!")
                return
            me = await client.get_me()
            logger.info(f"✅ [{session_name}] {me.first_name} শুরু")
            try:
                client.session.save()
                SESSION_STRINGS[session_name] = client.session.save()
                save_data()
                logger.info(f"[{session_name}] Session সেভ হয়েছে")
            except Exception as e:
                logger.error(f"[{session_name}] Session save error: {e}")
            account_health[session_name] = {'status': 'ok', 'user': me.first_name, 'last_check': datetime.now().isoformat()}
            save_data()
            groups = []
            try:
                dialogs = await client(GetDialogsRequest(
                    offset_date=None, offset_id=0,
                    offset_peer=InputPeerEmpty(), limit=200, hash=0
                ))
                for dialog in dialogs.dialogs:
                    try:
                        entity = await client.get_entity(dialog.peer)
                        if hasattr(entity, 'title') and entity.title not in EXCLUDED_GROUPS:
                            groups.append(entity)
                    except:
                        pass
            except:
                await client.disconnect()
                return
            if session_name not in account_stats:
                account_stats[session_name] = {'sent': 0, 'last_sent': 'N/A', 'groups': 0}
            account_stats[session_name]['groups'] = len(groups)
            save_data()
            if not groups:
                logger.warning(f"[{session_name}] কোনো গ্রুপ নেই!")
                await client.disconnect()
                return
            retry_count = 0
            reconnect_counter = 0
            RECONNECT_INTERVAL = 50
            while True:
                try:
                    for i, g in enumerate(groups):
                        try:
                            await client.send_message(g, MESSAGE)
                            account_stats[session_name]['sent'] = account_stats[session_name].get('sent', 0) + 1
                            account_stats[session_name]['last_sent'] = datetime.now().strftime('%Y-%m-%d %H:%M')
                            account_health[session_name]['last_check'] = datetime.now().isoformat()
                            save_data()
                        except FloodWaitError as e:
                            logger.warning(f"[{session_name}] Flood: {e.seconds}s")
                            await asyncio.sleep(e.seconds)
                        except (AuthKeyUnregisteredError, UserDeactivatedError):
                            account_health[session_name] = {'status': 'logged_out', 'last_check': datetime.now().isoformat()}
                            save_data()
                            logger.error(f"[{session_name}] লগআউট হয়ে গেছে!")
                            await client.disconnect()
                            return
                        except Exception as e:
                            if 'AUTH_KEY_UNREGISTERED' in str(e) or 'USER_DEACTIVATED' in str(e):
                                account_health[session_name] = {'status': 'logged_out', 'last_check': datetime.now().isoformat()}
                                save_data()
                                await client.disconnect()
                                return
                            if 'connect' in str(e).lower() or 'disconnect' in str(e).lower():
                                retry_count += 1
                                if retry_count >= MAX_RETRIES:
                                    await client.disconnect()
                                    return
                                await client.disconnect()
                                await asyncio.sleep(5)
                                break
                        await asyncio.sleep(random.randint(MIN_INTERVAL, MAX_INTERVAL))
                    else:
                        reconnect_counter += 1
                        if reconnect_counter >= RECONNECT_INTERVAL:
                            logger.info(f"[{session_name}] রিকানেক্ট করছি (session ফ্রেশ রাখতে)...")
                            await client.disconnect()
                            await asyncio.sleep(3)
                            session_path = f"{SESSIONS_DIR}/{session_name}"
                            client = TelegramClient(session_path, api_id, api_hash)
                            await client.connect()
                            if not await client.is_user_authorized():
                                account_health[session_name] = {'status': 'logged_out', 'last_check': datetime.now().isoformat()}
                                save_data()
                                await client.disconnect()
                                return
                            try:
                                client.session.save()
                                SESSION_STRINGS[session_name] = client.session.save()
                                save_data()
                            except:
                                pass
                            reconnect_counter = 0
                            logger.info(f"[{session_name}] রিকানেক্ট সফল!")
                        await asyncio.sleep(CYCLE_WAIT)
                        continue
                    break
                except asyncio.CancelledError:
                    logger.info(f"[{session_name}] বন্ধ করা হয়েছে")
                    try:
                        await client.disconnect()
                    except:
                        pass
                    return
                except Exception as e:
                    logger.error(f"[{session_name}] লুপ error: {e}")
                    retry_count += 1
                    if retry_count >= MAX_RETRIES:
                        try:
                            await client.disconnect()
                        except:
                            pass
                        return
                    await asyncio.sleep(10)
                    break
        except asyncio.CancelledError:
            return
        except Exception as e:
            retry_count += 1
            logger.error(f"[{session_name}] fatal error (attempt {retry_count}): {e}")
            if retry_count >= MAX_RETRIES:
                return
            await asyncio.sleep(10)


async def main():
    print("""
╔══════════════════════════════════════════════════════════╗
║   📱 ম্যাসেজিং বট v9 - পার্মানেন্ট সেশন (কোন লগআউট নাই) ║
║   💾 .session ফাইল + StringSession ডুয়েল ব্যাকআপ       ║
║   🔄 অটো রিকানেক্ট (৫০ সাইকেল পরপর)                    ║
╚══════════════════════════════════════════════════════════╝
    """)
    logger.info("🚀 শুরু হচ্ছে...")
    os.makedirs(SESSIONS_DIR, exist_ok=True)
    for f in os.listdir('.'):
        if f.endswith('.lock'):
            try:
                os.remove(f)
            except:
                pass
    load_data()
    session_files = [f for f in os.listdir(SESSIONS_DIR) if f.endswith('.session')] if os.path.exists(SESSIONS_DIR) else []
    logger.info(f"📊 {len(accounts_data)}টি অ্যাকাউন্ট লোড")
    logger.info(f"🔑 {len(SESSION_STRINGS)}টি StringSession পাওয়া গেছে")
    logger.info(f"💾 {len(session_files)}টি .session ফাইল পাওয়া গেছে ({SESSIONS_DIR}/)")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    await app.initialize()
    await app.start()
    await app.updater.start_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
    asyncio.create_task(health_check_all_accounts())
    print(f"\n✅ বট চালু! /start দিন কন্ট্রোল বটে")
    try:
        while True:
            await asyncio.sleep(3600)
            running = sum(1 for sn in running_tasks if sn in running_tasks and not running_tasks[sn].done())
            session_files = [f for f in os.listdir(SESSIONS_DIR) if f.endswith('.session')] if os.path.exists(SESSIONS_DIR) else []
            logger.info(f"জীবিত... চলছে: {running}/{len(accounts_data)} | .session ফাইল: {len(session_files)}টি")
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
