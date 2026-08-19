"""
Tests for the ingestion-diagnostic contracts: ``get_source_endpoint()``,
``check_source()``, ``check_station_source()``, the ``adl_sources_count``
duck-typed handover and the exception stamping in ``client.py``. See the
"Ingestion Diagnostic Contracts" page in the ADL developer guide.

All tests run without touching the database: model instances are built
unsaved and the HTTP layer is stubbed, so the seam under test is exactly the
contract core consumes. That is what ``SimpleTestCase`` buys here — Django
still calls ``setup_databases()`` whatever the class, so the suite is run on
this plugin's own compose stack with ``make test`` from the repo root.
"""

import ast
import os
from datetime import datetime, timedelta, timezone
from unittest import mock

import requests
from adl.core.models import Network, Station
from adl.core.source_checks import SourceCheckResult, SourceCheckStatus
from django.test import SimpleTestCase

from adl_weatherlink_plugin.client import WeatherLinkAPIClient, category_for_status
from adl_weatherlink_plugin.models import WeatherLinkConnection, WeatherLinkStationLink
from adl_weatherlink_plugin.plugins import WeatherLinkPlugin

NOT_JSON = object()

NOW = datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc)


class FakeResponse:
    """A stubbed ``requests`` response: status code, and a body that either
    parses or does not."""

    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self.payload = payload

    def json(self):
        if self.payload is NOT_JSON:
            # What an HTML login page reached through a redirect looks like
            # from here. requests' own JSONDecodeError is a ValueError too.
            raise requests.exceptions.JSONDecodeError("Expecting value", "<html>", 0)
        return self.payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} Error", response=self)


class FakeAPIClient:
    """A stubbed WeatherLink client that answers the one call a check makes."""

    def __init__(self, stations=None, error=None, conditions=None):
        self.stations = stations if stations is not None else {}
        self.error = error
        self.conditions = conditions

    def get_stations(self):
        if self.error is not None:
            raise self.error
        return self.stations

    def get_station(self, station_id):
        return self.get_stations().get(str(station_id))

    def get_current_conditions(self, station_id, sensor_types_list, start_date=None, end_date=None):
        if self.error is not None:
            raise self.error
        return self.conditions


def station_record(station_id="12345", name="Nairobi — Dagoretti Corner", sensors=None):
    record = {"station_id": station_id, "station_name": name}
    if sensors is not None:
        record["sensors"] = sensors
    return record


def make_connection(**kwargs):
    kwargs.setdefault("api_key", "key")
    kwargs.setdefault("api_secret", "secret")
    kwargs.setdefault("api_base_url", "https://api.weatherlink.com/v2")
    return WeatherLinkConnection(**kwargs)


def make_station_link(connection=None, **kwargs):
    kwargs.setdefault("weatherlink_station_id", "12345")
    link = WeatherLinkStationLink(**kwargs)
    link.network_connection = connection or make_connection()
    return link


def stub_api_client(client):
    """Patch the client factory, capturing the arguments the check passed."""
    calls = []

    def factory(self, **kwargs):
        calls.append(kwargs)
        return client

    patcher = mock.patch.object(WeatherLinkConnection, "get_api_client", autospec=True,
                                side_effect=factory)
    return patcher, calls


def snapshot(*sensors):
    return {"sensors": list(sensors)}


def sensor(sensor_type="45", entries=()):
    return {"sensor_type": sensor_type, "data": list(entries)}


def entry(observation_time, **values):
    return {"ts": int(observation_time.timestamp()), **values}


class GetApiClientTests(SimpleTestCase):
    """The factory's defaults are the ingestion path's behaviour, unchanged;
    only the on-demand checks ask for anything else."""

    def test_defaults_are_todays_ingestion_behaviour(self):
        client = make_connection().get_api_client()
        self.assertTrue(client.use_cache)
        self.assertEqual(client.timeout, 30)

    def test_checks_can_bound_and_bypass(self):
        client = make_connection().get_api_client(use_cache=False, timeout=5, retries=0)
        self.assertFalse(client.use_cache)
        self.assertEqual(client.timeout, 5)


class GetSourceEndpointTests(SimpleTestCase):

    def test_derives_host_and_default_port_from_the_base_url(self):
        self.assertEqual(make_connection().get_source_endpoint(),
                         ("api.weatherlink.com", 443))

    def test_honours_an_explicit_port(self):
        connection = make_connection(api_base_url="https://weatherlink.example.test:8443/v2")
        self.assertEqual(connection.get_source_endpoint(), ("weatherlink.example.test", 8443))

    def test_takes_port_80_from_an_http_scheme(self):
        connection = make_connection(api_base_url="http://weatherlink.example.test/v2")
        self.assertEqual(connection.get_source_endpoint(), ("weatherlink.example.test", 80))


