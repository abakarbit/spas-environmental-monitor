#!/bin/bash

# ============================================
#  SPAS — Edge-Based Environmental Telemetry & SPARING Gateway - Uninstaller
# ============================================
# Nama Aplikasi : SPAS — Edge-Based Environmental Telemetry & SPARING Gateway (logger)
# Fungsi        : Menghapus semua komponen logger dari sistem
# Dibuat oleh   : Abu Bakar <abubakar.it.dev@gmail.com>
# Versi         : 1.1
# ============================================

echo "============================================"
echo " SPAS — Edge-Based Environmental Telemetry & SPARING Gateway (logger) - Uninstaller"
echo "============================================"
echo "Dibuat oleh : Abu Bakar <abubakar.it.dev@gmail.com>"
echo ""

set -e  # Hentikan jika terjadi error

APP_BASE="/opt/logger"
SERVICES=("logger-sensor.service" "logger-web.service" "logger-web-log.service" "logger-gpio.service" "logger-backup.service" "logger-klhk-send.service" "logger-klhk-retry.service" "logger-has-send.service")

# === Hentikan dan nonaktifkan semua service ===
echo "Menghentikan dan menonaktifkan systemd services..."
for service in "${SERVICES[@]}"; do
    if systemctl is-enabled --quiet "$service"; then
        echo "🔻 Menonaktifkan & menghentikan $service..."
        systemctl stop "$service"
        systemctl disable "$service"
        rm -f "/etc/systemd/system/$service"
        echo "$service dihapus."
    else
        echo "ℹ$service tidak ditemukan atau sudah nonaktif."
    fi
done

# Reload systemd
echo "Reload systemd daemon..."
systemctl daemon-reload
systemctl reset-failed

# === Hapus direktori instalasi ===
if [[ -d "$APP_BASE" ]]; then
    echo "Menghapus direktori instalasi di $APP_BASE..."
    rm -rf "$APP_BASE"
else
    echo "Direktori $APP_BASE tidak ditemukan, melewati."
fi

# === Hapus symlink CLI ===
if [[ -f "/usr/bin/logger" ]]; then
    echo "Menghapus CLI /usr/bin/logger..."
    rm -f /usr/bin/logger
else
    echo "CLI /usr/bin/logger tidak ditemukan."
fi

# === Konfirmasi penghapusan database Docker ===
if docker ps -a --format '{{.Names}}' | grep -q "^db_logger$"; then
    echo ""
    echo "Container Docker 'db_logger' ditemukan."
    read -p "Apakah Anda ingin menghapus database ini? [y/N]: " confirm
    if [[ "$confirm" =~ ^[Yy]$ ]]; then
        echo "Menghentikan dan menghapus container 'db_logger'..."
        docker stop db_logger
        docker rm db_logger
        echo "Container 'db_logger' telah dihapus."
    else
        echo "Container 'db_logger' dibiarkan tetap ada."
    fi
else
    echo "Container 'db_logger' tidak ditemukan."
fi

echo ""
echo "Uninstall selesai! Semua komponen utama logger telah dihapus dari sistem."
echo "Terima kasih telah menggunakan logger Project!"