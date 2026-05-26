from flask import Flask, send_from_directory, jsonify, request, send_file
import pandas as pd
from datetime import datetime, timedelta
import json
import os
import io
import sys
import logging
import traceback
import re
import subprocess
import mysql.connector
from dotenv import load_dotenv

# === Logging Setup ===
log_path = "/opt/logger/log/web.log"
os.makedirs(os.path.dirname(log_path), exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_path),
        logging.StreamHandler(sys.stdout)
    ]
)

# === Load env ===
env_path = "/opt/logger/config/.env"
if not load_dotenv(dotenv_path=env_path):
    print(f"❌ env file not found at {env_path}")
    exit(1)

# === MySQL Config ===
DB_CONFIG = {
    "host": os.getenv('DB_HOST'),
    "database": os.getenv('DB_NAME'),
    "user": os.getenv('DB_USER'),
    "password": os.getenv('DB_PASSWORD'),
    "port": int(os.getenv('DB_PORT')),
}

PORT_NUMBER_APP = int(os.getenv('PORT_NUMBER_APP', '5010'))

# === Path Setup ===
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(BASE_DIR, "../frontend")

# === Load Metadata ===
try:
    CONFIG = {
        "parameters": os.getenv("PARAMETERS", "").split(","),
        "satuanph" : os.getenv("SATUAN_PH"),
        "satuanorp" : os.getenv("SATUAN_ORP"),
        "satuantds" : os.getenv("SATUAN_TDS"),
        "satuanconduct" : os.getenv("SATUAN_CONDUCT"),
        "satuando" : os.getenv("SATUAN_DO"),
        "satuansalinity" : os.getenv("SATUAN_SALINITY"),
        "satuannh3n" : os.getenv("SATUAN_NH3N"),
        "satuanturb" : os.getenv("SATUAN_TURB"),
        "satuantss" : os.getenv("SATUAN_TSS"),
        "satuancod" : os.getenv("SATUAN_COD"),
        "satuanbod" : os.getenv("SATUAN_BOD"),
        "satuanno3" : os.getenv("SATUAN_NO3"),
        "satuantemp" : os.getenv("SATUAN_TEMP"),
        "satuanpress" : os.getenv("SATUAN_PRESS"),
        "satuanbattery" : os.getenv("SATUAN_BATTERY"),
        "satuandepth" : os.getenv("SATUAN_DEPTH"),
        "satuanflow" : os.getenv("SATUAN_FLOW"),
        "satuantflow" : os.getenv("SATUAN_TFLOW"),
        "satuanhum" : os.getenv("SATUAN_HUM"),
        "satuanwspeed" : os.getenv("SATUAN_WSPEED"),
        "satuanwdir" : os.getenv("SATUAN_WDIR"),
        "satuanrain" : os.getenv("SATUAN_RAIN"),
        "satuansrad" : os.getenv("SATUAN_SRAD"),   
        "device": os.getenv("DEVICE_ID", ""),
        "location": os.getenv("LOCATION_NAME", ""),
        "software": os.getenv("SOFTWARE_VERSION", ""),
        "titlename": os.getenv("WEB_TITLE", ""),
        "headername": os.getenv("WEB_NAME", ""),
        "gapweb": int(os.getenv("GAP_WEB")),  # in minutes
        "geo": {
            "latitude": float(os.getenv("GEO_LATITUDE", "0")),
            "longitude": float(os.getenv("GEO_LONGITUDE", "0")),
        }
    }
except Exception as e:
    print(f"❌ Failed to load config from env: {e}")
    CONFIG = {}
    
    
# === Flask App ===
app = Flask(__name__, static_folder=None)

# === USB Mount Management ===
BASE_MOUNT_DIR = "/mnt"
MOUNTED_USB = []


def query_to_dataframe(query, params=None):
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor(dictionary=True)
    cursor.execute(query, params or ())
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    df = pd.DataFrame(rows)
    df.fillna(value=pd.NA, inplace=True)
    df = df.astype(object).where(pd.notnull(df), None)
    return df


def get_usb_devices():
    devices = []
    try:
        result = subprocess.run(['lsblk', '-S', '-o', 'NAME,TRAN,VENDOR'], capture_output=True, text=True)
        lines = result.stdout.strip().splitlines()[1:]
        for line in lines:
            parts = line.strip().split()
            if len(parts) >= 3:
                name, tran, vendor = parts[:3]
                if tran.lower() == 'usb':
                    part_result = subprocess.run(
                        ['lsblk', '-nrpo', 'NAME,TYPE,MOUNTPOINT', f'/dev/{name}'],
                        capture_output=True, text=True
                    )
                    for part_line in part_result.stdout.strip().splitlines():
                        part_info = part_line.strip().split()
                        if len(part_info) >= 3 and part_info[1] == "part":
                            part_name, _, mount_point = part_info
                            if mount_point == "-" or not mount_point:
                                safe_vendor = vendor.replace(" ", "_")
                                mount_point = os.path.join(BASE_MOUNT_DIR, safe_vendor)
                                os.makedirs(mount_point, exist_ok=True)
                                try:
                                    subprocess.run(['mount', part_name, mount_point], check=True)
                                    logging.info(f"✅ Mounted {part_name} at {mount_point}")
                                    MOUNTED_USB.append(mount_point)
                                except subprocess.CalledProcessError as e:
                                    print(f"❌ Mount failed for {part_name}: {e}")
                                    continue
                            devices.append({"label": vendor.strip(), "mount": mount_point})
        return devices
    except Exception as e:
        print(f"❌ USB detection error: {e}")
        return []


