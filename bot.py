#!/usr/bin/env python3
# mass_bot.py - Render Optimized (No aiohttp)

import os
import sys
import json
import asyncio
import random
import logging
from datetime import datetime
from telethon import TelegramClient
from telethon.errors import FloodWaitError
from telethon.tl.functions.messages import GetDialogsRequest
from telethon.tl.types import InputPeerEmpty
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# ====== লগিং ======
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# ====== আপনার বট টোকেন ======
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
        if not isinstance(accounts_data, dict):
            accounts_data = {}
        
        blocked_users = data.get('blocked_users', [])
        if not isinstance(blocked_users, list):
            blocked_users = []
        
        allowed_users = data.get('allowed_users', [])
        if not isinstance(allowed_users, list):
            allowed_users = []
        
        settings = data.get('settings', {})
        if not isinstance(settings, dict):
            settings = {}
        
        MESSAGE = settings.get('message', MESSAGE)
        MIN_INTERVAL = settings.get('min_interval', MIN_INTERVAL)
        MAX_INTERVAL = settings.get('max_interval', MAX_INTERVAL)
        CYCLE_WAIT = settings.get('cycle_wait', CYCLE_WAIT)
        
        return data
    except Exception as e:
        logger.warning(f"Data load error, creating fresh: {e}")
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
    if user_id == OWNER_ID:
        return True
    if user_id in blocked_users:
        return False
    if not allowed_users:
        return True
    return user_id in allowed_users


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
        await update.message.reply_text(
            f"👋 স্বাগতম {user.first_name}!",
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
        "🤖 *ম্যাসেজিং বট কন্ট্রোল প্যানেল*",
        parse_mode='Markdown',
        reply_markup=keyboard
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    if not await is_user_allowed(user_id):
        return
    
    data = query.data
    
    if data == 'user_status':
        await query.edit_message_text("📊 বট সক্রিয় আছে। বিস্তারিত জানতে ওনারকে যোগাযোগ করুন।")
        return
    
    if user_id != OWNER_ID:
        return
    
    if data == 'accounts':
        await show_accounts(query)
    elif data == 'add_account':
        context.user_data['awaiting_input'] = 'add_account'
        await query.edit_message_text(
            "📱 ফরম্যাট: `সেশন_নেম,API_ID,API_HASH`\nউদাহরণ: `acc1,123456,abc123`\n\n'বাতিল' লিখুন বাতিল করতে।",
            parse_mode='Markdown'
        )
    elif data.startswith('view_'):
        await view_account(query, data.replace('view_', ''))
    elif data.startswith('delete_'):
        await delete_account(query, data.replace('delete_', ''))
    elif data.startswith('toggle_'):
        await toggle_account(query, data.replace('toggle_', ''))
    elif data == 'settings':
        await show_settings(query)
    elif data == 'edit_message':
        context.user_data['awaiting_input'] = 'edit_message'
        await query.edit_message_text(f"✏️ নতুন ম্যাসেজ লিখুন:\nবর্তমান: `{MESSAGE}`", parse_mode='Markdown')
    elif data == 'edit_interval':
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"📉 মিনিমাম ({MIN_INTERVAL}s)", callback_data='set_min')],
            [InlineKeyboardButton(f"📈 ম্যাক্সিমাম ({MAX_INTERVAL}s)", callback_data='set_max')],
            [InlineKeyboardButton(f"🔄 সাইকেল ({CYCLE_WAIT}s)", callback_data='set_cycle')],
            [InlineKeyboardButton("🔙 ফিরে যান", callback_data='settings')]
        ])
        await query.edit_message_text("⚙️ *ইন্টারভাল সেটিংস*", parse_mode='Markdown', reply_markup=keyboard)
    elif data in ['set_min', 'set_max', 'set_cycle']:
        context.user_data['awaiting_input'] = data
        labels = {'set_min': f'মিনিমাম ({MIN_INTERVAL}s)', 'set_max': f'ম্যাক্সিমাম ({MAX_INTERVAL}s)', 'set_cycle': f'সাইকেল ({CYCLE_WAIT}s)'}
        await query.edit_message_text(f"✏️ {labels[data]} - নতুন মান (সেকেন্ড) লিখুন:")
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
            'add_blocked_user': 'ব্লক করতে ইউজার আইডি দিন:',
            'add_allowed_user': 'অনুমতি দিতে ইউজার আইডি দিন:',
            'remove_blocked_user': 'আনব্লক করতে ইউজার আইডি দিন:',
            'remove_allowed_user': 'অনুমতি সরাতে ইউজার আইডি দিন:'
        }
        context.user_data['awaiting_input'] = data
        await query.edit_message_text(f"🔒 {labels[data]}")
    elif data == 'toggle_mode':
        if allowed_users:
            allowed_users.clear()
        else:
            if OWNER_ID not in allowed_users:
                allowed_users.append(OWNER_ID)
        save_data()
        await query.answer("✅ মোড পরিবর্তন করা হয়েছে!")
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
        await query.edit_message_text("🤖 *ম্যাসেজিং বট কন্ট্রোল প্যানেল*", parse_mode='Markdown', reply_markup=keyboard)


