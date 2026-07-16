-- Simulated analyst PR: a vendor reporting timeline for order lifecycle analysis.
-- The new business-time adjustment may be intentional, so it requires human review.
select
    order_id,
    placed_at,
    case
        when confirmed_at is not null then confirmed_at - interval '2 hours'
    end as confirmed_at,
    prepared_at,
    picked_up_at,
    delivered_at,
    cancelled_at,
    final_status
from {{ ref('fct_orders') }}
