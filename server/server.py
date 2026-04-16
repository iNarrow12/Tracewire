import json
import os
import datetime
import logging
from typing import Dict, Optional
from asyncio import Lock

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Header
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from modules.location_history import append_location

# --- Logging ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# --- CONFIG ---
CONFIG_FILE = "server_config.json"
DEVICES_DIR = "devices"
os.makedirs(DEVICES_DIR, exist_ok=True)


def load_server_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    default = {
        "host": "0.0.0.0",
        "port": 8000,
        "password": "ChangeThisToAStrongPassword123!",   # ← CHANGE THIS!
        "max_location_history": 500,
        "location_history_interval": 60
    }
    with open(CONFIG_FILE, "w") as f:
        json.dump(default, f, indent=2)
    return default


server_config = load_server_config()

# Per-device lock to prevent file corruption
device_locks: Dict[str, Lock] = {}


# --- PASSWORD CHECK ---
def check_password(x_password: Optional[str] = Header(None)):
    if not server_config.get("password"):
        return
    if x_password != server_config["password"]:
        raise HTTPException(
            status_code=401,
            detail="Unauthorized - Invalid or missing X-Password header"
        )


# --- APP ---
class PrettyJSONResponse(JSONResponse):
    def render(self, content) -> bytes:
        return json.dumps(content, indent=2).encode("utf-8")


app = FastAPI(title="TraceWire Control Center", default_response_class=PrettyJSONResponse)

connections: Dict[str, WebSocket] = {}


# --- HELPERS ---
def device_path(agent_id: str) -> str:
    return os.path.join(DEVICES_DIR, f"{agent_id}.json")


def load_device(agent_id: str) -> dict:
    path = device_path(agent_id)
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return None


def save_device(data: dict):
    path = device_path(data["agent_id"])
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def new_device(agent_id: str, agent_name: str, agent_device_name: str) -> dict:
    return {
        "agent_id": agent_id,
        "agent_name": agent_name,
        "agent_device_name": agent_device_name,
        "agent_status": {
            "last_seen": None,
            "lat": None,
            "lon": None
        },
        "system_info": {},
        "modules": {
            "lock": False,
            "restart": False,
            "shutdown": False,
            "sleep": False,
            "hibernate": False,
            "schedule_shutdown": None,
            "schedule_restart": None,
            "cancel_schedule": False
        },
        "location_history": []
    }


async def update_device(agent_id: str, payload: dict):
    """Async version with locking"""
    if agent_id not in device_locks:
        device_locks[agent_id] = Lock()

    async with device_locks[agent_id]:
        device_name = payload.get("system_info", {}).get("agent_name") or payload.get("agent_name", "")
        hostname = payload.get("agent_name", "")

        device = load_device(agent_id) or new_device(agent_id, device_name, hostname)

        now = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
        
        location = payload.get("location", {})
        lat = location.get("latitude") or location.get("lat")
        lon = location.get("longitude") or location.get("lon")

        # Basic validation
        if lat is not None and (not isinstance(lat, (int, float)) or not -90 <= lat <= 90):
            lat = None
        if lon is not None and (not isinstance(lon, (int, float)) or not -180 <= lon <= 180):
            lon = None

        device["agent_name"] = payload.get("agent_name", device["agent_name"])
        device["agent_device_name"] = hostname
        device["agent_status"]["last_seen"] = now
        device["agent_status"]["lat"] = lat
        device["agent_status"]["lon"] = lon

        device["agent_status"].pop("map", None)
        device["system_info"] = payload.get("system_info", {})

        if lat is not None and lon is not None:
            device["location_history"] = append_location(
                device["location_history"],
                lat, lon,
                server_config["max_location_history"],
                server_config["location_history_interval"]
            )

        save_device(device)
        return device


def get_device_or_404(agent_id: str) -> dict:
    device = load_device(agent_id)
    if not device:
        raise HTTPException(status_code=404, detail="Agent not found")
    return device


