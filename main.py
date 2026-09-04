#!/usr/bin/env python3
"""
📱 TELEGRAM MASS MESSAGING BOT v5.1
✅ Phone login reply fix (flood-wait aware, error boundary, always-ack)
✅ Buttons: Start/Stop side-by-side in 1 row, every other action on its own row
✅ Admin time: +100000d increase / -10d decrease / =perm set / perm
✅ Owner sets per-admin account login limit (🔢 Set Account Limit)
✅ Profile rename reflected in Status & Delete menu
✅ Limit + duplicate-phone enforced on session-add & phone-login
"""
import sys, os, asyncio, random, logging, json, threading, httpx, re, uuid
from datetime import datetime, timedelta
from telethon import TelegramClient, errors, functions
from telethon.sessions import StringSession
from telethon.tl.functions.account import UpdateProfileRequest
from telethon.tl.functions.photos import UploadProfilePhotoRequest
from telethon.errors import (
    FloodWaitError, SessionPasswordNeededError, PhoneCodeInvalidError,
    PhoneCodeExpiredError, UserRestrictedError, AuthKeyUnregisteredError,
    UserDeactivatedError, UserDeactivatedBanError)
from telethon.tl.functions.messages import GetDialogsRequest
from telethon.tl.types import InputPeerEmpty
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from flask import Flask

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s',
                    force=True, handlers=[logging.StreamHandler(sys.stdout)])
logger = logging.getLogger(__name__)
print("=" * 60, flush=True); print("🤖 BOT v5.1 (FIXED)", flush=True); print("=" * 60, flush=True)

# ── ENV ──
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID = int(os.environ.get("OWNER_ID", "0"))
API_ID_1 = int(os.environ.get("API_ID_1", "0")); API_HASH_1 = os.environ.get("API_HASH_1", ""); SESSION_1 = os.environ.get("SESSION_1", "")
API_ID_2 = int(os.environ.get("API_ID_2", "0")); API_HASH_2 = os.environ.get("API_HASH_2", ""); SESSION_2 = os.environ.get("SESSION_2", "")
API_ID_3 = int(os.environ.get("API_ID_3", "0")); API_HASH_3 = os.environ.get("API_HASH_3", ""); SESSION_3 = os.environ.get("SESSION_3", "")

DYNAMIC_ACCOUNTS_FILE = "dynamic_accounts.json"
AUTH_SESSIONS_FILE = "auth_sessions.json"
ADMINS_FILE = "admins.json"
PROFILE_FILE = "profile_configs.json"
DEFAULT_PROFILE_KEY = "__default__"
MESSAGE = os.environ.get("MESSAGE", "𝟭𝟬 𝗠𝗜𝗡 𝗩𝗖 ₹𝟰𝟱 𝗕𝗔𝗕𝗬😘")
MIN_INTERVAL = int(os.environ.get("MIN_INTERVAL", "6"))
MAX_INTERVAL = int(os.environ.get("MAX_INTERVAL", "10"))
CYCLE_WAIT = int(os.environ.get("CYCLE_WAIT", "45"))

running_tasks, stop_flags, account_clients, account_stats, phone_login_states, display_names = {}, {}, {}, {}, {}, {}
data_file = "bot_data.json"
SHOW_START_TO_OTHERS = True
try:
    _e = os.environ.get("ADMIN_ACCOUNT_LIMIT", "").strip()
    DEFAULT_ADMIN_LIMIT = int(_e) if _e else None
except Exception:
    DEFAULT_ADMIN_LIMIT = None
BACK_KB = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data='back_main')]])

# ── Permissions ──
def is_owner(u): return u == OWNER_ID
def load_admins():
    try: return json.load(open(ADMINS_FILE)) if os.path.exists(ADMINS_FILE) else []
    except: return []
def save_admins(x):
    try: json.dump(x, open(ADMINS_FILE, 'w'), indent=2)
    except: pass
def get_admin(u):
    for a in load_admins():
        if a['user_id'] == u: return a
    return None
def is_valid_admin(u):
    a = get_admin(u)
    if not a: return False
    exp = a.get('expires_at')
    if not exp: return True
    try: return datetime.fromisoformat(exp) > datetime.now()
    except: return False
def remaining_time_str(e):
    if not e: return "♾️ Pemranent"
    try: d = datetime.fromisoformat(e) - datetime.now()
    except: return "?"
    if d.total_seconds() <= 0: return "⛔ EXPIRED"
    days, s = d.days, d.seconds
    h, m = s // 3600, (s % 3600) // 60
    p = []
    if days: p.append(f"{days}d")
    if h: p.append(f"{h}h")
    if m: p.append(f"{m}m")
    return " ".join(p) + " left" if p else "<1s"

def parse_duration(t):
    t = t.strip().lower()
    if t in ('perm','permanent','inf','unlimited','∞','none'): return None
    for a, b in [('seconds','s'),('second','s'),('secs','s'),('sec','s'),
                 ('minutes','m'),('minute','m'),('mins','m'),('min','m'),
                 ('hours','h'),('hour','h'),('hrs','h'),('hr','h'),
                 ('days','d'),('day','d'),('din','d')]:
        t = t.replace(a, b)
    total, found = timedelta(), False
    for num, unit in re.findall(r'(\d+)\s*([dhms])?', t):
        if not num: continue
        n = int(num); unit = unit or 'm'
        if unit == 'd': total += timedelta(days=n)
        elif unit == 'h': total += timedelta(hours=n)
        elif unit == 's': total += timedelta(seconds=n)
        else: total += timedelta(minutes=n)
        found = True
    if not found: raise ValueError("bad duration")
    return datetime.now() + total

def parse_admin_cmd(t):
    pr = t.strip().split(None, 1)
    if not pr: raise ValueError("need USER_ID")
    uid = int(pr[0]); rest = pr[1].strip() if len(pr) > 1 else 'perm'
    op = '+'
    if rest and rest[0] in ('+', '-', '='):
        op = rest[0]; rest = rest[1:].strip()
    if not rest or rest.lower() in ('perm','permanent','inf','unlimited'):
        return uid, op, None
    return uid, op, parse_duration(rest)

def gen_unique_id(p, o): return f"{p}_{o}_{uuid.uuid4().hex[:6]}"
def messages_file_for(u): return "messages.json" if is_owner(u) else f"messages_{u}.json"
def load_messages_for(u):
    f = messages_file_for(u)
    try: return json.load(open(f)) if os.path.exists(f) else []
    except: return []
def save_messages_for(u, m):
    try: json.dump(m, open(messages_file_for(u), 'w'), indent=2)
    except: pass
def get_random_message_for(u):
    m = load_messages_for(u)
    return random.choice(m) if m else MESSAGE

def load_profiles():
    try: return json.load(open(PROFILE_FILE)) if os.path.exists(PROFILE_FILE) else {}
    except: return {}
def save_profiles(p):
    try: json.dump(p, open(PROFILE_FILE, 'w'), indent=2)
    except: pass
def get_default_profile(): return load_profiles().get(DEFAULT_PROFILE_KEY, {})
def save_default_profile(cfg):
    p = load_profiles(); p[DEFAULT_PROFILE_KEY] = cfg; save_profiles(p)

def load_auth_sessions():
    try: return json.load(open(AUTH_SESSIONS_FILE)) if os.path.exists(AUTH_SESSIONS_FILE) else []
    except: return []
def save_auth_sessions(s):
    try: json.dump(s, open(AUTH_SESSIONS_FILE, 'w'), indent=2)
    except: pass

