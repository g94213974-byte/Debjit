#!/usr/bin/env python3
# mass_bot_v4.py - FINAL (User Account OTP Login - Message via User Account)

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

# ====== Flask HTTP (Render port scan fix) ======
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

# ====== কন্ট্রোল বট টোকেন (শুধু কন্ট্রোল প্যানেল) ======
BOT_TOKEN = "8875386448:AAH2RMJixaVOyLPZkYJayh3WcGVrc5octnA"
OWNER_ID = 8001816524

# ====== তোমার নিজের API Credentials (my.telegram.org থেকে) ======
# ⚠️ এখানে তোমার নিজের API_ID এবং API_HASH বসাও
MY_API_ID = 2040
MY_API_HASH = "b18441a1ff607e10a989891a5462e627"

# ====== ফাইল ======
DATA_FILE = "bot_data.json"
SESSIONS_DIR = "sessions"

# ====== গ্লোবাল ======
running_tasks = {}
accounts_data = {}
blocked_users = []
allowed_users = []
pending_otp = {}  # OTP লগইন পেন্ডিং
bot_app = None

# ====== ডিফল্ট ======
MESSAGE = "𝟭𝟬 𝗠𝗜𝗡 𝗩𝗖 ₹𝟰𝟵 𝗕𝗔𝗕𝗬😘"
MIN_INTERVAL = 10
MAX_INTERVAL = 20
CYCLE_WAIT = 120
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
        
        if not isinstance(data, dict): data = default_data
        
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
    except:
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
# হ্যান্ডলার
# ============================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    if not await is_user_allowed(user_id):
        await update.message.reply_text("❌ আপনি এই বট ব্যবহারের জন্য অনুমোদিত নন!")
        return
    
    if user_id != OWNER_ID:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📊 স্ট্যাটাস", callback_data='user_status')]
        ])
        await update.message.reply_text(f"👋 স্বাগতম {user.first_name}!", reply_markup=keyboard)
        return
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 অ্যাকাউন্ট", callback_data='accounts')],
        [InlineKeyboardButton("⚙️ সেটিংস", callback_data='settings')],
        [InlineKeyboardButton("🔒 ইউজার", callback_data='user_manage')],
        [InlineKeyboardButton("▶️ সব চালু", callback_data='start_all')],
        [InlineKeyboardButton("⏹️ সব বন্ধ", callback_data='stop_all')],
        [InlineKeyboardButton("📊 স্ট্যাটাস", callback_data='status')]
    ])
    
    await update.message.reply_text(
        "🤖 *ইউজার অ্যাকাউন্ট ম্যাসেজিং বট*\n\n"
        "ফোন নম্বর + OTP দিয়ে লগইন করুন এবং গ্রুপে ম্যাসেজ পাঠান 🚀",
        parse_mode='Markdown', reply_markup=keyboard
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    if not await is_user_allowed(user_id): return
    
    data = query.data
    
    if data == 'user_status':
        await query.edit_message_text("📊 বট সক্রিয় আছে।")
        return
    
    if user_id != OWNER_ID: return
    
    if data == 'accounts':
        await show_accounts(query)
    elif data == 'add_account':
        context.user_data['awaiting_input'] = 'add_account'
        await query.edit_message_text(
            "📱 *ইউজার অ্যাকাউন্ট যোগ করুন*\n\n"
            "ফরম্যাট: `নাম,ফোন_নম্বর`\n\n"
            "উদাহরণ: `acc1,+8801712345678`\n\n"
            "⚠️ ফোন + এবং কান্ট্রি কোড সহ\n"
            "⚠️ API_ID/API_HASH auto সেট হবে\n\n"
            "'বাতিল' লিখুন বাতিল করতে।",
            parse_mode='Markdown'
        )
    elif data.startswith('view_'):
        sn = data.replace('view_', '')
        context.user_data['last_viewed'] = sn
        await view_account(query, sn, context)
    elif data.startswith('delete_'):
        sn = data.replace('delete_', '')
        await delete_account(query, sn)
    elif data.startswith('toggle_'):
        sn = data.replace('toggle_', '')
        await toggle_account(query, sn)
    elif data == 'send_otp':
        sn = context.user_data.get('last_viewed', '')
        if sn and sn in accounts_data:
            await send_otp_process(query, sn, context)
        else:
            await query.edit_message_text("❌ অ্যাকাউন্ট সিলেক্ট করুন আগে!")
    elif data == 'settings':
        await show_settings(query, context)
    elif data == 'edit_message':
        context.user_data['awaiting_input'] = 'edit_message'
        await query.edit_message_text(f"✏️ নতুন ম্যাসেজ:\nবর্তমান: `{MESSAGE}`", parse_mode='Markdown')
    elif data == 'edit_interval':
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"📉 মিন ({MIN_INTERVAL}s)", callback_data='set_min'),
             InlineKeyboardButton(f"📈 ম্যাক্স ({MAX_INTERVAL}s)", callback_data='set_max')],
            [InlineKeyboardButton(f"🔄 সাইকেল ({CYCLE_WAIT}s)", callback_data='set_cycle')],
            [InlineKeyboardButton("🔙 ফিরে", callback_data='settings')]
        ])
        await query.edit_message_text("⚙️ *ইন্টারভাল*", parse_mode='Markdown', reply_markup=kb)
    elif data in ['set_min', 'set_max', 'set_cycle']:
        context.user_data['awaiting_input'] = data
        labels = {'set_min': 'মিনিমাম', 'set_max': 'ম্যাক্সিমাম', 'set_cycle': 'সাইকেল'}
        vals = {'set_min': MIN_INTERVAL, 'set_max': MAX_INTERVAL, 'set_cycle': CYCLE_WAIT}
        await query.edit_message_text(f"✏️ *{labels[data]}*\nবর্তমান: `{vals[data]}`s\n\nনতুন মান (সেকেন্ড):", parse_mode='Markdown')
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
            'add_blocked_user': '🔒 ব্লক করতে আইডি:',
            'add_allowed_user': '✅ অনুমতি দিতে আইডি:',
            'remove_blocked_user': '🔓 আনব্লক করতে আইডি:',
            'remove_allowed_user': '❌ অনুমতি সরাতে আইডি:'
        }
        context.user_data['awaiting_input'] = data
        await query.edit_message_text(labels[data])
    elif data == 'toggle_mode':
        if allowed_users:
            allowed_users.clear()
            await query.answer("✅ সবাই ব্যবহার করতে পারবে!")
        else:
            if OWNER_ID not in allowed_users: allowed_users.append(OWNER_ID)
            await query.answer("✅ শুধু অনুমতিপ্রাপ্ত!")
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
            [InlineKeyboardButton("➕ যোগ করুন", callback_data='add_account')],
            [InlineKeyboardButton("🔙 ফিরে", callback_data='back')]
        ])
        await query.edit_message_text("📭 *কোন অ্যাকাউন্ট নেই*", parse_mode='Markdown', reply_markup=kb)
        return
    
    text = "👥 *আপনার অ্যাকাউন্ট:*\n"
    kb = []
    
    for sn in accounts_data:
        ok = sn in running_tasks and not running_tasks[sn].done()
        sf = f"{SESSIONS_DIR}/{sn}.session"
        has_session = os.path.exists(sf)
        
        if ok:
            icon = '🟢'
            st = 'চালু'
        elif has_session:
            icon = '🟡'
            st = 'লগইন করা'
        else:
            icon = '🔴'
            st = 'লগইন করেনি'
        
        text += f"\n{icon} `{sn}` - {st}"
        kb.append([InlineKeyboardButton(f"{icon} {sn}", callback_data=f'view_{sn}')])
    
    kb.append([InlineKeyboardButton("➕ যোগ করুন", callback_data='add_account')])
    kb.append([InlineKeyboardButton("🔙 ফিরে", callback_data='back')])
    
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb))