async def show_accounts(query):
    if not accounts_data:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ অ্যাকাউন্ট যোগ করুন", callback_data='add_account')],
            [InlineKeyboardButton("🔙 ফিরে যান", callback_data='back')]
        ])
        await query.edit_message_text("📭 *কোন অ্যাকাউন্ট নেই!*", parse_mode='Markdown', reply_markup=keyboard)
        return
    
    text = "👥 *আপনার অ্যাকাউন্ট:*\n"
    keyboard = []
    for sn in accounts_data:
        is_running = sn in running_tasks and not running_tasks[sn].done()
        icon = "🟢" if is_running else "🔴"
        text += f"\n{icon} `{sn}`"
        keyboard.append([InlineKeyboardButton(f"{icon} {sn}", callback_data=f'view_{sn}')])
    
    keyboard.append([InlineKeyboardButton("➕ অ্যাকাউন্ট যোগ করুন", callback_data='add_account')])
    keyboard.append([InlineKeyboardButton("🔙 ফিরে যান", callback_data='back')])
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))


async def view_account(query, session_name):
    if session_name not in accounts_data:
        await query.edit_message_text("❌ পাওয়া যায়নি!")
        return
    
    acc = accounts_data[session_name]
    is_running = session_name in running_tasks and not running_tasks[session_name].done()
    
    text = (
        f"📱 *{session_name}*\n"
        f"স্ট্যাটাস: {'✅ চালু' if is_running else '⏹️ বন্ধ'}\n"
        f"API ID: `{acc['api_id']}`\n"
        f"API HASH: `{acc['api_hash'][:8]}...`"
    )
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("⏹️ বন্ধ করুন" if is_running else "▶️ চালু করুন", callback_data=f'toggle_{session_name}')],
        [InlineKeyboardButton("🗑️ ডিলিট", callback_data=f'delete_{session_name}')],
        [InlineKeyboardButton("🔙 ফিরে যান", callback_data='accounts')]
    ])
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=keyboard)


async def delete_account(query, session_name):
    if session_name in running_tasks and not running_tasks[session_name].done():
        running_tasks[session_name].cancel()
        del running_tasks[session_name]
    
    if session_name in accounts_data:
        del accounts_data[session_name]
        save_data()
    
    sf = f"{SESSIONS_DIR}/{session_name}.session"
    if os.path.exists(sf):
        os.remove(sf)
    
    await query.answer("✅ ডিলিট!")
    await show_accounts(query)


async def toggle_account(query, session_name):
    if session_name in running_tasks and not running_tasks[session_name].done():
        running_tasks[session_name].cancel()
        del running_tasks[session_name]
        await query.answer("⏹️ বন্ধ!")
    else:
        task = asyncio.create_task(run_account(session_name))
        running_tasks[session_name] = task
        await query.answer("▶️ চালু!")
    
    await view_account(query, session_name)


