# ZAYVORA MATAB OS — Production Deployment Runbook
**Document ID:** `DEPLOY-OPS-2026-10-13`  
**Classification:** Operational Runbook — Infrastructure & Deployment Engineering  
**Scope:** Standalone Zayvora Matab OS Edge & Cloud Deployments  
**Status:** READY FOR PRODUCTION STAGING  

---

## 1. System Requirements & Architecture Models

Zayvora Matab OS supports two primary deployment topologies:
1. **Edge Clinic Local Node (Recommended for Clinics & Hospital Branches):** Operates on a dedicated clinic mini-PC or server with zero external internet dependencies for consultation, prescription, dispensing, and billing.
2. **Containerized Cloud Instance (For Central Multi-Branch Administration & Aggregation):** Docker/Podman container hosted on a virtual private server (VPS).

### Hardware Minimum Specifications
| Component | Minimum (Edge Node) | Recommended (Multi-Doctor Hospital) |
| :--- | :--- | :--- |
| **Processor (CPU)** | Intel Core i3 / AMD Ryzen 3 (4 cores) | Intel Core i7 / AMD Ryzen 7 (8 cores) |
| **Memory (RAM)** | 8 GB DDR4 | 16 GB DDR4/DDR5 |
| **Storage** | 128 GB NVMe SSD | 512 GB Enterprise NVMe SSD (RAID 1) |
| **Network** | 1 Gbps Ethernet LAN | 1 Gbps LAN + Dual WAN Failover (Fiber + 4G/5G) |
| **Operating System** | Ubuntu Server 24.04 LTS / Debian 12 / macOS | Ubuntu Server 24.04 LTS |

---

## 2. Environment Variables Configuration

Create `/opt/zayvora/config/.env.production` with permissions `chmod 600`:

```env
# ==========================================
# ZAYVORA MATAB OS — PRODUCTION CONFIGURATION
# ==========================================
APP_ENV=production
APP_NAME="Zayvora Matab OS"
PORT=8000
HOST=127.0.0.1
DEBUG=false

# Database Configuration
DATABASE_URL="sqlite:////opt/zayvora/data/zayvora_matab.db"
SQLITE_WAL_MODE=true
SQLITE_BUSY_TIMEOUT=10000

# Security Secrets (Generate using openssl rand -hex 32)
JWT_SECRET_KEY="replace_with_64_char_secure_random_hex_string"
JWT_ALGORITHM="HS256"
SESSION_LIFETIME_HOURS=12

# Clinical Safety Firewall Defaults
ENFORCE_FAIL_CLOSED_SAFETY=true
REQUIRE_CLINICIAN_PIN_SIGNATURE=true
SCHEDULE_E1_RESTRICTIONS_ACTIVE=true

# Interoperability & Integration
ABDM_SANDBOX_ENABLED=false
FHIR_VALIDATION_STRICT=true
CORS_ALLOWED_ORIGINS="https://matab.zayvora.internal,https://hospital.zayvora.internal"

# Logging & Auditing
LOG_LEVEL=INFO
AUDIT_TRAIL_CHAINING=true
LOG_FILE_PATH="/var/log/zayvora/matab_app.log"
```

---

## 3. Bare-Metal Systemd Service Setup (Ubuntu Server)

### 3.1 Application Service Unit (`/etc/systemd/system/zayvora-api.service`)
```ini
[Unit]
Description=Zayvora Matab OS Clinical API Server
After=network.target

[Service]
Type=simple
User=zayvora
Group=zayvora
WorkingDirectory=/opt/zayvora/apps
EnvironmentFile=/opt/zayvora/config/.env.production
ExecStart=/usr/bin/python3 -m apps.api.main
Restart=always
RestartSec=5
LimitNOFILE=65535

# Hardening Directives
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/zayvora/data /var/log/zayvora /var/backups/zayvora_matab
PrivateTmp=true
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
```

### 3.2 Automated Backup Service & Timer
Create `/etc/systemd/system/zayvora-backup.service`:
```ini
[Unit]
Description=Zayvora Matab OS SQLite Online Vacuum Backup
After=zayvora-api.service

[Service]
Type=oneshot
User=zayvora
ExecStart=/opt/zayvora/scripts/online_vacuum_backup.sh
```

Create `/etc/systemd/system/zayvora-backup.timer`:
```ini
[Unit]
Description=Hourly Online Backup Timer for Zayvora Matab OS

[Timer]
OnCalendar=hourly
Persistent=true

[Install]
WantedBy=timers.target
```

Enable and start services:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now zayvora-api.service
sudo systemctl enable --now zayvora-backup.timer
```

---

## 4. Nginx Reverse Proxy & Security Hardening

Create `/etc/nginx/sites-available/zayvora-matab`:
```nginx
server {
    listen 80;
    server_name matab.zayvora.internal;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name matab.zayvora.internal;

    ssl_certificate /etc/ssl/certs/zayvora_internal.crt;
    ssl_certificate_key /etc/ssl/private/zayvora_internal.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    # Security Headers
    add_header X-Content-Type-Options nosniff always;
    add_header X-Frame-Options DENY always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self';" always;

    # Gzip Compression
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml;

    # Web Static UI
    location /static/ {
        alias /opt/zayvora/apps/web/static/;
        expires 7d;
        add_header Cache-Control "public, no-transform";
    }

    # API Proxy
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 5s;
        proxy_read_timeout 60s;
    }

    # Web App Root
    location / {
        root /opt/zayvora/apps/web;
        try_files /index.html =404;
    }
}
```

---

## 5. Deployment Verification Checklist

Run these commands immediately following service deployment:
1. **Health Endpoint Verification:**
   ```bash
   curl -s http://127.0.0.1:8000/api/health | jq .
   # Expected: {"status": "ok", "database": "connected", "migrations_version": 12}
   ```
2. **Database Integrity Verification:**
   ```bash
   sqlite3 /opt/zayvora/data/zayvora_matab.db "PRAGMA integrity_check;"
   # Expected: ok
   ```
3. **Safety Engine Ping:**
   ```bash
   curl -s http://127.0.0.1:8000/api/safety/status | jq .
   # Expected: {"firewall": "FAIL_CLOSED_ACTIVE", "rules_loaded": 42}
   ```
4. **Log Inspection:**
   ```bash
   journalctl -u zayvora-api.service -n 50 --no-pager
   ```