async def view_account(query, sn, context):
    if sn not in accounts_data:
        await query.edit_message_text("❌ নেই!")
        return
    
    acc = accounts_data[sn]
    ok = sn in running_tasks and not running_tasks[sn].done()
    sf = f"{SESSIONS_DIR}/{sn}.session"
    has_session = os.path.exists(sf)
    
    if ok:
        st = "✅ চালু"
    elif has_session:
        st = "🟡 লগইন করা (বন্ধ)"
    else:
        st = "🔴 লগইন করেনি"
    
    text = f"📱 *{sn}*\n"
    text += f"স্ট্যাটাস: {st}\n"
    text += f"ফোন: `{acc['phone']}`\n"
    
    but = []
    
    if ok:
        but.append([InlineKeyboardButton("⏹️ বন্ধ", callback_data=f'toggle_{sn}')])
    elif has_session:
        but.append([InlineKeyboardButton("▶️ চালু", callback_data=f'toggle_{sn}')])
    else:
        but.append([InlineKeyboardButton("📱 OTP পাঠান", callback_data='send_otp')])
    
    but.append([InlineKeyboardButton("🗑️ ডিলিট", callback_data=f'delete_{sn}')])
    but.append([InlineKeyboardButton("🔙 ফিরে", callback_data='accounts')])
    
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(but))


