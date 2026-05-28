# Rudi Server — Ubuntu Deployment

## Prerequisites

- Ubuntu 22.04+ (or any systemd-based Linux)
- Python 3.12+
- A dedicated user account (optional but recommended)

## Quick Setup

```bash
# 1. Create a service user (optional)
sudo useradd -r -s /usr/sbin/nologin -m -d /opt/rudi rudi

# 2. Copy server files to /opt/rudi
sudo mkdir -p /opt/rudi
sudo cp -r server/ static/ run_server.py version.py requirements-server.txt /opt/rudi/
sudo chown -R rudi:rudi /opt/rudi

# 3. Create a virtual environment and install dependencies
sudo -u rudi bash -c 'cd /opt/rudi && python3 -m venv venv && venv/bin/pip install -r requirements-server.txt'

# 4. Create data directories
sudo -u rudi mkdir -p /opt/rudi/data/database /opt/rudi/data/backups

# 5. Install the systemd service
sudo cp deploy/rudi-server.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable rudi-server
sudo systemctl start rudi-server
```

## Firewall

Open port 5000 (or whichever port you configure):

```bash
sudo ufw allow 5000/tcp
```

## Configuration

- **Port/host**: Edit `server/config.py` constants or set environment variables in the service file.
- **Data directory**: Set `RUDI_DATA_DIR` in the service file's `Environment=` line.

## Logs

```bash
sudo journalctl -u rudi-server -f
```

## Backups

The database lives at `$RUDI_DATA_DIR/database/rudi.db`. Back it up with a cron job or manual copy:

```bash
cp $RUDI_DATA_DIR/database/rudi.db $RUDI_DATA_DIR/backups/rudi-$(date +%Y%m%d).db
```

Media files are under `$RUDI_DATA_DIR/media/questions/`.
