import os
import re
import datetime
import requests
from bs4 import BeautifulSoup
from supabase import create_client, Client

# ==========================================
# 1. ตั้งค่าการเชื่อมต่อ Supabase
# ==========================================
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ Error: กรุณาตั้งค่า SUPABASE_URL และ SUPABASE_KEY ใน GitHub Secrets")
    exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# รายชื่อรหัสกองทุน MFC ที่ต้องการอัปเดต
TARGET_FUNDS = ['MPF07', 'MPF15', 'MPF18', 'MPF19', 'MPF23', 'MPF27']

def fetch_mfc_nav():
    url = "https://mfcfund.com/unit-value/"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'th-TH,th;q=0.9,en-US;q=0.8,en;q=0.7',
    }

    print(f"📡 กำลังดึงข้อมูล NAV จาก: {url}")
    nav_results = {}

    try:
        response = requests.get(url, headers=headers, timeout=25)
        print(f"ℹ️ HTTP Status: {response.status_code}")

        if response.status_code != 200:
            print(f"❌ ดึงข้อมูลไม่สำเร็จ HTTP Status: {response.status_code}")
            return nav_results

        html_content = response.text
        print(f"ℹ️ ขนาดความยาว HTML ที่ดึงได้: {len(html_content)} ตัวอักษร")

        soup = BeautifulSoup(html_content, 'html.parser')
        
        # --- วิธีที่ 1: ค้นหาจากแถวตาราง (Table Rows) ---
        rows = soup.find_all('tr')
        print(f"ℹ️ พบแถวตาราง (tr) ทั้งหมด: {len(rows)} แถว")

        for row in rows:
            row_text = row.get_text()
            for code in TARGET_FUNDS:
                if code in row_text and code not in nav_results:
                    # ดึงตัวเลขทศนิยม 4 ตำแหน่งในแถวนั้น
                    numbers = re.findall(r'\b\d{1,4}\.\d{4}\b', row_text)
                    if numbers:
                        nav_val = float(numbers[0])
                        if 1.0 <= nav_val <= 500.0:
                            nav_results[code] = nav_val
                            print(f"✅ [ค้นหาในตาราง] เจอ {code} -> NAV: {nav_val}")

        # --- วิธีที่ 2: หากตารางไม่เจอ ค้นหาข้อความรอบๆ ชื่อกองทุนใน HTML ---
        for code in TARGET_FUNDS:
            if code not in nav_results:
                pattern = re.compile(re.escape(code) + r'[\s\S]{1,150}?(\d{1,4}\.\d{4})')
                match = pattern.search(html_content)
                if match:
                    nav_val = float(match.group(1))
                    if 1.0 <= nav_val <= 500.0:
                        nav_results[code] = nav_val
                        print(f"✅ [ค้นหาจากข้อความ] เจอ {code} -> NAV: {nav_val}")

        return nav_results

    except Exception as e:
        print(f"❌ เกิดข้อผิดพลาดขณะดึง NAV: {e}")
        return nav_results

def update_supabase(nav_data):
    if not nav_data:
        print("⚠️ ไม่มีข้อมูล NAV ที่จะอัปเดต (nav_data เป็นค่าว่าง)")
        return

    today_str = datetime.date.today().isoformat()

    for fund_code, nav in nav_data.items():
        try:
            # 💡 หมายเหตุ: ปรับชื่อตาราง "funds" และชื่อคอลัมน์ให้ตรงกับ Supabase ของคุณ
            response = supabase.table("funds") \
                .update({
                    "nav": nav,
                    "updated_at": today_str
                }) \
                .eq("fund_code", fund_code) \
                .execute()
                
            print(f"💾 อัปเดต Supabase สำเร็จ: {fund_code} = {nav}")
        except Exception as e:
            print(f"❌ อัปเดต Supabase ไม่สำเร็จ ({fund_code}): {e}")

if __name__ == "__main__":
    print("🚀 เริ่มต้นกระบวนการ Auto Update NAV...")
    nav_data = fetch_mfc_nav()
    print(f"📊 สรุปข้อมูลที่ดึงได้ ({len(nav_data)} กองทุน): {nav_data}")
    update_supabase(nav_data)
    print("✨ ทำงานเสร็จสิ้น!")
