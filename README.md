# Health Check Monitor

TCP and ICMP ping health checker with interactive web dashboard. Monitors single or multiple targets via TCP connection or ping, runs configurable checks per minute, records uptime percentage and latency, auto-cleans old data.

## Requirements

- Python 3.6+
- No pip dependencies (stdlib only)
- Dashboard uses Chart.js via CDN (requires internet on client browser)

## Quick Start

```bash
# Start everything (health checks every 60s + dashboard)
./run.sh

# Open dashboard
open http://localhost:8111
```

## Usage

```bash
# Run checks + dashboard (default)
./run.sh

# Single check only (useful for cron)
./run.sh check

# Dashboard only
./run.sh dashboard

# Custom bind address and port
./run.sh dashboard 127.0.0.1 9090
./run.sh all 0.0.0.0 8080

# Direct Python usage
python3 healthcheck.py              # single check
python3 dashboard.py                # dashboard on default host:port
python3 dashboard.py 127.0.0.1 9090 # dashboard on custom host:port
```

### Cron Setup

To run checks every minute via cron:

```bash
# Edit crontab
crontab -e

# Add this line (adjust path)
* * * * * /path/to/healthcheck/run.sh check >> /path/to/healthcheck/check.log 2>&1
```

Then run the dashboard separately:

```bash
./run.sh dashboard
```

## Configuration

Edit `config.json`:

```json
{
  "targets": [
    {"name": "Google DNS", "host": "8.8.8.8", "port": 53, "type": "tcp"},
    {"name": "Cloudflare DNS", "host": "1.1.1.1", "port": 53, "type": "tcp"},
    {"name": "Google", "host": "google.com", "port": 443, "type": "tcp"},
    {"name": "Google Ping", "host": "8.8.8.8", "type": "ping"},
    {"name": "Cloudflare Ping", "host": "1.1.1.1", "type": "ping"},
    {"name": "GitHub API", "host": "api.github.com", "url": "https://api.github.com", "type": "http"},
    {"name": "Google HTTP", "host": "google.com", "url": "https://www.google.com", "type": "http"}
  ],
  "checks_per_minute": 10,
  "timeout_seconds": 5,
  "retention_days": 7,
  "data_dir": "data",
  "dashboard_host": "0.0.0.0",
  "dashboard_port": 8111
}
```

| Field | Description | Default |
|---|---|---|
| `targets` | Array of targets to monitor | — |
| `targets[].name` | Display name | — |
| `targets[].host` | Hostname or IP | — |
| `targets[].port` | TCP port (required for `tcp` type, omit for `ping`/`http`) | — |
| `targets[].type` | Check type: `tcp`, `ping`, or `http` | `tcp` |
| `targets[].url` | Full URL for `http` type (e.g., `https://api.example.com/health`) | — |
| `targets[].method` | HTTP method (`GET`, `POST`, `HEAD`, etc.) | `GET` |
| `targets[].headers` | HTTP headers as key-value object | — |
| `targets[].body` | Request body string (for POST/PUT) | — |
| `targets[].expected_status` | List of acceptable HTTP status codes (e.g., `[200, 201]`) | `200-399` |
| `checks_per_minute` | Number of check attempts per minute per target | `10` |
| `timeout_seconds` | TCP connection timeout | `5` |
| `retention_days` | Auto-delete data older than N days | `7` |
| `data_dir` | Directory for CSV data files (relative to script) | `data` |
| `dashboard_host` | Dashboard bind address (`0.0.0.0` = all interfaces, `127.0.0.1` = local only) | `0.0.0.0` |
| `dashboard_port` | Dashboard HTTP port | `8111` |

### HTTP/API Endpoint Examples

```json
// Basic HTTPS endpoint
{"name": "My API", "host": "api.example.com", "url": "https://api.example.com/health", "type": "http"}

// POST with headers and body
{"name": "Auth API", "host": "auth.example.com", "url": "https://auth.example.com/login",
 "type": "http", "method": "POST",
 "headers": {"Content-Type": "application/json"},
 "body": "{\"user\":\"healthcheck\"}"}

// Accept specific status codes
{"name": "Legacy API", "host": "old.example.com", "url": "https://old.example.com/status",
 "type": "http", "expected_status": [200, 204, 301]}
```

## Dashboard Features

- **Summary bar** — total targets, overall uptime %, average latency, data point count
- **Per-target cards** — donut gauge, uptime/latency stats, interactive Chart.js line graph
- **Combined uptime graph** — all targets overlaid with legend
- **Latency graph** — response time trends for all targets
- **Uptime heatmap** — GitHub-style hourly grid, colored green→red by health %
- **Log table** — last 100 checks with status badges and HTTP status codes
- **Time range selector** — 1H, 6H, 1D, 3D, 7D
- **Filters** — custom date/time range, target, and type (TCP/Ping/HTTP) dropdowns
- **Auto-refresh** — updates every 60 seconds

## Data Storage

Results are stored as daily CSV files in the `data/` directory:

```
data/
  2026-04-07.csv
  2026-04-08.csv
  ...
```

CSV columns: `timestamp, name, host, port, type, checks, successes, pct, avg_latency_ms, http_status`

Files older than `retention_days` are automatically deleted on each check run.

## Files

| File | Purpose |
|---|---|
| `config.json` | Configuration |
| `healthcheck.py` | Health check runner (measures uptime % and latency) |
| `dashboard.py` | Web dashboard server |
| `run.sh` | Convenience launcher |
| `data/*.csv` | Daily result files |
