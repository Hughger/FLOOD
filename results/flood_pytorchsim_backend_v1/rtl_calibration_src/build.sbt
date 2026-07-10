ThisBuild / scalaVersion := "2.13.12"
ThisBuild / organization := "flood.calibration"

lazy val root = (project in file("."))
  .settings(
    name := "flood-rtl-calibration",
    libraryDependencies ++= Seq(
      "edu.berkeley.cs" %% "chisel3" % "3.6.0"
    ),
    addCompilerPlugin("edu.berkeley.cs" % "chisel3-plugin" % "3.6.0" cross CrossVersion.full),
    Compile / scalaSource := baseDirectory.value / "src" / "main" / "scala",
    Test / scalaSource := baseDirectory.value / "src" / "test" / "scala"
  )
