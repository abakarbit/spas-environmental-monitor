#!/bin/bash
# ============================================
#  SPAS — Edge-Based Environmental Telemetry & SPARING Gateway - Installer
# ============================================
# Nama Aplikasi : SPAS — Edge-Based Environmental Telemetry & SPARING Gateway
# Deskripsi     : Sistem pemantauan cuaca dan kualitas udara otomatis.
# Fungsi        : Merekam data lingkungan seperti suhu, kelembaban, tekanan, dll.
# Dibuat oleh   : Abu Bakar <abubakar.it.dev@gmail.com>
# Versi         : 1.0
# Lisensi       : Private/Internal Project
# ============================================

# Strict mode untuk penanganan error yang lebih baik
set -euo pipefail
trap 'echo "Error pada baris $LINENO. Perintah gagal: $BASH_COMMAND"' ERR

# Fungsi untuk mengecek apakah port digunakan
check_port() {
    local port=$1
    if command -v ss >/dev/null 2>&1; then
        if ss -tuln | grep -q ":$port "; then
            return 0
        fi
    elif command -v netstat >/dev/null 2>&1; then
        if netstat -tuln | grep -q ":$port "; then
            return 0
        fi
    else
        echo "Error: Tidak dapat mengecek port: ss/netstat tidak ditemukan" >&2
        return 2
    fi
    return 1
}

# Fungsi untuk menampilkan pesan error dan keluar
error_exit() {
    echo "Error: $1" >&2
    exit 1
}


# === Konfigurasi ===
readonly CONFIG_FILE="config/.env"
if [[ ! -f "$CONFIG_FILE" ]]; then
    error_exit "File konfigurasi '$CONFIG_FILE' tidak ditemukan!"
fi
source "$CONFIG_FILE"
readonly WEB_PORT="${PORT_NUMBER_APP}"
readonly LOG_PORT="${PORT_NUMBER_LOG}"

# === Header ===
echo "============================================"
echo " SPAS — Edge-Based Environmental Telemetry & SPARING Gateway - Installer"
echo "============================================"
echo "Dibuat oleh        : Abu Bakar <abubakar.it.dev@gmail.com>"
echo "Deskripsi          : Sistem pemantauan cuaca dan kualitas udara otomatis berbasis Python & API"
echo "Lokasi Instalasi   : /opt/logger"
echo "Service            : logger-sensor, logger-web, logger-backup, logger-gpio, logger-klhk-send, logger-klhk-retry, logger-has-send"
echo "Web Port           : 0.0.0.0:$WEB_PORT"
echo "Web Log Port       : 0.0.0.0:$LOG_PORT"
echo "PhpMyAdmin         : 0.0.0.0:8080"
echo "============================================"
echo ""

# === Pengecekan Port ===
echo "🔍 Mengecek ketersediaan port..."
if [ ! -f "$CONFIG_FILE" ]; then
    error_exit "File konfigurasi '$CONFIG_FILE' tidak ditemukan!"
fi

# Cek port web
if check_port "$WEB_PORT"; then
    echo "Error: Port $WEB_PORT sudah digunakan!"
    echo "Solusi: Ubah konfigurasi port di file '$CONFIG_FILE'"
    echo "   Kemudian jalankan ulang installer ini"
    error_exit "Instalasi dibatalkan karena konflik port $WEB_PORT"
fi

# Cek port log
if check_port "$LOG_PORT"; then
    echo "Error: Port $LOG_PORT sudah digunakan!"
    echo "Solusi: Ubah konfigurasi port di file '$CONFIG_FILE'"
    echo "   Kemudian jalankan ulang installer ini"
    error_exit "Instalasi dibatalkan karena konflik port $LOG_PORT"
fi

echo "Semua port tersedia. Melanjutkan instalasi..."
echo ""

# === Validasi lingkungan ===
echo "Memvalidasi dependensi sistem..."
command -v python3 >/dev/null 2>&1 || error_exit "Python3 tidak ditemukan. Silakan install terlebih dahulu."
command -v pip >/dev/null 2>&1 || error_exit "pip tidak ditemukan. Silakan install terlebih dahulu."
command -v docker >/dev/null 2>&1 || error_exit "Docker tidak ditemukan. Silakan install terlebih dahulu."
echo "Semua dependensi terpenuhi."
echo ""

# === Pemeriksaan Service ===
readonly CHECK_SERVICES=("logger-sensor.service" "logger-web.service" "logger-web-log.service" "logger-backup.service" "logger-klhk-send.service" "logger-klhk-retry.service")
echo "Mengecek apakah service sudah ada..."
found_existing=false
for service in "${CHECK_SERVICES[@]}"; do
    if [[ -f "/etc/systemd/system/$service" ]]; then
        echo "  Ditemukan service: $service"
        found_existing=true
    fi
done

