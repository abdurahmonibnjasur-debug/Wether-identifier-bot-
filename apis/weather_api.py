from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import aiohttp


class WeatherAPIError(RuntimeError):
    pass


@dataclass(slots=True)
class WeatherInfo:
    city: str
    country_code: str
    temperature_c: float
    condition: str
    humidity: int
    wind_speed: float
    icon_code: str

    @property
    def icon_url(self) -> str:
        if not self.icon_code:
            return ""
        return f"https://openweathermap.org/img/wn/{self.icon_code}@2x.png"

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "WeatherInfo":
        return cls(
            city=str(payload.get("city", "Unknown")),
            country_code=str(payload.get("country_code", "")),
            temperature_c=float(payload.get("temperature_c") or 0.0),
            condition=str(payload.get("condition", "Unknown")),
            humidity=int(payload.get("humidity") or 0),
            wind_speed=float(payload.get("wind_speed") or 0.0),
            icon_code=str(payload.get("icon_code", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "city": self.city,
            "country_code": self.country_code,
            "temperature_c": self.temperature_c,
            "condition": self.condition,
            "humidity": self.humidity,
            "wind_speed": self.wind_speed,
            "icon_code": self.icon_code,
        }


class WeatherAPI:
    BASE_URL = "https://api.openweathermap.org/data/2.5/weather"

    def __init__(self, session: aiohttp.ClientSession, api_key: str):
        self._session = session
        self._api_key = api_key

    async def get_current(self, city_name: str) -> WeatherInfo | None:
        city_name = city_name.strip()
        if not city_name:
            return None

        params = {
            "q": city_name,
            "appid": self._api_key,
            "units": "metric",
        }

        try:
            async with self._session.get(self.BASE_URL, params=params) as response:
                if response.status == 404:
                    return None
                if response.status >= 400:
                    body = await response.text()
                    raise WeatherAPIError(
                        f"OpenWeather request failed ({response.status}): {body[:200]}"
                    )
                payload = await response.json()
        except aiohttp.ClientError as exc:
            raise WeatherAPIError("Unable to reach OpenWeather API.") from exc

        if not isinstance(payload, dict):
            return None

        weather_items = payload.get("weather") or []
        weather_data = weather_items[0] if weather_items else {}
        main_data = payload.get("main") or {}
        wind_data = payload.get("wind") or {}
        sys_data = payload.get("sys") or {}

        return WeatherInfo(
            city=str(payload.get("name") or city_name),
            country_code=str(sys_data.get("country") or ""),
            temperature_c=float(main_data.get("temp") or 0.0),
            condition=str(weather_data.get("main") or "Unknown"),
            humidity=int(main_data.get("humidity") or 0),
            wind_speed=float(wind_data.get("speed") or 0.0),
            icon_code=str(weather_data.get("icon") or ""),
        )
