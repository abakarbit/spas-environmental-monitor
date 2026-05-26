import serial
import time
import logging
import os
import traceback
import os
from dotenv import load_dotenv


# Load environment variables
env_path = "/opt/logger/config/.env"  # env file path
if not load_dotenv(dotenv_path=env_path):
    print(f"Error: env file not found at {env_path}")
    exit(1)

SEM5096_STATUS = os.getenv('SEM5096_STATUS')
SEM5096_PORT = os.getenv('SEM5096_PORT')

def get_sem5096_data():
    
    if SEM5096_STATUS.lower() != "active":
        print("[INFO] Modul RT200 tidak aktif. Melewati pembacaan data.")
        return None, None, None, None, None, None, None

    if not os.path.exists(SEM5096_PORT):
        print(f"Port {SEM5096_PORT} tidak tersedia. Membatalkan semua pembacaan.")
        return
    
    try:
        print("[INFO] Modul SEM5096 aktif. Melakukan pembacaan data.")
        port = SEM5096_PORT
        print(f"📡 Membuka port {port}...")

        ser = serial.Serial(
            port=port,
            baudrate=9600,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=1
        )

        if not ser.is_open:
            ser.open()
            print("✅ Port serial dibuka.")

        # Kirim request data ke sensor
        request = bytearray([0xFF, 0x03, 0x00, 0x09, 0x00, 0x07])
        request += bytearray([0xC1, 0xD4])  # CRC (disesuaikan sesuai sensor)

        ser.write(request)
        time.sleep(1)
        response = ser.read(256)
        ser.close()

        if not response or len(response) < 17:
            print(f"❌ Response kosong atau terlalu pendek: {response}")
            return None

        #print(f"✅ Raw response: {response.hex()}")

        try:
            temp = round(int.from_bytes(response[3:5], byteorder='big') / 100 - 40, 2)
            hum = round(int.from_bytes(response[5:7], byteorder='big') / 100, 2)
            press = round(int.from_bytes(response[7:9], byteorder='big') / 10, 2)
            wspeed = round(int.from_bytes(response[9:11], byteorder='big') / 100, 2)
            wdir = round(int.from_bytes(response[11:13], byteorder='big') / 10, 2)
            rain = round(int.from_bytes(response[13:15], byteorder='big') / 10, 2)
            srad = int.from_bytes(response[15:17], byteorder='big')

            #print(f"✅ Parsed: Temp={temp}, Hum={hum}, Press={press}, WSpeed={wspeed}, WDir={wdir}, Rain={rain}, Srad={srad}")
            return (temp, hum, press, wspeed, wdir, rain, srad)

        except Exception as parse_err:
            print(f"❌ Gagal parsing data sensor: {parse_err}")
            traceback.print_exc()
            return

    except Exception as e:
        print(f"❌ Exception saat membaca sensor: {e}")
        traceback.print_exc()
        return


# === Untuk pengujian langsung ===
# if __name__ == "__main__":
#     result = read_sensor()
#     if result:
#         print("✅ Sensor data:", result)
#     else:
#         print("❌ Gagal membaca data sensor.")