if [ "$found_existing" = true ]; then
    echo ""
    echo " Instalasi dibatalkan. Service sudah ada."
    echo " Hapus service lama dengan:"
    echo "    sudo systemctl stop <service>"
    echo "    sudo rm /etc/systemd/system/<service>"
    echo "    sudo systemctl daemon-reload"
    echo ""
    exit 1
fi
echo "Tidak ada konflik service. Lanjut instalasi..."
echo ""

# === Setup Directories ===
readonly APP_BASE="/opt/logger"
readonly LOG_DIR="$APP_BASE/logs"
echo "Membuat direktori instalasi di $APP_BASE..."
mkdir -p "$APP_BASE"
cp -r . "$APP_BASE"
echo "Direktori instalasi siap."
echo ""

# === Python Virtual Environment ===
echo "Membuat virtual environment..."
python3 -m venv "$APP_BASE/venv"
source "$APP_BASE/venv/bin/activate"
echo "Virtual environment berhasil dibuat."
echo ""

# === Install Python Dependencies ===
readonly REQ_FILE="$APP_BASE/requirements.txt"
if [[ -f "$REQ_FILE" ]]; then
    echo "Menginstal dependensi dari requirements.txt..."
    pip install -r "$REQ_FILE"
    echo "Semua dependensi Python terinstal."
else
    echo "requirements.txt tidak ditemukan. Melewati instalasi dependensi."
fi
echo ""

# === CLI Link ===
echo "Menautkan CLI 'logger' ke /usr/bin/logger..."
if [[ -f "$APP_BASE/logger" ]]; then
    install -m 755 "$APP_BASE/logger" /usr/bin/logger
    echo "CLI berhasil ditautkan."
else
    echo "File CLI logger tidak ditemukan."
fi
echo ""

# === Setup Logs ===
echo "Menyiapkan direktori log di $LOG_DIR..."
mkdir -p "$LOG_DIR"
chown root:root "$LOG_DIR"
echo "Direktori log siap digunakan."
echo ""

# === Docker Database ===
echo "Memeriksa container database..."
if ! docker ps -a --format '{{.Names}}' | grep -q "^db_logger$"; then
    echo "Menjalankan container database..."
    docker run -d \
        --restart=always \
        --name db_logger \
        --network host \
        -v /opt:/opt \
        -it aqliserdadu/db:logger
    
    echo "Menginstall MySQL client..."
    sudo apt-get update -qq && sudo apt-get install -y mariadb-client python3-rpi.gpio python3-dotenv python3-lgpio
    echo "Container database dan MySQL client siap."
else
    echo "Container db_logger sudah ada. Melewati pembuatan."
fi
echo ""

# === Buat Systemd Service Files ===
echo "Membuat service systemd..."

# === GPIO ARG314 Setup ===
echo "  • Membuat GPIO.service..."
cat <<EOF > "/etc/systemd/system/logger-gpio.service"
[Unit]
Description=logger GPIO Service
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/logger/backend
ExecStart=python3 -u  /opt/logger/backend/arg314.py
StandardOutput=append:/opt/logger/logs/gpio.log
StandardError=append:/opt/logger/logs/gpio.log
Restart=always
User=root
Group=root

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable logger-gpio
systemctl restart logger-gpio
echo "logger-gpio.service aktif."


#==== End GPIO ====

declare -A SERVICE_MAP
SERVICE_MAP[logger-sensor]="backend/main.py sensor.log"
SERVICE_MAP[logger-web]="backend/app.py web.log"
SERVICE_MAP[logger-web-log]="backend/log.py log.log"
SERVICE_MAP[logger-backup]="backend/backup.py backup.log"
SERVICE_MAP[logger-klhk-send]="klhk/send.py send.log"
SERVICE_MAP[logger-klhk-retry]="klhk/retry.py retry.log"
SERVICE_MAP[logger-has-send]="backend/hasSend.py has-send.log"

for service in "${!SERVICE_MAP[@]}"; do
    IFS=" " read -r script log <<< "${SERVICE_MAP[$service]}"
    echo "  • Membuat $service.service..."
    
    cat <<EOF > "/etc/systemd/system/$service.service"
[Unit]
Description=logger $service Service
After=network.target

[Service]
Type=simple
WorkingDirectory=$APP_BASE/$(dirname "$script")
ExecStart=$APP_BASE/venv/bin/python -u $(basename "$script")
StandardOutput=append:$LOG_DIR/$log
StandardError=append:$LOG_DIR/$log
Restart=always
User=root
Group=root

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable "$service"
    systemctl restart "$service"
    echo "$service.service aktif."
done
echo ""

# === Selesai ===
echo "Instalasi logger selesai!"
echo "Gunakan perintah 'logger' di terminal."
echo "Untuk bantuan, jalankan 'logger help'."
echo ""
echo "============================================"
echo "Aplikasi dapat diakses di:"
echo "   - Web Interface: http://localhost:$WEB_PORT"
echo "   - Log Viewer: http://localhost:$LOG_PORT"
echo "   - PhpMyAdmin: http://localhost:8080"
echo "============================================"
