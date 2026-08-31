#!/usr/bin/env python3
"""
📱 ADVANCED TELEGRAM MASS MESSAGING BOT v2.3
✅ FIXED: Message send ho raha hai ab! (permission check hata diya)
✅ FIXED: Random emoji INSIDE message (random position pe)
✅ FIXED: Har jagah BACK button
✅ NEW: 🧩 Emoji ON/OFF toggle — bot se on/off kar sakte ho
✅ NEW: Emoji setting save hoti hai (restart ke baad bhi yaad rahegi)
✅ Ekadhik messages se random pick
✅ Phone + OTP + 2FA Login
✅ Auto-skip banned channels (actual error aane par)
✅ Backup channel fallback
"""

import sys
import os
import asyncio
import random
import logging
import json
import threading
import httpx
import re
from datetime import datetime
from telethon import TelegramClient, errors
from telethon.sessions import StringSession
from telethon.errors import (
    FloodWaitError,
    SessionPasswordNeededError,
    PhoneCodeInvalidError,
    PhoneCodeExpiredError,
    UserRestrictedError,
    AuthKeyUnregisteredError,
    UserDeactivatedError,
    UserDeactivatedBanError
)
from telethon.tl.functions.messages import GetDialogsRequest
from telethon.tl.types import InputPeerEmpty
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from flask import Flask

# ══════════ LOGGING ══════════
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    force=True,
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

print("=" * 60, flush=True)
print("🤖 MESSAGING BOT v2.3 — EMOJI TOGGLE", flush=True)
print("=" * 60, flush=True)

# ══════════ ENVIRONMENT ══════════
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

# ══════════ CONFIG ══════════
DYNAMIC_ACCOUNTS_FILE = "dynamic_accounts.json"
BACKUP_CHANNELS_FILE = "backup_channels.json"
AUTH_SESSIONS_FILE = "auth_sessions.json"
MESSAGES_FILE = "messages.json"

MESSAGE = os.environ.get("MESSAGE", "𝟭𝟬 𝗠𝗜𝗡 𝗩𝗖 ₹𝟰𝟱 𝗕𝗔𝗕𝗬😘")
MIN_INTERVAL = int(os.environ.get("MIN_INTERVAL", "6"))
MAX_INTERVAL = int(os.environ.get("MAX_INTERVAL", "10"))
CYCLE_WAIT = int(os.environ.get("CYCLE_WAIT", "45"))

