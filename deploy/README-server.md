# Zoomies Server — Ubuntu Deployment

## Prerequisites

- Ubuntu 22.04+ (or any systemd-based Linux)
- Python 3.12+
- A dedicated user account (optional but recommended)

## Quick Setup

```bash
# 1. Create a service user (optional)
sudo useradd -r -s /usr/sbin/nologin -m -d /home/rudi rudi

# 2. Copy server files to /opt/zoomies
sudo mkdir -p /opt/zoomies
sudo cp -r server/ static/ run_server.py version.py requirements-server.txt /opt/zoomies/
sudo chown -R rudi:rudi /opt/zoomies

# 3. Create a virtual environment and install dependencies
sudo -u rudi bash -c 'cd /opt/zoomies && python3 -m venv venv && venv/bin/pip install -r requirements-server.txt'

# 4. Create data directories
sudo mkdir -p /var/opt/zoomies/database /var/opt/zoomies/media/questions /var/opt/zoomies/backups
sudo chown -R rudi:rudi /var/opt/zoomies

# 5. Install the systemd service
sudo cp deploy/zoomies.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable zoomies
sudo systemctl start zoomies
```

## Firewall

Open port 5000 (or whichever port you configure):

```bash
sudo ufw allow 5000/tcp
```

## Configuration

- **Port/host**: Edit the `SERVER_HOST`/`SERVER_PORT` constants in `server/config.py`.
- **Data directory**: Variable data lives under `/var/opt/zoomies/` (database, media, backups), separate from the read-only app code in `/opt/zoomies/`. See `server/config.py`.

## Logs

```bash
sudo journalctl -u zoomies -f
```

## Backups

The database lives at `/var/opt/zoomies/database/zoomies.db`. Back it up with a cron job or manual copy:

```bash
cp /var/opt/zoomies/database/zoomies.db /var/opt/zoomies/backups/zoomies-$(date +%Y%m%d).db
```

Media files are under `/var/opt/zoomies/media/questions/`.
