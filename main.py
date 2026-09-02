#!/usr/bin/env python3
"""
📱 ADVANCED TELEGRAM MASS MESSAGING BOT v4.2
✅ ADMIN SYSTEM (owner-controlled, custom expiry time, auto-stop on expiry)
✅ Flexible time format ('1 day 10 min', '2d 5h', '45m', 'perm')
✅ Admin time EXTENDS (adds to remaining time)
✅ Fixed: account delete bug (unique IDs — no more wrong account deleted!)
✅ Fixed: dead-session now notifies owner instead of failing silently
✅ NEW: 🎨 Profile Setup (name+photo+bio+channels per account, 1-click apply)
✅ NEW: 🗑 Delete All Accounts (with confirm)
✅ Menu: Account List & Message List buttons removed (features still in Settings)
✅ Back buttons on all prompts
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
import uuid
from datetime import datetime, timedelta
from telethon import TelegramClient, errors, functions
from telethon.sessions import StringSession
# ❌ AGE EROKOM CHILO:
# from telethon.tl.functions.account import UpdateProfileRequest, UploadProfilePhotoRequest

# ✅ EKHON EIROKOM KORO:
from telethon.tl.functions.account import UpdateProfileRequest
from telethon.tl.functions.photos import UploadProfilePhotoRequest
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
print("🤖 MESSAGING BOT v4.2 — PROFILE SETUP + FIXES", flush=True)
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
PROFILE_FILE = "profile_configs.json"

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
SHOW_START_TO_OTHERS = True

BACK_KB = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data='back_main')]])

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
        return True
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
    secs = delta.seconds % 60
    parts = []
    if days: parts.append(f"{days}d")
    if hours: parts.append(f"{hours}h")
    if mins: parts.append(f"{mins}m")
    if not days and not hours and secs: parts.append(f"{secs}s")
    return " ".join(parts) + " left" if parts else "<1s left"

def parse_duration(text):
    t = text.strip().lower()
    if t in ('perm', 'permanent', 'inf', 'unlimited', '∞'):
        return None
    t = t.replace('seconds', 's').replace('second', 's').replace('secs', 's').replace('sec', 's')
    t = t.replace('minutes', 'm').replace('minute', 'm').replace('mins', 'm').replace('min', 'm')
    t = t.replace('hours', 'h').replace('hour', 'h').replace('hrs', 'h').replace('hr', 'h')
    t = t.replace('days', 'd').replace('day', 'd')

    total = timedelta()
    found = False
    for num, unit in re.findall(r'(\d+)\s*([dhms])?', t):
        if not num:
            continue
        n = int(num)
        unit = unit or 'm'
        if unit == 'd':
            total += timedelta(days=n)
        elif unit == 'h':
            total += timedelta(hours=n)
        elif unit == 's':
            total += timedelta(seconds=n)
        else:
            total += timedelta(minutes=n)
        found = True

    if not found:
        raise ValueError("bad duration")
    return datetime.now() + total

# ══════════ UNIQUE ID GENERATOR (bug fix!) ══════════
def gen_unique_id(prefix, owner_id):
    """🔥 FIX: len()-based IDs got reused after deletion → wrong account deleted.
    uuid guarantees every ID is unique forever."""
    return f"{prefix}_{owner_id}_{uuid.uuid4().hex[:6]}"

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

# ══════════ PROFILE CONFIGS (🎨 new feature) ══════════
def load_profiles():
    if os.path.exists(PROFILE_FILE):
        try:
            with open(PROFILE_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_profiles(profiles):
    try:
        with open(PROFILE_FILE, 'w') as f:
            json.dump(profiles, f, indent=2)
    except:
        pass

def get_profile(acc_id):
    return load_profiles().get(acc_id, {})

def set_profile_key(acc_id, key, value):
    profiles = load_profiles()
    profiles.setdefault(acc_id, {})[key] = value
    save_profiles(profiles)

def clear_profile(acc_id):
    profiles = load_profiles()
    if acc_id in profiles:
        del profiles[acc_id]
        save_profiles(profiles)

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
    new_id = gen_unique_id("acc_dyn", owner_id)   # 🔥 unique ID fix
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
            clear_profile(account_id)
            return True
    auth_sessions = load_auth_sessions()
    for i, acc in enumerate(auth_sessions):
        if acc['id'] == account_id:
            auth_sessions.pop(i)
            save_auth_sessions(auth_sessions)
            clear_profile(account_id)
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
    return f"✅ Bot v4.2 | Accounts: {len(all_accs)} | Active: {running_count}/{len(all_accs)} | Sent: {total_sent} | Admins: {admin_count}"

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
    """
    💬 Find a recent message from a REAL USER to quote-reply.
    🔧 FIX: uses cached m.sender (no extra API call per message) + smaller
    scan limit → much faster, far less FloodWait → messages actually send.
    """
    try:
        async for m in client.iter_messages(group, limit=10):
            if m.from_id is None:
                continue
            sender = m.sender  # cached from batch — no extra API call
            if sender is None:
                continue
            if getattr(sender, 'bot', False):
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

# ══════════ 🎨 PROFILE APPLY HELPERS ══════════
async def join_link(client, link):
    """Join a public channel/group (@name or t.me/name) or private invite (t.me/+hash)."""
    link = link.strip().replace('http://', 'https://')
    if not link:
        raise ValueError("empty link")
    if 't.me/+' in link or 'joinchat' in link:
        m = re.search(r'(?:t\.me/\+|joinchat/)([A-Za-z0-9_-]+)', link)
        if not m:
            raise ValueError("bad invite link")
        await client(functions.messages.ImportChatInviteRequest(m.group(1)))
    else:
        m = re.search(r'(?:t\.me/|telegram\.me/|@)([A-Za-z0-9_]+)', link)
        username = m.group(1) if m else link.lstrip('@')
        await client(functions.channels.JoinChannelRequest(username))

async def apply_profile(acc, cfg, bot=None):
    """🎨 1-click: apply name + photo + bio + join all saved channels/groups."""
    results = []
    acc_id = acc['id']
    client = await get_client(acc)
    if not client.is_user_authorized():
        return ["❌ Session dead! Delete this account & login again."]

    if cfg.get('name'):
        try:
            await client(UpdateProfileRequest(first_name=cfg['name']))
            results.append("✅ Name updated")
        except Exception as e:
            results.append(f"❌ Name: {str(e)[:50]}")
        await asyncio.sleep(2)

    if cfg.get('bio'):
        try:
            await client(UpdateProfileRequest(about=cfg['bio']))
            results.append("✅ Bio updated")
        except Exception as e:
            results.append(f"❌ Bio: {str(e)[:50]}")
        await asyncio.sleep(2)

    if cfg.get('photo'):
        photo_path = None
        try:
            tg_file = await bot.get_file(cfg['photo'])
            photo_path = f"prof_{acc_id}.jpg"
            await tg_file.download_to_drive(custom_path=photo_path)
            with open(photo_path, 'rb') as fh:
                uploaded = await client.upload_file(fh)
            await client(UploadProfilePhotoRequest(file=uploaded))
            results.append("✅ Photo updated")
        except Exception as e:
            results.append(f"❌ Photo: {str(e)[:50]}")
        finally:
            if photo_path and os.path.exists(photo_path):
                try: os.remove(photo_path)
                except: pass
        await asyncio.sleep(2)

    for link in cfg.get('channels', []):
        try:
            await join_link(client, link)
            results.append(f"✅ Joined: {link}")
        except Exception as e:
            results.append(f"❌ {link}: {str(e)[:40]}")
        await asyncio.sleep(2)

    return results

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

        # 🔧 FIX: dead session → notify user instead of silent failure
        if not client.is_user_authorized():
            logger.error(f"❌ [{acc_name}] Session unauthorized/dead")
            await notify_user(owner_user_id,
                f"🚨 *SESSION DEAD!*\n👤 {acc_name}\n\n"
                f"❌ Eta account ta delete kore abar 📱 Phone Login diye login koro.\n"
                f"(Same session onno jaygay cholche kina check o koro!)",
                )
            stop_account(acc_id)
            return

        is_restricted, reason = await is_account_restricted(client)
        if is_restricted:
            logger.error(f"❌ [{acc_name}] Restricted: {reason}")
            await notify_user(owner_user_id, f"🚨 *ACCOUNT RESTRICTED!*\n👤 {acc_name}\n❌ {reason}")
            stop_account(acc_id)
            return

        groups = await get_groups(client)
        if not groups:
            logger.warning(f"[{acc_name}] No groups found!")
            await notify_user(owner_user_id, f"⚠️ *{acc_name}* — kono group paowa jay nai! Group e add koro.")
            account_stats[acc_id]['running'] = False
            return

        logger.info(f"[{acc_name}] {len(groups)} groups found")
        cycle_count = 0
        failed_this_cycle = set()

        while not stop_flags.get(acc_id, False):
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
        # 🔧 FIX: tell the user WHY messages weren't sending
        await notify_user(owner_user_id, f"❌ *{acc_name}* fatal error:\n`{str(e)[:150]}`")
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
    for acc in get_all_accounts(user_id):
        stop_account(acc['id'])

def stop_all_accounts():
    for acc in get_all_accounts():
        stop_account(acc['id'])

async def admin_expiry_checker():
    while True:
        try:
            await asyncio.sleep(60)
            valid_ids = {OWNER_ID}
            for a in load_admins():
                if is_valid_admin(a['user_id']):
                    valid_ids.add(a['user_id'])
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
            [InlineKeyboardButton("➕ Add Session", callback_data='add_account'),
             InlineKeyboardButton("📱 Phone Login", callback_data='phone_login')],
            [InlineKeyboardButton("🗑 Delete Account", callback_data='delete_account')],
            [InlineKeyboardButton("🗑 Delete ALL Accounts", callback_data='del_all_accounts')],
            [InlineKeyboardButton("🎨 Profile Setup", callback_data='profile_setup')],
            [InlineKeyboardButton("👑 Admin Panel", callback_data='admin_panel')],
        ])
    else:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("▶️ Start All", callback_data='start_all'),
             InlineKeyboardButton("⏹️ Stop All", callback_data='stop_all')],
            [InlineKeyboardButton("📊 Status", callback_data='status')],
            [InlineKeyboardButton("➕ Add Session", callback_data='add_account'),
             InlineKeyboardButton("📱 Phone Login", callback_data='phone_login')],
            [InlineKeyboardButton("🗑 Delete Account", callback_data='delete_account')],
            [InlineKeyboardButton("🗑 Delete ALL Accounts", callback_data='del_all_accounts')],
            [InlineKeyboardButton("🎨 Profile Setup", callback_data='profile_setup')],
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
        f"🤖 *Messaging Bot v4.2*\n"
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
    if SHOW_START_TO_OTHERS:
        await update.message.reply_text("🤖 Bot is private. Contact the owner for access.")

# ──── CALLBACK HANDLER ────
async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global MESSAGE, MIN_INTERVAL, MAX_INTERVAL, CYCLE_WAIT, SHOW_START_TO_OTHERS

    query = update.callback_query
    await query.answer()

    uid = query.from_user.id

    if not (is_owner(uid) or is_valid_admin(uid)):
        if SHOW_START_TO_OTHERS:
            await query.edit_message_text("⛔ Your access has expired or was removed.")
        else:
            await query.edit_message_text("​")
        return

    # ===== START ALL =====
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

    # ===== STOP ALL =====
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

    # ===== STATUS =====
    elif query.data == 'status':
        accs = get_all_accounts(uid)
        total_sent = sum(account_stats.get(acc['id'], {}).get('sent', 0) for acc in accs)

        text = "📊 *Status*\n\n"
        for i, acc in enumerate(accs, 1):
            aid = acc['id']
            name = acc.get('name', aid)
            status = '🟢' if account_stats.get(aid, {}).get('running', False) else '🔴'
            sent = account_stats.get(aid, {}).get('sent', 0)
            text += f"#{i} {name}: {status} | Sent: {sent}\n"

        if not accs:
            text += "_No accounts yet._\n"

        text += f"\n⏱️ {MIN_INTERVAL}-{MAX_INTERVAL}s | Cycle {CYCLE_WAIT}s"
        text += f"\n📨 Total: {total_sent}"

        kb = [[InlineKeyboardButton("🔙 Back", callback_data='back_main')]]
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb))

    # ══════════ 🗑 DELETE ALL ACCOUNTS ══════════
    elif query.data == 'del_all_accounts':
        accs = get_all_accounts(uid)
        deletable = [a for a in accs if a.get('type') != 'env']
        text = (
            f"⚠️ *DELETE ALL ACCOUNTS?*\n\n"
            f"📊 Total: {len(accs)} | Will delete: {len(deletable)}\n"
            f"(💚 Env accounts can't be deleted — they come back on restart)\n\n"
            f"❗ This is PERMANENT. Sessions will be gone forever!"
        )
        kb = [
            [InlineKeyboardButton("☠️ YES, DELETE ALL", callback_data='del_all_confirm')],
            [InlineKeyboardButton("🔙 Back", callback_data='back_main')],
        ]
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb))

    elif query.data == 'del_all_confirm':
        accs = get_all_accounts(uid)
        count = 0
        for acc in accs:
            if acc.get('type') == 'env':
                continue   # env accounts come from env vars, can't permanently delete
            acc_id = acc['id']
            stop_account(acc_id)
            remove_account_by_id(acc_id)
            await disconnect_client(acc_id)
            count += 1
        save_data()
        kb = [[InlineKeyboardButton("🔙 Back", callback_data='back_main')]]
        await query.edit_message_text(
            f"✅ {count} accounts deleted!\nAll sessions removed permanently.",
            reply_markup=InlineKeyboardMarkup(kb)
        )

    # ══════════ 🎨 PROFILE SETUP ══════════
    elif query.data == 'profile_setup':
        accs = get_all_accounts(uid)
        if not accs:
            kb = [[InlineKeyboardButton("🔙 Back", callback_data='back_main')]]
            await query.edit_message_text("❌ No accounts! Add one first.", reply_markup=InlineKeyboardMarkup(kb))
            return
        profiles = load_profiles()
        keyboard = []
        for i, acc in enumerate(accs, 1):
            has = "🟢" if profiles.get(acc['id']) else "⚪"
            keyboard.append([InlineKeyboardButton(
                f"{has} #{i} {acc.get('name', acc['id'])[:20]}",
                callback_data=f"profacc_{acc['id']}"
            )])
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data='back_main')])
        await query.edit_message_text(
            "🎨 *Profile Setup*\n\n"
            "Prottek account er (#1, #2, #3...) alada Name + Logo + Bio + "
            "Channel/Group link set korte parba. 1 click e apply hobe!\n\n"
            "🟢 = config saved | ⚪ = not set yet\n\n"
            "Account select koro:",
            parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif query.data.startswith('profacc_'):
        acc_id = query.data[len('profacc_'):]
        # 🔒 ownership check
        if not any(a['id'] == acc_id for a in get_all_accounts(uid)):
            await query.edit_message_text("⛔ Not your account!")
            return
        cfg = get_profile(acc_id)
        channels = cfg.get('channels', [])
        text = (
            f"🎨 *Profile Setup*\n\n"
            f"📝 Name: `{cfg.get('name', '—')}`\n"
            f"📄 Bio: `{cfg.get('bio', '—')}`\n"
            f"🖼 Photo: {'✅ Set' if cfg.get('photo') else '—'}\n"
            f"📢 Channels/Groups ({len(channels)}):\n"
        )
        for ch in channels:
            text += f"  • `{ch}`\n"
        keyboard = [
            [InlineKeyboardButton("⚡ APPLY ALL (1 Click)", callback_data=f"profapply_{acc_id}")],
            [InlineKeyboardButton("📝 Set Name", callback_data=f"profname_{acc_id}")],
            [InlineKeyboardButton("🖼 Set Photo", callback_data=f"profphoto_{acc_id}")],
            [InlineKeyboardButton("📄 Set Bio", callback_data=f"profbio_{acc_id}")],
            [InlineKeyboardButton("📢 Set Channels/Groups", callback_data=f"profchan_{acc_id}")],
            [InlineKeyboardButton("🔙 Back", callback_data='profile_setup')],
        ]
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data.startswith('profname_'):
        acc_id = query.data[len('profname_'):]
        context.user_data['awaiting'] = f'prof_name:{acc_id}'
        await query.edit_message_text(
            "📝 *Set Name*\n\nType the new name now:",
            parse_mode='Markdown', reply_markup=BACK_KB
        )

    elif query.data.startswith('profbio_'):
        acc_id = query.data[len('profbio_'):]
        context.user_data['awaiting'] = f'prof_bio:{acc_id}'
        await query.edit_message_text(
            "📄 *Set Bio*\n\nType the new bio now:",
            parse_mode='Markdown', reply_markup=BACK_KB
        )

    elif query.data.startswith('profphoto_'):
        acc_id = query.data[len('profphoto_'):]
        context.user_data['awaiting'] = f'prof_photo:{acc_id}'
        await query.edit_message_text(
            "🖼 *Set Photo (Logo)*\n\nSend the photo now (as photo, not file):",
            parse_mode='Markdown', reply_markup=BACK_KB
        )

    elif query.data.startswith('profchan_'):
        acc_id = query.data[len('profchan_'):]
        context.user_data['awaiting'] = f'prof_chan:{acc_id}'
        cfg = get_profile(acc_id)
        saved = cfg.get('channels', [])
        text = (
            "📢 *Set Channels/Groups*\n\n"
            "Link gulo pathao — ek line e ekta link, or comma diye alada koro.\n\n"
            "Examples:\n"
            "`@mychannel`\n"
            "`https://t.me/mygroup`\n"
            "`https://t.me/+AbCdEf123` (private invite)\n\n"
        )
        if saved:
            text += "Currently saved:\n" + "\n".join(f"• `{c}`" for c in saved)
        else:
            text += "Currently: none"
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=BACK_KB)

    elif query.data.startswith('profapply_'):
        acc_id = query.data[len('profapply_'):]
        acc = next((a for a in get_all_accounts(uid) if a['id'] == acc_id), None)
        if acc is None:
            await query.edit_message_text("⛔ Not your account!")
            return
        cfg = get_profile(acc_id)
        if not cfg:
            kb = [[InlineKeyboardButton("🔙 Back", callback_data=f"profacc_{acc_id}")]]
            await query.edit_message_text("❌ No profile config saved yet! Age Name/Photo/Bio/Channels set koro.",
                                          reply_markup=InlineKeyboardMarkup(kb))
            return
        await query.edit_message_text("⏳ Applying profile (name, photo, bio, joining channels)...")
        results = await apply_profile(acc, cfg, bot=context.bot)
        kb = [
            [InlineKeyboardButton("🎨 Profile Menu", callback_data=f"profacc_{acc_id}")],
            [InlineKeyboardButton("🔙 Back", callback_data='profile_setup')],
        ]
        await query.edit_message_text(
            f"🎨 *Profile Applied*\n\n" + "\n".join(results),
            parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb)
        )

    # ══════════ 👑 ADMIN PANEL — OWNER ONLY ══════════
    elif query.data == 'admin_panel':
        if not is_owner(uid):
            return
        admins = load_admins()
        text = (
            f"👑 *Admin Panel*\n\n"
            f"👥 Total Admins: {len(admins)}\n\n"
            f"➕ Add: send `USER_ID TIME`\n"
            f"Time examples: `30d`, `1 day 10 min`, `12h 30m`, `45`, `perm`\n\n"
            f"💡 If admin already exists → time will be ADDED to remaining time.\n\n"
            f"⏰ When time ends, admin's accounts auto-stop."
        )
        keyboard = [
            [InlineKeyboardButton("📋 Admin List & Stats", callback_data='admin_list')],
            [InlineKeyboardButton("➕ Add / Extend Admin", callback_data='add_admin')],
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
        stop_accounts_of(target)
        await asyncio.sleep(1)
        for acc in get_all_accounts(target):
            await disconnect_client(acc['id'])
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
            "➕ *Add / Extend Admin*\n\n"
            "Send: `USER_ID TIME`\n\n"
            "Time examples (any format works):\n"
            "`123456789 30d` → 30 days\n"
            "`123456789 1 day 10 min` → mixed\n"
            "`123456789 12h 30m` → 12h 30m\n"
            "`123456789 90` → 90 minutes\n"
            "`123456789 45 sec` → 45 seconds\n"
            "`123456789 perm` → permanent\n\n"
            "💡 Existing admin? Time gets ADDED to remaining time.\n\n"
            "Send now:",
            parse_mode='Markdown', reply_markup=BACK_KB
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

    # ===== MESSAGE LIST (accessible from Settings) =====
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
            [InlineKeyboardButton("🔙 Back", callback_data='settings')],
        ]
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == 'add_message':
        context.user_data['awaiting'] = 'add_message'
        await query.edit_message_text(
            f"✏️ *Add New Message*\n\n"
            f"Currently {len(load_messages_for(uid))} message(s).\n\n"
            f"Type your new message now:",
            parse_mode='Markdown', reply_markup=BACK_KB
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
        await query.edit_message_text(f"Minimum delay (seconds):\nCurrent: {MIN_INTERVAL}s", reply_markup=BACK_KB)

    elif query.data == 'set_max':
        if not is_owner(uid):
            return
        context.user_data['awaiting'] = 'max'
        await query.edit_message_text(f"Maximum delay (seconds):\nCurrent: {MAX_INTERVAL}s", reply_markup=BACK_KB)

    elif query.data == 'set_cycle':
        if not is_owner(uid):
            return
        context.user_data['awaiting'] = 'cycle'
        await query.edit_message_text(f"Cycle wait (seconds):\nCurrent: {CYCLE_WAIT}s", reply_markup=BACK_KB)

    # ===== PHONE LOGIN =====
    elif query.data == 'phone_login':
        context.user_data['awaiting'] = 'phone_number'
        await query.edit_message_text(
            "📱 *Phone Login*\n\n"
            "Send phone number (international format):\n\n"
            "Example: `+8801XXXXXXXXX`\n\n"
            "Send the number now:",
            parse_mode='Markdown', reply_markup=BACK_KB
        )

    # ===== ADD SESSION =====
    elif query.data == 'add_account':
        context.user_data['awaiting'] = 'add_account'
        await query.edit_message_text(
            "📱 *Add Session String*\n\n"
            "Send the **Session String** only.\n\n"
            "⚠️ Make sure the same session is NOT running anywhere else, or it will die permanently.\n\n"
            "Send it now:",
            parse_mode='Markdown', reply_markup=BACK_KB
        )

    # ===== DELETE ACCOUNT (own only) =====
    elif query.data == 'delete_account':
        all_accs = get_all_accounts(uid)
        if not all_accs:
            kb = [[InlineKeyboardButton("🔙 Back", callback_data='back_main')]]
            await query.edit_message_text("❌ No accounts!", reply_markup=InlineKeyboardMarkup(kb))
            return
        keyboard = []
        for i, acc in enumerate(all_accs, 1):
            type_icon = {'env': '💚', 'dynamic': '💙', 'phone_auth': '📱'}.get(acc.get('type', ''), '❓')
            display = f"{type_icon} #{i} {acc.get('name', acc['id'])[:25]}"
            keyboard.append([InlineKeyboardButton(display, callback_data=f"del_acc_{acc['id']}")])
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data='back_main')])
        await query.edit_message_text("🗑 *Delete which account?*", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data.startswith('del_acc_'):
        acc_id = query.data.replace('del_acc_', '')
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

    # ===== BACK MAIN =====
    elif query.data == 'back_main':
        context.user_data['awaiting'] = None   # clear any pending input
        refresh_account_stats(uid)
        await query.edit_message_text(main_menu_text(uid), parse_mode='Markdown', reply_markup=main_menu_keyboard(uid))


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """🖼 Receives profile photo for Profile Setup."""
    uid = update.effective_user.id
    if not (is_owner(uid) or is_valid_admin(uid)):
        return
    awaiting = context.user_data.get('awaiting')
    if awaiting and awaiting.startswith('prof_photo:'):
        acc_id = awaiting.split(':', 1)[1]
        if not any(a['id'] == acc_id for a in get_all_accounts(uid)):
            await update.message.reply_text("⛔ Not your account!")
            context.user_data['awaiting'] = None
            return
        file_id = update.message.photo[-1].file_id   # highest resolution
        set_profile_key(acc_id, 'photo', file_id)
        context.user_data['awaiting'] = None
        kb = [[InlineKeyboardButton("🎨 Profile Menu", callback_data=f"profacc_{acc_id}")]]
        await update.message.reply_text("✅ Photo saved! 1 click e apply korte paro.",
                                        reply_markup=InlineKeyboardMarkup(kb))


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    if not (is_owner(uid) or is_valid_admin(uid)):
        return

    text = update.message.text.strip()
    awaiting = context.user_data.get('awaiting')

    # ===== Add / Extend Admin — OWNER ONLY =====
    if awaiting == 'add_admin':
        context.user_data['awaiting'] = None
        if not is_owner(uid):
            return
        try:
            parts = text.split(None, 1)
            target_id = int(parts[0])
            expires_at = parse_duration(parts[1]) if len(parts) > 1 else None
        except:
            await update.message.reply_text(
                "❌ Wrong format!\nExample: `123456789 1 day 10 min` or `123456789 30d` or `123456789 perm`",
                parse_mode='Markdown'
            )
            return

        if target_id == OWNER_ID:
            await update.message.reply_text("❌ Owner is already the boss! 😎")
            return

        admins = load_admins()
        for a in admins:
            if a['user_id'] == target_id:
                if expires_at is None:
                    a['expires_at'] = None
                    a['updated_at'] = datetime.now().isoformat()
                    save_admins(admins)
                    kb = [[InlineKeyboardButton("🔙 Back", callback_data='admin_panel')]]
                    await update.message.reply_text(
                        f"✅ Admin `{target_id}` → ♾️ Permanent now!",
                        parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb)
                    )
                    return

                now = datetime.now()
                try:
                    current_exp = datetime.fromisoformat(a['expires_at']) if a.get('expires_at') else None
                except:
                    current_exp = None

                base = current_exp if (current_exp and current_exp > now) else now
                new_exp = base + (expires_at - now)

                a['expires_at'] = new_exp.isoformat()
                a['updated_at'] = now.isoformat()
                save_admins(admins)
                kb = [[InlineKeyboardButton("🔙 Back", callback_data='admin_panel')]]
                await update.message.reply_text(
                    f"✅ Admin `{target_id}` time EXTENDED!\n\n"
                    f"⏳ New time: {remaining_time_str(a['expires_at'])}",
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
            f"✅ *Admin added!*\n\n"
            f"👤 `{target_id}`\n"
            f"⏳ Time: {remaining_time_str(expires_at.isoformat() if expires_at else None)}\n\n"
            f"The admin can now use /start.",
            parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb)
        )
        return

    # ══════════ 🎨 PROFILE INPUTS ══════════
    if awaiting and awaiting.startswith('prof_name:'):
        acc_id = awaiting.split(':', 1)[1]
        context.user_data['awaiting'] = None
        if not any(a['id'] == acc_id for a in get_all_accounts(uid)):
            await update.message.reply_text("⛔ Not your account!")
            return
        set_profile_key(acc_id, 'name', text)
        kb = [[InlineKeyboardButton("🎨 Profile Menu", callback_data=f"profacc_{acc_id}")]]
        await update.message.reply_text(f"✅ Name saved: `{text}`", parse_mode='Markdown',
                                        reply_markup=InlineKeyboardMarkup(kb))
        return

    if awaiting and awaiting.startswith('prof_bio:'):
        acc_id = awaiting.split(':', 1)[1]
        context.user_data['awaiting'] = None
        if not any(a['id'] == acc_id for a in get_all_accounts(uid)):
            await update.message.reply_text("⛔ Not your account!")
            return
        set_profile_key(acc_id, 'bio', text)
        kb = [[InlineKeyboardButton("🎨 Profile Menu", callback_data=f"profacc_{acc_id}")]]
        await update.message.reply_text(f"✅ Bio saved: `{text[:50]}`", parse_mode='Markdown',
                                        reply_markup=InlineKeyboardMarkup(kb))
        return

    if awaiting and awaiting.startswith('prof_chan:'):
        acc_id = awaiting.split(':', 1)[1]
        context.user_data['awaiting'] = None
        if not any(a['id'] == acc_id for a in get_all_accounts(uid)):
            await update.message.reply_text("⛔ Not your account!")
            return
        links = [x.strip() for x in re.split(r'[\n,]+', text) if x.strip()]
        set_profile_key(acc_id, 'channels', links)
        kb = [[InlineKeyboardButton("🎨 Profile Menu", callback_data=f"profacc_{acc_id}")]]
        await update.message.reply_text(
            f"✅ {len(links)} channel/group link saved!\n\n" +
            "\n".join(f"• `{l}`" for l in links),
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

        client = None
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

            await status_msg.edit_text("✅ OTP sent!\n\nEnter the code (e.g. `12345`):",
                                       parse_mode='Markdown', reply_markup=BACK_KB)
        except Exception as e:
            await status_msg.edit_text(f"❌ Error: {str(e)[:200]}", reply_markup=BACK_KB)
            if client is not None:
                try: await client.disconnect()
                except: pass
        return

    # ===== OTP Code =====
    if awaiting == 'otp_code':
        context.user_data['awaiting'] = None
        login_id = context.user_data.get('login_id')
        if not login_id or login_id not in phone_login_states:
            await update.message.reply_text("❌ Session expired! Use /start", reply_markup=BACK_KB)
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
            new_id = gen_unique_id("phone", state['owner_id'])   # 🔥 unique ID fix
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
            await status_msg.edit_text("🔐 *Enter 2FA password:*", parse_mode='Markdown', reply_markup=BACK_KB)
        except PhoneCodeInvalidError:
            await status_msg.edit_text("❌ Wrong OTP! Try /start again", reply_markup=BACK_KB)
            try: await client.disconnect()
            except: pass
            del phone_login_states[login_id]
        except PhoneCodeExpiredError:
            await status_msg.edit_text("❌ OTP expired! Try /start again", reply_markup=BACK_KB)
            try: await client.disconnect()
            except: pass
            del phone_login_states[login_id]
        except Exception as e:
            await status_msg.edit_text(f"❌ Error: {str(e)[:200]}", reply_markup=BACK_KB)
            try: await client.disconnect()
            except: pass
            del phone_login_states[login_id]
        return

    # ===== 2FA Password =====
    if awaiting == '2fa_password':
        context.user_data['awaiting'] = None
        login_id = context.user_data.get('login_id')
        if not login_id or login_id not in phone_login_states:
            await update.message.reply_text("❌ Session expired! Use /start", reply_markup=BACK_KB)
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
            new_id = gen_unique_id("phone", state['owner_id'])   # 🔥 unique ID fix
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
            await status_msg.edit_text(f"❌ 2FA Error: {str(e)[:200]}", reply_markup=BACK_KB)
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
                        "➡️ Use 📱 Phone Login to create a fresh session.",
                        reply_markup=BACK_KB
                    )
                else:
                    await status_msg.edit_text(f"❌ Invalid session!\n{name}", reply_markup=BACK_KB)
                return
            success, result = add_dynamic_account(name, fresh_session, uid)
            if success:
                refresh_account_stats(uid)
                kb = [[InlineKeyboardButton("🔙 Back", callback_data='back_main')]]
                await status_msg.edit_text(f"✅ Added!\n👤 {name}\n🆔 `{result}`",
                                           parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb))
            else:
                await status_msg.edit_text(f"❌ {result}", reply_markup=BACK_KB)
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {str(e)[:200]}", reply_markup=BACK_KB)
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
    print("🤖 BOT v4.2 STARTING", flush=True)
    print("=" * 50, flush=True)

    await init_env_accounts()

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

    valid_ids = {OWNER_ID}
    for a in admins:
        if is_valid_admin(a['user_id']):
            valid_ids.add(a['user_id'])
    for acc in get_all_accounts():
        if acc.get('owner_id', OWNER_ID) not in valid_ids:
            stop_flags[acc['id']] = True

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
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    await app.initialize()
    await app.start()

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
