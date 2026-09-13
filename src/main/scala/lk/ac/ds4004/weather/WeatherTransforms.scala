package lk.ac.ds4004.weather

import org.apache.spark.ml.feature.VectorAssembler
import org.apache.spark.ml.regression.LinearRegression
import org.apache.spark.sql.{DataFrame, Row, SparkSession}
import org.apache.spark.sql.expressions.Window
import org.apache.spark.sql.functions._
import org.apache.spark.sql.types._

object WeatherTransforms {
  val WeatherSchema: StructType = StructType(Seq(
    StructField("location_id", StringType, nullable = false),
    StructField("timestamp", TimestampType, nullable = false),
    StructField("temperature_2m", DoubleType, nullable = true),
    StructField("precipitation", DoubleType, nullable = true),
    StructField("wind_speed_10m", DoubleType, nullable = true),
    StructField("relative_humidity_2m", DoubleType, nullable = true),
    StructField("source_year", IntegerType, nullable = false),
    StructField("ingested_at", TimestampType, nullable = false)
  ))

  def validate(weather: DataFrame): DataFrame = {
    val required = WeatherSchema.fieldNames.toSet
    val missing = required.diff(weather.columns.toSet)
    require(missing.isEmpty, s"Missing weather columns: ${missing.toSeq.sorted.mkString(", ")}")
    weather
      .filter(col("location_id").isNotNull && col("timestamp").isNotNull)
      .filter(col("temperature_2m").between(-100.0, 70.0))
      .filter(col("precipitation").between(0.0, Double.MaxValue))
      .filter(col("wind_speed_10m").between(0.0, Double.MaxValue))
      .filter(col("relative_humidity_2m").between(0.0, 100.0))
      .dropDuplicates("location_id", "timestamp")
  }

  def elevationBand(elevation: org.apache.spark.sql.Column): org.apache.spark.sql.Column =
    when(elevation < 200, "lowland")
      .when(elevation < 1000, "midland")
      .when(elevation < 3000, "highland")
      .otherwise("alpine")

  def season(monthColumn: org.apache.spark.sql.Column, latitude: org.apache.spark.sql.Column)
      : org.apache.spark.sql.Column = {
    val northern = when(monthColumn.isin(12, 1, 2), "winter")
      .when(monthColumn.isin(3, 4, 5), "spring")
      .when(monthColumn.isin(6, 7, 8), "summer")
      .otherwise("autumn")
    val southern = when(monthColumn.isin(12, 1, 2), "summer")
      .when(monthColumn.isin(3, 4, 5), "autumn")
      .when(monthColumn.isin(6, 7, 8), "winter")
      .otherwise("spring")
    when(latitude >= 0, northern).otherwise(southern)
  }

  def enrich(weather: DataFrame, locations: DataFrame): DataFrame = {
    val metadata = locations.select(
      "location_id", "name", "country", "region", "latitude", "longitude", "elevation_m"
    )
    weather.join(broadcast(metadata), Seq("location_id"), "inner")
      .withColumn("elevation_band", elevationBand(col("elevation_m")))
      .withColumn("date", to_date(col("timestamp")))
      .withColumn("year", year(col("timestamp")))
      .withColumn("season", season(month(col("timestamp")), col("latitude")))
  }

  def summaries(enriched: DataFrame): DataFrame =
    enriched.groupBy("elevation_band", "region", "season", "year")
      .agg(
        avg("temperature_2m").as("avg_temperature_c"),
        sum("precipitation").as("total_precipitation_mm"),
        avg("wind_speed_10m").as("avg_wind_speed_ms"),
        avg("relative_humidity_2m").as("avg_relative_humidity_pct"),
        count(lit(1)).as("observation_count")
      )

  def dailyMetrics(enriched: DataFrame): DataFrame = {
    val daily = enriched.groupBy(
      "location_id", "name", "region", "elevation_m", "elevation_band", "season", "date"
    ).agg(
      avg("temperature_2m").as("daily_avg_temperature_c"),
      sum("precipitation").as("daily_precipitation_mm"),
      avg("wind_speed_10m").as("daily_avg_wind_speed_ms"),
      count(lit(1)).as("observed_hours")
    )
    val rollingWindow = Window.partitionBy("location_id")
      .orderBy(unix_date(col("date"))).rangeBetween(-29, 0)
    daily.withColumn(
      "temperature_30d_rolling_avg_c",
      avg("daily_avg_temperature_c").over(rollingWindow)
    )
  }

  def yearlyMetrics(enriched: DataFrame): DataFrame = {
    val yearly = enriched.groupBy("location_id", "name", "region", "elevation_m", "year")
      .agg(avg("temperature_2m").as("annual_avg_temperature_c"))
    val yearWindow = Window.partitionBy("location_id").orderBy("year")
    yearly.withColumn(
      "temperature_yoy_change_c",
      col("annual_avg_temperature_c") - lag("annual_avg_temperature_c", 1).over(yearWindow)
    )
  }

  def lapseRates(daily: DataFrame)(implicit spark: SparkSession): DataFrame = {
    import spark.implicits._
    val regressionInput = daily
      .select("season", "elevation_m", "daily_avg_temperature_c")
      .na.drop()
    val seasons = regressionInput.select("season").distinct().as[String].collect().sorted
    val rows = seasons.flatMap { seasonName =>
      val seasonal = regressionInput.filter(col("season") === seasonName)
      if (seasonal.select("elevation_m").distinct().count() < 2) None
      else {
        val assembled = new VectorAssembler()
          .setInputCols(Array("elevation_m"))
          .setOutputCol("features")
          .transform(seasonal)
          .withColumnRenamed("daily_avg_temperature_c", "label")
        val model = new LinearRegression().setMaxIter(50).setRegParam(0.0).fit(assembled)
        Some((
          seasonName,
          model.coefficients(0),
          model.coefficients(0) * 1000.0,
          model.intercept,
          model.summary.r2,
          model.summary.rootMeanSquaredError,
          assembled.count()
        ))
      }
    }
    rows.toSeq.toDF(
      "season", "slope_c_per_m", "lapse_rate_c_per_km", "intercept_c", "r2", "rmse_c", "sample_size"
    )
  }
}
