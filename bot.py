from __future__ import annotations

import logging
import socket
from dataclasses import dataclass

import aiohttp
from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ChatAction, ParseMode
from aiogram.exceptions import TelegramNetworkError, TelegramUnauthorizedError
from aiogram.filters import CommandStart
from aiogram.types import Message

from apis import (
    CountryAPI,
    CountryAPIError,
    CountryInfo,
    WeatherAPI,
    WeatherAPIError,
    WeatherInfo,
)
from config import Config
from utils import JSONCache, build_links_keyboard, format_poster_caption

logger = logging.getLogger(__name__)
router = Router()


WELCOME_MESSAGE = (
    "Welcome! 🌍\n"
    "Send me the name of a country or city, and I will show useful information "
    "including weather, population, and more.\n\n"
    "Examples:\n"
    "• Uzbekistan\n"
    "• France\n"
    "• Tokyo"
)


class UserInputError(ValueError):
    pass


@dataclass(slots=True)
class Services:
    country_api: CountryAPI
    weather_api: WeatherAPI
    cache: JSONCache


@dataclass(slots=True)
class PosterData:
    country: CountryInfo
    weather: WeatherInfo
    requested_query: str
    is_country_query: bool


_services: Services | None = None


class StaticHostResolver(aiohttp.abc.AbstractResolver):
    def __init__(self, host_mapping: dict[str, str]):
        self._host_mapping = host_mapping
        self._default_resolver = aiohttp.resolver.DefaultResolver()

    async def resolve(
        self, host: str, port: int = 0, family: int = socket.AF_INET
    ) -> list[dict[str, object]]:
        forced_ip = self._host_mapping.get(host)
        if forced_ip is None:
            return await self._default_resolver.resolve(host, port, family)

        ip_family = socket.AF_INET6 if ":" in forced_ip else socket.AF_INET
        return [
            {
                "hostname": host,
                "host": forced_ip,
                "port": port,
                "family": ip_family,
                "proto": 0,
                "flags": socket.AI_NUMERICHOST,
            }
        ]

    async def close(self) -> None:
        await self._default_resolver.close()


@router.message(CommandStart())
async def start_handler(message: Message) -> None:
    await message.answer(WELCOME_MESSAGE)


@router.message(F.text)
async def location_handler(message: Message) -> None:
    if _services is None:
        await message.answer("Bot is not ready yet. Please try again.")
        return

    query = (message.text or "").strip()
    if not query:
        return

    if query.startswith("/"):
        await message.answer("Use /start, then send a country or city name.")
        return

    await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)

    try:
        poster = await build_poster(query, _services)
    except UserInputError:
        await message.answer(
            "I couldn't find that location. Try a valid country or city name, "
            "for example: Uzbekistan, France, Tokyo."
        )
        return
    except (CountryAPIError, WeatherAPIError) as exc:
        logger.exception("External API error: %s", exc)
        await message.answer(
            "One of the data providers is temporarily unavailable. Please try again in a moment."
        )
        return
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected error: %s", exc)
        await message.answer("Unexpected error occurred. Please try again.")
        return

    caption = format_poster_caption(
        country=poster.country,
        weather=poster.weather,
        requested_query=poster.requested_query,
        is_country_query=poster.is_country_query,
    )
    keyboard = build_links_keyboard(
        country=poster.country,
        requested_query=poster.requested_query,
    )

    if poster.country.flag_url:
        await message.answer_photo(
            photo=poster.country.flag_url,
            caption=caption,
            reply_markup=keyboard,
        )
    else:
        await message.answer(
            caption,
            reply_markup=keyboard,
            disable_web_page_preview=True,
        )


async def build_poster(query: str, services: Services) -> PosterData:
    normalized_query = " ".join(query.split())
    if len(normalized_query) < 2:
        raise UserInputError("Query is too short.")

    country = await get_country_by_name_cached(normalized_query, services)
    if country:
        weather_city = country.capital if country.capital != "N/A" else country.name
        weather = await get_weather_cached(weather_city, services)
        if not weather:
            weather = await get_weather_cached(country.name, services)
        if not weather:
            raise UserInputError("Weather not found for country.")

        return PosterData(
            country=country,
            weather=weather,
            requested_query=country.name,
            is_country_query=True,
        )

    weather = await get_weather_cached(normalized_query, services)
    if not weather:
        raise UserInputError("Location not found.")

    country = await get_country_by_code_cached(weather.country_code, services)
    if not country:
        country = CountryInfo(
            name=weather.city,
            capital=weather.city,
            population=0,
            region="N/A",
            continent="N/A",
            languages=[],
            currencies=[],
            flag_url="",
            country_code=weather.country_code,
            maps_url="",
        )

    return PosterData(
        country=country,
        weather=weather,
        requested_query=normalized_query,
        is_country_query=False,
    )


