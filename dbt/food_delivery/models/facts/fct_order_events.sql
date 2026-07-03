select
    event_id,
    event_type,
    order_id,
    occurred_at,
    customer_id,
    vendor_id,
    driver_id,
    cancelled_by,
    cancel_reason
from {{ source('silver', 'order_events') }}