async def send_command(agent_id: str, command: dict):
    if agent_id not in connections:
        raise HTTPException(status_code=404, detail="Agent not connected")
    try:
        await connections[agent_id].send_json(command)
        
        # Clear flags safely
        if agent_id in device_locks:
            async with device_locks[agent_id]:
                device = load_device(agent_id)
                if device:
                    for flag in ["lock", "restart", "shutdown", "sleep", "hibernate", "cancel_schedule"]:
                        device["modules"][flag] = False
                    save_device(device)
        
        return {"status": "success", "command": command.get("command")}
    except Exception as e:
        logger.error(f"Failed to send command to {agent_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to send command: {e}")


# --- MODELS ---
class SchedulePayload(BaseModel):
    at: str


# --- WEBSOCKET ---
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    agent_id = None

    try:
        data = await websocket.receive_json()
        agent_id = data.get("agent_id")

        if not agent_id:
            await websocket.close(code=1008)
            return

        if server_config.get("password"):
            if data.get("password") != server_config["password"]:
                await websocket.close(code=1008)
                logger.warning(f"Rejected agent {agent_id}: wrong password")
                return

        connections[agent_id] = websocket
        await update_device(agent_id, data)
        logger.info(f"Agent connected: {agent_id}")

        while True:
            data = await websocket.receive_json()
            if data.get("agent_id"):
                await update_device(agent_id, data)

    except WebSocketDisconnect:
        logger.info(f"Agent disconnected: {agent_id}")
    except Exception as e:
        logger.error(f"WebSocket error for {agent_id}: {e}")
    finally:
        if agent_id and agent_id in connections:
            del connections[agent_id]


# --- ROUTES ---
@app.get("/")
async def root():
    return RedirectResponse(url="/admin/index.html")


@app.get("/agents")
async def list_agents(x_password: Optional[str] = Header(None)):
    check_password(x_password)
    agents = []
    if os.path.exists(DEVICES_DIR):
        for f in os.listdir(DEVICES_DIR):
            if f.endswith(".json"):
                with open(os.path.join(DEVICES_DIR, f)) as fp:
                    d = json.load(fp)
                agents.append({
                    "agent_id": d["agent_id"],
                    "agent_name": d["agent_name"],
                    "agent_device_name": d.get("agent_device_name"),
                    "last_seen": d["agent_status"]["last_seen"],
                    "status": "online" if d["agent_id"] in connections else "offline"
                })
    return agents


@app.get("/agents/{agent_id}/info")
async def get_agent_info(agent_id: str, x_password: Optional[str] = Header(None)):
    check_password(x_password)
    d = get_device_or_404(agent_id)
    return {
        "agent_id": d["agent_id"],
        "agent_name": d["agent_name"],
        "agent_device_name": d.get("agent_device_name"),
        "last_seen": d["agent_status"]["last_seen"],
        "status": "online" if agent_id in connections else "offline"
    }


@app.get("/agents/{agent_id}/list")
async def get_full_data(agent_id: str, x_password: Optional[str] = Header(None)):
    check_password(x_password)
    return get_device_or_404(agent_id)


@app.get("/agents/{agent_id}/location")
async def get_location(agent_id: str, x_password: Optional[str] = Header(None)):
    check_password(x_password)
    d = get_device_or_404(agent_id)
    return d["agent_status"]


@app.get("/agents/{agent_id}/location/history")
async def get_location_history(agent_id: str, limit: Optional[int] = None, x_password: Optional[str] = Header(None)):
    check_password(x_password)
    d = get_device_or_404(agent_id)
    history = d["location_history"]
    if limit:
        history = history[-limit:]
    return history


@app.get("/agents/{agent_id}/system_info")
async def get_system_info(agent_id: str, x_password: Optional[str] = Header(None)):
    check_password(x_password)
    d = get_device_or_404(agent_id)
    return d["system_info"]


@app.get("/agents/{agent_id}/power_options")
async def get_power_options(agent_id: str, x_password: Optional[str] = Header(None)):
    check_password(x_password)
    d = get_device_or_404(agent_id)
    return {
        "battery": d["system_info"].get("battery"),
        "power_plan": d["system_info"].get("power_plan"),
        "schedules": {
            "shutdown": d["modules"]["schedule_shutdown"],
            "restart": d["modules"]["schedule_restart"]
        }
    }


