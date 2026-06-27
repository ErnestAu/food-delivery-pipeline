-- Slim event log at the event grain. Append-only source of truth for order lifecycle.
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
