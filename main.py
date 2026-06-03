#!/usr/bin/env python3
import sys
import os
import asyncio
import random
import logging
import json
import threading
from datetime import datetime
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import FloodWaitError
from telethon.tl.functions.messages import GetDialogsRequest
from telethon.tl.types import InputPeerEmpty
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from flask import Flask

logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    force=True,
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

print("=" * 60, flush=True)
print("🤖 10-ACCOUNT MASS MESSAGING BOT", flush=True)
print("=" * 60, flush=True)

# ====== Environment Variables ======
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID = int(os.environ.get("OWNER_ID", "0"))

# 10 টা একাউন্টের জন্য এনভায়রনমেন্ট ভেরিয়েবল
API_IDS = []
API_HASHES = []
SESSIONS = []

for i in range(1, 11):
    api_id = os.environ.get(f"API_ID_{i}")
    api_hash = os.environ.get(f"API_HASH_{i}")
    session = os.environ.get(f"SESSION_{i}")
    API_IDS.append(int(api_id) if api_id else 0)
    API_HASHES.append(api_hash if api_hash else "")
    SESSIONS.append(session if session else "")

MESSAGE = os.environ.get("MESSAGE", "𝟭𝟬 𝗠𝗜𝗡 𝗩𝗖 ₹𝟰𝟱 𝗕𝗔𝗕𝗬😘")
MIN_INTERVAL = int(os.environ.get("MIN_INTERVAL", "5"))
MAX_INTERVAL = int(os.environ.get("MAX_INTERVAL", "8"))
CYCLE_WAIT = int(os.environ.get("CYCLE_WAIT", "30"))
# ===================================

# শুধু valid (কনফিগার করা) একাউন্টগুলো নিচ্ছি
ACCOUNTS = []
for i in range(10):
    if all([API_IDS[i], API_HASHES[i], SESSIONS[i]]):
        ACCOUNTS.append({
            'id': f'acc{i+1}',
            'api_id': API_IDS[i],
            'api_hash': API_HASHES[i],
            'session': SESSIONS[i]
        })

print(f"📊 মোট কনফিগার করা একাউন্ট: {len(ACCOUNTS)}/10", flush=True)
for acc in ACCOUNTS:
    print(f"   ✅ {acc['id']}: সেটআপ করা আছে", flush=True)

if len(ACCOUNTS) == 0:
    print("\n❌ ERROR: কোনো একাউন্ট কনফিগার করা নেই!", flush=True)
    print("   API_ID_1, API_HASH_1, SESSION_1 সেট করতে ভুলো না।", flush=True)
    sys.exit(1)

if not all([BOT_TOKEN, OWNER_ID]):
    print("\n❌ ERROR: BOT_TOKEN বা OWNER_ID দেওয়া হয়নি!", flush=True)
    sys.exit(1)

# Global variables
running_tasks = {}
stop_flags = {}
account_clients = {}
account_stats = {}
for acc in ACCOUNTS:
    account_stats[acc['id']] = {'sent': 0, 'running': False}

data_file = "bot_data.json"

# ====== Flask Web Server ======
web_app = Flask(__name__)

@web_app.route("/")
def home():
    running_count = sum(1 for acc in ACCOUNTS if account_stats[acc['id']]['running'])
    total_sent = sum(account_stats[acc['id']]['sent'] for acc in ACCOUNTS)
    return f"✅ Bot Running | Active: {running_count}/{len(ACCOUNTS)} | Total Sent: {total_sent}"

@web_app.route("/health")
def health():
    return "OK", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    web_app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
# ============================================================


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
                for acc in ACCOUNTS:
                    acc_id = acc['id']
                    if acc_id in saved_stats:
                        account_stats[acc_id]['sent'] = saved_stats[acc_id].get('sent', 0)
        except:
            pass

def save_data():
    data = {
        'message': MESSAGE,
        'min_interval': MIN_INTERVAL,
        'max_interval': MAX_INTERVAL,
        'cycle_wait': CYCLE_WAIT,
        'stats': {acc['id']: {'sent': account_stats[acc['id']]['sent']} for acc in ACCOUNTS}
    }
    try:
        with open(data_file, 'w') as f:
            json.dump(data, f, indent=2)
    except:
        pass


