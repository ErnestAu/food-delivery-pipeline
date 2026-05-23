from pyspark import pipelines as dp
from pyspark.sql.functions import *
from pyspark.sql.types import *

# checkpoint_path = "s3://dev-bucket/_checkpoint/dev_table"

# (spark.readStream
#   .format("cloudFiles")
#   .option("cloudFiles.format", "json")
#   .option("cloudFiles.schemaLocation", checkpoint_path)
#   .load("s3://autoloader-source/json-data")
#   .writeStream
#   .option("checkpointLocation", checkpoint_path)
#   .trigger(availableNow=True)
#   .toTable("dev_catalog.dev_database.dev_table"))

# def test():
#   return (
#      spark.readStream.format('cloudFiles')\
#      .option('cloudFiles.format', 'csv')\
#      .load(f's3://food-delivery-pipeline-102947735140-ap-southeast-1-an/data/raw/dims/customers.csv')\
#      .limit(10)\
#      .display()
#  )

# files = [
#   "customers.csv",
#   "drivers.csv",
#   "menu_items.csv",
#   "vendors.csv"
#   ]


dims_path = "s3://food-delivery-pipeline-102947735140-ap-southeast-1-an/data/raw/dims"



@dp.materialized_view()
def dim_customers():
  df = spark.read\
    .format('csv')\
    .option("header", "true")\
    .option("inferSchema", "true")\
    .load(f"{dims_path}/customers.csv")
  
  return df

@dp.materialized_view()
def dim_drivers():
  df = spark.read\
    .format('csv')\
    .option("header", "true")\
    .option("inferSchema", "true")\
    .load(f"{dims_path}/drivers.csv")
  
  return df

@dp.materialized_view()
def dim_menu_items():
  df = spark.read\
    .format('csv')\
    .option("header", "true")\
    .option("inferSchema", "true")\
    .load(f"{dims_path}/menu_items.csv")
  
  return df

@dp.materialized_view()
def dim_vendors():
  df = spark.read\
    .format('csv')\
    .option("header", "true")\
    .option("inferSchema", "true")\
    .load(f"{dims_path}/vendors.csv")
  
  return df