ENV_ACCOUNTS = []
acc_configs = [('acc1',API_ID_1,API_HASH_1,SESSION_1),('acc2',API_ID_2,API_HASH_2,SESSION_2),('acc3',API_ID_3,API_HASH_3,SESSION_3)]
async def init_env_accounts():
    for acc_id, api_id, api_hash, session in acc_configs:
        if api_id and api_hash and session:
            try:
                c = TelegramClient(StringSession(session), api_id, api_hash, receive_updates=False)
                await c.start(); me = await c.get_me()
                n = me.first_name or f"User{me.id}"; await c.disconnect()
                ENV_ACCOUNTS.append({'id':acc_id,'name':n,'api_id':api_id,'api_hash':api_hash,'session':session,
                                     'type':'env','phone':getattr(me,'phone',''),'owner_id':OWNER_ID})
                display_names[acc_id] = n
                print(f"✅ {acc_id}: {n}", flush=True)
            except Exception as e:
                print(f"❌ {acc_id}: {str(e)[:50]}", flush=True)
            await asyncio.sleep(1)

def load_dynamic_accounts():
    try: return json.load(open(DYNAMIC_ACCOUNTS_FILE)) if os.path.exists(DYNAMIC_ACCOUNTS_FILE) else []
    except: return []
def save_dynamic_accounts(a):
    try: json.dump(a, open(DYNAMIC_ACCOUNTS_FILE, 'w'), indent=2)
    except: pass

def get_all_accounts(user_id=None):
    dyn = load_dynamic_accounts()
    auth = []
    for s in load_auth_sessions():
        auth.append({'id':s['id'],'name':s.get('name',f"User_{s.get('user_id','?')}"),'api_id':s['api_id'],
                     'api_hash':s['api_hash'],'session':s['session_string'],'type':'phone_auth',
                     'phone':s.get('phone',''),'owner_id':s.get('owner_id',OWNER_ID)})
    accs = ENV_ACCOUNTS + dyn + auth
    if user_id is None or user_id == OWNER_ID: return accs
    return [a for a in accs if a.get('owner_id') == user_id]

def get_display_name(acc): return display_names.get(acc.get('id')) or acc.get('name') or str(acc.get('id'))
def preload_display_names(accs):
    for acc in accs: display_names.setdefault(acc.get('id'), acc.get('name'))
def persist_rename(acc_id, new_name):
    if not new_name: return
    display_names[acc_id] = new_name
    for fname in (DYNAMIC_ACCOUNTS_FILE, AUTH_SESSIONS_FILE):
        if not os.path.exists(fname): continue
        try:
            data = json.load(open(fname)); ch = False
            for it in data:
                if it.get('id') == acc_id and it.get('name') != new_name:
                    it['name'] = new_name; ch = True
            if ch: json.dump(data, open(fname, 'w'), indent=2)
        except: pass
    for acc in ENV_ACCOUNTS:
        if acc['id'] == acc_id: acc['name'] = new_name

def add_dynamic_account(name, ss, owner_id, api_id=0, api_hash=""):
    accs = load_dynamic_accounts()
    for a in accs:
        if a['session'] == ss: return False, "Session exists!"
    nid = gen_unique_id("acc_dyn", owner_id)
    accs.append({'id':nid,'name':name,'api_id':api_id or API_ID_1,'api_hash':api_hash or API_HASH_1,
                 'session':ss,'type':'dynamic','owner_id':owner_id})
    save_dynamic_accounts(accs); display_names[nid] = name
    return True, nid

def remove_account_by_id(aid):
    global ENV_ACCOUNTS
    dyn = load_dynamic_accounts()
    for i, a in enumerate(dyn):
        if a['id'] == aid: dyn.pop(i); save_dynamic_accounts(dyn); display_names.pop(aid,None); return True
    au = load_auth_sessions()
    for i, a in enumerate(au):
        if a['id'] == aid: au.pop(i); save_auth_sessions(au); display_names.pop(aid,None); return True
    for i, a in enumerate(ENV_ACCOUNTS):
        if a['id'] == aid: ENV_ACCOUNTS.pop(i); display_names.pop(aid,None); return True
    return False

def admin_max_accounts(u):
    if is_owner(u): return None
    a = get_admin(u)
    if a and a.get('max_accounts') is not None: return int(a['max_accounts'])
    return DEFAULT_ADMIN_LIMIT
def owner_acc_count(u): return sum(1 for a in get_all_accounts() if a.get('owner_id') == u)
def account_limit_reached(u):
    if is_owner(u): return False, ""
    cap = admin_max_accounts(u)
    if cap is None: return False, ""
    if owner_acc_count(u) >= cap: return True, f"❌ Account limit ({owner_acc_count(u)}/{cap}) reached!"
    return False, ""
def refresh_account_stats(user_id=None):
    for a in get_all_accounts(user_id):
        aid = a['id']
        if aid not in account_stats:
            account_stats[aid] = {'sent':0,'running':False,'failed_channels':[]}
            stop_flags[aid] = False

web_app = Flask(__name__)
@web_app.route("/")
def home():
    all_a = get_all_accounts()
    run = sum(1 for a in all_a if account_stats.get(a['id'],{}).get('running',False))
    sent = sum(account_stats.get(a['id'],{}).get('sent',0) for a in all_a)
    return f"v5.1 | Accounts:{len(all_a)} | Active:{run}/{len(all_a)} | Sent:{sent} | Admins:{len(load_admins())}"
@web_app.route("/health")
def health(): return "OK", 200
def run_flask(): web_app.run(host="0.0.0.0", port=int(os.environ.get("PORT",10000)), debug=False, use_reloader=False)

def load_data():
    global MESSAGE, MIN_INTERVAL, MAX_INTERVAL, CYCLE_WAIT
    if os.path.exists(data_file):
        try:
            d = json.load(open(data_file))
            MESSAGE = d.get('message', MESSAGE); MIN_INTERVAL = d.get('min_interval', MIN_INTERVAL)
            MAX_INTERVAL = d.get('max_interval', MAX_INTERVAL); CYCLE_WAIT = d.get('cycle_wait', CYCLE_WAIT)
        except: pass
def save_data():
    try:
        json.dump({'message':MESSAGE,'min_interval':MIN_INTERVAL,'max_interval':MAX_INTERVAL,
                   'cycle_wait':CYCLE_WAIT,'show_start_to_others':SHOW_START_TO_OTHERS}, open(data_file,'w'), indent=2)
    except: pass

async def get_client(acc):
    aid = acc['id']; old = account_clients.get(aid)
    if old is not None:
        try:
            if old.is_connected(): return old
            await old.disconnect()
        except: pass
        del account_clients[aid]
    c = TelegramClient(StringSession(acc['session']), acc['api_id'], acc['api_hash'], receive_updates=False)
    await c.start(); account_clients[aid] = c; return c
async def disconnect_client(aid):
    c = account_clients.pop(aid, None)
    if c:
        try: await c.disconnect()
        except: pass
async def get_groups(client, retry=3):
    for _ in range(retry):
        try:
            dl = await client(GetDialogsRequest(offset_date=None, offset_id=0, offset_peer=InputPeerEmpty(), limit=200, hash=0))
            gs = []
            for d in dl.dialogs:
                try:
                    e = await client.get_entity(d.peer)
                    if hasattr(e, 'title'): gs.append(e)
                except: pass
            if gs: return gs
            await asyncio.sleep(3)
        except Exception as e:
            logger.error(f"groups: {e}"); await asyncio.sleep(3)
    return []
