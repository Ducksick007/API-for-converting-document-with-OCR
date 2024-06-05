import pytesseract as tess
from PIL import Image
import re
import enchant
import difflib

from flask import Flask, render_template, request, jsonify
import requests
from flask_cors import CORS
app = Flask(__name__)
CORS(app, resources={r"/extract-text": {"origins": "http://localhost:4000"}})

@app.route('/', methods=['POST'])
def home():
    return render_template('index.html')

def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ตั้งค่าเส้นทางไปยัง Tesseract
tess.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# สร้างพจนานุกรมสำหรับตรวจคำผิด
d = enchant.Dict("en_US")

# เพิ่มคำใหม่ในพจนานุกรม
new_words = ["tha", "หัวแปลง", "พร้อมชุดหัวแปลงไอโฟน", "อุปกรณ์สตรีมเมอร์", "HDMI", "Avermedia"]
for word in new_words:
    d.add(word)

@app.route('/extract-text', methods=['POST'])
def extract_text():
    try:
        # Check if a file was uploaded
        if 'image' not in request.files:
            return jsonify({'message': 'No file part'}), 400

        file = request.files['image']
        
        # Check if the file is empty
        if file.filename == '':
            return jsonify({'message': 'No selected file'}), 400

        # Check if the file is an allowed type
        if not allowed_file(file.filename):
            return jsonify({'message': 'File type not allowed'}), 400

        # อ่านรูปภาพและแปลงเป็นข้อความ
        image = Image.open(file)
        text = tess.image_to_string(image, lang='tha+eng')

        # รูปแบบ regex สำหรับข้อมูลผู้ส่ง
        sender_pattern = re.compile(r'(ผู้ส่ง \(FROM\)|Has \(FROM\)|Was \(FROM\))\s*(.+?)\n(.*?จังหวัด.+? \d+)', re.DOTALL)

        # รูปแบบ regex สำหรับข้อมูลผู้รับ
        recipient_pattern = re.compile(r'(ผู้รับ\(\d+\)|ผู้รับ \(1\d\)|ผู้รับ \(TO\)|ผู้รับ \(0\)|ผู้รับ \(20\)|Fu \(TO\)|Hau \(TO\)|Au \(To\))\s*(.+?)\n(.*?จังหวัด.+? \d+)', re.DOTALL)

        # รูปแบบ regex สำหรับหมายเลขออเดอร์ Shopee
        shopee_order_pattern = re.compile(r'Shopee Order No\. (\S+)')

        # รูปแบบ regex สำหรับตัวเลือกสินค้า
        product_option_pattern = re.compile(r'ตัวเลือกสินค้า\n(.+?)\n\n', re.DOTALL)

        order_data = {}

        # ค้นหาข้อมูลผู้ส่ง
        sender_match = sender_pattern.search(text)
        if sender_match:
            sender_name = sender_match.group(2).strip()
            sender_address = sender_match.group(3).strip().replace('\n', ' ')
            order_data['sender'] = {
                'name': sender_name,
                'address': sender_address
            }

        # ค้นหาข้อมูลผู้รับ
        recipient_match = recipient_pattern.search(text)
        if recipient_match:
            recipient_name = recipient_match.group(2).strip()
            recipient_address = recipient_match.group(3).strip().replace('\n', ' ')
            order_data['recipient'] = {
                'name': recipient_name,
                'address': recipient_address
            }

        # ค้นหา Shopee Order
        shopee_order_match = shopee_order_pattern.search(text)
        if shopee_order_match:
            shopee_order_number = shopee_order_match.group(1)
            order_data['shopee_order_no'] = shopee_order_number

        # ค้นหาตัวเลือกสินค้า
        product_option_match = product_option_pattern.search(text)
        if product_option_match:
            product_option = product_option_match.group(1).strip()
            order_data['product_option'] = product_option

        # แก้ไขคำผิดใน order_data
        order_data = find_and_correct_misspelled_words(order_data)

        # ค้นหาคำที่ยังสะกดผิดอยู่
        misspelled_words = find_misspelled_words(order_data)   
        
        print(order_data)
        requests.post('http://localhost:3000/store-data', json={"data":order_data,"user":request.form['user']})
        return jsonify({'data': order_data}), 200
    
    except Exception as e:
        return jsonify({'message': 'Error processing image', 'error': str(e)}), 500
    
# ฟังก์ชันค้นหาและแก้ไขคำผิด
def find_and_correct_misspelled_words(data):
    possibilities = ["ตำบล", "อุปกรณ์สตรีมเมอร์", "พร้อมชุดหัวแปลงไอโฟน", "Avermedia", "หัวแปลง", 
                     "HDMI ", "gc311", "IPHONE,ขาว", "เลขที่", "อำเภอ", "หมู่", "จังหวัด", "ผู้ส่ง", "ผู้รับ", "Capture", "ตำบลลอ"]
    for key, value in data.items():
        if isinstance(value, str):
            words = value.split()
            for i in range(len(words)):
                if not d.check(words[i]):  # ตรวจสอบคำผิด
                    close_matches = difflib.get_close_matches(words[i], possibilities, n=1, cutoff=0.3)
                    if close_matches:
                        words[i] = close_matches[0]  # เลือกใช้คำที่ใกล้เคียงที่สุดจาก possibilities
            data[key] = ' '.join(words)  # รวมคำที่แก้ไขแล้วกลับเข้าไปใน data
    return data

# ฟังก์ชันค้นหาคำที่สะกดผิด
def find_misspelled_words(data):
    misspelled_words = []
    for key, value in data.items():
        if isinstance(value, str):
            words = value.split()
            for word in words:
                if not d.check(word):  # ตรวจสอบคำผิด
                    misspelled_words.append(word)
    return misspelled_words

if __name__ == '__main__':
    app.run(debug=True)
