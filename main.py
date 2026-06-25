#!/usr/bin/env python3
"""
📱 ADVANCED TELEGRAM MASS MESSAGING BOT v2.2
✅ FIXED: Message send ho raha hai ab! (permission check hata diya)
✅ FIXED: Random emoji INSIDE message (random position pe)
✅ FIXED: Har jagah BACK button
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
print("🤖 MESSAGING BOT v2.2 — FIXED", flush=True)
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

# ══════════ GENERATE UNIQUE MESSAGE ══════════
def generate_unique_message():
    """
    🔥 CRITICAL FIX: Emoji ab MESSAGE ke ANDAR random position pe aayega
    Example: "𝟭𝟬 𝗠𝗜𝗡 𝗩𝗖 ₹𝟰𝟱 𝗕𝗔𝗕𝗬 ❤️😘" ya "🔥 𝟭𝟬 𝗠𝗜𝗡 𝗩𝗖 💋 ₹𝟰𝟱 𝗕𝗔𝗕𝗬"
    Har baar alag!
    """
    base_msg = get_random_message()
    
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

# ══════════ GLOBALS ══════════
running_tasks = {}
stop_flags = {}
account_clients = {}
account_stats = {}
banned_channels_cache = {}
phone_login_states = {}
data_file = "bot_data.json"

# ══════════ FLASK ══════════
web_app = Flask(__name__)

@web_app.route("/")
def home():
    all_accs = get_all_accounts()
    running_count = sum(1 for acc in all_accs if account_stats.get(acc['id'], {}).get('running', False))
    total_sent = sum(account_stats.get(acc['id'], {}).get('sent', 0) for acc in all_accs)
    return f"✅ Bot v2.2 | Accounts: {len(all_accs)} | Active: {running_count}/{len(all_accs)} | Sent: {total_sent}"

@web_app.route("/health")
def health():
    return "OK", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    web_app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

# ══════════ DATA PERSISTENCE ══════════
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
# MAIN MESSAGING LOOP — FIXED VERSION
# ═══════════════════════════════════════════
async def run_account_messaging(acc):
    """
    🔥 CRITICAL FIX: Ab pehle permission check nahi karta!
    Direct try karta hai send karne ka. Agar error aata hai TABHI skip karta hai.
    
    PURI PROBLEM: get_permissions() function bar bar None return kar raha tha
    ya exception throw kar raha tha, jis se SARE channels skip ho rahe the.
    
    SOLUTION: Permission check HATA diya. Sirf actual send error par skip karo.
    """
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
                    # 🔥 UNIQUE MESSAGE with emoji INSIDE
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
        [InlineKeyboardButton("📝 মেসেজ লিস্ট", callback_data='message_list')],
        [InlineKeyboardButton("👥 গ্রুপ লিস্ট", callback_data='groups')],
        [InlineKeyboardButton("➕ Session যোগ", callback_data='add_account')],
        [InlineKeyboardButton("📱 Phone Login", callback_data='phone_login')],
        [InlineKeyboardButton("🗑 একাউন্ট ডিলিট", callback_data='delete_account')],
        [InlineKeyboardButton("📋 একাউন্ট লিস্ট", callback_data='account_list')],
        [InlineKeyboardButton("📂 Backup Channels", callback_data='backup_channels_menu')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = (
        f"🤖 *ম্যাসেজিং বট v2.2*\n\n"
        f"🔥 *{msg_count} টি মেসেজ* থেকে random + emoji INSIDE\n\n"
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
    
    global MESSAGE, MIN_INTERVAL, MAX_INTERVAL, CYCLE_WAIT
    
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
            [InlineKeyboardButton("📝 মেসেজ লিস্ট ম্যানেজ", callback_data='message_list')],
            [InlineKeyboardButton("⏱️ স্পিড সেটিংস", callback_data='edit_speed')],
            [InlineKeyboardButton("🔙 ফিরে", callback_data='back_main')],
        ]
        msg_count = len(load_messages())
        text = (
            f"⚙️ *সেটিংস*\n\n"
            f"📝 মেসেজ পুলে: {msg_count} টি\n"
            f"⏱️ {MIN_INTERVAL}-{MAX_INTERVAL}s | সাইকেল {CYCLE_WAIT}s\n"
            f"🔥 Emoji message এর ভিতরে random position এ যুক্ত হয়"
        )
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
    
    # ===== MESSAGE LIST =====
    elif query.data == 'message_list':
        msgs = load_messages()
        text = f"📝 *মেসেজ লিস্ট ({len(msgs)} টি)*\n\n"
        for i, msg in enumerate(msgs, 1):
            short = msg[:30] + "..." if len(msg) > 30 else msg
            text += f"{i}. `{short}`\n"
        text += "\n🔥 Emoji auto INSIDE message at random position"
        
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
                text += f"{i}. {bc.get('name', '?')}\n"
        else:
            text += "কোনো ব্যাকআপ নেই।\n\n"
        text += "\nব্যান/রেস্ট্রিক্ট হলে অটো backup চ্যানেলে মেসেজ দেবে"
        
        keyboard = [
            [InlineKeyboardButton("➕ Backup যোগ", callback_data='add_backup')],
            [InlineKeyboardButton("🗑 Backup ডিলিট", callback_data='delete_backup')],
            [InlineKeyboardButton("🔙 ফিরে", callback_data='back_main')],
        ]
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif query.data == 'add_backup':
        context.user_data['awaiting'] = 'add_backup'
        await query.edit_message_text(
            "📂 *ব্যাকআপ চ্যানেল যোগ*\n\n"
            "ফরম্যাট: `নাম | লিংক`\n"
            "যেমন: `My Backup | https://t.me/mychannel`",
            parse_mode='Markdown'
        )
    
    elif query.data == 'delete_backup':
        backup_channels = load_backup_channels()
        if not backup_channels:
            kb = [[InlineKeyboardButton("🔙 ফিরে", callback_data='back_main')]]
            await query.edit_message_text("❌ No backups!", reply_markup=InlineKeyboardMarkup(kb))
            return
        keyboard = []
        for i, bc in enumerate(backup_channels):
            display = f"{i+1}. {bc.get('name', '?')[:30]}"
            keyboard.append([InlineKeyboardButton(display, callback_data=f"del_bc_{i}")])
        keyboard.append([InlineKeyboardButton("🔙 ফিরে", callback_data='backup_channels_menu')])
        await query.edit_message_text("🗑 *ডিলিট করুন:*", reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif query.data.startswith('del_bc_'):
        idx = int(query.data.replace('del_bc_', ''))
        backup_channels = load_backup_channels()
        if 0 <= idx < len(backup_channels):
            backup_channels.pop(idx)
            save_backup_channels(backup_channels)
            kb = [[InlineKeyboardButton("🔙 ফিরে", callback_data='backup_channels_menu')]]
            await query.edit_message_text(f"✅ Deleted!", reply_markup=InlineKeyboardMarkup(kb))
    
    # ===== PHONE LOGIN =====
    elif query.data == 'phone_login':
        context.user_data['awaiting'] = 'phone_number'
        await query.edit_message_text(
            "📱 *ফোন লগইন*\n\n"
            "ফোন নম্বর দিন (ইন্টারন্যাশনাল):\n\n"
            "যেমন: `+8801XXXXXXXXX`\n\n"
            "⚠️ API_ID_1 ও API_HASH_1 env থেকে auto নিবে।\n\n"
            "শুধু নম্বর লিখুন:",
            parse_mode='Markdown'
        )
    
    # ===== ADD SESSION =====
    elif query.data == 'add_account':
        context.user_data['awaiting'] = 'add_account'
        await query.edit_message_text(
            "📱 *Session String যোগ করুন*\n\n"
            "শুধু **Session String** টা পাঠান।\n\n"
            "API_ID_1 ও API_HASH_1 auto ব্যবহার হবে।\n\n"
            "এখন পাঠান:",
            parse_mode='Markdown'
        )
    
    # ===== DELETE ACCOUNT =====
    elif query.data == 'delete_account':
        all_accs = get_all_accounts()
        if not all_accs:
            kb = [[InlineKeyboardButton("🔙 ফিরে", callback_data='back_main')]]
            await query.edit_message_text("❌ No accounts!", reply_markup=InlineKeyboardMarkup(kb))
            return
        keyboard = []
        for acc in all_accs:
            type_icon = {'env': '💚', 'dynamic': '💙', 'phone_auth': '📱'}.get(acc.get('type', ''), '❓')
            display = f"{type_icon} {acc.get('name', acc['id'])[:30]}"
            keyboard.append([InlineKeyboardButton(display, callback_data=f"del_acc_{acc['id']}")])
        keyboard.append([InlineKeyboardButton("🔙 ফিরে", callback_data='back_main')])
        await query.edit_message_text("🗑 *ডিলিট করুন:*\n💚=Env 💙=Session 📱=Phone", reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif query.data.startswith('del_acc_'):
        acc_id = query.data.replace('del_acc_', '')
        acc_name = acc_id
        for acc in get_all_accounts():
            if acc['id'] == acc_id:
                acc_name = acc.get('name', acc_id)
                break
        if account_stats.get(acc_id, {}).get('running', False):
            stop_account(acc_id)
            await asyncio.sleep(1)
        if remove_account_by_id(acc_id):
            for d in [account_stats, stop_flags, running_tasks, account_clients, banned_channels_cache]:
                if acc_id in d:
                    try:
                        if d is account_clients:
                            await d[acc_id].disconnect()
                    except:
                        pass
                    try:
                        del d[acc_id]
                    except:
                        pass
            save_data()
            kb = [[InlineKeyboardButton("🔙 ফিরে", callback_data='back_main')]]
            await query.edit_message_text(f"✅ *{acc_name}* deleted!", parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb))
        else:
            kb = [[InlineKeyboardButton("🔙 ফিরে", callback_data='back_main')]]
            await query.edit_message_text(f"❌ Failed!", reply_markup=InlineKeyboardMarkup(kb))
    
    # ===== ACCOUNT LIST =====
    elif query.data == 'account_list':
        all_accs = get_all_accounts()
        if not all_accs:
            kb = [[InlineKeyboardButton("🔙 ফিরে", callback_data='back_main')]]
            await query.edit_message_text("❌ No accounts!", reply_markup=InlineKeyboardMarkup(kb))
            return
        text = f"📋 *একাউন্ট ({len(all_accs)})*\n\n"
        for i, acc in enumerate(all_accs, 1):
            acc_id = acc['id']
            type_icon = {'env': '💚', 'dynamic': '🔵', 'phone_auth': '📱'}.get(acc.get('type', ''), '❓')
            status = '🟢 চলছে' if account_stats.get(acc_id, {}).get('running', False) else '🔴 বন্ধ'
            sent = account_stats.get(acc_id, {}).get('sent', 0)
            text += f"{i}. {type_icon} {acc.get('name', acc_id)} - {status} | পাঠিয়েছে: {sent}\n"
        kb = [[InlineKeyboardButton("🔙 ফিরে", callback_data='back_main')]]
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb))
    
    # ===== BACK MAIN =====
    elif query.data == 'back_main':
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
            [InlineKeyboardButton("📝 মেসেজ লিস্ট", callback_data='message_list')],
            [InlineKeyboardButton("👥 গ্রুপ লিস্ট", callback_data='groups')],
            [InlineKeyboardButton("➕ Session যোগ", callback_data='add_account')],
            [InlineKeyboardButton("📱 Phone Login", callback_data='phone_login')],
            [InlineKeyboardButton("🗑 একাউন্ট ডিলিট", callback_data='delete_account')],
            [InlineKeyboardButton("📋 একাউন্ট লিস্ট", callback_data='account_list')],
            [InlineKeyboardButton("📂 Backup Channels", callback_data='backup_channels_menu')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        text = (
            f"🤖 *ম্যাসেজিং বট v2.2*\n\n"
            f"🔥 {msg_count} টি মেসেজ + emoji INSIDE\n\n"
            f"📊 একাউন্ট: {total} (চলছে: {running})\n"
            f"⏱️ {MIN_INTERVAL}-{MAX_INTERVAL}s | সাইকেল {CYCLE_WAIT}s\n"
            f"📨 মোট: {total_sent}\n"
            f"🔄 Backup: {backup_count}"
        )
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=reply_markup)


async def show_status(query):
    """Show status with BACK button"""
    all_accs = get_all_accounts()
    total_sent = sum(account_stats.get(acc['id'], {}).get('sent', 0) for acc in all_accs)
    msg_count = len(load_messages())
    
    text = "📊 *স্ট্যাটাস*\n\n"
    for acc in all_accs:
        aid = acc['id']
        name = acc.get('name', aid)
        status = '🟢 চলছে' if account_stats.get(aid, {}).get('running', False) else '🔴 বন্ধ'
        sent = account_stats.get(aid, {}).get('sent', 0)
        banned = len(banned_channels_cache.get(aid, set()))
        text += f"• {name}: {status} | পাঠিয়েছে: {sent} | ⛔স্কিপ: {banned}\n"
    
    text += f"\n📝 মেসেজ: {msg_count} টি (random + emoji)"
    text += f"\n⏱️ {MIN_INTERVAL}-{MAX_INTERVAL}s | সাইকেল {CYCLE_WAIT}s"
    text += f"\n📨 মোট: {total_sent}"
    text += f"\n🔄 Backup: {len(load_backup_channels())}"
    
    kb = [[InlineKeyboardButton("🔙 ফিরে", callback_data='back_main')]]
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb))


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    
    text = update.message.text.strip()
    awaiting = context.user_data.get('awaiting')
    
    # ===== Add Message =====
    if awaiting == 'add_message':
        context.user_data['awaiting'] = None
        msgs = load_messages()
        msgs.append(text)
        save_messages(msgs)
        kb = [[InlineKeyboardButton("🔙 ফিরে", callback_data='message_list')]]
        await update.message.reply_text(
            f"✅ *মেসেজ যোগ করা হয়েছে!*\n\n"
            f"`{text[:40]}...`\n\n"
            f"📊 মোট: {len(msgs)} টি\n\n"
            f"🔥 Emoji auto INSIDE message at random position",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(kb)
        )
        return
    
    # ===== Phone Number =====
    if awaiting == 'phone_number':
        context.user_data['awaiting'] = None
        phone_number = text.strip()
        if not phone_number.startswith('+'):
            phone_number = '+' + phone_number
        if not re.match(r'^\+\d{7,15}$', phone_number):
            await update.message.reply_text("❌ ভুল ফরম্যাট! যেমন: `+8801XXXXXXXXX`", parse_mode='Markdown')
            return
        
        api_id = API_ID_1
        api_hash = API_HASH_1
        if not api_id or not api_hash:
            await update.message.reply_text("❌ API_ID_1 বা API_HASH_1 env এ সেট নেই!")
            return
        
        status_msg = await update.message.reply_text(f"⏳ `{phone_number}` এ OTP পাঠানো হচ্ছে...")
        
        try:
            client = TelegramClient(StringSession(), api_id, api_hash, receive_updates=False)
            await client.connect()
            sent = await client.send_code_request(phone_number)
            
            login_id = f"login_{datetime.now().strftime('%Y%m%d%H%M%S')}_{random.randint(100,999)}"
            phone_login_states[login_id] = {
                'phone': phone_number, 'api_id': api_id, 'api_hash': api_hash,
                'client': client, 'step': 'waiting_code',
                'phone_code_hash': sent.phone_code_hash,
            }
            context.user_data['login_id'] = login_id
            context.user_data['awaiting'] = 'otp_code'
            
            await status_msg.edit_text(
                f"✅ OTP পাঠানো হয়েছে!\n\nকোড টি লিখুন (যেমন: `12345`):",
                parse_mode='Markdown'
            )
        except Exception as e:
            await status_msg.edit_text(f"❌ Error: {str(e)[:200]}")
            try: await client.disconnect()
            except: pass
        return
    
    # ===== OTP Code =====
    if awaiting == 'otp_code':
        context.user_data['awaiting'] = None
        login_id = context.user_data.get('login_id')
        if not login_id or login_id not in phone_login_states:
            await update.message.reply_text("❌ Session expired! /start করুন")
            return
        
        state = phone_login_states[login_id]
        client = state['client']
        code = text.strip().replace(' ', '').replace('-', '')
        
        if not code.isdigit():
            await update.message.reply_text("❌ শুধু সংখ্যা দিন!")
            return
        
        status_msg = await update.message.reply_text("⏳ ভেরিফাই করা হচ্ছে...")
        
        try:
            await client.sign_in(phone=state['phone'], code=code, phone_code_hash=state['phone_code_hash'])
            me = await client.get_me()
            session_string = client.session.save()
            await client.disconnect()
            
            auth_sessions = load_auth_sessions()
            new_id = f"phone_acc_{len(auth_sessions) + 1}"
            auth_sessions.append({
                'id': new_id, 'name': me.first_name or f"User{me.id}",
                'api_id': state['api_id'], 'api_hash': state['api_hash'],
                'session_string': session_string, 'phone': state['phone'],
                'user_id': me.id, 'login_time': datetime.now().isoformat()
            })
            save_auth_sessions(auth_sessions)
            del phone_login_states[login_id]
            refresh_account_stats()
            
            kb = [[InlineKeyboardButton("🔙 ফিরে", callback_data='back_main')]]
            await status_msg.edit_text(
                f"✅ *সফলভাবে লগইন!*\n\n"
                f"👤 {me.first_name}\n🆔 `{me.id}`\n📱 {state['phone']}\n🆔 `{new_id}`\n\n"
                f"মোট একাউন্ট: {len(get_all_accounts())}",
                parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb)
            )
            
        except SessionPasswordNeededError:
            context.user_data['awaiting'] = '2fa_password'
            context.user_data['login_id'] = login_id
            await status_msg.edit_text("🔐 *2FA পাসওয়ার্ড দিন:*", parse_mode='Markdown')
        except PhoneCodeInvalidError:
            await status_msg.edit_text("❌ ভুল OTP! আবার /start")
            try: await client.disconnect()
            except: pass
            del phone_login_states[login_id]
        except PhoneCodeExpiredError:
            await status_msg.edit_text("❌ OTP expired! আবার /start")
            try: await client.disconnect()
            except: pass
            del phone_login_states[login_id]
        except Exception as e:
            await status_msg.edit_text(f"❌ Error: {str(e)[:200]}")
            try: await client.disconnect()
            except: pass
            del phone_login_states[login_id]
        return
    
    # ===== 2FA Password =====
    if awaiting == '2fa_password':
        context.user_data['awaiting'] = None
        login_id = context.user_data.get('login_id')
        if not login_id or login_id not in phone_login_states:
            await update.message.reply_text("❌ Session expired! /start")
            return
        
        state = phone_login_states[login_id]
        client = state['client']
        status_msg = await update.message.reply_text("⏳ Verifying 2FA...")
        
        try:
            await client.sign_in(password=text.strip())
            me = await client.get_me()
            session_string = client.session.save()
            await client.disconnect()
            
            auth_sessions = load_auth_sessions()
            new_id = f"phone_acc_{len(auth_sessions) + 1}"
            auth_sessions.append({
                'id': new_id, 'name': me.first_name or f"User{me.id}",
                'api_id': state['api_id'], 'api_hash': state['api_hash'],
                'session_string': session_string, 'phone': state['phone'],
                'user_id': me.id, 'login_time': datetime.now().isoformat()
            })
            save_auth_sessions(auth_sessions)
            del phone_login_states[login_id]
            refresh_account_stats()
            
            kb = [[InlineKeyboardButton("🔙 ফিরে", callback_data='back_main')]]
            await status_msg.edit_text(
                f"✅ *2FA Login সফল!*\n\n"
                f"👤 {me.first_name}\n🆔 `{me.id}`\n📱 {state['phone']}\n🆔 `{new_id}`",
                parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb)
            )
        except Exception as e:
            await status_msg.edit_text(f"❌ 2FA Error: {str(e)[:200]}")
            try: await client.disconnect()
            except: pass
            del phone_login_states[login_id]
        return
    
    # ===== Add Session =====
    if awaiting == 'add_account':
        context.user_data['awaiting'] = None
        try:
            status_msg = await update.message.reply_text("⏳ Testing session...")
            success, name, user_id = await test_session_only(text)
            if not success:
                await status_msg.edit_text(f"❌ Invalid session!\n{name}")
                return
            success, result = add_dynamic_account(name, text)
            if success:
                refresh_account_stats()
                kb = [[InlineKeyboardButton("🔙 ফিরে", callback_data='back_main')]]
                await status_msg.edit_text(f"✅ Added!\n👤 {name}\n🆔 `{result}`", parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb))
            else:
                await status_msg.edit_text(f"❌ {result}")
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {str(e)[:200]}")
        return
    
    # ===== Add Backup =====
    if awaiting == 'add_backup':
        context.user_data['awaiting'] = None
        try:
            if '|' not in text:
                await update.message.reply_text("❌ ফরম্যাট: `নাম | লিংক`")
                return
            parts = text.split('|', 1)
            name = parts[0].strip()
            link = parts[1].strip()
            if link.startswith('@'):
                link = f"https://t.me/{link[1:]}"
            backup_channels = load_backup_channels()
            backup_channels.append({'name': name, 'link': link, 'added_at': datetime.now().isoformat()})
            save_backup_channels(backup_channels)
            kb = [[InlineKeyboardButton("🔙 ফিরে", callback_data='backup_channels_menu')]]
            await update.message.reply_text(f"✅ Backup added!\n📛 {name}\n📊 Total: {len(backup_channels)}", reply_markup=InlineKeyboardMarkup(kb))
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {str(e)[:200]}")
        return
    
    # ===== Settings =====
    if not awaiting:
        return
    
    global MESSAGE, MIN_INTERVAL, MAX_INTERVAL, CYCLE_WAIT
    
    if awaiting == 'min':
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


# ═══════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════
async def main():
    print("=" * 50, flush=True)
    print("🤖 BOT v2.2 STARTING", flush=True)
    print("=" * 50, flush=True)
    
    await init_env_accounts()
    load_data()
    
    # Ensure messages
    if not load_messages():
        save_messages([MESSAGE])
    
    for acc in get_all_accounts():
        if acc['id'] not in account_stats:
            account_stats[acc['id']] = {'sent': 0, 'running': False, 'failed_channels': []}
            stop_flags[acc['id']] = False
    
    dynamic = load_dynamic_accounts()
    if dynamic: print(f"📂 {len(dynamic)} dynamic accounts", flush=True)
    auth_sessions = load_auth_sessions()
    if auth_sessions: print(f"📂 {len(auth_sessions)} phone accounts", flush=True)
    
    # Clear webhook
    for attempt in range(5):
        try:
            httpx.post(f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook?drop_pending_updates=true")
            if attempt == 0: print(f"✅ Webhook cleared", flush=True)
            await asyncio.sleep(2)
        except:
            pass
    
    # Clear pending
    for i in range(3):
        try:
            r = httpx.post(f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates", json={"offset": -1, "timeout": 1})
            updates = r.json().get('result', [])
            if updates:
                last_id = updates[-1]['update_id']
                httpx.post(f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates", json={"offset": last_id + 1, "timeout": 1})
                print(f"✅ Pending updates cleared", flush=True)
            await asyncio.sleep(1)
        except:
            pass
    
    print("🤖 Building bot...", flush=True)
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CallbackQueryHandler(button_click))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    await app.initialize()
    await app.start()
    
    # Polling with ALL_TYPES fix
    poll_started = False
    for poll_attempt in range(5):
        try:
            await app.updater.start_polling(
                drop_pending_updates=True,
                timeout=30,
                read_timeout=30,
                connect_timeout=30,
                allowed_updates=Update.ALL_TYPES  # 🔥 CRITICAL FIX
            )
            print("✅✅✅ BOT RUNNING! ✅✅✅", flush=True)
            poll_started = True
            break
        except Exception as e:
            if "Conflict" in str(e):
                print(f"⚠️ Conflict (attempt {poll_attempt+1})", flush=True)
                try:
                    httpx.post(f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook?drop_pending_updates=true")
                except:
                    pass
                await asyncio.sleep(10 * (poll_attempt + 1))
            else:
                print(f"❌ Polling error: {str(e)[:100]}", flush=True)
                await asyncio.sleep(5)
    
    if not poll_started:
        print("❌❌❌ Polling failed!", flush=True)
        return
    
    try:
        await asyncio.Event().wait()
    except asyncio.CancelledError:
        pass
    finally:
        print("🛑 Stopping...", flush=True)
        stop_all_accounts()
        await asyncio.sleep(2)
        try: await app.updater.stop()
        except: pass
        try: await app.stop()
        except: pass
        try: await app.shutdown()
        except: pass


if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    print(f"🌐 Flask on port {os.environ.get('PORT', 10000)}", flush=True)
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("⛔ Interrupted")
    except Exception as e:
        print(f"\n❌ Fatal: {e}", flush=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)