async def is_account_restricted(client):
    try:
        me = await client.get_me()
        if me is None: return True, "deleted"
        return False, None
    except (UserRestrictedError,UserDeactivatedError,UserDeactivatedBanError,AuthKeyUnregisteredError) as e:
        return True, str(e)
    except: return False, None
async def get_reply_target(client, group):
    try:
        async for m in client.iter_messages(group, limit=10):
            if m.from_id and m.sender and not getattr(m.sender,'bot',False): return m
    except: pass
    return None
async def notify_user(uid, t):
    try:
        b = Application.builder().token(BOT_TOKEN).build()
        await b.bot.send_message(chat_id=uid, text=t, parse_mode='Markdown')
    except: pass
async def join_link(client, link):
    link = link.strip().replace('http://','https://')
    if not link: raise ValueError("empty")
    if 't.me/+' in link or 'joinchat' in link:
        m = re.search(r'(?:t\.me/\+|joinchat/)([A-Za-z0-9_-]+)', link)
        if not m: raise ValueError("bad invite")
        await client(functions.messages.ImportChatInviteRequest(m.group(1)))
    else:
        m = re.search(r'(?:t\.me/|telegram\.me/|@)([A-Za-z0-9_]+)', link)
        await client(functions.channels.JoinChannelRequest(m.group(1) if m else link.lstrip('@')))
async def apply_profile(acc, name, photo, bio, channels, bot=None):
    r = []; aid = acc['id']; client = await get_client(acc)
    if not client.is_user_authorized(): return ["❌ Session dead!"]
    if name:
        try: await client(UpdateProfileRequest(first_name=name)); r.append("✅ Name"); persist_rename(aid, name)
        except Exception as e: r.append(f"❌ Name:{str(e)[:40]}")
        await asyncio.sleep(1)
    if bio:
        try: await client(UpdateProfileRequest(about=bio)); r.append("✅ Bio")
        except Exception as e: r.append(f"❌ Bio:{str(e)[:40]}")
        await asyncio.sleep(1)
    if photo:
        p = None
        try:
            tf = await bot.get_file(photo); p = f"prof_{aid}.jpg"; await tf.download_to_drive(custom_path=p)
            with open(p,'rb') as fh: up = await client.upload_file(fh)
            await client(UploadProfilePhotoRequest(file=up)); r.append("✅ Photo")
        except Exception as e: r.append(f"❌ Photo:{str(e)[:40]}")
        finally:
            if p and os.path.exists(p):
                try: os.remove(p)
                except: pass
        await asyncio.sleep(1)
    for lk in channels:
        try: await join_link(client, lk); r.append(f"✅ {lk}")
        except Exception as e: r.append(f"❌ {lk}:{str(e)[:30]}")
        await asyncio.sleep(0.5)
    return r

async def run_account_messaging(acc, owner):
    aid = acc['id']; stop_flags[aid] = False
    account_stats.setdefault(aid, {'sent':0,'running':False,'failed_channels':[]})
    account_stats[aid]['running'] = True
    try:
        client = await get_client(acc); me = await client.get_me()
        if getattr(me,'first_name',None): persist_rename(aid, me.first_name)
        if not client.is_user_authorized():
            await notify_user(owner, f"🚨 *SESSION DEAD*\n{get_display_name(acc)}"); stop_account(aid); return
        res, reason = await is_account_restricted(client)
        if res: await notify_user(owner, f"🚨 *RESTRICTED*\n{get_display_name(acc)}"); stop_account(aid); return
        groups = await get_groups(client)
        if not groups:
            await notify_user(owner, f"⚠️ {get_display_name(acc)} — no groups"); account_stats[aid]['running'] = False; return
        cycle = 0; failed = set()
        while not stop_flags.get(aid, False):
            if not is_owner(owner) and not is_valid_admin(owner):
                stop_account(aid); return
            random.shuffle(groups)
            for g in groups:
                if stop_flags.get(aid, False): break
                if g.id in failed: continue
                try:
                    msg = get_random_message_for(owner)
                    rt = await get_reply_target(client, g)
                    if rt: await client.send_message(g, msg, reply_to=rt.id)
                    else: await client.send_message(g, msg)
                    account_stats[aid]['sent'] += 1
                except FloodWaitError as e:
                    for i in range(min(e.seconds, 60)):
                        if stop_flags.get(aid): break
                        await asyncio.sleep(1)
                    if e.seconds > 60: await asyncio.sleep(e.seconds - 60)
                except (errors.UserBannedInChannelError, errors.ChatWriteForbiddenError, errors.ChatAdminRequiredError):
                    failed.add(g.id)
                except errors.RPCError as e:
                    if any(x in str(e).lower() for x in ['ban','restrict','forbidden','write','permission']): failed.add(g.id)
                except Exception as e:
                    if any(x in str(e).lower() for x in ['ban','restrict','forbidden','admin',"can't write"]): failed.add(g.id)
                await asyncio.sleep(random.randint(MIN_INTERVAL, MAX_INTERVAL))
            res, reason = await is_account_restricted(client)
            if res: await notify_user(owner, f"🚨 *RESTRICTED*\n{get_display_name(acc)}"); stop_account(aid); return
            if stop_flags.get(aid): break
            failed = set(); cycle += 1
            for i in range(CYCLE_WAIT):
                if stop_flags.get(aid): break
                await asyncio.sleep(1)
            if cycle % 15 == 0:
                try:
                    await disconnect_client(aid); await asyncio.sleep(3)
                    if not stop_flags.get(aid):
                        client = await get_client(acc); groups = await get_groups(client)
                        me = await client.get_me()
                        if getattr(me,'first_name',None): persist_rename(aid, me.first_name)
                except Exception as e: logger.error(f"reconnect:{e}")
    except asyncio.CancelledError: pass
    except Exception as e:
        logger.error(f"fatal:{e}")
        await notify_user(owner, f"❌ fatal: `{str(e)[:150]}`")
    finally:
        await disconnect_client(aid); account_stats[aid]['running'] = False; stop_flags[aid] = True

def stop_account(aid):
    stop_flags[aid] = True
    if aid in running_tasks and not running_tasks[aid].done():
        running_tasks[aid].cancel()
        try: del running_tasks[aid]
        except: pass
    if aid in account_stats: account_stats[aid]['running'] = False
def stop_accounts_of(u):
    for a in get_all_accounts(u): stop_account(a['id'])
def stop_all_accounts():
    for a in get_all_accounts(): stop_account(a['id'])

async def admin_expiry_checker():
    while True:
        try:
            await asyncio.sleep(60)
            valid = {OWNER_ID}
            for a in load_admins():
                if is_valid_admin(a['user_id']): valid.add(a['user_id'])
            for acc in get_all_accounts():
                oid = acc.get('owner_id', OWNER_ID)
                if oid not in valid and account_stats.get(acc['id'],{}).get('running',False):
                    stop_account(acc['id']); await disconnect_client(acc['id'])
        except Exception as e:
            logger.error(f"expiry:{e}")

async def test_session_only(ss):
    c = None
    try:
        if not API_ID_1 or not API_HASH_1: return False, "API missing", None, None
        c = TelegramClient(StringSession(ss), API_ID_1, API_HASH_1, receive_updates=False)
        await c.start(); me = await c.get_me()
        return True, me.first_name, me.id, c.session.save()
    except Exception as e: return False, str(e), None, None
    finally:
        if c:
            try: await c.disconnect()
            except: pass

