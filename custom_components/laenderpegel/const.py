from datetime import timedelta
from typing import Any

DOMAIN = "laenderpegel"

CONF_PROVIDER = "provider"
CONF_STATION_ID = "station_id"
CONF_STATION_NAME = "station_name"
CONF_WASSER = "wasser"
CONF_GAUGE_ZERO = "pegelnullpunkt"

SCAN_INTERVAL = timedelta(minutes=15)
HTTP_TIMEOUT = 30


def get_device_info(entry: Any, provider_name: str) -> dict[str, Any]:
    return {
        "identifiers": {(DOMAIN, f"{entry.data[CONF_PROVIDER]}:{entry.data[CONF_STATION_ID]}")},
        "name": f"{entry.data[CONF_STATION_NAME]} ({entry.data[CONF_WASSER]})",
        "manufacturer": provider_name,
        "model": "Länderpegel",
    }
