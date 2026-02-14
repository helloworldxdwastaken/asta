import asyncio

from app.whatsapp_bridge import get_whatsapp_bridge_status


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload
        self.content = b"1"

    def json(self):
        return self._payload


class _FakeClient:
    def __init__(self, responses=None, raise_exc: Exception | None = None, **_kwargs):
        self._responses = responses or {}
        self._raise_exc = raise_exc

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url: str):
        if self._raise_exc:
            raise self._raise_exc
        return self._responses[url]


def test_whatsapp_bridge_status_not_configured():
    out = asyncio.run(get_whatsapp_bridge_status(""))
    assert out["configured"] is False
    assert out["state"] == "not_configured"
    assert out["reachable"] is False


def test_whatsapp_bridge_status_connected(monkeypatch):
    def _client_factory(*_args, **_kwargs):
        return _FakeClient(
            responses={
                "http://localhost:3001/status": _FakeResponse(
                    200,
                    {
                        "connected": True,
                        "connecting": False,
                        "has_qr": False,
                        "state": "connected",
                        "reconnect_attempts": 0,
                    },
                )
            }
        )

    monkeypatch.setattr("app.whatsapp_bridge.httpx.AsyncClient", _client_factory)
    out = asyncio.run(get_whatsapp_bridge_status("http://localhost:3001"))
    assert out["configured"] is True
    assert out["reachable"] is True
    assert out["connected"] is True
    assert out["state"] == "connected"


def test_whatsapp_bridge_status_unreachable(monkeypatch):
    def _client_factory(*_args, **_kwargs):
        return _FakeClient(raise_exc=RuntimeError("boom"))

    monkeypatch.setattr("app.whatsapp_bridge.httpx.AsyncClient", _client_factory)
    out = asyncio.run(get_whatsapp_bridge_status("http://localhost:3001"))
    assert out["configured"] is True
    assert out["reachable"] is False
    assert out["state"] == "unreachable"
    assert "Cannot reach bridge" in (out["error"] or "")