# ── Keyboards (Start/Stop pasa-pasi, rest own row) ──
def main_menu_keyboard(u):
    if is_owner(u):
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("▶️ Start All", callback_data='start_all'),
             InlineKeyboardButton("⏹️ Stop All", callback_data='stop_all')],
            [InlineKeyboardButton("⚙️ Settings", callback_data='settings')],
            [InlineKeyboardButton("➕ Add Session", callback_data='add_account')],
            [InlineKeyboardButton("📱 Phone Login", callback_data='phone_login')],
            [InlineKeyboardButton("🗑 Delete Account", callback_data='delete_account')],
            [InlineKeyboardButton("🎨 Profile Setup", callback_data='profile_setup')],
            [InlineKeyboardButton("👑 Admin Panel", callback_data='admin_panel')]])
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("▶️ Start All", callback_data='start_all'),
         InlineKeyboardButton("⏹️ Stop All", callback_data='stop_all')],
        [InlineKeyboardButton("📊 Status", callback_data='status')],
        [InlineKeyboardButton("➕ Add Session", callback_data='add_account')],
        [InlineKeyboardButton("📱 Phone Login", callback_data='phone_login')],
        [InlineKeyboardButton("🗑 Delete Account", callback_data='delete_account')],
        [InlineKeyboardButton("🎨 Profile Setup", callback_data='profile_setup')]])

def main_menu_text(u):
    accs = get_all_accounts(u); run = sum(1 for a in accs if account_stats.get(a['id'],{}).get('running',False))
    sent = sum(account_stats.get(a['id'],{}).get('sent',0) for a in accs)
    role = "👑 Owner" if is_owner(u) else "👤 Admin"
    extra = ""
    if not is_owner(u):
        a = get_admin(u); exp = f"\n⏳ Time: {remaining_time_str(a.get('expires_at') if a else None)}"
        cap = admin_max_accounts(u); cur = owner_acc_count(u)
        lim = f"\n🔢 Acc: {cur}" if cap is None else f"\n🔢 Acc: {cur}/{cap}"
        extra = exp + lim
    return (f"🤖 *Bot v5.1*\n👤 {role}{extra}\n\n"
            f"📊 Accounts: {len(accs)} (Running:{run})\n⏱️ {MIN_INTERVAL}-{MAX_INTERVAL}s | Cycle {CYCLE_WAIT}s\n📨 Sent: {sent}")

async def start_command(u, c):
    uid = u.effective_user.id
    if is_owner(uid) or is_valid_admin(uid):
        refresh_account_stats(uid); preload_display_names(get_all_accounts(uid))
        await u.message.reply_text(main_menu_text(uid), parse_mode='Markdown', reply_markup=main_menu_keyboard(uid))
        return
    if SHOW_START_TO_OTHERS: await u.message.reply_text("🤖 Private bot. Owner ke contact koro.")