# ⭐ ফিক্স: receive_updates=False — অযথা আপডেট সিঙ্ক বন্ধ
async def get_client(acc_id, api_id, api_hash, session_string):
    client = TelegramClient(
        StringSession(session_string), 
        api_id, 
        api_hash,
        receive_updates=False           # ← মেইন ফিক্স
    )
    await client.start()
    me = await client.get_me()
    logger.info(f"✅ [{acc_id}] লগইন: {me.first_name} {me.last_name or ''}")
    return client


async def run_account_messaging(acc_id, api_id, api_hash, session_string):
    global account_stats, stop_flags
    
    stop_flags[acc_id] = False
    logger.info(f"🚀 [{acc_id}] শুরু হচ্ছে...")
    
    try:
        client = await get_client(acc_id, api_id, api_hash, session_string)
        account_clients[acc_id] = client
        account_stats[acc_id]['running'] = True
        
        # সব গ্রুপ লিস্ট নিচ্ছি
        dialogs = await client(GetDialogsRequest(
            offset_date=None, offset_id=0,
            offset_peer=InputPeerEmpty(), limit=200, hash=0
        ))
        groups = []
        for dialog in dialogs.dialogs:
            try:
                entity = await client.get_entity(dialog.peer)
                if hasattr(entity, 'title') and hasattr(entity, 'megagroup'):
                    if entity.megagroup:
                        groups.append(entity)
                elif hasattr(entity, 'title') and not hasattr(entity, 'broadcast'):
                    groups.append(entity)
            except:
                pass
        
        if not groups:
            logger.warning(f"[{acc_id}] কোনো গ্রুপ পাওয়া যায়নি!")
            account_stats[acc_id]['running'] = False
            return
        
        logger.info(f"[{acc_id}] {len(groups)} টি গ্রুপে মেসেজ যাচ্ছে...")
        cycle_count = 0
        
        while not stop_flags.get(acc_id, False):
            for group in groups:
                if stop_flags.get(acc_id, False):
                    break
                    
                try:
                    await client.send_message(group, MESSAGE)
                    logger.info(f"✅ [{acc_id}] পাঠানো হয়েছে → {group.title}")
                    account_stats[acc_id]['sent'] += 1
                    save_data()
                except FloodWaitError as e:
                    wait_time = e.seconds
                    logger.warning(f"[{acc_id}] Flood ওয়েট: {wait_time}s")
                    for i in range(wait_time):
                        if stop_flags.get(acc_id, False):
                            break
                        await asyncio.sleep(1)
                except Exception as e:
                    error_str = str(e)
                    if "admin privileges" in error_str.lower() or "can't write" in error_str.lower():
                        logger.warning(f"[{acc_id}] স্কিপ {group.title}: পারমিশন নেই")
                    else:
                        logger.warning(f"[{acc_id}] এরর: {error_str[:100]}")
                
                # র‍্যান্ডম ডিলে
                await asyncio.sleep(random.randint(MIN_INTERVAL, MAX_INTERVAL))
            
            if stop_flags.get(acc_id, False):
                break
                
            cycle_count += 1
            logger.info(f"[{acc_id}] সাইকেল {cycle_count} শেষ। {CYCLE_WAIT}s অপেক্ষা...")
            
            for i in range(CYCLE_WAIT):
                if stop_flags.get(acc_id, False):
                    break
                await asyncio.sleep(1)
            
            # ⭐ ফিক্স: রিকানেক্ট ১০ এর বদলে ৫০ সাইকেলে
            if cycle_count % 50 == 0 and not stop_flags.get(acc_id, False):
                logger.info(f"[{acc_id}] রিকানেক্ট হচ্ছে...")
                await client.disconnect()
                await asyncio.sleep(3)
                if stop_flags.get(acc_id, False):
                    break
                client = await get_client(acc_id, api_id, api_hash, session_string)
                account_clients[acc_id] = client
                
                # আবার গ্রুপ লিস্ট আপডেট
                dialogs = await client(GetDialogsRequest(
                    offset_date=None, offset_id=0,
                    offset_peer=InputPeerEmpty(), limit=200, hash=0
                ))
                groups = []
                for dialog in dialogs.dialogs:
                    try:
                        entity = await client.get_entity(dialog.peer)
                        if hasattr(entity, 'title') and hasattr(entity, 'megagroup'):
                            if entity.megagroup:
                                groups.append(entity)
                        elif hasattr(entity, 'title') and not hasattr(entity, 'broadcast'):
                            groups.append(entity)
                    except:
                        pass
                logger.info(f"[{acc_id}] রিকানেক্ট সম্পন্ন। {len(groups)} টি গ্রুপ।")
            
    except asyncio.CancelledError:
        logger.info(f"[{acc_id}] ইউজার বন্ধ করেছেন")
    except Exception as e:
        logger.error(f"[{acc_id}] মারাত্মক এরর: {e}", exc_info=True)
    finally:
        account_stats[acc_id]['running'] = False
        stop_flags[acc_id] = True
        if acc_id in account_clients:
            try:
                await account_clients[acc_id].disconnect()
            except:
                pass
            del account_clients[acc_id]
        logger.info(f"[{acc_id}] সম্পূর্ণ বন্ধ")


