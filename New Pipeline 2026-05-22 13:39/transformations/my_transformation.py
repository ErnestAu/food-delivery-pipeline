checkpoint_path = "s3://dev-bucket/_checkpoint/dev_table"

(spark.readStream
  .format("cloudFiles")
  .option("cloudFiles.format", "json")
  .option("cloudFiles.schemaLocation", checkpoint_path)
  .load("s3://autoloader-source/json-data")
  .writeStream
  .option("checkpointLocation", checkpoint_path)
  .trigger(availableNow=True)
  .toTable("dev_catalog.dev_database.dev_table"))