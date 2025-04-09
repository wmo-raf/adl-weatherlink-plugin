from datetime import datetime, timezone

import requests
from django.core.cache import cache


# API Reference: https://weatherlink.github.io/v2-api/api-reference
class WeatherLinkAPIClient:
    def __init__(self, api_key, api_secret, base_url='https://api.weatherlink.com/v2/', use_cache=True):
        self.api_key = api_key
        
        if not base_url.endswith('/'):
            base_url += '/'
        
        self.base_url = base_url
        self.use_cache = use_cache
        
        self.headers = {
            "X-Api-Secret": api_secret
        }
    
    def get_stations(self):
        cache_key = f"{self.api_key}-weatherlink-stations"
        if self.use_cache and cache.get(cache_key):
            return cache.get(cache_key)
        else:
            url = f'{self.base_url}stations?api-key={self.api_key}'
            response = requests.get(url, headers=self.headers)
            
            response.raise_for_status()
            
            stations_data = response.json().get('stations', [])
            
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
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        
        sensors = response.json().get('sensors', [])
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
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        
        sensor_types_data = response.json().get('sensor_types', [])
        
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
            # dont include health sensors
            if sensor_catalog.get('category') == "Health":
                continue
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
    
    def get_current_conditions(self, station_id, sensor_types_list):
        sensor_types_list = [str(sensor_type) for sensor_type in sensor_types_list if sensor_type]
        
        url = f'{self.base_url}current/{station_id}?api-key={self.api_key}'
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        
        data_json = response.json()
        sensors = data_json.get('sensors', [])
        
        data = []
        
        for sensor in sensors:
            data_sensor_type = str(sensor['sensor_type'])
            if data_sensor_type in sensor_types_list:
                sensor_data = [{"datetime": datetime.fromtimestamp(item['ts']).replace(tzinfo=timezone.utc), **item} for
                               item in sensor.get("data", [])]
                data.extend(sensor_data)
        
        return data
