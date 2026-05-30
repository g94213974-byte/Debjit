#!/usr/bin/env python3
# mass_bot_v2.py - FINAL (Phone + OTP Login System)

import os
import sys
import json
import asyncio
import random
import logging
import threading
from datetime import datetime
from telethon import TelegramClient
from telethon.errors import FloodWaitError, SessionPasswordNeededError
from telethon.tl.functions.messages import GetDialogsRequest
from telethon.tl.types import InputPeerEmpty
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# ====== Flask HTTP সার্ভার (Render port scan fix) ======
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

# ====== লগিং ======
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# ====== আপনার বট টোকেন (এই বট কন্ট্রোল প্যানেল হিসেবে কাজ করবে) ======
BOT_TOKEN = "8875386448:AAH2RMJixaVOyLPZkYJayh3WcGVrc5octnA"
OWNER_ID = 8001816524

# ====== ডাটা ফাইল ======
DATA_FILE = "bot_data.json"
SESSIONS_DIR = "sessions"

# ====== গ্লোবাল ভেরিয়েবল ======
running_tasks = {}
accounts_data = {}
blocked_users = []
allowed_users = []
pending_logins = {}  # OTP লগইন পেন্ডিং রাখার জন্য
bot_app = None

# ====== ডিফল্ট সেটিংস ======
MESSAGE = "𝟭𝟬 𝗠𝗜𝗡 𝗩𝗖 ₹𝟰𝟵 𝗕𝗔𝗕𝗬😘"
MIN_INTERVAL = 3
MAX_INTERVAL = 7
CYCLE_WAIT = 60
EXCLUDED_GROUPS = ["Admin Group", "Private Chat"]


# ============================================================
# ডাটা সেভ/লোড
# ============================================================

