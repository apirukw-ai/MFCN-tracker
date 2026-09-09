import requests
import json

url = "https://www.scbam.com/medias/morning-star/scbam-morningstar.json"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json"
}

try:
    print("กำลังส่งคำขอไปยัง API...")
    response = requests.get(url, headers=headers, timeout=15)
    print(f"Status Code ที่ได้: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"ประเภทข้อมูลที่ได้: {type(data)}")
        
        # ลองปริ้นข้อความ 500 ตัวอักษรแรกออกมาดูว่าโครงสร้างหน้าตาเป็นอย่างไร
        text_data = json.dumps(data, ensure_ascii=False)
        print("ตัวอย่างข้อมูลบางส่วนที่เซิร์ฟเวอร์ส่งมา:")
        print(text_data[:500])
        
        # ลองหาคำว่า SCBNDQ ในข้อความดูว่ามีอยู่ไหม
        if "SCBNDQ" in text_data:
            print("\n✅ ข่าวดี: พบคำว่า SCBNDQ ในข้อมูลที่ดึงมาได้!")
        else:
            print("\n❌ ข่าวร้าย: ไม่พบชื่อกองทุนในข้อมูลชุดนี้ (ไฟล์อาจจะผิดหรือโครงสร้างเปลี่ยน)")
            
    else:
        print(f"ไม่สามารถโหลดข้อมูลได้ เซิร์ฟเวอร์ตอบกลับ: {response.text[:200]}")
except Exception as e:
    print(f"เกิดข้อผิดพลาดในการเชื่อมต่อ: {e}")