class CheckSourceTests(SimpleTestCase):

    def check(self, connection):
        result = connection.check_source()
        self.assertIsInstance(result, SourceCheckResult)
        self.assertIn(result.status, SourceCheckStatus.ALL)
        return result

    def run_check(self, client, connection=None):
        connection = connection or make_connection()
        patcher, calls = stub_api_client(client)
        with patcher:
            result = self.check(connection)
        return result, calls

    def test_a_parsed_station_list_is_ok(self):
        result, _calls = self.run_check(FakeAPIClient(stations={"12345": station_record()}))
        self.assertEqual(result.status, SourceCheckStatus.OK)
        self.assertIsNone(result.category)
        self.assertIn("api.weatherlink.com", result.message)
        self.assertIn("1", result.message)

    def test_bypasses_the_cache_and_bounds_the_call(self):
        _result, calls = self.run_check(FakeAPIClient(stations={}))
        self.assertEqual(calls, [{"use_cache": False, "timeout": 5, "retries": 0}])

    def test_classifies_from_the_status_the_server_sent(self):
        for status, category in ((401, "AUTH_FAILED"), (403, "PERMISSION_DENIED"),
                                 (404, "PATH_NOT_FOUND"), (500, "PROTOCOL_ERROR"),
                                 (503, "PROTOCOL_ERROR")):
            with self.subTest(status=status):
                error = requests.HTTPError(response=FakeResponse(status))
                result, _calls = self.run_check(FakeAPIClient(error=error))
                self.assertEqual(result.status, SourceCheckStatus.FAILED)
                self.assertEqual(result.category, category)
                self.assertIn(str(status), result.message)
                self.assertIn("/v2/stations", result.message)

    def test_never_names_the_api_key_bearing_query_string(self):
        error = requests.HTTPError(response=FakeResponse(401))
        result, _calls = self.run_check(FakeAPIClient(error=error))
        self.assertNotIn("api-key", result.message)
        self.assertNotIn("?", result.message)

    def test_declines_a_status_that_is_not_the_sources_fault(self):
        for status in (400, 422, 429):
            with self.subTest(status=status):
                error = requests.HTTPError(response=FakeResponse(status))
                result, _calls = self.run_check(FakeAPIClient(error=error))
                self.assertEqual(result.status, SourceCheckStatus.FAILED)
                self.assertIsNone(result.category)

    def test_a_login_page_200_is_not_ok(self):
        for error in (ValueError("The response carried no 'stations' list."),
                      requests.exceptions.JSONDecodeError("Expecting value", "<html>", 0)):
            with self.subTest(error=type(error).__name__):
                result, _calls = self.run_check(FakeAPIClient(error=error))
                self.assertEqual(result.status, SourceCheckStatus.FAILED)
                self.assertIsNone(result.category)
                self.assertIn("not a station list", result.message)

    def test_a_codeless_failure_declines_the_category(self):
        # Core stamps every return layer 5, so a layer-4 category here would
        # have the diagnostic contradict itself about which layer failed.
        for error in (requests.ConnectionError("connection refused"),
                      requests.exceptions.SSLError("bad handshake"),
                      requests.exceptions.ReadTimeout("timed out")):
            with self.subTest(error=type(error).__name__):
                result, _calls = self.run_check(FakeAPIClient(error=error))
                self.assertEqual(result.status, SourceCheckStatus.FAILED)
                self.assertIsNone(result.category)
                self.assertIn("could not be reached", result.message)

    def test_survives_the_core_normaliser(self):
        from adl.core.source_checks import normalise_source_check_result
        result, _calls = self.run_check(FakeAPIClient(stations={"12345": station_record()}))
        self.assertEqual(normalise_source_check_result(result).status, SourceCheckStatus.OK)

    def test_core_detects_the_override(self):
        from adl.core.source_checks import connection_implements_check_source
        self.assertTrue(connection_implements_check_source(make_connection()))


