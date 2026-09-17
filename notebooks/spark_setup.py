"""Import this module from a script in notebooks/ to start Spark automatically."""
from pyspark.sql import functions as F

from weather_analysis.notebook import NotebookSession, chronological_split, past_average

session = NotebookSession()
spark, weather, daily, locations = session.spark, session.weather, session.daily, session.locations

__all__ = ['spark', 'weather', 'daily', 'locations', 'session', 'F',
           'chronological_split', 'past_average']
