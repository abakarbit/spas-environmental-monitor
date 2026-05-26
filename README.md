# SPAS — Edge-Based Environmental Telemetry & SPARING Gateway

> **Real-time IIoT environmental monitoring platform** — acquires multi-parameter sensor data via Modbus RTU/TCP & GPIO, stores it in MySQL, serves a live web dashboard, and transmits hourly readings to the Indonesian **KLHK SPARING** regulatory API for environmental compliance.

[![License](https://img.shields.io/badge/License-Private%2FInternal-red.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-2.3.3-green.svg)](https://flask.palletsprojects.com/)
[![Platform](https://img.shields.io/badge/Platform-Raspberry%20Pi%20%7C%20Linux-lightgrey.svg)](https://www.raspberrypi.com/)
[![Version](https://img.shields.io/badge/Version-1.0.0-brightgreen.svg)]()

---

## Table of Contents

- [About the Project](#about-the-project)
- [Built With](#built-with)
- [System Architecture](#system-architecture)
- [Database Schema](#database-schema)
- [Sensor Modules](#sensor-modules)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
  - [Environment Configuration](#environment-configuration)
- [Usage](#usage)
  - [Service Management](#service-management)
  - [Web Dashboard](#web-dashboard)
  - [CLI Interface](#cli-interface)
- [Regulatory Integration](#regulatory-integration)
- [Roadmap](#roadmap)
- [License & Contact](#license--contact)

---

## About the Project

**SPAS — Edge-Based Environmental Telemetry & SPARING Gateway** is a field-deployable IIoT monitoring system designed for industrial and environmental applications requiring continuous, multi-parameter data acquisition. The system is architected around a Raspberry Pi edge device that communicates with a heterogeneous array of scientific instruments via RS485 (Modbus RTU), Ethernet (Modbus TCP), and GPIO interfaces.

### Problem Statement

Industrial facilities operating under Indonesian environmental regulations (PROPER, SPARING) are required to continuously monitor and report effluent quality parameters — including pH, COD, BOD, TSS, NH₃N, and flow rate — to the Kementerian Lingkungan Hidup dan Kehutanan (KLHK). Manual data submission is error-prone and non-compliant with SPARING's automated hourly reporting requirements.

### Solution

SPAS provides an end-to-end automated pipeline:

1. **Acquire** — Reads raw sensor data from up to six modular instrument drivers on a configurable polling interval (1–n minutes).
2. **Persist** — Stores timestamped readings in a MySQL database (containerized via Docker) with full audit columns and a separate transmission queue table.
3. **Visualize** — Serves a real-time web dashboard with interactive charts (Plotly), geographic map (Leaflet), and wind rose for meteorological stations.
4. **Transmit** — Dispatches hourly averages to the KLHK SPARING API and HAS API using JWT-authenticated HTTP requests, with automatic retry logic for failed submissions.
5. **Backup** — Executes daily compressed mysqldump backups with incremental state tracking.

### Design Philosophy

- **Modular sensor drivers**: Each instrument is an independent Python module activated/deactivated via a single environment variable flag (`active` / `inactive`). Adding a new instrument requires no changes to the orchestration layer.
- **Systemd-native**: Every daemon runs as a discrete `systemd` service with automatic restart, enabling production-grade reliability without external process managers.
- **Zero-downtime configuration**: All runtime parameters — sensor ports, API endpoints, database credentials, polling intervals — are externalized to a single `config/.env` file and loaded at startup.

---

## Built With

### Software & Frameworks

| Component | Technology | Version |
|---|---|---|
| Application runtime | Python | 3.9+ |
| Web framework | Flask | 2.3.3 |
| Database (primary) | MySQL via Docker | `aqliserdadu/db:logger` |
| Database (GPIO buffer) | SQLite3 | built-in |
| Frontend charting | Plotly.js | latest |
| Frontend mapping | Leaflet.js | latest |
| Frontend UI | Bootstrap | 5.3.3 |
| Date picker | Flatpickr | latest |
| Serial communication | pyserial | 3.5 |
| Database connector | mysql-connector-python | 8.3.0 |
| Environment management | python-dotenv | 1.0.1 |
| Timezone handling | pytz | 2024.1 |
| JWT authentication | PyJWT | 2.8.0 |
| Data processing | pandas / numpy | 2.2.2 / 1.26.4 |
| GPIO (option A) | RPi.GPIO | latest |
| GPIO (option B) | lgpio | latest |
| Process management | systemd | system |
| Container runtime | Docker | system |

### Hardware

| Device | Role | Interface |
|---|---|---|
| Raspberry Pi (any model with UART) | Edge compute & orchestration | — |
| **AT500** Multi-parameter Water Quality Probe | pH, ORP, TDS, Conductivity, DO, Salinity, NH₃N | RS485 Modbus RTU (`/dev/ttyAMA5`) |
| **RT200** Hydrostatic Level Transmitter | Temperature, Pressure, Depth | RS485 Modbus RTU (`/dev/ttyAMA4`) |
| **SEM5096** Automatic Weather Station | Temp, Humidity, Pressure, Wind Speed, Wind Direction, Rainfall, Solar Radiation | RS485 Serial (`/dev/ttyAMA6`) |
| **MACE** Electromagnetic Flow Meter | Battery, Depth, Flow Rate, Total Flow | RS485 Modbus RTU (`/dev/ttyAMA3`) |
| **SPECTRO** Photometric Analyzer | Turbidity, TSS, COD, BOD, NO₃ | Modbus TCP (Ethernet) |
| **ARG314** Tipping Bucket Rain Gauge | Rainfall accumulation | GPIO (BCM pin, configurable) |

---

## System Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                     RASPBERRY PI EDGE DEVICE                     │
│                                                                  │
│  ┌──────────┐  RS485/UART   ┌─────────────────────────────────┐ │
│  │  AT500   │──────────────▶│                                 │ │
│  │  RT200   │──────────────▶│   logger-sensor.service         │ │
│  │  SEM5096 │──────────────▶│   (main.py)                     │ │
│  │  MACE    │──────────────▶│   Polling interval: DELAY min   │ │
│  └──────────┘               └────────────┬────────────────────┘ │
│                                          │                       │
│  ┌──────────┐  Modbus TCP               ▼                       │
│  │  SPECTRO │──────────────▶  ┌─────────────────────┐          │
│  └──────────┘               │   MySQL (Docker)      │          │
│                             │   db_logger           │          │
│  ┌──────────┐  GPIO IRQ     │   tables: data, tmp   │          │
│  │  ARG314  │──────────────▶│                       │          │
│  └──────────┘  (arg314.py)  └─────┬─────────┬───────┘          │
│               SQLite buffer       │         │                   │
│                                   │         │                   │
│  ┌────────────────────────────────▼──┐   ┌──▼────────────────┐ │
│  │  logger-web.service (app.py)      │   │ logger-klhk-send  │ │
│  │  Flask REST API + Static Frontend │   │ logger-klhk-retry │ │
│  │  Port: $PORT_NUMBER_APP           │   │ logger-has-send   │ │
│  └────────────────────────────────┬──┘   └──┬────────────────┘ │
└───────────────────────────────────│──────────│──────────────────┘
                                    │          │
                    ┌───────────────▼──┐    ┌──▼──────────────────┐
                    │  Browser Client  │    │  KLHK SPARING API   │
                    │  Dashboard UI    │    │  HAS API            │
                    └──────────────────┘    └─────────────────────┘
```

### Systemd Services

| Service | Entry Point | Role |
|---|---|---|
| `logger-sensor` | `backend/main.py` | Main sensor polling loop |
| `logger-web` | `backend/app.py` | Flask web server & REST API |
| `logger-web-log` | — | Log streaming service (port `$PORT_NUMBER_LOG`) |
| `logger-backup` | `backend/backup.py` | Daily mysqldump + gzip backup |
| `logger-gpio` | `backend/arg314.py` | ARG314 rain gauge GPIO interrupt handler |
| `logger-klhk-send` | `klhk/send.py` | Hourly KLHK SPARING data submission |
| `logger-klhk-retry` | `klhk/retry.py` | Retry failed KLHK submissions at `$KLHK_TARGET_MINUTE` |
| `logger-has-send` | `backend/hasSend.py` | HAS API data transmission |

---

## Database Schema

The primary MySQL database (`logger`) contains the following core tables:

### `data` — Master Sensor Readings

```sql
CREATE TABLE data (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    device        TEXT,
    `date`        DATETIME,
    datetime      BIGINT DEFAULT 0,   -- Unix timestamp

    -- Water Quality (AT500)
    pH            FLOAT DEFAULT 0,
    orp           FLOAT DEFAULT 0,    -- mV
    tds           FLOAT DEFAULT 0,    -- ppm
    conduct       FLOAT DEFAULT 0,    -- µS/cm
    `do`          FLOAT DEFAULT 0,    -- mg/L
    salinity      FLOAT DEFAULT 0,    -- ppt
    nh3n          FLOAT DEFAULT 0,    -- mg/L

    -- Hydrology (MACE / RT200)
    battery       FLOAT DEFAULT 0,
    depth         FLOAT DEFAULT 0,    -- m
    flow          FLOAT DEFAULT 0,    -- m³/s
    tflow         FLOAT DEFAULT 0,    -- m³ (total)

    -- Spectrophotometry (SPECTRO)
    turb          FLOAT DEFAULT 0,    -- NTU
    tss           FLOAT DEFAULT 0,    -- mg/L
    cod           FLOAT DEFAULT 0,    -- mg/L
    bod           FLOAT DEFAULT 0,    -- mg/L
    no3           FLOAT DEFAULT 0,    -- mg/L

    -- Environmental (RT200 / SEM5096)
    temp          FLOAT DEFAULT 0,    -- °C
    press         FLOAT DEFAULT 0,    -- hPa
    hum           FLOAT DEFAULT 0,    -- %RH
    wspeed        FLOAT DEFAULT 0,    -- m/s
    wdir          FLOAT DEFAULT 0,    -- degrees
    rain          FLOAT DEFAULT 0,    -- mm
    srad          FLOAT DEFAULT 0,    -- W/m²

    -- Transmission metadata
    status        TEXT,
    keterangan    TEXT,
    dateterkirim  DATETIME,
    has           INT DEFAULT 0       -- HAS API send flag
);
```

### `tmp` — KLHK Transmission Queue

Mirrors the `data` schema. Populated alongside `data` on every insert. The `status` column tracks transmission state:

| `status` value | Meaning |
|---|---|
| `NULL` | Pending first send attempt |
| `'sent'` | Successfully delivered to KLHK SPARING |
| `'retry'` | Failed; queued for retry by `logger-klhk-retry` |

### `gpio` — Rain Gauge Buffer (SQLite)

Located at `$SQLITE_DB_PATH` (default: `/opt/logger/data/gpio_logger.db`):

```sql
CREATE TABLE gpio (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    date   DATETIME,
    sensor TEXT,
    nilai  REAL DEFAULT 0
);
```

---

## Sensor Modules

### Modbus RTU Sensors (RS485)

All RS485 drivers implement a shared retry pattern with configurable `MAX_RETRIES`. The serial connection is opened and closed per transaction to prevent port locking.

| Parameter | AT500 | RT200 | MACE |
|---|---|---|---|
| Baud Rate | 19200 | 19200 | 19200 |
| Parity | Even | Even | None |
| Stop Bits | 1 | 1 | 1 |
| Data Bits | 8 | 8 | 8 |
| Timeout | 1 s | 1 s | 1 s |
| Max Retries | 3 | 5 | 1 |

### Modbus TCP Sensor (SPECTRO)

Connects to a configurable IP endpoint (`$SPECTRO_IP:$SPECTRO_PORT`). Uses standard Modbus TCP framing (MBAP header + PDU). Each parameter is read from a discrete register address range with a 0.5 s inter-request delay.

### GPIO Rain Gauge (ARG314)

Uses hardware interrupt detection (falling-edge) on a configurable BCM pin. Each pulse corresponds to `$RESOLUTION` mm of rainfall. Debouncing is applied at `$DEBOUNCE_MS` milliseconds. Supports both `RPi.GPIO` and `lgpio` backends, selected via `$GPIO_MODULE`. A `DEMO_MODE` flag generates random simulated rainfall for development environments.

---

## Getting Started

### Prerequisites

Ensure the following are available on the target system before installation:

| Requirement | Minimum Version | Notes |
|---|---|---|
| Operating System | Linux (Debian/Raspberry Pi OS) | Systemd required |
| Python | 3.9+ | `python3 --version` |
| pip | latest | `pip --version` |
| Docker | latest | Required for MySQL container |
| MariaDB client | latest | `apt install mariadb-client` |
| Root access | — | `sudo` required for systemd & Docker |
| RS485 UART ports | — | Enabled in `/boot/config.txt` (RPi) |

#### Enabling Raspberry Pi UART Ports

The system uses up to four hardware UART channels. Add the following to `/boot/config.txt`:

```ini
# Enable overlay UARTs for RS485 sensors
dtoverlay=uart2
dtoverlay=uart3
dtoverlay=uart4
dtoverlay=uart5
```

Map the expected ports:

| UART | Device | Sensor |
|---|---|---|
| UART3 | `/dev/ttyAMA3` | MACE Flow Meter |
| UART4 | `/dev/ttyAMA4` | RT200 Level Transmitter |
| UART5 | `/dev/ttyAMA5` | AT500 Water Quality Probe |
| UART6 | `/dev/ttyAMA6` | SEM5096 Weather Station |

---

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/<your-org>/logger.git
cd logger

# 2. Configure environment variables (see section below)
cp config/.env config/.env.bak
nano config/.env

# 3. Run the installer as root
sudo bash install.sh
```

The installer performs the following operations automatically:

- Validates port availability and checks for conflicting existing services
- Copies the application to `/opt/logger`
- Creates a Python virtual environment at `/opt/logger/venv`
- Installs all Python dependencies from `requirements.txt`
- Pulls and starts the MySQL Docker container (`aqliserdadu/db:logger`)
- Installs `mariadb-client`, `python3-rpi.gpio`, `python3-lgpio`
- Creates and enables all systemd service units
- Registers the `logger` CLI at `/usr/bin/logger`

#### Uninstall

```bash
sudo bash uninstall.sh
```

---

### Environment Configuration

All runtime configuration is stored in `config/.env`. The file is sourced by the installer and loaded by all Python services at startup.

#### General

| Variable | Example | Description |
|---|---|---|
| `PORT_NUMBER_APP` | `5019` | Flask web dashboard port |
| `PORT_NUMBER_LOG` | `3001` | Log streaming port |
| `TIMEZONE` | `Asia/Jakarta` | System timezone (pytz string) |
| `DELAY` | `1` | Sensor polling interval (minutes) |
| `DEVICE_ID` | `SPAS-001` | Unique device identifier |
| `LOCATION_NAME` | `PT. Example Industry` | Displayed on dashboard |
| `SOFTWARE_VERSION` | `1.0.0` | Shown in UI metadata |
| `WEB_TITLE` | `SPAS Dashboard` | Browser tab title |
| `WEB_NAME` | `Smart Portable Analyzer` | Dashboard header text |

#### Database

| Variable | Example | Description |
|---|---|---|
| `DB_HOST` | `127.0.0.1` | MySQL host address |
| `DB_PORT` | `3306` | MySQL port |
| `DB_NAME` | `logger` | Database name |
| `DB_USER` | `project` | MySQL username |
| `DB_PASSWORD` | `**secret**` | MySQL password |
| `SQLITE_DB_PATH` | `/opt/logger/data/gpio_logger.db` | SQLite path for GPIO buffer |

#### Sensor Modules

Each sensor module is independently toggled. Set to `active` to enable, `inactive` to skip.

| Variable | Options | Description |
|---|---|---|
| `AT500_STATUS` | `active` / `inactive` | AT500 water quality probe |
| `AT500_PORT` | `/dev/ttyAMA5` | Serial device path |
| `RT200_STATUS` | `active` / `inactive` | RT200 level transmitter |
| `RT200_PORT` | `/dev/ttyAMA4` | Serial device path |
| `SEM5096_STATUS` | `active` / `inactive` | SEM5096 weather station |
| `SEM5096_PORT` | `/dev/ttyAMA6` | Serial device path |
| `MACE_STATUS` | `active` / `inactive` | MACE flow meter |
| `MACE_PORT` | `/dev/ttyAMA3` | Serial device path |
| `SPECTRO_STATUS` | `active` / `inactive` | SPECTRO photometric analyzer |
| `SPECTRO_IP` | `192.168.1.100` | Modbus TCP IP address |
| `SPECTRO_PORT` | `502` | Modbus TCP port |
| `ARG314_STATUS` | `active` / `inactive` | ARG314 tipping bucket rain gauge |
| `RAIN_SENSOR_PIN` | `18` | BCM GPIO pin number |
| `RESOLUTION` | `0.202` | Rainfall per tip (mm) |
| `DEBOUNCE_MS` | `200` | Hardware debounce delay (ms) |
| `DEMO_MODE` | `active` / `inactive` | Simulate random rainfall data |
| `GPIO_MODULE` | `Rpi.GPIO` / `lgpio` | GPIO backend library |

#### KLHK SPARING API

| Variable | Example | Description |
|---|---|---|
| `KLHK_STATUS` | `active` / `inactive` | Enable KLHK SPARING transmission |
| `KLHK_API_URL` | `https://kemenlh.go.id/api/xxxx` | Submission endpoint |
| `KLHK_TOKEN_URL` | `https://kemenlh.go.id/api/xxxx` | JWT token endpoint |
| `KLHK_UID` | `y5655446NH6WE` | Registered sensor UID |
| `KLHK_FIELDS` | `datetime,pH,tss,cod,nh3n,flow` | Parameters to transmit (comma-separated) |
| `KLHK_MAX_DUP_RETRY` | `3` | Maximum duplicate retry attempts |
| `KLHK_TARGET_MINUTE` | `5` | Minute of the hour to trigger retry service |

#### HAS API

| Variable | Example | Description |
|---|---|---|
| `HAS_STATUS` | `active` / `inactive` | Enable HAS API transmission |
| `HAS_API_URL` | `https://...` | HAS submission endpoint |
| `HAS_TOKEN` | `<jwt-secret>` | JWT signing key |

#### Parameter Units

Configure display units for each parameter on the web dashboard:

```ini
SATUAN_PH=""
SATUAN_ORP="mV"
SATUAN_TDS="ppm"
SATUAN_CONDUCT="µS/cm"
SATUAN_DO="mg/L"
SATUAN_SALINITY="ppt"
SATUAN_NH3N="mg/L"
SATUAN_TURB="NTU"
SATUAN_TSS="mg/L"
SATUAN_COD="mg/L"
SATUAN_BOD="mg/L"
SATUAN_NO3="mg/L"
SATUAN_TEMP="°C"
SATUAN_PRESS="hPa"
SATUAN_BATTERY="V"
SATUAN_DEPTH="m"
SATUAN_FLOW="m³/s"
SATUAN_TFLOW="m³"
SATUAN_HUM="%"
SATUAN_WSPEED="m/s"
SATUAN_WDIR="°"
SATUAN_RAIN="mm"
SATUAN_SRAD="W/m²"
```

---

## Usage

### Service Management

```bash
# Check status of all services
sudo systemctl status logger-sensor logger-web logger-gpio logger-klhk-send

# Start / stop / restart individual service
sudo systemctl start   logger-sensor.service
sudo systemctl stop    logger-sensor.service
sudo systemctl restart logger-web.service

# View real-time logs
journalctl -u logger-sensor -f
journalctl -u logger-web -f
journalctl -u logger-klhk-send -f

# View file-based logs
tail -f /opt/logger/logs/sensor.log
tail -f /opt/logger/log/web.log
tail -f /opt/logger/logs/gpio.log
```

### Web Dashboard

Access the dashboard from a browser on the local network:

```
http://<device-ip>:<PORT_NUMBER_APP>
```

The dashboard provides:

- **Live parameter cards** — current reading, unit, and last update timestamp for each active parameter
- **Time-series chart** — interactive Plotly chart with date range selection via Flatpickr
- **Wind rose** — directional frequency visualization for meteorological stations
- **Geographic map** — Leaflet.js map pinpointing the monitoring station location
- **WiFi management modal** — scan and connect to wireless networks without SSH

#### REST API Endpoints

The Flask backend exposes the following JSON endpoints:

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/latest` | Most recent sensor reading |
| `GET` | `/api/data?start=&end=` | Filtered historical data |
| `GET` | `/api/config` | Device metadata and parameter units |
| `GET` | `/api/export?start=&end=` | Export data as CSV/Excel |

### CLI Interface

The `logger` CLI (installed at `/usr/bin/logger`) provides shorthand commands for common operations:

```bash
logger status       # Show status of all services
logger restart      # Restart all services
logger logs         # Stream aggregated logs
logger backup       # Trigger manual database backup
```

---

## Regulatory Integration

### KLHK SPARING (Sistem Pemantauan Kualitas Air Secara Online)

SPAS integrates with the Indonesian Ministry of Environment (KLHK) SPARING platform, which mandates continuous online water quality monitoring for industries regulated under PROPER.

**Data Flow:**

```
[data table] → [tmp table] → [klhk/send.py] → KLHK SPARING API
                                 │
                             JWT Token
                         (fetched per session)
                                 │
                         [Hourly aggregation]
                                 │
                         HTTP POST (JSON payload)
                                 │
                         Status update in tmp table
                                 │
                         [klhk/retry.py at $KLHK_TARGET_MINUTE]
                                 │
                         Retry status='retry' records
```

**JWT Authentication:** The system fetches a session token from `$KLHK_TOKEN_URL` before each submission. The token is used as a Bearer credential in the Authorization header.

**Parameters transmitted** are configurable via `$KLHK_FIELDS`. Any subset of the available parameters can be sent without code modification.

---

## Project Structure

```
logger/
├── backend/
│   ├── main.py          # Sensor polling orchestrator
│   ├── app.py           # Flask web application & REST API
│   ├── config.py        # MySQL connection helpers & table initialization
│   ├── at500.py         # AT500 water quality probe driver (Modbus RTU)
│   ├── rt200.py         # RT200 level transmitter driver (Modbus RTU)
│   ├── sem5096.py       # SEM5096 weather station driver (RS485 serial)
│   ├── mace.py          # MACE flow meter driver (Modbus RTU)
│   ├── spectro.py       # SPECTRO photometric analyzer driver (Modbus TCP)
│   ├── arg314.py        # ARG314 rain gauge driver (GPIO interrupt)
│   ├── hasSend.py       # HAS API data transmission service
│   ├── backup.py        # Daily MySQL backup (mysqldump + gzip)
│   └── log.py           # Log streaming server
├── frontend/
│   ├── index.html       # Main dashboard
│   ├── log.html         # Log viewer
│   ├── css/style.css    # Custom stylesheet
│   └── js/script.js     # Dashboard logic
├── klhk/
│   ├── send.py          # KLHK SPARING hourly send service
│   └── retry.py         # KLHK SPARING retry service
├── config/
│   └── env              # Runtime configuration (all secrets)
├── requirements.txt     # Python dependencies
├── install.sh           # One-command installer
└── uninstall.sh         # Service teardown & cleanup
```

---

## Roadmap

| Priority | Feature | Status |
|---|---|---|
| High | HTTPS/TLS support for web dashboard | Planned |
| High | OTA (Over-The-Air) configuration update via API | Planned |
| Medium | InfluxDB + Grafana integration for long-term time-series analytics | Planned |
| Medium | SMS/email alert notification on threshold breach | Planned |
| Medium | Multi-device aggregation dashboard (fleet management) | Planned |
| Low | Docker Compose deployment option (full stack) | Planned |
| Low | Prometheus metrics exporter for `/metrics` endpoint | Planned |
| Low | Automated test suite with mock serial ports | Planned |

---

## License & Contact

**License:** Private / Internal Project — All rights reserved.

> This software is developed for internal operational use. Redistribution or modification without written authorization from the maintainer is prohibited.

---

**Maintainer:** Abu Bakar
**Email:** [abubakar.it.dev@gmail.com](mailto:abubakar.it.dev@gmail.com)
**Project Version:** 1.0.0
**Install Path:** `/opt/logger`

---

*Generated for SPAS — Edge-Based Environmental Telemetry & SPARING Gateway*
