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
> This is a **pre‑release version**. It currently supports only unencrypted `ws://` connections (`wss://` is not yet implemented). Therefore, it is **not recommended for production use** over the open internet.  
> TraceWire includes full location tracking and remote control capabilities – **use only on devices you own or have explicit permission to monitor**.  
> The project is intended for **educational purposes and authorized internal network monitoring**.

---

## `$ Screenshots`

<div align="center">
  
### `$ Admin Panel`
![Admin Panel](https://github.com/iNarrow12/Tracewire/blob/main/src/image.png)
### `$ Devices in Admin Panel`
![Devices in Admin Panel](https://github.com/iNarrow12/Tracewire/blob/main/src/admin_panle.png)
### `$ Docs`
![Docs](https://github.com/iNarrow12/Tracewire/blob/main/src/docs-nomal.png)

</div>

---

## `$ Tree Overview`

```
tracewire/
├── agent/
│   ├── modules/
│   │   ├── location.py          # Windows native (WinRT) + IP‑based geolocation
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
| **Location Breadcrumbs** | Records location changes only after a minimum time interval (`location_history_interval`) to avoid bloat. History is capped at `max_location_history`. On Windows, it uses the **native Geolocation API** for higher accuracy; falls back to IP geolocation otherwise. |
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

### **Server Dependencies**

```bash
pip install fastapi uvicorn pydantic websockets aiohttp psutil
```

### **Agent Dependencies** (run on each monitored device)

```bash
pip install websockets aiohttp psutil
```

> **Windows only**: For native GPS accuracy, install the WinRT bindings:
> ```bash
> pip install winrt
> ```

### **Clone the Repository**

```bash
git clone https://github.com/yourusername/tracewire.git
cd tracewire
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

## `$ Data Format (Server‑Side Storage)`

Each agent’s data is stored as a JSON file inside `server/devices/`. Below is an example (with **fake, randomized values**) showing the actual structure saved by the server:

```json
{
  "agent_id": "3f7e9a2b-8c1d-4e5f-9a6b-7c8d9e0f1a2b",
  "agent_name": "DESKTOP-ABC123",
  "agent_device_name": "DESKTOP-ABC123",
  "agent_status": {
    "last_seen": "2026-04-16T10:15:30.123456Z",
    "lat": 40.7128,
    "lon": -74.0060
  },
  "system_info": {
    "username": "johndoe",
    "platform": "Windows",
    "os_version": "10.0.22631",
    "mac_address": "00:1A:2B:3C:4D:5E",
    "ipv4": "192.0.2.123",
    "ipv6": "2351:3769:b6c4:7759e:678h:865k:hf6k:6584",
    "battery": {
      "percent": 85,
      "charging": false,
      "time_left": 7200
    },
    "power_plan": "Balanced"
  },
  "modules": {
    "lock": false,
    "restart": false,
    "shutdown": false,
    "sleep": false,
    "hibernate": false,
    "schedule_shutdown": null,
    "schedule_restart": null,
    "cancel_schedule": false
  },
  "location_history": [
    {
      "timestamp": "2026-04-16T10:14:00.000001Z",
      "lat": 40.7127,
      "lon": -74.0059,
      "map": "https://maps.google.com/?q=40.7127,-74.0059"
    },
    {
      "timestamp": "2026-04-16T10:15:00.000002Z",
      "lat": 40.7128,
      "lon": -74.0060,
      "map": "https://maps.google.com/?q=40.7128,-74.0060"
    }
  ]
}
```

**Key points:**
- `agent_status` holds the **latest** location and last‑seen timestamp.
- `location_history` is a rolling buffer of location records, each including a Google Maps link.
- `modules` contains pending command flags – these are cleared automatically after the command is sent to the agent.

---

## `$ License`

MIT — Free for personal, educational, and commercial use.

<div align="center">

![footer](https://capsule-render.vercel.app/api?type=waving&color=gradient&customColorList=12,20,24&height=100&section=footer)

</div>
