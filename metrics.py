import re
import time
from datetime import datetime

import requests

_cache_value: str | None = None
_cache_ts: int | None = None

FIELD_DESCRIPTIONS = {
    'cloud_cover': 'Total cloud cover at timestamp (%)',
    'condition': 'Current weather conditions',
    'dew_point': 'Dew point at timestamp, 2 m above ground (°C)',
    'icon': 'Icon alias suitable for the current weather conditions',
    'pressure_msl': 'Atmospheric pressure at timestamp, reduced to mean sea level (hPa)',
    'relative_humidity': 'Relative humidity at timestamp (%)',
    'temperature': 'Air temperature at timestamp, 2 m above the ground (°C)',
    'visibility': 'Visibility at timestamp (m)',
    'precipitation': 'Total precipitation during previous 60 minutes (mm)',
    'solar': 'Solar irradiation during previous 60 minutes (Wh/m²)',
    'sunshine': 'Sunshine duration during previous 60 minutes (min)',
    'wind_direction': 'Mean wind direction during previous hour, 10 m above the ground (°)',
    'wind_speed': 'Mean wind speed during previous hour, 10 m above the ground (m/s)',
    'wind_gust_direction': 'Direction of maximum wind gust during previous hour, 10 m above the ground (°)',
    'wind_gust_speed': 'Speed of maximum wind gust during previous hour, 10 m above the ground (m/s)',
    'precipitation_probability': 'Probability of more than 0.1 mm of precipitation in the previous hour (%)',
    'precipitation_probability_6h': 'Probability of more than 0.2 mm of precipitation in the previous 6 hours (%)',
}


def generate(*, lon: str, lat: str) -> str:
    global _cache_value, _cache_ts

    now = int(time.time())

    if not _cache_ts or now - _cache_ts > 15 * 60:  # cache 15min
        output_lines: list[str] = []
        seen_metrics: set[str] = set()

        resp = requests.get(
            'https://api.brightsky.dev/weather',
            params={
                'lon': lon,
                'lat': lat,
                'date': time.strftime('%Y-%m-%d')
            })

        if resp.status_code != 200:
            raise Exception(f'wrong response code={resp.status_code}; text={resp.text}')

        data = resp.json()
        source_by_id = {source.get('id'): source for source in data.get('sources', []) if source.get('id') is not None}

        for record in data.get('weather', []):
            timestamp = int(datetime.fromisoformat(record['timestamp']).timestamp() * 1000)

            for field_name, value in record.items():
                if field_name not in ('timestamp', 'source_id') and (type(value) in (int, float) or field_name  == 'condition'):

                    labels = {
                        "lon": lon,
                        "lat": lat,
                    }
                    source_id = record.get('fallback_source_ids', {}).get(field_name) or record.get('source_id')
                    if source_info := source_by_id.get(source_id):
                        for source_field in ['id', 'observation_type', 'lat', 'lon', 'height', 'station_name', 'distance']:
                            if source_info.get(source_field) is not None:
                                source_value = source_info[source_field]
                                if source_field in ('height', 'distance'):
                                    source_value = int(source_value)  # convert to int, as the API returns float for these fields
                                labels[f'source_{source_field}'] = source_value
                    if field_name == 'condition':
                        if value is None:
                            continue
                        labels['condition'] = value
                        if icon := record.get('icon'):
                            labels['icon'] = icon
                        value = 1  # for condition, we just set the value to 1, as the actual condition is in the label 
                    labels_str = ','.join(f'{k}="{str(v).replace("\"", "")}"' for k, v in labels.items())

                    metric_name = 'brightsky_dev_' + re.sub(r'[^a-zA-Z0-9_]', '_', field_name).strip('_')
                    if metric_name not in seen_metrics:
                        seen_metrics.add(metric_name)
                        if field_name in FIELD_DESCRIPTIONS:
                            output_lines.append(f'# HELP {metric_name} {FIELD_DESCRIPTIONS[field_name]}')
                        output_lines.append(f'# TYPE {metric_name} gauge')

                    output_lines.append(f'{metric_name}{{{labels_str}}} {value} {timestamp}')

        output = '\n'.join(output_lines) + ('\n' if output_lines else '')
        _cache_value = output
        _cache_ts = now

    return _cache_value


if __name__ == '__main__':
    print(generate(lon='13.5', lat='52.5'))