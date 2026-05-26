import socket
import struct
import time
import os
from dotenv import load_dotenv

# Load environment variables
env_path = "/opt/logger/config/.env"  # env file path
if not load_dotenv(dotenv_path=env_path):
    print(f"Error: env file not found at {env_path}")
    exit(1)

STATUS = os.getenv('SPECTRO_STATUS')
IP = os.getenv('SPECTRO_IP')
PORT = os.getenv('SPECTRO_PORT')

def send_modbus_request(sock, transaction_id, unit_id, start_address, register_count):
    # Build request
    protocol_id = 0x0000
    length = 6
    function_code = 0x04
    header = struct.pack('>HHHB', transaction_id, protocol_id, length, unit_id)
    body = struct.pack('>BHH', function_code, start_address, register_count)
    request = header + body

    # Kirim request
    #print(f"Request (hex): {request.hex()}")
    sock.send(request)
    time.sleep(0.5)
    response = sock.recv(1024)
    #print(f"Response (hex): {response.hex()}")

    # Validasi response
    if not response or len(response) < 13:
        print("Response tidak valid.")
        return None

    # Parse float (4 byte mulai byte ke-9)
    value = round(struct.unpack('>f', response[9:13])[0], 2)
    return value

def read_modbus_tcp():
    
    if STATUS.lower() != "active":
        print("[INFO] Modul SPECTRO tidak aktif. Melewati pembacaan data.")
        return None,None,None,None,None,None
    
    try:
        print("[INFO] Modul SPECTRO aktif. Melakukan pembacaan data.")
        print("Menghubungkan ke sensor Modbus TCP...")

        ip = IP    # IP sensor
        port = int(PORT)
        unit_id = 0xFF          # Slave ID sensor

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        sock.connect((ip, port))

        # Request Parameter 1
        turb = send_modbus_request(sock, 1, unit_id, 0x0082, 2)
        print(f"Turbidity: {turb}")

        # Request Parameter 2
        tss = send_modbus_request(sock, 2, unit_id, 0x008A, 2)
        print(f"TSS: {tss}")

        # Request Parameter 3
        cod = send_modbus_request(sock, 2, unit_id, 0x0092, 2)
        print(f"COD: {cod}")

        # Request Parameter 4
        bod = send_modbus_request(sock, 2, unit_id, 0x009A, 2)
        print(f"BOD: {bod}")

        # Request Parameter 5
        no3 = send_modbus_request(sock, 2, unit_id, 0x00A2, 2)
        print(f"NO3: {no3}")

        # Request Parameter 6
        temp = send_modbus_request(sock, 2, unit_id, 0x00AA, 2)
        print(f"Temperature: {temp}")

        sock.close()
        return turb, tss, cod, bod, no3, temp

    except Exception as e:
        print(f"Terjadi error: {e}")
        return None,None,None,None,None,None