def load_data():
    global accounts_data, blocked_users, allowed_users, MESSAGE, MIN_INTERVAL, MAX_INTERVAL, CYCLE_WAIT
    
    default_data = {
        'accounts': {},
        'blocked_users': [],
        'allowed_users': [],
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
        
        if not isinstance(data, dict):
            data = default_data
        
        accounts_data = data.get('accounts', {})
        if not isinstance(accounts_data, dict): accounts_data = {}
        
        blocked_users = data.get('blocked_users', [])
        if not isinstance(blocked_users, list): blocked_users = []
        
        allowed_users = data.get('allowed_users', [])
        if not isinstance(allowed_users, list): allowed_users = []
        
        settings = data.get('settings', {})
        if not isinstance(settings, dict): settings = {}
        
        MESSAGE = settings.get('message', MESSAGE)
        MIN_INTERVAL = settings.get('min_interval', MIN_INTERVAL)
        MAX_INTERVAL = settings.get('max_interval', MAX_INTERVAL)
        CYCLE_WAIT = settings.get('cycle_wait', CYCLE_WAIT)
        
        return data
    except Exception as e:
        logger.warning(f"Data load error: {e}")
        save_data(default_data)
        return default_data


def save_data(data=None):
    if data is None:
        data = {
            'accounts': accounts_data,
            'blocked_users': blocked_users,
            'allowed_users': allowed_users,
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
    except Exception as e:
        logger.error(f"Save error: {e}")


# ============================================================
# ইউজার চেক
# ============================================================

async def is_user_allowed(user_id):
    if user_id == OWNER_ID: return True
    if user_id in blocked_users: return False
    if not allowed_users: return True
    return user_id in allowed_users


# ============================================================
# OTP লগইন ফাংশন
# ============================================================

async def request_otp(session_name, phone, api_id, api_hash):
    """ফোন নম্বরে OTP রিকোয়েস্ট পাঠায়"""
    try:
        client = TelegramClient(f"{SESSIONS_DIR}/{session_name}", api_id, api_hash)
        await client.connect()
        
        if await client.is_user_authorized():
            return {"success": True, "message": "ইতিমধ্যে লগইন করা আছে!", "client": client}
        
        send_code_result = await client.send_code_request(phone)
        
        # pending_logins এ সেভ করি
        pending_logins[session_name] = {
            'client': client,
            'phone': phone,
            'phone_code_hash': send_code_result.phone_code_hash
        }
        
        return {"success": True, "message": f"OTP পাঠানো হয়েছে {phone} এ!", "client": client}
    
    except Exception as e:
        return {"success": False, "message": f"OTP রিকোয়েস্ট ব্যর্থ: {e}"}


async def verify_otp(session_name, code):
    """OTP ভেরিফাই করে"""
    if session_name not in pending_logins:
        return {"success": False, "message": "কোনো পেন্ডিং লগইন নেই!"}
    
    login_data = pending_logins[session_name]
    client = login_data['client']
    phone = login_data['phone']
    phone_code_hash = login_data['phone_code_hash']
    
    try:
        user = await client.sign_in(
            phone=phone,
            code=code,
            phone_code_hash=phone_code_hash
        )
        
        # পেন্ডিং থেকে সরাই
        del pending_logins[session_name]
        
        return {"success": True, "message": "✅ লগইন সফল!", "user": user}
    
    except SessionPasswordNeededError:
        # 2FA আছে
        return {"success": True, "need_2fa": True, "message": "2FA পাসওয়ার্ড প্রয়োজন!"}
    
    except Exception as e:
        return {"success": False, "message": f"OTP ভেরিফিকেশন ব্যর্থ: {e}"}


async def verify_2fa(session_name, password):
    """2FA পাসওয়ার্ড ভেরিফাই করে"""
    if session_name not in pending_logins:
        return {"success": False, "message": "কোনো পেন্ডিং লগইন নেই!"}
    
    client = pending_logins[session_name]['client']
    
    try:
        user = await client.sign_in(password=password)
        del pending_logins[session_name]
        return {"success": True, "message": "✅ 2FA লগইন সফল!", "user": user}
    except Exception as e:
        return {"success": False, "message": f"2FA ভেরিফিকেশন ব্যর্থ: {e}"}


# ============================================================
# বট হ্যান্ডলার
# ============================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    if not await is_user_allowed(user_id):
        await update.message.reply_text("❌ আপনি এই বট ব্যবহারের জন্য অনুমোদিত নন!")
        return
    
    if user_id != OWNER_ID:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📊 স্ট্যাটাস দেখুন", callback_data='user_status')]
        ])
        await update.message.reply_text(f"👋 স্বাগতম {user.first_name}!", reply_markup=keyboard)
        return
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 অ্যাকাউন্ট ম্যানেজ", callback_data='accounts')],
        [InlineKeyboardButton("⚙️ সেটিংস", callback_data='settings')],
        [InlineKeyboardButton("🔒 ইউজার ম্যানেজমেন্ট", callback_data='user_manage')],
        [InlineKeyboardButton("▶️ সব চালু করুন", callback_data='start_all')],
        [InlineKeyboardButton("⏹️ সব বন্ধ করুন", callback_data='stop_all')],
        [InlineKeyboardButton("📊 স্ট্যাটাস", callback_data='status')]
    ])
    
    await update.message.reply_text(
        "🤖 *ম্যাসেজিং বট কন্ট্রোল প্যানেল (OTP লগইন)*\n\n"
        "আপনি কি করতে চান?",
        parse_mode='Markdown', reply_markup=keyboard
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    if not await is_user_allowed(user_id): return
    
    data = query.data
    
    if data == 'user_status':
        await query.edit_message_text("📊 বট সক্রিয় আছে। বিস্তারিত জানতে ওনারকে যোগাযোগ করুন।")
        return
    
    if user_id != OWNER_ID: return
    
    if data == 'accounts':
        await show_accounts(query)
    elif data == 'add_account':
        context.user_data['awaiting_input'] = 'add_account'
        await query.edit_message_text(
            "📱 *ফোন নম্বর দিয়ে অ্যাকাউন্ট যোগ করুন*\n\n"
            "ফরম্যাট: `নাম,ফোন_নম্বর,API_ID,API_HASH`\n\n"
            "উদাহরণ: `acc1,+8801712345678,123456,abc123def456`\n\n"
            "⚠️ ফোন নম্বর + এবং কান্ট্রি কোড সহ দিন\n"
            "⚠️ API_ID এবং API_HASH my.telegram.org থেকে নিন\n\n"
            "'বাতিল' লিখুন বাতিল করতে।",
            parse_mode='Markdown'
        )
    elif data.startswith('view_'):
        await view_account(query, data.replace('view_', ''))
    elif data.startswith('delete_'):
        await delete_account(query, data.replace('delete_', ''))
    elif data.startswith('toggle_'):
        await toggle_account(query, data.replace('toggle_', ''))
    elif data.startswith('login_'):
        await start_otp_login(query, data.replace('login_', ''))
    elif data == 'settings':
        await show_settings(query)
    elif data == 'edit_message':
        context.user_data['awaiting_input'] = 'edit_message'
        await query.edit_message_text(f"✏️ নতুন ম্যাসেজ লিখুন:\nবর্তমান: `{MESSAGE}`", parse_mode='Markdown')
    elif data == 'edit_interval':
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"📉 মিন ({MIN_INTERVAL}s)", callback_data='set_min'),
             InlineKeyboardButton(f"📈 ম্যাক্স ({MAX_INTERVAL}s)", callback_data='set_max')],
            [InlineKeyboardButton(f"🔄 সাইকেল ({CYCLE_WAIT}s)", callback_data='set_cycle')],
            [InlineKeyboardButton("🔙 ফিরে যান", callback_data='settings')]
        ])
        await query.edit_message_text("⚙️ *ইন্টারভাল সেটিংস*", parse_mode='Markdown', reply_markup=kb)
    elif data in ['set_min', 'set_max', 'set_cycle']:
        context.user_data['awaiting_input'] = data
        labels = {'set_min': 'মিনিমাম', 'set_max': 'ম্যাক্সিমাম', 'set_cycle': 'সাইকেল ওয়েট'}
        vals = {'set_min': MIN_INTERVAL, 'set_max': MAX_INTERVAL, 'set_cycle': CYCLE_WAIT}
        await query.edit_message_text(f"✏️ *{labels[data]}*\nবর্তমান: `{vals[data]}`s\n\nনতুন মান (সেকেন্ড) লিখুন:", parse_mode='Markdown')
    elif data == 'start_all':
        await start_all_accounts(query)
    elif data == 'stop_all':
        await stop_all_accounts(query)
    elif data == 'status':
        await show_status(query)
    elif data == 'user_manage':
        await show_user_management(query)
    elif data in ['add_blocked_user', 'add_allowed_user', 'remove_blocked_user', 'remove_allowed_user']:
        labels = {
            'add_blocked_user': '🔒 ব্লক করতে ইউজার আইডি দিন:',
            'add_allowed_user': '✅ অনুমতি দিতে ইউজার আইডি দিন:',
            'remove_blocked_user': '🔓 আনব্লক করতে ইউজার আইডি দিন:',
            'remove_allowed_user': '❌ অনুমতি সরাতে ইউজার আইডি দিন:'
        }
        context.user_data['awaiting_input'] = data
        await query.edit_message_text(labels[data])
    elif data == 'toggle_mode':
        if allowed_users:
            allowed_users.clear()
            await query.answer("✅ এখন সবাই ব্যবহার করতে পারবে!")
        else:
            if OWNER_ID not in allowed_users: allowed_users.append(OWNER_ID)
            await query.answer("✅ শুধু অনুমতিপ্রাপ্ত ইউজাররাই ব্যবহার করতে পারবে!")
        save_data()
        await show_user_management(query)
    elif data == 'back':
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("👥 অ্যাকাউন্ট", callback_data='accounts')],
            [InlineKeyboardButton("⚙️ সেটিংস", callback_data='settings')],
            [InlineKeyboardButton("🔒 ইউজার", callback_data='user_manage')],
            [InlineKeyboardButton("▶️ সব চালু", callback_data='start_all')],
            [InlineKeyboardButton("⏹️ সব বন্ধ", callback_data='stop_all')],
            [InlineKeyboardButton("📊 স্ট্যাটাস", callback_data='status')]
        ])
        await query.edit_message_text("🤖 *ম্যাসেজিং বট*\n24/7 চলছে! 🚀", parse_mode='Markdown', reply_markup=kb)


