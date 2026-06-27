with events as (
    select * from {{ source('silver', 'order_events') }}
)

select
    order_id,
    customer_id,
    vendor_id,
    occurred_at,
    item.menu_item_id as menu_item_id,
    item.name         as item_name,
    item.quantity     as quantity,
    item.unit_price   as unit_price,
    item.line_total   as line_total
from events
lateral view explode(items) as item
where event_type = 'order_placed'
