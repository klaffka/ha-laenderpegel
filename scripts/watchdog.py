"""Live check of all laenderpegel provider endpoints."""

from __future__ import annotations

import asyncio
import sys

import aiohttp

from custom_components.laenderpegel.providers import PROVIDERS

TIMEOUT = 60


async def check_provider(
    session: aiohttp.ClientSession, provider: object
) -> tuple[str, str]:
    label = f"{provider.code} ({provider.name})"
    try:
        stations = await asyncio.wait_for(
            provider.async_get_stations(session), timeout=TIMEOUT
        )
    except (
        aiohttp.ClientError,
        asyncio.TimeoutError,
        ValueError,
        KeyError,
        IndexError,
        TypeError,
    ) as err:
        return label, f"FAIL stations: {type(err).__name__}: {err}"
    if not stations:
        return label, "FAIL: no stations returned"
    detail = f"{len(stations)} stations"
    if getattr(provider, "has_history", True):
        errors: list[str] = []
        ok = False
        for station in stations[:10]:
            try:
                series = await asyncio.wait_for(
                    provider.async_get_series(session, station.id), timeout=TIMEOUT
                )
            except (
                aiohttp.ClientError,
                asyncio.TimeoutError,
                ValueError,
                KeyError,
                IndexError,
                TypeError,
            ) as err:
                errors.append(f"{station.id}: {type(err).__name__}: {err}")
                continue
            if series:
                detail += f", series {len(series)} points"
                ok = True
                break
        if not ok:
            sample = f" ({errors[0]})" if errors else ""
            return label, f"FAIL: no series for any of first 10 stations{sample}"
    return label, f"OK: {detail}"


async def main() -> int:
    timeout = aiohttp.ClientTimeout(total=TIMEOUT + 30)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        results = await asyncio.gather(
            *(check_provider(session, provider) for provider in PROVIDERS.values())
        )
    failed = 0
    for label, status in sorted(results):
        print(f"{label}: {status}")
        if status.startswith("FAIL"):
            failed += 1
    print(f"\n{len(results) - failed}/{len(results)} providers OK")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))