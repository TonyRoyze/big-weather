"""Run: cd notebooks && ../.venv/bin/python spark_patterns.py

Copy this file for your own analysis. Spark starts on import; show/write/count
execute jobs. Collect only aggregated results for plotting.
"""
from spark_setup import F, past_average, session, weather

print('Available hourly columns:', weather.columns)
features = past_average(weather, 'temperature_2m', hours=24)
(features.groupBy('location_id', F.year('timestamp').alias('year'))
 .agg(F.avg('temperature_2m').alias('mean_temperature_c'),
      F.avg('temperature_2m_past_24h').alias('mean_past_temperature_c'),
      F.sum('precipitation').alias('annual_precipitation_mm'))
 .orderBy('location_id', 'year').show(20, truncate=False))
session.close()
