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

# ==========================================
# 2. จับคู่ asset_name ใน Supabase -> ชื่อสัญลักษณ์/คำค้นหาบนเว็บ SCBAM
# ==========================================
FUND_MAP = {
    'SCBAXJ(E)':   ['SCBAXJ(E)', 'SCBAXJ-E', 'SCBAXJ'],
    'SCBNDQ(E)':   ['SCBNDQ(E)', 'SCBNDQ-E', 'SCBNDQ'],
    'SCBS&P500E':  ['SCBS&P500E', 'SCBS&P500(E)', 'SCBS&P500-E', 'SCBS&P500'],
    'SCBSEMI(E)':  ['SCBSEMI(E)', 'SCBSEMI-E', 'SCBSEMI'],
    'SCBWORLD(E)': ['SCBWORLD(E)', 'SCBWORLD-E', 'SCBWORLD']
}

def fetch_scb_nav():
    url = "https://www.scbam.com/th/fund/fund-price"
    nav_results = {}

    print(f"📡 กำลังเปิด Headless Browser เพื่อดึงข้อมูล NAV จาก SCBAM: {url}")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            # เปิดหน้าเว็บและรอให้ JavaScript โหลดตารางราคาเสร็จ
            page.goto(url, wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(4000)

            html_content = page.content()
            browser.close()

        soup = BeautifulSoup(html_content, 'html.parser')
        rows = soup.find_all('tr')
        print(f"ℹ️ พบแถวตาราง (tr) ทั้งหมด: {len(rows)} แถว")

        for row in rows:
            raw_text = row.get_text()
            # ทำความสะอาดข้อความเพื่อเปรียบเทียบง่ายขึ้น (ลบช่องว่าง ขีด วงเล็บ และสัญลักษณ์พิเศษ)
            clean_text = re.sub(r'[\s\-\(\)\&]+', '', raw_text).upper()

            for asset_name, aliases in FUND_MAP.items():
                if asset_name in nav_results:
                    continue

                for alias in aliases:
                    clean_alias = re.sub(r'[\s\-\(\)\&]+', '', alias).upper()
                    
                    if clean_alias in clean_text:
                        # ดึงตัวเลขทศนิยม 4 ตำแหน่ง
                        matches = re.findall(r'\d[\d\,]*\.\d{4}', raw_text)
                        if matches:
                            try:
                                nav_val = float(matches[0].replace(',', ''))
                                if 1.0 <= nav_val <= 500.0:
                                    nav_results[asset_name] = nav_val
                                    print(f"✅ เจอ {asset_name} (จากชื่อบนเว็บ '{alias}') -> NAV: {nav_val}")
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
    print("🚀 เริ่มต้นกระบวนการ Auto Update NAV (SCB)...")
    nav_data = fetch_scb_nav()
    print(f"📊 สรุปข้อมูลที่ดึงได้ ({len(nav_data)} กองทุน): {nav_data}")
    update_supabase(nav_data)
    print("✨ ทำงานเสร็จสิ้น!")
