#!/usr/bin/env python3
# mass_bot.py - সম্পূর্ণ কন্ট্রোল প্যানেল সহ ম্যাসেজিং বট (Render Fix v2)

import os
import json
import asyncio
import random
import logging
from datetime import datetime
from telethon import TelegramClient
from telethon.errors import FloodWaitError, SessionPasswordNeededError
from telethon.tl.functions.messages import GetDialogsRequest
from telethon.tl.types import InputPeerEmpty
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# ====== লগিং ======
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ====== আপনার বট টোকেন ======
BOT_TOKEN = "8875386448:AAHhjXREES2lQYqEj-Wqv5Nlnln4e3wK0MM"
OWNER_ID = 8001816524

# ====== ডাটা ফাইল ======
DATA_FILE = "bot_data.json"
SESSIONS_DIR = "sessions"

# ====== গ্লোবাল ভেরিয়েবল ======
running_tasks = {}
accounts_data = {}
blocked_users = []
allowed_users = []
bot_app = None


# ============================================================
# ডাটা সেভ/লোড ফাংশন
# ============================================================

def load_data():
    global accounts_data, blocked_users, allowed_users, MESSAGE, MIN_INTERVAL, MAX_INTERVAL, CYCLE_WAIT
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r') as f:
                data = json.load(f)
                # 🔥 FIX: যদি পুরনো ডাটায় 'accounts' না থাকে তাহলে খালি ডাটা ব্যবহার করো
                if 'accounts' in data:
                    accounts_data = data.get('accounts', {})
                else:
                    # পুরনো ফরম্যাটে 'mode' ইত্যাদি থাকলে ignore করো
                    accounts_data = {}
                blocked_users = data.get('blocked_users', [])
                allowed_users = data.get('allowed_users', [])
                settings = data.get('settings', {})
                MESSAGE = settings.get('message', MESSAGE)
                MIN_INTERVAL = settings.get('min_interval', MIN_INTERVAL)
                MAX_INTERVAL = settings.get('max_interval', MAX_INTERVAL)
                CYCLE_WAIT = settings.get('cycle_wait', CYCLE_WAIT)
                return data
        except Exception as e:
            logger.error(f"Data load error: {e}")
            # ফাইল corrupted হলে নতুন তৈরি করো
            save_data()
    return {'accounts': {}, 'settings': {}, 'blocked_users': [], 'allowed_users': []}


def save_data():
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
# ডিফল্ট সেটিংস
# ============================================================

MESSAGE = "𝟭𝟬 𝗠𝗜𝗡 𝗩𝗖 ₹𝟰𝟵 𝗕𝗔𝗕𝗬😘"
MIN_INTERVAL = 3
MAX_INTERVAL = 7
CYCLE_WAIT = 60
EXCLUDED_GROUPS = ["Admin Group", "Private Chat"]


# ============================================================
# ইউজার চেক ফাংশন
# ============================================================

async def is_user_allowed(user_id):
    if user_id == OWNER_ID:
        return True
    if user_id in blocked_users:
        return False
    if not allowed_users:
        return True
    return user_id in allowed_users


