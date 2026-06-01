#!/usr/bin/env python3
import sys
import os
import asyncio
import random
import logging
import json
from datetime import datetime
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import FloodWaitError
from telethon.tl.functions.messages import GetDialogsRequest
from telethon.tl.types import InputPeerEmpty
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters

logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    force=True,
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

print("=" * 60, flush=True)
print("🤖 3-ACCOUNT BOT STARTING...", flush=True)
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

MESSAGE = os.environ.get("MESSAGE", "𝟭𝟬 𝗠𝗜𝗡 𝗩𝗖 ₹𝟰𝟱 𝗕𝗔𝗕𝗬😘")
MIN_INTERVAL = int(os.environ.get("MIN_INTERVAL", "3"))
MAX_INTERVAL = int(os.environ.get("MAX_INTERVAL", "5"))
CYCLE_WAIT = int(os.environ.get("CYCLE_WAIT", "30"))
# ===================================

print("📋 Checking environment variables...", flush=True)
print(f"   BOT_TOKEN: {'✅' if BOT_TOKEN else '❌'}", flush=True)
print(f"   OWNER_ID: {OWNER_ID}", flush=True)
print(f"   API_ID_1: {API_ID_1}", flush=True)
print(f"   API_HASH_1: {'✅' if API_HASH_1 else '❌'}", flush=True)
print(f"   SESSION_1: {'✅' if SESSION_1 else '❌'}", flush=True)

if not all([BOT_TOKEN, OWNER_ID, API_ID_1, API_HASH_1, SESSION_1]):
    print("\n❌ ERROR: Account 1 credentials missing!", flush=True)
    sys.exit(1)

running_tasks = {}
account_clients = {}
account_stats = {
    'acc1': {'sent': 0, 'running': False},
    'acc2': {'sent': 0, 'running': False},
    'acc3': {'sent': 0, 'running': False}
}
data_file = "bot_data.json"

ACCOUNTS = [
    {'id': 'acc1', 'api_id': API_ID_1, 'api_hash': API_HASH_1, 'session': SESSION_1},
    {'id': 'acc2', 'api_id': API_ID_2, 'api_hash': API_HASH_2, 'session': SESSION_2},
    {'id': 'acc3', 'api_id': API_ID_3, 'api_hash': API_HASH_3, 'session': SESSION_3}
]

ACTIVE_ACCOUNTS = [acc for acc in ACCOUNTS if all([acc['api_id'], acc['api_hash'], acc['session']])]

print(f"📊 Active accounts: {len(ACTIVE_ACCOUNTS)}", flush=True)
for acc in ACTIVE_ACCOUNTS:
    print(f"   ✅ {acc['id']}: configured", flush=True)

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
                for acc_id in account_stats:
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
        'stats': {acc_id: {'sent': account_stats[acc_id]['sent']} for acc_id in account_stats}
    }
    try:
        with open(data_file, 'w') as f:
            json.dump(data, f, indent=2)
    except:
        pass

async def get_client(acc_id, api_id, api_hash, session_string):
    client = TelegramClient(StringSession(session_string), api_id, api_hash)
    await client.start()
    me = await client.get_me()
    logger.info(f"✅ [{acc_id}] Logged in: {me.first_name}")
    return client