async def button_click(u, c):
    global MESSAGE, MIN_INTERVAL, MAX_INTERVAL, CYCLE_WAIT, SHOW_START_TO_OTHERS
    q = u.callback_query; await q.answer(); uid = q.from_user.id
    if not (is_owner(uid) or is_valid_admin(uid)):
        if SHOW_START_TO_OTHERS: await q.edit_message_text("⛔ Access expired.")
        else: await q.edit_message_text("​")
        return

    if q.data == 'start_all':
        p = []
        for a in get_all_accounts(uid):
            if account_stats.get(a['id'],{}).get('running',False): p.append(f"✅ {get_display_name(a)} running")
            else:
                stop_flags[a['id']] = False
                running_tasks[a['id']] = asyncio.create_task(run_account_messaging(a, uid))
                p.append(f"▶️ {get_display_name(a)} started")
        await q.edit_message_text("\n".join(p) if p else "❌ No accounts!", reply_markup=BACK_KB)
    elif q.data == 'stop_all':
        p = []
        for a in get_all_accounts(uid):
            if account_stats.get(a['id'],{}).get('running',False): stop_account(a['id']); p.append(f"⏹️ {get_display_name(a)} stopping")
            else: p.append(f"✅ {get_display_name(a)} stopped")
        await q.edit_message_text("\n".join(p) if p else "✅ none running", reply_markup=BACK_KB)
    elif q.data == 'status':
        accs = get_all_accounts(uid); txt = "📊 *Status*\n\n"
        for i, a in enumerate(accs, 1):
            st = '🟢' if account_stats.get(a['id'],{}).get('running',False) else '🔴'
            txt += f"#{i} {get_display_name(a)}: {st} Sent:{account_stats.get(a['id'],{}).get('sent',0)}\n"
        if not accs: txt += "_None_\n"
        txt += f"\nTot: {sum(account_stats.get(a['id'],{}).get('sent',0) for a in accs)}"
        await q.edit_message_text(txt, parse_mode='Markdown', reply_markup=BACK_KB)
    elif q.data == 'profile_setup':
        accs = get_all_accounts(uid)
        cfg = get_default_profile(); nm = cfg.get('names',[]); ph = cfg.get('photos',[])
        kb = [[InlineKeyboardButton(f"⚙️ Default Profile (Names:{len(nm)}|Logos:{len(ph)})", callback_data='profdefault')],
              [InlineKeyboardButton("⚡ 1-CLICK APPLY ALL", callback_data='profapply_all')],
              [InlineKeyboardButton("🔙 Back", callback_data='back_main')]]
        if not accs: await q.edit_message_text("❌ No accounts!", reply_markup=BACK_KB); return
        await q.edit_message_text(f"🎨 *Profile Setup*\nApply por Status/Delete e notun name dekhabe.\n📊 {len(accs)}",
                                  parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb))
    elif q.data == 'profdefault':
        cfg = get_default_profile(); nm = cfg.get('names',[]); ph = cfg.get('photos',[]); ch = cfg.get('channels',[])
        txt = f"⚙️ *Profile*\n📝 Names({len(nm)}):\n" + "".join(f" {i}.`{x}`\n" for i,x in enumerate(nm,1))
        txt += f"🖼 Logos:{len(ph)} | 📄 Bio:`{cfg.get('bio','—')}`\n📢 Chan({len(ch)}):\n" + "".join(f" •`{x}`\n" for x in ch)
        kb = [[InlineKeyboardButton("➕ Name", callback_data='def_add_name'), InlineKeyboardButton("➖ Name", callback_data='def_del_name')],
              [InlineKeyboardButton("🖼 Add Logo", callback_data='def_add_photo'), InlineKeyboardButton("🗑 Del Logo", callback_data='def_del_photo')],
              [InlineKeyboardButton("📄 Bio", callback_data='def_bio')],
              [InlineKeyboardButton("📢 Channels", callback_data='def_chan')],
              [InlineKeyboardButton("♻️ Reset", callback_data='def_reset')],
              [InlineKeyboardButton("🔙 Back", callback_data='profile_setup')]]
        await q.edit_message_text(txt, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb))
    elif q.data == 'def_add_name': c.user_data['awaiting'] = 'def_add_name'; await q.edit_message_text("Line-wise names pathao:", reply_markup=BACK_KB)
    elif q.data == 'def_del_name':
        nm = get_default_profile().get('names',[])
        if not nm: await q.edit_message_text("❌ none", reply_markup=BACK_KB); return
        kb = [[InlineKeyboardButton(f"🗑 {i+1}.{x[:20]}", callback_data=f'def_delname_{i}')] for i,x in enumerate(nm)]
        kb.append([InlineKeyboardButton("Back", callback_data='profdefault')])
        await q.edit_message_text("Which?", reply_markup=InlineKeyboardMarkup(kb))
    elif q.data.startswith('def_delname_'):
        cfg = get_default_profile(); nm = cfg.get('names',[]); i = int(q.data.replace('def_delname_',''))
        if 0 <= i < len(nm): nm.pop(i); cfg['names'] = nm; save_default_profile(cfg)
        await q.edit_message_text("Deleted!", reply_markup=BACK_KB)
    elif q.data == 'def_add_photo': c.user_data['awaiting'] = 'def_add_photo'; await q.edit_message_text("Photo pathao:", reply_markup=BACK_KB)
    elif q.data == 'def_del_photo':
        ph = get_default_profile().get('photos',[])
        if not ph: await q.edit_message_text("❌ none", reply_markup=BACK_KB); return
        kb = [[InlineKeyboardButton(f"🗑 Logo #{i+1}", callback_data=f'def_delphoto_{i}')] for i in range(len(ph))]
        kb.append([InlineKeyboardButton("Back", callback_data='profdefault')])
        await q.edit_message_text("Which?", reply_markup=InlineKeyboardMarkup(kb))
    elif q.data.startswith('def_delphoto_'):
        cfg = get_default_profile(); ph = cfg.get('photos',[]); i = int(q.data.replace('def_delphoto_',''))
        if 0 <= i < len(ph): ph.pop(i); cfg['photos'] = ph; save_default_profile(cfg)
        await q.edit_message_text("Deleted!", reply_markup=BACK_KB)
    elif q.data == 'def_bio': c.user_data['awaiting'] = 'def_bio'; await q.edit_message_text("Bio likho:", reply_markup=BACK_KB)
    elif q.data == 'def_chan': c.user_data['awaiting'] = 'def_chan'; await q.edit_message_text("Links:", reply_markup=BACK_KB)
    elif q.data == 'def_reset': save_default_profile({}); await q.edit_message_text("Reset!", reply_markup=BACK_KB)
    elif q.data == 'profapply_all':
        accs = get_all_accounts(uid); cfg = get_default_profile()
        nm = cfg.get('names',[]); ph = cfg.get('photos',[]); bio = cfg.get('bio',''); ch = cfg.get('channels',[])
        if not accs or (not nm and not ph and not bio and not ch): await q.edit_message_text("❌ Add account/config first!", reply_markup=BACK_KB); return
        total = len(accs); prog = {'done':0,'lines':{}}
        sm = await q.edit_message_text("⚡ 0%")
        async def one(i, acc):
            try:
                rr = await apply_profile(acc, nm[i%len(nm)] if nm else '', ph[i%len(ph)] if ph else None, bio, ch, bot=c.bot)
                ok = sum(1 for x in rr if x.startswith('✅'))
                prog['lines'][i] = f"#{i+1} {get_display_name(acc)[:12]}: ✅{ok}"
            except Exception as e: prog['lines'][i] = f"#{i+1}: ❌ {str(e)[:30]}"
            prog['done'] += 1
        tasks = [asyncio.create_task(one(i,a)) for i,a in enumerate(accs)]
        while any(not t.done() for t in tasks):
            pct = int(prog['done']*100/total)
            try: await sm.edit_text(f"{'█'*(pct//10)}{'░'*(10-pct//10)} {pct}%")
            except: pass
            await asyncio.sleep(2)
        await asyncio.gather(*tasks, return_exceptions=True)
        await sm.edit_text("✅ *DONE!*\n\n" + "\n".join(prog['lines'][i] for i in sorted(prog['lines'])),
                           parse_mode='Markdown', reply_markup=BACK_KB)
    elif q.data == 'admin_panel':
        if not is_owner(uid): return
        kb = [[InlineKeyboardButton("➕ Add/Edit Time (+/-/=)", callback_data='add_admin')],
              [InlineKeyboardButton("📋 Admin List", callback_data='admin_list')],
              [InlineKeyboardButton("🔢 Set Account Limit", callback_data='set_admin_limit')],
              [InlineKeyboardButton(f"👻 Start-msg: {'ON' if SHOW_START_TO_OTHERS else 'OFF'}", callback_data='toggle_startmsg')],
              [InlineKeyboardButton("Back", callback_data='back_main')]]
        await q.edit_message_text("👑 *Admin Panel*\n`uid +30d` / `uid -10d` / `uid =perm`", reply_markup=InlineKeyboardMarkup(kb))
    elif q.data == 'set_admin_limit':
        if not is_owner(uid): return
        c.user_data['awaiting'] = 'admin_limit'; await q.edit_message_text("🔢 `USER_ID NUMBER` (0=unlimited):", parse_mode='Markdown', reply_markup=BACK_KB)
    elif q.data == 'admin_list':
        if not is_owner(uid): return
        admins = load_admins()
        if not admins: await q.edit_message_text("❌ none", reply_markup=BACK_KB); return
        txt = "📋 *Admins*\n\n"; kb = []
        for a in admins:
            accs = get_all_accounts(a['user_id'])
            cap = a.get('max_accounts'); cap_str = f"🔢 {len(accs)}/{cap}" if cap else f"🔢 {len(accs)}"
            txt += f"👤 `{a['user_id']}`\n ⏳ {remaining_time_str(a.get('expires_at'))}\n {cap_str}\n\n"
            kb.append([InlineKeyboardButton(f"🗑 Del {a['user_id']}", callback_data=f'del_admin_{a["user_id"]}')])
        kb.append([InlineKeyboardButton("Back", callback_data='admin_panel')])
        await q.edit_message_text(txt, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb))
    elif q.data.startswith('del_admin_'):
        if not is_owner(uid): return
        t = int(q.data.replace('del_admin_',''))
        save_admins([a for a in load_admins() if a['user_id'] != t]); stop_accounts_of(t)
        await q.edit_message_text(f"✅ Admin {t} deleted!", reply_markup=BACK_KB)
    elif q.data == 'add_admin':
        if not is_owner(uid): return
        c.user_data['awaiting'] = 'add_admin'; await q.edit_message_text("➕ `USER_ID [+|-|=]TIME`\n`111 +100000d` / `111 -10d` / `111 =perm`", parse_mode='Markdown', reply_markup=BACK_KB)
    elif q.data == 'toggle_startmsg':
        if not is_owner(uid): return
        SHOW_START_TO_OTHERS = not SHOW_START_TO_OTHERS; save_data()
        await q.edit_message_text(f"Start-msg {'ON' if SHOW_START_TO_OTHERS else 'OFF'}", reply_markup=BACK_KB)
    elif q.data == 'settings':
        if not is_owner(uid): return
        kb = [[InlineKeyboardButton("📊 Status", callback_data='status')],
              [InlineKeyboardButton("📝 Messages", callback_data='message_list')],
              [InlineKeyboardButton("⏱️ Speed", callback_data='edit_speed')],
              [InlineKeyboardButton("Back", callback_data='back_main')]]
        await q.edit_message_text(f"⚙️ *Settings*\n⏱️ {MIN_INTERVAL}-{MAX_INTERVAL}s | Cycle {CYCLE_WAIT}s", reply_markup=InlineKeyboardMarkup(kb))
    elif q.data == 'message_list':
        m = load_messages_for(uid); txt = f"📝 ({len(m)}):\n" + "".join(f"{i}.`{x[:20]}`\n" for i,x in enumerate(m,1))
        kb = [[InlineKeyboardButton("➕ Add", callback_data='add_message'), InlineKeyboardButton("🗑 Del", callback_data='delete_message_menu')],
              [InlineKeyboardButton("🔄 Reset", callback_data='reset_messages')],
              [InlineKeyboardButton("Back", callback_data='settings')]]
        await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb))
    elif q.data == 'add_message': c.user_data['awaiting'] = 'add_message'; await q.edit_message_text("✏️ New message:", reply_markup=BACK_KB)
    elif q.data == 'delete_message_menu':
        m = load_messages_for(uid)
        if not m: await q.edit_message_text("❌ none", reply_markup=BACK_KB); return
        kb = [[InlineKeyboardButton(f"{i+1}.{x[:15]}", callback_data=f'del_msg_{i}')] for i,x in enumerate(m)]
        kb.append([InlineKeyboardButton("Back", callback_data='message_list')])
        await q.edit_message_text("Which?", reply_markup=InlineKeyboardMarkup(kb))
    elif q.data.startswith('del_msg_'):
        m = load_messages_for(uid); i = int(q.data.replace('del_msg_',''))
        if 0 <= i < len(m): m.pop(i); save_messages_for(uid, m)
        await q.edit_message_text("Deleted", reply_markup=BACK_KB)
    elif q.data == 'reset_messages': save_messages_for(uid, [MESSAGE]); await q.edit_message_text("Reset", reply_markup=BACK_KB)
    elif q.data == 'edit_speed':
        if not is_owner(uid): return
        kb = [[InlineKeyboardButton(f"Min {MIN_INTERVAL}s", callback_data='set_min'), InlineKeyboardButton(f"Max {MAX_INTERVAL}s", callback_data='set_max')],
              [InlineKeyboardButton(f"Cycle {CYCLE_WAIT}s", callback_data='set_cycle')],
              [InlineKeyboardButton("Back", callback_data='settings')]]
        await q.edit_message_text("⏱️ Speed", reply_markup=InlineKeyboardMarkup(kb))
    elif q.data == 'set_min':
        if not is_owner(uid): return
        c.user_data['awaiting'] = 'min'; await q.edit_message_text(f"Min (1-{MAX_INTERVAL-1}):", reply_markup=BACK_KB)
    elif q.data == 'set_max':
        if not is_owner(uid): return
        c.user_data['awaiting'] = 'max'; await q.edit_message_text(f"Max (>{MIN_INTERVAL}):", reply_markup=BACK_KB)
    elif q.data == 'set_cycle':
        if not is_owner(uid): return
        c.user_data['awaiting'] = 'cycle'; await q.edit_message_text("Cycle (5+):", reply_markup=BACK_KB)
    elif q.data == 'phone_login':
        c.user_data['awaiting'] = 'phone_number'
        await q.edit_message_text("📱 *Phone Login*\n\nNumber pathao (e.g. `+8801XXXXXXXXX`):", parse_mode='Markdown', reply_markup=BACK_KB)
    elif q.data == 'add_account':
        c.user_data['awaiting'] = 'add_account'; await q.edit_message_text("Session string pathao:", reply_markup=BACK_KB)
    elif q.data == 'delete_account':
        accs = get_all_accounts(uid)
        if not accs: await q.edit_message_text("❌ none", reply_markup=BACK_KB); return
        kb = []
        for i, a in enumerate(accs, 1):
            ti = {'env':'💚','dynamic':'💙','phone_auth':'📱'}.get(a.get('type',''),'❓')
            kb.append([InlineKeyboardButton(f"{ti} #{i} {get_display_name(a)[:22]}", callback_data=f'del_acc_{a["id"]}')])
        kb += [[InlineKeyboardButton("🗑 Delete ALL", callback_data='del_all_accounts'), InlineKeyboardButton("Back", callback_data='back_main')]]
        await q.edit_message_text("Delete which?", reply_markup=InlineKeyboardMarkup(kb))
    elif q.data == 'del_all_accounts':
        d = [a for a in get_all_accounts(uid) if a.get('type') != 'env']
        kb = [[InlineKeyboardButton("☠️ YES", callback_data='del_all_confirm'), InlineKeyboardButton("No", callback_data='delete_account')]]
        await q.edit_message_text(f"Delete {len(d)} accounts?", reply_markup=InlineKeyboardMarkup(kb))
    elif q.data == 'del_all_confirm':
        n = 0
        for a in get_all_accounts(uid):
            if a.get('type') == 'env': continue
            stop_account(a['id']); remove_account_by_id(a['id']); await disconnect_client(a['id']); n += 1
        await q.edit_message_text(f"✅ {n} deleted!", reply_markup=BACK_KB)
    elif q.data.startswith('del_acc_'):
        acc_id = q.data.replace('del_acc_',''); t = None
        for a in get_all_accounts(uid):
            if a['id'] == acc_id: t = a; break
        if not t: await q.edit_message_text("⛔ invalid", reply_markup=BACK_KB); return
        nm = get_display_name(t)
        if account_stats.get(acc_id,{}).get('running',False): stop_account(acc_id); await asyncio.sleep(1)
        remove_account_by_id(acc_id); await disconnect_client(acc_id)
        for dd in (account_stats, stop_flags, running_tasks, display_names): dd.pop(acc_id, None)
        await q.edit_message_text(f"✅ {nm} deleted!", reply_markup=BACK_KB)
    elif q.data == 'back_main':
        c.user_data['awaiting'] = None; c.user_data.pop('login_id', None)
        refresh_account_stats(uid); preload_display_names(get_all_accounts(uid))
        await q.edit_message_text(main_menu_text(uid), parse_mode='Markdown', reply_markup=main_menu_keyboard(uid))

