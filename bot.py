#!/usr/bin/env python3
import os, sys, asyncio, random, logging, json
from datetime import datetime
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import FloodWaitError
from telethon.tl.functions.messages import GetDialogsRequest
from telethon.tl.types import InputPeerEmpty
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ====== READ FROM ENVIRONMENT VARIABLES ======
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID = int(os.environ.get("OWNER_ID", "0"))
API_ID = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH", "")
SESSION_STRING = os.environ.get("SESSION_STRING", "")
MESSAGE = os.environ.get("MESSAGE", "𝟭𝟬 𝗠𝗜𝗡 𝗩𝗖 ₹𝟰𝟵 𝗕𝗔𝗕𝗬😘")
MIN_INTERVAL = int(os.environ.get("MIN_INTERVAL", "1"))
MAX_INTERVAL = int(os.environ.get("MAX_INTERVAL", "2"))
CYCLE_WAIT = int(os.environ.get("CYCLE_WAIT", "15"))
# ==============================================

if not all([BOT_TOKEN, OWNER_ID, API_ID, API_HASH, SESSION_STRING]):
    print("❌ ERROR: Environment variables missing!")
    print("Required: BOT_TOKEN, OWNER_ID, API_ID, API_HASH, SESSION_STRING")
    sys.exit(1)

running_task = None
account_stats = {}
data_file = "bot_data.json"

def load_data():
    global account_stats
    if os.path.exists(data_file):
        try:
            with open(data_file, 'r') as f:
                d = json.load(f)
                account_stats = d.get('stats', {})
        except:
            account_stats = {}

def save_data():
    data = {'stats': account_stats}
    try:
        with open(data_file, 'w') as f:
            json.dump(data, f, indent=2)
    except:
        pass

async def get_client():
    client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
    await client.start()
    me = await client.get_me()
    logger.info(f"✅ Logged in: {me.first_name}")
    return client

async def run_messaging():
    global running_task
    try:
        client = await get_client()
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
            logger.warning("No groups found!")
            return
        logger.info(f"Sending to {len(groups)} groups...")
        cycle_count = 0
        while True:
            for group in groups:
                try:
                    await client.send_message(group, MESSAGE)
                    logger.info(f"✅ {group.title}")
                    account_stats['total_sent'] = account_stats.get('total_sent', 0) + 1
                    save_data()
                except FloodWaitError as e:
                    logger.warning(f"Flood wait: {e.seconds}s")
                    await asyncio.sleep(e.seconds)
                except Exception as e:
                    logger.warning(f"Error: {e}")
                await asyncio.sleep(random.randint(MIN_INTERVAL, MAX_INTERVAL))
            cycle_count += 1
            logger.info(f"✅ Cycle {cycle_count} complete. Waiting {CYCLE_WAIT}s...")
            
            # Reconnect every 10 cycles to keep session fresh
            if cycle_count % 10 == 0:
                logger.info("🔄 Reconnecting to refresh session...")
                await client.disconnect()
                await asyncio.sleep(3)
                client = await get_client()
                # Re-fetch groups
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
                logger.info(f"🔄 Reconnected. {len(groups)} groups found.")
            
            await asyncio.sleep(CYCLE_WAIT)
    except asyncio.CancelledError:
        logger.info("⏹️ Stopped")
    except Exception as e:
        logger.error(f"Error: {e}")
    finally:
        running_task = None

async def start(update: Update, context):
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        await update.message.reply_text("❌ অনুমতি নেই!")
        return
    running = running_task is not None and not running_task.done()
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("▶️ চালু করুন", callback_data='start_msg')],
        [InlineKeyboardButton("⏹️ বন্ধ করুন", callback_data='stop_msg')],
        [InlineKeyboardButton("📊 স্ট্যাটাস", callback_data='status')],
        [InlineKeyboardButton("⚙️ সেটিংস", callback_data='settings')],
        [InlineKeyboardButton("👥 গ্রুপ লিস্ট", callback_data='groups')],
        [InlineKeyboardButton("🔄 Session Refresh", callback_data='refresh')]
    ])
    await update.message.reply_text(
        f"🤖 *ম্যাসেজিং বট*\n\n"
        f"{'🟢 চলছে' if running else '🔴 বন্ধ'}\n"
        f"📝 `{MESSAGE}`\n"
        f"⚡ {MIN_INTERVAL}-{MAX_INTERVAL}s | সাইকেল {CYCLE_WAIT}s\n"
        f"📊 মোট পাঠিয়েছে: {account_stats.get('total_sent', 0)}",
        parse_mode='Markdown', reply_markup=kb
    )

