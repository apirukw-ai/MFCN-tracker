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

# รายชื่อรหัสกองทุน MFC PVD ที่ต้องการอัปเดต
TARGET_FUNDS = ['MPF07', 'MPF15', 'MPF18', 'MPF19', 'MPF23', 'MPF27']

def fetch_mfc_nav():
    url = "https://mfcfund.com/unit-value/"
    nav_results = {}

    print(f"📡 กำลังเปิด Headless Browser จาก: {url}")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            # เปิดหน้าเว็บและรอจนกว่า network จะนิ่ง
            page.goto(url, wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(3000)

            # 1. พยายามคลิกแถบ/ปุ่ม "กองทุนสำรองเลี้ยงชีพ" หากหน้าเว็บแยกหมวดหมู่ไว้
            try:
                pvd_element = page.locator("text='กองทุนสำรองเลี้ยงชีพ'").first
                if pvd_element.is_visible():
                    print("👆 พบหัวข้อ 'กองทุนสำรองเลี้ยงชีพ' กำลังคลิกเลือก...")
                    pvd_element.click()
                    page.wait_for_timeout(3000)
            except Exception as e:
                print(f"ℹ️ สกิปการคลิกเลือกหมวดหมู่: {e}")

            # 2. พยายามพิมพ์คำว่า MPF ในช่องค้นหา (ถ้ามี)
            try:
                search_box = page.locator("input[type='text'], input[type='search'], input[placeholder*='ค้นหา']").first
                if search_box.is_visible():
                    print("🔍 พบช่องค้นหา กำลังพิมพ์ 'MPF'...")
                    search_box.fill("MPF")
                    page.wait_for_timeout(2000)
            except Exception as e:
                pass

            html_content = page.content()
            browser.close()

        soup = BeautifulSoup(html_content, 'html.parser')
        rows = soup.find_all('tr')
        print(f"ℹ️ พบแถวตาราง (tr) ทั้งหมด: {len(rows)} แถว")

        # สแกนทีละแถว
        for row in rows:
            raw_text = row.get_text()
            # ตัดช่องว่าง/เว้นวรรคออก และแปลงเป็นตัวพิมพ์ใหญ่ เพื่อเปรียบเทียบ (เช่น "MPF 27" -> "MPF27")
            clean_text = re.sub(r'\s+', '', raw_text).upper()

            for code in TARGET_FUNDS:
                if code in clean_text and code not in nav_results:
                    # ค้นหาตัวเลข NAV (ทศนิยม 4 ตำแหน่ง หรือ 2-4 ตำแหน่ง)
                    matches = re.findall(r'\d[\d\,]*\.\d{4}', raw_text)
                    if not matches:
                        matches = re.findall(r'\d[\d\,]*\.\d{2,4}', raw_text)

                    for m in matches:
                        try:
                            val = float(m.replace(',', ''))
                            if 1.0 <= val <= 500.0:
                                nav_results[code] = val
                                print(f"✅ เจอ {code} -> NAV: {val}")
                                break
                        except ValueError:
                            continue

        # หากสแกนตารางแล้วยังไม่เจอ พิมพ์ตัวอย่างข้อความในตารางออกมาเพื่อตรวจสอบ
        if not nav_results and len(rows) > 0:
            print("⚠️ ยังไม่พบรหัสกองทุนเป้าหมาย ตัวอย่างข้อความในตารางที่ดึงมาได้:")
            for i, r in enumerate(rows[:8]):
                txt = r.get_text().strip().replace('\n', ' ')
                if txt:
                    print(f"  [Row {i+1}]: {txt[:100]}")

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