async def run_account_messaging(acc_id, api_id, api_hash, session_string):
    global account_stats
    logger.info(f"🚀 [{acc_id}] Starting...")
    try:
        client = await get_client(acc_id, api_id, api_hash, session_string)
        account_clients[acc_id] = client
        account_stats[acc_id]['running'] = True
        
        dialogs = await client(GetDialogsRequest(
            offset_date=None, offset_id=0,
            offset_peer=InputPeerEmpty(), limit=200, hash=0
        ))
        groups = []
        for dialog in dialogs.dialogs:
            try:
                entity = await client.get_entity(dialog.peer)
                if hasattr(entity, 'title'):
                    groups.append(entity)
            except:
                pass
        if not groups:
            logger.warning(f"[{acc_id}] No groups found!")
            account_stats[acc_id]['running'] = False
            return
        
        logger.info(f"[{acc_id}] Sending to {len(groups)} groups...")
        cycle_count = 0
        
        while True:
            for group in groups:
                try:
                    await client.send_message(group, MESSAGE)
                    logger.info(f"✅ [{acc_id}] Sent to {group.title}")
                    account_stats[acc_id]['sent'] += 1
                    save_data()
                except FloodWaitError as e:
                    logger.warning(f"[{acc_id}] Flood wait: {e.seconds}s")
                    await asyncio.sleep(e.seconds)
                except Exception as e:
                    logger.warning(f"[{acc_id}] Error: {e}")
                await asyncio.sleep(random.randint(MIN_INTERVAL, MAX_INTERVAL))
            
            cycle_count += 1
            logger.info(f"[{acc_id}] Cycle {cycle_count} done. Waiting {CYCLE_WAIT}s...")
            
            if cycle_count % 15 == 0:
                logger.info(f"[{acc_id}] Reconnecting...")
                await client.disconnect()
                await asyncio.sleep(3)
                client = await get_client(acc_id, api_id, api_hash, session_string)
                account_clients[acc_id] = client
                
                dialogs = await client(GetDialogsRequest(
                    offset_date=None, offset_id=0,
                    offset_peer=InputPeerEmpty(), limit=200, hash=0
                ))
                groups = []
                for dialog in dialogs.dialogs:
                    try:
                        entity = await client.get_entity(dialog.peer)
                        if hasattr(entity, 'title'):
                            groups.append(entity)
                    except:
                        pass
                logger.info(f"[{acc_id}] Reconnected. {len(groups)} groups.")
            
            await asyncio.sleep(CYCLE_WAIT)
            
    except asyncio.CancelledError:
        logger.info(f"[{acc_id}] Stopped by user")
    except Exception as e:
        logger.error(f"[{acc_id}] Fatal error: {e}", exc_info=True)
    finally:
        account_stats[acc_id]['running'] = False
        if acc_id in account_clients:
            try:
                await account_clients[acc_id].disconnect()
            except:
                pass
            del account_clients[acc_id]