def stop_account(acc_id):
    stop_flags[acc_id] = True
    if acc_id in running_tasks and not running_tasks[acc_id].done():
        running_tasks[acc_id].cancel()
        del running_tasks[acc_id]
    account_stats[acc_id]['running'] = False
    logger.info(f"[{acc_id}] স্টপ সিগন্যাল পাঠানো হয়েছে")

def stop_all_accounts():
    for acc in ACCOUNTS:
        stop_account(acc['id'])


# ==================== টেলিগ্রাম বট হ্যান্ডলার ====================

async def start(update: Update, context):
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        await update.message.reply_text("❌ অনুমতি নেই!")
        return
    
    total_accounts = len(ACCOUNTS)
    running_count = sum(1 for acc in ACCOUNTS if account_stats[acc['id']]['running'])
    total_sent = sum(account_stats[acc['id']]['sent'] for acc in ACCOUNTS)
    
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("▶️ সব চালু", callback_data='start_all'),
         InlineKeyboardButton("⏹️ সব বন্ধ", callback_data='stop_all')],
        [InlineKeyboardButton("📊 স্ট্যাটাস", callback_data='status')],
        [InlineKeyboardButton("⚙️ সেটিংস", callback_data='settings')],
        [InlineKeyboardButton("👥 গ্রুপ লিস্ট", callback_data='groups')],
        [InlineKeyboardButton("🔄 Session Refresh", callback_data='refresh_all')]
    ])
    
    await update.message.reply_text(
        f"🤖 *ম্যাসেজিং বট - {total_accounts} একাউন্ট*\n\n"
        f"📊 চলছে: {running_count}/{total_accounts}\n"
        f"📝 `{MESSAGE[:30]}...`\n"
        f"⚡ {MIN_INTERVAL}-{MAX_INTERVAL}s | সাইকেল {CYCLE_WAIT}s\n"
        f"📨 মোট পাঠিয়েছে: {total_sent}",
        parse_mode='Markdown', reply_markup=kb
    )


