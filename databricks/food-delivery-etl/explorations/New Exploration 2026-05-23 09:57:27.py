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
