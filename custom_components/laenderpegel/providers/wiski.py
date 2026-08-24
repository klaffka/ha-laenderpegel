from __future__ import annotations

from datetime import datetime

import aiohttp

from ..const import HTTP_TIMEOUT


async def async_get_json(session: aiohttp.ClientSession, url: str) -> object:
    async with session.get(url, timeout=aiohttp.ClientTimeout(total=HTTP_TIMEOUT)) as response:
        response.raise_for_status()
        return await response.json()


def parse_wiski_data(payload: list[dict]) -> list[tuple[datetime, float]]:
    punkte: list[tuple[datetime, float]] = []
    for chunk in payload:
        for wertepaar in chunk.get("data", []):
            if len(wertepaar) < 2 or wertepaar[1] is None:
                continue
            zeitpunkt = datetime.fromisoformat(wertepaar[0])
            punkte.append((zeitpunkt, float(wertepaar[1])))
    return punkte