# ============================================================
# বট কমান্ড হ্যান্ডলার
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
        await update.message.reply_text(
            f"👋 স্বাগতম {user.first_name}!\n\n"
            "আপনি এই বটের মাধ্যমে ম্যাসেজিং সার্ভিস ব্যবহার করতে পারেন।",
            reply_markup=keyboard
        )
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
        "🤖 *ম্যাসেজিং বট কন্ট্রোল প্যানেল*\n\n"
        "আপনি কি করতে চান? নিচের বাটন ব্যবহার করুন:",
        parse_mode='Markdown',
        reply_markup=keyboard
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    if not await is_user_allowed(user_id):
        await query.edit_message_text("❌ আপনার অনুমতি নেই!")
        return
    
    data = query.data
    
    if data == 'user_status':
        await show_user_status(query)
        return
    
    if user_id != OWNER_ID:
        return
    
    if data == 'accounts':
        await show_accounts(query)
    
    elif data == 'add_account':
        await query.edit_message_text(
            "📱 *নতুন অ্যাকাউন্ট যোগ করুন*\n\n"
            "দয়া করে নিচের ফরম্যাটে ইনফো পাঠান:\n\n"
            "`সেশন_নেম,API_ID,API_HASH`\n\n"
            "উদাহরণ: `acc1,123456,abc123def456`\n\n"
            "অথবা 'বাতিল' লিখুন।",
            parse_mode='Markdown'
        )
        context.user_data['awaiting_input'] = 'add_account'
    
    elif data.startswith('view_'):
        session = data.replace('view_', '')
        await view_account(query, session)
    
    elif data.startswith('delete_'):
        session = data.replace('delete_', '')
        await delete_account(query, session)
    
    elif data.startswith('toggle_'):
        session = data.replace('toggle_', '')
        await toggle_account(query, session)
    
    elif data == 'settings':
        await show_settings(query)
    
    elif data == 'edit_message':
        await query.edit_message_text(
            f"✏️ *ম্যাসেজ সেট করুন*\n\n"
            f"আপনার নতুন ম্যাসেজ টেক্সট লিখুন:\n\n"
            f"বর্তমান: `{MESSAGE}`",
            parse_mode='Markdown'
        )
        context.user_data['awaiting_input'] = 'edit_message'
    
    elif data == 'edit_interval':
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"📉 মিনিমাম ({MIN_INTERVAL}s)", callback_data='set_min')],
            [InlineKeyboardButton(f"📈 ম্যাক্সিমাম ({MAX_INTERVAL}s)", callback_data='set_max')],
            [InlineKeyboardButton(f"🔄 সাইকেল ওয়েট ({CYCLE_WAIT}s)", callback_data='set_cycle')],
            [InlineKeyboardButton("🔙 ফিরে যান", callback_data='settings')]
        ])
        await query.edit_message_text(
            "⚙️ *ইন্টারভাল সেটিংস*\n\n"
            f"বর্তমান:\n"
            f"• মিনিমাম: `{MIN_INTERVAL}` সেকেন্ড\n"
            f"• ম্যাক্সিমাম: `{MAX_INTERVAL}` সেকেন্ড\n"
            f"• সাইকেল ওয়েট: `{CYCLE_WAIT}` সেকেন্ড\n\n"
            "কোনটি পরিবর্তন করতে চান?",
            parse_mode='Markdown',
            reply_markup=keyboard
        )
    
    elif data == 'set_min':
        context.user_data['awaiting_input'] = 'set_min'
        await query.edit_message_text(
            f"✏️ *মিনিমাম ইন্টারভাল*\n\n"
            f"বর্তমান মান: `{MIN_INTERVAL}` সেকেন্ড\n"
            f"ম্যাক্সিমাম: `{MAX_INTERVAL}` সেকেন্ড\n\n"
            f"নতুন মান (সেকেন্ড) লিখুন:",
            parse_mode='Markdown'
        )
    
    elif data == 'set_max':
        context.user_data['awaiting_input'] = 'set_max'
        await query.edit_message_text(
            f"✏️ *ম্যাক্সিমাম ইন্টারভাল*\n\n"
            f"বর্তমান মান: `{MAX_INTERVAL}` সেকেন্ড\n"
            f"মিনিমাম: `{MIN_INTERVAL}` সেকেন্ড\n\n"
            f"নতুন মান (সেকেন্ড) লিখুন:",
            parse_mode='Markdown'
        )
    
    elif data == 'set_cycle':
        context.user_data['awaiting_input'] = 'set_cycle'
        await query.edit_message_text(
            f"✏️ *সাইকেল ওয়েট*\n\n"
            f"বর্তমান মান: `{CYCLE_WAIT}` সেকেন্ড\n\n"
            f"নতুন মান (সেকেন্ড) লিখুন:",
            parse_mode='Markdown'
        )
    
    elif data == 'start_all':
        await start_all_accounts(query)
    
    elif data == 'stop_all':
        await stop_all_accounts(query)
    
    elif data == 'status':
        await show_status(query)
    
    elif data == 'user_manage':
        await show_user_management(query)
    
    elif data == 'add_blocked_user':
        await query.edit_message_text(
            "🔒 *ব্লক করতে ইউজার আইডি দিন*\n\n"
            "যে ইউজারকে ব্লক করতে চান তার টেলিগ্রাম আইডি লিখুন:\n\n"
            "শুধু সংখ্যা দিন (যেমন: `123456789`)",
            parse_mode='Markdown'
        )
        context.user_data['awaiting_input'] = 'add_blocked'
    
    elif data == 'add_allowed_user':
        await query.edit_message_text(
            "✅ *অনুমতি দিতে ইউজার আইডি দিন*\n\n"
            "যে ইউজারকে অনুমতি দিতে চান তার টেলিগ্রাম আইডি লিখুন:\n\n"
            "শুধু সংখ্যা দিন (যেমন: `123456789`)",
            parse_mode='Markdown'
        )
        context.user_data['awaiting_input'] = 'add_allowed'
    
    elif data == 'remove_blocked_user':
        await query.edit_message_text(
            "🔓 *ব্লক তালিকা থেকে সরাতে ইউজার আইডি দিন*\n\n"
            "যে ইউজারকে আনব্লক করতে চান তার আইডি লিখুন:\n\n"
            "শুধু সংখ্যা দিন (যেমন: `123456789`)",
            parse_mode='Markdown'
        )
        context.user_data['awaiting_input'] = 'remove_blocked'
    
    elif data == 'remove_allowed_user':
        await query.edit_message_text(
            "❌ *অনুমতি তালিকা থেকে সরাতে ইউজার আইডি দিন*\n\n"
            "যে ইউজারকে সরাতে চান তার আইডি লিখুন:\n\n"
            "শুধু সংখ্যা দিন (যেমন: `123456789`)",
            parse_mode='Markdown'
        )
        context.user_data['awaiting_input'] = 'remove_allowed'
    
    elif data == 'toggle_mode':
        if allowed_users:
            allowed_users.clear()
            save_data()
            await query.answer("✅ এখন সবাই বট ব্যবহার করতে পারবে!")
        else:
            if OWNER_ID not in allowed_users:
                allowed_users.append(OWNER_ID)
            save_data()
            await query.answer("✅ শুধু অনুমতিপ্রাপ্ত ইউজাররাই ব্যবহার করতে পারবে!")
        
        await show_user_management(query)
    
    elif data == 'back':
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("👥 অ্যাকাউন্ট ম্যানেজ", callback_data='accounts')],
            [InlineKeyboardButton("⚙️ সেটিংস", callback_data='settings')],
            [InlineKeyboardButton("🔒 ইউজার ম্যানেজমেন্ট", callback_data='user_manage')],
            [InlineKeyboardButton("▶️ সব চালু করুন", callback_data='start_all')],
            [InlineKeyboardButton("⏹️ সব বন্ধ করুন", callback_data='stop_all')],
            [InlineKeyboardButton("📊 স্ট্যাটাস", callback_data='status')]
        ])
        await query.edit_message_text(
            "🤖 *ম্যাসেজিং বট কন্ট্রোল প্যানেল*\n\n"
            "আপনি কি করতে চান?",
            parse_mode='Markdown',
            reply_markup=keyboard
        )


