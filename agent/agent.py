import json
import os
import uuid
import platform
import asyncio
import logging
import websockets
import ssl
from typing import Optional

from modules.system_info import get_system_info
from modules.location import get_location_async
from modules.power_options import handle_command

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

CONFIG_FILE = "agent_config.json"

DEFAULTS = {
    "agent_name": "",
    "server": "ws://127.0.0.1:8000/ws",   # Change to wss:// when using HTTPS
    "password": "",
    "update_interval": 30,                 # Increased from 10s → better for battery & server load
    "schedules": {
        "shutdown": None,
        "restart": None
    }
}


def load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            config = json.load(f)
        if not config.get("agent_id"):
            config["agent_id"] = str(uuid.uuid4())
            save_config(config)
        return config

    config = DEFAULTS.copy()
    config["agent_id"] = str(uuid.uuid4())
    config["agent_name"] = platform.node()
    save_config(config)
    logger.info("[tracewire] agent_config.json created. Edit server and password before running.")
    return config


def save_config(config: dict):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


async def build_payload(config: dict) -> dict:
    try:
        return {
            "agent_id": config["agent_id"],
            "agent_name": config["agent_name"] or platform.node(),
            "password": config.get("password", ""),
            "system_info": await get_system_info(),
            "location": await get_location_async()
        }
    except Exception as e:
        logger.error(f"Failed to build payload: {e}")
        return {
            "agent_id": config["agent_id"],
            "agent_name": config["agent_name"] or platform.node(),
            "password": config.get("password", ""),
            "system_info": {},
            "location": {}
        }


async def run_agent():
    config = load_config()
    backoff = 5  # starting backoff in seconds

    while True:
        try:
            uri = config["server"]
            logger.info(f"Connecting to {uri}...")

            # Prepare SSL context for wss://
            ssl_context: Optional[ssl.SSLContext] = None
            if uri.startswith("wss://"):
                ssl_context = ssl.create_default_context()

            async with websockets.connect(
                uri,
                ssl=ssl_context,
                ping_interval=25,      # Keep connection alive
                ping_timeout=10,       # Timeout if no pong
                close_timeout=5
            ) as ws:
                backoff = 5  # Reset backoff on successful connection

                # Send initial payload
                payload = await build_payload(config)
                await ws.send(json.dumps(payload))
                logger.info(f"Registered successfully as {config['agent_id']}")

                # Background task to send periodic updates
                async def send_loop():
                    while True:
                        try:
                            await asyncio.sleep(config.get("update_interval", 30))
                            payload = await build_payload(config)
                            await ws.send(json.dumps(payload))
                        except websockets.exceptions.ConnectionClosed:
                            logger.warning("Connection closed during send")
                            break
                        except Exception as e:
                            logger.error(f"Error sending update: {e}")
                            break

                loop_task = asyncio.create_task(send_loop())

                # Main receive loop
                try:
                    async for message in ws:
                        try:
                            data = json.loads(message)
                            if data.get("type") == "control":
                                cmd = data.get("command")
                                logger.info(f"Received command: {cmd}")
                                await handle_command(data)
                            else:
                                logger.warning(f"Unknown message type: {data}")
                        except json.JSONDecodeError:
                            logger.error("Received invalid JSON message")
                        except Exception as e:
                            logger.error(f"Error handling message: {e}")

                finally:
                    loop_task.cancel()
                    try:
                        await loop_task
                    except asyncio.CancelledError:
                        pass

        except websockets.exceptions.InvalidStatusCode as e:
            if e.status_code == 401:
                logger.error("Authentication failed - Check password in agent_config.json")
            else:
                logger.error(f"Connection rejected: {e}")
        except Exception as e:
            logger.error(f"Connection error: {e}")

        # Exponential backoff before retrying
        logger.info(f"Reconnecting in {backoff} seconds...")
        await asyncio.sleep(backoff)
        backoff = min(backoff * 2, 300)  # Max 5 minutes


if __name__ == "__main__":
    try:
        asyncio.run(run_agent())
    except KeyboardInterrupt:
        logger.info("Agent stopped by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
