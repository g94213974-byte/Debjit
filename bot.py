#!/usr/bin/env python3
"""টেস্ট - Session সেভ হচ্ছে কিনা চেক করুন"""
import os, asyncio
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError, PhoneCodeExpiredError

API_ID = 34124317
API_HASH = "b6a4101c735dda0625454c22b579d702"
PHONE = "+880..."  # আপনার ফোন
SESSIONS_DIR = "sessions"
os.makedirs(SESSIONS_DIR, exist_ok=True)

async def test_login():
    sn = "test_account_1"
    session_path = os.path.join(SESSIONS_DIR, sn)
    
    # STEP 1: OTP পাঠান
    client = TelegramClient(session_path, API_ID, API_HASH)
    await client.connect()
    
    if await client.is_user_authorized():
        me = await client.get_me()
        print(f"✅ ইতিমধ্যে লগইন! {me.first_name}")
        await client.disconnect()
        return
    
    result = await client.send_code_request(PHONE)
    phone_code_hash = result.phone_code_hash
    print(f"✅ OTP পাঠানো হয়েছে (hash: {phone_code_hash[:10]}...)")
    
    # STEP 2: ইউজারকে OTP ইনপুট নিন
    code = input("OTP কোড দিন (5 digit): ").strip()
    
    try:
        await client.sign_in(
            phone=PHONE,
            code=code,
            phone_code_hash=phone_code_hash
        )
        
        me = await client.get_me()
        print(f"✅ লগইন সফল! {me.first_name}")
        
        # 🔥 ফিক্স: API কল করুন session ফ্লাশ করার জন্য
        await client.get_me()  # session ডাটা ফ্লাশ হবে
        
        # 🔥 ফিক্স: disconnect() - এতেই session ফাইল তৈরি হবে
        await client.disconnect()
        
        # চেক করুন
        sf = os.path.join(SESSIONS_DIR, f"{sn}.session")
        if os.path.exists(sf):
            print(f"✅ Session সেভ হয়েছে! ফাইল: {sf} ({os.path.getsize(sf)} bytes)")
        else:
            print(f"❌ Session ফাইল নেই!")
            
    except PhoneCodeInvalidError:
        print("❌ OTP ভুল!")
    except PhoneCodeExpiredError:
        print("❌ OTP মেয়াদ শেষ!")
    except SessionPasswordNeededError:
        pwd = input("2FA পাসওয়ার্ড দিন: ").strip()
        await client.sign_in(password=pwd)
        me = await client.get_me()
        print(f"✅ 2FA লগইন! {me.first_name}")
        await client.get_me()
        await client.disconnect()
        
        sf = os.path.join(SESSIONS_DIR, f"{sn}.session")
        if os.path.exists(sf):
            print(f"✅ Session সেভ হয়েছে! ({os.path.getsize(sf)} bytes)")
        else:
            print(f"❌ Session ফাইল নেই!")

asyncio.run(test_login())