async def show_accounts(query):
    if not accounts_data:
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ অ্যাকাউন্ট যোগ করুন", callback_data='add_account')],
            [InlineKeyboardButton("🔙 ফিরে যান", callback_data='back')]
        ])
        await query.edit_message_text("📭 *কোন অ্যাকাউন্ট নেই!*\n\nনিচে 'অ্যাকাউন্ট যোগ করুন' বাটনে ক্লিক করে নতুন অ্যাকাউন্ট যোগ করুন।", parse_mode='Markdown', reply_markup=kb)
        return
    
    text = "👥 *আপনার অ্যাকাউন্ট:*\n"
    kb = []
    for sn in accounts_data:
        ok = sn in running_tasks and not running_tasks[sn].done()
        # চেক করি session file আছে কিনা (লগইন করা আছে কিনা)
        session_file = f"{SESSIONS_DIR}/{sn}.session"
        is_logged_in = os.path.exists(session_file)
        
        if ok:
            status_icon = '🟢'
            status_text = 'চালু'
        elif is_logged_in:
            status_icon = '🟡'
            status_text = 'লগইন করা (বন্ধ)'
        else:
            status_icon = '🔴'
            status_text = 'লগইন করা হয়নি'
        
        text += f"\n{status_icon} `{sn}` - {status_text}"
        kb.append([InlineKeyboardButton(f"{status_icon} {sn}", callback_data=f'view_{sn}')])
    
    kb.append([InlineKeyboardButton("➕ অ্যাকাউন্ট যোগ করুন", callback_data='add_account')])
    kb.append([InlineKeyboardButton("🔙 ফিরে যান", callback_data='back')])
    
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb))