async def show_user_status(query):
    await query.edit_message_text(
        "📊 *বট স্ট্যাটাস*\n\n"
        "বটটি সক্রিয় আছে এবং কাজ করছে।\n"
        "বিস্তারিত জানতে ওনারকে যোগাযোগ করুন।",
        parse_mode='Markdown'
    )


async def show_accounts(query):
    if not accounts_data:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ নতুন অ্যাকাউন্ট যোগ করুন", callback_data='add_account')],
            [InlineKeyboardButton("🔙 ফিরে যান", callback_data='back')]
        ])
        await query.edit_message_text(
            "📭 *কোন অ্যাকাউন্ট নেই!*\n\n"
            "নিচের বাটনে ক্লিক করে নতুন অ্যাকাউন্ট যোগ করুন:",
            parse_mode='Markdown',
            reply_markup=keyboard
        )
        return
    
    text = "👥 *আপনার অ্যাকাউন্ট:*\n\n"
    keyboard = []
    
    for session_name in accounts_data:
        is_running = session_name in running_tasks and running_tasks[session_name] is not None and not running_tasks[session_name].done()
        icon = "🟢" if is_running else "🔴"
        status = "✅ চলছে" if is_running else "⏹️ বন্ধ"
        text += f"• {icon} `{session_name}` — {status}\n"
        keyboard.append([InlineKeyboardButton(
            f"{icon} {session_name}",
            callback_data=f'view_{session_name}'
        )])
    
    keyboard.append([InlineKeyboardButton("➕ নতুন অ্যাকাউন্ট যোগ করুন", callback_data='add_account')])
    keyboard.append([InlineKeyboardButton("🔙 ফিরে যান", callback_data='back')])
    
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))


