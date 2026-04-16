import platform
import asyncio
import datetime
import aiohttp

HAS_WINRT = False
if platform.system() == "Windows":
    try:
        import winrt.windows.devices.geolocation as geolocation
        HAS_WINRT = True
    except ImportError:
        pass


async def _get_windows_location() -> dict | None:
    """Use Windows native geolocation (most accurate when available)"""
    if not HAS_WINRT:
        return None
    try:
        locator = geolocation.Geolocator()
        # Add timeout to prevent hanging
        pos = await asyncio.wait_for(locator.get_geoposition_async(), timeout=10.0)
        return {
            "latitude": pos.coordinate.point.position.latitude,
            "longitude": pos.coordinate.point.position.longitude,
            "accuracy": getattr(pos.coordinate, 'accuracy', None),
            "source": "windows-native"
        }
    except asyncio.TimeoutError:
        print("[location] Windows geolocation timeout")
        return None
    except Exception as e:
        print(f"[location] Windows geolocation failed: {e}")
        return None


async def _get_ip_location() -> dict | None:
    """Fallback: Get location from IP address"""
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=6)) as session:
            async with session.get("http://ip-api.com/json/") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("status") == "success":
                        return {
                            "latitude": data.get("lat"),
                            "longitude": data.get("lon"),
                            "city": data.get("city"),
                            "region": data.get("regionName"),
                            "country": data.get("country"),
                            "isp": data.get("isp"),
                            "accuracy": None,
                            "source": "ip-api"
                        }
    except Exception as e:
        print(f"[location] IP geolocation failed: {e}")
    return None


async def get_location_async() -> dict:
    """Main async location function"""
    loc_data = await _get_windows_location()
    
    if not loc_data:
        loc_data = await _get_ip_location()

    if loc_data and loc_data.get("latitude") is not None:
        return {
            "latitude": loc_data.get("latitude"),
            "longitude": loc_data.get("longitude"),
            "city": loc_data.get("city"),
            "region": loc_data.get("region"),
            "country": loc_data.get("country"),
            "isp": loc_data.get("isp"),
            "accuracy": loc_data.get("accuracy"),
            "source": loc_data.get("source"),
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
        }

    # Return empty but valid structure when location unavailable
    return {
        "latitude": None,
        "longitude": None,
        "city": None,
        "region": None,
        "country": None,
        "isp": None,
        "accuracy": None,
        "source": "unavailable",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
        "error": "location unavailable"
    }


# For standalone testing
def get_location() -> dict:
    return asyncio.run(get_location_async())


if __name__ == "__main__":
    import json
    print(json.dumps(get_location(), indent=2))
