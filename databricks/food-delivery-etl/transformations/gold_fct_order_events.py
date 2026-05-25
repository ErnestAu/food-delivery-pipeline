from pyspark import pipelines as dp
from pyspark.sql.functions import *


@dp.materialized_view(name="gold.fct_order_events")
def fct_order_events():
    """Slim event log at the event grain. Append-only source of truth for order lifecycle."""
    return (
        spark.read.table("food_delivery.silver.order_events")
        .select(
            "event_id",
            "event_type",
            "order_id",
            "occurred_at",
            "customer_id",
            "vendor_id",
            "driver_id",
            "cancelled_by",
            "cancel_reason",
        )
    )
