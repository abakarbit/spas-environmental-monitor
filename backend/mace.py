import serial
import struct
import time
import os
from dotenv import load_dotenv

env_path = "/opt/logger/config/.env"  # env file path
if not load_dotenv(dotenv_path=env_path):
    print(f"Error: env file not found at {env_path}")
    exit(1)

MACE_STATUS = os.getenv('MACE_STATUS')
MACE_PORT = os.getenv('MACE_PORT')

def read_mace():
    try:
        port = MACE_PORT
        baudrate = 19200
        parity = serial.PARITY_NONE
        stopbits = serial.STOPBITS_ONE
        bytesize = serial.EIGHTBITS
        timeout = 1

        ser = serial.Serial(port, baudrate, bytesize, parity, stopbits, timeout)
        time.sleep(0.2) 
        request = bytearray([0x01, 0x04, 0x00, 0x00, 0x00, 0x08])
        crc = bytearray([0xF1, 0xCC])
        modbus_request = request + crc

        ser.write(modbus_request)
        time.sleep(0.2)  
        response = ser.read(256)

        if not response:
            print("No response received from MACE sensor")
            ser.close()
            return None, None, None, None
        
        if len(response) >= 15:  
            battery = round(struct.unpack('>f', response[3:7])[0], 2)
            depth = round(struct.unpack('>f', response[7:11])[0], 2)
            flow = round(struct.unpack('>f', response[11:15])[0], 2)
            tflow = round(struct.unpack('>f', response[15:19])[0], 2)
        else:
            print("Incomplete response received from MACE sensor")
            ser.close()
            return None, None, None, None

        ser.close()
        return battery, depth, flow, tflow
    except Exception as e:
        print(f"Error in read_modbus4: {e}")
        return None, None, None, None

def get_mace_data():
    
    if MACE_STATUS.lower() != "active":
        print("[INFO] Modul MACE tidak aktif. Melewati pembacaan data.")
        return (None,) * 4
    
    if not os.path.exists(MACE_PORT):
        print(f"Port {MACE_PORT} tidak tersedia. Membatalkan semua pembacaan.")
        return
    
    try:
        print("[INFO] Modul MACE aktif. Melakukan pembacaan data.")
        return read_mace()

    except Exception as e:
        print(f"[ERROR] Gagal membaca data AT500: {e}")
        return (None,) * 4