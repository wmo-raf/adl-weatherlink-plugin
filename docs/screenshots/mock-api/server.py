"""A stub of the WeatherLink v2 API, for the documentation screenshot harness.

It answers the four calls this plugin makes, so a capture run exercises the real
client, the real select widgets and the real diagnostics without a live account:

    GET <base>/stations         the account's stations
    GET <base>/sensors          the sensors on them
    GET <base>/sensor-catalog   the vendor's sensor/data-structure definitions
    GET <base>/current/<id>     the latest reading per sensor

The payloads were recorded from a real service and then anonymised: the sensor
catalogue is kept verbatim (it is vendor documentation, identical for every
customer, and is what the guide teaches operators to read), while station names,
station and hardware ids, uuids and coordinates are replaced with demo values.
Recording rather than inventing is the point -- a hand-written catalogue would
serve sensor types and field names the real API does not have, and the docs
would look green while documenting a fiction.

Readings are synthesised at request time, so the newest one is always "now" and
the freshness layer of the ingestion diagnostic is honest. Davis reports
imperial units, and so does this stub.

Environment: MOCK_API_KEY / MOCK_API_SECRET (the credentials it accepts),
MOCK_PORT (default 8000).
"""

import json
import math
import os
import random
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

PAYLOADS = Path(__file__).with_name("payloads")
STATIONS = json.loads((PAYLOADS / "stations.json").read_text())
SENSORS = json.loads((PAYLOADS / "sensors.json").read_text())
CATALOG = json.loads((PAYLOADS / "sensor-catalog.json").read_text())
CURRENT = json.loads((PAYLOADS / "current.json").read_text())

API_KEY = os.environ.get("MOCK_API_KEY", "demo-key")
API_SECRET = os.environ.get("MOCK_API_SECRET", "demo-secret")
PORT = int(os.environ.get("MOCK_PORT", "8000"))

# field -> (base, amplitude, digits). Imperial, as Davis hardware reports.
CURVES = {
    "temp": (79.0, 11.0, 1),           # degrees Fahrenheit
    "hum": (65.0, -20.0, 1),           # percent
    "wind_speed_last": (5.5, 3.0, 2),  # miles per hour
    "wind_dir_last": (180.0, 40.0, 0),  # degrees
    "bar_sea_level": (29.92, 0.05, 3),  # inches of mercury
    "rainfall_last_15_min_mm": (0.0, 0.0, 1),
}


def reading(field, moment, seed):
    base, amp, digits = CURVES[field]
    rng = random.Random(f"{seed}-{field}-{moment:%Y%m%d%H%M}")
    hour = moment.hour + moment.minute / 60
    diurnal = math.sin((hour - 9) / 24 * 2 * math.pi)
    if field == "rainfall_last_15_min_mm":
        return round(rng.choice([0, 0, 0, 0, 0.2, 0.6]) if 14 <= hour <= 17 else 0, 1)
    value = round(base + amp * diurnal + rng.uniform(-0.3, 0.3), digits)
    if field == "wind_dir_last":
        value = round(value % 360)
    if field == "hum":
        value = max(0.0, min(100.0, value))
    return value


def current_for(station_id):
    """The recorded response for this station, with a fresh timestamp and fresh
    values on the fields the guide maps. Every other field keeps whatever the
    recording held, so the shape stays exactly the vendor's."""
    body = json.loads(json.dumps(CURRENT[station_id]))
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    stamp = int(now.timestamp())
    body["generated_at"] = stamp
    for sensor in body.get("sensors", []):
        for entry in sensor.get("data", []):
            entry["ts"] = stamp
            for field in CURVES:
                if field in entry:
                    entry[field] = reading(field, now, f"{station_id}-{sensor['sensor_type']}")
    return body


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)

        # Both halves of the credential are checked, so an operator's "wrong key"
        # or "wrong secret" failure and the diagnostic it produces are capturable.
        if (query.get("api-key") or [None])[0] != API_KEY:
            return self.send(401, {"code": "UnauthorizedError", "message": "invalid api key"})
        if self.headers.get("X-Api-Secret") != API_SECRET:
            return self.send(403, {"code": "ForbiddenError", "message": "invalid api secret"})

        path = parsed.path.rstrip("/")
        if path.endswith("/stations"):
            return self.send(200, STATIONS)
        if path.endswith("/sensors"):
            return self.send(200, SENSORS)
        if path.endswith("/sensor-catalog"):
            return self.send(200, CATALOG)
        if "/current/" in path:
            station_id = path.rsplit("/", 1)[-1]
            if station_id not in CURRENT:
                return self.send(404, {"code": "NotFoundError",
                                       "message": f"no station {station_id}"})
            return self.send(200, current_for(station_id))
        return self.send(404, {"code": "NotFoundError", "message": f"no such path: {parsed.path}"})

    def send(self, status, body):
        raw = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, fmt, *args):
        print(f"[mock-weatherlink] {fmt % args}", flush=True)


if __name__ == "__main__":
    print(f"[mock-weatherlink] {len(STATIONS['stations'])} stations, "
          f"{len(SENSORS['sensors'])} sensors, "
          f"{len(CATALOG['sensor_types'])} catalogue types, port {PORT}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
