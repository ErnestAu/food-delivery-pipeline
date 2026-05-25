from pyspark.sql.functions import *
from pyspark.sql.types import *
from pyspark import pipelines as dp

@dp.table(name = "food_delivery.silver.order_events")
def order_events():
    df = (
        spark.readStream
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

    return df