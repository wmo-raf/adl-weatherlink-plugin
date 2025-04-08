# Generated by Django 5.1.4 on 2025-04-08 12:23

import adl_weatherlink_plugin.validators
import django.db.models.deletion
import timezone_field.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('core', '0016_alter_dataparameter_options_alter_unit_options'),
    ]

    operations = [
        migrations.CreateModel(
            name='WeatherLinkConnection',
            fields=[
                ('networkconnection_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='core.networkconnection')),
                ('api_base_url', models.URLField(default='https://api.weatherlink.com/v2', max_length=255, verbose_name='API Base URL')),
                ('api_key', models.CharField(max_length=255, verbose_name='API Key')),
                ('api_secret', models.CharField(max_length=255, verbose_name='API Secret')),
            ],
            options={
                'verbose_name': 'WeatherLink Connection',
                'verbose_name_plural': 'WeatherLink Connections',
            },
            bases=('core.networkconnection',),
        ),
        migrations.CreateModel(
            name='WeatherLinkStationLink',
            fields=[
                ('stationlink_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='core.stationlink')),
                ('weatherlink_station_id', models.CharField(max_length=255, verbose_name='WeatherLink Station ID')),
                ('timezone', timezone_field.fields.TimeZoneField(default='UTC', help_text='Timezone used by the station for recording observations', verbose_name='Station Timezone')),
                ('start_date', models.DateTimeField(blank=True, help_text='Start date for data pulling. Select a past date to include the historical data. Leave blank for collecting realtime data only', null=True, validators=[adl_weatherlink_plugin.validators.validate_start_date], verbose_name='Start Date')),
                ('sensor_type', models.CharField(max_length=255, verbose_name='WeatherLink Sensor Type')),
                ('data_structure_type', models.CharField(max_length=255, verbose_name='WeatherLink Data Structure Type')),
            ],
            options={
                'verbose_name': 'WeatherLink Station Link',
                'verbose_name_plural': 'WeatherLink Stations Link',
            },
            bases=('core.stationlink',),
        ),
    ]
