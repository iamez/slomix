"""Signal notification connector (signal-cli wrapper / daemon path)."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Optional

try:
    import httpx
except ImportError:  # pragma: no cover - optional dependency
    httpx = None  # type: ignore[assignment]

logger = logging.getLogger("bot.services.signal_connector")


class SignalConnector:
    """Send Signal messages via signal-cli directly or daemon REST endpoint."""

    def __init__(
        self,
        *,
        enabled: bool,
        mode: str = "cli",
        signal_cli_path: str = "signal-cli",
        sender_number: str = "",
        daemon_url: str = "http://127.0.0.1:8080",
        min_interval_seconds: float = 0.2,
        max_retries: int = 2,
        request_timeout_seconds: int = 20,
    ):
        self.mode = (mode or "cli").strip().lower()
        if self.mode not in {"cli", "daemon"}:
            self.mode = "cli"

        requested_cli_path = (signal_cli_path or "signal-cli").strip()
        allowed_cli_paths = {"signal-cli", "/usr/bin/signal-cli", "/usr/local/bin/signal-cli"}
        if requested_cli_path in allowed_cli_paths:
            self.signal_cli_path = requested_cli_path
        else:
            logger.warning(
                "Unsupported signal-cli path '%s'; falling back to PATH lookup",
                requested_cli_path,
            )
            self.signal_cli_path = "signal-cli"
        self.sender_number = (sender_number or "").strip()
        self.daemon_url = (daemon_url or "http://127.0.0.1:8080").rstrip("/")
        self.min_interval_seconds = max(0.0, float(min_interval_seconds))
        self.max_retries = max(1, int(max_retries))
        self.request_timeout_seconds = max(5, int(request_timeout_seconds))

        self.enabled = bool(enabled and self.sender_number)
        self._send_lock = asyncio.Lock()
        self._next_send_at = 0.0
        self._client: Optional[Any] = None

        if self.enabled and self.mode == "daemon" and httpx is None:
            logger.warning("Signal daemon mode requested but httpx is not installed; disabling connector")
            self.enabled = False

        if enabled and not self.sender_number:
            logger.warning("Signal connector enabled but SIGNAL sender number is missing")

    async def _get_client(self):
        if httpx is None:
            raise RuntimeError("httpx is not installed")
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.request_timeout_seconds)
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def send_message(self, recipient: str, message: str) -> str:
        """Send a Signal message to a recipient."""
        if not self.enabled:
            raise RuntimeError("Signal connector is disabled")

        target = (recipient or "").strip()
        if not target:
            raise ValueError("Signal recipient is required")

        async with self._send_lock:
            for attempt in range(1, self.max_retries + 1):
                await self._pace_locked()
                try:
                    if self.mode == "daemon":
                        return await self._send_via_daemon(target, message)
                    return await self._send_via_cli(target, message)
                except Exception as exc:
                    if attempt >= self.max_retries:
                        raise RuntimeError(f"Signal send failed: {exc}") from exc
                    await asyncio.sleep(min(2 ** (attempt - 1), 10))

            raise RuntimeError("Signal send failed after retries")

    async def _send_via_daemon(self, recipient: str, message: str) -> str:
        client = await self._get_client()
        endpoint = f"{self.daemon_url}/v2/send"
        payload = {
            "number": self.sender_number,
            "recipients": [recipient],
            "message": message,
        }

        response = await client.post(endpoint, json=payload)
        if response.status_code == 429:
            retry_after = self._extract_retry_after(response)
            wait = retry_after or 1.0
            logger.warning("Signal daemon rate-limited, waiting %ss", wait)
            await asyncio.sleep(wait)
            raise RuntimeError("Signal daemon rate limit")

        if response.status_code >= 400:
            detail = self._response_detail(response)
            raise RuntimeError(
                f"Signal daemon error ({response.status_code}): {detail}"
            )
        data = self._safe_json(response)
        if isinstance(data, dict):
            if isinstance(data.get("timestamp"), (int, float, str)):
                return str(data.get("timestamp"))
            if isinstance(data.get("result"), dict):
                ts = data["result"].get("timestamp")
                if ts is not None:
                    return str(ts)
        return "ok"

    async def _send_via_cli(self, recipient: str, message: str) -> str:
        try:
            if self.signal_cli_path == "/usr/bin/signal-cli":
                process = await asyncio.create_subprocess_exec(
                    "/usr/bin/signal-cli",
                    "-u",
                    self.sender_number,
                    "send",
                    "-m",
                    message,
                    recipient,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
            elif self.signal_cli_path == "/usr/local/bin/signal-cli":
                process = await asyncio.create_subprocess_exec(
                    "/usr/local/bin/signal-cli",
                    "-u",
                    self.sender_number,
                    "send",
                    "-m",
                    message,
                    recipient,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
            else:
                process = await asyncio.create_subprocess_exec(
                    "signal-cli",
                    "-u",
                    self.sender_number,
                    "send",
                    "-m",
                    message,
                    recipient,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
        except FileNotFoundError as exc:
            raise RuntimeError(f"signal-cli not found at '{self.signal_cli_path}'") from exc

        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            detail = (stderr or stdout or b"").decode("utf-8", errors="replace").strip()
            raise RuntimeError(
                f"signal-cli exited with {process.returncode}: {detail or 'unknown error'}"
            )
        return "ok"

    async def _pace_locked(self) -> None:
        now = time.monotonic()
        if now < self._next_send_at:
            await asyncio.sleep(self._next_send_at - now)
        self._next_send_at = time.monotonic() + self.min_interval_seconds

    def _extract_retry_after(self, response: httpx.Response) -> Optional[float]:
        header_val = response.headers.get("Retry-After")
        if header_val:
            try:
                return max(0.0, float(header_val))
            except (TypeError, ValueError):
                pass

        data = self._safe_json(response)
        if isinstance(data, dict):
            retry_after = (
                (data.get("error") or {}).get("retry_after")
                if isinstance(data.get("error"), dict)
                else None
            )
            if retry_after is None and isinstance(data.get("parameters"), dict):
                retry_after = data["parameters"].get("retry_after")
            try:
                if retry_after is not None:
                    return max(0.0, float(retry_after))
            except (TypeError, ValueError):
                return None
        return None

    @staticmethod
    def _safe_json(response: httpx.Response) -> Any:
        try:
            return response.json()
        except Exception:
            return None

    def _response_detail(self, response: httpx.Response) -> str:
        data = self._safe_json(response)
        if isinstance(data, dict):
            return str(data)
        text = (response.text or "").strip()
        return text[:300] if text else "no response body"
