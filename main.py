#!/usr/bin/env python3
"""
📱 ADVANCED TELEGRAM MASS MESSAGING BOT v4.0
✅ ADMIN SYSTEM (owner-controlled, custom expiry time, auto-stop on expiry)
✅ Plain message + Quote-reply to real user's message
✅ Single cached client per account (two-IP error fix)
✅ Full English UI
✅ Per-user isolated data (admin sees a brand-new bot)
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
print("🤖 MESSAGING BOT v4.0 — ADMIN SYSTEM", flush=True)
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
AUTH_SESSIONS_FILE = "auth_sessions.json"
ADMINS_FILE = "admins.json"

MESSAGE = os.environ.get("MESSAGE", "𝟭𝟬 𝗠𝗜𝗡 𝗩𝗖 ₹𝟰𝟱 𝗕𝗔𝗕𝗬😘")
MIN_INTERVAL = int(os.environ.get("MIN_INTERVAL", "6"))
MAX_INTERVAL = int(os.environ.get("MAX_INTERVAL", "10"))
CYCLE_WAIT = int(os.environ.get("CYCLE_WAIT", "45"))

# ══════════ GLOBALS ══════════
running_tasks = {}
stop_flags = {}
account_clients = {}
account_stats = {}
phone_login_states = {}
data_file = "bot_data.json"

# ══════════ PERMISSIONS ══════════
def is_owner(user_id):
    return user_id == OWNER_ID

def load_admins():
    if os.path.exists(ADMINS_FILE):
        try:
            with open(ADMINS_FILE, 'r') as f:
                return json.load(f)
        except:
            return []
    return []

def save_admins(admins):
    try:
        with open(ADMINS_FILE, 'w') as f:
            json.dump(admins, f, indent=2)
    except:
        pass

def get_admin(user_id):
    for a in load_admins():
        if a['user_id'] == user_id:
            return a
    return None

def is_valid_admin(user_id):
    a = get_admin(user_id)
    if not a:
        return False
    exp = a.get('expires_at')
    if not exp:
        return True  # permanent
    try:
        return datetime.fromisoformat(exp) > datetime.now()
    except:
        return False

def can_use_bot(user_id):
    return is_owner(user_id) or is_valid_admin(user_id)

def remaining_time_str(expires_at):
    if not expires_at:
        return "♾️ Permanent"
    try:
        delta = datetime.fromisoformat(expires_at) - datetime.now()
    except:
        return "?"
    if delta.total_seconds() <= 0:
        return "⛔ EXPIRED"
    days = delta.days
    hours = delta.seconds // 3600
    mins = (delta.seconds % 3600) // 60
    return f"{days}d {hours}h {mins}m left"

def parse_duration(text):
    """'30d' / '12h' / '45m' / 'perm' → datetime or None (permanent)."""
    t = text.strip().lower()
    if t in ('perm', 'permanent', '0', '0d', 'inf'):
        return None
    m = re.match(r'^(\d+)\s*([dhm])?$', t)
    if not m:
        raise ValueError("bad duration")
    n = int(m.group(1))
    unit = m.group(2) or 'd'
    if unit == 'd':
        return datetime.now() + timedelta(days=n)
    if unit == 'h':
        return datetime.now() + timedelta(hours=n)
    return datetime.now() + timedelta(minutes=n)

# ══════════ MESSAGES (per-user pool) ══════════
def messages_file_for(user_id):
    if is_owner(user_id):
        return "messages.json"
    return f"messages_{user_id}.json"

def load_messages_for(user_id):
    f = messages_file_for(user_id)
    if os.path.exists(f):
        try:
            with open(f, 'r') as fh:
                return json.load(fh)
        except:
            pass
    default_msgs = [MESSAGE]
    save_messages_for(user_id, default_msgs)
    return default_msgs

def save_messages_for(user_id, msgs):
    try:
        with open(messages_file_for(user_id), 'w') as fh:
            json.dump(msgs, fh, indent=2)
    except:
        pass

def get_random_message_for(user_id):
    msgs = load_messages_for(user_id)
    return random.choice(msgs) if msgs else MESSAGE

# ══════════ FILE HELPERS ══════════
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

# ══════════ ENV ACCOUNTS (owner only) ══════════
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
                    'owner_id': OWNER_ID,
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

def get_all_accounts(user_id=None):
    dynamic = load_dynamic_accounts()
    auth = load_auth_sessions()
    auth_accounts = []
    for s in auth:
        auth_accounts.append({
            'id': s['id'], 'name': s.get('name', f"User_{s.get('user_id','?')}"),
            'api_id': s['api_id'], 'api_hash': s['api_hash'],
            'session': s['session_string'], 'type': 'phone_auth',
            'phone': s.get('phone', ''), 'owner_id': s.get('owner_id', OWNER_ID),
        })
    accs = ENV_ACCOUNTS + dynamic + auth_accounts
    if user_id is None or user_id == OWNER_ID:
        return accs
    return [a for a in accs if a.get('owner_id') == user_id]

def add_dynamic_account(name, session_string, owner_id, api_id=0, api_hash=""):
    accounts = load_dynamic_accounts()
    for acc in accounts:
        if acc['session'] == session_string:
            return False, "Session already exists!"
    new_id = f"acc_dyn_{owner_id}_{len(accounts) + 1}"
    detected_api_id = api_id if api_id else API_ID_1
    detected_api_hash = api_hash if api_hash else API_HASH_1
    accounts.append({
        'id': new_id, 'name': name, 'api_id': detected_api_id,
        'api_hash': detected_api_hash, 'session': session_string,
        'type': 'dynamic', 'owner_id': owner_id
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

def refresh_account_stats(user_id=None):
    for acc in get_all_accounts(user_id):
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
    admin_count = len(load_admins())
    return f"✅ Bot v4.0 | Accounts: {len(all_accs)} | Active: {running_count}/{len(all_accs)} | Sent: {total_sent} | Admins: {admin_count}"

@web_app.route("/health")
def health():
    return "OK", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    web_app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

# ══════════ DATA PERSISTENCE ══════════
def load_data():
    global MESSAGE, MIN_INTERVAL, MAX_INTERVAL, CYCLE_WAIT
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
        'show_start_to_others': SHOW_START_TO_OTHERS,
        'stats': {acc['id']: {'sent': account_stats.get(acc['id'], {}).get('sent', 0)} for acc in get_all_accounts()}
    }
    try:
        with open(data_file, 'w') as f:
            json.dump(data, f, indent=2)
    except:
        pass

# ══════════ START-VISIBILITY TOGGLE ══════════
SHOW_START_TO_OTHERS = True  # if False → unauthorized users see NOTHING on /start

# ══════════ TELEGRAM HELPERS ══════════
async def get_client(acc):
    acc_id = acc['id']
    old = account_clients.get(acc_id)
    if old is not None:
        try:
            if old.is_connected():
                return old
            await old.disconnect()
        except:
            pass
        del account_clients[acc_id]
    client = TelegramClient(
        StringSession(acc['session']),
        acc['api_id'],
        acc['api_hash'],
        receive_updates=False
    )
    await client.start()
    account_clients[acc_id] = client
    return client

async def disconnect_client(acc_id):
    client = account_clients.pop(acc_id, None)
    if client is not None:
        try:
            await client.disconnect()
        except:
            pass

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

async def get_reply_target(client, group):
    try:
        async for m in client.iter_messages(group, limit=30):
            sender = await m.get_sender()
            if sender is None:
                continue
            if getattr(sender, 'bot', False):
                continue
            if m.from_id is None:
                continue
            return m
    except Exception as e:
        logger.debug(f"Reply target error: {e}")
    return None

async def notify_user(user_id, text):
    try:
        bot_app = Application.builder().token(BOT_TOKEN).build()
        await bot_app.bot.send_message(chat_id=user_id, text=text, parse_mode='Markdown')
    except:
        pass

# ═══════════════════════════════════════════
# MAIN MESSAGING LOOP
# ═══════════════════════════════════════════
async def run_account_messaging(acc, owner_user_id):
    acc_id = acc['id']
    acc_name = acc.get('name', acc_id)
    stop_flags[acc_id] = False
    account_stats.setdefault(acc_id, {'sent': 0, 'running': False, 'failed_channels': []})
    account_stats[acc_id]['running'] = True
    account_stats[acc_id]['failed_channels'] = []

    logger.info(f"🚀 [{acc_name}] Starting... (owner: {owner_user_id})")

    try:
        client = await get_client(acc)

        me = await client.get_me()
        logger.info(f"✅ [{acc_name}] Logged in: {me.first_name}")

        is_restricted, reason = await is_account_restricted(client)
        if is_restricted:
            logger.error(f"❌ [{acc_name}] Restricted: {reason}")
            await notify_user(owner_user_id, f"🚨 *ACCOUNT RESTRICTED!*\n👤 {acc_name}\n❌ {reason}")
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
            # 🔒 If an admin's time expired, stop instantly
            if not is_owner(owner_user_id) and not is_valid_admin(owner_user_id):
                logger.warning(f"[{acc_name}] Admin expired — stopping")
                stop_account(acc_id)
                return

            random.shuffle(groups)

            for group in groups:
                if stop_flags.get(acc_id, False):
                    break

                if group.id in failed_this_cycle:
                    continue

                try:
                    msg = get_random_message_for(owner_user_id)

                    reply_target = await get_reply_target(client, group)
                    if reply_target is not None:
                        await client.send_message(group, msg, reply_to=reply_target.id)
                        logger.info(f"✅ [{acc_name}] → {group.title} (reply)")
                    else:
                        await client.send_message(group, msg)
                        logger.info(f"✅ [{acc_name}] → {group.title} (plain)")

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
                    failed_this_cycle.add(group.id)
                    logger.warning(f"[{acc_name}] ⛔ Banned in {group.title}")

                except errors.ChatWriteForbiddenError:
                    failed_this_cycle.add(group.id)
                    logger.warning(f"[{acc_name}] ⛔ Can't write in {group.title}")

                except errors.ChatAdminRequiredError:
                    failed_this_cycle.add(group.id)
                    logger.warning(f"[{acc_name}] ⛔ Admin required: {group.title}")

                except errors.RPCError as e:
                    err_str = str(e).lower()
                    if any(x in err_str for x in ['ban', 'restrict', 'permission', 'forbidden', 'write']):
                        failed_this_cycle.add(group.id)
                        logger.warning(f"[{acc_name}] ⛔ {group.title}: {str(e)[:60]}")
                    else:
                        logger.warning(f"[{acc_name}] ⚠️ {group.title}: {str(e)[:80]}")

                except Exception as e:
                    err = str(e).lower()
                    if any(x in err for x in ['admin', "can't write", 'permission', 'forbidden', 'ban', 'restrict']):
                        failed_this_cycle.add(group.id)
                        logger.warning(f"[{acc_name}] ⛔ Skip {group.title}: {err[:60]}")
                    else:
                        logger.warning(f"[{acc_name}] ⚠️ Error: {err[:80]}")

                await asyncio.sleep(random.randint(MIN_INTERVAL, MAX_INTERVAL))

            is_restricted, reason = await is_account_restricted(client)
            if is_restricted:
                logger.error(f"❌ [{acc_name}] Restricted: {reason}")
                await notify_user(owner_user_id, f"🚨 *ACCOUNT RESTRICTED!*\n👤 {acc_name}\n❌ {reason}")
                stop_account(acc_id)
                return

            if stop_flags.get(acc_id, False):
                break

            failed_this_cycle = set()
            cycle_count += 1
            logger.info(f"[{acc_name}] Cycle {cycle_count} done. Wait {CYCLE_WAIT}s...")

            for i in range(CYCLE_WAIT):
                if stop_flags.get(acc_id, False):
                    break
                await asyncio.sleep(1)

            if cycle_count % 15 == 0 and not stop_flags.get(acc_id, False):
                logger.info(f"[{acc_name}] Reconnecting...")
                try:
                    await disconnect_client(acc_id)
                    await asyncio.sleep(3)
                    if not stop_flags.get(acc_id, False):
                        client = await get_client(acc)
                        groups = await get_groups(client)
                        logger.info(f"[{acc_name}] Reconnect done. {len(groups)} groups")
                except Exception as e:
                    logger.error(f"[{acc_name}] Reconnect failed: {e}")

    except asyncio.CancelledError:
        logger.info(f"[{acc_name}] Stopped")
    except Exception as e:
        logger.error(f"[{acc_name}] Fatal: {e}")
    finally:
        await disconnect_client(acc_id)
        account_stats[acc_id]['running'] = False
        stop_flags[acc_id] = True
        logger.info(f"[{acc_name}] Fully stopped")

def stop_account(acc_id):
    stop_flags[acc_id] = True
    if acc_id in running_tasks and not running_tasks[acc_id].done():
        running_tasks[acc_id].cancel()
        try:
            del running_tasks[acc_id]
        except:
            pass
    if acc_id in account_stats:
        account_stats[acc_id]['running'] = False

def stop_accounts_of(user_id):
    """Stop every running account belonging to a user (used on admin expiry/delete)."""
    for acc in get_all_accounts(user_id):
        stop_account(acc['id'])
        # force-disconnect too
        asyncio.ensure_future(disconnect_client(acc['id']))

def stop_all_accounts():
    for acc in get_all_accounts():
        stop_account(acc['id'])

async def admin_expiry_checker():
    """👑 Every 60s: stop accounts of expired/deleted admins."""
    while True:
        try:
            await asyncio.sleep(60)
            valid_ids = {OWNER_ID}
            for a in load_admins():
                if is_valid_admin(a['user_id']):
                    valid_ids.add(a['user_id'])
            # any running account whose owner is not valid → stop
            for acc in get_all_accounts():
                oid = acc.get('owner_id', OWNER_ID)
                if oid not in valid_ids and account_stats.get(acc['id'], {}).get('running', False):
                    logger.warning(f"⏰ Admin {oid} expired/deleted — stopping {acc['id']}")
                    stop_account(acc['id'])
                    await disconnect_client(acc['id'])
        except Exception as e:
            logger.error(f"Expiry checker error: {e}")

async def test_session_only(session_string):
    client = None
    try:
        if not API_ID_1 or not API_HASH_1:
            return False, "API_ID_1 or API_HASH_1 not set in env!", None, None
        client = TelegramClient(StringSession(session_string), API_ID_1, API_HASH_1, receive_updates=False)
        await client.start()
        me = await client.get_me()
        fresh_session = client.session.save()
        return True, me.first_name, me.id, fresh_session
    except Exception as e:
        return False, str(e), None, None
    finally:
        if client is not None:
            try: await client.disconnect()
            except: pass

# ═══════════════════════════════════════════
# MENUS
# ═══════════════════════════════════════════
def main_menu_keyboard(user_id):
    if is_owner(user_id):
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("▶️ Start All", callback_data='start_all'),
             InlineKeyboardButton("⏹️ Stop All", callback_data='stop_all')],
            [InlineKeyboardButton("📊 Status", callback_data='status')],
            [InlineKeyboardButton("⚙️ Settings", callback_data='settings')],
            [InlineKeyboardButton("📝 Message List", callback_data='message_list')],
            [InlineKeyboardButton("➕ Add Session", callback_data='add_account')],
            [InlineKeyboardButton("📱 Phone Login", callback_data='phone_login')],
            [InlineKeyboardButton("🗑 Delete Account", callback_data='delete_account')],
            [InlineKeyboardButton("📋 Account List", callback_data='account_list')],
            [InlineKeyboardButton("👑 Admin Panel", callback_data='admin_panel')],
        ])
    else:
        # 👤 Admin menu — no Settings, no Admin Panel
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("▶️ Start All", callback_data='start_all'),
             InlineKeyboardButton("⏹️ Stop All", callback_data='stop_all')],
            [InlineKeyboardButton("📊 Status", callback_data='status')],
            [InlineKeyboardButton("📝 Message List", callback_data='message_list')],
            [InlineKeyboardButton("➕ Add Session", callback_data='add_account')],
            [InlineKeyboardButton("📱 Phone Login", callback_data='phone_login')],
            [InlineKeyboardButton("🗑 Delete Account", callback_data='delete_account')],
            [InlineKeyboardButton("📋 Account List", callback_data='account_list')],
        ])

def main_menu_text(user_id):
    accs = get_all_accounts(user_id)
    total = len(accs)
    running = sum(1 for acc in accs if account_stats.get(acc['id'], {}).get('running', False))
    total_sent = sum(account_stats.get(acc['id'], {}).get('sent', 0) for acc in accs)
    role = "👑 Owner" if is_owner(user_id) else "👤 Admin"
    expiry = ""
    if not is_owner(user_id):
        a = get_admin(user_id)
        expiry = f"\n⏳ Admin time: {remaining_time_str(a.get('expires_at') if a else None)}"
    return (
        f"🤖 *Messaging Bot v4.0*\n"
        f"👤 Role: {role}{expiry}\n\n"
        f"📊 Accounts: {total} (Running: {running})\n"
        f"⏱️ {MIN_INTERVAL}-{MAX_INTERVAL}s | Cycle {CYCLE_WAIT}s\n"
        f"📨 Total Sent: {total_sent}"
    )

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if is_owner(uid) or is_valid_admin(uid):
        refresh_account_stats(uid)
        await update.message.reply_text(
            main_menu_text(uid), parse_mode='Markdown', reply_markup=main_menu_keyboard(uid)
        )
        return
    # 👻 Unauthorized user
    if SHOW_START_TO_OTHERS:
        await update.message.reply_text("🤖 Bot is private. Contact the owner for access.")
    # if toggle OFF → reply NOTHING

# ──── CALLBACK HANDLER ────
async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    uid = query.from_user.id

    # 🔒 permission gate (admin expiry checked live)
    if not (is_owner(uid) or is_valid_admin(uid)):
        if SHOW_START_TO_OTHERS:
            await query.edit_message_text("⛔ Your access has expired or was removed.")
        else:
            await query.edit_message_text("​")
        return

    global MESSAGE, MIN_INTERVAL, MAX_INTERVAL, CYCLE_WAIT, SHOW_START_TO_OTHERS

    # ===== START ALL (own accounts only) =====
    if query.data == 'start_all':
        text_parts = []
        for acc in get_all_accounts(uid):
            acc_id = acc['id']
            if account_stats.get(acc_id, {}).get('running', False):
                text_parts.append(f"✅ {acc.get('name', acc_id)} already running")
            else:
                stop_flags[acc_id] = False
                task = asyncio.create_task(run_account_messaging(acc, uid))
                running_tasks[acc_id] = task
                text_parts.append(f"▶️ {acc.get('name', acc_id)} started")

        msg = "\n".join(text_parts) if text_parts else "❌ No accounts! Add one first."
        kb = [[InlineKeyboardButton("🔙 Back", callback_data='back_main')]]
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(kb))

    # ===== STOP ALL (own accounts) =====
    elif query.data == 'stop_all':
        text_parts = []
        for acc in get_all_accounts(uid):
            acc_id = acc['id']
            if account_stats.get(acc_id, {}).get('running', False):
                stop_account(acc_id)
                text_parts.append(f"⏹️ {acc.get('name', acc_id)} stopping...")
            else:
                text_parts.append(f"❌ {acc.get('name', acc_id)} already stopped")

        msg = "\n".join(text_parts) if text_parts else "❌ No accounts!"
        kb = [[InlineKeyboardButton("🔙 Back", callback_data='back_main')]]
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(kb))

    # ===== STATUS (own accounts) =====
    elif query.data == 'status':
        accs = get_all_accounts(uid)
        total_sent = sum(account_stats.get(acc['id'], {}).get('sent', 0) for acc in accs)

        text = "📊 *Status*\n\n"
        for acc in accs:
            aid = acc['id']
            name = acc.get('name', aid)
            status = '🟢 Running' if account_stats.get(aid, {}).get('running', False) else '🔴 Stopped'
            sent = account_stats.get(aid, {}).get('sent', 0)
            text += f"• {name}: {status} | Sent: {sent}\n"

        if not accs:
            text += "_No accounts yet._\n"

        text += f"\n⏱️ {MIN_INTERVAL}-{MAX_INTERVAL}s | Cycle {CYCLE_WAIT}s"
        text += f"\n📨 Total: {total_sent}"

        kb = [[InlineKeyboardButton("🔙 Back", callback_data='back_main')]]
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb))

    # ══════════════════════════════════
    # 👑 ADMIN PANEL — OWNER ONLY
    # ══════════════════════════════════
    elif query.data == 'admin_panel':
        if not is_owner(uid):
            return
        admins = load_admins()
        text = (
            f"👑 *Admin Panel*\n\n"
            f"👥 Total Admins: {len(admins)}\n\n"
            f"➕ Add: send `USER_ID 30d` (d=days, h=hours, m=minutes, perm=permanent)\n\n"
            f"⏰ Time শেষ হলে admin-এর সব account automatic stop হবে।"
        )
        keyboard = [
            [InlineKeyboardButton("📋 Admin List & Stats", callback_data='admin_list')],
            [InlineKeyboardButton("➕ Add Admin", callback_data='add_admin')],
            [InlineKeyboardButton(f"👻 Start-msg to others: {'ON' if SHOW_START_TO_OTHERS else 'OFF'}",
                                  callback_data='toggle_startmsg')],
            [InlineKeyboardButton("🔙 Back", callback_data='back_main')],
        ]
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == 'admin_list':
        if not is_owner(uid):
            return
        admins = load_admins()
        if not admins:
            kb = [[InlineKeyboardButton("🔙 Back", callback_data='admin_panel')]]
            await query.edit_message_text("❌ No admins yet.", reply_markup=InlineKeyboardMarkup(kb))
            return
        text = "📋 *Admins*\n\n"
        keyboard = []
        for a in admins:
            aid = a['user_id']
            accs = get_all_accounts(aid)
            running = sum(1 for acc in accs if account_stats.get(acc['id'], {}).get('running', False))
            sent = sum(account_stats.get(acc['id'], {}).get('sent', 0) for acc in accs)
            text += (
                f"👤 `{aid}`\n"
                f"   ⏳ {remaining_time_str(a.get('expires_at'))}\n"
                f"   📊 Accounts: {len(accs)} | Running: {running} | Sent: {sent}\n\n"
            )
            keyboard.append([InlineKeyboardButton(f"🗑 Delete {aid}", callback_data=f"del_admin_{aid}")])
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data='admin_panel')])
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data.startswith('del_admin_'):
        if not is_owner(uid):
            return
        target = int(query.data.replace('del_admin_', ''))
        admins = [a for a in load_admins() if a['user_id'] != target]
        save_admins(admins)
        # 🔥 immediate stop of that admin's accounts
        stop_accounts_of(target)
        kb = [[InlineKeyboardButton("🔙 Back", callback_data='admin_list')]]
        await query.edit_message_text(
            f"✅ Admin `{target}` deleted!\nAll their accounts stopped.",
            parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb)
        )

    elif query.data == 'add_admin':
        if not is_owner(uid):
            return
        context.user_data['awaiting'] = 'add_admin'
        await query.edit_message_text(
            "➕ *Add Admin*\n\n"
            "Send: `USER_ID TIME`\n\n"
            "Examples:\n"
            "`123456789 30d` → 30 days\n"
            "`123456789 12h` → 12 hours\n"
            "`123456789 45m` → 45 minutes\n"
            "`123456789 perm` → permanent\n\n"
            "Send now:",
            parse_mode='Markdown'
        )

    elif query.data == 'toggle_startmsg':
        if not is_owner(uid):
            return
        SHOW_START_TO_OTHERS = not SHOW_START_TO_OTHERS
        save_data()
        kb = [[InlineKeyboardButton("🔙 Back", callback_data='admin_panel')]]
        state = "ON — unauthorized users see a notice" if SHOW_START_TO_OTHERS else "OFF — unauthorized users see NOTHING"
        await query.edit_message_text(f"👻 Start-msg: {state}", reply_markup=InlineKeyboardMarkup(kb))

    # ===== SETTINGS — OWNER ONLY =====
    elif query.data == 'settings':
        if not is_owner(uid):
            return
        keyboard = [
            [InlineKeyboardButton("📝 Manage Messages", callback_data='message_list')],
            [InlineKeyboardButton("⏱️ Speed Settings", callback_data='edit_speed')],
            [InlineKeyboardButton("🔙 Back", callback_data='back_main')],
        ]
        text = (
            f"⚙️ *Settings*\n\n"
            f"⏱️ {MIN_INTERVAL}-{MAX_INTERVAL}s | Cycle {CYCLE_WAIT}s\n"
            f"💬 Mode: Quote-reply to user's message"
        )
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

    # ===== MESSAGE LIST (per-user pool) =====
    elif query.data == 'message_list':
        msgs = load_messages_for(uid)
        text = f"📝 *Message List ({len(msgs)})*\n\n"
        for i, msg in enumerate(msgs, 1):
            short = msg[:30] + "..." if len(msg) > 30 else msg
            text += f"{i}. `{short}`\n"

        keyboard = [
            [InlineKeyboardButton("➕ Add Message", callback_data='add_message')],
            [InlineKeyboardButton("🗑 Delete Message", callback_data='delete_message_menu')],
            [InlineKeyboardButton("🔄 Reset", callback_data='reset_messages')],
            [InlineKeyboardButton("🔙 Back", callback_data='back_main')],
        ]
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == 'add_message':
        context.user_data['awaiting'] = 'add_message'
        await query.edit_message_text(
            f"✏️ *Add New Message*\n\n"
            f"Currently {len(load_messages_for(uid))} message(s).\n\n"
            f"Type your new message now:",
            parse_mode='Markdown'
        )

    elif query.data == 'delete_message_menu':
        msgs = load_messages_for(uid)
        if not msgs:
            kb = [[InlineKeyboardButton("🔙 Back", callback_data='message_list')]]
            await query.edit_message_text("❌ No messages!", reply_markup=InlineKeyboardMarkup(kb))
            return
        keyboard = []
        for i, msg in enumerate(msgs):
            short = msg[:20] + "..." if len(msg) > 20 else msg
            keyboard.append([InlineKeyboardButton(f"{i+1}. {short}", callback_data=f"del_msg_{i}")])
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data='message_list')])
        await query.edit_message_text("🗑 *Delete which one?*", parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data.startswith('del_msg_'):
        idx = int(query.data.replace('del_msg_', ''))
        msgs = load_messages_for(uid)
        if 0 <= idx < len(msgs):
            msgs.pop(idx)
            save_messages_for(uid, msgs)
            kb = [[InlineKeyboardButton("🔙 Back", callback_data='message_list')]]
            await query.edit_message_text(f"✅ Deleted!\nRemaining: {len(msgs)}", reply_markup=InlineKeyboardMarkup(kb))

    elif query.data == 'reset_messages':
        save_messages_for(uid, [MESSAGE])
        kb = [[InlineKeyboardButton("🔙 Back", callback_data='message_list')]]
        await query.edit_message_text("🔄 Reset! 1 default message set.", reply_markup=InlineKeyboardMarkup(kb))

    # ===== SPEED — OWNER ONLY =====
    elif query.data == 'edit_speed':
        if not is_owner(uid):
            return
        keyboard = [
            [InlineKeyboardButton(f"📉 Min: {MIN_INTERVAL}s", callback_data='set_min')],
            [InlineKeyboardButton(f"📈 Max: {MAX_INTERVAL}s", callback_data='set_max')],
            [InlineKeyboardButton(f"🔄 Cycle: {CYCLE_WAIT}s", callback_data='set_cycle')],
            [InlineKeyboardButton("🔙 Back", callback_data='settings')],
        ]
        await query.edit_message_text("⏱️ *Speed Control*", parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == 'set_min':
        if not is_owner(uid):
            return
        context.user_data['awaiting'] = 'min'
        await query.edit_message_text(f"Minimum delay (seconds):\nCurrent: {MIN_INTERVAL}s")

    elif query.data == 'set_max':
        if not is_owner(uid):
            return
        context.user_data['awaiting'] = 'max'
        await query.edit_message_text(f"Maximum delay (seconds):\nCurrent: {MAX_INTERVAL}s")

    elif query.data == 'set_cycle':
        if not is_owner(uid):
            return
        context.user_data['awaiting'] = 'cycle'
        await query.edit_message_text(f"Cycle wait (seconds):\nCurrent: {CYCLE_WAIT}s")

    # ===== PHONE LOGIN =====
    elif query.data == 'phone_login':
        context.user_data['awaiting'] = 'phone_number'
        await query.edit_message_text(
            "📱 *Phone Login*\n\n"
            "Send phone number (international format):\n\n"
            "Example: `+8801XXXXXXXXX`\n\n"
            "Send the number now:",
            parse_mode='Markdown'
        )

    # ===== ADD SESSION =====
    elif query.data == 'add_account':
        context.user_data['awaiting'] = 'add_account'
        await query.edit_message_text(
            "📱 *Add Session String*\n\n"
            "Send the **Session String** only.\n\n"
            "⚠️ Make sure the same session is NOT running anywhere else, or it will die permanently.\n\n"
            "Send it now:",
            parse_mode='Markdown'
        )

    # ===== DELETE ACCOUNT (own only) =====
    elif query.data == 'delete_account':
        all_accs = get_all_accounts(uid)
        if not all_accs:
            kb = [[InlineKeyboardButton("🔙 Back", callback_data='back_main')]]
            await query.edit_message_text("❌ No accounts!", reply_markup=InlineKeyboardMarkup(kb))
            return
        keyboard = []
        for acc in all_accs:
            type_icon = {'env': '💚', 'dynamic': '💙', 'phone_auth': '📱'}.get(acc.get('type', ''), '❓')
            display = f"{type_icon} {acc.get('name', acc['id'])[:30]}"
            keyboard.append([InlineKeyboardButton(display, callback_data=f"del_acc_{acc['id']}")])
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data='back_main')])
        await query.edit_message_text("🗑 *Delete which account?*", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data.startswith('del_acc_'):
        acc_id = query.data.replace('del_acc_', '')
        # 🔒 ownership check
        target_acc = None
        for acc in get_all_accounts(uid):
            if acc['id'] == acc_id:
                target_acc = acc
                break
        if target_acc is None:
            await query.edit_message_text("⛔ Not your account!")
            return
        acc_name = target_acc.get('name', acc_id)
        if account_stats.get(acc_id, {}).get('running', False):
            stop_account(acc_id)
            await asyncio.sleep(1)
        if remove_account_by_id(acc_id):
            for d in [account_stats, stop_flags, running_tasks]:
                if acc_id in d:
                    try:
                        del d[acc_id]
                    except:
                        pass
            await disconnect_client(acc_id)
            save_data()
            kb = [[InlineKeyboardButton("🔙 Back", callback_data='back_main')]]
            await query.edit_message_text(f"✅ *{acc_name}* deleted!", parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb))
        else:
            kb = [[InlineKeyboardButton("🔙 Back", callback_data='back_main')]]
            await query.edit_message_text("❌ Failed!", reply_markup=InlineKeyboardMarkup(kb))

    # ===== ACCOUNT LIST (own only) =====
    elif query.data == 'account_list':
        all_accs = get_all_accounts(uid)
        if not all_accs:
            kb = [[InlineKeyboardButton("🔙 Back", callback_data='back_main')]]
            await query.edit_message_text("❌ No accounts!", reply_markup=InlineKeyboardMarkup(kb))
            return
        text = f"📋 *Accounts ({len(all_accs)})*\n\n"
        for i, acc in enumerate(all_accs, 1):
            acc_id = acc['id']
            type_icon = {'env': '💚', 'dynamic': '🔵', 'phone_auth': '📱'}.get(acc.get('type', ''), '❓')
            status = '🟢 Running' if account_stats.get(acc_id, {}).get('running', False) else '🔴 Stopped'
            sent = account_stats.get(acc_id, {}).get('sent', 0)
            text += f"{i}. {type_icon} {acc.get('name', acc_id)} - {status} | Sent: {sent}\n"
        kb = [[InlineKeyboardButton("🔙 Back", callback_data='back_main')]]
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb))

    # ===== BACK MAIN =====
    elif query.data == 'back_main':
        refresh_account_stats(uid)
        await query.edit_message_text(main_menu_text(uid), parse_mode='Markdown', reply_markup=main_menu_keyboard(uid))


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    # 🔒 permission gate
    if not (is_owner(uid) or is_valid_admin(uid)):
        return

    text = update.message.text.strip()
    awaiting = context.user_data.get('awaiting')

    # ===== Add Admin — OWNER ONLY =====
    if awaiting == 'add_admin':
        context.user_data['awaiting'] = None
        if not is_owner(uid):
            return
        try:
            parts = text.split()
            target_id = int(parts[0])
            expires_at = parse_duration(parts[1]) if len(parts) > 1 else None
        except:
            await update.message.reply_text(
                "❌ Wrong format!\nExample: `123456789 30d` or `123456789 perm`",
                parse_mode='Markdown'
            )
            return

        if target_id == OWNER_ID:
            await update.message.reply_text("❌ Owner is already the boss! 😎")
            return

        admins = load_admins()
        for a in admins:
            if a['user_id'] == target_id:
                # update time instead
                a['expires_at'] = expires_at.isoformat() if expires_at else None
                a['updated_at'] = datetime.now().isoformat()
                save_admins(admins)
                kb = [[InlineKeyboardButton("🔙 Back", callback_data='admin_panel')]]
                await update.message.reply_text(
                    f"✅ Admin `{target_id}` time updated!\n⏳ {remaining_time_str(a['expires_at'])}",
                    parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb)
                )
                return

        admins.append({
            'user_id': target_id,
            'expires_at': expires_at.isoformat() if expires_at else None,
            'added_at': datetime.now().isoformat()
        })
        save_admins(admins)
        kb = [[InlineKeyboardButton("🔙 Back", callback_data='admin_panel')]]
        await update.message.reply_text(
            f"✅ *Admin added!*\n\n👤 `{target_id}`\n⏳ {remaining_time_str(expires_at.isoformat() if expires_at else None)}\n\n"
            f"The admin can now use /start.",
            parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb)
        )
        return

    # ===== Add Message =====
    if awaiting == 'add_message':
        context.user_data['awaiting'] = None
        msgs = load_messages_for(uid)
        msgs.append(text)
        save_messages_for(uid, msgs)
        kb = [[InlineKeyboardButton("🔙 Back", callback_data='message_list')]]
        await update.message.reply_text(
            f"✅ *Message added!*\n\n`{text[:40]}...`\n\n📊 Total: {len(msgs)} message(s)",
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
            await update.message.reply_text("❌ Invalid format! Example: `+8801XXXXXXXXX`", parse_mode='Markdown')
            return

        api_id = API_ID_1
        api_hash = API_HASH_1
        if not api_id or not api_hash:
            await update.message.reply_text("❌ API_ID_1 or API_HASH_1 not set in env!")
            return

        status_msg = await update.message.reply_text(f"⏳ Sending OTP to `{phone_number}`...")

        try:
            client = TelegramClient(StringSession(), api_id, api_hash, receive_updates=False)
            await client.connect()
            sent = await client.send_code_request(phone_number)

            login_id = f"login_{datetime.now().strftime('%Y%m%d%H%M%S')}_{random.randint(100,999)}"
            phone_login_states[login_id] = {
                'phone': phone_number, 'api_id': api_id, 'api_hash': api_hash,
                'client': client, 'owner_id': uid,
                'phone_code_hash': sent.phone_code_hash,
            }
            context.user_data['login_id'] = login_id
            context.user_data['awaiting'] = 'otp_code'

            await status_msg.edit_text("✅ OTP sent!\n\nEnter the code (e.g. `12345`):", parse_mode='Markdown')
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
            await update.message.reply_text("❌ Session expired! Use /start")
            return

        state = phone_login_states[login_id]
        client = state['client']
        code = text.strip().replace(' ', '').replace('-', '')

        if not code.isdigit():
            await update.message.reply_text("❌ Numbers only!")
            return

        status_msg = await update.message.reply_text("⏳ Verifying...")

        try:
            await client.sign_in(phone=state['phone'], code=code, phone_code_hash=state['phone_code_hash'])
            me = await client.get_me()
            session_string = client.session.save()
            await client.disconnect()

            auth_sessions = load_auth_sessions()
            new_id = f"phone_{state['owner_id']}_{len(auth_sessions) + 1}"
            auth_sessions.append({
                'id': new_id, 'name': me.first_name or f"User{me.id}",
                'api_id': state['api_id'], 'api_hash': state['api_hash'],
                'session_string': session_string, 'phone': state['phone'],
                'user_id': me.id, 'owner_id': state['owner_id'],
                'login_time': datetime.now().isoformat()
            })
            save_auth_sessions(auth_sessions)
            del phone_login_states[login_id]
            refresh_account_stats(state['owner_id'])

            kb = [[InlineKeyboardButton("🔙 Back", callback_data='back_main')]]
            await status_msg.edit_text(
                f"✅ *Login successful!*\n\n"
                f"👤 {me.first_name}\n🆔 `{me.id}`\n📱 {state['phone']}\n\n"
                f"Total accounts: {len(get_all_accounts(state['owner_id']))}",
                parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb)
            )

        except SessionPasswordNeededError:
            context.user_data['awaiting'] = '2fa_password'
            context.user_data['login_id'] = login_id
            await status_msg.edit_text("🔐 *Enter 2FA password:*", parse_mode='Markdown')
        except PhoneCodeInvalidError:
            await status_msg.edit_text("❌ Wrong OTP! Try /start again")
            try: await client.disconnect()
            except: pass
            del phone_login_states[login_id]
        except PhoneCodeExpiredError:
            await status_msg.edit_text("❌ OTP expired! Try /start again")
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
            await update.message.reply_text("❌ Session expired! Use /start")
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
            new_id = f"phone_{state['owner_id']}_{len(auth_sessions) + 1}"
            auth_sessions.append({
                'id': new_id, 'name': me.first_name or f"User{me.id}",
                'api_id': state['api_id'], 'api_hash': state['api_hash'],
                'session_string': session_string, 'phone': state['phone'],
                'user_id': me.id, 'owner_id': state['owner_id'],
                'login_time': datetime.now().isoformat()
            })
            save_auth_sessions(auth_sessions)
            del phone_login_states[login_id]
            refresh_account_stats(state['owner_id'])

            kb = [[InlineKeyboardButton("🔙 Back", callback_data='back_main')]]
            await status_msg.edit_text(
                f"✅ *2FA Login successful!*\n\n"
                f"👤 {me.first_name}\n🆔 `{me.id}`\n📱 {state['phone']}",
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
            success, name, user_id, fresh_session = await test_session_only(text)
            if not success:
                if 'two different IP' in str(name) or 'AuthKeyUnregistered' in str(name):
                    await status_msg.edit_text(
                        "❌ This session is DEAD (was used from two IPs).\n"
                        "➡️ Use 📱 Phone Login to create a fresh session."
                    )
                else:
                    await status_msg.edit_text(f"❌ Invalid session!\n{name}")
                return
            success, result = add_dynamic_account(name, fresh_session, uid)
            if success:
                refresh_account_stats(uid)
                kb = [[InlineKeyboardButton("🔙 Back", callback_data='back_main')]]
                await status_msg.edit_text(f"✅ Added!\n👤 {name}\n🆔 `{result}`",
                                           parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb))
            else:
                await status_msg.edit_text(f"❌ {result}")
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {str(e)[:200]}")
        return

    # ===== Settings inputs — OWNER ONLY =====
    if not awaiting:
        return

    if awaiting in ('min', 'max', 'cycle') and not is_owner(uid):
        context.user_data['awaiting'] = None
        return

    if awaiting == 'min':
        try:
            v = int(text)
            if v < 1 or v >= MAX_INTERVAL:
                await update.message.reply_text(f"❌ Enter a value between 1-{MAX_INTERVAL-1}!")
            else:
                MIN_INTERVAL = v
                save_data()
                await update.message.reply_text(f"✅ Min set: {v}s")
        except:
            await update.message.reply_text("❌ Numbers only!")
        context.user_data['awaiting'] = None

    elif awaiting == 'max':
        try:
            v = int(text)
            if v <= MIN_INTERVAL:
                await update.message.reply_text(f"❌ Max must be greater than {MIN_INTERVAL}!")
            else:
                MAX_INTERVAL = v
                save_data()
                await update.message.reply_text(f"✅ Max set: {v}s")
        except:
            await update.message.reply_text("❌ Numbers only!")
        context.user_data['awaiting'] = None

    elif awaiting == 'cycle':
        try:
            v = int(text)
            if v < 5:
                await update.message.reply_text("❌ Cycle must be 5 seconds or more!")
            else:
                CYCLE_WAIT = v
                save_data()
                await update.message.reply_text(f"✅ Cycle set: {v}s")
        except:
            await update.message.reply_text("❌ Numbers only!")
        context.user_data['awaiting'] = None


# ═══════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════
async def main():
    global SHOW_START_TO_OTHERS
    print("=" * 50, flush=True)
    print("🤖 BOT v4.0 STARTING", flush=True)
    print("=" * 50, flush=True)

    await init_env_accounts()

    # load saved settings first
    if os.path.exists(data_file):
        try:
            with open(data_file, 'r') as f:
                d = json.load(f)
                SHOW_START_TO_OTHERS = d.get('show_start_to_others', True)
        except:
            pass

    load_data()

    if not load_messages_for(OWNER_ID):
        save_messages_for(OWNER_ID, [MESSAGE])

    for acc in get_all_accounts():
        if acc['id'] not in account_stats:
            account_stats[acc['id']] = {'sent': 0, 'running': False, 'failed_channels': []}
            stop_flags[acc['id']] = False

    admins = load_admins()
    print(f"👑 Owner: {OWNER_ID}", flush=True)
    print(f"👥 Admins: {len(admins)}", flush=True)

    # 🔥 On startup: stop any accounts of expired/deleted admins
    valid_ids = {OWNER_ID}
    for a in admins:
        if is_valid_admin(a['user_id']):
            valid_ids.add(a['user_id'])
    for acc in get_all_accounts():
        if acc.get('owner_id', OWNER_ID) not in valid_ids:
            stop_flags[acc['id']] = True

    # Clear webhook
    for attempt in range(5):
        try:
            httpx.post(f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook?drop_pending_updates=true")
            if attempt == 0: print("✅ Webhook cleared", flush=True)
            await asyncio.sleep(2)
        except:
            pass

    print("🤖 Building bot...", flush=True)
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CallbackQueryHandler(button_click))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    await app.initialize()
    await app.start()

    # 🔥 Start admin expiry checker (auto-stop expired admins)
    asyncio.create_task(admin_expiry_checker())
    print("⏰ Admin expiry checker running", flush=True)

    poll_started = False
    for poll_attempt in range(5):
        try:
            await app.updater.start_polling(
                drop_pending_updates=True,
                timeout=30,
                read_timeout=30,
                connect_timeout=30,
                allowed_updates=Update.ALL_TYPES
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
