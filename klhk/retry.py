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
FIELDS = os.getenv("KLHK_FIELDS")
STATUS = os.getenv("KLHK_STATUS")
# Variabel konfigurasi dari env
TARGET_MINUTE = int(os.getenv('KLHK_TARGET_MINUTE'))
HOST = os.getenv('DB_HOST')
USER = os.getenv('DB_USER')
PASSWORD = os.getenv('DB_PASSWORD')
DATABASE = os.getenv('DB_NAME')
PORT = int(os.getenv('DB_PORT'))
TIMEZONE = os.getenv('TIMEZONE', 'Asia/Jakarta')
API_ENDPOINT = os.getenv('KLHK_API_URL')
API_JWT = os.getenv('KLHK_TOKEN_URL')
UID = os.getenv('KLHK_UID')
MAX_DUP_RETRY = int(os.getenv('KLHK_MAX_DUP_RETRY', 3))

tz = pytz.timezone(TIMEZONE)
duplicate_attempt = 0

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

def get_jwt_token():
    try:
        response = requests.get(API_JWT)
        if response.status_code == 200:
            jwt_token = response.text.strip()
            if jwt_token:
                write_log(f"✅ Token JWT didapatkan : {jwt_token}")
                return jwt_token
        write_log(f"❌ Gagal dapatkan token, status code: {response.status_code}")
    except requests.exceptions.RequestException as e:
        write_log(f"❌ Error koneksi token API: {e}")
    return None

def ambil_data():
    global duplicate_attempt
    now = datetime.now(tz)
    grouped_data = defaultdict(list)

    try:
        with mysql.connector.connect(**MYSQL_CONFIG) as conn:
            with conn.cursor() as cursor:
                query_fields = ", ".join(["date"] + FIELDS)
                cursor.execute(f"SELECT {query_fields} FROM tmp WHERE status='retry' AND date < %s", [now])
                rows = cursor.fetchall()

                if not rows:
                    write_log("ℹ️ Tidak ada data baru.")
                    return

                for row in rows:
                    date_val = row[0]
                    key = f"{date_val.strftime('%Y-%m-%d')} {date_val.hour}:00"
                    grouped_data[key].append(row)

                for key, data in grouped_data.items():
                    start_time = min(entry[0] for entry in data)
                    end_time = max(entry[0] for entry in data)
                    start = start_time.strftime('%Y-%m-%d %H:%M:%S')
                    end = end_time.strftime('%Y-%m-%d %H:%M:%S')

                    payload = []
                    for entry in data:
                        row_dict = dict(zip(["date"] + FIELDS, entry))
                        item = {field: row_dict[field] for field in FIELDS}
                        payload.append(item)

                    send_data_to_api(payload, start, end)
    except mysql.connector.Error as e:
        write_log(f"❌ DB Error: {e}")
    except Exception as e:
        write_log(f"❌ Error ambil_data: {e}")

def send_data_to_api(data, start, end):
    global duplicate_attempt
    if not data:
        return

    write_log(f"🚀 Retry kirim data jam {start} - {end}")
    try:
        key_token = get_jwt_token()
        if not key_token:
            return

        payload = {"uid": UID, "data": data}
        jwt_header = {"alg": "HS256", "typ": "JWT"}

        try:
            encoded = jwt.encode(payload, key_token, algorithm='HS256', headers=jwt_header)
            write_log(f"📦 Payload JWT: \n{json.dumps(payload, default=str, indent=4)}")
            write_log(f"🔐 Encoded JWT: {encoded}")
        except AttributeError:
            write_log("❌ Gagal encode JWT. Pastikan gunakan `PyJWT`, bukan `jwt` package lain.")
            return

        headers = {'Authorization': f'Bearer {key_token}', 'Content-Type': 'application/json'}
        response = requests.post(API_ENDPOINT, json={"token": encoded}, headers=headers)
        result = response.json()

        with mysql.connector.connect(**MYSQL_CONFIG) as conn:
            with conn.cursor() as cursor:
                if result.get("status"):
                    now = datetime.now(tz)
                    cursor.execute("UPDATE tmp SET dateterkirim=%s, status='terkirim', keterangan='sukses' WHERE date >=%s AND date <=%s", [now, start, end])
                    cursor.execute("INSERT INTO data SELECT * FROM tmp WHERE date >=%s AND date <=%s", [start, end])
                    cursor.execute("DELETE FROM tmp WHERE date >=%s AND date <=%s", [start, end])
                    conn.commit()
                    write_log("✅ Data berhasil dikirim & diproses.")
                else:
                    desc = result.get("desc", "unknown error")
                    write_log(f"⚠️ Gagal kirim: {desc}")
                    if "duplikasi" in desc.lower():
                        duplicate_attempt += 1
                        if duplicate_attempt >= MAX_DUP_RETRY:
                            cursor.execute("UPDATE tmp SET status='Duplikasi', keterangan='Manual check' WHERE date >=%s AND date <=%s", [start, end])
                            conn.commit()
                            write_log("⚠️ Duplikasi berulang. Pengiriman dihentikan.")
                            return

                        for ts in result.get("data", []):
                            cursor.execute("DELETE FROM tmp WHERE date = %s", [ts])
                            write_log(f"🗑️ Hapus duplikat: {ts}")
                        conn.commit()

                        # Re-fetch & resend
                        cursor.execute(f"SELECT {', '.join(FIELDS)} FROM tmp WHERE date >=%s AND date <=%s", [start, end])
                        rows = cursor.fetchall()
                        if rows:
                            data_cleaned = [dict(zip(FIELDS, row)) for row in rows]
                            send_data_to_api(data_cleaned, start, end)
                        else:
                            write_log("ℹ️ Tidak ada data tersisa setelah hapus duplikat.")
                    else:
                        cursor.execute("UPDATE tmp SET status='retry', keterangan=%s WHERE date >=%s AND date <=%s", [desc, start, end])
                        conn.commit()

    except Exception as e:
        write_log(f"❌ Error kirim data: {e}")

def scheduler():
    write_log(f"⏱️ Service aktif. Menunggu eksekusi tiap jam pada menit ke-{TARGET_MINUTE}.")
    last_run = None
    try:
        while True:
            now = datetime.now(tz)
            if now.minute == TARGET_MINUTE and now.second == 0:
                run_time = now.replace(minute=TARGET_MINUTE, second=0, microsecond=0)
                if last_run != run_time:
                    
                    if STATUS.lower() != "active":
                        write_log("ℹ️ Module KLHK Retry tidak aktif. Melewati eksekusi.")
                    else:   
                        write_log(f"⏳ Menjalankan scheduler pada {now}")
                        ambil_data() 
                        
                    last_run = run_time
            time.sleep(1)
    except KeyboardInterrupt:
        write_log("🛑 Service dihentikan manual.")

if __name__ == "__main__":
    scheduler()
    # ambil_data()  # Uncomment jika ingin satu kali jalan
