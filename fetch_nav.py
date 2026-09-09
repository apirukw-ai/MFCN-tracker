import os
import re
import datetime
from playwright.sync_api import sync_playwright
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

TARGET_FUNDS = ['MPF07', 'MPF15', 'MPF18', 'MPF19', 'MPF23', 'MPF27']

def fetch_mfc_nav():
    url = "https://mfcfund.com/unit-value/"
    nav_results = {}

    print(f"📡 กำลังเปิด Headless Browser เพื่อโหลด JavaScript จาก: {url}")

    try:
        # เปิด Playwright Chromium เพื่อรัน JavaScript หน้าเว็บ
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            # สั่งให้เปิดหน้าเว็บและรอจนกว่า network จะหยุดรัน (ตารางโหลดเสร็จ)
            page.goto(url, wait_until="networkidle", timeout=60000)
            
            # ดึง HTML ที่เบราว์เซอร์วาดตารางเสร็จเรียบร้อยแล้ว
            html_content = page.content()
            browser.close()

        soup = BeautifulSoup(html_content, 'html.parser')
        rows = soup.find_all('tr')
        print(f"ℹ️ พบแถวตาราง (tr) หลัง Render JavaScript: {len(rows)} แถว")

        for row in rows:
            row_text = row.get_text()
            for code in TARGET_FUNDS:
                if code in row_text and code not in nav_results:
                    numbers = re.findall(r'\b\d{1,4}\.\d{4}\b', row_text)
                    if numbers:
                        nav_val = float(numbers[0])
                        if 1.0 <= nav_val <= 500.0:
                            nav_results[code] = nav_val
                            print(f"✅ เจอ {code} -> NAV: {nav_val}")

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