async def show_settings(query):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ ম্যাসেজ", callback_data='edit_message')],
        [InlineKeyboardButton("⏱️ ইন্টারভাল", callback_data='edit_interval')],
        [InlineKeyboardButton("🔙 ফিরে যান", callback_data='back')]
    ])
    await query.edit_message_text(
        f"⚙️ *সেটিংস:*\n📝 `{MESSAGE}`\n⏱️ `{MIN_INTERVAL}`-`{MAX_INTERVAL}`s | 🔄 `{CYCLE_WAIT}`s",
        parse_mode='Markdown', reply_markup=keyboard
    )


async def show_user_management(query):
    mode = "🔓 সবাই" if not allowed_users else "🔒 শুধু অনুমতিপ্রাপ্ত"
    text = f"🔒 *ইউজার ম্যানেজমেন্ট*\nমোড: {mode}\n\n🚫 ব্লক: "
    text += ', '.join(f'`{u}`' for u in blocked_users) if blocked_users else 'কেউ নেই'
    text += "\n\n✅ অনুমতি: "
    text += ', '.join(f'`{u}`' for u in allowed_users) if allowed_users else 'সবাই'
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔒 ব্লক", callback_data='add_blocked_user'),
         InlineKeyboardButton("🔓 আনব্লক", callback_data='remove_blocked_user')],
        [InlineKeyboardButton("✅ অনুমতি দিন", callback_data='add_allowed_user'),
         InlineKeyboardButton("❌ অনুমতি সরান", callback_data='remove_allowed_user')],
        [InlineKeyboardButton("🔄 মোড পরিবর্তন", callback_data='toggle_mode')],
        [InlineKeyboardButton("🔙 ফিরে যান", callback_data='back')]
    ])
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=keyboard)


async def start_all_accounts(query):
    if not accounts_data:
        await query.edit_message_text("❌ কোনো অ্যাকাউন্ট নেই!")
        return
    
    c = 0
    for sn in accounts_data:
        if sn not in running_tasks or running_tasks[sn].done():
            running_tasks[sn] = asyncio.create_task(run_account(sn))
            c += 1
    await query.answer(f"✅ {c} চালু!")
    await query.edit_message_text(f"✅ {c} টি অ্যাকাউন্ট চালু!")


async def stop_all_accounts(query):
    c = 0
    for sn in list(running_tasks.keys()):
        if not running_tasks[sn].done():
            running_tasks[sn].cancel()
            del running_tasks[sn]
            c += 1
    await query.answer(f"⏹️ {c} বন্ধ!")
    await query.edit_message_text(f"⏹️ {c} টি অ্যাকাউন্ট বন্ধ!")


async def show_status(query):
    text = "📊 *স্ট্যাটাস*\n"
    if not accounts_data:
        text += "\n❌ কোনো অ্যাকাউন্ট নেই"
    else:
        r = 0
        for sn in accounts_data:
            ok = sn in running_tasks and not running_tasks[sn].done()
            text += f"\n{'🟢' if ok else '🔴'} `{sn}`"
            if ok: r += 1
        text += f"\n\nমোট: {len(accounts_data)} | চলছে: {r}"
    
    text += f"\n\n📝 `{MESSAGE}`\n⏱️ `{MIN_INTERVAL}`-`{MAX_INTERVAL}`s\n🔄 `{CYCLE_WAIT}`s"
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 রিফ্রেশ", callback_data='status')],
        [InlineKeyboardButton("🔙 ফিরে যান", callback_data='back')]
    ])
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=keyboard)


