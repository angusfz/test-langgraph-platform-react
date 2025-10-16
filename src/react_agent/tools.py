"""Utility tools available to the ReAct agent."""

from __future__ import annotations

import asyncio
import json
import re
import socket
import ssl
from typing import Any, Callable, List, Optional, cast
from urllib import parse, request
from urllib.error import HTTPError, URLError

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


async def search_104_jobs(keyword: str) -> Optional[dict[str, Any]]:
    """Search job openings on 104 人力銀行.

    Use this tool whenever the user requests job listings, vacancies, hiring info, 找工作, 找職缺, or mentions 104.
    Supports optional `page=<number>` suffix in the natural language query to paginate results.
    """
    if not keyword.strip():
        return None

    page = 1
    cleaned_keyword = keyword.strip()

    page_match = re.search(r"page\s*=\s*(\d+)", cleaned_keyword, flags=re.IGNORECASE)
    if page_match:
        try:
            page = max(int(page_match.group(1)), 1)
        except ValueError:
            page = 1
        cleaned_keyword = (
            (cleaned_keyword[: page_match.start()] + cleaned_keyword[page_match.end() :])
            .strip(" ,;")
            .strip()
        )

    if not cleaned_keyword:
        return None

    def _fetch_json() -> Optional[dict[str, Any]]:
        params = {
            "ro": 0,
            "kwop": 1,
            "keyword": cleaned_keyword,
            "expansionType": "job",
            "order": 14,
            "asc": 0,
            "page": page,
            "mode": "s",
            "langFlag": 0,
            "langStatus": 0,
            "recommendJob": 1,
            "hotJob": 1,
            "appliedJob": 0,
        }
        url = "https://www.104.com.tw/jobs/search/list?" + parse.urlencode(params)
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://www.104.com.tw/",
            "Accept": "application/json",
        }

        try:
            context = ssl.create_default_context()
            context.set_ciphers("DEFAULT@SECLEVEL=1")
            req = request.Request(url, headers=headers)
            with request.urlopen(req, context=context, timeout=10) as response:
                return cast(dict[str, Any], json.load(response))
        except (HTTPError, URLError, socket.timeout, json.JSONDecodeError, ValueError):
            return None

    payload = await asyncio.to_thread(_fetch_json)
    if not payload or payload.get("status") != 200:
        return None

    data = cast(dict[str, Any], payload.get("data") or {})
    job_list = cast(List[dict[str, Any]], data.get("list") or [])
    results: List[dict[str, Any]] = []

    for job in job_list[:10]:
        link = job.get("link", {})
        job_url = cast(Optional[str], link.get("job"))
        if job_url and job_url.startswith("//"):
            job_url = f"https:{job_url}"

        results.append(
            {
                "job_name": job.get("jobName"),
                "company": job.get("custName"),
                "location": job.get("jobAddrNoDesc"),
                "salary": job.get("salaryDesc"),
                "posted_date": job.get("appearDate"),
                "job_url": job_url,
                "description": job.get("descWithoutHighlight")
                or job.get("description")
                or "",
            }
        )

    return {
        "keyword": cleaned_keyword,
        "page": data.get("query", {}).get("page", page),
        "total_count": data.get("totalCount"),
        "jobs": results,
        "source": "https://www.104.com.tw/",
    }


TOOLS: List[Callable[..., Any]] = [get_weather, search_104_jobs]