async def button_handler(update: Update, context):
    query = update.callback_query
    await query.answer()
    if query.from_user.id != OWNER_ID:
        return
    
    global MESSAGE, MIN_INTERVAL, MAX_INTERVAL, CYCLE_WAIT
    
    if query.data == 'start_all':
        text = ""
        for acc in ACCOUNTS:
            acc_id = acc['id']
            if account_stats[acc_id]['running']:
                text += f"✅ {acc_id} ইতিমধ্যে চলছে\n"
            else:
                stop_flags[acc_id] = False
                task = asyncio.create_task(run_account_messaging(acc_id, acc['api_id'], acc['api_hash'], acc['session']))
                running_tasks[acc_id] = task
                text += f"▶️ {acc_id} চালু হয়েছে\n"
        if not text:
            text = "❌ কোনো একাউন্ট নেই!"
        await query.edit_message_text(text)
    
    elif query.data == 'stop_all':
        text = ""
        for acc in ACCOUNTS:
            acc_id = acc['id']
            if account_stats[acc_id]['running']:
                stop_account(acc_id)
                text += f"⏹️ {acc_id} বন্ধ করা হচ্ছে...\n"
            else:
                text += f"❌ {acc_id} ইতিমধ্যে বন্ধ\n"
        if not text:
            text = "❌ কিছুই চলছে না!"
        await query.edit_message_text(text)
        await asyncio.sleep(2)
        await show_status_auto(query)
    
    elif query.data == 'status':
        await show_status_auto(query)
    
    elif query.data == 'settings':
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✏️ ম্যাসেজ পরিবর্তন", callback_data='edit_msg')],
            [InlineKeyboardButton("⏱️ স্পিড সেটিংস", callback_data='edit_speed')],
            [InlineKeyboardButton("🔙 ফিরে", callback_data='back_main')]
        ])
        await query.edit_message_text(
            f"⚙️ *সেটিংস*\n\n"
            f"📝 `{MESSAGE[:30]}...`\n"
            f"⏱️ মিন: {MIN_INTERVAL}s | ম্যাক্স: {MAX_INTERVAL}s\n"
            f"🔄 সাইকেল: {CYCLE_WAIT}s",
            parse_mode='Markdown', reply_markup=kb
        )
    
    elif query.data == 'edit_msg':
        context.user_data['awaiting'] = 'message'
        await query.edit_message_text(
            f"✏️ *নতুন ম্যাসেজ লিখুন*\n\nবর্তমান: `{MESSAGE}`\n\nশুধু ম্যাসেজ টা লিখে পাঠান:",
            parse_mode='Markdown'
        )
    
    elif query.data == 'edit_speed':
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"📉 মিন: {MIN_INTERVAL}s", callback_data='set_min')],
            [InlineKeyboardButton(f"📈 ম্যাক্স: {MAX_INTERVAL}s", callback_data='set_max')],
            [InlineKeyboardButton(f"🔄 সাইকেল: {CYCLE_WAIT}s", callback_data='set_cycle')],
            [InlineKeyboardButton("🔙 ফিরে", callback_data='settings')]
        ])
        await query.edit_message_text("⏱️ *স্পিড কন্ট্রোল*", parse_mode='Markdown', reply_markup=kb)
    
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
            acc = ACCOUNTS[0]  # প্রথম একাউন্ট ব্যবহার করবে
            client = await get_client(acc['id'], acc['api_id'], acc['api_hash'], acc['session'])
            dialogs = await client(GetDialogsRequest(
                offset_date=None, offset_id=0,
                offset_peer=InputPeerEmpty(), limit=200, hash=0
            ))
            groups = []
            for dialog in dialogs.dialogs:
                try:
                    entity = await client.get_entity(dialog.peer)
                    if hasattr(entity, 'title'):
                        groups.append(f"• {entity.title}")
                except:
                    pass
            await client.disconnect()
            text = f"👥 *গ্রুপ ({len(groups)})*\n\n" + "\n".join(groups[:50])
            if len(groups) > 50:
                text += f"\n\n...আরও {len(groups)-50} টি"
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 ফিরে", callback_data='back_main')]])
            await query.edit_message_text(text, parse_mode='Markdown', reply_markup=kb)
        except Exception as e:
            await query.edit_message_text(f"❌ Error: {str(e)[:100]}")
    
    elif query.data == 'refresh_all':
        text = "🔄 Session রিনিউ করা হচ্ছে...\n\n"
        for acc in ACCOUNTS:
            aid = acc['id']
            try:
                if account_stats[aid]['running']:
                    stop_account(aid)
                    await asyncio.sleep(2)
                client = await get_client(aid, acc['api_id'], acc['api_hash'], acc['session'])
                await client.disconnect()
                text += f"✅ {aid}: Session OK\n"
            except Exception as e:
                text += f"❌ {aid}: {str(e)[:50]}\n"
        await query.edit_message_text(text)
        await asyncio.sleep(2)
        # স্টার্ট মেন্যু দেখাচ্ছি
        total_accounts = len(ACCOUNTS)
        running_count = sum(1 for a in ACCOUNTS if account_stats[a['id']]['running'])
        total_sent = sum(account_stats[a['id']]['sent'] for a in ACCOUNTS)
        
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("▶️ সব চালু", callback_data='start_all'),
             InlineKeyboardButton("⏹️ সব বন্ধ", callback_data='stop_all')],
            [InlineKeyboardButton("📊 স্ট্যাটাস", callback_data='status')],
            [InlineKeyboardButton("⚙️ সেটিংস", callback_data='settings')],
            [InlineKeyboardButton("👥 গ্রুপ লিস্ট", callback_data='groups')],
            [InlineKeyboardButton("🔄 Session Refresh", callback_data='refresh_all')]
        ])
        await query.message.reply_text(
            f"🤖 *ম্যাসেজিং বট - {total_accounts} একাউন্ট*\n\n"
            f"📊 চলছে: {running_count}/{total_accounts}\n"
            f"📝 `{MESSAGE[:30]}...`\n"
            f"⏱️ {MIN_INTERVAL}-{MAX_INTERVAL}s | সাইকেল {CYCLE_WAIT}s\n"
            f"📨 মোট পাঠিয়েছে: {total_sent}",
            parse_mode='Markdown', reply_markup=kb
        )
    
    elif query.data == 'back_main':
        await start(update, context)


