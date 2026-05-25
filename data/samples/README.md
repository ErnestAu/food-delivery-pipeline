# Data Samples

Tiny representative slice of generated data, committed so the repo shows what the pipeline ingests without needing to run the simulator.

## What's here

- **`dims/`** — first 10 rows of each dimension CSV (`customers`, `vendors`, `drivers`, `menu_items`)
- **`order_events/sample_events.jsonl`** — one hour of generated events (~140 events covering all 6 event types)

## Schema reference

**Event schema** (one per line in JSONL):
```json
{
  "event_id": "evt_...",
  "event_type": "order_placed | order_confirmed | order_prepared | order_picked_up | order_delivered | order_cancelled",
  "order_id": "ord_...",
  "occurred_at": "2024-01-15T12:00:00.000Z",
  "customer_id": "cust_...",
  "vendor_id": "vend_...",
  "driver_id": "driv_... | null",
  "payload": { ... }  // shape varies by event_type
}
```

**Payload by event type:**
- `order_placed`: items[], food_cost, delivery_fee, service_fee, discount, gmv, delivery_address
- `order_confirmed`: estimated_prep_minutes
- `order_prepared`: {} (empty)
- `order_picked_up`: driver_id, vehicle_type
- `order_delivered`: {} (empty)
- `order_cancelled`: cancelled_by, reason

## Generating the full dataset

Real data is gitignored. Generate it locally:
```bash
python -m simulator.main --start-date 2024-01-17 --base-orders 100
aws s3 sync data/raw/ s3://your-bucket/data/raw/
```
