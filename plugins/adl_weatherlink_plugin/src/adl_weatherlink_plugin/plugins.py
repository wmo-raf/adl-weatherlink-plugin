from adl.core.registries import Plugin


class WeatherLinkPlugin(Plugin):
    type = "adl_weatherlink_plugin"
    label = "ADL WeatherLink Plugin"
    
    def get_urls(self):
        return []
    
    def get_data(self):
        return []
