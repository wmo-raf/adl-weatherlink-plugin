from adl.core.models import NetworkConnection, StationLink, DataParameter, Unit
from django.db import models
from django.utils.translation import gettext_lazy as _
from modelcluster.fields import ParentalKey
from timezone_field import TimeZoneField
from wagtail.admin.panels import MultiFieldPanel, FieldPanel, InlinePanel
from wagtail.models import Orderable

from .client import WeatherLinkAPIClient
from .validators import validate_start_date
from .widgets import (
    WeatherLinkStationSelectWidget,
    WeatherLinkSensorTypeSelectWidget,
    WeatherLinkStationDataStructureSelectWidget,
    WeatherLinkStationDataStructureItemSelectWidget
)


class WeatherLinkConnection(NetworkConnection):
    """
    Model representing a connection to a WeatherLink API.
    """
    station_link_model_string_label = "adl_weatherlink_plugin.WeatherLinkStationLink"
    
    api_base_url = models.URLField(max_length=255, verbose_name="API Base URL",
                                   default="https://api.weatherlink.com/v2")
    api_key = models.CharField(max_length=255, verbose_name="API Key")
    api_secret = models.CharField(max_length=255, verbose_name="API Secret")
    
    panels = NetworkConnection.panels + [
        MultiFieldPanel([
            FieldPanel("api_base_url"),
            FieldPanel("api_key"),
            FieldPanel("api_secret"),
        ], heading=_("WeatherLink API Credentials")),
    ]
    
    class Meta:
        verbose_name = "WeatherLink Connection"
        verbose_name_plural = "WeatherLink Connections"
    
    def get_extra_model_admin_links(self):
        return []
    
    def get_api_client(self):
        """
        Returns the WeatherLink API client instance.
        """
        return WeatherLinkAPIClient(api_key=self.api_key, api_secret=self.api_secret, base_url=self.api_base_url)


class WeatherLinkStationLink(StationLink):
    """
    Model representing a link to a WeatherLink station.
    """
    weatherlink_station_id = models.CharField(max_length=255, verbose_name="WeatherLink Station ID")
    timezone = TimeZoneField(default='UTC', verbose_name=_("Station Timezone"),
                             help_text=_("Timezone used by the station for recording observations"))
    start_date = models.DateTimeField(blank=True, null=True, validators=[validate_start_date],
                                      verbose_name=_("Start Date"),
                                      help_text=_("Start date for data pulling. Select a past date to include the "
                                                  "historical data. Leave blank for collecting realtime data only"), )
    
    sensor_type = models.CharField(max_length=255, verbose_name="WeatherLink Sensor Type")
    data_structure_type = models.CharField(max_length=255, verbose_name="WeatherLink Data Structure Type")
    
    panels = StationLink.panels + [
        FieldPanel("weatherlink_station_id", widget=WeatherLinkStationSelectWidget),
        FieldPanel("sensor_type", widget=WeatherLinkSensorTypeSelectWidget),
        FieldPanel("data_structure_type", widget=WeatherLinkStationDataStructureSelectWidget),
        FieldPanel("timezone"),
        FieldPanel("start_date"),
        InlinePanel("variable_mappings", label=_("Station Variable Mapping"), heading=_("Station Variable Mappings")),
    ]
    
    class Meta:
        verbose_name = "WeatherLink Station Link"
        verbose_name_plural = "WeatherLink Stations Link"
    
    def __str__(self):
        return f"{self.weatherlink_station_id} - {self.station} - {self.station.wigos_id}"


class WeatherLinkStationLinkVariableMapping(Orderable):
    station_link = ParentalKey(WeatherLinkStationLink, on_delete=models.CASCADE, related_name="variable_mappings")
    adl_parameter = models.ForeignKey(DataParameter, on_delete=models.CASCADE, verbose_name=_("ADL Parameter"))
    weatherlink_parameter = models.CharField(max_length=255, verbose_name=_("WeatherLink Parameter"))
    weatherlink_parameter_unit = models.ForeignKey(Unit, on_delete=models.CASCADE,
                                                   verbose_name=_("WeatherLink Parameter Unit"))
    
    panels = [
        FieldPanel("adl_parameter"),
        FieldPanel("weatherlink_parameter", widget=WeatherLinkStationDataStructureItemSelectWidget),
        FieldPanel("weatherlink_parameter_unit"),
    ]
