import subprocess
import asyncio
import datetime
from typing import Optional

# Global reference for scheduled task
_scheduled_task: Optional[asyncio.Task] = None


async def handle_command(command: dict):
    """
    Async handler for power commands
    Called from agent.py
    """
    global _scheduled_task

    cmd = command.get("command")
    delay = command.get("delay_seconds", 0)
    at = command.get("at")

    try:
        if cmd == "shutdown":
            subprocess.run(["shutdown", "/s", "/t", str(delay)], check=True)

        elif cmd == "restart":
            subprocess.run(["shutdown", "/r", "/t", str(delay)], check=True)

        elif cmd == "sleep":
            subprocess.run(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"], check=True)

        elif cmd == "hibernate":
            subprocess.run(["shutdown", "/h"], check=True)

        elif cmd == "lock":
            subprocess.run(["rundll32.exe", "user32.dll,LockWorkStation"], check=True)

        elif cmd in ("schedule_shutdown", "schedule_restart"):
            if at:
                # Cancel any existing scheduled task
                if _scheduled_task and not _scheduled_task.done():
                    _scheduled_task.cancel()

                _scheduled_task = asyncio.create_task(_run_scheduled(cmd, at))

        elif cmd == "cancel_schedule":
            if _scheduled_task and not _scheduled_task.done():
                _scheduled_task.cancel()
                _scheduled_task = None

    except subprocess.CalledProcessError as e:
        print(f"[power_options] Command failed: {cmd} - {e}")
    except Exception as e:
        print(f"[power_options] Error executing {cmd}: {e}")


async def _run_scheduled(cmd: str, at: str):
    """Run scheduled shutdown/restart at specific time"""
    try:
        # Handle both with and without Z suffix
        if at.endswith('Z'):
            target = datetime.datetime.fromisoformat(at.replace('Z', '+00:00'))
        else:
            target = datetime.datetime.fromisoformat(at)

        now = datetime.datetime.now(datetime.timezone.utc)
        delay = (target - now).total_seconds()

        if delay > 0:
            print(f"[power_options] Scheduled {cmd} in {delay:.0f} seconds")
            await asyncio.sleep(delay)

        # Execute the command
        if cmd == "schedule_shutdown":
            subprocess.run(["shutdown", "/s", "/t", "0"], check=True)
        elif cmd == "schedule_restart":
            subprocess.run(["shutdown", "/r", "/t", "0"], check=True)

        print(f"[power_options] Executed scheduled {cmd}")

    except asyncio.CancelledError:
        print(f"[power_options] Scheduled {cmd} cancelled")
    except Exception as e:
        print(f"[power_options] Scheduled task error: {e}")