async def view_account(query, session_name):
    if session_name not in accounts_data:
        await query.edit_message_text("❌ অ্যাকাউন্ট পাওয়া যায়নি!")
        return
    
    acc = accounts_data[session_name]
    is_running = session_name in running_tasks and running_tasks[session_name] is not None and not running_tasks[session_name].done()
    status = "✅ চালু" if is_running else "⏹️ বন্ধ"
    
    text = (
        f"📱 *অ্যাকাউন্ট: {session_name}*\n\n"
        f"• স্ট্যাটাস: {status}\n"
        f"• API ID: `{acc['api_id']}`\n"
        f"• API HASH: `{acc['api_hash'][:10]}...`\n\n"
        f"কি করতে চান?"
    )
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("▶️ চালু করুন" if not is_running else "⏹️ বন্ধ করুন", callback_data=f'toggle_{session_name}')],
        [InlineKeyboardButton("🗑️ ডিলিট করুন", callback_data=f'delete_{session_name}')],
        [InlineKeyboardButton("🔙 ফিরে যান", callback_data='accounts')]
    ])
    
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=keyboard)


async def delete_account(query, session_name):
    if session_name in running_tasks and running_tasks[session_name] is not None and not running_tasks[session_name].done():
        running_tasks[session_name].cancel()
        del running_tasks[session_name]
    
    if session_name in accounts_data:
        del accounts_data[session_name]
        save_data()
    
    session_file = f"{SESSIONS_DIR}/{session_name}.session"
    if os.path.exists(session_file):
        os.remove(session_file)
    
    await query.answer("✅ অ্যাকাউন্ট ডিলিট করা হয়েছে!")
    await show_accounts(query)


async def toggle_account(query, session_name):
    if session_name in running_tasks and running_tasks[session_name] is not None and not running_tasks[session_name].done():
        running_tasks[session_name].cancel()
        del running_tasks[session_name]
        await query.answer("⏹️ বন্ধ করা হয়েছে!")
    else:
        task = asyncio.create_task(run_account(session_name))
        running_tasks[session_name] = task
        await query.answer("▶️ চালু করা হয়েছে!")
    
    await view_account(query, session_name)


async def show_settings(query):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ ম্যাসেজ পরিবর্তন করুন", callback_data='edit_message')],
        [InlineKeyboardButton("⏱️ ইন্টারভাল সেটিংস", callback_data='edit_interval')],
        [InlineKeyboardButton("🔙 ফিরে যান", callback_data='back')]
    ])
    
    await query.edit_message_text(
        "⚙️ *বর্তমান সেটিংস:*\n\n"
        f"📝 ম্যাসেজ: `{MESSAGE}`\n"
        f"⏱️ মিনিমাম: `{MIN_INTERVAL}` সেকেন্ড\n"
        f"⏱️ ম্যাক্সিমাম: `{MAX_INTERVAL}` সেকেন্ড\n"
        f"🔄 সাইকেল ওয়েট: `{CYCLE_WAIT}` সেকেন্ড\n\n"
        "কি পরিবর্তন করতে চান?",
        parse_mode='Markdown',
        reply_markup=keyboard
    )


