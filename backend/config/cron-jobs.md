# Cron Jobs Configuration

## Daily Sync Job

Add this to your crontab (`crontab -e`):

```bash
# Football Predictions Daily Sync
# Runs at 6:00 AM every day (before most Ligue 1 matches)
0 6 * * * cd /Users/hatemahmed/football-predictions/backend && /usr/bin/python3 scripts/daily_sync.py >> logs/daily_sync.log 2>&1
```

## Alternative: Systemd Timer (Linux)

1. Create service file `/etc/systemd/system/kickstat-sync.service`:

```ini
[Unit]
Description=Kickstat Daily Sync
After=network.target

[Service]
Type=oneshot
User=your_user
WorkingDirectory=/path/to/football-predictions/backend
ExecStart=/usr/bin/python3 scripts/daily_sync.py
StandardOutput=append:/path/to/football-predictions/backend/logs/daily_sync.log
StandardError=append:/path/to/football-predictions/backend/logs/daily_sync.log

[Install]
WantedBy=multi-user.target
```

2. Create timer file `/etc/systemd/system/kickstat-sync.timer`:

```ini
[Unit]
Description=Run Kickstat sync daily

[Timer]
OnCalendar=*-*-* 06:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

3. Enable the timer:

```bash
sudo systemctl enable kickstat-sync.timer
sudo systemctl start kickstat-sync.timer
```

## Launchd (macOS)

Create `~/Library/LaunchAgents/com.kickstat.sync.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.kickstat.sync</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>/Users/hatemahmed/football-predictions/backend/scripts/daily_sync.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/Users/hatemahmed/football-predictions/backend</string>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>6</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>/Users/hatemahmed/football-predictions/backend/logs/daily_sync.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/hatemahmed/football-predictions/backend/logs/daily_sync.log</string>
</dict>
</plist>
```

Load the agent:

```bash
launchctl load ~/Library/LaunchAgents/com.kickstat.sync.plist
```

## Manual Run

```bash
cd /Users/hatemahmed/football-predictions/backend
python scripts/daily_sync.py

# Or with specific options:
python scripts/daily_sync.py --fixtures-only
python scripts/daily_sync.py --odds-only
python scripts/daily_sync.py --xg-only
```