# ══════════ MESSAGES ══════════
def load_messages():
    if os.path.exists(MESSAGES_FILE):
        try:
            with open(MESSAGES_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    default_msgs = [MESSAGE]
    save_messages(default_msgs)
    return default_msgs

def save_messages(msgs):
    try:
        with open(MESSAGES_FILE, 'w') as f:
            json.dump(msgs, f, indent=2)
    except:
        pass

def get_random_message():
    msgs = load_messages()
    return random.choice(msgs) if msgs else MESSAGE

# ══════════ EMOJI POOL ══════════
EMOJI_POOL = [
    "❤️","🔥","🥰","💋","😘","💕","🌹","💖","😍","✨",
    "💞","⭐","🌸","💗","🌺","💝","💫","🌟","💓","🎀",
    "😻","💜","💙","💚","💛","🧡","🤎","🖤","🤍","💝",
    "💐","🌷","🌻","🌼","🍷","🍾","🎉","🎊","💎","👑",
    "💄","👠","👜","💍","🌹","🌺","🌸","🌼","🌻","🌷",
    "⭐","🌟","✨","⚡","🔥","💫","🎯","🎲","🎭","🎨",
    "🍫","🍭","🍬","🍰","🎂","🍩","🍪","🧁","🥂","🍸",
    "🎵","🎶","💃","🕺","🤗","😚","😗","😙","😏","💯",
    "💢","💦","💨","🕊️","🌈","☀️","🌙","💥","❤️‍🔥","💘",
    "😎","🤩","🥳","😈","👻","🎃","💀","☠️","👽","🤖",
    "🐱","🐶","🐼","🐯","🦁","🐮","🐷","🐸","🐵","🦊",
    "🍕","🍔","🌮","🍜","🍣","🥟","🍦","🍩","🍪","🧁",
    "⚽","🏀","🏈","🎾","🏐","🎱","🏓","🏸","🥊","🎯",
    "🚗","🚕","🚙","🚌","🏎️","🚓","🚑","🚀","✈️","🚁",
]

# ══════════ GLOBALS ══════════
running_tasks = {}
stop_flags = {}
account_clients = {}
account_stats = {}
banned_channels_cache = {}
phone_login_states = {}
phone_login_states = {}
data_file = "bot_data.json"
EMOJI_ENABLED = True  # 🧩 Emoji ON/OFF toggle

# ══════════ GENERATE UNIQUE MESSAGE ══════════
def generate_unique_message():
    """
    🔥 Emoji MESSAGE ke ANDAR random position pe aayega
    Example: "𝟭𝟬 𝗠𝗜𝗡 𝗩𝗖 ₹𝟰𝟱 𝗕𝗔𝗕𝗬 ❤️😘" ya "🔥 𝟭𝟬 𝗠𝗜𝗡 𝗩𝗖 💋 ₹𝟰𝟱 𝗕𝗔𝗕𝗬"
    Har baar alag!
    
    🧩 NAYA: EMOJI_ENABLED == False ho to original message hi jayega
    """
    base_msg = get_random_message()
    
    # 🧩 Emoji OFF hai to original message hi bhejo
    if not EMOJI_ENABLED:
        return base_msg
    
    # 1-2 random emoji choose karo
    num_emojis = random.randint(1, 2)
    selected = random.sample(EMOJI_POOL, min(num_emojis, len(EMOJI_POOL)))
    emoji_str = " ".join(selected)
    
    # Random position: 0=start, 1=middle, 2=end, 3=before last word, 4=after first word
    position = random.randint(0, 4)
    words = base_msg.split()
    
    if position == 0 or len(words) <= 2:
        # Start mein emoji
        return f"{emoji_str} {base_msg}"
    elif position == 1:
        # End mein emoji
        return f"{base_msg} {emoji_str}"
    elif position == 2:
        # Middle mein
        mid = len(base_msg) // 2
        return f"{base_msg[:mid]} {emoji_str} {base_msg[mid:]}"
    elif position == 3:
        # Last word se pehle
        return f"{' '.join(words[:-1])} {emoji_str} {words[-1]}"
    else:
        # First word ke baad
        return f"{words[0]} {emoji_str} {' '.join(words[1:])}"

# ══════════ FILE HELPERS ══════════
def load_backup_channels():
    if os.path.exists(BACKUP_CHANNELS_FILE):
        try:
            with open(BACKUP_CHANNELS_FILE, 'r') as f:
                return json.load(f)
        except:
            return []
    return []

def save_backup_channels(channels):
    try:
        with open(BACKUP_CHANNELS_FILE, 'w') as f:
            json.dump(channels, f, indent=2)
    except:
        pass

def load_auth_sessions():
    if os.path.exists(AUTH_SESSIONS_FILE):
        try:
            with open(AUTH_SESSIONS_FILE, 'r') as f:
                return json.load(f)
        except:
            return []
    return []

def save_auth_sessions(sessions):
    try:
        with open(AUTH_SESSIONS_FILE, 'w') as f:
            json.dump(sessions, f, indent=2)
    except:
        pass

# ══════════ ENV ACCOUNTS ══════════
ENV_ACCOUNTS = []
acc_configs = [
    ('acc1', API_ID_1, API_HASH_1, SESSION_1),
    ('acc2', API_ID_2, API_HASH_2, SESSION_2),
    ('acc3', API_ID_3, API_HASH_3, SESSION_3),
]

async def init_env_accounts():
    for acc_id, api_id, api_hash, session in acc_configs:
        if api_id and api_hash and session:
            try:
                client = TelegramClient(StringSession(session), api_id, api_hash, receive_updates=False)
                await client.start()
                me = await client.get_me()
                name = me.first_name or f"User{me.id}"
                await client.disconnect()
                ENV_ACCOUNTS.append({
                    'id': acc_id, 'name': name, 'api_id': api_id,
                    'api_hash': api_hash, 'session': session,
                    'type': 'env', 'phone': getattr(me, 'phone', ''),
                })
                print(f"✅ {acc_id}: {name}", flush=True)
            except Exception as e:
                print(f"❌ {acc_id}: {str(e)[:50]}", flush=True)
            await asyncio.sleep(1)

# ══════════ DYNAMIC ACCOUNTS ══════════
def load_dynamic_accounts():
    if os.path.exists(DYNAMIC_ACCOUNTS_FILE):
        try:
            with open(DYNAMIC_ACCOUNTS_FILE, 'r') as f:
                return json.load(f)
        except:
            return []
    return []

def save_dynamic_accounts(accounts):
    try:
        with open(DYNAMIC_ACCOUNTS_FILE, 'w') as f:
            json.dump(accounts, f, indent=2)
    except:
        pass

def get_all_accounts():
    dynamic = load_dynamic_accounts()
    auth = load_auth_sessions()
    auth_accounts = []
    for s in auth:
        auth_accounts.append({
            'id': s['id'], 'name': s.get('name', f"User_{s.get('user_id','?')}"),
            'api_id': s['api_id'], 'api_hash': s['api_hash'],
            'session': s['session_string'], 'type': 'phone_auth',
            'phone': s.get('phone', '')
        })
    return ENV_ACCOUNTS + dynamic + auth_accounts

def add_dynamic_account(name, session_string, api_id=0, api_hash=""):
    accounts = load_dynamic_accounts()
    for acc in accounts:
        if acc['session'] == session_string:
            return False, "Session already exists!"
    new_id = f"acc_dynamic_{len(accounts) + 1}"
    detected_api_id = api_id if api_id else API_ID_1
    detected_api_hash = api_hash if api_hash else API_HASH_1
    accounts.append({
        'id': new_id, 'name': name, 'api_id': detected_api_id,
        'api_hash': detected_api_hash, 'session': session_string,
        'type': 'dynamic'
    })
    save_dynamic_accounts(accounts)
    return True, new_id

def remove_account_by_id(account_id):
    global ENV_ACCOUNTS
    accounts = load_dynamic_accounts()
    for i, acc in enumerate(accounts):
        if acc['id'] == account_id:
            accounts.pop(i)
            save_dynamic_accounts(accounts)
            return True
    auth_sessions = load_auth_sessions()
    for i, acc in enumerate(auth_sessions):
        if acc['id'] == account_id:
            auth_sessions.pop(i)
            save_auth_sessions(auth_sessions)
            return True
    for i, acc in enumerate(ENV_ACCOUNTS):
        if acc['id'] == account_id:
            ENV_ACCOUNTS.pop(i)
            return True
    return False

def refresh_account_stats():
    for acc in get_all_accounts():
        if acc['id'] not in account_stats:
            account_stats[acc['id']] = {'sent': 0, 'running': False, 'failed_channels': []}
            stop_flags[acc['id']] = False

# ══════════ FLASK ══════════
web_app = Flask(__name__)

@web_app.route("/")
def home():
    all_accs = get_all_accounts()
    running_count = sum(1 for acc in all_accs if account_stats.get(acc['id'], {}).get('running', False))
    total_sent = sum(account_stats.get(acc['id'], {}).get('sent', 0) for acc in all_accs)
    emoji_status = "ON" if EMOJI_ENABLED else "OFF"
    return f"✅ Bot v2.3 | Accounts: {len(all_accs)} | Active: {running_count}/{len(all_accs)} | Sent: {total_sent} | Emoji: {emoji_status}"

@web_app.route("/health")
def health():
    return "OK", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    web_app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

# ══════════ DATA PERSISTENCE ══════════
def load_data():
    global MESSAGE, MIN_INTERVAL, MAX_INTERVAL, CYCLE_WAIT, EMOJI_ENABLED
    if os.path.exists(data_file):
        try:
            with open(data_file, 'r') as f:
                d = json.load(f)
                MESSAGE = d.get('message', MESSAGE)
                MIN_INTERVAL = d.get('min_interval', MIN_INTERVAL)
                MAX_INTERVAL = d.get('max_interval', MAX_INTERVAL)
                CYCLE_WAIT = d.get('cycle_wait', CYCLE_WAIT)
                EMOJI_ENABLED = d.get('emoji_enabled', True)  # 🧩 emoji state load
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
        'emoji_enabled': EMOJI_ENABLED,  # 🧩 emoji state save
        'stats': {acc['id']: {'sent': account_stats.get(acc['id'], {}).get('sent', 0)} for acc in get_all_accounts()}
    }
    try:
        with open(data_file, 'w') as f:
            json.dump(data, f, indent=2)
    except:
        pass

