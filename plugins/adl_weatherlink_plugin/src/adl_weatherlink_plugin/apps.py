from adl.core.registries import plugin_registry
from django.apps import AppConfig


class WeatherLinkPluginConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = "adl_weatherlink_plugin"
    
    def ready(self):
        from .plugins import WeatherLinkPlugin
        
        plugin_registry.register(WeatherLinkPlugin())
