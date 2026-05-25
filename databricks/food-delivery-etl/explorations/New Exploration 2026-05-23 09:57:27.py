# Databricks notebook source

dbutils.fs.ls("s3://food-delivery-pipeline-102947735140-ap-southeast-1-an/data/raw/")

df = spark.read.format('csv').load('s3://food-delivery-pipeline-102947735140-ap-southeast-1-an/data/raw/dims/customers.csv').limit(10).display()
df2 = spark.read.format('json').load('s3://food-delivery-pipeline-102947735140-ap-southeast-1-an/data/raw/order_events/2024-01-15/00/events_00_0cc9b206.jsonl').limit(10).display()


# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT * FROM food_delivery.bronze.dim_customers

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT * FROM food_delivery.bronze.order_events 
# MAGIC WHERE customer_id = "cust_f232810e77b5"
# MAGIC ORDER BY occurred_at
# MAGIC LIMIT 50
# MAGIC

# COMMAND ----------

from pyspark.sql.functions import *

df = (
    spark.read
        .table("food_delivery.bronze.order_events")
        .withColumn("occurred_at", to_timestamp(col("occurred_at")))
        .withWatermark("occurred_at", "1 hours")
        .dropDuplicates(["event_id"])
        # flatten payload struct into top-level columns
        .select(
            "event_id",
            "event_type",
            "order_id",
            "occurred_at",
            "customer_id",
            "vendor_id",
            "driver_id",
            col("payload.gmv").alias("gmv"),
            col("payload.food_cost").alias("food_cost"),
            col("payload.delivery_fee").alias("delivery_fee"),
            col("payload.service_fee").alias("service_fee"),
            col("payload.discount").alias("discount"),
            col("payload.delivery_address").alias("delivery_address"),
            col("payload.estimated_prep_minutes").alias("estimated_prep_minutes"),
            col("payload.cancelled_by").alias("cancelled_by"),
            col("payload.reason").alias("cancel_reason"),
            col("payload.vehicle_type").alias("vehicle_type"),
            col("payload.items").alias("items"),
        )
)


df.display()
