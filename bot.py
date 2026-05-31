#!/usr/bin/env python3
import os, sys, asyncio, random, logging
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import FloodWaitError
from telethon.tl.functions.messages import GetDialogsRequest
from telethon.tl.types import InputPeerEmpty
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ====== ENVIRONMENT VARIABLES থেকে পড়ুন ======
BOT_TOKEN = os.environ.get("8875386448:AAH2RMJixaVOyLPZkYJayh3WcGVrc5octnA")
OWNER_ID = int(os.environ.get("8001816524", "0"))
API_ID = int(os.environ.get("36952100", "0"))
API_HASH = os.environ.get("21c793e15e6ceef225eeb83e5727d446", "")
SESSION_STRING = os.environ.get("1BVtsOL8Bu2KY_DAs-8av9yWTcpEhFTl3qS72FJp08HyrzwwdCNBw-liieDLN9qj8uFIrccHBFDbDkC3HkmBOJVb698J7zNWGTtq251zfMw6ja4acc5T5OBAc8_xdADt5peeSHIur84v1uU_hCXXeuhs9ixwwOLDB6N7EF4uc3MmYomfsDwCzaptaOO3gcOKJr29hjvpSYKmaDz_tdAQ_LYsnEb1BqXk5OZqsLmTaXH7qqbqrGRMP6mTVBCLf6iUUOgbwe8H7UIdu2idb2SzDZmLSLscYzauci9PzPTsc26K6QXdtCVM4b7jmCrEeuq4nHL8N6Bgyp2l1qPS2Dl798UnDflxAcc4=", "")
MESSAGE = os.environ.get("MESSAGE", "Hello everyone!")
MIN_INTERVAL = int(os.environ.get("MIN_INTERVAL", "1"))
MAX_INTERVAL = int(os.environ.get("MAX_INTERVAL", "2"))
CYCLE_WAIT = int(os.environ.get("CYCLE_WAIT", "15"))
# ==============================================

if not all([BOT_TOKEN, OWNER_ID, API_ID, API_HASH, SESSION_STRING]):
    print("❌ ERROR: Environment variables missing!")
    sys.exit(1)

running_task = None

async def get_client():
    """OTP ছাড়া সরাসরি লগইন হবে SESSION_STRING ব্যবহার করে"""
    client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
    await client.start()  # NO OTP needed!
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
            logger.warning("কোন গ্রুপ পাওয়া যায়নি!")
            return
        
        logger.info(f"{len(groups)} টি গ্রুপে ম্যাসেজ যাচ্ছে...")
        
        while True:
            for group in groups:
                try:
                    await client.send_message(group, MESSAGE)
                    logger.info(f"✅ {group.title}")
                except FloodWaitError as e:
                    await asyncio.sleep(e.seconds)
                except Exception as e:
                    logger.warning(f"Error: {e}")
                await asyncio.sleep(random.randint(MIN_INTERVAL, MAX_INTERVAL))
            logger.info(f"✅ সাইকেল শেষ, {CYCLE_WAIT}s অপেক্ষা...")
            await asyncio.sleep(CYCLE_WAIT)
    except asyncio.CancelledError:
        logger.info("⏹️ বন্ধ")
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
        [InlineKeyboardButton("📊 স্ট্যাটাস", callback_data='status')]
    ])
    
    await update.message.reply_text(
        f"🤖 *ম্যাসেজিং বট*\n\n"
        f"{'🟢 চলছে' if running else '🔴 বন্ধ'}\n"
        f"📝 `{MESSAGE}`\n"
        f"⚡ {MIN_INTERVAL}-{MAX_INTERVAL}s | সাইকেল {CYCLE_WAIT}s",
        parse_mode='Markdown',
        reply_markup=kb
    )

async def button_handler(update: Update, context):
    query = update.callback_query
    await query.answer()
    
    if query.data == 'start_msg':
        global running_task
        if running_task and not running_task.done():
            await query.edit_message_text("✅ ইতিমধ্যে চলছে!")
        else:
            running_task = asyncio.create_task(run_messaging())
            await query.edit_message_text("▶️ ম্যাসেজিং শুরু!")
    
    elif query.data == 'stop_msg':
        if running_task and not running_task.done():
            running_task.cancel()
            running_task = None
        await query.edit_message_text("⏹️ বন্ধ!")
    
    elif query.data == 'status':
        running = running_task is not None and not running_task.done()
        await query.edit_message_text(
            f"📊 *স্ট্যাটাস*\n\n"
            f"চলছে: {'✅ হ্যাঁ' if running else '❌ না'}\n"
            f"ম্যাসেজ: `{MESSAGE}`\n"
            f"ডেল: {MIN_INTERVAL}-{MAX_INTERVAL}s\n"
            f"সাইকেল: {CYCLE_WAIT}s",
            parse_mode='Markdown'
        )

async def main():
    logger.info("🚀 বট শুরু হচ্ছে...")
    
    # Verify session works
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
    
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    
    print("✅ বট চালু! /start দিন টেলিগ্রামে")
    
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
