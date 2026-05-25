from pyspark import pipelines as dp
from pyspark.sql.functions import *


@dp.materialized_view(name="gold.fct_orders")
def fct_orders():
    events = spark.read.table("food_delivery.silver.order_events")

    return (
        events
        .groupBy("order_id")
        .agg(
            # FKs
            first("customer_id", ignorenulls=True).alias("customer_id"),
            first("vendor_id", ignorenulls=True).alias("vendor_id"),
            first("driver_id", ignorenulls=True).alias("driver_id"),

            # Lifecycle timestamps
            max(when(col("event_type") == "order_placed",    col("occurred_at"))).alias("placed_at"),
            max(when(col("event_type") == "order_confirmed", col("occurred_at"))).alias("confirmed_at"),
            max(when(col("event_type") == "order_prepared",  col("occurred_at"))).alias("prepared_at"),
            max(when(col("event_type") == "order_picked_up", col("occurred_at"))).alias("picked_up_at"),
            max(when(col("event_type") == "order_delivered", col("occurred_at"))).alias("delivered_at"),
            max(when(col("event_type") == "order_cancelled", col("occurred_at"))).alias("cancelled_at"),

            # Measures (only populated on order_placed event)
            max(when(col("event_type") == "order_placed", col("gmv"))).alias("gmv"),
            max(when(col("event_type") == "order_placed", col("food_cost"))).alias("food_cost"),
            max(when(col("event_type") == "order_placed", col("delivery_fee"))).alias("delivery_fee"),
            max(when(col("event_type") == "order_placed", col("service_fee"))).alias("service_fee"),
            max(when(col("event_type") == "order_placed", col("discount"))).alias("discount"),

            # Cancellation context
            max(when(col("event_type") == "order_cancelled", col("cancelled_by"))).alias("cancelled_by"),
            max(when(col("event_type") == "order_cancelled", col("cancel_reason"))).alias("cancel_reason"),
        )
        .withColumn(
            "final_status",
            when(col("delivered_at").isNotNull(),  "delivered")
            .when(col("cancelled_at").isNotNull(), "cancelled")
            .when(col("picked_up_at").isNotNull(), "in_transit")
            .when(col("prepared_at").isNotNull(), "prepared")
            .when(col("confirmed_at").isNotNull(), "confirmed")
            .when(col("placed_at").isNotNull(),    "placed")
            .otherwise("unknown")
        )
    )
