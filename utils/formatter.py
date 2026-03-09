from __future__ import annotations

from html import escape
from urllib.parse import quote, quote_plus

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from apis.country_api import CountryInfo
from apis.weather_api import WeatherInfo


def _format_population(population: int) -> str:
    if population <= 0:
        return "N/A"
    return f"{population:,}"


def _weather_emoji(condition: str) -> str:
    emoji_map = {
        "Clear": "☀️",
        "Clouds": "☁️",
        "Rain": "🌧️",
        "Drizzle": "🌦️",
        "Thunderstorm": "⛈️",
        "Snow": "❄️",
        "Mist": "🌫️",
        "Haze": "🌫️",
        "Fog": "🌫️",
        "Smoke": "🌫️",
        "Dust": "🌪️",
        "Sand": "🌪️",
        "Squall": "💨",
        "Tornado": "🌪️",
    }
    return emoji_map.get(condition, "🌤️")


def _compose_region(country: CountryInfo) -> str:
    parts: list[str] = []
    if country.region and country.region != "N/A":
        parts.append(country.region)
    if country.continent and country.continent != "N/A" and country.continent not in parts:
        parts.append(country.continent)
    return " / ".join(parts) if parts else "N/A"


def format_poster_caption(
    country: CountryInfo,
    weather: WeatherInfo,
    requested_query: str,
    is_country_query: bool,
) -> str:
    languages = ", ".join(country.languages) if country.languages else "N/A"
    currencies = ", ".join(country.currencies) if country.currencies else "N/A"
    region_line = _compose_region(country)
    weather_symbol = _weather_emoji(weather.condition)

    temperature = f"{weather.temperature_c:.1f}".rstrip("0").rstrip(".")
    wind_speed = f"{weather.wind_speed:.1f}".rstrip("0").rstrip(".")

    title = country.name if is_country_query else requested_query.title()

    return (
        f"<b>🧭 Country Poster: {escape(title)}</b>\n\n"
        f"<b>🌍 Country:</b> {escape(country.name)}\n"
        f"<b>🏙 Capital:</b> {escape(country.capital)}\n"
        f"<b>👥 Population:</b> {_format_population(country.population)}\n"
        f"<b>🌐 Region / Continent:</b> {escape(region_line)}\n"
        f"<b>💬 Languages:</b> {escape(languages)}\n"
        f"<b>💰 Currency:</b> {escape(currencies)}\n\n"
        f"<b>🌤 Weather in {escape(weather.city)}</b>\n"
        f"<b>🌡 Temperature:</b> {temperature}°C\n"
        f"<b>{weather_symbol} Condition:</b> {escape(weather.condition)}\n"
        f"<b>💧 Humidity:</b> {weather.humidity}%\n"
        f"<b>💨 Wind speed:</b> {wind_speed} m/s"
    )


def build_links_keyboard(
    country: CountryInfo, requested_query: str
) -> InlineKeyboardMarkup:
    subject = requested_query.strip() or country.name

    wikipedia_url = f"https://en.wikipedia.org/wiki/{quote(subject.replace(' ', '_'))}"
    youtube_url = (
        "https://youtube.com/results?search_query="
        f"{quote_plus(f'{subject} documentary')}"
    )
    tourism_url = (
        "https://www.google.com/search?q="
        f"{quote_plus(f'{subject} official tourism website')}"
    )

    keyboard = InlineKeyboardBuilder()
    keyboard.row(
        InlineKeyboardButton(text="📚 Wikipedia", url=wikipedia_url),
        InlineKeyboardButton(text="🎥 Watch on YouTube", url=youtube_url),
    )
    keyboard.row(InlineKeyboardButton(text="🌐 Official Website", url=tourism_url))

    if country.maps_url:
        keyboard.row(InlineKeyboardButton(text="🗺 Map", url=country.maps_url))

    return keyboard.as_markup()