async def show_user_management(query):
    mode_text = "🔓 সবাই ব্যবহার করতে পারে" if not allowed_users else "🔒 শুধু অনুমতিপ্রাপ্ত ইউজার"
    
    text = (
        "🔒 *ইউজার ম্যানেজমেন্ট*\n\n"
        f"বর্তমান মোড: {mode_text}\n\n"
        "**ব্লক করা ইউজার:**\n"
    )
    
    if blocked_users:
        for uid in blocked_users:
            text += f"• ❌ `{uid}`\n"
    else:
        text += "• কেউ নেই\n"
    
    text += "\n**অনুমতিপ্রাপ্ত ইউজার:**\n"
    if allowed_users:
        for uid in allowed_users:
            marker = "👑 (Owner)" if uid == OWNER_ID else ""
            text += f"• ✅ `{uid}` {marker}\n"
    else:
        text += "• সবাই (কোন সীমা নেই)\n"
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔒 ইউজার ব্লক করুন", callback_data='add_blocked_user')],
        [InlineKeyboardButton("🔓 আনব্লক করুন", callback_data='remove_blocked_user')],
        [InlineKeyboardButton("✅ ইউজার অনুমতি দিন", callback_data='add_allowed_user')],
        [InlineKeyboardButton("❌ অনুমতি সরান", callback_data='remove_allowed_user')],
        [InlineKeyboardButton("🔄 মোড পরিবর্তন (সবাই/শুধু অনুমতি)", callback_data='toggle_mode')],
        [InlineKeyboardButton("🔙 ফিরে যান", callback_data='back')]
    ])
    
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=keyboard)


async def start_all_accounts(query):
    if not accounts_data:
        await query.edit_message_text("❌ কোনো অ্যাকাউন্ট নেই! আগে অ্যাকাউন্ট যোগ করুন।")
        return
    
    count = 0
    for session_name in accounts_data:
        is_running = session_name in running_tasks and running_tasks[session_name] is not None and not running_tasks[session_name].done()
        if not is_running:
            task = asyncio.create_task(run_account(session_name))
            running_tasks[session_name] = task
            count += 1
    
    await query.answer(f"✅ {count} টি অ্যাকাউন্ট চালু করা হয়েছে!")
    await query.edit_message_text(f"✅ *{count}* টি অ্যাকাউন্ট চালু করা হয়েছে!\n\nস্ট্যাটাস দেখতে /start দিন।", parse_mode='Markdown')


async def stop_all_accounts(query):
    count = 0
    for session_name in list(running_tasks.keys()):
        if running_tasks[session_name] is not None and not running_tasks[session_name].done():
            running_tasks[session_name].cancel()
            del running_tasks[session_name]
            count += 1
    
    await query.answer(f"⏹️ {count} টি অ্যাকাউন্ট বন্ধ করা হয়েছে!")
    await query.edit_message_text(f"⏹️ *{count}* টি অ্যাকাউন্ট বন্ধ করা হয়েছে!", parse_mode='Markdown')


async def show_status(query):
    text = "📊 *স্ট্যাটাস রিপোর্ট*\n\n"
    
    if not accounts_data:
        text += "❌ কোনো অ্যাকাউন্ট নেই।\n"
    else:
        running = 0
        for session_name in accounts_data:
            is_running = session_name in running_tasks and running_tasks[session_name] is not None and not running_tasks[session_name].done()
            status = "✅ চলছে" if is_running else "⏹️ বন্ধ"
            text += f"• `{session_name}` — {status}\n"
            if is_running:
                running += 1
        
        text += f"\nমোট: {len(accounts_data)} | চলছে: {running} | বন্ধ: {len(accounts_data) - running}"
    
    text += f"\n\n📝 ম্যাসেজ: `{MESSAGE}`"
    text += f"\n⏱️ ইন্টারভাল: `{MIN_INTERVAL}`-`{MAX_INTERVAL}` সেকেন্ড"
    text += f"\n🔄 সাইকেল: প্রতি `{CYCLE_WAIT}` সেকেন্ড"
    
    mode_text = "🔓 সবাই" if not allowed_users else "🔒 শুধু অনুমতিপ্রাপ্ত"
    text += f"\n👥 ইউজার মোড: {mode_text}"
    text += f"\n🔒 ব্লককৃত: {len(blocked_users)} জন"
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 রিফ্রেশ", callback_data='status')],
        [InlineKeyboardButton("🔙 ফিরে যান", callback_data='back')]
    ])
    
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=keyboard)


