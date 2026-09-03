import os
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta
from supabase import create_client, Client

# 1. เชื่อมต่อ Supabase
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")

if not url or not key:
    print("❌ Missing Supabase Credentials")
    exit(1)

supabase: Client = create_client(url, key)

def get_nav_from_mfc_page(fund_code, fund_name, html_content):
    """ค้นหาตัวเลข NAV โดยใช้ทั้งรหัสกองทุน และ ชื่อกองทุน"""
    if not html_content:
        return None
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # ทำความสะอาดคำค้นหา (ตัดช่องว่างและเปลี่ยนเป็นตัวพิมพ์เล็ก)
        clean_code = fund_code.replace(' ', '').lower() if fund_code else ""
        clean_name = fund_name.replace(' ', '').lower() if fund_name else ""

        for row in soup.find_all('tr'):
            row_text = row.get_text(strip=True)
            clean_row = row_text.replace(' ', '').lower()
            
            # ตรวจสอบว่าในแถวนั้นมี รหัส หรือ ชื่อกองทุน ตรงกันหรือไม่
            is_match = False
            if clean_code and clean_code in clean_row:
                is_match = True
            elif clean_name and clean_name in clean_row:
                is_match = True

            if is_match:
                # ดึงตัวเลขทศนิยม (NAV) จากแถวนั้น
                numbers = re.findall(r'\d+\.\d{4}', row_text)
                if numbers:
                    return float(numbers[0])
    except Exception as e:
        print(f"⚠️ เกิดข้อผิดพลาดในการแกะข้อมูล {fund_code} / {fund_name}: {e}")
    return None

def fetch_and_update():
    try:
        # เวลาประเทศไทย (UTC+7)
        thai_tz = timezone(timedelta(hours=7))
        now_thai = datetime.now(thai_tz).strftime('%d/%m/%Y %H:%M:%S')

        # 2. ดึงหน้า HTML จากเว็บ MFC
        target_url = "https://mfcfund.com/unit-value/"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        print("🌐 กำลังโหลดข้อมูลจาก https://mfcfund.com/unit-value/...")
        res = requests.get(target_url, headers=headers, timeout=20)
        html_content = res.text if res.status_code == 200 else ""

        if res.status_code != 200:
            print(f"❌ ไม่สามารถเข้าถึงหน้าเว็บ MFC ได้ Status Code: {res.status_code}")

        # 3. ดึงรายการกองทุนทั้งหมดจาก Supabase
        db_res = supabase.table('policies').select('*').execute()
        policies = db_res.data

        for policy in policies:
            code = policy.get('code', '')
            name = policy.get('name', '')  # ดึงชื่อกองทุนจาก Supabase
            current_nav = float(policy.get('nav', 0))
            units = float(policy.get('units', 0))

            print(f"🔄 กำลังค้นหา NAV ของ {code} - {name}...")

            # ค้นหา NAV โดยใช้ทั้ง Code และ Name
            latest_nav = get_nav_from_mfc_page(code, name, html_content)

            if latest_nav and latest_nav != current_nav:
                prev_amt = current_nav * units
                supabase.table('policies').update({
                    'nav': latest_nav,
                    'prev_amt': prev_amt,
                    'updated_at': now_thai
                }).eq('id', policy['id']).execute()
                print(f"✅ อัปเดตสำเร็จ {code}: {current_nav} ➔ {latest_nav}")
            else:
                supabase.table('policies').update({
                    'updated_at': now_thai
                }).eq('id', policy['id']).execute()
                print(f"ℹ️ {code} ราคาล่าสุด: {latest_nav if latest_nav else current_nav} (ไม่เปลี่ยนแปลง)")

        # บรรทัด 97 เดิม
        print(f"✅ อัปเดตข้อมูลเสร็จสิ้นเมื่อ: {now_thai}")

        # 📍 เพิ่มโค้ดส่วนนี้ต่อจากบรรทัด 97
        try:
            # ดึงมูลค่ารวมของ MFC ล่าสุดจากตาราง policies
            mfc_policies = supabase.table('policies').select('*').execute().data
            mfc_total = sum(float(p.get('nav', 0)) * float(p.get('units', 0)) for p in mfc_policies)

            # บันทึก Snapshot ลงตาราง portfolio_history
            from datetime import date
            supabase.table('portfolio_history').insert({
                'record_date': str(date.today()),
                'mfc_val': mfc_total
            }).execute()
            print("📈 บันทึกประวัติ MFC ลง portfolio_history เรียบร้อย")
        except Exception as hist_err:
            print(f"⚠️ บันทึกประวัติไม่สำเร็จ: {hist_err}")

    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    fetch_and_update()
