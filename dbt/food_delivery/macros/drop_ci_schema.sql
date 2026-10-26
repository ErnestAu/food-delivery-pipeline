{# Drops this run's CI schema once its checks are done. Refuses anything but a CI target. #}
{% macro drop_ci_schema() %}
  {% if target.name != 'ci' or not target.schema.startswith('gold_dbt_ci') %}
    {{ exceptions.raise_compiler_error("drop_ci_schema only runs against a gold_dbt_ci* schema on the ci target") }}
  {% endif %}
  {% do adapter.drop_schema(api.Relation.create(database=target.database, schema=target.schema)) %}
  {{ log("Dropped " ~ target.database ~ "." ~ target.schema, info=True) }}
{% endmacro %}
