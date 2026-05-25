from pyspark import pipelines as dp
from pyspark.sql.functions import *


@dp.materialized_view(name="gold.fct_daily_metrics")
def fct_daily_metrics():
    """Daily ops KPIs at the date grain. One row per day."""
    orders = spark.read.table("food_delivery.gold.fct_orders")

    return (
        orders
        .withColumn("order_date", to_date(col("placed_at")))
        .groupBy("order_date")
        .agg(
            # Volume
            count("*").alias("total_orders"),
            sum(when(col("final_status") == "delivered", 1).otherwise(0)).alias("delivered_orders"),
            sum(when(col("final_status") == "cancelled", 1).otherwise(0)).alias("cancelled_orders"),
            sum(when(col("final_status").isin("placed", "confirmed", "prepared", "in_transit"), 1).otherwise(0)).alias("in_progress_orders"),

            # Revenue (delivered orders only — cancelled orders shouldn't count toward GMV)
            sum(when(col("final_status") == "delivered", col("gmv"))).alias("total_gmv"),
            avg(when(col("final_status") == "delivered", col("gmv"))).alias("avg_order_value"),
            sum(when(col("final_status") == "delivered", col("discount"))).alias("total_discount_given"),

            # Timing (delivered orders only)
            avg(
                when(
                    col("final_status") == "delivered",
                    (unix_timestamp("delivered_at") - unix_timestamp("placed_at")) / 60.0
                )
            ).alias("avg_delivery_time_minutes"),
            avg(
                when(
                    col("final_status") == "delivered",
                    (unix_timestamp("prepared_at") - unix_timestamp("confirmed_at")) / 60.0
                )
            ).alias("avg_prep_time_minutes"),

            # Activity
            countDistinct("customer_id").alias("unique_customers"),
            countDistinct("vendor_id").alias("unique_vendors_active"),
            countDistinct("driver_id").alias("unique_drivers_active"),
        )
        # Computed rates
        .withColumn("cancellation_rate", round(col("cancelled_orders") / col("total_orders"), 4))
        .withColumn("completion_rate",   round(col("delivered_orders") / col("total_orders"), 4))
        # Round timing for readability
        .withColumn("avg_delivery_time_minutes", round(col("avg_delivery_time_minutes"), 2))
        .withColumn("avg_prep_time_minutes",     round(col("avg_prep_time_minutes"), 2))
        .withColumn("avg_order_value",            round(col("avg_order_value"), 2))
        .orderBy("order_date")
    )