async def show_status_auto(query):
    total_sent = sum(account_stats[acc['id']]['sent'] for acc in ACCOUNTS)
    text = "📊 *স্ট্যাটাস*\n\n"
    for acc in ACCOUNTS:
        aid = acc['id']
        status = '🟢 চলছে' if account_stats[aid]['running'] else '🔴 বন্ধ'
        text += f"• {aid}: {status} | পাঠিয়েছে: {account_stats[aid]['sent']}\n"
    text += f"\n📝 `{MESSAGE[:40]}`"
    text += f"\n⏱️ {MIN_INTERVAL}-{MAX_INTERVAL}s | সাইকেল {CYCLE_WAIT}s"
    text += f"\n📨 মোট: {total_sent}"
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 ফিরে", callback_data='back_main')]])
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=kb)


async def text_handler(update: Update, context):
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
        await update.message.reply_text(f"✅ ম্যাসেজ আপডেট!\n\n`{MESSAGE}`", parse_mode='Markdown')
    
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
    print("=" * 50, flush=True)
    print(f"🤖 {len(ACCOUNTS)}-ACCOUNT MASS MESSAGING BOT", flush=True)
    print("=" * 50, flush=True)
    
    print(f"🐍 Python version: {sys.version}", flush=True)
    load_data()
    print(f"📂 ডাটা লোড করা হয়েছে", flush=True)
    
    print("\n🔐 Session চেক করা হচ্ছে...", flush=True)
    for acc in ACCOUNTS:
        try:
            print(f"   {acc['id']} চেক...", end=' ', flush=True)
            client = await get_client(acc['id'], acc['api_id'], acc['api_hash'], acc['session'])
            await client.disconnect()
            print("✅ OK", flush=True)
        except Exception as e:
            print(f"❌ ব্যর্থ: {e}", flush=True)
            sys.exit(1)
    
    print("\n🤖 বট সেটআপ হচ্ছে...", flush=True)
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    
    await app.initialize()
    await app.start()
    
    # ⭐ ফিক্স: পোলিং টাইমআউট যোগ
    await app.updater.start_polling(
        drop_pending_updates=True,
        timeout=30          # ← পোলিং টাইমআউট
    )
    print("✅✅✅ BOT চালু! টেলিগ্রামে /start দিন ✅✅✅", flush=True)
    
    try:
        await asyncio.Event().wait()
    except asyncio.CancelledError:
        pass
    finally:
        logger.info("🛑 বন্ধ হচ্ছে...")
        stop_all_accounts()
        await asyncio.sleep(1)
        await app.stop()
        await app.shutdown()


if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    print(f"🌐 Flask ওয়েব সার্ভার পোর্ট {os.environ.get('PORT', 10000)} এ শুরু", flush=True)
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("⛔ Keyboard interrupt দিয়ে বন্ধ")
    except Exception as e:
        print(f"\n❌❌❌ মারাত্মক এরর: {e}", flush=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)
