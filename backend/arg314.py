#!/usr/bin/env python3
import time
import sys
import os
import sqlite3
from dotenv import load_dotenv
import random
import threading

# =============================
# Load Environment
# =============================
env_path = "/opt/logger/config/.env"
if not load_dotenv(dotenv_path=env_path):
    print(f"Error: env file not found at {env_path}")
    exit(1)

DB_PATH = os.getenv("SQLITE_DB_PATH", "/opt/logger/data/gpio_logger.db")
GPIO_MODULE = os.getenv("GPIO_MODULE", "").lower()  # Baca pilihan modul dari env

# =============================
# Pilih dan Import Modul GPIO
# =============================
gpio = None
module_name = ""

if GPIO_MODULE == "lgpio":
    try:
        import lgpio as gpio
        module_name = "lgpio"
        print("Menggunakan modul lgpio (sesuai konfigurasi)")
    except ImportError:
        print("Error: Modul lgpio tidak tersedia")
        exit(1)
elif GPIO_MODULE == "rpi.gpio":
    try:
        import RPi.GPIO as gpio
        module_name = "RPi.GPIO"
        print("Menggunakan modul RPi.GPIO (sesuai konfigurasi)")
    except ImportError:
        print("Error: Modul RPi.GPIO tidak tersedia")
        exit(1)
else:
    # Jika tidak diatur, coba otomatis deteksi
    try:
        import lgpio as gpio
        module_name = "lgpio"
        print("Menggunakan modul lgpio (deteksi otomatis)")
    except ImportError:
        try:
            import RPi.GPIO as gpio
            module_name = "RPi.GPIO"
            print("Menggunakan modul RPi.GPIO (deteksi otomatis)")
        except ImportError:
            print("Error: Tidak dapat menemukan modul lgpio atau RPi.GPIO")
            exit(1)

# =============================
# Fungsi Database
# =============================
def connect_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    return sqlite3.connect(DB_PATH)

def cekTable():
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS gpio (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date DATETIME,
            sensor TEXT,
            nilai REAL DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()

def insert_data_gpio(date, sensor, nilai):
    cekTable()
    try:
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO gpio (date, sensor, nilai) VALUES (?, ?, ?);", (date, sensor, nilai))
        conn.commit()
        print(f"[INFO] Data GPIO berhasil dimasukkan: {(date, sensor, nilai)}")
    except Exception as e:
        print(f"[ERROR] Gagal memasukkan data ke database: {e}")
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals(): conn.close()

# =============================
# Konfigurasi Parameter
# =============================
ARG314_STATUS = os.getenv('ARG314_STATUS')
RAIN_SENSOR_PIN = int(os.getenv('RAIN_SENSOR_PIN'))
RESOLUTION = float(os.getenv('RESOLUTION'))
DEFAULT_INTERVAL = int(os.getenv('DELAY'))
DEBOUNCE_MS = int(os.getenv('DEBOUNCE_MS'))
DEMO_MODE = os.getenv('DEMO_MODE')

# =============================
# Variabel Global
# =============================
tipping_count = 0
last_logged_minute = -1
interval_minutes = DEFAULT_INTERVAL
lock = threading.Lock()

# =============================
# Setup GPIO berdasarkan modul
# =============================
def setup_gpio():
    if module_name == "lgpio":
        return setup_lgpio()
    elif module_name == "RPi.GPIO":
        return setup_rpi_gpio()

def setup_lgpio():
    try:
        h = gpio.gpiochip_open(0)
        gpio.gpio_claim_input(h, RAIN_SENSOR_PIN)
        gpio.gpio_claim_alert(h, RAIN_SENSOR_PIN, gpio.FALLING_EDGE)
        gpio.gpio_set_debounce_micros(h, RAIN_SENSOR_PIN, DEBOUNCE_MS * 1000)
        
        def callback(chip, pin, level, tick):
            global tipping_count
            if level == 0:  # FALLING edge
                with lock:
                    tipping_count += 1
                print(f"Tipping terdeteksi! Total: {tipping_count}")
        
        gpio.callback(h, RAIN_SENSOR_PIN, gpio.FALLING_EDGE, callback)
        print(f"✅ Rain Gauge Monitor aktif di pin BCM {RAIN_SENSOR_PIN} (lgpio)")
        return h
    except Exception as e:
        print(f"[ERROR] Gagal inisialisasi lgpio: {e}")
        exit(1)

def setup_rpi_gpio():
    try:
        gpio.setmode(gpio.BCM)
        gpio.setup(RAIN_SENSOR_PIN, gpio.IN, pull_up_down=gpio.PUD_UP)
        
        def callback(channel):
            global tipping_count
            with lock:
                tipping_count += 1
            print(f"Tipping terdeteksi! Total: {tipping_count}")
        
        gpio.add_event_detect(RAIN_SENSOR_PIN, gpio.FALLING, 
                            callback=callback, bouncetime=DEBOUNCE_MS)
        print(f"✅ Rain Gauge Monitor aktif di pin BCM {RAIN_SENSOR_PIN} (RPi.GPIO)")
        return None
    except Exception as e:
        print(f"[ERROR] Gagal inisialisasi RPi.GPIO: {e}")
        exit(1)

# =============================
# Inisialisasi GPIO
# =============================
gpio_handle = setup_gpio()

# =============================
# Baca argumen interval
# =============================
if len(sys.argv) > 1:
    try:
        interval_minutes = int(sys.argv[1])
    except ValueError:
        pass

print(f"Interval pembacaan: {interval_minutes} menit")

# =============================
# Loop utama
# =============================
try:
    while True:
        now = time.localtime()
        current_minute = now.tm_min
        current_second = now.tm_sec

        if ARG314_STATUS and ARG314_STATUS.lower() != "active":
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Sensor ARG314 tidak aktif. Menunggu...")
            time.sleep(10)
            continue

        if current_second == 0 and (current_minute % interval_minutes == 0) and current_minute != last_logged_minute:
            timestamp = time.strftime('%Y-%m-%d %H:%M:%S')

            if DEMO_MODE and DEMO_MODE.lower() == "active":
                with lock:
                    tipping_count = random.randint(0, 60)
                print(f"[DEMO MODE] Simulasi tipping count: {tipping_count}")

            with lock:
                rainfall_mm = tipping_count * RESOLUTION
                tipping_count = 0

            print(f"[{timestamp}] Curah hujan: {rainfall_mm:.3f} mm")
            insert_data_gpio(timestamp, "rain_sensor", rainfall_mm)
            last_logged_minute = current_minute

        time.sleep(0.5)

except KeyboardInterrupt:
    print("\nDihentikan oleh user.")

finally:
    # Cleanup berdasarkan modul
    if module_name == "lgpio" and gpio_handle:
        gpio.gpiochip_close(gpio_handle)
    elif module_name == "RPi.GPIO":
        gpio.cleanup()
    print("GPIO ditutup dan program dihentikan.")