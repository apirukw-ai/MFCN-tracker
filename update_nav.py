import os
import requests
from supabase import create_client, Client

# 1. เชื่อมต่อ Supabase
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") # หรือ Anon Key
supabase: Client = create_client(url, key)

# 2. ดึงข้อมูลกองทุนเดิมจาก Supabase
response = supabase.table('policies').select('*').execute()
policies = response.data

for policy in policies:
    fund_code = policy['code'] # เช่น MPF23, MPF15
    
    # 3. ดึงค่า NAV วันนี้จาก API หรือ Web Scraping (ตัวอย่าง API สมมติ / SEC Open API)
    # หมายเหตุ: สามารถใช้ API ของ ก.ล.ต. (SEC Open API) หรือ API กองทุนรวมไทยได้
    try:
        # สมมติการเรียก API NAV กองทุน
        nav_api_url = f"https://api.sec.or.th/FundFactsheet/fund/{fund_code}/nav"
        # nav_today = ... ดึงค่า NAV จาก API ...
        
        # 4. หาก NAV มีการเปลี่ยนแปลง ให้ย้าย nav เดิมไปเป็น prev_amt แล้วบันทึก nav ใหม่
        # supabase.table('policies').update({
        #     'nav': nav_today,
        #     'prev_amt': policy['nav'] * policy['units']
        # }).eq('id', policy['id']).execute()
        
        print(f"✅ Updated {fund_code}")
    except Exception as e:
        print(f"❌ Failed to update {fund_code}: {e}")