# ============================================================
# টেক্সট ইনপুট
# ============================================================

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not await is_user_allowed(user_id):
        return
    
    text = update.message.text.strip()
    awaiting = context.user_data.get('awaiting_input')
    if not awaiting:
        return
    
    if user_id != OWNER_ID:
        return
    
    global MESSAGE, MIN_INTERVAL, MAX_INTERVAL, CYCLE_WAIT
    
    if awaiting == 'add_account':
        if text.lower() == 'বাতিল':
            context.user_data['awaiting_input'] = None
            await update.message.reply_text("✅ বাতিল")
            return
        
        parts = text.split(',')
        if len(parts) != 3:
            await update.message.reply_text("❌ ফরম্যাট: `সেশন,API_ID,API_HASH`")
            return
        
        sn, aid, ah = parts[0].strip(), parts[1].strip(), parts[2].strip()
        if not aid.isdigit():
            await update.message.reply_text("❌ API_ID সংখ্যা হতে হবে!")
            return
        
        accounts_data[sn] = {'api_id': int(aid), 'api_hash': ah}
        os.makedirs(SESSIONS_DIR, exist_ok=True)
        save_data()
        context.user_data['awaiting_input'] = None
        await update.message.reply_text(f"✅ `{sn}` যোগ করা হয়েছে!", parse_mode='Markdown')
    
    elif awaiting == 'edit_message':
        MESSAGE = text
        save_data()
        context.user_data['awaiting_input'] = None
        await update.message.reply_text(f"✅ ম্যাসেজ আপডেট!\n`{MESSAGE}`", parse_mode='Markdown')
    
    elif awaiting in ['set_min', 'set_max', 'set_cycle']:
        if not text.isdigit() or int(text) < 1:
            await update.message.reply_text("❌ বৈধ সংখ্যা দিন!")
            return
        v = int(text)
        if awaiting == 'set_min' and v >= MAX_INTERVAL:
            await update.message.reply_text(f"❌ মিনিমাম {MAX_INTERVAL} এর কম হতে হবে!")
            return
        if awaiting == 'set_max' and v <= MIN_INTERVAL:
            await update.message.reply_text(f"❌ ম্যাক্সিমাম {MIN_INTERVAL} এর বেশি হতে হবে!")
            return
        
        if awaiting == 'set_min': MIN_INTERVAL = v
        elif awaiting == 'set_max': MAX_INTERVAL = v
        elif awaiting == 'set_cycle': CYCLE_WAIT = v
        
        save_data()
        context.user_data['awaiting_input'] = None
        await update.message.reply_text(f"✅ আপডেট! নতুন মান: `{v}`s", parse_mode='Markdown')

    elif awaiting == 'add_blocked_user':
        if not text.isdigit(): return await update.message.reply_text("❌ সংখ্যা দিন!")
        uid = int(text)
        if uid == OWNER_ID: return await update.message.reply_text("❌ ওনারকে ব্লক করা যাবে না!")
        if uid not in blocked_users:
            blocked_users.append(uid)
            save_data()
        await update.message.reply_text(f"🔒 `{uid}` ব্লক করা হয়েছে!", parse_mode='Markdown')
        context.user_data['awaiting_input'] = None

    elif awaiting == 'add_allowed_user':
        if not text.isdigit(): return await update.message.reply_text("❌ সংখ্যা দিন!")
        uid = int(text)
        if uid not in allowed_users:
            allowed_users.append(uid)
            save_data()
        await update.message.reply_text(f"✅ `{uid}` অনুমতি দেওয়া হয়েছে!", parse_mode='Markdown')
        context.user_data['awaiting_input'] = None

    elif awaiting == 'remove_blocked_user':
        if not text.isdigit(): return await update.message.reply_text("❌ সংখ্যা দিন!")
        uid = int(text)
        if uid in blocked_users:
            blocked_users.remove(uid)
            save_data()
        await update.message.reply_text(f"🔓 `{uid}` আনব্লক করা হয়েছে!", parse_mode='Markdown')
        context.user_data['awaiting_input'] = None

    elif awaiting == 'remove_allowed_user':
        if not text.isdigit(): return await update.message.reply_text("❌ সংখ্যা দিন!")
        uid = int(text)
        if uid == OWNER_ID: return await update.message.reply_text("❌ ওনারকে সরানো যাবে না!")
        if uid in allowed_users:
            allowed_users.remove(uid)
            save_data()
        await update.message.reply_text(f"❌ `{uid}` সরানো হয়েছে!", parse_mode='Markdown')
        context.user_data['awaiting_input'] = None