async def view_account(query, sn):
    if sn not in accounts_data:
        await query.edit_message_text("❌ পাওয়া যায়নি!")
        return
    
    acc = accounts_data[sn]
    ok = sn in running_tasks and not running_tasks[sn].done()
    
    session_file = f"{SESSIONS_DIR}/{sn}.session"
    is_logged_in = os.path.exists(session_file)
    
    if ok:
        status_text = "✅ চালু"
        status_icon = "🟢"
    elif is_logged_in:
        status_text = "🟡 লগইন করা (বন্ধ)"
        status_icon = "🟡"
    else:
        status_text = "🔴 লগইন করা হয়নি"
        status_icon = "🔴"
    
    text = f"📱 *{sn}*\n"
    text += f"স্ট্যাটাস: {status_text}\n"
    text += f"ফোন: `{acc.get('phone', 'N/A')}`\n"
    text += f"API ID: `{acc['api_id']}`\n"
    
    kb_buttons = []
    
    if ok:
        kb_buttons.append([InlineKeyboardButton("⏹️ বন্ধ করুন", callback_data=f'toggle_{sn}')])
    elif is_logged_in:
        kb_buttons.append([InlineKeyboardButton("▶️ চালু করুন", callback_data=f'toggle_{sn}')])
    else:
        kb_buttons.append([InlineKeyboardButton("📱 OTP লগইন করুন", callback_data=f'login_{sn}')])
    
    kb_buttons.append([InlineKeyboardButton("🗑️ ডিলিট করুন", callback_data=f'delete_{sn}')])
    kb_buttons.append([InlineKeyboardButton("🔙 ফিরে যান", callback_data='accounts')])
    
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb_buttons))


async def delete_account(query, sn):
    if sn in running_tasks and not running_tasks[sn].done():
        running_tasks[sn].cancel()
        del running_tasks[sn]
    
    if sn in accounts_data:
        del accounts_data[sn]
        save_data()
    
    # session file ডিলিট
    sf = f"{SESSIONS_DIR}/{sn}.session"
    if os.path.exists(sf):
        os.remove(sf)
    
    await query.answer("✅ ডিলিট করা হয়েছে!")
    await show_accounts(query)


async def toggle_account(query, sn):
    if sn not in accounts_data:
        await query.answer("❌ অ্যাকাউন্ট নেই!")
        return
    
    # চেক করি session file আছে কিনা
    session_file = f"{SESSIONS_DIR}/{sn}.session"
    if not os.path.exists(session_file):
        await query.answer("❌ আগে লগইন করুন!")
        await view_account(query, sn)
        return
    
    if sn in running_tasks and not running_tasks[sn].done():
        running_tasks[sn].cancel()
        del running_tasks[sn]
        await query.answer("⏹️ বন্ধ করা হয়েছে!")
    else:
        running_tasks[sn] = asyncio.create_task(run_account(sn))
        await query.answer("▶️ চালু করা হয়েছে!")
    
    await view_account(query, sn)


async def start_otp_login(query, sn):
    """OTP লগইন প্রক্রিয়া শুরু করে"""
    if sn not in accounts_data:
        await query.edit_message_text("❌ অ্যাকাউন্ট নেই!")
        return
    
    acc = accounts_data[sn]
    phone = acc.get('phone')
    api_id = acc['api_id']
    api_hash = acc['api_hash']
    
    if not phone:
        await query.edit_message_text("❌ ফোন নম্বর নেই! অ্যাকাউন্টে ফোন নম্বর যোগ করুন।")
        return
    
    await query.edit_message_text(f"📱 *OTP পাঠানো হচ্ছে...*\n\nফোন: `{phone}`\n\nঅপেক্ষা করুন...", parse_mode='Markdown')
    
    result = await request_otp(sn, phone, api_id, api_hash)
    
    if result['success'] and result.get('client'):
        # চেক করি ইতিমধ্যে লগইন করা আছে কিনা
        if await result['client'].is_user_authorized():
            await query.edit_message_text(
                f"✅ *ইতিমধ্যে লগইন করা আছে!*\n\n"
                f"একাউন্ট: `{sn}`\n"
                f"এখন /start দিন এবং একাউন্ট চালু করুন।",
                parse_mode='Markdown'
            )
            return
    
    if result['success']:
        await query.edit_message_text(
            f"✅ *OTP পাঠানো হয়েছে!*\n\n"
            f"একাউন্ট: `{sn}`\n"
            f"ফোন: `{phone}`\n\n"
            f"📩 আপনার টেলিগ্রাম অ্যাপে কোড এসেছে।\n"
            f"সেটি নিচে টাইপ করে পাঠান:\n\n"
            f"যেমন: `12345`",
            parse_mode='Markdown'
        )
        
        # ইউজারের কাছ থেকে OTP ইনপুট নেওয়ার জন্য await_input সেট করি
        from telegram import Bot
        # আমরা context.user_data ব্যবহার করব text_handler এ
        # বর্তমানে query থেকে context পাই না,所以我们用 global variable
        # আসলে callback_query থেকে context পাওয়া যায়
    else:
        await query.edit_message_text(f"❌ OTP পাঠানো ব্যর্থ: {result['message']}")


