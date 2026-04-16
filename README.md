I've updated the README to reflect your notes. The "Expose Publicly" section has been removed entirely. The default server password is now shown as `admin` (users are still warned to change it). A clear disclaimer about pre‑release status and educational use has been added.

```markdown
<div align="center">

![header](https://capsule-render.vercel.app/api?type=waving&height=300&text=TraceWire&textBg=false&fontColor=ffff&fontAlignY=42)

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![WebSocket](https://img.shields.io/badge/WebSockets-Realtime-010101?style=for-the-badge&logo=websocket&logoColor=white)
![Status](https://img.shields.io/badge/Status-Pre--release-FFA500?style=for-the-badge)

</div>

---

## `$ Overview`

**TraceWire** is a cross‑platform device tracking and remote management framework built for **real‑time telemetry** and **secure command execution**. A lightweight Python agent pushes system info and geolocation over WebSockets to a central FastAPI server, while the server can issue instant power commands (shutdown, lock, sleep, etc.) and schedule future actions.

The system is ideal for:
- Monitoring fleets of laptops or workstations
- Remote IT support and asset recovery
- Building custom location‑aware automation

> **⚠️ IMPORTANT**  
> This is a **pre‑release version**. It currently supports only unencrypted `ws://` connections (`wss://` is not yet implemented).  
> TraceWire includes full location tracking and remote control capabilities – **use only on devices you own or have explicit permission to monitor**.  
> The project is intended for **educational purposes and authorized internal network monitoring**.

---

## `$ Screenshots`

*(Add screenshots of the admin panel dashboard, agent list, or location map here once deployed)*

---

## `$ Tree Overview`

```
tracewire/
├── agent/
│   ├── modules/
│   │   ├── location.py          # Windows native + IP‑based geolocation
│   │   ├── power_options.py     # OS power commands & scheduling
│   │   └── system_info.py       # Hardware, battery, and public IP telemetry
│   ├── agent.py                 # WebSocket client core
│   └── agent_config.json        # Client configuration (server URL, password, interval)
├── server/
│   ├── devices/                 # Persistent JSON storage per agent
│   ├── modules/
│   │   └── location_history.py  # Smart breadcrumb recording with interval/throttle
│   ├── admin_panel/             # Static HTML dashboard
│   ├── server.py                # FastAPI app + WebSocket endpoint
│   └── server_config.json       # Server settings (auth, port, max history)
└── README.md
```

---

## `$ Features`

| Module / Component | Description |
|-------------------|-------------|
| **Real‑time Telemetry** | Agents send system info (OS, battery, IP, MAC) and location on a configurable interval. |
| **Bi‑directional WebSocket** | Server pushes commands instantly to connected agents – no polling needed. |
| **Persistent State** | Each agent’s data is saved to `devices/<agent_id>.json` and survives server restarts. |
| **Location Breadcrumbs** | Records location changes only after a minimum time interval (`location_history_interval`) to avoid bloat. History is capped at `max_location_history`. |
| **Secure Authentication** | Agent handshake includes a password; all REST endpoints require an `X-Password` header. |
| **Power Control Suite** | Immediate shutdown, restart, sleep, hibernate, lock, plus **scheduled** actions at precise ISO timestamps. |
| **Cross‑Platform Agent** | Windows native geolocation (WinRT) with IP‑based fallback. Linux/macOS can use IP‑only out‑of‑the‑box. |
| **Admin Dashboard** | Static HTML panel served at `/admin` – view agents, location history, and send commands. |

---

