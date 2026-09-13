package lk.ac.ds4004.weather

import java.sql.Timestamp
import org.apache.spark.sql.SparkSession
import org.apache.spark.sql.functions._
import org.scalatest.BeforeAndAfterAll
import org.scalatest.funsuite.AnyFunSuite

class WeatherTransformsSpec extends AnyFunSuite with BeforeAndAfterAll {
  implicit var spark: SparkSession = _

  override def beforeAll(): Unit = {
    spark = SparkSession.builder().master("local[2]").appName("weather-tests")
      .config("spark.ui.enabled", "false").config("spark.driver.host", "127.0.0.1").getOrCreate()
    spark.sparkContext.setLogLevel("ERROR")
  }

  override def afterAll(): Unit = if (spark != null) spark.stop()

  test("elevation boundaries match the proposal") {
    val session = spark
    import session.implicits._
    val actual = Seq(0.0, 199.9, 200.0, 999.9, 1000.0, 2999.9, 3000.0).toDF("metres")
      .select(WeatherTransforms.elevationBand(col("metres")).as[String]).as[String].collect()
    assert(actual === Array("lowland", "lowland", "midland", "midland", "highland", "highland", "alpine"))
  }

  test("season mapping accounts for hemisphere") {
    val session = spark
    import session.implicits._
    val actual = Seq((1, 10.0), (1, -10.0), (7, 10.0), (7, -10.0)).toDF("month", "latitude")
      .select(WeatherTransforms.season(col("month"), col("latitude")).as[String]).as[String].collect()
    assert(actual === Array("winter", "summer", "summer", "winter"))
  }

  test("validation removes duplicates and impossible observations") {
    val session = spark
    import session.implicits._
    val now = Timestamp.valueOf("2024-01-01 00:00:00")
    val rows = Seq(
      ("a", now, 20.0, 0.0, 2.0, 60.0, 2024, now),
      ("a", now, 20.0, 0.0, 2.0, 60.0, 2024, now),
      ("b", now, 200.0, 0.0, 2.0, 60.0, 2024, now),
      ("c", now, 20.0, Double.NaN, 2.0, 60.0, 2024, now),
      ("d", now, 20.0, 0.0, Double.PositiveInfinity, 60.0, 2024, now)
    ).toDF(WeatherTransforms.WeatherSchema.fieldNames: _*)
    assert(WeatherTransforms.validate(rows).count() === 1)
  }
}