# ══════════ TELEGRAM HELPERS ══════════
async def get_client(api_id, api_hash, session_string):
    client = TelegramClient(
        StringSession(session_string),
        api_id,
        api_hash,
        receive_updates=False
    )
    await client.start()
    return client

async def get_groups(client, retry=3):
    for attempt in range(retry):
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
                        groups.append(entity)
                except:
                    pass
            if groups:
                return groups
            await asyncio.sleep(3)
        except Exception as e:
            logger.error(f"Group list error: {e}")
            await asyncio.sleep(3)
    return []

async def is_account_restricted(client):
    try:
        me = await client.get_me()
        if me is None:
            return True, "Account deleted/deactivated"
        return False, None
    except (UserRestrictedError, UserDeactivatedError, UserDeactivatedBanError, AuthKeyUnregisteredError) as e:
        return True, str(e)
    except Exception:
        return False, None

async def try_backup_channels(client, acc):
    backup_channels = load_backup_channels()
    if not backup_channels:
        return 0
    success_count = 0
    for bc in backup_channels:
        try:
            try:
                await client.join_channel(bc['link'])
                await asyncio.sleep(2)
            except:
                pass
            entity = await client.get_entity(bc['link'])
            msg = generate_unique_message()
            await client.send_message(entity, msg)
            acc_id = acc['id']
            account_stats.setdefault(acc_id, {'sent': 0, 'running': False, 'failed_channels': []})
            account_stats[acc_id]['sent'] += 1
            success_count += 1
            logger.info(f"[{acc.get('name', acc_id)}] ✅ Backup: {bc['name']}")
            await asyncio.sleep(random.randint(MIN_INTERVAL, MAX_INTERVAL))
        except:
            continue
    return success_count

