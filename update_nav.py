import os
from datetime import datetime, timezone, timedelta
from supabase import create_client, Client

# 1. ตั้งค่าการเชื่อมต่อ Supabase
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")

if not url or not key:
    print("❌ Missing Supabase Credentials")
    exit(1)

supabase: Client = create_client(url, key)

def fetch_and_update():
    try:
        # 2. คำนวณเวลาปัจจุบันของประเทศไทย (UTC+7)
        thai_tz = timezone(timedelta(hours=7))
        now_thai = datetime.now(thai_tz).strftime('%d/%m/%Y %H:%M:%S')

        # 3. ดึงรายการกองทุนจาก Supabase
        res = supabase.table('policies').select('*').execute()
        policies = res.data

        for policy in policies:
            code = policy.get('code')
            print(f"🔄 Checking {code}...")

            # --- จุดที่มีการอัปเดต NAV ให้ส่ง updated_at ไปด้วย ---
            # ตัวอย่างการอัปเดตค่าเมื่อได้ NAV ใหม่:
            # new_nav = 18.7135 
            # supabase.table('policies').update({
            #     'nav': new_nav,
            #     'prev_amt': policy['nav'] * policy['units'],
            #     'updated_at': now_thai                     # 👈 ส่ง Timestamp เวลาไทยไปลง DB
            # }).eq('id', policy['id']).execute()

            # หรือหากต้องการบันทึกแค่เวลาอัปเดตล่าสุดไว้ทดสอบ:
            supabase.table('policies').update({
                'updated_at': now_thai
            }).eq('id', policy['id']).execute()

        print(f"✅ Updated timestamp at: {now_thai}")

    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    fetch_and_update()