# ============================================================
# টেক্সট ইনপুট হ্যান্ডলার
# ============================================================

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not await is_user_allowed(user_id):
        return
    
    text = update.message.text.strip()
    awaiting = context.user_data.get('awaiting_input')
    
    if not awaiting:
        return
    
    if user_id != OWNER_ID and awaiting in ['add_account', 'edit_message', 'set_min', 'set_max', 'set_cycle', 'add_blocked', 'add_allowed', 'remove_blocked', 'remove_allowed']:
        return
    
    global MESSAGE, MIN_INTERVAL, MAX_INTERVAL, CYCLE_WAIT
    
    if awaiting == 'add_account':
        if text.lower() == 'বাতিল':
            context.user_data['awaiting_input'] = None
            await update.message.reply_text("✅ বাতিল করা হয়েছে। /start দিন")
            return
        
        parts = text.split(',')
        if len(parts) != 3:
            await update.message.reply_text(
                "❌ ভুল ফরম্যাট! সঠিক ফরম্যাট:\n"
                "`সেশন_নেম,API_ID,API_HASH`\n\n"
                "উদাহরণ: `acc1,123456,abc123def456`"
            )
            return
        
        session_name = parts[0].strip()
        api_id = parts[1].strip()
        api_hash = parts[2].strip()
        
        if not api_id.isdigit():
            await update.message.reply_text("❌ API_ID অবশ্যই সংখ্যা হতে হবে!")
            return
        
        accounts_data[session_name] = {
            'api_id': int(api_id),
            'api_hash': api_hash
        }
        
        os.makedirs(SESSIONS_DIR, exist_ok=True)
        save_data()
        context.user_data['awaiting_input'] = None
        
        await update.message.reply_text(
            f"✅ *অ্যাকাউন্ট যোগ করা হয়েছে!*\n\n"
            f"নাম: `{session_name}`\n"
            f"API ID: `{api_id}`\n"
            f"API HASH: `{api_hash[:8]}...`\n\n"
            f"/start দিন দেখতে।",
            parse_mode='Markdown'
        )
    
    elif awaiting == 'edit_message':
        MESSAGE = text
        save_data()
        context.user_data['awaiting_input'] = None
        await update.message.reply_text(
            f"✅ *ম্যাসেজ আপডেট করা হয়েছে!*\n\nনতুন ম্যাসেজ:\n`{MESSAGE}`",
            parse_mode='Markdown'
        )
    
    elif awaiting in ['set_min', 'set_max', 'set_cycle']:
        if not text.isdigit() or int(text) < 1:
            await update.message.reply_text("❌ দয়া করে একটি বৈধ সংখ্যা দিন (১ বা তার বেশি)!")
            return
        
        value = int(text)
        
        if awaiting == 'set_min':
            if value >= MAX_INTERVAL:
                await update.message.reply_text(f"❌ মিনিমাম ম্যাক্সিমামের ({MAX_INTERVAL}) চেয়ে কম হতে হবে!")
                return
            MIN_INTERVAL = value
        elif awaiting == 'set_max':
            if value <= MIN_INTERVAL:
                await update.message.reply_text(f"❌ ম্যাক্সিমাম মিনিমামের ({MIN_INTERVAL}) চেয়ে বেশি হতে হবে!")
                return
            MAX_INTERVAL = value
        elif awaiting == 'set_cycle':
            CYCLE_WAIT = value
        
        save_data()
        context.user_data['awaiting_input'] = None
        
        names = {'set_min': 'মিনিমাম ইন্টারভাল', 'set_max': 'ম্যাক্সিমাম ইন্টারভাল', 'set_cycle': 'সাইকেল ওয়েট'}
        await update.message.reply_text(
            f"✅ *{names[awaiting]} আপডেট করা হয়েছে!*\n\nনতুন মান: `{value}` সেকেন্ড",
            parse_mode='Markdown'
        )
    
    elif awaiting == 'add_blocked':
        if not text.isdigit():
            await update.message.reply_text("❌ শুধু সংখ্যা দিন!")
            return
        
        uid = int(text)
        if uid == OWNER_ID:
            await update.message.reply_text("❌ ওনারকে ব্লক করা যাবে না!")
            return
        
        if uid in blocked_users:
            await update.message.reply_text(f"✅ `{uid}` ইতিমধ্যে ব্লক করা আছে!")
        else:
            blocked_users.append(uid)
            save_data()
            await update.message.reply_text(f"🔒 ✅ `{uid}` ব্লক করা হয়েছে!")
        
        context.user_data['awaiting_input'] = None

    elif awaiting == 'add_allowed':
        if not text.isdigit():
            await update.message.reply_text("❌ শুধু সংখ্যা দিন!")
            return
        
        uid = int(text)
        
        if uid in allowed_users:
            await update.message.reply_text(f"✅ `{uid}` ইতিমধ্যে অনুমতিপ্রাপ্ত!")
        else:
            allowed_users.append(uid)
            save_data()
            await update.message.reply_text(f"✅ ✅ `{uid}` কে অনুমতি দেওয়া হয়েছে!")
        
        context.user_data['awaiting_input'] = None

    elif awaiting == 'remove_blocked':
        if not text.isdigit():
            await update.message.reply_text("❌ শুধু সংখ্যা দিন!")
            return
        
        uid = int(text)
        
        if uid in blocked_users:
            blocked_users.remove(uid)
            save_data()
            await update.message.reply_text(f"🔓 ✅ `{uid}` আনব্লক করা হয়েছে!")
        else:
            await update.message.reply_text(f"❌ `{uid}` ব্লক লিস্টে নেই!")
        
        context.user_data['awaiting_input'] = None

    elif awaiting == 'remove_allowed':
        if not text.isdigit():
            await update.message.reply_text("❌ শুধু সংখ্যা দিন!")
            return
        
        uid = int(text)
        
        if uid == OWNER_ID:
            await update.message.reply_text("❌ ওনারকে সরানো যাবে না!")
            return
        
        if uid in allowed_users:
            allowed_users.remove(uid)
            save_data()
            await update.message.reply_text(f"❌ ✅ `{uid}` কে অনুমতি লিস্ট থেকে সরানো হয়েছে!")
        else:
            await update.message.reply_text(f"❌ `{uid}` অনুমতি লিস্টে নেই!")
        
        context.user_data['awaiting_input'] = None