class CheckStationSourceTests(SimpleTestCase):

    def check(self, link):
        result = link.check_station_source()
        self.assertIsInstance(result, SourceCheckResult)
        self.assertIn(result.status, SourceCheckStatus.ALL)
        return result

    def run_check(self, client, link=None):
        link = link or make_station_link()
        patcher, calls = stub_api_client(client)
        with patcher:
            result = self.check(link)
        return result, calls

    def test_a_present_id_is_ok_with_the_upstream_label(self):
        client = FakeAPIClient(stations={"12345": station_record()})
        result, _calls = self.run_check(client)
        self.assertEqual(result.status, SourceCheckStatus.OK)
        self.assertIn("12345", result.message)
        self.assertIn("Nairobi — Dagoretti Corner", result.message)

    def test_reports_the_sensor_count_the_record_already_carried(self):
        client = FakeAPIClient(stations={"12345": station_record(sensors=[{}, {}, {}])})
        result, _calls = self.run_check(client)
        self.assertEqual(result.status, SourceCheckStatus.OK)
        self.assertIn("3 sensor", result.message)

    def test_zero_sensors_is_ok_with_the_zero_stated(self):
        client = FakeAPIClient(stations={"12345": station_record(sensors=[])})
        result, _calls = self.run_check(client)
        self.assertEqual(result.status, SourceCheckStatus.OK)
        self.assertIn("0 sensor", result.message)

    def test_an_absent_id_is_proven_not_found(self):
        client = FakeAPIClient(stations={"99999": station_record(station_id="99999")})
        result, _calls = self.run_check(client)
        self.assertEqual(result.status, SourceCheckStatus.FAILED)
        self.assertEqual(result.category, "PATH_NOT_FOUND")
        self.assertIn("12345", result.message)

    def test_bypasses_the_cache(self):
        # Harder here than at connection scope: a day-old list would report a
        # station added upstream yesterday as proven missing.
        _result, calls = self.run_check(FakeAPIClient(stations={"12345": station_record()}))
        self.assertEqual(calls, [{"use_cache": False, "timeout": 5, "retries": 0}])

    def test_a_failed_read_is_never_converted_into_ok(self):
        for error in (requests.ConnectionError("connection refused"),
                      requests.HTTPError(response=FakeResponse(500)),
                      ValueError("The response carried no 'stations' list.")):
            with self.subTest(error=type(error).__name__):
                result, _calls = self.run_check(FakeAPIClient(error=error))
                self.assertEqual(result.status, SourceCheckStatus.FAILED)
                self.assertNotEqual(result.category, "PATH_NOT_FOUND")

    def test_core_detects_the_override(self):
        from adl.core.source_checks import station_link_implements_check_station_source
        self.assertTrue(station_link_implements_check_station_source(make_station_link()))


class SourcesCountTests(SimpleTestCase):
    """The count is committed only from something the source told us, only
    once it has told us, and only for the window that was asked about."""

    START = NOW - timedelta(hours=1)
    END = NOW

    def make_link(self):
        link = make_station_link()
        # The plugin logs the link, and its __str__ reaches for the station.
        link.station = Station(name="Station 1")
        link.station.network = Network(name="WeatherLink Network")
        link.get_variable_mappings = lambda: []
        return link

    def collect(self, link, client):
        patcher, _calls = stub_api_client(client)
        with patcher:
            return WeatherLinkPlugin().get_station_data(link, self.START, self.END)

    def test_counts_what_the_client_reported(self):
        link = self.make_link()
        self.collect(link, FakeAPIClient(conditions=([], 4)))
        self.assertEqual(link.adl_sources_count, 4)

    def test_an_empty_answer_is_zero_not_silence(self):
        link = self.make_link()
        self.collect(link, FakeAPIClient(conditions=([], 0)))
        self.assertEqual(link.adl_sources_count, 0)

    def test_a_failed_call_makes_no_claim_at_all(self):
        # None, never 0: a run that never got an answer must not accuse the
        # source of having offered nothing.
        link = self.make_link()
        link.adl_sources_count = None
        with self.assertRaises(requests.ConnectionError):
            self.collect(link, FakeAPIClient(error=requests.ConnectionError("refused")))
        self.assertIsNone(link.adl_sources_count)


class CurrentConditionsWindowTests(SimpleTestCase):
    """The window rule, applied by this plugin because the endpoint will not:
    `current/<station_id>` answers with the console's last known reading
    whatever window was asked for."""

    START = NOW - timedelta(hours=1)
    END = NOW

    def conditions(self, payload, sensor_types=("45",), start_date=None, end_date=None):
        client = WeatherLinkAPIClient(api_key="key", api_secret="secret")
        with mock.patch.object(client.session, "get", return_value=FakeResponse(200, payload)):
            return client.get_current_conditions("12345", sensor_types,
                                                 start_date=start_date, end_date=end_date)

    def test_a_fresh_snapshot_counts(self):
        payload = snapshot(sensor(entries=[entry(NOW - timedelta(minutes=4), temp=21.5)]))
        _records, count = self.conditions(payload, start_date=self.START, end_date=self.END)
        self.assertEqual(count, 1)

    def test_a_dead_console_counts_zero(self):
        # The endpoint still answers, with a reading four weeks old. Counting
        # it would acquit the source exactly when it is the fault.
        payload = snapshot(sensor(entries=[entry(NOW - timedelta(weeks=4), temp=21.5)]))
        _records, count = self.conditions(payload, start_date=self.START, end_date=self.END)
        self.assertEqual(count, 0)

    def test_counts_sensors_our_mappings_did_not_ask_for(self):
        # Counting only the mapped subset would read a mapping change as the
        # source having gone quiet.
        payload = snapshot(
            sensor(sensor_type="45", entries=[entry(NOW - timedelta(minutes=4), temp=21.5)]),
            sensor(sensor_type="99", entries=[entry(NOW - timedelta(minutes=4), rain=0)]),
        )
        records, count = self.conditions(payload, sensor_types=("45",),
                                         start_date=self.START, end_date=self.END)
        self.assertEqual(count, 2)
        self.assertEqual(len(records), 1)

    def test_an_entry_without_a_timestamp_is_not_counted(self):
        # On an unmapped sensor, so this exercises the counter rather than the
        # record builder, which has always required a `ts`.
        payload = snapshot(sensor(sensor_type="99", entries=[{"temp": 21.5}]))
        _records, count = self.conditions(payload, sensor_types=("45",),
                                          start_date=self.START, end_date=self.END)
        self.assertEqual(count, 0)

    def test_an_unbounded_call_counts_everything_the_response_carried(self):
        payload = snapshot(sensor(entries=[entry(NOW - timedelta(weeks=4), temp=21.5)]))
        _records, count = self.conditions(payload)
        self.assertEqual(count, 1)


