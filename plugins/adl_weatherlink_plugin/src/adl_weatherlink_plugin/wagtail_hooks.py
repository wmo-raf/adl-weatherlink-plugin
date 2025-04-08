from django.urls import path
from wagtail import hooks

from .views import (
    get_weatherlink_stations_for_connection,
    get_weatherlink_station_sensor_types,
    get_weatherlink_sensor_type_data_structures,
    get_weatherlink_sensor_type_data_structure_items
)


@hooks.register('register_admin_urls')
def urlconf_weatherlink_plugin():
    return [
        path("adl-weatherlink-plugin/weatherlink-conn-stations/", get_weatherlink_stations_for_connection,
             name="weatherlink_stations_for_connection"),
        path("adl-weatherlink-plugin/weatherlink-conn-station-sensor-types/",
             get_weatherlink_station_sensor_types,
             name="weatherlink_station_sensor_types", ),
        path("adl-weatherlink-plugin/weatherlink-conn-sensor-type-data-structures/",
             get_weatherlink_sensor_type_data_structures, name="weatherlink_sensor_type_data_structures", ),
        path("adl-weatherlink-plugin/weatherlink-conn-sensor-type-data-structure-items/",
             get_weatherlink_sensor_type_data_structure_items, name="weatherlink_sensor_type_data_structure_items", )
    ]
