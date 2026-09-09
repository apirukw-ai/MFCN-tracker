import os
import re
import datetime
import requests
from supabase import create_client, Client

# ==========================================
# 1. ตั้งค่าการเชื่อมต่อ Supabase
# ==========================================
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ Error: กรุณาตั้งค่า SUPABASE_URL และ SUPABASE_SERVICE_ROLE_KEY ใน GitHub Secrets")
    exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ==========================================
# 2. จับคู่ asset_name ใน Supabase -> ชื่อสัญลักษณ์บนเว็บ SCBAM
# ==========================================
FUND_MAP = {
    'SCBAXJ(E)':   ['SCBAXJ(E)', 'SCBAXJ-E', 'SCBAXJ'],
    'SCBNDQ(E)':   ['SCBNDQ(E)', 'SCBNDQ-E', 'SCBNDQ'],
    'SCBS&P500E':  ['SCBS&P500E', 'SCBS&P500(E)', 'SCBS&P500-E', 'SCBS&P500'],
    'SCBSEMI(E)':  ['SCBSEMI(E)', 'SCBSEMI-E', 'SCBSEMI'],
    'SCBWORLD(E)': ['SCBWORLD(E)', 'SCBWORLD-E', 'SCBWORLD']
}

def fetch_scb_nav():
    # URL API ตรงจากหน้าเว็บ SCB Morningstar
    url = "https://www.scbam.com/medias/morning-star/scbam-morningstar.json"
    nav_results = {}

    print(f"📡 กำลังดึงข้อมูลผ่าน API JSON โดยตรงจาก: {url}")

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept': 'application/json'
    }

    try:
        # ใช้ requests ดึงข้อมูลตรงๆ ได้เลย ไม่ต้องใช้เบราว์เซอร์จำลอง
        response = requests.get(url, headers=headers, timeout=20)
        
        if response.status_code != 200:
            print(f"❌ ดึงข้อมูลไม่สำเร็จ HTTP Status: {response.status_code}")
            return nav_results

        # โหลดข้อมูล JSON มาในรูปแบบตัวอักษร
        data_text = response.text

        # ใช้ Regex สแกนหาชื่อกองทุนและตัวเลข NAV (ทศนิยม 4 ตำแหน่ง) ที่อยู่ใกล้เคียงกัน
        for asset_name, aliases in FUND_MAP.items():
            for alias in aliases:
                # ป้องกันข้อผิดพลาดของสัญลักษณ์พิเศษด้วย re.escape
                # ค้นหา alias ตามด้วยข้อความอะไรก็ได้ไม่เกิน 150 ตัวอักษร แล้วค่อยหาทศนิยม 4 ตำแหน่ง
                pattern = re.compile(re.escape(alias) + r'[\s\S]{1,150}?(\d{1,4}\.\d{4})', re.IGNORECASE)
                match = pattern.search(data_text)
                
                if match:
                    try:
                        nav_val = float(match.group(1))
                        # ตรวจสอบความสมเหตุสมผลของ NAV
                        if 1.0 <= nav_val <= 500.0:
                            nav_results[asset_name] = nav_val
                            print(f"✅ เจอ {asset_name} (จาก '{alias}') -> NAV: {nav_val}")
                            break
                    except ValueError:
                        continue

        return nav_results

    except Exception as e:
        print(f"❌ เกิดข้อผิดพลาดขณะดึง NAV ของ SCB: {e}")
        return nav_results

def update_supabase(nav_data):
    if not nav_data:
        print("⚠️ ไม่มีข้อมูล NAV ที่จะอัปเดต")
        return

    for asset_name, nav in nav_data.items():
        try:
            response = supabase.table("user_portfolios") \
                .update({"current_nav": nav}) \
                .eq("asset_name", asset_name) \
                .execute()
                
            print(f"💾 อัปเดต Supabase สำเร็จ: {asset_name} = {nav}")
        except Exception as e:
            print(f"❌ อัปเดต Supabase ไม่สำเร็จ ({asset_name}): {e}")

if __name__ == "__main__":
    print("🚀 เริ่มต้นกระบวนการ Auto Update NAV (SCB API)...")
    nav_data = fetch_scb_nav()
    print(f"📊 สรุปข้อมูลที่ดึงได้ ({len(nav_data)} กองทุน): {nav_data}")
    update_supabase(nav_data)
    print("✨ ทำงานเสร็จสิ้น!")
