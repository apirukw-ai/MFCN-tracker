import os
import requests
from supabase import create_client, Client

# 1. ดึง Keys จาก Environment Variables
SEC_API_KEY = os.environ.get("SEC_API_KEY")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if not SEC_API_KEY:
    raise ValueError("ไม่พบ SEC_API_KEY ในระบบ!")

# 2. ตั้งค่า Header สำหรับ SEC Open API
headers = {
    'Ocp-Apim-Subscription-Key': SEC_API_KEY,
    'Content-Type': 'application/json'
}

# 3. ยิง API ขอข้อมูลจาก ก.ล.ต.
# ตัวอย่าง Endpoint ดึงข้อมูล บลจ. หรือ NAV
url = "https://api.sec.or.th/v2/fund/general-info/amcs"

try:
    response = requests.get(url, headers=headers, timeout=15)
    
    if response.status_code == 200:
        data = response.json()
        print("เชื่อมต่อ SEC Open API สำเร็จ!")
        # นำข้อมูลที่ได้ไปอัปเดตลง Supabase...
    else:
        print(f"เกิดข้อผิดพลาดจาก SEC API (Status {response.status_code}): {response.text}")

except Exception as e:
    print(f"Connection Error: {e}")
