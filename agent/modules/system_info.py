import os
import uuid
import platform
import subprocess
import psutil
from functools import lru_cache
import asyncio
import aiohttp


@lru_cache(maxsize=1)
def _get_mac_address() -> str:
    """Get MAC address once and cache it"""
    mac = uuid.getnode()
    return ':'.join(('%012X' % mac)[i:i+2] for i in range(0, 12, 2))


async def _get_public_ip() -> dict:
    """Async public IP fetch with timeout"""
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
            async with session.get("https://api4.ipify.org") as resp:
                if resp.status == 200:
                    ipv4 = (await resp.text()).strip()
                    return {"ipv4": ipv4, "ipv6": None}
    except Exception:
        pass
    return {"ipv4": None, "ipv6": None}


def _get_battery() -> dict:
    """Get battery information"""
    try:
        battery = psutil.sensors_battery()
        if battery:
            return {
                "percent": int(battery.percent),
                "charging": bool(battery.power_plugged),
                "time_left": battery.secsleft if battery.secsleft > 0 else None
            }
    except Exception:
        pass
    return {"percent": None, "charging": None, "time_left": None}


def _get_power_plan() -> str:
    """Get current Windows power plan"""
    try:
        result = subprocess.run(
            ["powercfg", "/getactivescheme"],
            capture_output=True,
            text=True,
            timeout=3
        )
        if "(" in result.stdout:
            return result.stdout.strip().split("(")[-1].rstrip(")").strip()
        return result.stdout.strip()
    except Exception:
        return "Unknown"


async def get_system_info() -> dict:
    """Main function - called from agent.py"""
    # Run blocking calls in thread to not block event loop
    loop = asyncio.get_running_loop()
    
    ips = await _get_public_ip()
    
    battery = await loop.run_in_executor(None, _get_battery)
    power_plan = await loop.run_in_executor(None, _get_power_plan)

    return {
        "username": os.getlogin(),
        "platform": platform.system(),
        "os_version": platform.version(),
        "mac_address": _get_mac_address(),
        "ipv4": ips["ipv4"],
        "ipv6": ips["ipv6"],
        "battery": battery,
        "power_plan": power_plan
    }
