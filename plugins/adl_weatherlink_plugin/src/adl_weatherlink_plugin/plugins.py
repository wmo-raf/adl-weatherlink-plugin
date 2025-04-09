import logging

from adl.core.models import ObservationRecord
from adl.core.registries import Plugin

logger = logging.getLogger(__name__)


class WeatherLinkPlugin(Plugin):
    type = "adl_weatherlink_plugin"
    label = "ADL WeatherLink Plugin"
    
    client = None
    
    def get_urls(self):
        return []
    
    def get_data(self):
        network_conn_name = self.network_connection.name
        
        logger.info(f"[WEATHERLINK_PLUGIN] Starting data processing for {network_conn_name}")
        
        station_links = self.network_connection.station_links.all()
        
        logger.debug(f"[WEATHERLINK_PLUGIN] Found {len(station_links)} station links for {network_conn_name}")
        
        self.client = self.network_connection.get_api_client()
        
        stations_records_count = {}
        
        try:
            for station_link in station_links:
                station_name = station_link.station.name
                
                if not station_link.enabled:
                    logger.warning(f"[WEATHERLINK_PLUGIN] Station link {station_name} is disabled.")
                    continue
                
                logger.debug(f"[WEATHERLINK_PLUGIN] Processing data for {station_name}")
                
                station_link_records_count = self.process_station_link(station_link)
                
                stations_records_count[station_link.station.id] = station_link_records_count
        except Exception as e:
            logger.error(f"[WEATHERLINK_PLUGIN] Error processing data for {network_conn_name}. {e}")
        
        return stations_records_count
    
    def process_station_link(self, station_link):
        station_name = station_link.station.name
        
        logger.debug(f"[WEATHERLINK_PLUGIN] Getting latest data for {station_name}")
        
        station_variable_mappings = station_link.variable_mappings.all()
        
        if not station_variable_mappings:
            logger.warning(f"[WEATHERLINK_PLUGIN] No variable mappings found for {station_name}.")
            return 0
        
        unique_sensor_types = set(v_mapping.weatherlink_sensor_type for v_mapping in station_variable_mappings)
        
        # Get the latest data from the WeatherLink API
        current_conditions_data_records = self.client.get_current_conditions(station_link.weatherlink_station_id,
                                                                             unique_sensor_types)
        
        if not current_conditions_data_records:
            logger.warning(f"[WEATHERLINK_PLUGIN] No data found for {station_name}.")
            return 0
        
        observation_records = []
        
        for record in current_conditions_data_records:
            record_datetime = record.get("datetime")
            
            if not record_datetime:
                logger.warning(f"[WEATHERLINK_PLUGIN] No datetime found for {station_name}.")
                continue
            
            for variable_mapping in station_variable_mappings:
                adl_parameter = variable_mapping.adl_parameter
                weatherlink_parameter = variable_mapping.weatherlink_parameter
                weatherlink_parameter_unit = variable_mapping.weatherlink_parameter_unit
                
                value = record.get(weatherlink_parameter)
                
                if value is None:
                    logger.debug(
                        f"[WEATHERLINK_PLUGIN] Data column for parameter {adl_parameter.name} not found in record")
                    continue
                
                if adl_parameter.unit != weatherlink_parameter_unit:
                    value = adl_parameter.convert_value_from_units(value, weatherlink_parameter_unit)
                
                record_data = {
                    "station": station_link.station,
                    "parameter": adl_parameter,
                    "time": record_datetime,
                    "value": value,
                    "connection": station_link.network_connection,
                }
                
                param_obs_record = ObservationRecord(**record_data)
                observation_records.append(param_obs_record)
        
        records_count = len(observation_records)
        
        if observation_records:
            logger.debug(f"[WEATHERLINK_PLUGIN] Saving {records_count} records for {station_name}.")
            ObservationRecord.objects.bulk_create(
                observation_records,
                update_conflicts=True,
                update_fields=["value"],
                unique_fields=["station", "parameter", "time", "connection"]
            )
        
        return records_count
