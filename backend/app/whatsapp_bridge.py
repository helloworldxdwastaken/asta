"""Helpers for WhatsApp bridge runtime status (single-user)."""

from __future__ import annotations

import httpx


def _base_status(bridge_url: str | None) -> dict:
    base = (bridge_url or "").strip().rstrip("/")
    configured = bool(base)
    return {
        "configured": configured,
        "bridge_url": base if configured else None,
        "reachable": False,
        "connected": False,
        "connecting": False,
        "has_qr": False,
        "state": "not_configured" if not configured else "unreachable",
        "reconnect_attempts": None,
        "owner_jid": None,
        "last_connected_at": None,
        "last_disconnect": None,
        "uptime_sec": None,
        "error": None,
    }


async def get_whatsapp_bridge_status(bridge_url: str | None, timeout_s: float = 4.0) -> dict:
    """Return normalized bridge status for UI/CLI.

    Single-user model only: one bridge URL, one runtime state.
    """
    status = _base_status(bridge_url)
    base = status["bridge_url"]
    if not base:
        status["error"] = (
            "Bridge URL not set. Add ASTA_WHATSAPP_BRIDGE_URL in backend/.env "
            "(e.g. http://localhost:3001)."
        )
        return status

    try:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            response = await client.get(f"{base}/status")
            if response.status_code != 200:
                status["error"] = f"Bridge returned HTTP {response.status_code}"
                return status

            payload = response.json() if response.content else {}
            if not isinstance(payload, dict):
                status["error"] = "Bridge returned invalid status payload"
                return status

            status["reachable"] = True
            status["connected"] = bool(payload.get("connected"))
            status["connecting"] = bool(payload.get("connecting"))
            status["has_qr"] = bool(payload.get("has_qr"))
            raw_state = str(payload.get("state") or "").strip()
            if raw_state:
                status["state"] = raw_state
            elif status["connected"]:
                status["state"] = "connected"
            elif status["has_qr"]:
                status["state"] = "awaiting_qr"
            elif status["connecting"]:
                status["state"] = "connecting"
            else:
                status["state"] = "disconnected"
            status["reconnect_attempts"] = payload.get("reconnect_attempts")
            status["owner_jid"] = payload.get("owner_jid")
            status["last_connected_at"] = payload.get("last_connected_at")
            status["last_disconnect"] = payload.get("last_disconnect")
            status["uptime_sec"] = payload.get("uptime_sec")
            return status
    except Exception:
        status["error"] = f"Cannot reach bridge at {base}. Start it with: cd services/whatsapp && npm run start"
        return status
