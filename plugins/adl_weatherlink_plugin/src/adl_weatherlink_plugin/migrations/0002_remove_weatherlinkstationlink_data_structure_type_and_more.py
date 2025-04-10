# Generated by Django 5.1.4 on 2025-04-09 08:18

import django.db.models.deletion
import modelcluster.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('adl_weatherlink_plugin', '0001_initial'),
        ('core', '0016_alter_dataparameter_options_alter_unit_options'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='weatherlinkstationlink',
            name='data_structure_type',
        ),
        migrations.RemoveField(
            model_name='weatherlinkstationlink',
            name='sensor_type',
        ),
        migrations.CreateModel(
            name='WeatherLinkStationLinkVariableMapping',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('sort_order', models.IntegerField(blank=True, editable=False, null=True)),
                ('weatherlink_sensor_type', models.CharField(max_length=255, verbose_name='WeatherLink Sensor Type')),
                ('weatherlink_data_structure_type', models.CharField(max_length=255, verbose_name='WeatherLink Data Structure Type')),
                ('weatherlink_parameter', models.CharField(max_length=255, verbose_name='WeatherLink Parameter')),
                ('adl_parameter', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='core.dataparameter', verbose_name='ADL Parameter')),
                ('station_link', modelcluster.fields.ParentalKey(on_delete=django.db.models.deletion.CASCADE, related_name='variable_mappings', to='adl_weatherlink_plugin.weatherlinkstationlink')),
                ('weatherlink_parameter_unit', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='core.unit', verbose_name='WeatherLink Parameter Unit')),
            ],
            options={
                'ordering': ['sort_order'],
                'abstract': False,
            },
        ),
    ]