async def get_country_by_name_cached(
    country_name: str, services: Services
) -> CountryInfo | None:
    cache_key = f"country:name:{country_name.lower()}"
    cached = services.cache.get(cache_key)
    if isinstance(cached, dict):
        return CountryInfo.from_dict(cached)

    country = await services.country_api.get_by_name(country_name)
    if country:
        services.cache.set(cache_key, country.to_dict())
    return country


async def get_country_by_code_cached(
    country_code: str, services: Services
) -> CountryInfo | None:
    if not country_code:
        return None

    cache_key = f"country:code:{country_code.lower()}"
    cached = services.cache.get(cache_key)
    if isinstance(cached, dict):
        return CountryInfo.from_dict(cached)

    country = await services.country_api.get_by_code(country_code)
    if country:
        services.cache.set(cache_key, country.to_dict())
    return country


async def get_weather_cached(city_name: str, services: Services) -> WeatherInfo | None:
    cache_key = f"weather:city:{city_name.lower()}"
    cached = services.cache.get(cache_key)
    if isinstance(cached, dict):
        return WeatherInfo.from_dict(cached)

    weather = await services.weather_api.get_current(city_name)
    if weather:
        services.cache.set(cache_key, weather.to_dict())
    return weather


def build_bot(config: Config, telegram_api_ip: str | None = None) -> Bot:
    bot_session = AiohttpSession(
        proxy=config.telegram_proxy_url,
        timeout=float(config.http_timeout_seconds),
    )

    if telegram_api_ip and not config.telegram_proxy_url:
        bot_session._connector_init["resolver"] = StaticHostResolver(
            {"api.telegram.org": telegram_api_ip}
        )

    return Bot(
        token=config.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        session=bot_session,
    )


async def connect_bot_with_fallback(config: Config) -> Bot | None:
    candidates: list[str | None] = []
    if config.telegram_api_ip:
        candidates.append(config.telegram_api_ip)
    else:
        candidates.append(None)

    for fallback_ip in config.telegram_api_fallback_ips:
        if fallback_ip not in candidates:
            candidates.append(fallback_ip)

    if config.telegram_proxy_url and candidates[0] is not None:
        candidates.insert(0, None)

    for candidate_ip in candidates:
        bot = build_bot(config, telegram_api_ip=candidate_ip)
        attempt_desc = (
            f" via TELEGRAM_API_IP={candidate_ip}" if candidate_ip else " via direct DNS"
        )
        logger.info("Checking Telegram API connectivity%s...", attempt_desc)
        try:
            me = await bot.get_me()
            logger.info("Connected to Telegram as @%s (id=%s)", me.username, me.id)
            if candidate_ip:
                logger.info("Using Telegram API IP override: %s", candidate_ip)
            return bot
        except TelegramUnauthorizedError:
            logger.error(
                "Invalid TELEGRAM_BOT_TOKEN. Update TELEGRAM_BOT_TOKEN in .env and retry."
            )
            await bot.session.close()
            return None
        except TelegramNetworkError as exc:
            logger.warning(
                "Telegram connectivity failed%s. Details: %s", attempt_desc, exc
            )
            await bot.session.close()

    logger.error(
        "Telegram API is unreachable from this network. Set TELEGRAM_PROXY_URL "
        "(for example socks5://127.0.0.1:1080) or configure TELEGRAM_API_IP "
        "to a reachable Telegram API IP."
    )
    return None


async def run() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    config = Config.from_env()
    dispatcher = Dispatcher()
    dispatcher.include_router(router)

    timeout = aiohttp.ClientTimeout(total=config.http_timeout_seconds)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        services = Services(
            country_api=CountryAPI(session),
            weather_api=WeatherAPI(session, config.openweather_api_key),
            cache=JSONCache(config.cache_file, config.cache_ttl_seconds),
        )

        global _services
        _services = services
        bot = await connect_bot_with_fallback(config)
        if bot is None:
            return

        try:
            await dispatcher.start_polling(
                bot,
                allowed_updates=dispatcher.resolve_used_update_types(),
            )
        finally:
            await bot.session.close()
