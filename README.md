# webapp

A Flask + Dash web application for collecting, storing, and visualising metrics from remote devices. Devices push metrics over HTTP and maintain a persistent WebSocket connection for real-time control commands.

## Features

- **Live dashboard** — Plotly Dash UI with gauges, line charts, and text cards, auto-refreshing every 3 seconds
- **REST API** — authenticated endpoints to ingest metrics and query the latest readings
- **WebSocket control hub** — send commands (`pause`, `resume`, `restart`, `set_interval`) to connected devices in real time
- **SQLite storage** — normalised schema (sources → metric definitions → metric values) via SQLAlchemy ORM
- **nginx reverse proxy** — TLS termination, security headers, and static file blocking

## Architecture

```
Browser
  └── nginx (TLS :5025)
        ├── /            → Flask/Dash  (:8000)
        └── /ws          → WebSocket control hub (:8765)

Remote agents
  ├── POST /api/metrics  → ingest metrics
  └── ws://.../ws        → register & receive commands
```

## Project structure

```
webapp/
├── main.py              # App entry point
├── routes.py            # REST API blueprints
├── dashboard.py         # Dash UI and callbacks
├── dashboard_utils.py   # Chart builders
├── ingestion.py         # Metric parsing and DB insertion
├── database.py          # SQLAlchemy engine and session
├── models.py            # ORM models (Source, MetricDefinition, MetricValue)
├── control_ws.py        # WebSocket control hub (ControlHub)
├── config/
│   ├── config.py        # Logging setup and theme constants
│   └── config.json      # Configuration file
├── nginx/
│   └── webapp.conf      # nginx site config
├── requirements.txt
├── .env                 # Local environment variables (not committed)
└── .env.example         # Template for required environment variables
```

## Setup

**Prerequisites:** Python 3.12+, pip, nginx

```bash
git clone <repo-url>
cd webapp
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env with your values
```

## Configuration

Copy `.env.example` to `.env` and fill in the values:

| Variable | Default | Description |
|---|---|---|
| `HOST` | `localhost` | Flask bind address |
| `PORT` | `8000` | Flask bind port |
| `FLASK_DEBUG` | `false` | Enable Flask debug mode |
| `API_KEY` | — | Secret key for `X-API-Key` header authentication |
| `WS_CONTROL_HOST` | `127.0.0.1` | WebSocket server bind address |
| `WS_CONTROL_PORT` | `8765` | WebSocket server port |
| `WS_CONTROL_TOKEN` | — | **Required.** Token devices must present on registration |
| `DATABASE_URL` | `sqlite:///metrics.db` | SQLAlchemy database URL |

## Running

```bash
source venv/bin/activate
gunicorn -w 1 -b 0.0.0.0:8000 main:app
```

> Use a single worker (`-w 1`) — the WebSocket hub runs in a background thread tied to the process.

## API

All endpoints require the `X-API-Key` header.

### Ingest metrics

```
POST /api/metrics
```

**Body:**
```json
{
  "metrics": [
    {
      "device_id": "my-device",
      "collector_type": "system",
      "name": "cpu.usage",
      "value": 42.5,
      "unit": "%",
      "timestamp": "2024-01-01T12:00:00"
    }
  ]
}
```

**Response:**
```json
{ "status": "success", "inserted": 1 }
```

### Get latest metrics (JSON)

```
GET /metrics/latest/json
```

### Get latest metrics (text)

```
GET /metrics/latest/text
```

### Status

```
GET /api/status
```

## WebSocket control protocol

Devices connect to `wss://<host>/ws` and register first:

```json
{ "type": "register", "device_id": "my-device", "token": "<WS_CONTROL_TOKEN>" }
```

The server responds:
```json
{ "type": "registered", "device_id": "my-device" }
```

The server then sends commands:
```json
{ "type": "command", "request_id": "<uuid>", "command": "pause", "payload": {} }
```

Devices must acknowledge:
```json
{ "type": "ack", "request_id": "<uuid>", "ok": true, "message": "paused" }
```

**Supported commands:** `pause`, `resume`, `restart`, `set_interval` (payload: `{"upload_interval_seconds": <int>}`)

## nginx

Copy `nginx/webapp.conf` to `/etc/nginx/sites-available/` and symlink it. The config expects TLS certificates at `/etc/nginx/ssl/webapp.crt` and `/etc/nginx/ssl/webapp.key`.

```bash
sudo ln -s /etc/nginx/sites-available/webapp.conf /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```