async def handle_photo(u, c):
    uid = u.effective_user.id
    if not (is_owner(uid) or is_valid_admin(uid)): return
    if c.user_data.get('awaiting') == 'def_add_photo':
        cfg = get_default_profile(); ph = cfg.get('photos',[]); ph.append(u.message.photo[-1].file_id)
        cfg['photos'] = ph; save_default_profile(cfg); c.user_data['awaiting'] = None
        await u.message.reply_text(f"✅ Logo #{len(ph)} saved!", reply_markup=BACK_KB)

async def handle_text(u, c):
    uid = u.effective_user.id
    if not (is_owner(uid) or is_valid_admin(uid)): return
    text = u.message.text.strip(); aw = c.user_data.get('awaiting')

    # ── Add/Edit admin time (owner) ──
    if aw == 'add_admin':
        c.user_data['awaiting'] = None
        if not is_owner(uid): return
        try: target, op, nd = parse_admin_cmd(text)
        except Exception:
            await u.message.reply_text("❌ e.g. `123456789 +30d` / `-10d` / `=perm`", parse_mode='Markdown'); return
        now = datetime.now()
        if target == OWNER_ID: await u.message.reply_text("❌ owner already boss"); return
        admins = load_admins(); a = get_admin(target)
        if a is None:
            a = {'user_id':target,'expires_at':None if nd is None else nd.isoformat(),
                 'added_at':now.isoformat(),'updated_at':now.isoformat(),'max_accounts':DEFAULT_ADMIN_LIMIT}
            admins.append(a); save_admins(admins)
            await u.message.reply_text(f"✅ Admin `{target}` added! ⏳ {remaining_time_str(a['expires_at'])}", parse_mode='Markdown'); return
        if nd is None:
            if op == '-': a['expires_at'] = now.isoformat(); chg = "expired now"
            else: a['expires_at'] = None; chg = "♾️ Permanent"
        else:
            cur = None
            try: cur = datetime.fromisoformat(a['expires_at']) if a.get('expires_at') else None
            except: cur = None
            rem = (cur - now) if (cur and cur > now) else timedelta(0)
            dl = nd - now
            if op == '=': ne = nd
            elif op == '-':
                ne = now + (rem - dl)
                if ne < now: ne = now
            else: ne = (max(now, cur) if cur else now) + dl
            a['expires_at'] = ne.isoformat(); chg = remaining_time_str(a['expires_at'])
        a['updated_at'] = now.isoformat(); save_admins(admins)
        await u.message.reply_text(f"✅ `{target}` → ⏳ {chg}", parse_mode='Markdown', reply_markup=BACK_KB); return

    # ── account limit (owner) ──
    if aw == 'admin_limit':
        c.user_data['awaiting'] = None
        if not is_owner(uid): return
        try:
            p = text.split(); t = int(p[0]); cap = int(p[1])
            if cap < 0: raise ValueError
        except Exception:
            await u.message.reply_text("❌ `USER_ID NUMBER` (0=unlimited)", parse_mode='Markdown'); return
        admins = load_admins(); ok = False
        for a in admins:
            if a['user_id'] == t: a['max_accounts'] = (None if cap == 0 else cap); ok = True
        if not ok: await u.message.reply_text(f"❌ Admin {t} nei!", parse_mode='Markdown'); return
        save_admins(admins)
        await u.message.reply_text(f"✅ `{t}` limit: {'unlimited' if cap == 0 else str(cap)}", parse_mode='Markdown', reply_markup=BACK_KB); return

    # ── profile inputs ──
    if aw == 'def_add_name':
        c.user_data['awaiting'] = None; cfg = get_default_profile(); nm = cfg.get('names',[])
        nn = [x.strip() for x in text.split('\n') if x.strip()]; nm += nn; cfg['names'] = nm; save_default_profile(cfg)
        await u.message.reply_text(f"✅ {len(nn)} added (total {len(nm)}).", reply_markup=BACK_KB); return
    if aw == 'def_bio':
        c.user_data['awaiting'] = None; cfg = get_default_profile(); cfg['bio'] = text; save_default_profile(cfg)
        await u.message.reply_text("✅ Bio set!", reply_markup=BACK_KB); return
    if aw == 'def_chan':
        c.user_data['awaiting'] = None; cfg = get_default_profile()
        cfg['channels'] = [x.strip() for x in re.split(r'[\n,]+', text) if x.strip()]; save_default_profile(cfg)
        await u.message.reply_text("✅ Links saved!", reply_markup=BACK_KB); return
    if aw == 'add_message':
        c.user_data['awaiting'] = None; m = load_messages_for(uid); m.append(text); save_messages_for(uid, m)
        await u.message.reply_text(f"✅ {len(m)} msgs", reply_markup=BACK_KB); return

    # ── PHONE LOGIN: number (full try/except, always ack) ──
    if aw == 'phone_number':
        c.user_data['awaiting'] = None
        try:
            ph = text.strip()
            if not ph.startswith('+'): ph = '+' + ph
            if not re.match(r'^\+\d{7,15}$', ph):
                await u.message.reply_text("❌ Invalid! e.g. `+8801XXXXXXXXX`", parse_mode='Markdown'); return
            reached, rm = account_limit_reached(uid)
            if reached: await u.message.reply_text(rm, parse_mode='Markdown'); return
            if not API_ID_1 or not API_HASH_1:
                await u.message.reply_text("❌ API env missing!", parse_mode='Markdown'); return
            # clean stale states for this user
            for ok in [k for k, v in phone_login_states.items() if v.get('owner_id') == uid]:
                old = phone_login_states.pop(ok, None)
                if old.get('client'):
                    try: await old['client'].disconnect()
                    except: pass
            sm = await u.message.reply_text("⏳ OTP pathacchi...", parse_mode='Markdown')
            client = None
            try:
                client = TelegramClient(StringSession(), API_ID_1, API_HASH_1, receive_updates=False)
                await client.connect()
                sent = await client.send_code_request(ph)
                lid = gen_unique_id("plogin", uid)
                phone_login_states[lid] = {'phone':ph,'api_id':API_ID_1,'api_hash':API_HASH_1,'client':client,
                                           'owner_id':uid,'phone_code_hash':sent.phone_code_hash,'created':datetime.now()}
                c.user_data['login_id'] = lid; c.user_data['awaiting'] = 'otp_code'
                await sm.edit_text("✅ OTP sent! Code likho:", parse_mode='Markdown', reply_markup=BACK_KB)
            except FloodWaitError as fw:
                try:
                    if client: await client.disconnect()
                except: pass
                await sm.edit_text(f"⏳ Flood {fw.seconds}s. Por try koro.", parse_mode='Markdown', reply_markup=BACK_KB)
            except Exception as e:
                try:
                    if client: await client.disconnect()
                except: pass
                logger.error(f"phone-code error: {e}")
                await sm.edit_text(f"❌ OTP fail: {str(e)[:160]}", parse_mode='Markdown', reply_markup=BACK_KB)
        except Exception as top:
            logger.error(f"phone_number top error: {top}")
            try: await u.message.reply_text(f"❌ err: {str(top)[:150]}", reply_markup=BACK_KB)
            except: pass
        return

    # ── OTP code ──
    if aw == 'otp_code':
        lid = c.user_data.get('login_id')
        st = phone_login_states.get(lid) if lid else None
        if not st:
            c.user_data['awaiting'] = None
            await u.message.reply_text("⏳ Flow reset. Abar Phone Login koro.", reply_markup=BACK_KB); return
        code = text.strip().replace(' ','').replace('-','')
        if not code.isdigit(): await u.message.reply_text("❌ digits only", reply_markup=BACK_KB); return
        client = st['client']
        sm = await u.message.reply_text("⏳ Verifying...", parse_mode='Markdown')
        try:
            await client.sign_in(phone=st['phone'], code=code, phone_code_hash=st['phone_code_hash'])
        except SessionPasswordNeededError:
            c.user_data['awaiting'] = '2fa_password'
            await sm.edit_text("🔐 2FA password:", parse_mode='Markdown', reply_markup=BACK_KB); return
        except PhoneCodeInvalidError:
            await sm.edit_text("❌ Wrong code. Abar chash:", reply_markup=BACK_KB); return
        except PhoneCodeExpiredError:
            try:
                sent = await client.send_code_request(st['phone']); st['phone_code_hash'] = sent.phone_code_hash
                await sm.edit_text("🔄 New code pathano! Abar likho:", reply_markup=BACK_KB)
            except Exception as e: await sm.edit_text(f"❌ {str(e)[:120]}", reply_markup=BACK_KB)
            return
        except Exception as e:
            await sm.edit_text(f"❌ {str(e)[:150]}", reply_markup=BACK_KB); return
        # build clean session fresh (prevents re-used-hash errors on next run)
        me = None; fresh = None
        try: await client.disconnect()
        except: pass
        try:
            c2 = TelegramClient(StringSession(), st['api_id'], st['api_hash'], receive_updates=False)
            await c2.connect(); await c2.sign_in(phone=st['phone'], code=code, phone_code_hash=st['phone_code_hash'])
            me = await c2.get_me(); fresh = c2.session.save(); await c2.disconnect()
        except Exception:
            try:
                await client.connect(); me = await client.get_me(); fresh = client.session.save(); await client.disconnect()
            except Exception as e: await sm.edit_text(f"❌ {str(e)[:120]}", reply_markup=BACK_KB); return
        reached, rm = account_limit_reached(st['owner_id'])
        if reached: await sm.edit_text(rm, reply_markup=BACK_KB); return
        au = load_auth_sessions()
        if any(s.get('owner_id')==st['owner_id'] and s.get('phone')==st['phone'] for s in au):
            await sm.edit_text("❌ Ei phone already ache!", reply_markup=BACK_KB); return
        nid = gen_unique_id("phone", st['owner_id'])
        fname = getattr(me,'first_name',None) or f"User{getattr(me,'id','?')}"
        au.append({'id':nid,'name':fname,'api_id':st['api_id'],'api_hash':st['api_hash'],'session_string':fresh,
                   'phone':st['phone'],'user_id':getattr(me,'id',None),'owner_id':st['owner_id'],
                   'login_time':datetime.now().isoformat()})
        save_auth_sessions(au); display_names[nid] = fname
        c.user_data['awaiting'] = None; c.user_data.pop('login_id', None)
        phone_login_states.pop(lid, None); refresh_account_stats(st['owner_id'])
        await sm.edit_text(f"✅ Login success!\n👤 {fname}\n🆔 `{getattr(me,'id','?')}`", parse_mode='Markdown', reply_markup=BACK_KB)
        return

    # ── 2FA ──
    if aw == '2fa_password':
        lid = c.user_data.get('login_id'); st = phone_login_states.get(lid) if lid else None
        if not st:
            c.user_data['awaiting'] = None; await u.message.reply_text("Flow reset. Abar login.", reply_markup=BACK_KB); return
        client = st['client']; sm = await u.message.reply_text("⏳...", parse_mode='Markdown')
        try: await client.sign_in(password=text.strip())
        except Exception as e: await sm.edit_text(f"❌ 2FA: {str(e)[:150]}", reply_markup=BACK_KB); return
        try:
            me = await client.get_me(); fresh = client.session.save(); await client.disconnect()
        except Exception as e: await sm.edit_text(f"❌ {str(e)[:120]}", reply_markup=BACK_KB); return
        reached, rm = account_limit_reached(st['owner_id'])
        if reached: await sm.edit_text(rm, reply_markup=BACK_KB); return
        au = load_auth_sessions()
        if any(s.get('owner_id')==st['owner_id'] and s.get('phone')==st['phone'] for s in au):
            await sm.edit_text("❌ Duplicate!", reply_markup=BACK_KB); return
        nid = gen_unique_id("phone", st['owner_id']); fname = getattr(me,'first_name',None) or "Unknown"
        au.append({'id':nid,'name':fname,'api_id':st['api_id'],'api_hash':st['api_hash'],'session_string':fresh,
                   'phone':st['phone'],'user_id':getattr(me,'id',None),'owner_id':st['owner_id'],
                   'login_time':datetime.now().isoformat()})
        save_auth_sessions(au); display_names[nid] = fname
        c.user_data['awaiting'] = None; c.user_data.pop('login_id', None)
        phone_login_states.pop(lid, None); refresh_account_stats(st['owner_id'])
        await sm.edit_text(f"✅ 2FA done! 👤 {fname}", parse_mode='Markdown', reply_markup=BACK_KB)
        return

    # ── Manual session add ──
    if aw == 'add_account':
        c.user_data['awaiting'] = None
        try:
            reached, rm = account_limit_reached(uid)
            if reached: await u.message.reply_text(rm, parse_mode='Markdown'); return
            sm = await u.message.reply_text("⏳ Testing...", parse_mode='Markdown')
            ok, name, _, fresh = await test_session_only(text)
            if not ok:
                await sm.edit_text("❌ Invalid/Dead session. Phone Login try koro.", reply_markup=BACK_KB); return
            suc, data = add_dynamic_account(name, fresh, uid)
            await sm.edit_text(f"✅ {name} added!" if suc else f"❌ {data}", reply_markup=BACK_KB)
        except Exception as e: await u.message.reply_text(f"❌ {str(e)[:160]}", reply_markup=BACK_KB)
        return

    # ── speed (owner) ──
    if aw in ('min','max','cycle') and not is_owner(uid): c.user_data['awaiting'] = None; return
    if aw == 'min':
        c.user_data['awaiting'] = None
        try:
            v = int(text)
            if 1 <= v < MAX_INTERVAL: MIN_INTERVAL = v; save_data(); await u.message.reply_text(f"Min {v}s")
            else: await u.message.reply_text(f"1-{MAX_INTERVAL-1}")
        except: await u.message.reply_text("❌ number")
    elif aw == 'max':
        c.user_data['awaiting'] = None
        try:
            v = int(text)
            if v > MIN_INTERVAL: MAX_INTERVAL = v; save_data(); await u.message.reply_text(f"Max {v}s")
            else: await u.message.reply_text(f">{MIN_INTERVAL}")
        except: await u.message.reply_text("❌ number")
    elif aw == 'cycle':
        c.user_data['awaiting'] = None
        try:
            v = int(text)
            if v >= 5: CYCLE_WAIT = v; save_data(); await u.message.reply_text(f"Cycle {v}s")
            else: await u.message.reply_text(">=5")
        except: await u.message.reply_text("❌ number")

