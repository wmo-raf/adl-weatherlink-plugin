from datetime import datetime, timezone

import requests
from django.core.cache import cache

DEFAULT_BASE_URL = 'https://api.weatherlink.com/v2/'
DEFAULT_TIMEOUT = 30

STATIONS_PATH = 'stations'

# The ingestion diagnostic's shared HTTP status table. The category strings are
# written out rather than imported from core: an import of core's vocabulary
# would break this plugin at import time on an older core, and core drops any
# value it does not recognise anyway.
#
# 400 and 422 decline because a malformed request is our bug, 429 because rate
# limiting is our polling schedule, and 3xx because a redirect says nothing
# about the source. Nothing here ever stamps UNKNOWN: declining leaves core's
# read-time classification free to do better later, and a stamp does not.
STATUS_CATEGORIES = {
    401: "AUTH_FAILED",
    403: "PERMISSION_DENIED",
    404: "PATH_NOT_FOUND",
}


def category_for_status(status_code):
    """The diagnostic failure category for an HTTP status, or None when the
    status carries no honest one."""
    if status_code in STATUS_CATEGORIES:
        return STATUS_CATEGORIES[status_code]
    if status_code is not None and 500 <= status_code < 600:
        return "PROTOCOL_ERROR"
    return None


def _raise_for_status(response):
    """``raise_for_status()``, tagging the raised error for the diagnostic.

    The exception is stamped in place rather than wrapped, so the original
    type still matches core's own exception table and the traceback survives.
    A code from the server is proof the server answered, which is what makes
    every category derived from one layer 5.
    """
    try:
        response.raise_for_status()
    except requests.HTTPError as e:
        category = category_for_status(e.response.status_code)
        if category:
            e.adl_category = category
            e.adl_layer = 5
        raise


def _parsed_list(response, key):
    """The list under ``key`` in a response body that really is one.

    A 2xx is not proof of an API response: ``requests`` follows redirects, so
    an expired session that lands on an HTML login page arrives here as a
    clean 200. Both that and a JSON body without the key raise ``ValueError``
    — requests' own ``JSONDecodeError`` is one too — so a caller has a single
    type to catch for "answered, but not with what we asked for".
    """
    payload = response.json()
    if not isinstance(payload, dict) or not isinstance(payload.get(key), list):
        raise ValueError(f"The response carried no '{key}' list.")
    return payload[key]


def _entry_time(item):
    """The observation time of one snapshot entry, or None when it carries no
    usable timestamp."""
    ts = item.get("ts")
    if ts is None:
        return None
    try:
        return datetime.fromtimestamp(ts).replace(tzinfo=timezone.utc)
    except (TypeError, ValueError, OSError):
        return None


def _within_window(item, start_date, end_date):
    """Whether one snapshot entry falls inside the requested window.

    ``current/<station_id>`` is a latest-snapshot endpoint: it ignores the
    window and answers with the console's last known reading, whether that is
    4 minutes or 4 weeks old. An unbounded count of its entries is therefore
    always >= 1 for a configured station, and layer 5 would acquit the source
    exactly when a dead console is the fault. So the window is applied here,
    on timestamps as received, before any mapping or conversion.
    """
    observation_time = _entry_time(item)
    if observation_time is None:
        return False
    if start_date and observation_time < start_date:
        return False
    if end_date and observation_time > end_date:
        return False
    return True


