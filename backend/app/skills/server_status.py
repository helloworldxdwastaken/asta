from app.lib.skill import Skill
from typing import Any

class ServerStatusSkill(Skill):
    @property
    def name(self) -> str:
        return "server_status"

    def check_eligibility(self, text: str, user_id: str) -> bool:
        t = (text or "").strip().lower()
        if any(k in t for k in ("server status", "system stats", "cpu usage", "ram usage", "disk space", "uptime", "/status")):
            return True
        if t == "status":
            return True
        return False

    async def execute(self, user_id: str, text: str, extra: dict[str, Any]) -> dict[str, Any]:
        import asyncio
        from app.server_status import get_server_status
        # get_server_status is sync; run in executor to avoid blocking
        return {"server_status": await asyncio.to_thread(get_server_status)}

    async def get_context_section(self, db, user_id: str, extra: dict[str, Any]) -> str | None:
        if extra and extra.get("server_status"):
            ss = extra["server_status"]
            parts = []
            if ss.get("ok"):
                parts.append("--- Server Status (REAL-TIME METRICS) ---")
                parts.append(f"CPU Usage: {ss['cpu_percent']}%")
                parts.append(f"RAM Usage: {ss['ram']['percent']}% ({ss['ram']['used_gb']}GB / {ss['ram']['total_gb']}GB)")
                parts.append(f"Disk Usage: {ss['disk']['percent']}% ({ss['disk']['used_gb']}GB / {ss['disk']['total_gb']}GB)")
                parts.append(f"System Uptime: {ss['uptime_str']}")
                parts.append(f"Asta Version: {ss.get('version', 'Unknown')}")
                parts.append("Use these exact values to answer 'server status' or 'system stats' questions. Do NOT say you cannot check.")
            else:
                parts.append("--- Server Status ---")
                parts.append(f"Status check failed: {ss.get('error')}")
            return "\n".join(parts) + "\n"
        return None