async def button_handler(update: Update, context):
    query = update.callback_query
    await query.answer()
    if query.from_user.id != OWNER_ID:
        return
    global running_task, MESSAGE, MIN_INTERVAL, MAX_INTERVAL, CYCLE_WAIT

    if query.data == 'start_msg':
        if running_task and not running_task.done():
            await query.edit_message_text("✅ ইতিমধ্যে চলছে!")
        else:
            running_task = asyncio.create_task(run_messaging())
            await query.edit_message_text("▶️ ম্যাসেজিং শুরু হয়েছে!")

    elif query.data == 'stop_msg':
        if running_task and not running_task.done():
            running_task.cancel()
            running_task = None
        await query.edit_message_text("⏹️ বন্ধ করা হয়েছে!")

    elif query.data == 'status':
        running = running_task is not None and not running_task.done()
        await query.edit_message_text(
            f"📊 *স্ট্যাটাস*\n\n"
            f"চলছে: {'✅ হ্যাঁ' if running else '❌ না'}\n"
            f"📝 ম্যাসেজ: `{MESSAGE}`\n"
            f"⏱️ ডেল: {MIN_INTERVAL}-{MAX_INTERVAL}s\n"
            f"🔄 সাইকেল: {CYCLE_WAIT}s\n"
            f"📨 মোট পাঠিয়েছে: {account_stats.get('total_sent', 0)}",
            parse_mode='Markdown'
        )

    elif query.data == 'settings':
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✏️ ম্যাসেজ পরিবর্তন", callback_data='edit_msg')],
            [InlineKeyboardButton("⏱️ স্পিড সেটিংস", callback_data='edit_speed')],
            [InlineKeyboardButton("🔙 ফিরে", callback_data='back_main')]
        ])
        await query.edit_message_text("⚙️ *সেটিংস*", parse_mode='Markdown', reply_markup=kb)

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
        await query.edit_message_text("⏱️ *স্পিড সেটিংস*", parse_mode='Markdown', reply_markup=kb)

    elif query.data == 'set_min':
        context.user_data['awaiting'] = 'min'
        await query.edit_message_text(f"মিনিমাম ডেল সেকেন্ড দিন (বর্তমান: {MIN_INTERVAL}):")

    elif query.data == 'set_max':
        context.user_data['awaiting'] = 'max'
        await query.edit_message_text(f"ম্যাক্সিমাম ডেল সেকেন্ড দিন (বর্তমান: {MAX_INTERVAL}):")

    elif query.data == 'set_cycle':
        context.user_data['awaiting'] = 'cycle'
        await query.edit_message_text(f"সাইকেল ওয়েট সেকেন্ড দিন (বর্তমান: {CYCLE_WAIT}):")

    elif query.data == 'groups':
        await query.edit_message_text("👥 *গ্রুপ লিস্ট*\nলোড হচ্ছে... অপেক্ষা করুন...", parse_mode='Markdown')
        try:
            client = await get_client()
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

    elif query.data == 'refresh':
        await query.edit_message_text("🔄 Session রিফ্রেশ করা হচ্ছে...")
        try:
            client = await get_client()
            await client.disconnect()
            await query.edit_message_text("✅ Session রিফ্রেশ সফল!")
        except Exception as e:
            await query.edit_message_text(f"❌ Session Error: {str(e)[:100]}")

    elif query.data == 'back_main':
        running = running_task is not None and not running_task.done()
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("▶️ চালু করুন", callback_data='start_msg')],
            [InlineKeyboardButton("⏹️ বন্ধ করুন", callback_data='stop_msg')],
            [InlineKeyboardButton("📊 স্ট্যাটাস", callback_data='status')],
            [InlineKeyboardButton("⚙️ সেটিংস", callback_data='settings')],
            [InlineKeyboardButton("👥 গ্রুপ লিস্ট", callback_data='groups')],
            [InlineKeyboardButton("🔄 Session Refresh", callback_data='refresh')]
        ])
        await query.edit_message_text(
            f"🤖 *ম্যাসেজিং বট*\n\n"
            f"{'🟢 চলছে' if running else '🔴 বন্ধ'}\n"
            f"📝 `{MESSAGE}`\n"
            f"⚡ {MIN_INTERVAL}-{MAX_INTERVAL}s | সাইকেল {CYCLE_WAIT}s\n"
            f"📊 মোট পাঠিয়েছে: {account_stats.get('total_sent', 0)}",
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
        await update.message.reply_text(f"✅ ম্যাসেজ আপডেট!\n\n`{MESSAGE}`", parse_mode='Markdown')

    elif awaiting == 'min':
        try:
            v = int(text)
            if v < MAX_INTERVAL:
                MIN_INTERVAL = v
                await update.message.reply_text(f"✅ মিন সেট: {v}s")
            else:
                await update.message.reply_text(f"❌ মিন {MAX_INTERVAL} এর কম হবে!")
        except:
            await update.message.reply_text("❌ শুধু সংখ্যা দিন!")
        context.user_data['awaiting'] = None

    elif awaiting == 'max':
        try:
            v = int(text)
            if v > MIN_INTERVAL:
                MAX_INTERVAL = v
                await update.message.reply_text(f"✅ ম্যাক্স সেট: {v}s")
            else:
                await update.message.reply_text(f"❌ ম্যাক্স {MIN_INTERVAL} এর বেশি হবে!")
        except:
            await update.message.reply_text("❌ শুধু সংখ্যা দিন!")
        context.user_data['awaiting'] = None

    elif awaiting == 'cycle':
        try:
            v = int(text)
            CYCLE_WAIT = v
            await update.message.reply_text(f"✅ সাইকেল সেট: {v}s")
        except:
            await update.message.reply_text("❌ শুধু সংখ্যা দিন!")
        context.user_data['awaiting'] = None

async def main():
    logger.info("🚀 বট শুরু হচ্ছে...")
    load_data()
    try:
        client = await get_client()
        await client.disconnect()
        logger.info("✅ Session verified!")
    except Exception as e:
        logger.error(f"❌ Session failed: {e}")
        sys.exit(1)

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    print("✅ বট চালু! Telegram এ /start দিন")
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
        logger.info("⛔ বন্ধ")