async def send_otp_process(query, sn, context):
    """OTP পাঠানোর প্রক্রিয়া"""
    if sn not in accounts_data:
        await query.edit_message_text("❌ অ্যাকাউন্ট নেই!")
        return
    
    acc = accounts_data[sn]
    phone = acc['phone']
    api_id = MY_API_ID
    api_hash = MY_API_HASH
    
    await query.edit_message_text(f"📱 *OTP পাঠানো হচ্ছে*\n\nফোন: `{phone}`\n\nঅপেক্ষা করুন...", parse_mode='Markdown')
    
    try:
        client = TelegramClient(f"{SESSIONS_DIR}/{sn}", api_id, api_hash)
        await client.connect()
        
        # ইতিমধ্যে লগইন করা আছে কিনা চেক
        if await client.is_user_authorized():
            me = await client.get_me()
            await query.edit_message_text(
                f"✅ *ইতিমধ্যে লগইন করা!*\n\n"
                f"নাম: `{sn}`\n"
                f"ব্যবহারকারী: {me.first_name}\n\n"
                f"এখন '▶️ চালু' দিন।",
                parse_mode='Markdown'
            )
            await client.disconnect()
            return
        
        # OTP রিকোয়েস্ট
        result = await client.send_code_request(phone)
        
        # পেন্ডিং লগইন সেভ
        pending_otp[sn] = {
            'client': client,
            'phone': phone,
            'phone_code_hash': result.phone_code_hash
        }
        
        # ইউজারকে জানাই
        context.user_data['awaiting_input'] = f'otp_{sn}'
        
        await query.edit_message_text(
            f"✅ *OTP পাঠানো হয়েছে!*\n\n"
            f"একাউন্ট: `{sn}`\n"
            f"ফোন: `{phone}`\n\n"
            f"📩 টেলিগ্রাম অ্যাপে কোড এসেছে\n"
            f"নিচে শুধু **কোডটা** লিখে পাঠান:\n"
            f'যেমন: `12345`',
            parse_mode='Markdown'
        )
        
    except Exception as e:
        await query.edit_message_text(f"❌ OTP পাঠাতে ব্যর্থ: {e}")


async def delete_account(query, sn):
    if sn in running_tasks and not running_tasks[sn].done():
        running_tasks[sn].cancel()
        if sn in running_tasks: del running_tasks[sn]
    
    if sn in accounts_data:
        del accounts_data[sn]
        save_data()
    
    sf = f"{SESSIONS_DIR}/{sn}.session"
    if os.path.exists(sf): os.remove(sf)
    
    # পেন্ডিং থাকলে ক্লিন
    if sn in pending_otp:
        try: await pending_otp[sn]['client'].disconnect()
        except: pass
        del pending_otp[sn]
    
    await query.answer("✅ ডিলিট!")
    await show_accounts(query)


