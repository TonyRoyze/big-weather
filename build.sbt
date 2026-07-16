ThisBuild / organization := "lk.ac.ds4004"
ThisBuild / version := "0.1.0-SNAPSHOT"
ThisBuild / scalaVersion := "2.13.16"

lazy val sparkVersion = "4.0.1"

lazy val root = (project in file("."))
  .settings(
    name := "big-weather",
    libraryDependencies ++= Seq(
      "org.apache.spark" %% "spark-sql" % sparkVersion,
      "org.apache.spark" %% "spark-mllib" % sparkVersion,
      "org.scalatest" %% "scalatest" % "3.2.19" % Test
    ),
    Test / fork := true,
    Test / parallelExecution := false,
    Test / javaOptions ++= Seq(
      "-Xmx2G",
      "-Dio.netty.tryReflectionSetAccessible=true",
      "--add-opens=java.base/sun.nio.ch=ALL-UNNAMED"
    ),
    Compile / run / fork := true,
    Compile / run / javaOptions ++= Seq(
      "-Xmx4G",
      "-Dio.netty.tryReflectionSetAccessible=true",
      "--add-opens=java.base/sun.nio.ch=ALL-UNNAMED"
    )
  )