# ============================================================
# ম্যাসেজ সেন্ডিং
# ============================================================

async def run_account(session_name):
    if session_name not in accounts_data:
        return
    
    acc = accounts_data[session_name]
    client = TelegramClient(f"{SESSIONS_DIR}/{session_name}", acc['api_id'], acc['api_hash'])
    
    try:
        await client.start()
        logger.info(f"✅ [{session_name}] Login OK")
        
        groups = []
        try:
            d = await client(GetDialogsRequest(offset_date=None, offset_id=0, offset_peer=InputPeerEmpty(), limit=200, hash=0))
            for dialog in d.dialogs:
                try:
                    e = await client.get_entity(dialog.peer)
                    if hasattr(e, 'title') and e.title not in EXCLUDED_GROUPS:
                        groups.append(e)
                except: pass
        except Exception as e:
            logger.error(f"[{session_name}] Group error: {e}")
            return
        
        if not groups:
            logger.warning(f"[{session_name}] No groups found")
            return
        
        while True:
            logger.info(f"[{session_name}] Cycle {len(groups)} groups")
            for g in groups:
                try:
                    title = g.title if hasattr(g, 'title') else str(g)
                    await client.send_message(g, MESSAGE)
                    logger.info(f"[{session_name}] ✅ {title}")
                except FloodWaitError as e:
                    logger.warning(f"[{session_name}] ⏳ Flood {e.seconds}s")
                    await asyncio.sleep(e.seconds)
                except Exception as e:
                    logger.error(f"[{session_name}] Send error: {e}")
                await asyncio.sleep(random.randint(MIN_INTERVAL, MAX_INTERVAL))
            logger.info(f"[{session_name}] 🔄 Waiting {CYCLE_WAIT}s...")
            await asyncio.sleep(CYCLE_WAIT)
    except Exception as e:
        logger.error(f"[{session_name}] Fatal: {e}")
    finally:
        await client.disconnect()


# ============================================================
# 🔥 মেইন ফাংশন (Render-এর জন্য)
# ============================================================

async def main():
    logger.info("🚀 Starting bot...")
    print("✅ Bot starting...")
    
    os.makedirs(SESSIONS_DIR, exist_ok=True)
    
    # 🔥 পুরনো instance মেরে ফেলার জন্য force restart
    # ফাইল সিস্টেম ক্লিন করুন
    for f in os.listdir('.'):
        if f.endswith('.lock'):
            os.remove(f)
    
    load_data()
    logger.info(f"📊 Loaded {len(accounts_data)} accounts, {len(blocked_users)} blocked, {len(allowed_users)} allowed")
    print(f"✅ Loaded {len(accounts_data)} accounts")
    
    # Bot Application তৈরি করুন
    app = Application.builder().token(BOT_TOKEN).build()
    
    # হ্যান্ডলার যোগ করুন
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    
    # 🔥 গুরুত্বপূর্ণ: Initialize এবং start করুন
    await app.initialize()
    await app.start()
    
    # 🔥 polling শুরু করুন (non-blocking)
    await app.updater.start_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True  # 🔥 আগের pending updates ড্রপ করবে
    )
    
    logger.info("✅ Bot is now running! Press Ctrl+C to stop.")
    print("✅ Bot চালু! টেলিগ্রামে /start দিন।")
    
    # 🔥 Render-কে alive রাখতে periodic log
    try:
        while True:
            await asyncio.sleep(60)  # প্রতি মিনিটে
            logger.debug("Bot alive...")
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error(f"Main loop error: {e}")
    finally:
        logger.info("Shutting down...")
        await app.updater.stop()
        await app.stop()
        await app.shutdown()


# ============================================================
# এন্ট্রি পয়েন্ট
# ============================================================

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("⛔ Bot stopped by user")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}", exc_info=True)
        sys.exit(1)
