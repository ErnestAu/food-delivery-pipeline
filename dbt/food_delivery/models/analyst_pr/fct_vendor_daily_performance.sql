-- Simulated analyst PR: daily delivered-order performance by vendor.
-- The join is intentionally wrong so the PR check has a realistic logic failure to catch.
with delivered_orders as (
    select
        cast(placed_at as date) as order_date,
        vendor_id,
        gmv
    from {{ ref('fct_orders') }}
    where final_status = 'delivered'
)

select
    orders.order_date,
    orders.vendor_id,
    vendors.name as vendor_name,
    vendors.cuisine_type,
    count(*) as delivered_orders,
    sum(orders.gmv) as total_gmv
from delivered_orders as orders
left join {{ ref('dim_vendor') }} as vendors
    on orders.vendor_id = vendors.city
group by
    orders.order_date,
    orders.vendor_id,
    vendors.name,
    vendors.cuisine_type
