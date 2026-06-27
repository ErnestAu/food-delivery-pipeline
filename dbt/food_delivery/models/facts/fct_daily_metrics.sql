-- Daily ops KPIs at the date grain. One row per day.
with orders as (
    select
        *,
        to_date(placed_at) as order_date
    from {{ ref('fct_orders') }}
),

agg as (
    select
        order_date,

        count(*) as total_orders,
        sum(case when final_status = 'delivered' then 1 else 0 end) as delivered_orders,
        sum(case when final_status = 'cancelled' then 1 else 0 end) as cancelled_orders,
        sum(case when final_status in ('placed', 'confirmed', 'prepared', 'in_transit') then 1 else 0 end) as in_progress_orders,

        sum(case when final_status = 'delivered' then gmv end) as total_gmv,
        avg(case when final_status = 'delivered' then gmv end) as avg_order_value,
        sum(case when final_status = 'delivered' then discount end) as total_discount_given,

        avg(case when final_status = 'delivered'
            then (unix_timestamp(delivered_at) - unix_timestamp(placed_at)) / 60.0
        end) as avg_delivery_time_minutes,
        avg(case when final_status = 'delivered'
            then (unix_timestamp(prepared_at) - unix_timestamp(confirmed_at)) / 60.0
        end) as avg_prep_time_minutes,

        count(distinct customer_id) as unique_customers,
        count(distinct vendor_id) as unique_vendors_active,
        count(distinct driver_id) as unique_drivers_active

    from orders
    group by order_date
)

select
    order_date,
    total_orders,
    delivered_orders,
    cancelled_orders,
    in_progress_orders,
    total_gmv,
    round(avg_order_value, 2) as avg_order_value,
    total_discount_given,
    round(avg_delivery_time_minutes, 2) as avg_delivery_time_minutes,
    round(avg_prep_time_minutes, 2) as avg_prep_time_minutes,
    unique_customers,
    unique_vendors_active,
    unique_drivers_active,
    round(cancelled_orders / total_orders, 4) as cancellation_rate,
    round(delivered_orders / total_orders, 4) as completion_rate
from agg
order by order_date