@app.delete("/agents/{agent_id}")
async def remove_agent(agent_id: str, x_password: Optional[str] = Header(None)):
    check_password(x_password)
    path = device_path(agent_id)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Agent not found")
    os.remove(path)
    if agent_id in connections:
        await connections[agent_id].close()
        del connections[agent_id]
    return {"status": "removed", "agent_id": agent_id}


# Power control routes
@app.post("/agents/{agent_id}/power_options/shutdown")
async def shutdown(agent_id: str, delay_seconds: int = 0, x_password: Optional[str] = Header(None)):
    check_password(x_password)
    d = get_device_or_404(agent_id)
    d["modules"]["shutdown"] = True
    save_device(d)
    return await send_command(agent_id, {"type": "control", "command": "shutdown", "delay_seconds": delay_seconds})


@app.post("/agents/{agent_id}/power_options/restart")
async def restart(agent_id: str, delay_seconds: int = 0, x_password: Optional[str] = Header(None)):
    check_password(x_password)
    d = get_device_or_404(agent_id)
    d["modules"]["restart"] = True
    save_device(d)
    return await send_command(agent_id, {"type": "control", "command": "restart", "delay_seconds": delay_seconds})


@app.post("/agents/{agent_id}/power_options/sleep")
async def sleep(agent_id: str, x_password: Optional[str] = Header(None)):
    check_password(x_password)
    d = get_device_or_404(agent_id)
    d["modules"]["sleep"] = True
    save_device(d)
    return await send_command(agent_id, {"type": "control", "command": "sleep"})


@app.post("/agents/{agent_id}/power_options/hibernate")
async def hibernate(agent_id: str, x_password: Optional[str] = Header(None)):
    check_password(x_password)
    d = get_device_or_404(agent_id)
    d["modules"]["hibernate"] = True
    save_device(d)
    return await send_command(agent_id, {"type": "control", "command": "hibernate"})


@app.post("/agents/{agent_id}/power_options/lock")
async def lock(agent_id: str, x_password: Optional[str] = Header(None)):
    check_password(x_password)
    d = get_device_or_404(agent_id)
    d["modules"]["lock"] = True
    save_device(d)
    return await send_command(agent_id, {"type": "control", "command": "lock"})


@app.post("/agents/{agent_id}/power_options/schedule_shutdown")
async def schedule_shutdown(agent_id: str, payload: SchedulePayload, x_password: Optional[str] = Header(None)):
    check_password(x_password)
    d = get_device_or_404(agent_id)
    d["modules"]["schedule_shutdown"] = payload.at
    save_device(d)
    return await send_command(agent_id, {"type": "control", "command": "schedule_shutdown", "at": payload.at})


@app.post("/agents/{agent_id}/power_options/schedule_restart")
async def schedule_restart(agent_id: str, payload: SchedulePayload, x_password: Optional[str] = Header(None)):
    check_password(x_password)
    d = get_device_or_404(agent_id)
    d["modules"]["schedule_restart"] = payload.at
    save_device(d)
    return await send_command(agent_id, {"type": "control", "command": "schedule_restart", "at": payload.at})


@app.post("/agents/{agent_id}/power_options/cancel_schedule")
async def cancel_schedule(agent_id: str, x_password: Optional[str] = Header(None)):
    check_password(x_password)
    d = get_device_or_404(agent_id)
    d["modules"]["schedule_shutdown"] = None
    d["modules"]["schedule_restart"] = None
    d["modules"]["cancel_schedule"] = True
    save_device(d)
    return await send_command(agent_id, {"type": "control", "command": "cancel_schedule"})


# --- STATIC FILES ---
ADMIN_DIR = os.path.join(os.path.dirname(__file__), "admin_panel")
if os.path.exists(ADMIN_DIR):
    app.mount("/admin", StaticFiles(directory=ADMIN_DIR, html=True), name="admin")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=server_config["host"],
        port=server_config["port"],
        log_level="info"
    )
