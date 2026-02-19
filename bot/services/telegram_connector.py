"""Telegram notification connector with pacing and 429 retry handling."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Optional

try:
    import httpx
except ImportError:  # pragma: no cover - optional dependency
    httpx = None  # type: ignore[assignment]

logger = logging.getLogger("bot.services.telegram_connector")


class TelegramConnector:
    """Send Telegram messages via Bot API with retry/pacing controls."""

    def __init__(
        self,
        *,
        enabled: bool,
        bot_token: str,
        api_base_url: str = "https://api.telegram.org",
        min_interval_seconds: float = 0.2,
        max_retries: int = 3,
        request_timeout_seconds: int = 15,
    ):
        self.bot_token = (bot_token or "").strip()
        self.api_base_url = (api_base_url or "https://api.telegram.org").rstrip("/")
        self.min_interval_seconds = max(0.0, float(min_interval_seconds))
        self.max_retries = max(1, int(max_retries))
        self.request_timeout_seconds = max(5, int(request_timeout_seconds))

        self.enabled = bool(enabled and self.bot_token)
        self._send_lock = asyncio.Lock()
        self._next_send_at = 0.0
        self._client: Optional[Any] = None

        if self.enabled and httpx is None:
            logger.warning("Telegram connector requested but httpx is not installed; disabling connector")
            self.enabled = False

        if enabled and not self.bot_token:
            logger.warning("Telegram connector enabled but bot token is missing")

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

    async def send_message(self, chat_id: str | int, message: str) -> str:
        """Send a message to a Telegram chat with retry/backoff on 429 + transient errors."""
        if not self.enabled:
            raise RuntimeError("Telegram connector is disabled")

        target = str(chat_id).strip()
        if not target:
            raise ValueError("Telegram chat_id is required")

        endpoint = f"{self.api_base_url}/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": target,
            "text": message,
            "disable_web_page_preview": True,
        }

        async with self._send_lock:
            for attempt in range(1, self.max_retries + 1):
                await self._pace_locked()
                client = await self._get_client()

                try:
                    response = await client.post(endpoint, json=payload)
                except Exception as exc:
                    if attempt >= self.max_retries:
                        raise RuntimeError(f"Telegram request failed: {exc}") from exc
                    await asyncio.sleep(min(2 ** (attempt - 1), 10))
                    continue

                retry_after = self._extract_retry_after(response)
                if response.status_code == 429:
                    wait_seconds = retry_after or min(2 ** attempt, 30)
                    if attempt >= self.max_retries:
                        raise RuntimeError(
                            f"Telegram rate-limited after {self.max_retries} attempts"
                        )
                    logger.warning(
                        "Telegram 429 for chat_id=%s, retry_after=%ss", target, wait_seconds
                    )
                    await asyncio.sleep(wait_seconds)
                    continue

                if 500 <= response.status_code < 600:
                    if attempt >= self.max_retries:
                        detail = self._response_detail(response)
                        raise RuntimeError(
                            f"Telegram server error {response.status_code}: {detail}"
                        )
                    await asyncio.sleep(min(2 ** (attempt - 1), 10))
                    continue

                if response.status_code >= 400:
                    detail = self._response_detail(response)
                    raise RuntimeError(
                        f"Telegram send failed ({response.status_code}): {detail}"
                    )

                data = self._safe_json(response)
                if isinstance(data, dict) and data.get("ok", False):
                    result = data.get("result") if isinstance(data.get("result"), dict) else {}
                    message_id = result.get("message_id")
                    return str(message_id) if message_id is not None else "ok"

                detail = "unexpected Telegram response"
                if isinstance(data, dict):
                    detail = str(data.get("description") or detail)
                raise RuntimeError(f"Telegram send failed: {detail}")

            raise RuntimeError("Telegram send failed after retries")

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
            params = data.get("parameters") or {}
            retry_after = params.get("retry_after")
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
            if data.get("description"):
                return str(data["description"])
            return str(data)
        text = (response.text or "").strip()
        return text[:300] if text else "no response body"