async def show_settings(query):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ ম্যাসেজ পরিবর্তন", callback_data='edit_message')],
        [InlineKeyboardButton("⏱️ ইন্টারভাল সেটিংস", callback_data='edit_interval')],
        [InlineKeyboardButton("🔙 ফিরে যান", callback_data='back')]
    ])
    await query.edit_message_text(
        f"⚙️ *বর্তমান সেটিংস:*\n\n"
        f"📝 ম্যাসেজ: `{MESSAGE}`\n"
        f"⏱️ মিনিমাম: `{MIN_INTERVAL}`s\n"
        f"⏱️ ম্যাক্সিমাম: `{MAX_INTERVAL}`s\n"
        f"🔄 সাইকেল: `{CYCLE_WAIT}`s",
        parse_mode='Markdown', reply_markup=kb
    )


async def show_user_management(query):
    mode = "🔓 সবাই ব্যবহার করতে পারে" if not allowed_users else "🔒 শুধু অনুমতিপ্রাপ্ত ইউজার"
    text = f"🔒 *ইউজার ম্যানেজমেন্ট*\n\nমোড: {mode}\n\n🚫 **ব্লক করা:**\n"
    text += '\n'.join(f'• `{u}`' for u in blocked_users) if blocked_users else '• কেউ নেই'
    text += "\n\n✅ **অনুমতিপ্রাপ্ত:**\n"
    text += '\n'.join(f'• `{u}`' for u in allowed_users) if allowed_users else '• সবাই (কোন সীমা নেই)'
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔒 ব্লক করুন", callback_data='add_blocked_user'),
         InlineKeyboardButton("🔓 আনব্লক করুন", callback_data='remove_blocked_user')],
        [InlineKeyboardButton("✅ অনুমতি দিন", callback_data='add_allowed_user'),
         InlineKeyboardButton("❌ অনুমতি সরান", callback_data='remove_allowed_user')],
        [InlineKeyboardButton("🔄 মোড পরিবর্তন", callback_data='toggle_mode')],
        [InlineKeyboardButton("🔙 ফিরে যান", callback_data='back')]
    ])
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=kb)


async def start_all_accounts(query):
    if not accounts_data:
        await query.edit_message_text("❌ কোনো অ্যাকাউন্ট নেই!")
        return
    
    c = 0
    for sn in accounts_data:
        # চেক করি session file আছে কিনা
        session_file = f"{SESSIONS_DIR}/{sn}.session"
        if not os.path.exists(session_file):
            continue
        
        if sn not in running_tasks or running_tasks[sn].done():
            running_tasks[sn] = asyncio.create_task(run_account(sn))
            c += 1
    
    await query.answer(f"✅ {c} টি চালু করা হয়েছে!")
    await query.edit_message_text(f"✅ {c} টি অ্যাকাউন্ট চালু করা হয়েছে!\n\nযেগুলোতে লগইন করা নেই, সেগুলো শুরু হয়নি।")


async def stop_all_accounts(query):
    c = 0
    for sn in list(running_tasks.keys()):
        if not running_tasks[sn].done():
            running_tasks[sn].cancel()
            del running_tasks[sn]
            c += 1
    await query.answer(f"⏹️ {c} টি বন্ধ করা হয়েছে!")
    await query.edit_message_text(f"⏹️ {c} টি অ্যাকাউন্ট বন্ধ করা হয়েছে!")


async def show_status(query):
    text = "📊 *স্ট্যাটাস রিপোর্ট*\n\n"
    
    if not accounts_data:
        text += "❌ কোনো অ্যাকাউন্ট নেই।"
    else:
        running_count = 0
        logged_in_count = 0
        
        for sn in accounts_data:
            ok = sn in running_tasks and not running_tasks[sn].done()
            session_file = f"{SESSIONS_DIR}/{sn}.session"
            is_logged_in = os.path.exists(session_file)
            
            if ok:
                text += f"🟢 `{sn}` (চালু)\n"
                running_count += 1
                if is_logged_in:
                    logged_in_count += 1
            elif is_logged_in:
                text += f"🟡 `{sn}` (লগইন করা, বন্ধ)\n"
                logged_in_count += 1
            else:
                text += f"🔴 `{sn}` (লগইন করা হয়নি)\n"
        
        text += f"\nমোট: {len(accounts_data)}"
        text += f"\nলগইন করা: {logged_in_count}"
        text += f"\nচলছে: {running_count}"
        text += f"\nবন্ধ: {len(accounts_data) - running_count}"
    
    text += f"\n\n📝 ম্যাসেজ: `{MESSAGE}`"
    text += f"\n⏱️ `{MIN_INTERVAL}`-`{MAX_INTERVAL}`s"
    text += f"\n🔄 প্রতি `{CYCLE_WAIT}`s"
    
    mode = "🔓 সবাই" if not allowed_users else "🔒 শুধু অনুমতি"
    text += f"\n👥 মোড: {mode} | ব্লক: {len(blocked_users)} জন"
    
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 রিফ্রেশ", callback_data='status')],
        [InlineKeyboardButton("🔙 ফিরে যান", callback_data='back')]
    ])
    
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=kb)


