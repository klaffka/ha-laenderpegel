import argparse
import sys
from collections import Counter
from datetime import datetime

import requests

API_BASE = "https://www.pegelonline.wsv.de/webservices/rest-api/v2"
DEFAULT_STATION_UUID = "a26e57c9-1cb8-4fca-ba80-9e02abc81df8"


def fetch_json(url):
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.json()


def station_label(station):
    km = station.get("km")
    return f"{station['longname']} ({station['water']['longname']}, km {km})" if km is not None else f"{station['longname']} ({station['water']['longname']})"


def match_station(station, query):
    q = query.strip().upper()
    if q == station.get("uuid", "").upper():
        return True
    if q == station.get("number", ""):
        return True
    return q in station["longname"].upper() or q in station["shortname"].upper()


def filter_stations(stations, wasser=None, station=None):
    ergebnis = stations
    if wasser:
        w = wasser.strip().upper()
        ergebnis = [s for s in ergebnis if w == s["water"]["shortname"].upper() or w in s["water"]["longname"].upper()]
    if station:
        ergebnis = [s for s in ergebnis if match_station(s, station)]
    return ergebnis


def show_station_list(stations):
    if not stations:
        print("Keine Messstellen gefunden.")
        return 1
    for s in sorted(stations, key=lambda x: (x["water"]["longname"], x.get("km") or 0)):
        km = s.get("km")
        km_text = f"km {km}" if km is not None else "km -"
        print(f"{s['number']:>10}  {s['longname']:<35} {s['water']['longname']:<12} {km_text}")
    print(f"\n{len(stations)} Messstellen")
    return 0


def show_station_data(uuid, tage):
    station = fetch_json(f"{API_BASE}/stations/{uuid}.json?includeTimeseries=true")
    zeitreihen = [ts for ts in station.get("timeseries", []) if ts.get("shortname") == "W"]
    if not zeitreihen:
        print(f"Fehler: Station {station['longname']} hat keine Wasserstands-Zeitreihe (W).")
        return 1
    einheit = zeitreihen[0].get("unit", "")

    try:
        aktuell = fetch_json(f"{API_BASE}/stations/{uuid}/W/currentmeasurement.json")
    except requests.HTTPError:
        aktuell = None

    messwerte = fetch_json(f"{API_BASE}/stations/{uuid}/W/measurements.json?start=P{tage}D")

    print(f"📊 Pegelzusammenfassung: {station_label(station)}")
    if aktuell:
        stand = datetime.fromisoformat(aktuell["timestamp"]).strftime("%Y-%m-%d %H:%M %z")
        print(f"🌊 Aktueller Wert: {aktuell['value']} {einheit} (Stand: {stand})")
    else:
        print("🌊 Aktueller Wert: nicht verfügbar")

    if messwerte:
        print(f"\n🕰️ Letzte 5 Messwerte (letzte {tage} Tage):")
        for eintrag in messwerte[-5:]:
            zeit = datetime.fromisoformat(eintrag["timestamp"]).strftime("%Y-%m-%d %H:%M")
            print(f"{zeit}: {eintrag['value']} {einheit}")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Wasserstände aus der WSV PEGELONLINE REST-API (v2)")
    parser.add_argument("--wasser", help="Gewässer filtern oder listen (z. B. RHEIN, ELBE, MOSEL)")
    parser.add_argument("--station", help="Station nach Nummer, Namen oder UUID wählen (z. B. HITZACKER)")
    parser.add_argument("--tage", type=int, default=7, help="Tage für die Historie (1-30, Standard: 7)")
    parser.add_argument("--liste", action="store_true", help="alle Gewässer mit Stationsanzahl anzeigen")
    args = parser.parse_args()

    tage = max(1, min(30, args.tage))

    try:
        stations = fetch_json(f"{API_BASE}/stations.json")
    except requests.RequestException as e:
        print(f"Fehler beim Abruf der Messstellen: {e}", file=sys.stderr)
        return 1

    if args.liste:
        zaehler = Counter(s["water"]["longname"] for s in stations)
        for name, anzahl in zaehler.most_common():
            print(f"{anzahl:4d}  {name}")
        print(f"\n{len(zaehler)} Gewässer, {len(stations)} Messstellen")
        return 0

    if args.wasser or args.station:
        ergebnis = filter_stations(stations, wasser=args.wasser, station=args.station)
        if not ergebnis:
            print(f"Keine Messstelle für {args.wasser or ''} {args.station or ''} gefunden.", file=sys.stderr)
            return 1
        if len(ergebnis) > 1 and not args.station:
            return show_station_list(ergebnis)
        if len(ergebnis) > 1:
            print("Mehrere Treffer – bitte --station genauer angeben:")
            return show_station_list(ergebnis)
        return show_station_data(ergebnis[0]["uuid"], tage)

    return show_station_data(DEFAULT_STATION_UUID, tage)


if __name__ == "__main__":
    sys.exit(main())