async def notify_owner_restricted(acc_name, reason, acc):
    try:
        bot_app = Application.builder().token(BOT_TOKEN).build()
        await bot_app.bot.send_message(
            chat_id=OWNER_ID,
            text=f"🚨 *ACCOUNT RESTRICTED!*\n\n"
                 f"👤 Account: {acc_name}\n"
                 f"❌ Reason: {reason}\n"
                 f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                 f"Auto-logged out.",
            parse_mode='Markdown'
        )
    except:
        pass

# ═══════════════════════════════════════════
# MAIN MESSAGING LOOP
# ═══════════════════════════════════════════
async def run_account_messaging(acc):
    acc_id = acc['id']
    acc_name = acc.get('name', acc_id)
    stop_flags[acc_id] = False
    account_stats.setdefault(acc_id, {'sent': 0, 'running': False, 'failed_channels': []})
    account_stats[acc_id]['running'] = True
    account_stats[acc_id]['failed_channels'] = []
    
    logger.info(f"🚀 [{acc_name}] Starting...")
    
    try:
        client = await get_client(acc['api_id'], acc['api_hash'], acc['session'])
        account_clients[acc_id] = client
        
        me = await client.get_me()
        logger.info(f"✅ [{acc_name}] Logged in: {me.first_name}")
        
        # Check account restriction
        is_restricted, reason = await is_account_restricted(client)
        if is_restricted:
            logger.error(f"❌ [{acc_name}] Restricted: {reason}")
            await notify_owner_restricted(acc_name, reason, acc)
            stop_account(acc_id)
            return
        
        groups = await get_groups(client)
        if not groups:
            logger.warning(f"[{acc_name}] No groups found!")
            account_stats[acc_id]['running'] = False
            return
        
        logger.info(f"[{acc_name}] {len(groups)} groups found")
        cycle_count = 0
        failed_this_cycle = set()
        
        while not stop_flags.get(acc_id, False):
            # 🔥 SHUFFLE groups har cycle mein — alag order mein send hoga
            random.shuffle(groups)
            
            for group in groups:
                if stop_flags.get(acc_id, False):
                    break
                
                # Skip known banned channels (jo pehle error de chuke hain)
                if group.id in banned_channels_cache.get(acc_id, set()):
                    continue
                
                try:
                    # 🧩 UNIQUE MESSAGE (emoji ON ho to andar random position pe)
                    unique_msg = generate_unique_message()
                    
                    # 🔥 DIRECT SEND — NO PERMISSION CHECK!
                    await client.send_message(group, unique_msg)
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
                        
                except errors.UserBannedInChannelError:
                    banned_channels_cache.setdefault(acc_id, set()).add(group.id)
                    failed_this_cycle.add(group.id)
                    logger.warning(f"[{acc_name}] ⛔ Banned in {group.title}")
                    
                except errors.ChatWriteForbiddenError:
                    banned_channels_cache.setdefault(acc_id, set()).add(group.id)
                    failed_this_cycle.add(group.id)
                    logger.warning(f"[{acc_name}] ⛔ Can't write in {group.title}")
                    
                except errors.ChatAdminRequiredError:
                    banned_channels_cache.setdefault(acc_id, set()).add(group.id)
                    failed_this_cycle.add(group.id)
                    logger.warning(f"[{acc_name}] ⛔ Admin required: {group.title}")
                    
                except errors.RPCError as e:
                    err_str = str(e).lower()
                    if any(x in err_str for x in ['ban', 'restrict', 'permission', 'forbidden', 'write']):
                        banned_channels_cache.setdefault(acc_id, set()).add(group.id)
                        failed_this_cycle.add(group.id)
                        logger.warning(f"[{acc_name}] ⛔ {group.title}: {str(e)[:60]}")
                    else:
                        logger.warning(f"[{acc_name}] ⚠️ {group.title}: {str(e)[:80]}")
                        
                except Exception as e:
                    err = str(e).lower()
                    if any(x in err for x in ['admin', "can't write", 'permission', 'forbidden', 'ban', 'restrict']):
                        banned_channels_cache.setdefault(acc_id, set()).add(group.id)
                        failed_this_cycle.add(group.id)
                        logger.warning(f"[{acc_name}] ⛔ Skip {group.title}: {err[:60]}")
                    else:
                        logger.warning(f"[{acc_name}] ⚠️ Error: {err[:80]}")
                
                await asyncio.sleep(random.randint(MIN_INTERVAL, MAX_INTERVAL))
            
            # Re-check account restriction
            is_restricted, reason = await is_account_restricted(client)
            if is_restricted:
                logger.error(f"❌ [{acc_name}] Restricted: {reason}")
                await notify_owner_restricted(acc_name, reason, acc)
                stop_account(acc_id)
                return
            
            # Try backup channels if some failed
            if failed_this_cycle:
                backup_count = await try_backup_channels(client, acc)
                if backup_count > 0:
                    logger.info(f"[{acc_name}] Backup messaged: {backup_count}")
            
            if failed_this_cycle:
                account_stats[acc_id]['failed_channels'] = list(
                    set(account_stats[acc_id].get('failed_channels', [])) | failed_this_cycle
                )
            
            if stop_flags.get(acc_id, False):
                break
            
            failed_this_cycle = set()
            cycle_count += 1
            logger.info(f"[{acc_name}] Cycle {cycle_count} done. Wait {CYCLE_WAIT}s...")
            
            for i in range(CYCLE_WAIT):
                if stop_flags.get(acc_id, False):
                    break
                await asyncio.sleep(1)
            
            # Reconnect every 15 cycles
            if cycle_count % 15 == 0 and not stop_flags.get(acc_id, False):
                logger.info(f"[{acc_name}] Reconnecting...")
                try:
                    await client.disconnect()
                    await asyncio.sleep(3)
                    if not stop_flags.get(acc_id, False):
                        client = await get_client(acc['api_id'], acc['api_hash'], acc['session'])
                        account_clients[acc_id] = client
                        groups = await get_groups(client)
                        logger.info(f"[{acc_name}] Reconnect done. {len(groups)} groups")
                except Exception as e:
                    logger.error(f"[{acc_name}] Reconnect failed: {e}")
    
    except asyncio.CancelledError:
        logger.info(f"[{acc_name}] Stopped")
    except Exception as e:
        logger.error(f"[{acc_name}] Fatal: {e}")
    finally:
        account_stats[acc_id]['running'] = False
        stop_flags[acc_id] = True
        if acc_id in account_clients:
            try:
                await account_clients[acc_id].disconnect()
            except:
                pass
            del account_clients[acc_id]
        logger.info(f"[{acc_name}] Fully stopped")

