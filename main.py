#!/usr/bin/env python3
import sys
import os
import asyncio
import random
import logging
import json
import threading
import httpx
from datetime import datetime
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import FloodWaitError
from telethon.tl.functions.messages import GetDialogsRequest
from telethon.tl.types import InputPeerEmpty
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from flask import Flask

# লগিং
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    force=True,
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

print("=" * 60, flush=True)
print("🤖 BOT STARTING...", flush=True)
print("=" * 60, flush=True)

# ====== Environment Variables ======
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID = int(os.environ.get("OWNER_ID", "0"))

API_ID_1 = int(os.environ.get("API_ID_1", "0"))
API_HASH_1 = os.environ.get("API_HASH_1", "")
SESSION_1 = os.environ.get("SESSION_1", "")

API_ID_2 = int(os.environ.get("API_ID_2", "0"))
API_HASH_2 = os.environ.get("API_HASH_2", "")
SESSION_2 = os.environ.get("SESSION_2", "")

API_ID_3 = int(os.environ.get("API_ID_3", "0"))
API_HASH_3 = os.environ.get("API_HASH_3", "")
SESSION_3 = os.environ.get("SESSION_3", "")

# ====== ডায়নামিক একাউন্টের জন্য ফাইল ======
DYNAMIC_ACCOUNTS_FILE = "dynamic_accounts.json"

MESSAGE = os.environ.get("MESSAGE", "𝟭𝟬 𝗠𝗜𝗡 𝗩𝗖 ₹𝟰𝟱 𝗕𝗔𝗕𝗬😘")
MIN_INTERVAL = int(os.environ.get("MIN_INTERVAL", "5"))
MAX_INTERVAL = int(os.environ.get("MAX_INTERVAL", "8"))
CYCLE_WAIT = int(os.environ.get("CYCLE_WAIT", "30"))
# ===================================

# চেক
print(f"📋 BOT_TOKEN: {'✅' if BOT_TOKEN else '❌'}", flush=True)
print(f"📋 OWNER_ID: {OWNER_ID}", flush=True)

# ==========================================
# শুধুমাত্র Environment থেকে অটো Load হবে
# Add Account অপশন সরানো হয়েছে
# ==========================================
ENV_ACCOUNTS = []
acc_configs = [
    ('acc1', API_ID_1, API_HASH_1, SESSION_1),
    ('acc2', API_ID_2, API_HASH_2, SESSION_2),
    ('acc3', API_ID_3, API_HASH_3, SESSION_3),
]

# Environment থেকে কানেক্ট করে নাম সহ সেভ করবো
async def init_env_accounts():
    """Environment accounts থেকে নাম নিয়ে initialize"""
    for acc_id, api_id, api_hash, session in acc_configs:
        if api_id and api_hash and session:
            try:
                client = TelegramClient(StringSession(session), api_id, api_hash, receive_updates=False)
                await client.start()
                me = await client.get_me()
                name = me.first_name or f"User{me.id}"
                await client.disconnect()
                
                ENV_ACCOUNTS.append({
                    'id': acc_id,
                    'name': name,
                    'api_id': api_id,
                    'api_hash': api_hash,
                    'session': session,
                    'type': 'env'
                })
                print(f"✅ {acc_id}: {name}", flush=True)
            except Exception as e:
                print(f"❌ {acc_id}: {str(e)[:50]}", flush=True)
            await asyncio.sleep(1)

print(f"📊 Environment থেকে একাউন্ট লোড হবে...", flush=True)

if not BOT_TOKEN or not OWNER_ID:
    print("❌ BOT_TOKEN বা OWNER_ID দেওয়া হয়নি!", flush=True)
    sys.exit(1)

# ====== ডায়নামিক একাউন্ট ম্যানেজমেন্ট ======
def load_dynamic_accounts():
    """ডায়নামিক একাউন্ট লোড"""
    if os.path.exists(DYNAMIC_ACCOUNTS_FILE):
        try:
            with open(DYNAMIC_ACCOUNTS_FILE, 'r') as f:
                return json.load(f)
        except:
            return []
    return []

