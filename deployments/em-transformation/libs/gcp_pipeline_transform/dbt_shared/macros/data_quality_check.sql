-- dbt Macro: Data Quality Checks
--
-- Provides reusable macros for quality checks:
-- - Check completeness (non-null required fields)
-- - Check uniqueness (no duplicate keys)
-- - Check value ranges (numeric bounds)
-- - Check pattern matches (format validation)
--
-- Usage:
--   {{ check_completeness(column_name) }}
--

{% macro check_required_fields(table, required_fields) %}
    {% set sql %}
        SELECT
            COUNT(*) as total_records,
            SUM(CASE WHEN {{ required_fields | join(" IS NULL OR ") }} IS NULL THEN 1 ELSE 0 END) as missing_count,
            ROUND(100 * (1 - SUM(CASE WHEN {{ required_fields | join(" IS NULL OR ") }} IS NULL THEN 1 ELSE 0 END) / COUNT(*)), 2) as completeness_percent
        FROM {{ table }}
    {% endset %}

    {% if execute %}
        {% set result = run_query(sql) %}
        {% set completeness = result.columns[2].values()[0] %}
        {% set quality_threshold = var('quality_completeness_threshold', 95) %}

        {% if completeness < quality_threshold %}
            {% do exceptions.warn("Completeness for " ~ table ~ " is " ~ completeness ~ "%") %}
        {% endif %}
    {% endif %}
{% endmacro %}


{% macro check_uniqueness(table, key_field) %}
    {% set sql %}
        SELECT
            COUNT(DISTINCT {{ key_field }}) as unique_count,
            COUNT(*) as total_count,
            ROUND(100 * COUNT(DISTINCT {{ key_field }}) / COUNT(*), 2) as uniqueness_percent
        FROM {{ table }}
    {% endset %}

    {% if execute %}
        {% set result = run_query(sql) %}
        {% set uniqueness = result.columns[2].values()[0] %}

        {% if uniqueness < 100 %}
            {% do exceptions.warn("Duplicate records detected in " ~ table ~ " on field " ~ key_field) %}
        {% endif %}
    {% endif %}
{% endmacro %}


{% macro check_value_range(table, column, min_value, max_value) %}
    {% set sql %}
        SELECT
            COUNT(*) as total_records,
            SUM(CASE WHEN {{ column }} < {{ min_value }} OR {{ column }} > {{ max_value }} THEN 1 ELSE 0 END) as out_of_range_count,
            ROUND(100 * (1 - SUM(CASE WHEN {{ column }} < {{ min_value }} OR {{ column }} > {{ max_value }} THEN 1 ELSE 0 END) / COUNT(*)), 2) as valid_percent
        FROM {{ table }}
    {% endset %}

    {% if execute %}
        {% set result = run_query(sql) %}
        {% set valid_percent = result.columns[2].values()[0] %}

        {% if valid_percent < 95 %}
            {% do exceptions.warn(column ~ " has " ~ (100 - valid_percent) ~ "% values outside range [" ~ min_value ~ ", " ~ max_value ~ "]") %}
        {% endif %}
    {% endif %}
{% endmacro %}


{% macro check_pattern_match(table, column, pattern) %}
    {% set sql %}
        SELECT
            COUNT(*) as total_records,
            SUM(CASE WHEN {{ column }} NOT REGEXP '{{ pattern }}' THEN 1 ELSE 0 END) as pattern_mismatch_count,
            ROUND(100 * (1 - SUM(CASE WHEN {{ column }} NOT REGEXP '{{ pattern }}' THEN 1 ELSE 0 END) / COUNT(*)), 2) as valid_percent
        FROM {{ table }}
    {% endset %}

    {% if execute %}
        {% set result = run_query(sql) %}
        {% set valid_percent = result.columns[2].values()[0] %}

        {% if valid_percent < 95 %}
            {% do exceptions.warn(column ~ " has pattern mismatches. Valid: " ~ valid_percent ~ "%") %}
        {% endif %}
    {% endif %}
{% endmacro %}


{% macro check_freshness(table, timestamp_column, max_age_hours) %}
    {% set sql %}
        SELECT
            MAX({{ timestamp_column }}) as max_timestamp,
            TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), MAX({{ timestamp_column }}), HOUR) as age_hours,
            CASE WHEN TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), MAX({{ timestamp_column }}), HOUR) > {{ max_age_hours }} THEN 'STALE' ELSE 'FRESH' END as freshness
        FROM {{ table }}
    {% endset %}

    {% if execute %}
        {% set result = run_query(sql) %}
        {% set freshness = result.columns[2].values()[0] %}

        {% if freshness == 'STALE' %}
            {% do exceptions.warn("Data in " ~ table ~ " is stale (> " ~ max_age_hours ~ " hours old)") %}
        {% endif %}
    {% endif %}
{% endmacro %}


-- Generic test macro for use in tests section of dbt_project.yml
{% macro generic_not_null_and_unique(model, column_name) %}
    SELECT *
    FROM {{ model }}
    WHERE {{ column_name }} IS NULL
       OR (SELECT COUNT(DISTINCT {{ column_name }}) FROM {{ model }}) < COUNT(*)
{% endmacro %}

