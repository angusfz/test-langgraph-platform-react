"""Utility tools available to the ReAct agent."""

from __future__ import annotations

import asyncio
import json
import socket
from typing import Any, Callable, List, Optional, cast
from urllib import parse, request
from urllib.error import HTTPError, URLError

from langchain_tavily import TavilySearch  # type: ignore[import-not-found]
from langgraph.runtime import get_runtime

from react_agent.context import Context


async def search(query: str) -> Optional[dict[str, Any]]:
    """Search for general web results.

    This function performs a search using the Tavily search engine, which is designed
    to provide comprehensive, accurate, and trusted results. It's particularly useful
    for answering questions about current events.
    """
    runtime = get_runtime(Context)
    wrapped = TavilySearch(max_results=runtime.context.max_search_results)
    return cast(dict[str, Any], await wrapped.ainvoke({"query": query}))


async def get_weather(location: str) -> Optional[dict[str, Any]]:
    """Fetch current weather and short-term forecast for a location.

    Args:
        location: Free-form location name supplied by the user.

    Returns:
        Optional[dict[str, Any]]: Weather data if the lookup succeeds, otherwise None.
    """

    def _fetch_json(url: str) -> Optional[dict[str, Any]]:
        """Perform a blocking HTTP GET and parse JSON in a worker thread."""
        try:
            with request.urlopen(url, timeout=10) as response:
                return cast(dict[str, Any], json.load(response))
        except (HTTPError, URLError, socket.timeout, json.JSONDecodeError):
            return None

    if not location.strip():
        return None

    encoded_location = parse.quote_plus(location.strip())
    geocode_url = (
        "https://geocoding-api.open-meteo.com/v1/search"
        f"?name={encoded_location}&count=1&language=en&format=json"
    )

    geocode = await asyncio.to_thread(_fetch_json, geocode_url)
    if not geocode or not geocode.get("results"):
        return None

    match = geocode["results"][0]
    latitude = match.get("latitude")
    longitude = match.get("longitude")
    if latitude is None or longitude is None:
        return None

    resolved_name_parts = [
        part for part in (match.get("name"), match.get("admin1"), match.get("country")) if part
    ]
    resolved_name = ", ".join(resolved_name_parts) if resolved_name_parts else location.strip()

    forecast_params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": "temperature_2m,apparent_temperature,relative_humidity_2m,precipitation,"
        "weather_code,wind_speed_10m",
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
        "timezone": "auto",
    }
    forecast_url = f"https://api.open-meteo.com/v1/forecast?{parse.urlencode(forecast_params)}"

    forecast = await asyncio.to_thread(_fetch_json, forecast_url)
    if not forecast or "current" not in forecast:
        return None

    return {
        "resolved_location": resolved_name,
        "latitude": latitude,
        "longitude": longitude,
        "current": forecast.get("current"),
        "current_units": forecast.get("current_units"),
        "daily": forecast.get("daily"),
        "daily_units": forecast.get("daily_units"),
        "source": "https://open-meteo.com/",
    }


TOOLS: List[Callable[..., Any]] = [search, get_weather]