async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    if not await is_user_allowed(user_id):
        return
    
    awaiting = context.user_data.get('awaiting_input')
    
    # ====== OTP কোড হ্যান্ডলিং ======
    # যদি awaiting_input 'otp_' দিয়ে শুরু হয়, তাহলে OTP ইনপুট
    if awaiting and awaiting.startswith('otp_'):
        session_name = awaiting.replace('otp_', '')
        
        if user_id != OWNER_ID:
            return
        
        await update.message.reply_text(f"⏳ OTP ভেরিফাই করা হচ্ছে...")
        
        result = await verify_otp(session_name, text)
        
        if result.get('need_2fa'):
            # 2FA পাসওয়ার্ড চাই
            context.user_data['awaiting_input'] = f'2fa_{session_name}'
            await update.message.reply_text(
                "🔑 *2FA পাসওয়ার্ড প্রয়োজন!*\n\n"
                "আপনার টু-ফ্যাক্টর অথেনটিকেশন পাসওয়ার্ড দিন:",
                parse_mode='Markdown'
            )
        elif result['success']:
            context.user_data['awaiting_input'] = None
            await update.message.reply_text(
                f"✅ *OTP লগইন সফল!*\n\n"
                f"একাউন্ট: `{session_name}`\n\n"
                f"এখন /start দিন এবং একাউন্ট চালু করুন।",
                parse_mode='Markdown'
            )
        else:
            context.user_data['awaiting_input'] = None
            await update.message.reply_text(f"❌ {result['message']}")
        
        return
    
    # ====== 2FA পাসওয়ার্ড হ্যান্ডলিং ======
    if awaiting and awaiting.startswith('2fa_'):
        session_name = awaiting.replace('2fa_', '')
        
        if user_id != OWNER_ID:
            return
        
        await update.message.reply_text(f"⏳ 2FA পাসওয়ার্ড ভেরিফাই করা হচ্ছে...")
        
        result = await verify_2fa(session_name, text)
        
        if result['success']:
            context.user_data['awaiting_input'] = None
            await update.message.reply_text(
                f"✅ *2FA লগইন সফল!*\n\n"
                f"একাউন্ট: `{session_name}`\n\n"
                f"এখন /start দিন এবং একাউন্ট চালু করুন।",
                parse_mode='Markdown'
            )
        else:
            context.user_data['awaiting_input'] = None
            await update.message.reply_text(f"❌ {result['message']}")
        
        return
    
    # ====== অন্যান্য ইনপুট হ্যান্ডলিং ======
    if not awaiting or user_id != OWNER_ID:
        return
    
    global MESSAGE, MIN_INTERVAL, MAX_INTERVAL, CYCLE_WAIT
    
    if awaiting == 'add_account':
        if text.lower() == 'বাতিল':
            context.user_data['awaiting_input'] = None
            await update.message.reply_text("✅ বাতিল করা হয়েছে। /start দিন")
            return
        
        parts = text.split(',')
        if len(parts) != 4:
            await update.message.reply_text(
                "❌ ফরম্যাট: `নাম,ফোন_নম্বর,API_ID,API_HASH`\n\n"
                "উদাহরণ: `acc1,+8801712345678,123456,abc123def456`",
                parse_mode='Markdown'
            )
            return
        
        sn, phone, aid, ah = parts[0].strip(), parts[1].strip(), parts[2].strip(), parts[3].strip()
        
        if not aid.isdigit():
            await update.message.reply_text("❌ API_ID সংখ্যা হতে হবে!")
            return
        
        if not phone.startswith('+'):
            await update.message.reply_text("❌ ফোন নম্বর + দিয়ে শুরু হতে হবে! যেমন: `+8801712345678`", parse_mode='Markdown')
            return
        
        accounts_data[sn] = {
            'phone': phone,
            'api_id': int(aid),
            'api_hash': ah
        }
        
        os.makedirs(SESSIONS_DIR, exist_ok=True)
        save_data()
        context.user_data['awaiting_input'] = None
        
        await update.message.reply_text(
            f"✅ *অ্যাকাউন্ট যোগ হয়েছে!*\n\n"
            f"নাম: `{sn}`\n"
            f"ফোন: `{phone}`\n"
            f"API ID: `{aid}`\n\n"
            f"এখন একাউন্ট সিলেক্ট করে OTP লগইন করুন।\n"
            f"/start দিন দেখতে।",
            parse_mode='Markdown'
        )
    
    elif awaiting == 'edit_message':
        MESSAGE = text
        save_data()
        context.user_data['awaiting_input'] = None
        await update.message.reply_text(f"✅ *ম্যাসেজ আপডেট!*\n\n`{MESSAGE}`", parse_mode='Markdown')
    
    elif awaiting in ['set_min', 'set_max', 'set_cycle']:
        if not text.isdigit() or int(text) < 1:
            await update.message.reply_text("❌ বৈধ সংখ্যা দিন (১ বা তার বেশি)!")
            return
        
        v = int(text)
        if awaiting == 'set_min' and v >= MAX_INTERVAL:
            await update.message.reply_text(f"❌ মিনিমাম {MAX_INTERVAL} এর কম হতে হবে!")
            return
        if awaiting == 'set_max' and v <= MIN_INTERVAL:
            await update.message.reply_text(f"❌ ম্যাক্সিমাম {MIN_INTERVAL} এর বেশি হতে হবে!")
            return
        
        if awaiting == 'set_min':
            MIN_INTERVAL = v
        elif awaiting == 'set_max':
            MAX_INTERVAL = v
        elif awaiting == 'set_cycle':
            CYCLE_WAIT = v
        
        save_data()
        context.user_data['awaiting_input'] = None
        
        names = {'set_min': 'মিনিমাম', 'set_max': 'ম্যাক্সিমাম', 'set_cycle': 'সাইকেল'}
        await update.message.reply_text(f"✅ *{names[awaiting]} আপডেট!*\n\nনতুন মান: `{v}` সেকেন্ড", parse_mode='Markdown')
    
    elif awaiting == 'add_blocked_user':
        if not text.isdigit():
            await update.message.reply_text("❌ সংখ্যা দিন!")
            return
        uid = int(text)
        if uid == OWNER_ID:
            await update.message.reply_text("❌ ওনারকে ব্লক করা যাবে না!")
            return
        if uid not in blocked_users:
            blocked_users.append(uid)
            save_data()
        await update.message.reply_text(f"🔒 `{uid}` ব্লক করা হয়েছে!", parse_mode='Markdown')
        context.user_data['awaiting_input'] = None
    
    elif awaiting == 'add_allowed_user':
        if not text.isdigit():
            await update.message.reply_text("❌ সংখ্যা দিন!")
            return
        uid = int(text)
        if uid not in allowed_users:
            allowed_users.append(uid)
            save_data()
        await update.message.reply_text(f"✅ `{uid}` কে অনুমতি দেওয়া হয়েছে!", parse_mode='Markdown')
        context.user_data['awaiting_input'] = None
    
    elif awaiting == 'remove_blocked_user':
        if not text.isdigit():
            await update.message.reply_text("❌ সংখ্যা দিন!")
            return
        uid = int(text)
        if uid in blocked_users:
            blocked_users.remove(uid)
            save_data()
        await update.message.reply_text(f"🔓 `{uid}` আনব্লক করা হয়েছে!", parse_mode='Markdown')
        context.user_data['awaiting_input'] = None
    
    elif awaiting == 'remove_allowed_user':
        if not text.isdigit():
            await update.message.reply_text("❌ সংখ্যা দিন!")
            return
        uid = int(text)
        if uid == OWNER_ID:
            await update.message.reply_text("❌ ওনারকে সরানো যাবে না!")
            return
        if uid in allowed_users:
            allowed_users.remove(uid)
            save_data()
        await update.message.reply_text(f"❌ `{uid}` সরানো হয়েছে!", parse_mode='Markdown')
        context.user_data['awaiting_input'] = None


