import serial
import struct
import time
import os
from dotenv import load_dotenv

env_path = "/opt/logger/config/.env"  # env file path
if not load_dotenv(dotenv_path=env_path):
    print(f"Error: env file not found at {env_path}")
    exit(1)

RT200_STATUS = os.getenv('RT200_STATUS')
PORT_SERIAL = os.getenv('RT200_PORT')

# Jumlah maksimum percobaan jika tidak ada respon dari sensor
MAX_RETRIES = 5

def read_modbus(port, request, crc):
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            baudrate = 19200
            parity = serial.PARITY_EVEN
            stopbits = serial.STOPBITS_ONE
            bytesize = serial.EIGHTBITS
            timeout = 1

            ser = serial.Serial(port, baudrate, bytesize, parity, stopbits, timeout)
            time.sleep(0.5)

            modbus_request = request + crc
            ser.write(modbus_request)
            time.sleep(0.5)  # Tunggu respons
            response = ser.read(256)

            if not response:
                print(f"Percobaan {attempt}/{MAX_RETRIES}: No response from {port}, retrying...")
                ser.close()
                time.sleep(0.5)  # Tunggu sebelum mencoba lagi
                continue

            if len(response) >= 7:  # Pastikan respons cukup panjang
                data = round(struct.unpack('>f', response[3:7])[0], 2)
                ser.close()
                return data
            else:
                print(f"Percobaan {attempt}/{MAX_RETRIES}: Incomplete response from {port}, retrying...")
                ser.close()
                time.sleep(1)
                continue

        except Exception as e:
            print(f"Percobaan {attempt}/{MAX_RETRIES}: Error reading Modbus: {e}, retrying...")
            time.sleep(1)  # Tunggu sebelum mencoba lagi

    print(f"Gagal membaca data dari {port} setelah {MAX_RETRIES} percobaan.")
    return None  # Kembalikan None jika gagal membaca setelah 3 percobaan

def read_temp():
    return read_modbus(
        PORT_SERIAL,
        bytearray([0x05, 0x03, 0x00, 0x2D, 0x00, 0x02]),
        bytearray([0x55, 0x86])
    )

def read_press():
    return read_modbus(
        PORT_SERIAL,
        bytearray([0x05, 0x03, 0x00, 0x25, 0x00, 0x02]),
        bytearray([0xD4, 0x44])
    )

def read_depth():
    return read_modbus(
        PORT_SERIAL,
        bytearray([0x05, 0x03, 0x00, 0x35, 0x00, 0x02]),
        bytearray([0xD5, 0x81])
    )

def get_rt200_data():
    
    if RT200_STATUS.lower() != "active":
        print("[INFO] Modul RT200 tidak aktif. Melewati pembacaan data.")
        return None, None, None

    if not os.path.exists(PORT_SERIAL):
        print(f"Port {PORT_SERIAL} tidak tersedia. Membatalkan semua pembacaan.")
        return
    else:
        print("[INFO] Modul RT200 aktif. Melakukan pembacaan data.")  
        temp = read_temp()
        press = read_press()
        depth = round((read_depth() * 30.48),2)  # Konversi dari feet ke cm
        return temp, press, depth


# # Tambahan untuk menjalankan langsung
# if __name__ == "__main__":
#     while True:
#         temp, press, depth = get_rt200_data()
#         print(f"Temperature: {temp}, Pressure: {press}, Depth: {depth}")
#         time.sleep(10)
