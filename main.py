#!/usr/bin/env python3
"""
📱 Telegram Mass Messaging Bot with:
✅ Phone + OTP + 2FA Login
✅ Auto-skip banned/restricted channels
✅ Backup channel fallback when banned
✅ Auto-logout + notification on account restriction
✅ Dynamic account management
✅ Web dashboard
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
from datetime import datetime, timedelta
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
from telethon.tl.types import InputPeerEmpty, Channel, Chat, User
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from flask import Flask, request

# ═══════════════════════════════════════════
# লগিং
# ═══════════════════════════════════════════
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    force=True,
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

print("=" * 60, flush=True)
print("🤖 ADVANCED MESSAGING BOT STARTING...", flush=True)
print("=" * 60, flush=True)

# ═══════════════════════════════════════════
# Environment Variables
# ═══════════════════════════════════════════
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID = int(os.environ.get("OWNER_ID", "0"))

# Default API credentials (used for dynamic accounts)
API_ID_1 = int(os.environ.get("API_ID_1", "0"))
API_HASH_1 = os.environ.get("API_HASH_1", "")
SESSION_1 = os.environ.get("SESSION_1", "")

API_ID_2 = int(os.environ.get("API_ID_2", "0"))
API_HASH_2 = os.environ.get("API_HASH_2", "")
SESSION_2 = os.environ.get("SESSION_2", "")

API_ID_3 = int(os.environ.get("API_ID_3", "0"))
API_HASH_3 = os.environ.get("API_HASH_3", "")
SESSION_3 = os.environ.get("SESSION_3", "")

# ═══════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════
DYNAMIC_ACCOUNTS_FILE = "dynamic_accounts.json"
BACKUP_CHANNELS_FILE = "backup_channels.json"
AUTH_SESSIONS_FILE = "auth_sessions.json"

MESSAGE = os.environ.get("MESSAGE", "𝟭𝟬 𝗠𝗜𝗡 𝗩𝗖 ₹𝟰𝟱 𝗕𝗔𝗕𝗬😘")
MIN_INTERVAL = int(os.environ.get("MIN_INTERVAL", "5"))
MAX_INTERVAL = int(os.environ.get("MAX_INTERVAL", "8"))
CYCLE_WAIT = int(os.environ.get("CYCLE_WAIT", "30"))
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID = int(os.environ.get("OWNER_ID", "0"))

# ═══════════════════════════════════════════
# Backup Channels File Management
# ═══════════════════════════════════════════
def load_backup_channels():
    """Backup channels লোড"""
    if os.path.exists(BACKUP_CHANNELS_FILE):
        try:
            with open(BACKUP_CHANNELS_FILE, 'r') as f:
                return json.load(f)
        except:
            return []
    return []

def save_backup_channels(channels):
    """Backup channels সেভ"""
    try:
        with open(BACKUP_CHANNELS_FILE, 'w') as f:
            json.dump(channels, f, indent=2)
    except Exception as e:
        logger.error(f"Backup channels save error: {e}")

# ═══════════════════════════════════════════
# Auth Sessions File Management
# ═══════════════════════════════════════════
def load_auth_sessions():
    """Phone login session info লোড"""
    if os.path.exists(AUTH_SESSIONS_FILE):
        try:
            with open(AUTH_SESSIONS_FILE, 'r') as f:
                return json.load(f)
        except:
            return []
    return []

def save_auth_sessions(sessions):
    """Phone login session info সেভ"""
    try:
        with open(AUTH_SESSIONS_FILE, 'w') as f:
            json.dump(sessions, f, indent=2)
    except Exception as e:
        logger.error(f"Auth sessions save error: {e}")

# ═══════════════════════════════════════════
# Environment Accounts initialization
# ═══════════════════════════════════════════
ENV_ACCOUNTS = []
acc_configs = [
    ('acc1', API_ID_1, API_HASH_1, SESSION_1),
    ('acc2', API_ID_2, API_HASH_2, SESSION_2),
    ('acc3', API_ID_3, API_HASH_3, SESSION_3),
]

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
                    'type': 'env',
                    'phone': getattr(me, 'phone', ''),
                    'login_method': 'session'  # env accounts use session string
                })
                print(f"✅ {acc_id}: {name}", flush=True)
            except Exception as e:
                print(f"❌ {acc_id}: {str(e)[:50]}", flush=True)
            await asyncio.sleep(1)

# ═══════════════════════════════════════════
# Dynamic Account Management
# ═══════════════════════════════════════════
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
    except Exception as e:
        logger.error(f"Save error: {e}")

def get_all_accounts():
    """সব একাউন্ট (env + dynamic + phone-logged-in)"""
    dynamic = load_dynamic_accounts()
    auth = load_auth_sessions()
    # Convert auth sessions to account format
    auth_accounts = []
    for s in auth:
        auth_accounts.append({
            'id': s['id'],
            'name': s.get('name', f"Phone_{s['phone'][-4:]}"),
            'api_id': s['api_id'],
            'api_hash': s['api_hash'],
            'session': s['session_string'],
            'type': 'phone_auth',
            'phone': s.get('phone', ''),
            'login_method': 'phone'
        })
    return ENV_ACCOUNTS + dynamic + auth_accounts

def add_dynamic_account(name, session_string, api_id=0, api_hash=""):
    accounts = load_dynamic_accounts()
    for acc in accounts:
        if acc['session'] == session_string:
            return False, "এই session ইতিমধ্যে আছে!"
    
    new_id = f"acc_dynamic_{len(accounts) + 1}"
    detected_api_id = api_id if api_id else API_ID_1
    detected_api_hash = api_hash if api_hash else API_HASH_1
    
    accounts.append({
        'id': new_id,
        'name': name,
        'api_id': detected_api_id,
        'api_hash': detected_api_hash,
        'session': session_string,
        'type': 'dynamic',
        'login_method': 'session'
    })
    save_dynamic_accounts(accounts)
    return True, new_id

def remove_account_by_id(account_id):
    """যেকোনো একাউন্ট ডিলিট (env + dynamic + phone_auth)"""
    global ENV_ACCOUNTS
    
    # Dynamic থেকে
    accounts = load_dynamic_accounts()
    for i, acc in enumerate(accounts):
        if acc['id'] == account_id:
            accounts.pop(i)
            save_dynamic_accounts(accounts)
            return True
    
    # Auth sessions থেকে
    auth_sessions = load_auth_sessions()
    for i, acc in enumerate(auth_sessions):
        if acc['id'] == account_id:
            auth_sessions.pop(i)
            save_auth_sessions(auth_sessions)
            return True
    
    # Environment থেকে
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

# ═══════════════════════════════════════════
# Global Variables
# ═══════════════════════════════════════════
running_tasks = {}
stop_flags = {}
account_clients = {}
account_stats = {}
banned_channels_cache = {}  # acc_id -> set of channel_ids that banned/restricted the account
data_file = "bot_data.json"

# ═══════════════════════════════════════════
# Flask Web Server
# ═══════════════════════════════════════════
web_app = Flask(__name__)

@web_app.route("/")
def home():
    all_accs = get_all_accounts()
    running_count = sum(1 for acc in all_accs if account_stats.get(acc['id'], {}).get('running', False))
    total_sent = sum(account_stats.get(acc['id'], {}).get('sent', 0) for acc in all_accs)
    banned_count = sum(len(account_stats.get(acc['id'], {}).get('failed_channels', [])) for acc in all_accs)
    return f"✅ Bot Running | Accounts: {len(all_accs)} | Active: {running_count}/{len(all_accs)} | Total Sent: {total_sent} | Banned/Skipped: {banned_count}"

@web_app.route("/health")
def health():
    return "OK", 200

@web_app.route("/phone_callback", methods=['POST'])
def phone_callback():
    """OTP verification callback from external service (optional)"""
    data = request.json
    if not data:
        return {"error": "No data"}, 400
    phone = data.get('phone')
    code = data.get('code')
    phone_id = data.get('phone_id')
    
    # Store in global waiting codes
    if phone_id in phone_login_states:
        phone_login_states[phone_id]['received_code'] = code
        phone_login_states[phone_id]['code_time'] = datetime.now()
        return {"status": "ok"}, 200
    
    return {"error": "No pending login for this phone_id"}, 404

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    web_app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

# ═══════════════════════════════════════════
# Phone Login State Management
# ═══════════════════════════════════════════
phone_login_states = {}  # phone_id -> {phone, api_id, api_hash, client, step, ...}

# ═══════════════════════════════════════════
# Data Persistence
# ═══════════════════════════════════════════
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

# ═══════════════════════════════════════════
# Telegram Client Helpers
# ═══════════════════════════════════════════
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
    """সব গ্রুপ/চ্যানেল লিস্ট বের করা"""
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
        return groups
    except Exception as e:
        logger.error(f"Group list error: {e}")
        return []

async def is_account_restricted(client):
    """Check if account is restricted/banned globally"""
    try:
        # Try to get self - if account is deactivated/restricted this will fail
        me = await client.get_me()
        if me is None:
            return True, "Account deleted/deactivated"
        return False, None
    except (UserRestrictedError, UserDeactivatedError, UserDeactivatedBanError, AuthKeyUnregisteredError) as e:
        return True, str(e)
    except Exception as e:
        # Other errors might be temporary
        return False, None

async def can_send_to_channel(client, channel_entity, acc_id):
    """
    Check if account can send messages to this channel.
    Returns: (can_send: bool, reason: str)
    """
    try:
        # Try to get my permissions in this chat
        me = await client.get_me()
        permissions = await client.get_permissions(channel_entity, me.id)
        
        if permissions.is_banned:
            banned_channels_cache.setdefault(acc_id, set()).add(channel_entity.id)
            return False, "BANNED"
        
        if permissions.send_messages is False:
            banned_channels_cache.setdefault(acc_id, set()).add(channel_entity.id)
            return False, "NO_SEND_PERMISSION"
            
        return True, None
        
    except errors.ChatWriteForbiddenError:
        banned_channels_cache.setdefault(acc_id, set()).add(channel_entity.id)
        return False, "WRITE_FORBIDDEN"
    except errors.ChatAdminRequiredError:
        banned_channels_cache.setdefault(acc_id, set()).add(channel_entity.id)
        return False, "ADMIN_REQUIRED"
    except errors.UserBannedInChannelError:
        banned_channels_cache.setdefault(acc_id, set()).add(channel_entity.id)
        return False, "USER_BANNED"
    except Exception as e:
        err_str = str(e).lower()
        if any(x in err_str for x in ['banned', 'restricted', 'forbidden', 'permission', 'can\'t write', 'admin']):
            banned_channels_cache.setdefault(acc_id, set()).add(channel_entity.id)
            return False, f"ERROR: {str(e)[:50]}"
        return True, None

async def try_backup_channels(client, acc):
    """
    Try to join and send to backup channels.
    Returns number of backup channels messaged successfully.
    """
    backup_channels = load_backup_channels()
    if not backup_channels:
        return 0
    
    success_count = 0
    for bc in backup_channels:
        try:
            # Try to join if not already
            try:
                await client.join_channel(bc['link'])
                logger.info(f"[{acc.get('name', acc['id'])}] Joined backup channel: {bc['name']}")
                await asyncio.sleep(2)
            except Exception:
                pass  # Already joined or can't join
            
            # Try to send
            entity = await client.get_entity(bc['link'])
            await client.send_message(entity, MESSAGE)
            acc_id = acc['id']
            account_stats.setdefault(acc_id, {'sent': 0, 'running': False, 'failed_channels': []})
            account_stats[acc_id]['sent'] += 1
            success_count += 1
            logger.info(f"[{acc.get('name', acc['id'])}] ✅ Backup success: {bc['name']}")
            await asyncio.sleep(random.randint(MIN_INTERVAL, MAX_INTERVAL))
            
        except Exception as e:
            logger.warning(f"[{acc.get('name', acc['id'])}] Backup failed {bc.get('name', 'unknown')}: {str(e)[:60]}")
            continue
    
    return success_count

# ═══════════════════════════════════════════
# Main Messaging Loop per Account
# ═══════════════════════════════════════════
async def run_account_messaging(acc):
    """একাউন্ট দিয়ে মেসেজ পাঠানো - with smart ban/restriction handling"""
    acc_id = acc['id']
    acc_name = acc.get('name', acc_id)
    stop_flags[acc_id] = False
    account_stats.setdefault(acc_id, {'sent': 0, 'running': False, 'failed_channels': []})
    account_stats[acc_id]['running'] = True
    account_stats[acc_id]['failed_channels'] = []
    
    logger.info(f"🚀 [{acc_name}] শুরু হচ্ছে...")
    
    try:
        client = await get_client(acc['api_id'], acc['api_hash'], acc['session'])
        account_clients[acc_id] = client
        
        me = await client.get_me()
        logger.info(f"✅ [{acc_name}] লগইন: {me.first_name}")
        
        # Check if account itself is restricted
        is_restricted, reason = await is_account_restricted(client)
        if is_restricted:
            logger.error(f"❌ [{acc_name}] Account restricted! Reason: {reason}")
            # Auto-logout and notify
            await notify_owner_restricted(acc_name, reason, acc)
            stop_account(acc_id)
            return
        
        groups = await get_groups(client)
        
        if not groups:
            logger.warning(f"[{acc_name}] কোনো গ্রুপ/চ্যানেল পাওয়া যায়নি!")
            account_stats[acc_id]['running'] = False
            return
        
        logger.info(f"[{acc_name}] {len(groups)} টি গ্রুপ/চ্যানেল পাওয়া গেছে")
        cycle_count = 0
        failed_channels_this_cycle = set()
        
        while not stop_flags.get(acc_id, False):
            for group in groups:
                if stop_flags.get(acc_id, False):
                    break
                
                # Skip if already known as banned
                if group.id in banned_channels_cache.get(acc_id, set()):
                    continue
                
                # Pre-check permissions
                can_send, fail_reason = await can_send_to_channel(client, group, acc_id)
                if not can_send:
                    failed_channels_this_cycle.add(group.id)
                    banned_channels_cache.setdefault(acc_id, set()).add(group.id)
                    logger.warning(f"[{acc_name}] ⛔ Skipping {group.title}: {fail_reason}")
                    continue
                
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
                        
                except errors.ChatWriteForbiddenError:
                    banned_channels_cache.setdefault(acc_id, set()).add(group.id)
                    failed_channels_this_cycle.add(group.id)
                    logger.warning(f"[{acc_name}] ⛔ {group.title}: Write forbidden")
                    
                except errors.UserBannedInChannelError:
                    banned_channels_cache.setdefault(acc_id, set()).add(group.id)
                    failed_channels_this_cycle.add(group.id)
                    logger.warning(f"[{acc_name}] ⛔ {group.title}: User banned")
                    
                except errors.ChatAdminRequiredError:
                    banned_channels_cache.setdefault(acc_id, set()).add(group.id)
                    failed_channels_this_cycle.add(group.id)
                    logger.warning(f"[{acc_name}] ⛔ {group.title}: Admin required")
                    
                except errors.RPCError as e:
                    err_str = str(e).lower()
                    if any(x in err_str for x in ['ban', 'restrict', 'permission', 'forbidden']):
                        banned_channels_cache.setdefault(acc_id, set()).add(group.id)
                        failed_channels_this_cycle.add(group.id)
                        logger.warning(f"[{acc_name}] ⛔ {group.title}: {str(e)[:60]}")
                    else:
                        logger.warning(f"[{acc_name}] ⚠️ {group.title}: {str(e)[:80]}")
                        
                except Exception as e:
                    err = str(e)
                    if "admin privileges" in err.lower() or "can't write" in err.lower():
                        banned_channels_cache.setdefault(acc_id, set()).add(group.id)
                        failed_channels_this_cycle.add(group.id)
                        logger.warning(f"[{acc_name}] ⛔ Skip {group.title}: No permission")
                    else:
                        logger.warning(f"[{acc_name}] ⚠️ Error: {err[:80]}")
                
                await asyncio.sleep(random.randint(MIN_INTERVAL, MAX_INTERVAL))
            
            # Check if account got restricted during this cycle
            is_restricted, reason = await is_account_restricted(client)
            if is_restricted:
                logger.error(f"❌ [{acc_name}] Account restricted during cycle! Reason: {reason}")
                await notify_owner_restricted(acc_name, reason, acc)
                stop_account(acc_id)
                return
            
            # If some channels failed, try backup channels
            if failed_channels_this_cycle:
                backup_count = await try_backup_channels(client, acc)
                if backup_count > 0:
                    logger.info(f"[{acc_name}] Backup channels messaged: {backup_count}")
            
            # Record failed channels
            if failed_channels_this_cycle:
                account_stats[acc_id]['failed_channels'] = list(
                    set(account_stats[acc_id].get('failed_channels', [])) | failed_channels_this_cycle
                )
            
            if stop_flags.get(acc_id, False):
                break
            
            failed_channels_this_cycle = set()
            cycle_count += 1
            logger.info(f"[{acc_name}] সাইকেল {cycle_count} শেষ। {CYCLE_WAIT}s বিরতি...")
            
            for i in range(CYCLE_WAIT):
                if stop_flags.get(acc_id, False):
                    break
                await asyncio.sleep(1)
            
            # Periodic reconnect (every 20 cycles)
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

async def notify_owner_restricted(acc_name, reason, acc):
    """যখন একাউন্ট restricted হয়, ওনারকে নোটিফিকেশন পাঠায়"""
    try:
        app = Application.builder().token(BOT_TOKEN).build()
        await app.bot.send_message(
            chat_id=OWNER_ID,
            text=f"🚨 *ACCOUNT RESTRICTED!*\n\n"
                 f"👤 Account: {acc_name}\n"
                 f"📌 ID: `{acc['id']}`\n"
                 f"❌ Reason: {reason}\n"
                 f"🕐 Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                 f"Account has been auto-logged out and removed from active list.",
            parse_mode='Markdown'
        )
    except:
        pass

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

async def test_session_only(session_string):
    """শুধু Session String দিয়ে টেস্ট"""
    try:
        if not API_ID_1 or not API_HASH_1:
            return False, "API_ID_1 বা API_HASH_1 সেট করা নেই!", None
        
        client = TelegramClient(StringSession(session_string), API_ID_1, API_HASH_1, receive_updates=False)
        await client.start()
        me = await client.get_me()
        await client.disconnect()
        return True, me.first_name, me.id
    except Exception as e:
        return False, str(e), None

# ═══════════════════════════════════════════
# Telegram Bot Handlers
# ═══════════════════════════════════════════

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
    backup_count = len(load_backup_channels())
    
    keyboard = [
        [InlineKeyboardButton("▶️ সব চালু", callback_data='start_all'),
         InlineKeyboardButton("⏹️ সব বন্ধ", callback_data='stop_all')],
        [InlineKeyboardButton("📊 স্ট্যাটাস", callback_data='status')],
        [InlineKeyboardButton("⚙️ সেটিংস", callback_data='settings')],
        [InlineKeyboardButton("👥 গ্রুপ লিস্ট", callback_data='groups')],
        [InlineKeyboardButton("➕ Session যোগ", callback_data='add_account')],
        [InlineKeyboardButton("📱 Phone Login", callback_data='phone_login')],
        [InlineKeyboardButton("🗑 একাউন্ট ডিলিট", callback_data='delete_account')],
        [InlineKeyboardButton("📋 একাউন্ট লিস্ট", callback_data='account_list')],
        [InlineKeyboardButton("📂 Backup Channels", callback_data='backup_channels_menu')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = (
        f"🤖 *অ্যাডভান্সড ব্যাচ মেসেজিং বট*\n\n"
        f"📊 একাউন্ট: {total} (চলছে: {running})\n"
        f"📝 মেসেজ: `{MESSAGE[:35]}...`\n"
        f"⚡ {MIN_INTERVAL}-{MAX_INTERVAL}s | সাইকেল {CYCLE_WAIT}s\n"
        f"📨 মোট পাঠিয়েছে: {total_sent}\n"
        f"🔄 Backup Channels: {backup_count}"
    )
    
    await update.message.reply_text(text, parse_mode='Markdown', reply_markup=reply_markup)

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """বাটন ক্লিক হ্যান্ডলার"""
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id != OWNER_ID:
        return
    
    global MESSAGE, MIN_INTERVAL, MAX_INTERVAL, CYCLE_WAIT
    
    # ── Main Controls ──
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
    
    # ── Settings ──
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
    
    # ── Groups List ──
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
            
            # Separate channels and groups
            channels = [g for g in groups if hasattr(g, 'broadcast') and g.broadcast]
            regular_groups = [g for g in groups if not (hasattr(g, 'broadcast') and g.broadcast)]
            
            text = f"👥 *গ্রুপ ({len(regular_groups)}) + চ্যানেল ({len(channels)})*\n\n"
            
            if regular_groups:
                text += "📌 *গ্রুপ:*\n"
                for i, g in enumerate(regular_groups[:30], 1):
                    text += f"{i}. {g.title}\n"
                if len(regular_groups) > 30:
                    text += f"...আরও {len(regular_groups)-30} টি\n"
            
            if channels:
                text += "\n📢 *চ্যানেল:*\n"
                for i, g in enumerate(channels[:20], 1):
                    text += f"{i}. {g.title}\n"
                if len(channels) > 20:
                    text += f"...আরও {len(channels)-20} টি\n"
            
            keyboard = [[InlineKeyboardButton("🔙 ফিরে", callback_data='back_main')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, parse_mode='Markdown', reply_markup=reply_markup)
        except Exception as e:
            await query.edit_message_text(f"❌ Error: {str(e)[:100]}")
    
    # ── Backup Channels Menu ──
    elif query.data == 'backup_channels_menu':
        backup_channels = load_backup_channels()
        text = "📂 *ব্যাকআপ চ্যানেল*\n\n"
        if backup_channels:
            for i, bc in enumerate(backup_channels, 1):
                text += f"{i}. {bc.get('name', 'Unknown')} - {bc.get('link', 'No link')}\n"
        else:
            text += "কোনো ব্যাকআপ চ্যানেল নেই।\n\n"
        
        text += "\nব্যবহার:\n• ব্যাকআপ চ্যানেল যোগ করুন\n• ব্যান/রেস্ট্রিক্ট হলে অটো জয়েন করে মেসেজ দেবে"
        
        keyboard = [
            [InlineKeyboardButton("➕ Backup যোগ", callback_data='add_backup')],
            [InlineKeyboardButton("🗑 Backup ডিলিট", callback_data='delete_backup')],
            [InlineKeyboardButton("🔙 ফিরে", callback_data='back_main')],
        ]
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif query.data == 'add_backup':
        context.user_data['awaiting'] = 'add_backup'
        await query.edit_message_text(
            "📂 *ব্যাকআপ চ্যানেল যোগ করুন*\n\n"
            "ফরম্যাট: `নাম | চ্যানেল_লিংক`\n\n"
            "যেমন:\n"
            "`My Backup | https://t.me/mychannel`\n"
            "`Backup 2 | @mybackupchannel`\n\n"
            "লিংক/ইউজারনেম সহ পাঠান:",
            parse_mode='Markdown'
        )
    
    elif query.data == 'delete_backup':
        backup_channels = load_backup_channels()
        if not backup_channels:
            await query.edit_message_text(
                "❌ কোনো ব্যাকআপ চ্যানেল নেই!",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 ফিরে", callback_data='back_main')]])
            )
            return
        
        keyboard = []
        for i, bc in enumerate(backup_channels):
            display = f"{i+1}. {bc.get('name', 'Unknown')}"
            if len(display) > 35:
                display = display[:32] + "..."
            keyboard.append([InlineKeyboardButton(display, callback_data=f"del_bc_{i}")])
        keyboard.append([InlineKeyboardButton("🔙 ফিরে", callback_data='backup_channels_menu')])
        
        await query.edit_message_text(
            "🗑 *ডিলিট করার জন্য ব্যাকআপ চ্যানেল নির্বাচন:*",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif query.data.startswith('del_bc_'):
        idx = int(query.data.replace('del_bc_', ''))
        backup_channels = load_backup_channels()
        if 0 <= idx < len(backup_channels):
            removed = backup_channels.pop(idx)
            save_backup_channels(backup_channels)
            await query.edit_message_text(
                f"✅ `{removed.get('name', 'Unknown')}` ডিলিট!",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 ফিরে", callback_data='backup_channels_menu')]])
            )
    
    # ── Phone Login ──
    elif query.data == 'phone_login':
        context.user_data['awaiting'] = 'phone_number'
        await query.edit_message_text(
            "📱 *ফোন লগইন*\n\n"
            "আপনার ফোন নম্বর দিন (ইন্টারন্যাশনাল ফরম্যাটে):\n\n"
            "যেমন: `+8801XXXXXXXXX`\n\n"
            "শুধু ফোন নম্বর লিখুন:",
            parse_mode='Markdown'
        )
    
    # ── Add Account (Session) ──
    elif query.data == 'add_account':
        await query.edit_message_text(
            "📱 *Session String যোগ করুন*\n\n"
            "শুধু **Session String** টা পাঠান।\n\n"
            "Session String বের করার কমান্ড:\n"
            "```\npip install telethon && python -c \"from telethon.sync import TelegramClient; from telethon.sessions import StringSession; c = TelegramClient(StringSession(), API_ID, 'API_HASH'); c.start(); print(c.session.save())\"\n```\n\n"
            "⚠️ API_ID_1 এবং API_HASH_1 ইউজ হবে ডিফল্ট হিসেবে।\n\n"
            "শুধু Session String টা লিখে পাঠান:",
            parse_mode='Markdown'
        )
        context.user_data['awaiting'] = 'add_account'
    
    # ── Delete Account ──
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
            acc_type = acc.get('type', 'unknown')
            type_icon = {
                'env': '💚',
                'dynamic': '💙',
                'phone_auth': '📱'
            }.get(acc_type, '❓')
            display_text = f"{type_icon} {acc_name}"
            if len(display_text) > 35:
                display_text = display_text[:32] + "..."
            keyboard.append([InlineKeyboardButton(display_text, callback_data=f"del_acc_{acc['id']}")])
        keyboard.append([InlineKeyboardButton("🔙 ফিরে", callback_data='back_main')])
        
        await query.edit_message_text(
            "🗑 *ডিলিট করার জন্য একাউন্ট নির্বাচন করুন:*\n\n"
            "💚 = Environment\n💙 = Dynamic Session\n📱 = Phone Login",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
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
            if acc_id in banned_channels_cache:
                del banned_channels_cache[acc_id]
            
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
    
    # ── Account List ──
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
            acc_type = acc.get('type', 'unknown')
            type_icon = {'env': '💚', 'dynamic': '🔵', 'phone_auth': '📱'}.get(acc_type, '❓')
            status = '🟢 চলছে' if account_stats.get(acc_id, {}).get('running', False) else '🔴 বন্ধ'
            sent = account_stats.get(acc_id, {}).get('sent', 0)
            banned = len(banned_channels_cache.get(acc_id, set()))
            text += f"{i}. {type_icon} {acc_name} - {status} | পাঠিয়েছে: {sent} | বাইপাস: {banned}\n"
        
        keyboard = [[InlineKeyboardButton("🔙 ফিরে", callback_data='back_main')]]
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
    
    # ── Back to Main ──
    elif query.data == 'back_main':
        all_accs = get_all_accounts()
        total = len(all_accs)
        running = sum(1 for acc in all_accs if account_stats.get(acc['id'], {}).get('running', False))
        total_sent = sum(account_stats.get(acc['id'], {}).get('sent', 0) for acc in all_accs)
        backup_count = len(load_backup_channels())
        
        keyboard = [
            [InlineKeyboardButton("▶️ সব চালু", callback_data='start_all'),
             InlineKeyboardButton("⏹️ সব বন্ধ", callback_data='stop_all')],
            [InlineKeyboardButton("📊 স্ট্যাটাস", callback_data='status')],
            [InlineKeyboardButton("⚙️ সেটিংস", callback_data='settings')],
            [InlineKeyboardButton("👥 গ্রুপ লিস্ট", callback_data='groups')],
            [InlineKeyboardButton("➕ Session যোগ", callback_data='add_account')],
            [InlineKeyboardButton("📱 Phone Login", callback_data='phone_login')],
            [InlineKeyboardButton("🗑 একাউন্ট ডিলিট", callback_data='delete_account')],
            [InlineKeyboardButton("📋 একাউন্ট লিস্ট", callback_data='account_list')],
            [InlineKeyboardButton("📂 Backup Channels", callback_data='backup_channels_menu')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        text = (
            f"🤖 *অ্যাডভান্সড ব্যাচ মেসেজিং বট*\n\n"
            f"📊 একাউন্ট: {total} (চলছে: {running})\n"
            f"📝 মেসেজ: `{MESSAGE[:35]}...`\n"
            f"⚡ {MIN_INTERVAL}-{MAX_INTERVAL}s | সাইকেল {CYCLE_WAIT}s\n"
            f"📨 মোট পাঠিয়েছে: {total_sent}\n"
            f"🔄 Backup Channels: {backup_count}"
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
        sent = account_stats.get(aid, {}).get('sent', 0)
        banned = len(banned_channels_cache.get(aid, set()))
        text += f"• {name}: {status} | পাঠিয়েছে: {sent} | ⛔ {banned}\n"
    text += f"\n📝 `{MESSAGE[:40]}`"
    text += f"\n⏱️ {MIN_INTERVAL}-{MAX_INTERVAL}s | সাইকেল {CYCLE_WAIT}s"
    text += f"\n📨 মোট: {total_sent}"
    text += f"\n🔄 Backup Channels: {len(load_backup_channels())}"
    
    keyboard = [[InlineKeyboardButton("🔙 ফিরে", callback_data='back_main')]]
    reply_markup =InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=reply_markup)

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """টেক্সট মেসেজ হ্যান্ডলার"""
    if update.effective_user.id != OWNER_ID:
        return
    
    text = update.message.text.strip()
    awaiting = context.user_data.get('awaiting')
    
    # ── Handle Phone Number Input ──
    if awaiting == 'phone_number':
        context.user_data['awaiting'] = None
        
        phone_number = text.strip()
        if not phone_number.startswith('+'):
            phone_number = '+' + phone_number
        
        # Validate phone format
        if not re.match(r'^\+\d{7,15}$', phone_number):
            await update.message.reply_text("❌ ভুল ফোন নম্বর ফরম্যাট!\n\nসঠিক ফরম্যাট: `+8801XXXXXXXXX`", parse_mode='Markdown')
            return
        
        await update.message.reply_text(f"⏳ `{phone_number}` এ OTP পাঠানো হচ্ছে...\n\nআপনার API_ID এবং API_HASH দিন:\nফরম্যাট: `API_ID | API_HASH`\n\nঅথবা শুধু `default` লিখুন (API_ID_1 ও API_HASH_1 ব্যবহার হবে):", parse_mode='Markdown')
        
        # Store phone in user_data
        context.user_data['login_phone'] = phone_number
        context.user_data['awaiting'] = 'api_credentials'
        return
    
    # ── Handle API Credentials ──
    if awaiting == 'api_credentials':
        context.user_data['awaiting'] = None
        phone = context.user_data.get('login_phone')
        
        if text.lower() == 'default':
            api_id = API_ID_1
            api_hash = API_HASH_1
            if not api_id or not api_hash:
                await update.message.reply_text("❌ API_ID_1 বা API_HASH_1 এনভায়রনমেন্টে সেট নেই!\n\nঅনুগ্রহ করে API_ID | API_HASH ফরম্যাটে দিন।")
                return
        else:
            try:
                parts = text.split('|')
                api_id = int(parts[0].strip())
                api_hash = parts[1].strip()
            except:
                await update.message.reply_text("❌ ভুল ফরম্যাট!\n\nসঠিক: `API_ID | API_HASH`\nযেমন: `12345 | 1a2b3c4d5e6f7g8h9i0j1k2l3m4n5o6`")
                return
        
        # Start login process
        status_msg = await update.message.reply_text("⏳ টেলিগ্রামে সংযোগ হচ্ছে...")
        
        try:
            client = TelegramClient(StringSession(), api_id, api_hash, receive_updates=False)
            await client.connect()
            
            # Send code
            sent = await client.send_code_request(phone)
            
            # Generate a unique login ID
            login_id = f"login_{datetime.now().strftime('%Y%m%d%H%M%S')}_{random.randint(100,999)}"
            
            phone_login_states[login_id] = {
                'phone': phone,
                'api_id': api_id,
                'api_hash': api_hash,
                'client': client,
                'step': 'waiting_code',
                'phone_code_hash': sent.phone_code_hash,
                'received_code': None,
                'code_time': None
            }
            
            context.user_data['login_id'] = login_id
            context.user_data['awaiting'] = 'otp_code'
            
            await status_msg.edit_text(
                f"✅ OTP পাঠানো হয়েছে `{phone}` এ!\n\n"
                f"📱 টেলিগ্রাম থেকে OTP কোড টি লিখুন:\n\n"
                f"শুধু কোড টি দিন (যেমন: `12345`):",
                parse_mode='Markdown'
            )
            
        except Exception as e:
            await status_msg.edit_text(f"❌ Error: {str(e)[:200]}")
            try:
                await client.disconnect()
            except:
                pass
        return
    
    # ── Handle OTP Code ──
    if awaiting == 'otp_code':
        context.user_data['awaiting'] = None
        login_id = context.user_data.get('login_id')
        
        if not login_id or login_id not in phone_login_states:
            await update.message.reply_text("❌ Login session expired! আবার শুরু করুন /start")
            return
        
        state = phone_login_states[login_id]
        client = state['client']
        code = text.strip()
        
        # Remove any spaces or dashes
        code = code.replace(' ', '').replace('-', '')
        
        if not code.isdigit():
            await update.message.reply_text("❌ শুধু সংখ্যা দিন! যেমন: `12345`")
            return
        
        status_msg = await update.message.reply_text("⏳ ভেরিফাই করা হচ্ছে...")
        
        try:
            await client.sign_in(
                phone=state['phone'],
                code=code,
                phone_code_hash=state['phone_code_hash']
            )
            
            # Login successful!
            me = await client.get_me()
            session_string = client.session.save()
            await client.disconnect()
            
            # Save to auth sessions
            auth_sessions = load_auth_sessions()
            new_id = f"phone_acc_{len(auth_sessions) + 1}"
            auth_sessions.append({
                'id': new_id,
                'name': me.first_name or f"User{me.id}",
                'api_id': state['api_id'],
                'api_hash': state['api_hash'],
                'session_string': session_string,
                'phone': state['phone'],
                'user_id': me.id,
                'login_time': datetime.now().isoformat()
            })
            save_auth_sessions(auth_sessions)
            
            # Cleanup state
            del phone_login_states[login_id]
            
            # Refresh stats
            refresh_account_stats()
            
            await status_msg.edit_text(
                f"✅ *সফলভাবে লগইন!* 🎉\n\n"
                f"👤 নাম: {me.first_name}\n"
                f"🆔 ইউজার আইডি: `{me.id}`\n"
                f"📱 ফোন: {state['phone']}\n"
                f"🆔 একাউন্ট আইডি: `{new_id}`\n\n"
                f"মোট একাউন্ট: {len(get_all_accounts())}",
                parse_mode='Markdown'
            )
            
        except SessionPasswordNeededError:
            # 2FA required
            context.user_data['awaiting'] = '2fa_password'
            context.user_data['login_id'] = login_id
            await status_msg.edit_text(
                "🔐 *2FA পাসওয়ার্ড প্রয়োজন!*\n\n"
                "আপনার Telegram 2FA পাসওয়ার্ড দিন:",
                parse_mode='Markdown'
            )
            
        except PhoneCodeInvalidError:
            await status_msg.edit_text("❌ ভুল OTP কোড! আবার চেষ্টা করুন /start")
            try:
                await client.disconnect()
            except:
                pass
            del phone_login_states[login_id]
            
        except PhoneCodeExpiredError:
            await status_msg.edit_text("❌ OTP কোড expired! আবার চেষ্টা করুন /start")
            try:
                await client.disconnect()
            except:
                pass
            del phone_login_states[login_id]
            
        except Exception as e:
            await status_msg.edit_text(f"❌ Error: {str(e)[:200]}")
            try:
                await client.disconnect()
            except:
                pass
            del phone_login_states[login_id]
        return
    
    # ── Handle 2FA Password ──
    if awaiting == '2fa_password':
        context.user_data['awaiting'] = None
        login_id = context.user_data.get('login_id')
        
        if not login_id or login_id not in phone_login_states:
            await update.message.reply_text("❌ Login session expired! আবার শুরু করুন /start")
            return
        
        state = phone_login_states[login_id]
        client = state['client']
        password = text.strip()
        
        status_msg = await update.message.reply_text("⏳ 2FA ভেরিফাই করা হচ্ছে...")
        
        try:
            await client.sign_in(password=password)
            
            me = await client.get_me()
            session_string = client.session.save()
            await client.disconnect()
            
            # Save to auth sessions
            auth_sessions = load_auth_sessions()
            new_id = f"phone_acc_{len(auth_sessions) + 1}"
            auth_sessions.append({
                'id': new_id,
                'name': me.first_name or f"User{me.id}",
                'api_id': state['api_id'],
                'api_hash': state['api_hash'],
                'session_string': session_string,
                'phone': state['phone'],
                'user_id': me.id,
                'login_time': datetime.now().isoformat()
            })
            save_auth_sessions(auth_sessions)
            
            del phone_login_states[login_id]
            refresh_account_stats()
            
            await status_msg.edit_text(
                f"✅ *2FA Login সফল!* 🎉\n\n"
                f"👤 নাম: {me.first_name}\n"
                f"🆔 ইউজার: `{me.id}`\n"
                f"📱 ফোন: {state['phone']}\n"
                f"🆔 একাউন্ট: `{new_id}`\n\n"
                f"মোট একাউন্ট: {len(get_all_accounts())}",
                parse_mode='Markdown'
            )
            
        except Exception as e:
            await status_msg.edit_text(f"❌ 2FA Error: {str(e)[:200]}")
            try:
                await client.disconnect()
            except:
                pass
            del phone_login_states[login_id]
        return
    
    # ── Handle Add Account (Session String) ──
    if awaiting == 'add_account':
        context.user_data['awaiting'] = None
        
        try:
            session_string = text
            
            status_msg = await update.message.reply_text("⏳ Session টেস্ট করা হচ্ছে...")
            
            success, name, user_id = await test_session_only(session_string)
            
            if not success:
                await status_msg.edit_text(f"❌ Session ভ্যালিড নয়!\n\nError: {name}")
                return
            
            # একাউন্ট যোগ
            success, result = add_dynamic_account(name, session_string)
            
            if success:
                refresh_account_stats()
                
                new_id = result
                await status_msg.edit_text(
                    f"✅ *একাউন্ট যোগ করা হয়েছে!* 🎉\n\n"
                    f"👤 নাম: {name}\n"
                    f"🆔 আইডি: `{new_id}`\n"
                    f"🆔 ইউজার আইডি: `{user_id}`\n\n"
                    f"মোট একাউন্ট: {len(get_all_accounts())}",
                    parse_mode='Markdown'
                )
            else:
                await status_msg.edit_text(f"❌ যোগ করতে ব্যর্থ!\n\n{result}")
        
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {str(e)[:200]}")
        
        return
    
    # ── Handle Add Backup Channel ──
    if awaiting == 'add_backup':
        context.user_data['awaiting'] = None
        
        try:
            if '|' not in text:
                await update.message.reply_text("❌ ভুল ফরম্যাট!\n\nসঠিক: `নাম | লিংক`\nযেমন: `My Backup | https://t.me/mychannel`")
                return
            
            parts = text.split('|', 1)
            name = parts[0].strip()
            link = parts[1].strip()
            
            # Clean link
            if link.startswith('@'):
                link = f"https://t.me/{link[1:]}"
            
            backup_channels = load_backup_channels()
            backup_channels.append({
                'name': name,
                'link': link,
                'added_at': datetime.now().isoformat()
            })
            save_backup_channels(backup_channels)
            
            await update.message.reply_text(
                f"✅ *ব্যাকআপ চ্যানেল যোগ করা হয়েছে!*\n\n"
                f"📛 নাম: {name}\n"
                f"🔗 লিংক: `{link}`\n"
                f"📊 মোট ব্যাকআপ: {len(backup_channels)}",
                parse_mode='Markdown'
            )
            
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {str(e)[:200]}")
        
        return
    
    # ── Settings Updates ──
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
    print(f"🤖 ADVANCED BOT READY", flush=True)
    print("=" * 50, flush=True)
    
    # Environment accounts থেকে নাম লোড
    print("📂 Environment accounts লোড হচ্ছে...", flush=True)
    await init_env_accounts()
    
    load_data()
    print("📂 ডাটা লোড করা হয়েছে", flush=True)
    
    # ব্যাকআপ চ্যানেল লোড
    backup_channels = load_backup_channels()
    if backup_channels:
        print(f"📂 {len(backup_channels)} টি ব্যাকআপ চ্যানেল লোড করা হয়েছে", flush=True)
    
    # ইনিশিয়াল স্ট্যাটাস
    for acc in get_all_accounts():
        if acc['id'] not in account_stats:
            account_stats[acc['id']] = {'sent': 0, 'running': False, 'failed_channels': []}
            stop_flags[acc['id']] = False
    
    # ডায়নামিক একাউন্ট লোড
    dynamic = load_dynamic_accounts()
    if dynamic:
        print(f"📂 {len(dynamic)} টি ডায়নামিক একাউন্ট লোড করা হয়েছে", flush=True)
    
    # Phone auth একাউন্ট লোড
    auth_sessions = load_auth_sessions()
    if auth_sessions:
        print(f"📂 {len(auth_sessions)} টি Phone Login একাউন্ট লোড করা হয়েছে", flush=True)
    
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