async def toggle_account(query, sn):
    if sn not in accounts_data:
        await query.answer("❌ নেই!")
        return
    
    sf = f"{SESSIONS_DIR}/{sn}.session"
    
    if not os.path.exists(sf):
        # session file নেই — OTP লাগবে
        await query.answer("❌ আগে OTP দিন!")
        return
    
    if sn in running_tasks and not running_tasks[sn].done():
        running_tasks[sn].cancel()
        if sn in running_tasks: del running_tasks[sn]
        await query.answer("⏹️ বন্ধ!")
    else:
        running_tasks[sn] = asyncio.create_task(run_account(sn))
        await query.answer("▶️ চালু!")
    
    await asyncio.sleep(2)
    # রিফ্রেশ দেখানোর জন্য accounts এ ফেরত
    from telegram import Bot
    await show_accounts(query)


async def show_settings(query, context):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ ম্যাসেজ", callback_data='edit_message')],
        [InlineKeyboardButton("⏱️ ইন্টারভাল", callback_data='edit_interval')],
        [InlineKeyboardButton("🔙 ফিরে", callback_data='back')]
    ])
    await query.edit_message_text(
        f"⚙️ *সেটিংস:*\n\n"
        f"📝 `{MESSAGE}`\n"
        f"⏱️ `{MIN_INTERVAL}`-`{MAX_INTERVAL}`s\n"
        f"🔄 প্রতি `{CYCLE_WAIT}`s",
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
    for sn in accounts_data:
        sf = f"{SESSIONS_DIR}/{sn}.session"
        if not os.path.exists(sf): continue
        if sn not in running_tasks or running_tasks[sn].done():
            running_tasks[sn] = asyncio.create_task(run_account(sn))
            c += 1
    await query.answer(f"✅ {c} টি চালু!")
    await query.edit_message_text(f"✅ {c} টি চালু করা হচ্ছে...")


async def stop_all_accounts(query):
    c = 0
    for sn in list(running_tasks.keys()):
        if not running_tasks[sn].done():
            running_tasks[sn].cancel()
            if sn in running_tasks: del running_tasks[sn]
            c += 1
    await query.answer(f"⏹️ {c} টি বন্ধ!")
    await query.edit_message_text(f"⏹️ {c} টি বন্ধ করা হয়েছে!")


async def show_status(query):
    text = "📊 *স্ট্যাটাস*\n\n"
    if not accounts_data:
        text += "❌ কোনো অ্যাকাউন্ট নেই"
    else:
        r, l = 0, 0
        for sn in accounts_data:
            ok = sn in running_tasks and not running_tasks[sn].done()
            hs = os.path.exists(f"{SESSIONS_DIR}/{sn}.session")
            if ok:
                text += f"🟢 `{sn}`\n"; r += 1
                if hs: l += 1
            elif hs:
                text += f"🟡 `{sn}`\n"; l += 1
            else:
                text += f"🔴 `{sn}`\n"
        text += f"\nমোট: {len(accounts_data)} | চালু: {r}"
        text += f"\nলগইন: {l} | বাকি: {len(accounts_data)-l}"
    text += f"\n\n📝 `{MESSAGE}`\n⏱️ `{MIN_INTERVAL}`-`{MAX_INTERVAL}`s\n🔄 `{CYCLE_WAIT}`s"
    await query.edit_message_text(text, parse_mode='Markdown')


# ============================================================
# OTP ও 2FA হ্যান্ডলিং (টেক্সট হ্যান্ডলার)
# ============================================================

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    if not await is_user_allowed(user_id):
        return
    
    awaiting = context.user_data.get('awaiting_input')
    
    if not awaiting or user_id != OWNER_ID:
        return
    
    global MESSAGE, MIN_INTERVAL, MAX_INTERVAL, CYCLE_WAIT
    
    # ====== OTP কোড ইনপুট ======
    if awaiting.startswith('otp_'):
        sn = awaiting.replace('otp_', '')
        
        if sn not in pending_otp:
            await update.message.reply_text("❌ OTP সেশন মেয়াদ শেষ! আবার OTP পাঠান।")
            context.user_data['awaiting_input'] = None
            return
        
        login_data = pending_otp[sn]
        client = login_data['client']
        phone = login_data['phone']
        phone_code_hash = login_data['phone_code_hash']
        
        await update.message.reply_text("⏳ OTP ভেরিফাই করা হচ্ছে...")
        
        try:
            # OTP ভেরিফাই
            user = await client.sign_in(
                phone=phone,
                code=text,
                phone_code_hash=phone_code_hash
            )
            
            # সফল
            me = await client.get_me()
            logger.info(f"✅ [{sn}] OTP লগইন সফল! ইউজার: {me.first_name}")
            
            del pending_otp[sn]
            context.user_data['awaiting_input'] = None
            
            await update.message.reply_text(
                f"✅ *লগইন সফল!*\n\n"
                f"নাম: `{sn}`\n"
                f"ব্যবহারকারী: {me.first_name}\n"
                f"ফোন: `{phone}`\n\n"
                f"এখন /start দিন এবং '▶️ চালু করুন' এ ক্লিক করুন 🚀",
                parse_mode='Markdown'
            )
            
        except SessionPasswordNeededError:
            # 2FA চাই
            context.user_data['awaiting_input'] = f'2fa_{sn}'
            await update.message.reply_text(
                "🔑 *2FA পাসওয়ার্ড লাগবে!*\n\n"
                "আপনার টু-ফ্যাক্টর পাসওয়ার্ড দিন:",
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"[{sn}] OTP error: {e}")
            await update.message.reply_text(f"❌ OTP ভুল বা মেয়াদ শেষ: {e}\n\nআবার 'OTP পাঠান' দিন।")
            # ব্যর্থ হলে ক্লায়েন্ট ডিসকানেক্ট
            try: await client.disconnect()
            except: pass
            if sn in pending_otp: del pending_otp[sn]
            context.user_data['awaiting_input'] = None
        
        return
    
    # ====== 2FA পাসওয়ার্ড ======
    if awaiting.startswith('2fa_'):
        sn = awaiting.replace('2fa_', '')
        
        if sn not in pending_otp:
            await update.message.reply_text("❌ সেশন নেই! আবার OTP দিন।")
            context.user_data['awaiting_input'] = None
            return
        
        client = pending_otp[sn]['client']
        
        await update.message.reply_text("⏳ 2FA ভেরিফাই করা হচ্ছে...")
        
        try:
            user = await client.sign_in(password=text)
            me = await client.get_me()
            logger.info(f"✅ [{sn}] 2FA লগইন সফল! ইউজার: {me.first_name}")
            
            del pending_otp[sn]
            context.user_data['awaiting_input'] = None
            
            await update.message.reply_text(
                f"✅ *2FA লগইন সফল!*\n\n"
                f"নাম: `{sn}`\n"
                f"ব্যবহারকারী: {me.first_name}\n\n"
                f"এখন /start দিন এবং '▶️ চালু করুন' এ ক্লিক করুন 🚀",
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"[{sn}] 2FA error: {e}")
            await update.message.reply_text(f"❌ পাসওয়ার্ড ভুল: {e}")
        
        return
    
    # ====== বাকি ইনপুট ======
    
    if awaiting == 'add_account':
        if text.lower() == 'বাতিল':
            context.user_data['awaiting_input'] = None
            await update.message.reply_text("✅ বাতিল। /start দিন")
            return
        
        parts = text.split(',')
        if len(parts) != 2:
            await update.message.reply_text("❌ ফরম্যাট: `নাম,ফোন_নম্বর`\nযেমন: `acc1,+8801712345678`", parse_mode='Markdown')
            return
        
        sn, phone = parts[0].strip(), parts[1].strip()
        
        if not phone.startswith('+'):
            await update.message.reply_text("❌ ফোন + দিয়ে শুরু হবে! যেমন: `+8801712345678`", parse_mode='Markdown')
            return
        
        accounts_data[sn] = {'phone': phone}
        os.makedirs(SESSIONS_DIR, exist_ok=True)
        save_data()
        context.user_data['awaiting_input'] = None
        
        await update.message.reply_text(
            f"✅ *অ্যাকাউন্ট যোগ!*\n\n"
            f"নাম: `{sn}`\n"
            f"ফোন: `{phone}`\n\n"
            f"এখন একাউন্টে ক্লিক করে 'OTP পাঠান' দিন।\n"
            f"/start করুন",
            parse_mode='Markdown'
        )
    
    elif awaiting == 'edit_message':
        MESSAGE = text
        save_data()
        context.user_data['awaiting_input'] = None
        await update.message.reply_text(f"✅ *আপডেট!*\n\n`{MESSAGE}`", parse_mode='Markdown')
    
    elif awaiting in ['set_min', 'set_max', 'set_cycle']:
        if not text.isdigit() or int(text) < 2:
            await update.message.reply_text("❌ ২ বা তার বেশি দিন!")
            return
        v = int(text)
        if awaiting == 'set_min' and v >= MAX_INTERVAL:
            await update.message.reply_text(f"❌ মিন {MAX_INTERVAL} এর কম হতে হবে!")
            return
        if awaiting == 'set_max' and v <= MIN_INTERVAL:
            await update.message.reply_text(f"❌ ম্যাক্স {MIN_INTERVAL} এর বেশি হতে হবে!")
            return
        if awaiting == 'set_min': MIN_INTERVAL = v
        elif awaiting == 'set_max': MAX_INTERVAL = v
        elif awaiting == 'set_cycle': CYCLE_WAIT = v
        save_data()
        context.user_data['awaiting_input'] = None
        names = {'set_min': 'মিন', 'set_max': 'ম্যাক্স', 'set_cycle': 'সাইকেল'}
        await update.message.reply_text(f"✅ *{names[awaiting]} আপডেট!*\n\n`{v}`s", parse_mode='Markdown')
    
    elif awaiting == 'add_blocked_user':
        if not text.isdigit(): await update.message.reply_text("❌ সংখ্যা দিন!"); return
        uid = int(text)
        if uid == OWNER_ID: await update.message.reply_text("❓ ওনারকে ব্লক? না!"); return
        if uid not in blocked_users: blocked_users.append(uid); save_data()
        await update.message.reply_text(f"🔒 `{uid}` ব্লক!", parse_mode='Markdown')
        context.user_data['awaiting_input'] = None
    
    elif awaiting == 'add_allowed_user':
        if not text.isdigit(): await update.message.reply_text("❌ সংখ্যা দিন!"); return
        uid = int(text)
        if uid not in allowed_users: allowed_users.append(uid); save_data()
        await update.message.reply_text(f"✅ `{uid}` অনুমতি!", parse_mode='Markdown')
        context.user_data['awaiting_input'] = None
    
    elif awaiting == 'remove_blocked_user':
        if not text.isdigit(): await update.message.reply_text("❌ সংখ্যা দিন!"); return
        uid = int(text)
        if uid in blocked_users: blocked_users.remove(uid); save_data()
        await update.message.reply_text(f"🔓 `{uid}` আনব্লক!", parse_mode='Markdown')
        context.user_data['awaiting_input'] = None
    
    elif awaiting == 'remove_allowed_user':
        if not text.isdigit(): await update.message.reply_text("❌ সংখ্যা দিন!"); return
        uid = int(text)
        if uid == OWNER_ID: await update.message.reply_text("❓ ওনারকে সরাব?!"); return
        if uid in allowed_users: allowed_users.remove(uid); save_data()
        await update.message.reply_text(f"❌ `{uid}` সরানো!", parse_mode='Markdown')
        context.user_data['awaiting_input'] = None


# ============================================================
# ম্যাসেজ পাঠানো (ব্যবহারকারী অ্যাকাউন্ট দিয়ে)
# ============================================================

async def run_account(session_name):
    """ব্যবহারকারীর অ্যাকাউন্ট দিয়ে লগইন করে গ্রুপে ম্যাসেজ পাঠায়"""
    if session_name not in accounts_data:
        return
    
    acc = accounts_data[session_name]
    phone = acc['phone']
    session_file = f"{SESSIONS_DIR}/{session_name}.session"
    
    if not os.path.exists(session_file):
        logger.warning(f"[{session_name}] Session নেই!")
        return
    
    client = TelegramClient(session_file.replace('.session', ''), MY_API_ID, MY_API_HASH)
    
    try:
        await client.connect()
        
        if not await client.is_user_authorized():
            logger.warning(f"[{session_name}] অথরাইজড না! session নষ্ট।")
            try: os.remove(session_file)
            except: pass
            await client.disconnect()
            return
        
        me = await client.get_me()
        logger.info(f"✅ [{session_name}] লগইন: {me.first_name} ({phone})")
        
        # গ্রুপ লিস্ট
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
                except: pass
        except Exception as e:
            logger.error(f"[{session_name}] গ্রুপ error: {e}")
            await client.disconnect()
            return
        
        if not groups:
            logger.warning(f"[{session_name}] কোনো গ্রুপ নেই!")
            await client.disconnect()
            return
        
        logger.info(f"[{session_name}] {len(groups)} গ্রুপ")
        
        while True:
            logger.info(f"[{session_name}] সাইকেল: {len(groups)} গ্রুপ")
            
            for i, g in enumerate(groups):
                try:
                    title = g.title if hasattr(g, 'title') else str(g.id)
                    
                    # ইউজার অ্যাকাউন্ট দিয়ে ম্যাসেজ পাঠানো
                    await client.send_message(g, MESSAGE)
                    
                    logger.info(f"[{session_name}] ✅ [{i+1}/{len(groups)}] {title}")
                    
                except FloodWaitError as e:
                    logger.warning(f"[{session_name}] ⏳ Flood {e.seconds}s")
                    await asyncio.sleep(e.seconds)
                except Exception as e:
                    logger.error(f"[{session_name}] সেন্ড error: {e}")
                
                await asyncio.sleep(random.randint(MIN_INTERVAL, MAX_INTERVAL))
            
            logger.info(f"[{session_name}] 🔄 সাইকেল শেষ. {CYCLE_WAIT}s বিরতি...")
            await asyncio.sleep(CYCLE_WAIT)
    
    except asyncio.CancelledError:
        logger.info(f"[{session_name}] ⛔ বন্ধ")
    except Exception as e:
        logger.error(f"[{session_name}] fatal: {e}")
    finally:
        try: await client.disconnect()
        except: pass


# ============================================================
# ASCII আর্ট স্টার্টআপ
# ============================================================

def print_banner():
    print("""
╔══════════════════════════════════════╗
║     📱 ইউজার অ্যাকাউন্ট বট 📱        ║
║   OTP লগইন → গ্রুপ ম্যাসেজিং        ║
╚══════════════════════════════════════╝
    """)


# ============================================================
# 🔥 মেইন
# ============================================================

async def main():
    print_banner()
    logger.info("🚀 শুরু হচ্ছে...")
    
    os.makedirs(SESSIONS_DIR, exist_ok=True)
    
    for f in os.listdir('.'):
        if f.endswith('.lock'):
            try: os.remove(f)
            except: pass
    
    load_data()
    logger.info(f"📊 {len(accounts_data)} অ্যাকাউন্ট লোড")
    print(f"✅ {len(accounts_data)} অ্যাকাউন্ট")
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    
    await app.initialize()
    await app.start()
    await app.updater.start_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
    
    port = os.environ.get("PORT", "10000")
    print(f"\n✅ বট চালু! Flask port: {port}")
    print("✅ কন্ট্রোল বটে /start দিন")
    
    try:
        while True:
            await asyncio.sleep(3600)
            logger.info("বট জীবিত...")
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