def save_dynamic_accounts(accounts):
    """ডায়নামিক একাউন্ট সেভ"""
    try:
        with open(DYNAMIC_ACCOUNTS_FILE, 'w') as f:
            json.dump(accounts, f, indent=2)
    except Exception as e:
        logger.error(f"সেভ এরর: {e}")

def get_all_accounts():
    """সব একাউন্ট (এনভায়রনমেন্ট + ডায়নামিক)"""
    dynamic = load_dynamic_accounts()
    return ENV_ACCOUNTS + dynamic

def remove_account_by_id(account_id):
    """যেকোনো একাউন্ট ডিলিট (এনভি + ডায়নামিক)"""
    global ENV_ACCOUNTS
    
    # প্রথমে ডায়নামিক থেকে চেক
    accounts = load_dynamic_accounts()
    for i, acc in enumerate(accounts):
        if acc['id'] == account_id:
            accounts.pop(i)
            save_dynamic_accounts(accounts)
            return True
    
    # এনভায়রনমেন্ট থেকে ডিলিট
    for i, acc in enumerate(ENV_ACCOUNTS):
        if acc['id'] == account_id:
            ENV_ACCOUNTS.pop(i)
            return True
    
    return False

def refresh_account_stats():
    """নতুন একাউন্টের জন্য স্ট্যাটাস রিফ্রেশ"""
    for acc in get_all_accounts():
        if acc['id'] not in account_stats:
            account_stats[acc['id']] = {'sent': 0, 'running': False}
            stop_flags[acc['id']] = False
# ==========================================

# গ্লোবাল ভেরিয়েবল
running_tasks = {}
stop_flags = {}
account_clients = {}
account_stats = {}

data_file = "bot_data.json"

# ====== Flask ======
web_app = Flask(__name__)

@web_app.route("/")
def home():
    all_accs = get_all_accounts()
    running_count = sum(1 for acc in all_accs if account_stats.get(acc['id'], {}).get('running', False))
    total_sent = sum(account_stats.get(acc['id'], {}).get('sent', 0) for acc in all_accs)
    return f"✅ Bot Running | Accounts: {len(all_accs)} | Active: {running_count}/{len(all_accs)} | Total Sent: {total_sent}"

@web_app.route("/health")
def health():
    return "OK", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    web_app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
# ================================


def load_data():
    global MESSAGE, MIN_INTERVAL, MAX_INTERVAL, CYCLE_WAIT, account_stats
    if os.path.exists(data_file):
        try:
            with open(data_file, 'r') as f:
                d = json.load(f)
                MESSAGE = d.get('message', MESSAGE)
                MIN_INTERVAL = d.get('min_interval', MIN_INTERVAL)
                MAX_INTERVAL = d.get('max_interval', MAX_INTERVAL)
                CYCLE_WAIT = d.get('cycle_wait', CYCLE_WAIT)
                saved_stats = d.get('stats', {})
                for acc in get_all_accounts():
                    if acc['id'] in saved_stats:
                        account_stats[acc['id']]['sent'] = saved_stats[acc['id']].get('sent', 0)
        except:
            pass

def save_data():
    data = {
        'message': MESSAGE,
        'min_interval': MIN_INTERVAL,
        'max_interval': MAX_INTERVAL,
        'cycle_wait': CYCLE_WAIT,
        'stats': {acc['id']: {'sent': account_stats.get(acc['id'], {}).get('sent', 0)} for acc in get_all_accounts()}
    }
    try:
        with open(data_file, 'w') as f:
            json.dump(data, f, indent=2)
    except:
        pass


async def get_client(api_id, api_hash, session_string):
    client = TelegramClient(
        StringSession(session_string),
        api_id,
        api_hash,
        receive_updates=False
    )
    await client.start()
    return client


