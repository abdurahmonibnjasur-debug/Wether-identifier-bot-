from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


@dataclass(slots=True)
class Config:
    telegram_bot_token: str
    openweather_api_key: str
    telegram_proxy_url: str | None
    telegram_api_ip: str | None
    telegram_api_fallback_ips: list[str]
    cache_file: Path
    cache_ttl_seconds: int
    http_timeout_seconds: int

    @classmethod
    def from_env(cls) -> "Config":
        telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        openweather_api_key = os.getenv("OPENWEATHER_API_KEY", "").strip()
        telegram_proxy_url = os.getenv("TELEGRAM_PROXY_URL", "").strip() or None
        telegram_api_ip = os.getenv("TELEGRAM_API_IP", "").strip() or None
        raw_fallback_ips = os.getenv("TELEGRAM_API_FALLBACK_IPS", "149.154.167.99")
        telegram_api_fallback_ips = [
            item.strip() for item in raw_fallback_ips.split(",") if item.strip()
        ]

        if not telegram_bot_token:
            raise ValueError("Missing TELEGRAM_BOT_TOKEN environment variable.")
        if not openweather_api_key:
            raise ValueError("Missing OPENWEATHER_API_KEY environment variable.")

        cache_file = Path(os.getenv("CACHE_FILE", "cache/data.json"))

        try:
            cache_ttl_seconds = int(os.getenv("CACHE_TTL_SECONDS", "21600"))
        except ValueError as exc:
            raise ValueError("CACHE_TTL_SECONDS must be an integer.") from exc

        try:
            http_timeout_seconds = int(os.getenv("HTTP_TIMEOUT_SECONDS", "20"))
        except ValueError as exc:
            raise ValueError("HTTP_TIMEOUT_SECONDS must be an integer.") from exc

        return cls(
            telegram_bot_token=telegram_bot_token,
            openweather_api_key=openweather_api_key,
            telegram_proxy_url=telegram_proxy_url,
            telegram_api_ip=telegram_api_ip,
            telegram_api_fallback_ips=telegram_api_fallback_ips,
            cache_file=cache_file,
            cache_ttl_seconds=max(cache_ttl_seconds, 0),
            http_timeout_seconds=max(http_timeout_seconds, 5),
        )
