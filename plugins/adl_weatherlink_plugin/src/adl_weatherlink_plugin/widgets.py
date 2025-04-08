from django.forms import Widget
from django.urls import reverse
from wagtail.api.v2.utils import get_full_url


class WeatherLinkStationSelectWidget(Widget):
    template_name = 'adl_weatherlink_plugin/widgets/weatherlink_01_station_select_widget.html'
    
    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        
        context.update({
            'weatherlink_stations_url': reverse("weatherlink_stations_for_connection"),
        })
        
        return context


class WeatherLinkSensorTypeSelectWidget(Widget):
    template_name = 'adl_weatherlink_plugin/widgets/weatherlink_02_station_sensor_type_select_widget.html'
    
    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        
        context.update({
            'weatherlink_stations_sensor_type_url': reverse("weatherlink_station_sensor_types"),
        })
        
        return context


class WeatherLinkStationDataStructureSelectWidget(Widget):
    template_name = 'adl_weatherlink_plugin/widgets/weatherlink_03_station_data_structure_select_widget.html'
    
    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        
        context.update({
            'weatherlink_stations_data_structure_url': reverse("weatherlink_sensor_type_data_structures"),
        })
        
        return context


class WeatherLinkStationDataStructureItemSelectWidget(Widget):
    template_name = 'adl_weatherlink_plugin/widgets/weatherlink_04_station_data_structure_item_select_widget.html'
    
    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        
        url = get_full_url(None, reverse("weatherlink_sensor_type_data_structure_items"))
        
        context.update({
            'weatherlink_sensor_type_data_structure_items': url,
        })
        
        return context