# ============================================================
# ম্যাসেজ সেন্ডিং ফাংশন
# ============================================================

async def run_account(session_name):
    """একাউন্ট চালু করে এবং সব গ্রুপে ম্যাসেজ পাঠায়"""
    if session_name not in accounts_data:
        return
    
    acc = accounts_data[session_name]
    
    # চেক করি session file আছে কিনা
    session_file = f"{SESSIONS_DIR}/{session_name}.session"
    if not os.path.exists(session_file):
        logger.warning(f"[{session_name}] Session file নেই! লগইন করা হয়নি।")
        return
    
    client = TelegramClient(f"{SESSIONS_DIR}/{session_name}", acc['api_id'], acc['api_hash'])
    
    try:
        await client.connect()
        
        # চেক করি অথরাইজড কিনা
        if not await client.is_user_authorized():
            logger.warning(f"[{session_name}] অথরাইজড না! OTP লাগবে।")
            # session file ডিলিট করে দিই যাতে ইউজার বুঝতে পারে
            try:
                os.remove(session_file)
            except:
                pass
            await client.disconnect()
            return
        
        me = await client.get_me()
        logger.info(f"✅ [{session_name}] লগইন সফল! ইউজার: {me.first_name}")
        
        # গ্রুপ লিস্ট নেওয়া
        groups = []
        try:
            dialogs = await client(GetDialogsRequest(
                offset_date=None,
                offset_id=0,
                offset_peer=InputPeerEmpty(),
                limit=200,
                hash=0
            ))
            
            for dialog in dialogs.dialogs:
                try:
                    entity = await client.get_entity(dialog.peer)
                    if hasattr(entity, 'title') and entity.title not in EXCLUDED_GROUPS:
                        groups.append(entity)
                except:
                    pass
                    
        except Exception as e:
            logger.error(f"[{session_name}] গ্রুপ লিস্ট নিতে ত্রুটি: {e}")
            await client.disconnect()
            return
        
        if not groups:
            logger.warning(f"[{session_name}] কোনো গ্রুপ পাওয়া যায়নি!")
            await client.disconnect()
            return
        
        logger.info(f"[{session_name}] {len(groups)} টি গ্রুপ পাওয়া গেছে")
        
        # ম্যাসেজ পাঠানোর লুপ
        while True:
            logger.info(f"[{session_name}] সাইকেল শুরু: {len(groups)} গ্রুপ")
            
            for i, g in enumerate(groups):
                try:
                    title = g.title if hasattr(g, 'title') else str(g.id)
                    await client.send_message(g, MESSAGE)
                    logger.info(f"[{session_name}] ✅ [{i+1}/{len(groups)}] {title}")
                    
                except FloodWaitError as e:
                    logger.warning(f"[{session_name}] ⏳ FloodWait: {e.seconds} সেকেন্ড অপেক্ষা")
                    await asyncio.sleep(e.seconds)
                    
                except Exception as e:
                    logger.error(f"[{session_name}] পাঠাতে ত্রুটি: {e}")
                
                # র্যান্ডম ইন্টারভাল
                await asyncio.sleep(random.randint(MIN_INTERVAL, MAX_INTERVAL))
            
            logger.info(f"[{session_name}] 🔄 সাইকেল শেষ। {CYCLE_WAIT} সেকেন্ড অপেক্ষা...")
            await asyncio.sleep(CYCLE_WAIT)
    
    except asyncio.CancelledError:
        logger.info(f"[{session_name}] ⛔ বন্ধ করা হয়েছে")
        
    except Exception as e:
        logger.error(f"[{session_name}] মারাত্মক ত্রুটি: {e}")
    
    finally:
        try:
            await client.disconnect()
        except:
            pass