async def start(update: Update, context):
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        await update.message.reply_text("❌ অনুমতি নেই!")
        return
    
    total_accounts = len(ACTIVE_ACCOUNTS)
    running_count = sum(1 for acc in ACTIVE_ACCOUNTS if account_stats[acc['id']]['running'])
    total_sent = sum(account_stats[acc['id']]['sent'] for acc in ACTIVE_ACCOUNTS)
    
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("▶️ সব চালু", callback_data='start_all'),
         InlineKeyboardButton("⏹️ সব বন্ধ", callback_data='stop_all')],
        [InlineKeyboardButton("📊 স্ট্যাটাস", callback_data='status')],
        [InlineKeyboardButton("⚙️ সেটিংস", callback_data='settings')],
        [InlineKeyboardButton("👥 গ্রুপ লিস্ট", callback_data='groups')],
        [InlineKeyboardButton("🔄 Session Refresh", callback_data='refresh_all')]
    ])
    
    await update.message.reply_text(
        f"🤖 *ম্যাসেজিং বট - ৩ একাউন্ট*\n\n"
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
        for acc in ACTIVE_ACCOUNTS:
            acc_id = acc['id']
            if account_stats[acc_id]['running']:
                text += f"✅ {acc_id} ইতিমধ্যে চলছে\n"
            else:
                task = asyncio.create_task(run_account_messaging(acc_id, acc['api_id'], acc['api_hash'], acc['session']))
                running_tasks[acc_id] = task
                text += f"▶️ {acc_id} চালু হয়েছে\n"
        if not text:
            text = "❌ কোনো একাউন্ট নেই!"
        await query.edit_message_text(text)
    
    elif query.data == 'stop_all':
        text = ""
        for acc_id in list(running_tasks.keys()):
            if not running_tasks[acc_id].done():
                running_tasks[acc_id].cancel()
                text += f"⏹️ {acc_id} বন্ধ\n"
            del running_tasks[acc_id]
        for acc in ACTIVE_ACCOUNTS:
            account_stats[acc['id']]['running'] = False
        if not text:
            text = "❌ কিছুই চলছে না!"
        await query.edit_message_text(text)
    
    elif query.data == 'status':
        total_sent = sum(account_stats[acc['id']]['sent'] for acc in ACTIVE_ACCOUNTS)
        text = "📊 *স্ট্যাটাস*\n\n"
        for acc in ACTIVE_ACCOUNTS:
            aid = acc['id']
            status = '🟢 চলছে' if account_stats[aid]['running'] else '🔴 বন্ধ'
            text += f"• {aid}: {status} | পাঠিয়েছে: {account_stats[aid]['sent']}\n"
        text += f"\n📝 `{MESSAGE[:40]}`"
        text += f"\n⏱️ {MIN_INTERVAL}-{MAX_INTERVAL}s | সাইকেল {CYCLE_WAIT}s"
        text += f"\n📨 মোট: {total_sent}"
        await query.edit_message_text(text, parse_mode='Markdown')
    
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
        await query.edit_message_text(f"মিনিমাম ডেল (সেকেন্ড) দিন:\nবর্তমান: {MIN_INTERVAL}s\n\nযেমন: 2")
    
    elif query.data == 'set_max':
        context.user_data['awaiting'] = 'max'
        await query.edit_message_text(f"ম্যাক্সিমাম ডেল (সেকেন্ড) দিন:\nবর্তমান: {MAX_INTERVAL}s\n\nযেমন: 5")
    
    elif query.data == 'set_cycle':
        context.user_data['awaiting'] = 'cycle'
        await query.edit_message_text(f"সাইকেল ওয়েট (সেকেন্ড) দিন:\nবর্তমান: {CYCLE_WAIT}s\n\nযেমন: 30")
    
    elif query.data == 'groups':
        await query.edit_message_text("👥 *গ্রুপ লিস্ট*\nলোড হচ্ছে...", parse_mode='Markdown')
        try:
            acc = ACTIVE_ACCOUNTS[0]
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
        for acc in ACTIVE_ACCOUNTS:
            aid = acc['id']
            try:
                if aid in running_tasks and not running_tasks[aid].done():
                    running_tasks[aid].cancel()
                    del running_tasks[aid]
                account_stats[aid]['running'] = False
                client = await get_client(aid, acc['api_id'], acc['api_hash'], acc['session'])
                await client.disconnect()
                text += f"✅ {aid}: Session OK\n"
            except Exception as e:
                text += f"❌ {aid}: {str(e)[:50]}\n"
        await query.edit_message_text(text)
    
    elif query.data == 'back_main':
        total_accounts = len(ACTIVE_ACCOUNTS)
        running_count = sum(1 for acc in ACTIVE_ACCOUNTS if account_stats[acc['id']]['running'])
        total_sent = sum(account_stats[acc['id']]['sent'] for acc in ACTIVE_ACCOUNTS)
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("▶️ সব চালু", callback_data='start_all'),
             InlineKeyboardButton("⏹️ সব বন্ধ", callback_data='stop_all')],
            [InlineKeyboardButton("📊 স্ট্যাটাস", callback_data='status')],
            [InlineKeyboardButton("⚙️ সেটিংস", callback_data='settings')],
            [InlineKeyboardButton("👥 গ্রুপ লিস্ট", callback_data='groups')],
            [InlineKeyboardButton("🔄 Session Refresh", callback_data='refresh_all')]
        ])
        await query.edit_message_text(
            f"🤖 *ম্যাসেজিং বট*\n\n"
            f"📊 চলছে: {running_count}/{total_accounts}\n"
            f"📝 `{MESSAGE[:30]}...`\n"
            f"⚡ {MIN_INTERVAL}-{MAX_INTERVAL}s | সাইকেল {CYCLE_WAIT}s\n"
            f"📨 মোট পাঠিয়েছে: {total_sent}",
            parse_mode='Markdown', reply_markup=kb
        )

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
    print("🤖 3-ACCOUNT MASS MESSAGING BOT", flush=True)
    print("=" * 50, flush=True)
    
    print(f"🐍 Python version: {sys.version}", flush=True)
    load_data()
    print(f"📂 Data loaded successfully", flush=True)
    
    print("\n🔐 Verifying sessions...", flush=True)
    for acc in ACTIVE_ACCOUNTS:
        try:
            print(f"   Checking {acc['id']}...", end=' ', flush=True)
            client = await get_client(acc['id'], acc['api_id'], acc['api_hash'], acc['session'])
            await client.disconnect()
            print("✅ OK", flush=True)
        except Exception as e:
            print(f"❌ Failed: {e}", flush=True)
            sys.exit(1)
    
    print("\n🤖 Setting up bot...", flush=True)
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    
    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    print("✅✅✅ BOT IS RUNNING! Send /start in Telegram ✅✅✅", flush=True)
    
    try:
        while True:
            await asyncio.sleep(3600)
    except:
        pass
    finally:
        await app.stop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("⛔ Stopped")
    except Exception as e:
        print(f"\n❌❌❌ FATAL ERROR: {e}", flush=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)