def cleanup_usb_mounts():
    global MOUNTED_USB
    for mount_point in MOUNTED_USB:
        try:
            subprocess.run(['umount', mount_point], check=True)
            logging.info(f"🛑 Unmounted {mount_point}")
        except subprocess.CalledProcessError as e:
            print(f"⚠️ Failed to unmount {mount_point}: {e}")
    MOUNTED_USB = []


def sanitize_filename(filename):
    filename = filename.replace(":", "-").replace("/", "-")
    return re.sub(r"[^a-zA-Z0-9_\-\.]", "_", filename)


@app.route("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/<path:filename>")
def serve_frontend_assets(filename):
    return send_from_directory(FRONTEND_DIR, filename)


@app.route('/api/config')
def get_config():
    return jsonify(CONFIG)


@app.route('/api/latest')
def latest_data():
    try:
        params = CONFIG.get("parameters", [])
        if not params:
            return jsonify({"error": "No parameters defined in config"}), 400

        param_fields = ', '.join(params + ["date"])
        query = f"""
                    SELECT {param_fields}
                    FROM (
                        SELECT {param_fields} FROM data
                        UNION ALL
                        SELECT {param_fields} FROM tmp
                    ) AS combined
                    ORDER BY date DESC LIMIT 1
                """
        df = query_to_dataframe(query)

        if df.empty:
            return jsonify({param: None for param in params})

        row = df.iloc[0].to_dict()
        if 'date' in row and row['date']:
            row['date_str'] = row['date'].strftime("%Y-%m-%d %H:%M")
        return jsonify(row)

    except Exception as e:
        print(f"❌ Exception in /api/latest: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/history')
def history_data():
    param = request.args.get('param', 'temp')
    range_time = request.args.get('range', 'realtime')
    now = datetime.now()
    start_time = {
        "realtime": now - timedelta(minutes=15),
        "1h": now - timedelta(hours=1),
        "12h": now - timedelta(hours=12),
        "1d": now - timedelta(days=1),
        "3d": now - timedelta(days=3),
        "7d": now - timedelta(days=7)
    }.get(range_time, now - timedelta(minutes=15))

    try:
        query = f"""
            SELECT date, {param}
            FROM (
                SELECT date, {param} FROM data
                UNION ALL
                SELECT date, {param} FROM tmp
            ) AS combined
            WHERE date >= %s
            ORDER BY date ASC;
        """
        df = query_to_dataframe(query, (start_time,))

        if param not in df.columns:
            return jsonify({"timestamps": [], "values": []})

        return jsonify({
            "timestamps": df["date"].astype(str).tolist(),
            "values": df[param].tolist()
        })
    except Exception as e:
        print(f"❌ /api/history error: {e}")
        return jsonify({"timestamps": [], "values": [], "error": str(e)}), 500


@app.route('/api/windrose')
def windrose_data():
    range_time = request.args.get('range', 'realtime')
    now = datetime.now()
    start_time = {
        "realtime": now - timedelta(minutes=15),
        "1h": now - timedelta(hours=1),
        "12h": now - timedelta(hours=12),
        "1d": now - timedelta(days=1),
        "3d": now - timedelta(days=3),
        "7d": now - timedelta(days=7)
    }.get(range_time, now - timedelta(minutes=15))

    try:
        
        query = f"""
            SELECT date, wspeed, wdir
            FROM (
                SELECT date,  wspeed, wdir FROM data
                UNION ALL
                SELECT date,  wspeed, wdir FROM tmp
            ) AS combined
            WHERE date >= %s
            ORDER BY date ASC;
        """
        df = query_to_dataframe(query, (start_time,))

        # Ganti NaN dengan None agar JSON valid
        df.fillna(value=pd.NA, inplace=True)
        df = df.astype(object).where(pd.notnull(df), None)

        if "wspeed" not in df.columns or "wdir" not in df.columns:
            return jsonify({"timestamps": [], "wspeed": [], "wdir": []})

        return jsonify({
            "timestamps": df["date"].astype(str).tolist(),
            "wspeed": df["wspeed"].tolist(),
            "wdir": df["wdir"].tolist()
        })

    except Exception as e:
        logging.error("❌ /api/windrose error: %s", e)
        traceback.print_exc()
        return jsonify({"timestamps": [], "wspeed": [], "wdir": [], "error": str(e)}), 500






@app.route('/api/usb-list')
def list_usb_devices():
    try:
        usb_devices = get_usb_devices()
        devices = ["download"] + [usb["label"] for usb in usb_devices]
        return jsonify(devices)
    except Exception as e:
        print(f"❌ USB list error: {e}")
        return jsonify(["download"]), 500
    finally:
        cleanup_usb_mounts()


@app.route('/api/export', methods=['POST'])
def export_data():
    try:
        data = request.get_json()
        start = data.get("start")
        end = data.get("end")
        destination = data.get("destination", "download")

        if not start or not end:
            return jsonify({"error": "Parameter 'start' dan 'end' wajib diisi."}), 400

        logging.info(f"📦 Export request: {start} → {end} to {destination}")
        start_dt = datetime.fromisoformat(start)
        end_dt = datetime.fromisoformat(end)

        query = """
            SELECT * FROM (
                SELECT * FROM data
                UNION ALL
                SELECT * FROM tmp
            ) AS combined
            WHERE date BETWEEN %s AND %s ORDER BY date ASC;
        """
        df = query_to_dataframe(query, (start_dt, end_dt))

        if df.empty:
            return jsonify({"error": "Tidak ada data dalam rentang waktu tersebut."}), 400

        filename = sanitize_filename(f"export_{start}_{end}.csv")

        if destination == "download":
            csv_io = io.StringIO()
            df.to_csv(csv_io, index=False)
            mem = io.BytesIO()
            mem.write(csv_io.getvalue().encode('utf-8'))
            mem.seek(0)
            return send_file(
                mem,
                download_name=filename,
                as_attachment=True,
                mimetype='text/csv'
            )
        else:
            usb_devices = get_usb_devices()
            mount_point = next((usb["mount"] for usb in usb_devices if usb["label"] == destination), None)
            if not mount_point or not os.access(mount_point, os.W_OK):
                return jsonify({"error": f"USB '{destination}' tidak ditemukan atau tidak bisa ditulis."}), 500
            export_path = os.path.join(mount_point, filename)
            df.to_csv(export_path, index=False)
            logging.info(f"✅ Data exported to: {export_path}")
            return jsonify({"status": "success", "path": export_path})
    except Exception as e:
        print(f"❌ Export error: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        cleanup_usb_mounts()


@app.route('/api/wifi-status')
def wifi_status():
    try:
        result = subprocess.run(['nmcli', '-t', '-f', 'active,ssid', 'dev', 'wifi'], capture_output=True, text=True)
        lines = result.stdout.strip().split('\n')
        ssid_connected = "-"
        for line in lines:
            if line.startswith("yes:"):
                parts = line.split(":")
                if len(parts) > 1:
                    ssid_connected = parts[1]
                break

        ping_check = subprocess.run(['ping', '-c', '1', '8.8.8.8'], stdout=subprocess.DEVNULL)
        connected = ping_check.returncode == 0

        return jsonify({'connected': connected, 'ssid': ssid_connected})
    except Exception as e:
        print(f"WiFi status error: {e}")
        return jsonify({'connected': False, 'ssid': '-'})


@app.route('/api/wifi-scan')
def wifi_scan():
    try:
        result = subprocess.run(['nmcli', '-t', '-f', 'ssid', 'dev', 'wifi'], capture_output=True, text=True)
        ssids = list({s for s in result.stdout.strip().split('\n') if s.strip()})
        return jsonify({'ssids': ssids})
    except Exception as e:
        print(f"WiFi scan error: {e}")
        return jsonify({'ssids': []})


@app.route('/api/connect-wifi', methods=['POST'])
def connect_wifi():
    try:
        data = request.get_json()
        ssid = data.get('ssid')
        password = data.get('password')
        #logging.info(f"Simulating connect to SSID: {ssid}")
        subprocess.run(['nmcli', 'dev', 'wifi', 'connect', ssid, 'password', password])
        return jsonify({'message': f'Terhubung ke {ssid} .'})
    except Exception as e:
        print(f"Connect WiFi error: {e}")
        return jsonify({'message': 'Gagal menghubungkan ke WiFi.'}), 500


@app.route('/api/system/restart', methods=['POST'])
def restart():
    logging.warning("⚠️ Restart requested!")
    os.system('sudo reboot')
    return '', 204


@app.route('/api/system/shutdown', methods=['POST'])
def shutdown():
    logging.warning("⚠️ Shutdown requested!")
    os.system('sudo shutdown now')
    return '', 204


if __name__ == "__main__":
    
    port = int(sys.argv[1]) if len(sys.argv) > 1 else PORT_NUMBER_APP
    app.run(host="0.0.0.0", port=port)