# API Reference: https://weatherlink.github.io/v2-api/api-reference
class WeatherLinkAPIClient:
    def __init__(self, api_key, api_secret, base_url=DEFAULT_BASE_URL, timeout=DEFAULT_TIMEOUT, retries=None,
                 use_cache=True):
        self.api_key = api_key
        
        if not base_url.endswith('/'):
            base_url += '/'
        
        self.base_url = base_url
        self.timeout = timeout
        self.use_cache = use_cache
        
        self.headers = {
            "X-Api-Secret": api_secret
        }
        
        self.session = requests.Session()
        if retries is not None:
            # Mounted only when asked for. requests' default adapter already
            # retries nothing, so the ingestion path keeps its behaviour and
            # the on-demand diagnostic checks can say so explicitly.
            adapter = requests.adapters.HTTPAdapter(max_retries=retries)
            self.session.mount("https://", adapter)
            self.session.mount("http://", adapter)
    
    def get_stations(self):
        cache_key = f"{self.api_key}-weatherlink-stations"
        if self.use_cache and cache.get(cache_key):
            return cache.get(cache_key)
        
        url = f'{self.base_url}{STATIONS_PATH}?api-key={self.api_key}'
        response = self.session.get(url, headers=self.headers, timeout=self.timeout)
        
        _raise_for_status(response)
        
        stations_data = _parsed_list(response, 'stations')
        
        stations_data_dict_by_id = {}
        for station in stations_data:
            station_id = str(station['station_id'])
            stations_data_dict_by_id[station_id] = station
        
        if self.use_cache:
            # cache for 24 hours
            cache.set(cache_key, stations_data_dict_by_id, 86400)
        
        return stations_data_dict_by_id
    
    def get_station(self, station_id):
        
        stations = self.get_stations()
        
        if not stations.get(station_id):
            return None
        
        return stations.get(station_id)
    
    def get_sensors(self):
        cache_key = f"{self.api_key}-weatherlink-sensors"
        if self.use_cache and cache.get(cache_key):
            return cache.get(cache_key)
        
        url = f'{self.base_url}sensors?api-key={self.api_key}'
        response = self.session.get(url, headers=self.headers, timeout=self.timeout)
        _raise_for_status(response)
        
        sensors = _parsed_list(response, 'sensors')
        sensors_dict_by_station = {}
        
        for sensor in sensors:
            station_id = str(sensor['station_id'])
            if sensors_dict_by_station.get(station_id):
                sensors_dict_by_station[station_id].append(sensor)
            else:
                sensors_dict_by_station[station_id] = [sensor]
        
        if self.use_cache:
            # cache for 24 hours
            cache.set(cache_key, sensors_dict_by_station, 86400)
        
        return sensors_dict_by_station
    
    def get_sensors_for_station(self, station_id):
        station_id = str(station_id)
        sensors = self.get_sensors()
        
        return sensors.get(station_id, [])
    
    def get_sensor_catalog(self):
        cache_key = f"{self.api_key}-weatherlink-sensor-catalog"
        if self.use_cache and cache.get(cache_key):
            return cache.get(cache_key)
        
        url = f'{self.base_url}sensor-catalog?api-key={self.api_key}'
        response = self.session.get(url, headers=self.headers, timeout=self.timeout)
        _raise_for_status(response)
        
        sensor_types_data = _parsed_list(response, 'sensor_types')
        
        data_dict_by_sensor_type = {}
        for sensor_type in sensor_types_data:
            data_dict_by_sensor_type[str(sensor_type['sensor_type'])] = sensor_type
        
        if self.use_cache:
            # cache for 24 hours
            cache.set(cache_key, data_dict_by_sensor_type, 86400)
        
        return data_dict_by_sensor_type
    
    def get_sensor_catalog_for_sensor_type(self, sensor_type):
        sensor_type = str(sensor_type)
        sensor_catalog = self.get_sensor_catalog()
        
        return sensor_catalog.get(sensor_type, {})
    
    def get_sensor_catalog_for_station(self, station_id):
        station_id = str(station_id)
        sensors = self.get_sensors_for_station(station_id)
        
        catalog = []
        
        for sensor in sensors:
            sensor_catalog = self.get_sensor_catalog_for_sensor_type(sensor['sensor_type'])
            catalog.append(sensor_catalog)
        
        return catalog
    
    def get_data_structures_for_sensor_type(self, sensor_type):
        sensor_type = str(sensor_type)
        sensor_catalog = self.get_sensor_catalog_for_sensor_type(sensor_type)
        data_structures = sensor_catalog.get('data_structures', [])
        return data_structures
    
    def get_data_sensor_type_data_structure_items_by_id(self, sensor_type, data_structure_type):
        data_structures = self.get_data_structures_for_sensor_type(sensor_type)
        for data_structure in data_structures:
            if str(data_structure['data_structure_type']) == str(data_structure_type):
                items = data_structure.get('data_structure')
                return items
        
        return None
    
    def get_current_conditions(self, station_id, sensor_types_list, start_date=None, end_date=None):
        """
        Fetch the station's current conditions, returning ``(records, sources_count)``.
        
        The count is of the entries the response carried that fall inside the
        requested window — every sensor in it, not the ``sensor_types_list``
        subset our own variable mappings asked for, which would turn a mapping
        change into a source fault. The window bound is this plugin's to apply:
        the endpoint is a latest-snapshot one and ignores it. It leaves the
        client by return value because the station link the count is reported
        on belongs to the plugin, not here.
        """
        sensor_types_list = [str(sensor_type) for sensor_type in sensor_types_list if sensor_type]
        
        url = f'{self.base_url}current/{station_id}?api-key={self.api_key}'
        response = self.session.get(url, headers=self.headers, timeout=self.timeout)
        _raise_for_status(response)
        
        sensors = _parsed_list(response, 'sensors')
        
        data = []
        sources_count = 0
        
        for sensor in sensors:
            data_sensor_type = str(sensor['sensor_type'])
            entries = sensor.get("data", [])
            
            sources_count += sum(1 for item in entries if _within_window(item, start_date, end_date))
            
            if data_sensor_type in sensor_types_list:
                sensor_data = [
                    {"observation_time": datetime.fromtimestamp(item['ts']).replace(tzinfo=timezone.utc), **item} for
                    item in entries]
                data.extend(sensor_data)
        
        return data, sources_count
