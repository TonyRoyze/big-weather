package lk.ac.ds4004.weather

import java.nio.file.{Files, Path, Paths}
import com.fasterxml.jackson.databind.ObjectMapper
import org.apache.spark.sql.{SaveMode, SparkSession}

object WeatherJob {
  final case class Config(input: Path = Paths.get("data/raw"), output: Path = Paths.get("data/processed"))

  private def parseArgs(args: Array[String]): Config = args.toList match {
    case Nil => Config()
    case "--input" :: input :: "--output" :: output :: Nil => Config(Paths.get(input), Paths.get(output))
    case _ => throw new IllegalArgumentException("Usage: WeatherJob [--input PATH --output PATH]")
  }

  def main(args: Array[String]): Unit = {
    val config = parseArgs(args)
    val started = System.nanoTime()
    implicit val spark: SparkSession = SparkSession.builder()
      .appName("Big Weather Processing")
      .master(sys.env.getOrElse("SPARK_MASTER", "local[4]"))
      .config("spark.sql.session.timeZone", "UTC")
      .config("spark.sql.shuffle.partitions", "4")
      .config("spark.driver.host", "127.0.0.1")
      .getOrCreate()
    spark.sparkContext.setLogLevel("WARN")

    try {
      val weather = spark.read.parquet(config.input.resolve("weather").toString).repartition(4).cache()
      val locations = spark.read.parquet(config.input.resolve("locations").toString)
      val validated = WeatherTransforms.validate(weather).cache()
      val enriched = WeatherTransforms.enrich(validated, locations).cache()
      val daily = WeatherTransforms.dailyMetrics(enriched).cache()

      enriched.write.mode(SaveMode.Overwrite).partitionBy("elevation_band")
        .parquet(config.output.resolve("enriched_weather").toString)
      WeatherTransforms.summaries(enriched).write.mode(SaveMode.Overwrite)
        .parquet(config.output.resolve("summaries").toString)
      daily.write.mode(SaveMode.Overwrite)
        .parquet(config.output.resolve("daily_metrics").toString)
      WeatherTransforms.yearlyMetrics(enriched).write.mode(SaveMode.Overwrite)
        .parquet(config.output.resolve("yearly_metrics").toString)
      WeatherTransforms.lapseRates(daily).write.mode(SaveMode.Overwrite)
        .parquet(config.output.resolve("lapse_rates").toString)
      val inputRows = weather.count()
      val validatedRows = validated.count()
      val outputRows = enriched.count()
      val metrics = new java.util.LinkedHashMap[String, Object]()
      metrics.put("input_rows", Long.box(inputRows))
      metrics.put("validated_rows", Long.box(validatedRows))
      metrics.put("rejected_or_duplicate_rows", Long.box(inputRows - validatedRows))
      metrics.put("unmatched_location_rows", Long.box(validatedRows - outputRows))
      metrics.put("output_rows", Long.box(outputRows))
      metrics.put("daily_rows", Long.box(daily.count()))
      metrics.put("input_partitions", Int.box(weather.rdd.getNumPartitions))
      metrics.put("shuffle_partitions", Int.box(4))
      metrics.put("spark_master", spark.sparkContext.master)
      metrics.put("spark_version", spark.version)
      metrics.put("completed_at", java.time.Instant.now().toString)
      metrics.put("duration_seconds", Double.box((System.nanoTime() - started) / 1e9))
      Files.writeString(config.output.resolve("pipeline_metrics.json"),
        new ObjectMapper().writerWithDefaultPrettyPrinter().writeValueAsString(metrics))
    } finally {
      spark.stop()
    }
  }
}
