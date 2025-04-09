from adl.core.utils import get_object_or_none
from django.http import JsonResponse
from django.utils.translation import gettext_lazy as _

from .models import WeatherLinkConnection


def get_weatherlink_stations_for_connection(request):
    network_connection_id = request.GET.get('connection_id')
    
    if not network_connection_id:
        response = {
            "error": _("Network connection ID is required.")
        }
        return JsonResponse(response, status=400)
    
    network_conn = get_object_or_none(WeatherLinkConnection, pk=network_connection_id)
    if not network_conn:
        response = {
            "error": _("The selected connection is not a Weatherlink Connection")
        }
        
        return JsonResponse(response, status=400)
    
    client = network_conn.get_api_client()
    
    stations_dict = client.get_stations()
    
    stations_list = []
    
    for key, station in stations_dict.items():
        station_id = station.get("station_id")
        station_name = station.get("station_name")
        station_label = f"{station_name} ({station_id})"
        stations_list.append({"label": station_label, "value": station_id})
    
    return JsonResponse(stations_list, safe=False)


def get_weatherlink_station_sensor_types(request):
    network_connection_id = request.GET.get('connection_id')
    weatherlink_station_id = request.GET.get('station_id')
    
    if not network_connection_id:
        response = {
            "error": _("Network connection ID is required.")
        }
        return JsonResponse(response, status=400)
    
    if not weatherlink_station_id:
        response = {
            "error": _("Weatherlink station ID is required.")
        }
        return JsonResponse(response, status=400)
    
    network_conn = get_object_or_none(WeatherLinkConnection, pk=network_connection_id)
    if not network_conn:
        response = {
            "error": _("The selected connection is not a Weatherlink Connection")
        }
        
        return JsonResponse(response, status=400)
    
    client = network_conn.get_api_client()
    station_sensor_types = client.get_sensors_for_station(weatherlink_station_id)
    
    if not station_sensor_types:
        response = {
            "error": _("No sensors found for the selected station.")
        }
        return JsonResponse(response, status=400)
    
    station_sensor_types = [
        {
            "label": f"{sensor.get('product_name')} ({sensor.get('sensor_type')})",
            "value": sensor.get('sensor_type'),
        }
        for sensor in station_sensor_types
    ]
    
    return JsonResponse(station_sensor_types, safe=False)


def get_weatherlink_sensor_type_data_structures(request):
    network_connection_id = request.GET.get('connection_id')
    sensor_type = request.GET.get('sensor_type')
    
    if not network_connection_id:
        response = {
            "error": _("Network connection ID is required.")
        }
        return JsonResponse(response, status=400)
    
    if not sensor_type:
        response = {
            "error": _("Sensor type is required.")
        }
        return JsonResponse(response, status=400)
    
    network_conn = get_object_or_none(WeatherLinkConnection, pk=network_connection_id)
    if not network_conn:
        response = {
            "error": _("The selected connection is not a Weatherlink Connection")
        }
        
        return JsonResponse(response, status=400)
    
    client = network_conn.get_api_client()
    sensor_type_data_structures = client.get_data_structures_for_sensor_type(sensor_type)
    
    if not sensor_type_data_structures:
        response = {
            "error": _("No data structure found for the provided sensor type.")
        }
        return JsonResponse(response, status=400)
    
    sensor_type_data_structures = [
        {
            "label": f"{ds.get('description')} ({ds.get('data_structure_type')})",
            "value": ds.get('data_structure_type'),
        }
        for ds in sensor_type_data_structures
    ]
    
    return JsonResponse(sensor_type_data_structures, safe=False)


def get_weatherlink_sensor_type_data_structure_items(request):
    network_connection_id = request.GET.get('connection_id')
    sensor_type = request.GET.get('sensor_type')
    data_structure_type = request.GET.get('data_structure_type')
    
    if not network_connection_id:
        response = {
            "error": _("Network connection ID is required.")
        }
        return JsonResponse(response, status=400)
    
    if not sensor_type:
        response = {
            "error": _("Sensor type is required.")
        }
        return JsonResponse(response, status=400)
    
    if not data_structure_type:
        response = {
            "error": _("Data structure type is required.")
        }
        return JsonResponse(response, status=400)
    
    network_conn = get_object_or_none(WeatherLinkConnection, pk=network_connection_id)
    if not network_conn:
        response = {
            "error": _("The selected connection is not a Weatherlink Connection")
        }
        
        return JsonResponse(response, status=400)
    
    client = network_conn.get_api_client()
    data_structure_items = client.get_data_sensor_type_data_structure_items_by_id(sensor_type, data_structure_type)
    
    if not data_structure_items:
        response = {
            "error": _("No data structure items found for the provided sensor type.")
        }
        return JsonResponse(response, status=400)
    
    sensor_type_data_structure_items = [
        {
            "label": f"{ds_key} ({ds_meta.get('units')})",
            "value": ds_key,
        }
        for ds_key, ds_meta in data_structure_items.items()
    ]
    
    return JsonResponse(sensor_type_data_structure_items, safe=False)