# ============================================================
# ম্যাসেজ সেন্ডিং ফাংশন (প্রতি অ্যাকাউন্টের জন্য)
# ============================================================

async def run_account(session_name):
    """একটি অ্যাকাউন্ট দিয়ে ম্যাসেজ পাঠানো"""
    if session_name not in accounts_data:
        logger.error(f"Account {session_name} not found in data")
        return
    
    acc = accounts_data[session_name]
    session_path = f"{SESSIONS_DIR}/{session_name}"
    
    client = TelegramClient(session_path, acc['api_id'], acc['api_hash'])
    
    try:
        await client.start()
        logger.info(f"✅ [{session_name}] Login successful")
        
        # গ্রুপ লিস্ট বের করুন
        groups = []
        try:
            dialogues = await client(GetDialogsRequest(
                offset_date=None, offset_id=0,
                offset_peer=InputPeerEmpty(), limit=200, hash=0
            ))
            
            for dialog in dialogues.dialogs:
                try:
                    entity = await client.get_entity(dialog.peer)
                    if hasattr(entity, 'title') and entity.title not in EXCLUDED_GROUPS:
                        groups.append(entity)
                except:
                    continue
            
            logger.info(f"[{session_name}] Found {len(groups)} groups")
        except Exception as e:
            logger.error(f"[{session_name}] Error getting groups: {e}")
            return
        
        if not groups:
            logger.warning(f"[{session_name}] No groups found!")
            return
        
        # মেইন লুপ
        while True:
            logger.info(f"[{session_name}] Starting cycle ({len(groups)} groups)...")
            
            for i, group in enumerate(groups):
                try:
                    title = group.title if hasattr(group, 'title') else str(group)
                    await client.send_message(group, MESSAGE)
                    logger.info(f"[{session_name}] ✅ [{i+1}/{len(groups)}] {title}")
                    
                except FloodWaitError as e:
                    logger.warning(f"[{session_name}] ⏳ Flood wait {e.seconds}s")
                    await asyncio.sleep(e.seconds)
                    
                except Exception as e:
                    logger.error(f"[{session_name}] ❌ Error: {e}")
                
                # র্যান্ডম ডেল
                delay = random.randint(MIN_INTERVAL, MAX_INTERVAL)
                await asyncio.sleep(delay)
            
            logger.info(f"[{session_name}] 🔄 Cycle done. Waiting {CYCLE_WAIT}s...")
            await asyncio.sleep(CYCLE_WAIT)
    
    except Exception as e:
        logger.error(f"[{session_name}] Fatal error: {e}")
    finally:
        await client.disconnect()