async def get_groups(client):
    """সব গ্রুপ লিস্ট বের করা"""
    try:
        dialogs = await client(GetDialogsRequest(
            offset_date=None,
            offset_id=0,
            offset_peer=InputPeerEmpty(),
            limit=200,
            hash=0
        ))
        groups = []
        for dialog in dialogs.dialogs:
            try:
                entity = await client.get_entity(dialog.peer)
                if hasattr(entity, 'title'):
                    is_group = hasattr(entity, 'megagroup') and entity.megagroup
                    is_not_broadcast = not (hasattr(entity, 'broadcast') and entity.broadcast)
                    if is_group or is_not_broadcast:
                        groups.append(entity)
            except:
                pass
        return groups
    except Exception as e:
        logger.error(f"গ্রুপ লিস্ট এরর: {e}")
        return []


async def run_account_messaging(acc):
    """একাউন্ট দিয়ে মেসেজ পাঠানো"""
    acc_id = acc['id']
    acc_name = acc.get('name', acc_id)
    stop_flags[acc_id] = False
    account_stats[acc_id]['running'] = True
    
    logger.info(f"🚀 [{acc_name}] শুরু হচ্ছে...")
    
    try:
        client = await get_client(acc['api_id'], acc['api_hash'], acc['session'])
        account_clients[acc_id] = client
        
        me = await client.get_me()
        logger.info(f"✅ [{acc_name}] লগইন: {me.first_name}")
        
        groups = await get_groups(client)
        
        if not groups:
            logger.warning(f"[{acc_name}] কোনো গ্রুপ পাওয়া যায়নি!")
            account_stats[acc_id]['running'] = False
            return
        
        logger.info(f"[{acc_name}] {len(groups)} টি গ্রুপে মেসেজ যাচ্ছে...")
        cycle_count = 0
        
        while not stop_flags.get(acc_id, False):
            for group in groups:
                if stop_flags.get(acc_id, False):
                    break
                
                try:
                    await client.send_message(group, MESSAGE)
                    logger.info(f"✅ [{acc_name}] → {group.title}")
                    account_stats[acc_id]['sent'] += 1
                    save_data()
                except FloodWaitError as e:
                    wait_time = e.seconds
                    logger.warning(f"[{acc_name}] Flood wait: {wait_time}s")
                    for i in range(min(wait_time, 60)):
                        if stop_flags.get(acc_id, False):
                            break
                        await asyncio.sleep(1)
                    if wait_time > 60:
                        await asyncio.sleep(wait_time - 60)
                except Exception as e:
                    err = str(e)
                    if "admin privileges" in err.lower() or "can't write" in err.lower():
                        logger.warning(f"[{acc_name}] স্কিপ {group.title}: পারমিশন নেই")
                    else:
                        logger.warning(f"[{acc_name}] এরর: {err[:80]}")
                
                await asyncio.sleep(random.randint(MIN_INTERVAL, MAX_INTERVAL))
            
            if stop_flags.get(acc_id, False):
                break
            
            cycle_count += 1
            logger.info(f"[{acc_name}] সাইকেল {cycle_count} শেষ। {CYCLE_WAIT}s বিরতি...")
            
            for i in range(CYCLE_WAIT):
                if stop_flags.get(acc_id, False):
                    break
                await asyncio.sleep(1)
            
            if cycle_count % 20 == 0 and not stop_flags.get(acc_id, False):
                logger.info(f"[{acc_name}] রিকানেক্ট হচ্ছে...")
                try:
                    await client.disconnect()
                    await asyncio.sleep(2)
                    if not stop_flags.get(acc_id, False):
                        client = await get_client(acc['api_id'], acc['api_hash'], acc['session'])
                        account_clients[acc_id] = client
                        groups = await get_groups(client)
                        logger.info(f"[{acc_name}] রিকানেক্ট সম্পন্ন। {len(groups)} গ্রুপ")
                except Exception as e:
                    logger.error(f"[{acc_name}] রিকানেক্ট ব্যর্থ: {e}")
    
    except asyncio.CancelledError:
        logger.info(f"[{acc_name}] বন্ধ করা হয়েছে")
    except Exception as e:
        logger.error(f"[{acc_name}] মারাত্মক এরর: {e}")
    finally:
        account_stats[acc_id]['running'] = False
        stop_flags[acc_id] = True
        if acc_id in account_clients:
            try:
                await account_clients[acc_id].disconnect()
            except:
                pass
            del account_clients[acc_id]
        logger.info(f"[{acc_name}] সম্পূর্ণ বন্ধ")