class ExceptionStampingTests(SimpleTestCase):
    """A failed ingestion run carries the source's own verdict into the
    activity log, stamped in place so core's type table still applies."""

    def get_stations(self, response):
        client = WeatherLinkAPIClient(api_key="key", api_secret="secret")
        with mock.patch.object(client.session, "get", return_value=response):
            return client.get_stations()

    def test_stamps_a_classified_status_at_layer_5(self):
        for status, category in ((401, "AUTH_FAILED"), (403, "PERMISSION_DENIED"),
                                 (404, "PATH_NOT_FOUND"), (502, "PROTOCOL_ERROR")):
            with self.subTest(status=status):
                with self.assertRaises(requests.HTTPError) as caught:
                    self.get_stations(FakeResponse(status))
                self.assertEqual(caught.exception.adl_category, category)
                self.assertEqual(caught.exception.adl_layer, 5)

    def test_leaves_a_declined_status_unstamped(self):
        # Declining keeps core's read-time tier free to classify the row
        # later; a stamp — UNKNOWN above all — would block it permanently.
        for status in (400, 422, 429):
            with self.subTest(status=status):
                with self.assertRaises(requests.HTTPError) as caught:
                    self.get_stations(FakeResponse(status))
                self.assertFalse(hasattr(caught.exception, "adl_category"))

    def test_core_reads_the_stamp(self):
        from adl.core.classification import classify_failure
        with self.assertRaises(requests.HTTPError) as caught:
            self.get_stations(FakeResponse(401))
        self.assertEqual(classify_failure(caught.exception), ("AUTH_FAILED", 5))

    def test_a_body_that_is_not_a_station_list_raises(self):
        for payload in (NOT_JSON, {"error": "unauthorized"}, []):
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError):
                    self.get_stations(FakeResponse(200, payload))

    def test_the_status_table_declines_what_is_not_the_sources_fault(self):
        self.assertIsNone(category_for_status(302))
        self.assertIsNone(category_for_status(429))
        self.assertEqual(category_for_status(404), "PATH_NOT_FOUND")


class OlderCoreImportSafetyTests(SimpleTestCase):
    """The plugin must import cleanly on a core release that predates the
    source-check contracts, so nothing may import ``adl.core.source_checks``
    at module level.

    The contracts import it lazily instead, inside the method that needs it.
    Never wrap that import in ``try/except ImportError``: on an older core the
    method is never called, so the handler is unreachable, and it would turn a
    genuine import failure into a silent "this plugin does not support the
    check".
    """

    # Every module this plugin ships. Extend it as the plugin grows more.
    MODULES = ["models.py", "plugins.py", "client.py", "apps.py", "views.py",
               "validators.py", "widgets.py", "wagtail_hooks.py"]

    DENIED = "adl.core.source_checks"

    def test_no_module_level_import_of_source_checks(self):
        package_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        for name in self.MODULES:
            path = os.path.join(package_dir, name)
            if not os.path.exists(path):
                continue  # a module this plugin does not (yet) ship
            with open(path) as f:
                tree = ast.parse(f.read())
            for node in ast.walk(tree):
                if not isinstance(node, (ast.Import, ast.ImportFrom)):
                    continue
                if node.col_offset != 0:
                    continue  # indented imports are lazy, inside a function
                names = [a.name for a in node.names]
                module = getattr(node, "module", "") or ""
                self.assertNotIn(
                    self.DENIED, [module] + names,
                    f"{name} imports {self.DENIED} at module level")
