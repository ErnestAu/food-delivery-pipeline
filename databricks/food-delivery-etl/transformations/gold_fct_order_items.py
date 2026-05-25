from pyspark import pipelines as dp
from pyspark.sql.functions import *


@dp.materialized_view(name="gold.fct_order_items")
def fct_order_items():
    return (
        spark.read.table("food_delivery.silver.order_events")
        # items only exist on the order_placed event
        .filter(col("event_type") == "order_placed")
        .select(
            "order_id",
            "customer_id",
            "vendor_id",
            "occurred_at",
            explode("items").alias("item"),
        )
        .select(
            "order_id",
            "customer_id",
            "vendor_id",
            "occurred_at",
            col("item.menu_item_id").alias("menu_item_id"),
            col("item.name").alias("item_name"),
            col("item.quantity").alias("quantity"),
            col("item.unit_price").alias("unit_price"),
            col("item.line_total").alias("line_total"),
        )
    )
