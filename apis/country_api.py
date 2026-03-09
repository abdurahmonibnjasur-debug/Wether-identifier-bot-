from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import aiohttp


class CountryAPIError(RuntimeError):
    pass


@dataclass(slots=True)
class CountryInfo:
    name: str
    capital: str
    population: int
    region: str
    continent: str
    languages: list[str]
    currencies: list[str]
    flag_url: str
    country_code: str
    maps_url: str

    @classmethod
    def from_restcountries(cls, payload: dict[str, Any]) -> "CountryInfo":
        name_payload = payload.get("name") or {}
        name = name_payload.get("common") or name_payload.get("official") or "Unknown"

        capitals = payload.get("capital") or []
        capital = capitals[0] if capitals else "N/A"

        population = int(payload.get("population") or 0)

        region = str(payload.get("region") or "N/A")

        continents = payload.get("continents") or []
        continent = str(continents[0]) if continents else "N/A"

        languages_payload = payload.get("languages") or {}
        languages = [str(value) for value in languages_payload.values()]

        currencies_payload = payload.get("currencies") or {}
        currencies: list[str] = []
        for code, value in currencies_payload.items():
            if isinstance(value, dict):
                currency_name = value.get("name")
                currency_symbol = value.get("symbol")
                if currency_name and currency_symbol:
                    currencies.append(f"{currency_name} ({currency_symbol})")
                elif currency_name:
                    currencies.append(str(currency_name))
                else:
                    currencies.append(str(code))
            else:
                currencies.append(str(code))

        flags_payload = payload.get("flags") or {}
        flag_url = str(flags_payload.get("png") or flags_payload.get("svg") or "")

        country_code = str(payload.get("cca2") or payload.get("cca3") or "")

        maps_payload = payload.get("maps") or {}
        maps_url = str(
            maps_payload.get("googleMaps") or maps_payload.get("openStreetMaps") or ""
        )

        return cls(
            name=name,
            capital=capital,
            population=population,
            region=region,
            continent=continent,
            languages=languages,
            currencies=currencies,
            flag_url=flag_url,
            country_code=country_code,
            maps_url=maps_url,
        )

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "CountryInfo":
        return cls(
            name=str(payload.get("name", "Unknown")),
            capital=str(payload.get("capital", "N/A")),
            population=int(payload.get("population") or 0),
            region=str(payload.get("region", "N/A")),
            continent=str(payload.get("continent", "N/A")),
            languages=[str(item) for item in payload.get("languages", [])],
            currencies=[str(item) for item in payload.get("currencies", [])],
            flag_url=str(payload.get("flag_url", "")),
            country_code=str(payload.get("country_code", "")),
            maps_url=str(payload.get("maps_url", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "capital": self.capital,
            "population": self.population,
            "region": self.region,
            "continent": self.continent,
            "languages": self.languages,
            "currencies": self.currencies,
            "flag_url": self.flag_url,
            "country_code": self.country_code,
            "maps_url": self.maps_url,
        }


class CountryAPI:
    BASE_URL = "https://restcountries.com/v3.1"

    def __init__(self, session: aiohttp.ClientSession):
        self._session = session

    async def get_by_name(self, country_name: str) -> CountryInfo | None:
        country_name = country_name.strip()
        if not country_name:
            return None

        strict_data = await self._request(
            f"/name/{quote(country_name)}", params={"fullText": "true"}
        )
        payload = strict_data[0] if isinstance(strict_data, list) and strict_data else None
        if not payload:
            broad_data = await self._request(f"/name/{quote(country_name)}")
            payload = broad_data[0] if isinstance(broad_data, list) and broad_data else None

        if not isinstance(payload, dict):
            return None
        return CountryInfo.from_restcountries(payload)

    async def get_by_code(self, country_code: str) -> CountryInfo | None:
        country_code = country_code.strip()
        if not country_code:
            return None

        data = await self._request(f"/alpha/{quote(country_code)}")
        if isinstance(data, list):
            payload = data[0] if data else None
        else:
            payload = data

        if not isinstance(payload, dict):
            return None
        return CountryInfo.from_restcountries(payload)

    async def _request(
        self, path: str, params: dict[str, str] | None = None
    ) -> Any | None:
        url = f"{self.BASE_URL}{path}"
        try:
            async with self._session.get(url, params=params) as response:
                if response.status == 404:
                    return None
                if response.status >= 400:
                    body = await response.text()
                    raise CountryAPIError(
                        f"RestCountries request failed ({response.status}): {body[:200]}"
                    )
                return await response.json()
        except aiohttp.ClientError as exc:
            raise CountryAPIError("Unable to reach RestCountries API.") from exc
