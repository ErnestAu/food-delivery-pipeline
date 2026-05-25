from pyspark import pipelines as dp


# Type 1 dims for v0 — straight pass-through from bronze.
# SCD2 is a v1 enhancement (requires dim mutations in the simulator first).


@dp.materialized_view(name="gold.dim_customer")
def dim_customer():
    return spark.read.table("food_delivery.bronze.dim_customers")


@dp.materialized_view(name="gold.dim_vendor")
def dim_vendor():
    return spark.read.table("food_delivery.bronze.dim_vendors")


@dp.materialized_view(name="gold.dim_driver")
def dim_driver():
    return spark.read.table("food_delivery.bronze.dim_drivers")


@dp.materialized_view(name="gold.dim_menu_item")
def dim_menu_item():
    return spark.read.table("food_delivery.bronze.dim_menu_items")