def stop_account(acc_id):
    """একাউন্ট বন্ধ"""
    stop_flags[acc_id] = True
    if acc_id in running_tasks and not running_tasks[acc_id].done():
        running_tasks[acc_id].cancel()
        try:
            del running_tasks[acc_id]
        except:
            pass
    account_stats[acc_id]['running'] = False

def stop_all_accounts():
    """সব একাউন্ট বন্ধ"""
    for acc in get_all_accounts():
        stop_account(acc['id'])


# ====================
# টেলিগ্রাম বট হ্যান্ডলার
# ====================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """স্টার্ট কমান্ড"""
    
    user_id = update.effective_user.id
    
    if user_id != OWNER_ID:
        await update.message.reply_text(f"❌ অনুমতি নেই!")
        return
    
    all_accs = get_all_accounts()
    total = len(all_accs)
    running = sum(1 for acc in all_accs if account_stats.get(acc['id'], {}).get('running', False))
    total_sent = sum(account_stats.get(acc['id'], {}).get('sent', 0) for acc in all_accs)
    
    keyboard = [
        [InlineKeyboardButton("▶️ সব চালু", callback_data='start_all'),
         InlineKeyboardButton("⏹️ সব বন্ধ", callback_data='stop_all')],
        [InlineKeyboardButton("📊 স্ট্যাটাস", callback_data='status')],
        [InlineKeyboardButton("⚙️ সেটিংস", callback_data='settings')],
        [InlineKeyboardButton("👥 গ্রুপ লিস্ট", callback_data='groups')],
        [InlineKeyboardButton("🗑 একাউন্ট ডিলিট", callback_data='delete_account')],
        [InlineKeyboardButton("📋 একাউন্ট লিস্ট", callback_data='account_list')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = (
        f"🤖 *ম্যাসেজিং বট - {total} একাউন্ট*\n\n"
        f"📊 চলছে: {running}/{total}\n"
        f"📝 `{MESSAGE[:35]}...`\n"
        f"⚡ {MIN_INTERVAL}-{MAX_INTERVAL}s | সাইকেল {CYCLE_WAIT}s\n"
        f"📨 মোট পাঠিয়েছে: {total_sent}"
    )
    
    await update.message.reply_text(text, parse_mode='Markdown', reply_markup=reply_markup)


async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """বাটন ক্লিক হ্যান্ডলার"""
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id != OWNER_ID:
        return
    
    global MESSAGE, MIN_INTERVAL, MAX_INTERVAL, CYCLE_WAIT
    
    if query.data == 'start_all':
        text_parts = []
        for acc in get_all_accounts():
            acc_id = acc['id']
            if account_stats.get(acc_id, {}).get('running', False):
                text_parts.append(f"✅ {acc.get('name', acc_id)} ইতিমধ্যে চলছে")
            else:
                if acc_id not in stop_flags:
                    stop_flags[acc_id] = False
                stop_flags[acc_id] = False
                task = asyncio.create_task(run_account_messaging(acc))
                running_tasks[acc_id] = task
                text_parts.append(f"▶️ {acc.get('name', acc_id)} চালু হয়েছে")
        
        await query.edit_message_text("\n".join(text_parts) if text_parts else "❌ কিছুই করা যায়নি")
        await asyncio.sleep(2)
        await show_status(query)
    
    elif query.data == 'stop_all':
        text_parts = []
        for acc in get_all_accounts():
            acc_id = acc['id']
            if account_stats.get(acc_id, {}).get('running', False):
                stop_account(acc_id)
                text_parts.append(f"⏹️ {acc.get('name', acc_id)} বন্ধ করা হচ্ছে...")
            else:
                text_parts.append(f"❌ {acc.get('name', acc_id)} ইতিমধ্যে বন্ধ")
        
        await query.edit_message_text("\n".join(text_parts))
        await asyncio.sleep(2)
        await show_status(query)
    
    elif query.data == 'status':
        await show_status(query)
    
    elif query.data == 'settings':
        keyboard = [
            [InlineKeyboardButton("✏️ মেসেজ পরিবর্তন", callback_data='edit_msg')],
            [InlineKeyboardButton("⏱️ স্পিড সেটিংস", callback_data='edit_speed')],
            [InlineKeyboardButton("🔙 ফিরে", callback_data='back_main')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        text = (
            f"⚙️ *সেটিংস*\n\n"
            f"📝 `{MESSAGE[:30]}...`\n"
            f"⏱️ মিন: {MIN_INTERVAL}s | ম্যাক্স: {MAX_INTERVAL}s\n"
            f"🔄 সাইকেল: {CYCLE_WAIT}s"
        )
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=reply_markup)
    
    elif query.data == 'edit_msg':
        context.user_data['awaiting'] = 'message'
        await query.edit_message_text(
            f"✏️ *নতুন মেসেজ লিখুন*\n\nবর্তমান: `{MESSAGE}`\n\nশুধু মেসেজ টা লিখে পাঠান:",
            parse_mode='Markdown'
        )
    
    elif query.data == 'edit_speed':
        keyboard = [
            [InlineKeyboardButton(f"📉 মিন: {MIN_INTERVAL}s", callback_data='set_min')],
            [InlineKeyboardButton(f"📈 ম্যাক্স: {MAX_INTERVAL}s", callback_data='set_max')],
            [InlineKeyboardButton(f"🔄 সাইকেল: {CYCLE_WAIT}s", callback_data='set_cycle')],
            [InlineKeyboardButton("🔙 ফিরে", callback_data='settings')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("⏱️ *স্পিড কন্ট্রোল*", parse_mode='Markdown', reply_markup=reply_markup)
    
    elif query.data == 'set_min':
        context.user_data['awaiting'] = 'min'
        await query.edit_message_text(f"মিনিমাম ডেল (সেকেন্ড) দিন:\nবর্তমান: {MIN_INTERVAL}s\n\nযেমন: 5")
    
    elif query.data == 'set_max':
        context.user_data['awaiting'] = 'max'
        await query.edit_message_text(f"ম্যাক্সিমাম ডেল (সেকেন্ড) দিন:\nবর্তমান: {MAX_INTERVAL}s\n\nযেমন: 10")
    
    elif query.data == 'set_cycle':
        context.user_data['awaiting'] = 'cycle'
        await query.edit_message_text(f"সাইকেল ওয়েট (সেকেন্ড) দিন:\nবর্তমান: {CYCLE_WAIT}s\n\nযেমন: 30")
    
    elif query.data == 'groups':
        await query.edit_message_text("👥 *গ্রুপ লিস্ট*\nলোড হচ্ছে...", parse_mode='Markdown')
        try:
            all_accs = get_all_accounts()
            if not all_accs:
                await query.edit_message_text("❌ কোনো একাউন্ট নেই!")
                return
            acc = all_accs[0]
            client = await get_client(acc['api_id'], acc['api_hash'], acc['session'])
            groups = await get_groups(client)
            await client.disconnect()
            
            text = f"👥 *গ্রুপ ({len(groups)})*\n\n"
            for i, g in enumerate(groups[:50], 1):
                text += f"{i}. {g.title}\n"
            if len(groups) > 50:
                text += f"\n...আরও {len(groups)-50} টি"
            
            keyboard = [[InlineKeyboardButton("🔙 ফিরে", callback_data='back_main')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, parse_mode='Markdown', reply_markup=reply_markup)
        except Exception as e:
            await query.edit_message_text(f"❌ Error: {str(e)[:100]}")
    
    # ===== DELETE ACCOUNT (নাম সহ দেখাবে) =====
    elif query.data == 'delete_account':
        all_accs = get_all_accounts()
        
        if not all_accs:
            await query.edit_message_text(
                "❌ কোনো একাউন্ট নেই!",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 ফিরে", callback_data='back_main')]])
            )
            return
        
        keyboard = []
        for acc in all_accs:
            acc_name = acc.get('name', acc['id'])
            acc_type = "💚" if acc.get('type') == 'env' else "💙"
            display_text = f"{acc_type} {acc_name}"
            if len(display_text) > 35:
                display_text = display_text[:32] + "..."
            keyboard.append([InlineKeyboardButton(display_text, callback_data=f"del_acc_{acc['id']}")])
        keyboard.append([InlineKeyboardButton("🔙 ফিরে", callback_data='back_main')])
        
        await query.edit_message_text(
            "🗑 *ডিলিট করার জন্য একাউন্ট নির্বাচন করুন:*\n\n"
            "💚 = Environment Account\n💙 = Dynamic Account\n\n"
            "⚠️ Environment account delete করলে শুধু এই session থেকে মুছে যাবে, env variable থাকলে পরের restart এ আবার আসবে।",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif query.data.startswith('del_acc_'):
        acc_id = query.data.replace('del_acc_', '')
        
        # একাউন্টের নাম খুঁজে বের করো
        acc_name = acc_id
        for acc in get_all_accounts():
            if acc['id'] == acc_id:
                acc_name = acc.get('name', acc_id)
                break
        
        # প্রথমে বন্ধ করুন
        if account_stats.get(acc_id, {}).get('running', False):
            stop_account(acc_id)
            await asyncio.sleep(1)
        
        if remove_account_by_id(acc_id):
            # স্ট্যাটাস ক্লিনআপ
            if acc_id in account_stats:
                del account_stats[acc_id]
            if acc_id in stop_flags:
                del stop_flags[acc_id]
            if acc_id in running_tasks:
                del running_tasks[acc_id]
            if acc_id in account_clients:
                try:
                    await account_clients[acc_id].disconnect()
                except:
                    pass
                del account_clients[acc_id]
            
            save_data()
            await query.edit_message_text(
                f"✅ *{acc_name}* ডিলিট করা হয়েছে! 🎉",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 ফিরে", callback_data='back_main')]])
            )
        else:
            await query.edit_message_text(
                f"❌ *{acc_name}* ডিলিট করতে ব্যর্থ!",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 ফিরে", callback_data='back_main')]])
            )
    
    elif query.data == 'account_list':
        all_accs = get_all_accounts()
        if not all_accs:
            await query.edit_message_text(
                "❌ কোনো একাউন্ট নেই!",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 ফিরে", callback_data='back_main')]])
            )
            return
        
        text = f"📋 *একাউন্ট লিস্ট ({len(all_accs)})*\n\n"
        for i, acc in enumerate(all_accs, 1):
            acc_id = acc['id']
            acc_name = acc.get('name', acc_id)
            acc_type = "🟢 এনভি" if acc.get('type') == 'env' else "🔵 ডায়নামিক"
            status = '🟢 চলছে' if account_stats.get(acc_id, {}).get('running', False) else '🔴 বন্ধ'
            sent = account_stats.get(acc_id, {}).get('sent', 0)
            text += f"{i}. {acc_name} ({acc_type}) - {status} - পাঠিয়েছে: {sent}\n"
        
        keyboard = [[InlineKeyboardButton("🔙 ফিরে", callback_data='back_main')]]
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif query.data == 'back_main':
        all_accs = get_all_accounts()
        total = len(all_accs)
        running = sum(1 for acc in all_accs if account_stats.get(acc['id'], {}).get('running', False))
        total_sent = sum(account_stats.get(acc['id'], {}).get('sent', 0) for acc in all_accs)
        
        keyboard = [
            [InlineKeyboardButton("▶️ সব চালু", callback_data='start_all'),
             InlineKeyboardButton("⏹️ সব বন্ধ", callback_data='stop_all')],
            [InlineKeyboardButton("📊 স্ট্যাটাস", callback_data='status')],
            [InlineKeyboardButton("⚙️ সেটিংস", callback_data='settings')],
            [InlineKeyboardButton("👥 গ্রুপ লিস্ট", callback_data='groups')],
            [InlineKeyboardButton("🗑 একাউন্ট ডিলিট", callback_data='delete_account')],
            [InlineKeyboardButton("📋 একাউন্ট লিস্ট", callback_data='account_list')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        text = (
            f"🤖 *ম্যাসেজিং বট - {total} একাউন্ট*\n\n"
            f"📊 চলছে: {running}/{total}\n"
            f"📝 `{MESSAGE[:35]}...`\n"
            f"⚡ {MIN_INTERVAL}-{MAX_INTERVAL}s | সাইকেল {CYCLE_WAIT}s\n"
            f"📨 মোট পাঠিয়েছে: {total_sent}"
        )
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=reply_markup)


async def show_status(query):
    """স্ট্যাটাস দেখানো (নাম সহ)"""
    all_accs = get_all_accounts()
    total_sent = sum(account_stats.get(acc['id'], {}).get('sent', 0) for acc in all_accs)
    
    text = "📊 *স্ট্যাটাস*\n\n"
    for acc in all_accs:
        aid = acc['id']
        name = acc.get('name', aid)
        status = '🟢 চলছে' if account_stats.get(aid, {}).get('running', False) else '🔴 বন্ধ'
        text += f"• {name}: {status} | পাঠিয়েছে: {account_stats.get(aid, {}).get('sent', 0)}\n"
    text += f"\n📝 `{MESSAGE[:40]}`"
    text += f"\n⏱️ {MIN_INTERVAL}-{MAX_INTERVAL}s | সাইকেল {CYCLE_WAIT}s"
    text += f"\n📨 মোট: {total_sent}"
    
    keyboard = [[InlineKeyboardButton("🔙 ফিরে", callback_data='back_main')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=reply_markup)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """টেক্সট মেসেজ হ্যান্ডলার"""
    if update.effective_user.id != OWNER_ID:
        return
    
    text = update.message.text.strip()
    awaiting = context.user_data.get('awaiting')
    
    if not awaiting:
        return
    
    global MESSAGE, MIN_INTERVAL, MAX_INTERVAL, CYCLE_WAIT
    
    if awaiting == 'message':
        MESSAGE = text
        context.user_data['awaiting'] = None
        save_data()
        await update.message.reply_text(f"✅ মেসেজ আপডেট!\n\n`{MESSAGE}`", parse_mode='Markdown')
    
    elif awaiting == 'min':
        try:
            v = int(text)
            if v < 1 or v >= MAX_INTERVAL:
                await update.message.reply_text(f"❌ ১-{MAX_INTERVAL-1} এর মধ্যে দিন!")
            else:
                MIN_INTERVAL = v
                save_data()
                await update.message.reply_text(f"✅ মিন সেট: {v}s")
        except:
            await update.message.reply_text("❌ শুধু সংখ্যা দিন!")
        context.user_data['awaiting'] = None
    
    elif awaiting == 'max':
        try:
            v = int(text)
            if v <= MIN_INTERVAL:
                await update.message.reply_text(f"❌ ম্যাক্স {MIN_INTERVAL} এর বেশি হবে!")
            else:
                MAX_INTERVAL = v
                save_data()
                await update.message.reply_text(f"✅ ম্যাক্স সেট: {v}s")
        except:
            await update.message.reply_text("❌ শুধু সংখ্যা দিন!")
        context.user_data['awaiting'] = None
    
    elif awaiting == 'cycle':
        try:
            v = int(text)
            if v < 5:
                await update.message.reply_text("❌ সাইকেল ৫ সেকেন্ড বা বেশি দিন!")
            else:
                CYCLE_WAIT = v
                save_data()
                await update.message.reply_text(f"✅ সাইকেল সেট: {v}s")
        except:
            await update.message.reply_text("❌ শুধু সংখ্যা দিন!")
        context.user_data['awaiting'] = None


async def main():
    """মেইন ফাংশন"""
    print("=" * 50, flush=True)
    print(f"🤖 BOT READY", flush=True)
    print("=" * 50, flush=True)
    
    # Environment accounts থেকে নাম লোড
    print("📂 Environment accounts লোড হচ্ছে...", flush=True)
    await init_env_accounts()
    
    load_data()
    print("📂 ডাটা লোড করা হয়েছে", flush=True)
    
    # ইনিশিয়াল স্ট্যাটাস
    for acc in get_all_accounts():
        if acc['id'] not in account_stats:
            account_stats[acc['id']] = {'sent': 0, 'running': False}
            stop_flags[acc['id']] = False
    
    # ডায়নামিক একাউন্ট লোড
    dynamic = load_dynamic_accounts()
    if dynamic:
        print(f"📂 {len(dynamic)} টি ডায়নামিক একাউন্ট লোড করা হয়েছে", flush=True)
    
    # ✅ ওয়েবহুক ক্লিয়ার
    for attempt in range(5):
        try:
            r = httpx.post(f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook?drop_pending_updates=true")
            print(f"✅ ওয়েবহুক ক্লিয়ার (attempt {attempt+1})", flush=True)
            await asyncio.sleep(2)
        except Exception as e:
            print(f"⚠️ ওয়েবহুক এরর: {e}", flush=True)
    
    # পেন্ডিং আপডেট ক্লিয়ার
    for i in range(3):
        try:
            r = httpx.post(f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates", json={"offset": -1, "timeout": 1})
            updates = r.json().get('result', [])
            if updates:
                last_id = updates[-1]['update_id']
                httpx.post(f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates", json={"offset": last_id + 1, "timeout": 1})
                print(f"✅ পেন্ডিং আপডেট ক্লিয়ার (attempt {i+1})", flush=True)
            await asyncio.sleep(1)
        except:
            pass
    
    print("🤖 বট তৈরি হচ্ছে...", flush=True)
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CallbackQueryHandler(button_click))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    await app.initialize()
    await app.start()
    
    # ✅ Polling
    poll_started = False
    for poll_attempt in range(5):
        try:
            await app.updater.start_polling(
                drop_pending_updates=True,
                timeout=30,
                read_timeout=30,
                connect_timeout=30
            )
            print("✅✅✅ বট চালু! ✅✅✅", flush=True)
            poll_started = True
            break
        except Exception as e:
            error_msg = str(e)
            if "Conflict" in error_msg:
                print(f"⚠️ Conflict detected (attempt {poll_attempt+1})", flush=True)
                try:
                    httpx.post(f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook?drop_pending_updates=true")
                except:
                    pass
                await asyncio.sleep(10 * (poll_attempt + 1))
            else:
                print(f"❌ Polling error: {error_msg[:100]}", flush=True)
                await asyncio.sleep(5)
    
    if not poll_started:
        print("❌❌❌ Polling start করতে ব্যর্থ!", flush=True)
        return
    
    try:
        await asyncio.Event().wait()
    except asyncio.CancelledError:
        pass
    finally:
        print("🛑 বন্ধ হচ্ছে...", flush=True)
        stop_all_accounts()
        await asyncio.sleep(2)
        try:
            await app.updater.stop()
        except:
            pass
        try:
            await app.stop()
        except:
            pass
        try:
            await app.shutdown()
        except:
            pass


if __name__ == "__main__":
    # Flask থ্রেড
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    print(f"🌐 Flask ওয়েব সার্ভার পোর্ট {os.environ.get('PORT', 10000)}", flush=True)
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("⛔ Keyboard interrupt")
    except Exception as e:
        print(f"\n❌ মারাত্মক এরর: {e}", flush=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)
