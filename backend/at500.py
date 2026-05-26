import serial
import struct
import time
import os
from dotenv import load_dotenv

env_path = "/opt/logger/config/.env"  # env file path
if not load_dotenv(dotenv_path=env_path):
    print(f"Error: env file not found at {env_path}")
    exit(1)

AT500_STATUS = os.getenv('AT500_STATUS')
AT500_PORT = os.getenv('AT500_PORT')
# Jumlah maksimum percobaan jika tidak ada respon dari sensor
MAX_RETRIES = 3

def read_modbus(port, request, crc):
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            baudrate = 19200
            parity = serial.PARITY_EVEN
            stopbits = serial.STOPBITS_ONE
            bytesize = serial.EIGHTBITS
            timeout = 1

            ser = serial.Serial(port, baudrate, bytesize, parity, stopbits, timeout)
            time.sleep(0.2)

            modbus_request = request + crc
            ser.write(modbus_request)
            time.sleep(0.2)  # Tunggu respons
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
                time.sleep(0.5)
                continue

        except Exception as e:
            print(f"Percobaan {attempt}/{MAX_RETRIES}: Error reading Modbus: {e}, retrying...")
            time.sleep(0.5)  # Tunggu sebelum mencoba lagi

    print(f"Gagal membaca data dari {port} setelah {MAX_RETRIES} percobaan.")
    return None  # Kembalikan None jika gagal membaca setelah 3 percobaan

def read_ph():
    return read_modbus(
        AT500_PORT,
        bytearray([0x01, 0x03, 0x15, 0xBA, 0x00, 0x02]),
        bytearray([0xE1, 0xE2])
    )

def read_orp():
    return read_modbus(
        AT500_PORT,
        bytearray([0x01, 0x03, 0x15, 0xC8, 0x00, 0x02]),
        bytearray([0x41, 0xF9])
    )

def read_nh3n():
    return read_modbus(
        AT500_PORT,
        bytearray([0x01, 0x03, 0x16, 0x69, 0x00, 0x02]),
        bytearray([0x10, 0x5F])
    )

def read_tds():
    return read_modbus(
        AT500_PORT,
        bytearray([0x01, 0x03, 0x15, 0x9E, 0x00, 0x02]),
        bytearray([0xA1, 0xE9])
    )

def read_conduct():
    return read_modbus(
        AT500_PORT,
        bytearray([0x01, 0x03, 0x15, 0x82, 0x00, 0x02]),
        bytearray([0x60, 0x2F])
    )

def read_do():
    return read_modbus(
        AT500_PORT,
        bytearray([0x01, 0x03, 0x15, 0xCF, 0x00, 0x02]),
        bytearray([0xF0, 0x38])
    )

def read_salinity():
    return read_modbus(
        AT500_PORT,
        bytearray([0x01, 0x03, 0x15, 0x97, 0x00, 0x02]),
        bytearray([0x71, 0xEB])
    )

def get_at500_data():
    """
    Membaca data dari sensor AT500.
    Return tuple: (pH, ORP, TDS, Conductivity, DO, Salinity, NH3-N)
    Jika sensor tidak aktif atau port tidak tersedia, return tuple berisi None.
    """

    if AT500_STATUS.lower() != "active":
        print("[INFO] Modul AT500 tidak aktif. Melewati pembacaan data.")
        return (None,) * 7

    if not os.path.exists(AT500_PORT):
        print(f"[ERROR] Port {AT500_PORT} tidak tersedia. Membatalkan pembacaan.")
        return

    try:
        print("[INFO] Modul AT500 aktif. Melakukan pembacaan data.")
        ph = read_ph()
        orp = read_orp()
        tds = read_tds()
        conduct = read_conduct()
        do = read_do()
        salinity = read_salinity()
        nh3n = read_nh3n()

        return ph, orp, tds, conduct, do, salinity, nh3n

    except Exception as e:
        print(f"[ERROR] Gagal membaca data AT500: {e}")
        return (None,) * 7

