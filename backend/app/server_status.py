import psutil
import time
from datetime import datetime

def get_server_status():
    """Returns a dictionary of system metrics."""
    try:
        # CPU
        cpu_percent = psutil.cpu_percent(interval=None)
        
        # RAM
        ram = psutil.virtual_memory()
        ram_total = ram.total / (1024**3)
        ram_used = ram.used / (1024**3)
        ram_percent = ram.percent
        
        # Disk (root)
        disk = psutil.disk_usage('/')
        disk_total = disk.total / (1024**3)
        disk_used = disk.used / (1024**3)
        disk_percent = disk.percent
        
        # Uptime
        boot_time = psutil.boot_time()
        uptime_seconds = time.time() - boot_time
        
        uptime_days = int(uptime_seconds // 86400)
        uptime_hours = int((uptime_seconds % 86400) // 3600)
        uptime_minutes = int((uptime_seconds % 3600) // 60)
        
        parts = []
        if uptime_days > 0:
            parts.append(f"{uptime_days}d")
        if uptime_hours > 0:
            parts.append(f"{uptime_hours}h")
        parts.append(f"{uptime_minutes}m")
        uptime_str = " ".join(parts)
        
        # Version
        try:
            from pathlib import Path
            # server_status.py is in backend/app/
            # VERSION is in root (backend/app/../../VERSION)
            root_dir = Path(__file__).resolve().parent.parent.parent
            version_file = root_dir / "VERSION"
            if version_file.exists():
                with open(version_file, "r") as f:
                    version = f.read().strip()
            else:
                version = "Unknown"
        except Exception:
            version = "Unknown"
            
        return {
            "ok": True,
            "version": version,
            "cpu_percent": cpu_percent,
            "ram": {
                "total_gb": round(ram_total, 2),
                "used_gb": round(ram_used, 2),
                "percent": ram_percent
            },
            "disk": {
                "total_gb": round(disk_total, 2),
                "used_gb": round(disk_used, 2),
                "percent": disk_percent
            },
            "uptime_seconds": int(uptime_seconds),
            "uptime_str": uptime_str,
            "boot_time": datetime.fromtimestamp(boot_time).strftime('%Y-%m-%d %H:%M:%S')
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}
