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
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ Error: กรุณาตั้งค่า SUPABASE_URL และ SUPABASE_SERVICE_ROLE_KEY ใน GitHub Secrets")
    exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# รายชื่อรหัสกองทุน MFC (PVD) ที่ต้องการอัปเดต
TARGET_FUNDS = ['MPF07', 'MPF15', 'MPF18', 'MPF19', 'MPF23', 'MPF27']

def fetch_mfc_nav():
    url = "https://mfcfund.com/unit-value/"
    
    # ป้องกันการโดนบล็อก IP โดยจำลอง Header ให้เหมือนเบราว์เซอร์จริง
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'th-TH,th;q=0.9,en-US;q=0.8,en;q=0.7',
        'Cache-Control': 'no-cache'
    }

    print(f"📡 กำลังดึงข้อมูล NAV จาก: {url}")
    
    try:
        response = requests.get(url, headers=headers, timeout=20)
        
        # เช็ค HTTP Status Code
        if response.status_code != 200:
            print(f"❌ ดึงข้อมูลไม่สำเร็จ HTTP Status: {response.status_code}")
            return {}

        # เช็คว่าติดหน้า Security/Cloudflare หรือไม่
        if "Just a moment..." in response.text or "Cloudflare" in response.text:
            print("❌ โดนระบบความปลอดภัยของเว็บปลายทางบล็อก (Cloudflare)")
            return {}

        # ใช้ BeautifulSoup เจาะอ่านโครงสร้าง HTML DOM
        soup = BeautifulSoup(response.text, 'html.parser')
        nav_results = {}

        # ค้นหาเฉพาะในแถวตาราง <tr> เท่านั้น เพื่อไม่ให้โดนเลขอื่นรบกวน
        rows = soup.find_all('tr')
        
        for row in rows:
            row_text = row.get_text()
            
            for code in TARGET_FUNDS:
                if code in row_text:
                    cols = row.find_all(['td', 'th'])
                    
                    # ค้นหาช่องที่มีตัวเลข NAV
                    for col in cols:
                        val = col.get_text().strip().replace(',', '')
                        
                        # Regex ล็อคเฉพาะรูปแบบตัวเลข NAV (ทศนิยม 4 ตำแหน่ง เช่น 10.5654 หรือ 123.4567)
                        match = re.search(r'^\d{1,4}\.\d{4}$', val)
                        if match:
                            nav_val = float(match.group(0))
                            
                            # Validation: ตรวจสอบความถูกต้อง (NAV กองทุนทั่วไปควรอยู่ระหว่าง 1.0 - 500.0)
                            if 1.0 <= nav_val <= 500.0:
                                nav_results[code] = nav_val
                                print(f"✅ เจอ {code} -> NAV: {nav_val}")
                                break

        return nav_results

    except Exception as e:
        print(f"❌ เกิดข้อผิดพลาดขณะดึง NAV: {e}")
        return {}

def update_supabase(nav_data):
    if not nav_data:
        print("⚠️ ไม่มีข้อมูล NAV ที่จะอัปเดต")
        return

    today_str = datetime.date.today().isoformat()

    for fund_code, nav in nav_data.items():
        try:
            # 💡 หมายเหตุ: ปรับชื่อตาราง (เช่น 'funds') และชื่อ Column ให้ตรงกับใน Supabase ของคุณ
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
