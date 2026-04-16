import datetime


def should_append(history: list, lat: float, lon: float, interval_seconds: int) -> bool:
    if not history:
        return True

    last = history[-1]

    # don't append if not enough time has passed
    try:
        # Python 3.11+ handles 'Z' suffix correctly
        last_time = datetime.datetime.fromisoformat(last["timestamp"])
        now = datetime.datetime.now(datetime.UTC)
        if (now - last_time).total_seconds() < interval_seconds:
            return False
    except Exception:
        pass

    return True


def append_location(history: list, lat: float, lon: float, max_history: int, interval_seconds: int) -> list:
    if not should_append(history, lat, lon, interval_seconds):
        return history

    now = datetime.datetime.now(datetime.UTC).isoformat().replace("+00:00", "Z")
    history.append({
        "timestamp": now,
        "lat": lat,
        "lon": lon,
        "map": f"https://maps.google.com/?q={lat},{lon}"
    })

    # trim to max
    if len(history) > max_history:
        history = history[-max_history:]

    return history