## `$ API Reference` (All require `X-Password` header)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET`  | `/` | Redirects to `/admin/index.html` |
| `GET`  | `/agents` | List all registered agents with online/offline status |
| `GET`  | `/agents/{id}/info` | Basic registration and last‑seen info |
| `GET`  | `/agents/{id}/list` | Full stored device JSON (includes location history) |
| `GET`  | `/agents/{id}/location` | Current latitude, longitude, and timestamp |
| `GET`  | `/agents/{id}/location/history` | Historical breadcrumbs, optionally `?limit=N` |
| `GET`  | `/agents/{id}/system_info` | Hardware, battery, OS, and network telemetry |
| `DELETE` | `/agents/{id}` | Unregister agent and delete its JSON file |
| `POST` | `/agents/{id}/power_options/shutdown` | Shutdown with optional `?delay_seconds` |
| `POST` | `/agents/{id}/power_options/restart` | Restart with optional `?delay_seconds` |
| `POST` | `/agents/{id}/power_options/sleep` | Put the machine to sleep |
| `POST` | `/agents/{id}/power_options/hibernate` | Hibernate the machine |
| `POST` | `/agents/{id}/power_options/lock` | Lock the workstation |
| `POST` | `/agents/{id}/power_options/schedule_shutdown` | Schedule shutdown – body: `{"at": "ISO-8601"}` |
| `POST` | `/agents/{id}/power_options/schedule_restart` | Schedule restart – body: `{"at": "ISO-8601"}` |
| `POST` | `/agents/{id}/power_options/cancel_schedule` | Cancel any pending scheduled action |

---

## `$ Installation`

```bash
git clone https://github.com/yourusername/tracewire.git
cd tracewire

# Server dependencies
pip install fastapi uvicorn websockets aiohttp psutil

# Agent dependencies (run on each monitored device)
pip install websockets aiohttp psutil
# On Windows only: pip install winrt  (for native geolocation)
```

---

## `$ Usage`

### **1. Configure and Start the Server**

Edit `server/server_config.json`:
```json
{
  "host": "0.0.0.0",
  "port": 8000,
  "password": "admin",                // ← CHANGE THIS immediately!
  "max_location_history": 500,
  "location_history_interval": 60
}
```

Launch the server:
```bash
cd server
python server.py
```

The admin panel will be available at `http://your-server-ip:8000/admin`.

---

### **2. Deploy the Agent**

Edit `agent/agent_config.json` on each device:
```json
{
  "agent_name": "My-Laptop",
  "server": "ws://your-server-ip:8000/ws",
  "password": "admin",                // Must match server password
  "update_interval": 30
}
```

Run the agent:
```bash
cd agent
python agent.py
```

The agent will connect automatically, send its telemetry, and await commands.

---

## `$ Configuration Deep Dive`

| File | Key Option | Purpose |
|------|------------|---------|
| `server_config.json` | `max_location_history` | Maximum number of location records stored per agent. |
| | `location_history_interval` | Minimum seconds between location appends. |
| `agent_config.json` | `update_interval` | How often (seconds) the agent pushes new data. |
| | `server` | WebSocket URL (`ws://` only in this release). |
| `index.html` (admin) | (static) | Modify the admin panel to match your branding. |

---

## `$ Agent Telemetry Payload (Example)`

```json
{
  "agent_id": "aa0fcd64-5ad7-4651-870d-9992ee593416",
  "agent_name": "DESKTOP-HRIQ9LH",
  "password": "admin",
  "system_info": {
    "username": "User",
    "platform": "Windows",
    "os_version": "10.0.22631",
    "mac_address": "00:1A:2B:3C:4D:5E",
    "ipv4": "203.0.113.45",
    "battery": { "percent": 87, "charging": true, "time_left": null },
    "power_plan": "Balanced"
  },
  "location": {
    "latitude": 40.7128,
    "longitude": -74.0060,
    "city": "New York",
    "region": "NY",
    "country": "United States",
    "accuracy": 50,
    "source": "ip-api",
    "timestamp": "2025-03-15T14:32:00Z"
  }
}
```

---

## `$ Database Structure`

Agent data is stored as JSON files under `server/devices/`:

```
devices/
└── aa0fcd64-5ad7-4651-870d-9992ee593416.json
```

Each file contains:
- Agent metadata (`agent_id`, `agent_name`, `agent_device_name`)
- Current status (`last_seen`, `lat`, `lon`)
- Full `system_info` snapshot
- Pending command flags (`modules.lock`, `modules.shutdown`, etc.)
- **`location_history`** array with timestamp, coordinates, and a Google Maps link.

---

## `$ License`

MIT — Free for personal, educational, and commercial use.

<div align="center">

![footer](https://capsule-render.vercel.app/api?type=waving&color=gradient&customColorList=12,20,24&height=100&section=footer)

</div>
```