def stop_account(acc_id):
    stop_flags[acc_id] = True
    if acc_id in running_tasks and not running_tasks[acc_id].done():
        running_tasks[acc_id].cancel()
        try:
            del running_tasks[acc_id]
        except:
            pass
    account_stats[acc_id]['running'] = False

def stop_all_accounts():
    for acc in get_all_accounts():
        stop_account(acc['id'])

async def test_session_only(session_string):
    try:
        if not API_ID_1 or not API_HASH_1:
            return False, "API_ID_1 ya API_HASH_1 set nahi!", None
        client = TelegramClient(StringSession(session_string), API_ID_1, API_HASH_1, receive_updates=False)
        await client.start()
        me = await client.get_me()
        await client.disconnect()
        return True, me.first_name, me.id
    except Exception as e:
        return False, str(e), None

# ═══════════════════════════════════════════
# BOT HANDLERS
# ═══════════════════════════════════════════

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        await update.message.reply_text("❌ অনুমতি নেই!")
        return
    
    all_accs = get_all_accounts()
    total = len(all_accs)
    running = sum(1 for acc in all_accs if account_stats.get(acc['id'], {}).get('running', False))
    total_sent = sum(account_stats.get(acc['id'], {}).get('sent', 0) for acc in all_accs)
    backup_count = len(load_backup_channels())
    msg_count = len(load_messages())
    
    keyboard = [
        [InlineKeyboardButton("▶️ সব চালু", callback_data='start_all'),
         InlineKeyboardButton("⏹️ সব বন্ধ", callback_data='stop_all')],
        [InlineKeyboardButton("📊 স্ট্যাটাস", callback_data='status')],
        [InlineKeyboardButton("⚙️ সেটিংস", callback_data='settings')],
        [InlineKeyboardButton(f"🧩 Emoji: {'ON ✅' if EMOJI_ENABLED else 'OFF ❌'}",
                              callback_data='toggle_emoji')],
        [InlineKeyboardButton("📝 মেসেজ লিস্ট", callback_data='message_list')],
        [InlineKeyboardButton("👥 গ্রুপ লিস্ট", callback_data='groups')],
        [InlineKeyboardButton("➕ Session যোগ", callback_data='add_account')],
        [InlineKeyboardButton("📱 Phone Login", callback_data='phone_login')],
        [InlineKeyboardButton("🗑 একাউন্ট ডিলিট", callback_data='delete_account')],
        [InlineKeyboardButton("📋 একাউন্ট লিস্ট", callback_data='account_list')],
        [InlineKeyboardButton("📂 Backup Channels", callback_data='backup_channels_menu')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    emoji_status = "ON ✅" if EMOJI_ENABLED else "OFF ❌"
    text = (
        f"🤖 *ম্যাসেজিং বট v2.3*\n\n"
        f"🔥 *{msg_count} টি মেসেজ* থেকে random + emoji INSIDE\n"
        f"🧩 Emoji: {emoji_status}\n\n"
        f"📊 একাউন্ট: {total} (চলছে: {running})\n"
        f"⏱️ {MIN_INTERVAL}-{MAX_INTERVAL}s | সাইকেল {CYCLE_WAIT}s\n"
        f"📨 মোট পাঠিয়েছে: {total_sent}\n"
        f"🔄 Backup: {backup_count}"
    )
    await update.message.reply_text(text, parse_mode='Markdown', reply_markup=reply_markup)

# ──── CALLBACK HANDLER ────
async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id != OWNER_ID:
        return
    
    global MESSAGE, MIN_INTERVAL, MAX_INTERVAL, CYCLE_WAIT, EMOJI_ENABLED
    
    # ===== EMOJI TOGGLE 🧩 =====
    elif False:
        pass
    if query.data == 'toggle_emoji':
        EMOJI_ENABLED = not EMOJI_ENABLED
        save_data()
        status = "ON ✅ (emoji message ke andar random position pe)" if EMOJI_ENABLED \
                 else "OFF ❌ (sirf original message jayega)"
        kb = [[InlineKeyboardButton("🔙 ফিরে", callback_data='back_main')]]
        await query.edit_message_text(
            f"🧩 *Emoji: {'ON' if EMOJI_ENABLED else 'OFF'}*\n\n"
            f"Abhi ka mode: {status}",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(kb)
        )
    
    # ===== START ALL =====
    if query.data == 'start_all':
        text_parts = []
        for acc in get_all_accounts():
            acc_id = acc['id']
            if account_stats.get(acc_id, {}).get('running', False):
                text_parts.append(f"✅ {acc.get('name', acc_id)} already running")
            else:
                if acc_id not in stop_flags:
                    stop_flags[acc_id] = False
                stop_flags[acc_id] = False
                task = asyncio.create_task(run_account_messaging(acc))
                running_tasks[acc_id] = task
                text_parts.append(f"▶️ {acc.get('name', acc_id)} started")
        
        msg = "\n".join(text_parts) if text_parts else "❌ Nothing"
        kb = [[InlineKeyboardButton("🔙 ফিরে", callback_data='back_main')]]
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(kb))
    
    # ===== STOP ALL =====
    elif query.data == 'stop_all':
        text_parts = []
        for acc in get_all_accounts():
            acc_id = acc['id']
            if account_stats.get(acc_id, {}).get('running', False):
                stop_account(acc_id)
                text_parts.append(f"⏹️ {acc.get('name', acc_id)} stopping...")
            else:
                text_parts.append(f"❌ {acc.get('name', acc_id)} already stopped")
        
        msg = "\n".join(text_parts)
        kb = [[InlineKeyboardButton("🔙 ফিরে", callback_data='back_main')]]
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(kb))
    
    # ===== STATUS =====
    elif query.data == 'status':
        await show_status(query)
    
    # ===== SETTINGS =====
    elif query.data == 'settings':
        keyboard = [
            [InlineKeyboardButton(f"🧩 Emoji: {'ON ✅' if EMOJI_ENABLED else 'OFF ❌'}",
                                  callback_data='toggle_emoji')],
            [InlineKeyboardButton("📝 মেসেজ লিস্ট ম্যানেজ", callback_data='message_list')],
            [InlineKeyboardButton("⏱️ স্পিড সেটিংস", callback_data='edit_speed')],
            [InlineKeyboardButton("🔙 ফিরে", callback_data='back_main')],
        ]
        msg_count = len(load_messages())
        emoji_status = "ON ✅" if EMOJI_ENABLED else "OFF ❌"
        text = (
            f"⚙️ *সেটিংস*\n\n"
            f"📝 মেসেজ পুলে: {msg_count} টি\n"
            f"🧩 Emoji: {emoji_status}\n"
            f"⏱️ {MIN_INTERVAL}-{MAX_INTERVAL}s | সাইকেল {CYCLE_WAIT}s\n"
            f"🔥 Emoji ON হলে message এর ভিতরে random position এ যুক্ত হয়"
        )
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
    
    # ===== MESSAGE LIST =====
    elif query.data == 'message_list':
        msgs = load_messages()
        text = f"📝 *মেসেজ লিস্ট ({len(msgs)} টি)*\n\n"
        for i, msg in enumerate(msgs, 1):
            short = msg[:30] + "..." if len(msg) > 30 else msg
            text += f"{i}. `{short}`\n"
        emoji_status = "ON ✅ (emoji INSIDE message at random position)" if EMOJI_ENABLED \
                       else "OFF ❌ (sirf original message)"
        text += f"\n🧩 Emoji: {emoji_status}"
        
        keyboard = [
            [InlineKeyboardButton("➕ নতুন মেসেজ যোগ", callback_data='add_message')],
            [InlineKeyboardButton("🗑 মেসেজ ডিলিট", callback_data='delete_message_menu')],
            [InlineKeyboardButton("🔄 রিসেট", callback_data='reset_messages')],
            [InlineKeyboardButton("🔙 ফিরে", callback_data='back_main')],
        ]
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
    
    # ===== ADD MESSAGE =====
    elif query.data == 'add_message':
        context.user_data['awaiting'] = 'add_message'
        await query.edit_message_text(
            f"✏️ *নতুন মেসেজ যোগ করুন*\n\n"
            f"বর্তমানে {len(load_messages())} টি মেসেজ আছে।\n\n"
            f"আপনার নতুন মেসেজ টি লিখুন। এটি **যোগ** হবে (পুরনো থাকবে)।\n\n"
            f"এখন লিখুন:",
            parse_mode='Markdown'
        )
    
    # ===== DELETE MESSAGE =====
    elif query.data == 'delete_message_menu':
        msgs = load_messages()
        if not msgs:
            kb = [[InlineKeyboardButton("🔙 ফিরে", callback_data='message_list')]]
            await query.edit_message_text("❌ কোনো মেসেজ নেই!", reply_markup=InlineKeyboardMarkup(kb))
            return
        keyboard = []
        for i, msg in enumerate(msgs):
            short = msg[:20] + "..." if len(msg) > 20 else msg
            keyboard.append([InlineKeyboardButton(f"{i+1}. {short}", callback_data=f"del_msg_{i}")])
        keyboard.append([InlineKeyboardButton("🔙 ফিরে", callback_data='message_list')])
        await query.edit_message_text("🗑 *ডিলিট করুন:*", parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif query.data.startswith('del_msg_'):
        idx = int(query.data.replace('del_msg_', ''))
        msgs = load_messages()
        if 0 <= idx < len(msgs):
            removed = msgs.pop(idx)
            save_messages(msgs)
            kb = [[InlineKeyboardButton("🔙 ফিরে", callback_data='message_list')]]
            await query.edit_message_text(f"✅ Deleted!\nবাকি: {len(msgs)} টি", reply_markup=InlineKeyboardMarkup(kb))
    
    # ===== RESET MESSAGES =====
    elif query.data == 'reset_messages':
        save_messages([MESSAGE])
        kb = [[InlineKeyboardButton("🔙 ফিরে", callback_data='message_list')]]
        await query.edit_message_text(f"🔄 Reset! 1 টি ডিফল্ট মেসেজ সেট।", reply_markup=InlineKeyboardMarkup(kb))
    
    # ===== SPEED =====
    elif query.data == 'edit_speed':
        keyboard = [
            [InlineKeyboardButton(f"📉 মিন: {MIN_INTERVAL}s", callback_data='set_min')],
            [InlineKeyboardButton(f"📈 ম্যাক্স: {MAX_INTERVAL}s", callback_data='set_max')],
            [InlineKeyboardButton(f"🔄 সাইকেল: {CYCLE_WAIT}s", callback_data='set_cycle')],
            [InlineKeyboardButton("🔙 ফিরে", callback_data='settings')],
        ]
        await query.edit_message_text("⏱️ *স্পিড কন্ট্রোল*", parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif query.data == 'set_min':
        context.user_data['awaiting'] = 'min'
        await query.edit_message_text(f"মিনিমাম ডেল (সেকেন্ড):\nবর্তমান: {MIN_INTERVAL}s")
    
    elif query.data == 'set_max':
        context.user_data['awaiting'] = 'max'
        await query.edit_message_text(f"ম্যাক্সিমাম ডেল (সেকেন্ড):\nবর্তমান: {MAX_INTERVAL}s")
    
    elif query.data == 'set_cycle':
        context.user_data['awaiting'] = 'cycle'
        await query.edit_message_text(f"সাইকেল ওয়েট (সেকেন্ড):\nবর্তমান: {CYCLE_WAIT}s")
    
    # ===== GROUPS =====
    elif query.data == 'groups':
        await query.edit_message_text("👥 লোড হচ্ছে...")
        try:
            all_accs = get_all_accounts()
            if not all_accs:
                kb = [[InlineKeyboardButton("🔙 ফিরে", callback_data='back_main')]]
                await query.edit_message_text("❌ No accounts!", reply_markup=InlineKeyboardMarkup(kb))
                return
            acc = all_accs[0]
            client = await get_client(acc['api_id'], acc['api_hash'], acc['session'])
            groups = await get_groups(client)
            await client.disconnect()
            
            channels = [g for g in groups if hasattr(g, 'broadcast') and g.broadcast]
            regular = [g for g in groups if not (hasattr(g, 'broadcast') and g.broadcast)]
            
            text = f"👥 *গ্রুপ ({len(regular)}) + চ্যানেল ({len(channels)})*\n\n"
            if regular:
                text += "📌 *গ্রুপ:*\n"
                for i, g in enumerate(regular[:30], 1):
                    text += f"{i}. {g.title}\n"
                if len(regular) > 30:
                    text += f"...আরও {len(regular)-30} টি\n"
            if channels:
                text += "\n📢 *চ্যানেল:*\n"
                for i, g in enumerate(channels[:20], 1):
                    text += f"{i}. {g.title}\n"
                if len(channels) > 20:
                    text += f"...আরও {len(channels)-20} টি"
            
            kb = [[InlineKeyboardButton("🔙 ফিরে", callback_data='back_main')]]
            await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb))
        except Exception as e:
            kb = [[InlineKeyboardButton("🔙 ফিরে", callback_data='back_main')]]
            await query.edit_message_text(f"❌ Error: {str(e)[:100]}", reply_markup=InlineKeyboardMarkup(kb))
    
    # ===== BACKUP CHANNELS =====
    elif query.data == 'backup_channels_menu':
        backup_channels = load_backup_channels()
        text = "📂 *ব্যাকআপ চ্যানেল*\n\n"
        if backup_channels:
            for i, bc in enumerate(backup_channels, 1):
                text += f"{i}. {bc.get('
