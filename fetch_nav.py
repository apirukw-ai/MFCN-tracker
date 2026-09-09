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
# 2. จับคู่รหัส PVD (MPFxx) -> ชื่อกองทุนหลักบนหน้าเว็บ
# (สามารถเพิ่ม/แก้ไข ชื่อตัวเลือกใน List ของแต่ละ MPF ได้ตามจริง)
# ==========================================
FUND_MAP = {
    'MPF07': ['IGOLD-G', 'IGOLD'],
    'MPF15': ['MTECH', 'M-TECH'],
    'MPF18': ['MVIET', 'M-VIET', 'MEMERGE'],
    'MPF19': ['MPF19', 'M-PROP'],
    'MPF23': ['MPF23', 'M-MIDSMALL'],
    'MPF27': ['MPF27', 'MVIET']
}

def fetch_mfc_nav():
    url = "https://mfcfund.com/unit-value/"
    nav_results = {}

    print(f"📡 กำลังเปิด Headless Browser เพื่อดึงข้อมูลจาก: {url}")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            page.goto(url, wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(3000)

            html_content = page.content()
            browser.close()

        soup = BeautifulSoup(html_content, 'html.parser')
        rows = soup.find_all('tr')
        print(f"ℹ️ พบแถวตาราง (tr) ทั้งหมด: {len(rows)} แถว")

        for row in rows:
            raw_text = row.get_text()
            # ตัดช่องว่าง ขีด และแปลงเป็นตัวพิมพ์ใหญ่ เพื่อเปรียบเทียบข้อความได้แม่นยำ
            clean_text = re.sub(r'[\s\-]+', '', raw_text).upper()

            for pvd_code, aliases in FUND_MAP.items():
                if pvd_code in nav_results:
                    continue  # หากเจอค่าของกองทุนนี้แล้ว ให้ข้ามไป

                for alias in aliases:
                    clean_alias = re.sub(r'[\s\-]+', '', alias).upper()
                    
                    if clean_alias in clean_text:
                        # ดึงตัวเลข NAV (ทศนิยม 4 ตำแหน่ง)
                        matches = re.findall(r'\d[\d\,]*\.\d{4}', raw_text)
                        if matches:
                            try:
                                nav_val = float(matches[0].replace(',', ''))
                                if 1.0 <= nav_val <= 500.0:
                                    nav_results[pvd_code] = nav_val
                                    print(f"✅ เจอ {pvd_code} (จากชื่อบนเว็บ '{alias}') -> NAV: {nav_val}")
                                    break
                            except ValueError:
                                continue

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
