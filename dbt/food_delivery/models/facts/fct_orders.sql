with events as (
    select * from {{ source('silver', 'order_events') }}
),

agg as (
    select
        order_id,

        any_value(customer_id) as customer_id,
        any_value(vendor_id) as vendor_id,
        any_value(driver_id) as driver_id,

        max(case when event_type = 'order_placed' then occurred_at end) as placed_at,
        max(case when event_type = 'order_confirmed' then occurred_at end) as confirmed_at,
        max(case when event_type = 'order_prepared' then occurred_at end) as prepared_at,
        max(case when event_type = 'order_picked_up' then occurred_at end) as picked_up_at,
        max(case when event_type = 'order_delivered' then occurred_at end) as delivered_at,
        max(case when event_type = 'order_cancelled' then occurred_at end) as cancelled_at,

        max(case when event_type = 'order_placed' then gmv end) as gmv,
        max(case when event_type = 'order_placed' then food_cost end) as food_cost,
        max(case when event_type = 'order_placed' then delivery_fee end) as delivery_fee,
        max(case when event_type = 'order_placed' then service_fee end) as service_fee,
        max(case when event_type = 'order_placed' then discount end) as discount,

        max(case when event_type = 'order_cancelled' then cancelled_by end) as cancelled_by,
        max(case when event_type = 'order_cancelled' then cancel_reason end) as cancel_reason

    from events
    group by order_id
)

select
    *,
    case
        when delivered_at  is not null then 'delivered'
        when cancelled_at  is not null then 'cancelled'
        when picked_up_at  is not null then 'in_transit'
        when prepared_at   is not null then 'prepared'
        when confirmed_at  is not null then 'confirmed'
        when placed_at     is not null then 'placed'
        else 'unknown'
    end as final_status
from agg