# ============================================================
# 🔥 রেন্ডারের জন্য মেইন ফাংশন (Timed Out ফিক্স সহ)
# ============================================================

async def main():
    """বট চালু করুন (Render Timed Out ফিক্স)"""
    global bot_app
    
    print("✅ Bot starting...")
    logger.info("Bot initializing...")
    
    # sessions ফোল্ডার তৈরি করুন
    os.makedirs(SESSIONS_DIR, exist_ok=True)
    
    # আগের ডাটা লোড করুন
    load_data()
    print(f"✅ Loaded {len(accounts_data)} accounts")
    
    # 🔥 প্রথমে পুরনো bot_data.json চেক করুন এবং ক্লিন করুন
    # যদি কোনো পুরনো 'mode' বা 'account' কী থাকে, সেটা রিমুভ করো
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r') as f:
                raw = json.load(f)
            # শুধু valid keys রাখো
            valid_keys = ['accounts', 'blocked_users', 'allowed_users', 'settings']
            cleaned = {k: raw[k] for k in valid_keys if k in raw}
            # যদি 'accounts' না থাকে তাহলে {}
            if 'accounts' not in cleaned:
                cleaned['accounts'] = {}
            with open(DATA_FILE, 'w') as f:
                json.dump(cleaned, f, indent=2)
            # পুনরায় লোড
            load_data()
    except Exception as e:
        logger.warning(f"Data cleanup warning: {e}")
    
    # বট তৈরি করুন
    app = Application.builder().token(BOT_TOKEN).build()
    
    # হ্যান্ডলার যোগ করুন
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    
    bot_app = app
    
    print("✅ Bot is running!")
    logger.info("Bot is now running!")
    
    # 🔥 রেন্ডারের জন্য: start_polling এবং keep alive
    await app.initialize()
    await app.start()
    await app.updater.start_polling(allowed_updates=Update.ALL_TYPES)
    
    # 🔥 Timed Out সমস্যা সমাধান: প্রতি ৫ মিনিটে Render-কে জানাবো যে বট alive
    try:
        while True:
            await asyncio.sleep(300)  # 5 মিনিট
            # Render-এ log print করলে connection alive থাকে
            logger.info("Bot is alive...")
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error(f"Loop error: {e}")
    finally:
        await app.updater.stop()
        await app.stop()
        await app.shutdown()


# ============================================================
# 🔥 এন্ট্রি পয়েন্ট
# ============================================================

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("⛔ Bot stopped by user")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
