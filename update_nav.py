import os
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta, date
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

        print(f"✅ อัปเดตข้อมูลเสร็จสิ้นเมื่อ: {now_thai}")

        # 📍 4. บันทึก Snapshot รวมทุกพอร์ตลง portfolio_history
        try:
            print("🔄 กำลังดึงมูลค่าพอร์ตอื่นๆ (GPF, SCB, DIME) จาก Firebase เพื่อรวมยอด...")

            # 4.1 คำนวณมูลค่า MFC ล่าสุด
            mfc_policies = supabase.table('policies').select('*').execute().data
            mfc_total = sum(float(p.get('nav', 0)) * float(p.get('units', 0)) for p in mfc_policies)

            # 4.2 ดึงอัตราแลกเปลี่ยน USD/THB
            fx_rate = 36.5
            try:
                fx_res = requests.get('https://open.er-api.com/v6/latest/USD', timeout=10).json()
                fx_rate = float(fx_res.get('rates', {}).get('THB', 36.5))
            except Exception as fx_err:
                print(f"⚠️ ดึง FX Rate ไม่สำเร็จ ใช้ค่าเริ่มต้น {fx_rate}: {fx_err}")

            # 4.3 ดึงยอด GPF จาก Firebase
            gpf_val = 0.0
            try:
                gpf_res = requests.get('https://scb-e-class-default-rtdb.asia-southeast1.firebasedatabase.app/gpf_ports/my-gpf-4750131.json', timeout=10).json()
                if gpf_res and 'funds' in gpf_res:
                    gpf_val = sum(float(f.get('units', 0)) * float(f.get('currentNav', 0)) for f in gpf_res.get('funds', []))
            except Exception as gpf_err:
                print(f"⚠️ ดึงข้อมูล GPF ไม่สำเร็จ: {gpf_err}")

            # 4.4 ดึงยอด SCB จาก Firebase
            scb_val = 0.0
            try:
                scb_res = requests.get('https://scb-e-class-default-rtdb.asia-southeast1.firebasedatabase.app/ports/my-scb-port.json', timeout=10).json()
                scb_funds = scb_res if isinstance(scb_res, list) else scb_res.get('funds', []) if isinstance(scb_res, dict) else []
                scb_val = sum(float(f.get('units', 0)) * float(f.get('currentNav', 0)) for f in scb_funds if isinstance(f, dict))
            except Exception as scb_err:
                print(f"⚠️ ดึงข้อมูล SCB ไม่สำเร็จ: {scb_err}")

            # 4.5 ดึงยอด DIME จาก Firebase (แปลง USD เป็น THB)
            dime_val = 0.0
            try:
                dime_res = requests.get('https://scb-e-class-default-rtdb.asia-southeast1.firebasedatabase.app/dime_summary/current.json', timeout=10).json()
                if dime_res:
                    dime_usd = float(dime_res.get('value', 0))
                    dime_val = dime_usd * fx_rate
            except Exception as dime_err:
                print(f"⚠️ ดึงข้อมูล DIME ไม่สำเร็จ: {dime_err}")

            # 4.6 รวม Total Wealth ทั้งหมด
            total_wealth = mfc_total + gpf_val + scb_val + dime_val

            # 4.7 บันทึก/อัปเดตลง Supabase portfolio_history
            record_payload = {
                'record_date': str(date.today()),
                'mfc_val': round(mfc_total, 2),
                'gpf_val': round(gpf_val, 2),
                'scb_val': round(scb_val, 2),
                'dime_val': round(dime_val, 2),
                'total_wealth': round(total_wealth, 2)
            }

            supabase.table('portfolio_history').upsert(record_payload, on_conflict='record_date').execute()
            print(f"📈 บันทึกประวัติสมบูรณ์! Total Wealth: ฿{total_wealth:,.2f} (MFC: ฿{mfc_total:,.2f}, GPF: ฿{gpf_val:,.2f}, SCB: ฿{scb_val:,.2f}, DIME: ฿{dime_val:,.2f})")

        except Exception as hist_err:
            print(f"⚠️ บันทึกประวัติลง portfolio_history ไม่สำเร็จ: {hist_err}")

    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    fetch_and_update()
