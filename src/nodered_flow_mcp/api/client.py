from __future__ import annotations

import logging
from typing import Any

import httpx

from ..settings import Settings

log = logging.getLogger("nodered_flow_mcp")


class NodeRedError(Exception):
    def __init__(self, status: int, message: str, body: Any = None):
        super().__init__(f"HTTP {status}: {message}")
        self.status = status
        self.body = body


class RevisionConflict(NodeRedError):
    pass


class NodeRedClient:
    """Async Admin API adapter. Never log tokens or request bodies."""

    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None):
        self.settings = settings
        self._token: str | None = settings.token.get_secret_value() if settings.token else None
        self._http = httpx.AsyncClient(
            base_url=settings.url.rstrip("/"), timeout=settings.timeout, transport=transport
        )

    async def aclose(self) -> None:
        await self._http.aclose()

    # ---- auth ----
    async def auth_scheme(self) -> dict:
        r = await self._http.get("/auth/login")
        r.raise_for_status()
        return r.json()

    async def _login(self) -> None:
        s = self.settings
        if self._token and not (s.user and s.password):
            return
        scheme = await self.auth_scheme()
        if not scheme:
            return  # no auth
        if not (s.user and s.password):
            raise NodeRedError(401, "Node-RED requires credentials; set NODERED_USER/NODERED_PASSWORD or NODERED_TOKEN")
        scope = "read" if s.read_only else "*"
        r = await self._http.post(
            "/auth/token",
            data={
                "client_id": "node-red-admin",
                "grant_type": "password",
                "scope": scope,
                "username": s.user,
                "password": s.password.get_secret_value(),
            },
        )
        if r.status_code != 200:
            raise NodeRedError(r.status_code, "token request failed")
        self._token = r.json()["access_token"]

    async def request(
        self,
        method: str,
        path: str,
        *,
        headers: dict | None = None,
        json: Any = None,
        data: dict | None = None,
        accept_html: bool = False,
        _retry: bool = True,
    ) -> httpx.Response:
        if self._token is None and not getattr(self, "_probed", False):
            self._probed = True
            await self._login()
        h = dict(headers or {})
        if self._token:
            h["Authorization"] = f"Bearer {self._token}"
        if accept_html:
            h["Accept"] = "text/html"
        r = await self._http.request(method, path, headers=h, json=json, data=data)
        if r.status_code == 401 and _retry and self.settings.user:
            self._token = None
            await self._login()
            return await self.request(
                method, path, headers=headers, json=json, data=data, accept_html=accept_html, _retry=False
            )
        if r.status_code >= 400:
            try:
                body = r.json()
            except Exception:
                body = None
            msg = (body or {}).get("message") if isinstance(body, dict) else None
            cls = RevisionConflict if r.status_code == 409 else NodeRedError
            raise cls(r.status_code, msg or r.reason_phrase, body)
        return r

    async def get_json(self, path: str, **kw) -> Any:
        return (await self.request("GET", path, **kw)).json()
