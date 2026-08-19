import logging

from adl.core.registries import Plugin

logger = logging.getLogger(__name__)


class WeatherLinkPlugin(Plugin):
    type = "adl_weatherlink_plugin"
    label = "ADL WeatherLink Plugin"

    client = None

    def get_urls(self):
        return []

    def get_station_data(self, station_link, start_date=None, end_date=None):
        """
        Fetches the station data for a given station link.

        :param station_link: The station link to fetch data for.
        :param start_date: The start date for the data collection (optional).
        :param end_date: The end date for the data collection (optional).
        :return: A list of observation records.
        """
        logger.debug(f"[WEATHERLINK_PLUGIN] Fetching data for station link {station_link}")

        station_variable_mappings = station_link.get_variable_mappings()
        unique_sensor_types = set(v_mapping.weatherlink_sensor_type for v_mapping in station_variable_mappings)

        weatherlink_client = station_link.network_connection.get_api_client()

        data_records, sources_count = weatherlink_client.get_current_conditions(
            station_link.weatherlink_station_id,
            unique_sensor_types,
            start_date=start_date,
            end_date=end_date
        )

        # Duck-typed sources-count handover: core stores this on the run's
        # activity log so "looked, found nothing" (0) stays distinguishable
        # from "never looked" (None). Committed only here, once the response
        # is parsed — a call that raised leaves the attribute None, and core's
        # evidence rule abstains on NULL rather than blaming the source for a
        # run that never got an answer.
        if getattr(station_link, "adl_sources_count", None) is None:
            station_link.adl_sources_count = 0
        station_link.adl_sources_count += sources_count

        return data_records
