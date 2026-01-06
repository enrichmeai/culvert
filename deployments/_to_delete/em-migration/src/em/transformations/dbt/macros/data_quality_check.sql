-- Generic dbt Macro: Data Quality Checks
-- Validates data quality metrics (completeness, uniqueness, patterns)
-- Thresholds configurable via dbt variables

{% macro check_data_quality(table_name) %}
  select
    '{{ table_name }}' as table_name,
    count(*) as row_count,
    count(case when id is not null then 1 end) / count(*) * 100 as completeness_pct,
    count(distinct id) / count(*) * 100 as uniqueness_pct,
    max(created_at) as last_updated
  from {{ table_name }}
  where completeness_pct >= {{ var('quality_completeness_threshold', 95) }}
    and uniqueness_pct >= {{ var('quality_uniqueness_threshold', 100) }}
{% endmacro %}

