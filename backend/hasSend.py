import time
import os
import json
import pytz
import jwt  # Pastikan ini adalah PyJWT
import requests
import mysql.connector
from datetime import datetime
from collections import defaultdict
from dotenv import load_dotenv

# Load environment variables
env_path = "/opt/logger/config/.env"
if not load_dotenv(dotenv_path=env_path):
    print(f"Error: env file not found at {env_path}")
    exit(1)

# Config from env
STATUS = os.getenv("HAS_STATUS")
HOST = os.getenv('DB_HOST')
USER = os.getenv('DB_USER')
PASSWORD = os.getenv('DB_PASSWORD')
DATABASE = os.getenv('DB_NAME')
PORT = int(os.getenv('DB_PORT'))
TIMEZONE = os.getenv('TIMEZONE', 'Asia/Jakarta')
API_ENDPOINT = os.getenv('HAS_API_URL')
API_JWT = os.getenv('HAS_TOKEN')
tz = pytz.timezone(TIMEZONE)

MYSQL_CONFIG = {
    'host': HOST,
    'user': USER,
    'password': PASSWORD,
    'database': DATABASE,
    'port': PORT
}

def write_log(message):
    timestamp = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")


def ambil_data():
    global duplicate_attempt
    now = datetime.now(tz)
    grouped_data = defaultdict(list)

    try:
        with mysql.connector.connect(**MYSQL_CONFIG) as conn:
            with conn.cursor() as cursor:
                cursor.execute(f"SELECT * FROM ( SELECT * FROM data WHERE has = '0' UNION ALL  SELECT * FROM data WHERE has = '0' ) AS gabung ")
                rows = cursor.fetchall()
                
                if rows:
                    return rows
                else:
                    return None
                
    except mysql.connector.Error as e:
        write_log("❌ DB Error: {e}")
        return None
    except Exception as e:
        write_log("❌ Error ambil_data: {e}")
        return None

def send_data():
    
    rows = ambil_data()
    if not rows:
        write_log("Tidak ada data baru untuk dikirim.")
        return

    try:
        key_token = API_JWT
        if not key_token:
            return

        payload = {"uid": UID, "data": data}
        jwt_header = {"alg": "HS256", "typ": "JWT"}

        try:
            encoded = jwt.encode(payload, key_token, algorithm='HS256', headers=jwt_header)
            write_log("📦 Payload JWT: \n{json.dumps(payload, default=str, indent=4)}")
            write_log("🔐 Encoded JWT: {encoded}")
        except AttributeError:
            write_log("❌ Gagal encode JWT. Pastikan gunakan `PyJWT`, bukan `jwt` package lain.")
            return

        headers = {'Authorization': f'Bearer {key_token}', 'Content-Type': 'application/json'}
        response = requests.post(API_ENDPOINT, json={"token": encoded}, headers=headers)
        result = response.json()

        with mysql.connector.connect(**MYSQL_CONFIG) as conn:
            with conn.cursor() as cursor:
                if result:
                    now = datetime.now(tz)
                    cursor.execute("UPDATE tmp SET has='1', WHERE has ='0'")
                    cursor.execute("UPDATE data SET has='1', WHERE has ='0'")
                    conn.commit()
                    write_log("✅ Data berhasil dikirim & diproses.")
                else:
                    write_log("⚠️ Gagal kirim: {response.text}")

    except Exception as e:
        write_log("❌ Error kirim data: {e}")

def scheduler():
    write_log("⏱️ Service aktif. Menunggu eksekusi setiap jam pada menit ke-0")
    last_run = None
    try:
        while True:
            now = datetime.now(tz)
            if now.minute == 0 and now.second == 0:
                key_time = now.replace(minute=0, second=0, microsecond=0)
                if last_run != key_time:
                    
                    if STATUS.lower() != "active":
                        write_log("ℹ️ Module HAS API tidak aktif. Melewati eksekusi.")
                    else:   
                        write_log(f"⏳ Menjalankan scheduler pada {now}")
                        ambil_data()      
                    last_run = key_time
            time.sleep(1)
    except KeyboardInterrupt:
        write_log("🛑 Service dihentikan manual.")

if __name__ == "__main__":
    scheduler()