# ============================================================
# 🔥 মেইন ফাংশন
# ============================================================

async def main():
    logger.info("🚀 বট শুরু হচ্ছে Flask HTTP সার্ভার সহ...")
    print("✅ বট চালু হচ্ছে...")
    
    os.makedirs(SESSIONS_DIR, exist_ok=True)
    
    # পুরনো লক ফাইল মুছুন
    for f in os.listdir('.'):
        if f.endswith('.lock'):
            try:
                os.remove(f)
            except:
                pass
    
    load_data()
    logger.info(f"📊 {len(accounts_data)} টি অ্যাকাউন্ট লোড করা হয়েছে")
    print(f"✅ {len(accounts_data)} টি অ্যাকাউন্ট লোড করা হয়েছে")
    
    # Bot তৈরি করুন
    app = Application.builder().token(BOT_TOKEN).build()
    
    # হ্যান্ডলার যোগ করুন
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    
    await app.initialize()
    await app.start()
    await app.updater.start_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
    
    logger.info("✅ বট এখন 24/7 চলছে!")
    print("✅ বট চালু! Flask HTTP সার্ভার চলছে port " + os.environ.get("PORT", "10000"))
    print("✅ টেলিগ্রামে আপনার বটে /start দিন।")
    
    try:
        while True:
            await asyncio.sleep(3600)
            logger.info("বট জীবিত আছে...")
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
        logger.info("⛔ বট বন্ধ করা হয়েছে")
    except Exception as e:
        logger.error(f"❌ মারাত্মক ত্রুটি: {e}", exc_info=True)
        sys.exit(1)
