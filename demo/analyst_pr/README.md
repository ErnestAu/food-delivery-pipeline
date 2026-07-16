# Simulated analyst pull request

`fct_vendor_daily_performance` is deliberately separate from the established
food-delivery facts and dimensions. It represents a new analyst contribution
that a GitHub pull-request check will evaluate.

The model contains an intentional, syntactically valid join-key error. The
`not_null` contract on `vendor_name` is expected to fail: every delivered order
has a vendor ID, so an unresolved vendor name is evidence that the new model
does not preserve the model's declared relationship to `dim_vendor`.

This is a high-confidence repair scenario for the future reviewer. In contrast,
a lifecycle-ordering failure will be treated as an ambiguity to explain and
escalate rather than automatically patch.

`fct_order_lifecycle_timeline` is that ambiguity scenario. It changes
`confirmed_at` for a possible business-time policy and fails the established
lifecycle ordering test. The reviewer must ask the analyst to confirm the
policy rather than changing timestamps only to satisfy the existing test.