async def main():
    global SHOW_START_TO_OTHERS
    print("BOT v5.1 START...", flush=True)
    await init_env_accounts()
    try: SHOW_START_TO_OTHERS = json.load(open(data_file)).get('show_start_to_others', True)
    except: pass
    load_data()
    for acc in get_all_accounts():
        aid = acc['id']; account_stats.setdefault(aid, {'sent':0,'running':False,'failed_channels':[]})
        stop_flags[aid] = False; display_names.setdefault(aid, acc.get('name'))
    valid = {OWNER_ID}
    for a in load_admins():
        if is_valid_admin(a['user_id']): valid.add(a['user_id'])
    for acc in get_all_accounts():
        if acc.get('owner_id', OWNER_ID) not in valid: stop_flags[acc['id']] = True
    for _ in range(5):
        try: httpx.post(f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook?drop_pending_updates=true"); break
        except: await asyncio.sleep(2)
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CallbackQueryHandler(button_click))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    await app.initialize(); await app.start()
    asyncio.create_task(admin_expiry_checker())
    ok_start = False
    for i in range(5):
        try:
            await app.updater.start_polling(drop_pending_updates=True, timeout=30, read_timeout=30, connect_timeout=30, allowed_updates=Update.ALL_TYPES)
            print("✅✅✅ BOT RUNNING ✅✅✅", flush=True); ok_start = True; break
        except Exception as e:
            if "Conflict" in str(e):
                try: httpx.post(f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook?drop_pending_updates=true")
                except: pass
                await asyncio.sleep(10*(i+1))
            else: print(f"❌ {str(e)[:120]}", flush=True); await asyncio.sleep(5)
    if not ok_start: print("❌ polling failed", flush=True); return
    try: await asyncio.Event().wait()
    except asyncio.CancelledError: pass
    finally:
        stop_all_accounts(); await asyncio.sleep(2)
        for fn in (app.updater.stop, app.stop, app.shutdown):
            try: await fn()
            except: pass

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    print(f"🌐 Flask {os.environ.get('PORT',10000)}", flush=True)
    try: asyncio.run(main())
    except KeyboardInterrupt: logger.info("exit")
    except Exception as e:
        print(f"❌ {e}", flush=True); import traceback; traceback.print_exc(); sys.exit(1)
