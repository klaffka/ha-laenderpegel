from datetime import timedelta
from typing import Any

DOMAIN = "pegelonline"

CONF_STATION_UUID = "station_uuid"
CONF_STATION_NUMBER = "station_number"
CONF_STATION_NAME = "station_name"
CONF_WASSER = "wasser"
CONF_KM = "fluss_km"
CONF_UNIT = "unit"
CONF_FORECAST_UNIT = "forecast_unit"
CONF_GAUGE_ZERO = "pegelnullpunkt"
CONF_HAS_FORECAST = "has_forecast"

API_BASE = "https://www.pegelonline.wsv.de/webservices/rest-api/v2"
SCAN_INTERVAL = timedelta(minutes=5)
FORECAST_HORIZON_HOURS = 24
HTTP_TIMEOUT = 30


def get_device_info(entry: Any) -> dict[str, Any]:
    return {
        "identifiers": {(DOMAIN, entry.data[CONF_STATION_UUID])},
        "name": f"{entry.data[CONF_STATION_NAME]} ({entry.data[CONF_WASSER]})",
        "manufacturer": "Wasserstraßen- und Schifffahrtsverwaltung des Bundes",
        "model": "PEGELONLINE",
    }
