-- dbt Macro: Configurable Data Enrichment
-- Generic macro to apply enrichment rules defined in metadata/config
--
-- Supported Rule Types:
-- - DATE_PARTS: Extracts year, month, day, quarter from a date column
-- - BUCKET: Categorizes numeric values into ranges
-- - LOOKUP: Maps codes to descriptions
-- - EXPRESSION: Applies a custom SQL expression
--
-- Usage:
--   {{ apply_enrichment([
--       {'column': 'app_date', 'type': 'DATE_PARTS', 'prefix': 'app'},
--       {'column': 'score', 'type': 'BUCKET', 'buckets': {'<600': 'Poor', '>700': 'Good'}, 'target': 'score_cat'}
--   ]) }}

{% macro apply_enrichment(rules) %}
    {% for rule in rules %}
        {% if rule.type == 'DATE_PARTS' %}
            , EXTRACT(YEAR FROM {{ rule.column }}) as {{ rule.prefix ~ '_' if rule.prefix else '' }}year
            , EXTRACT(MONTH FROM {{ rule.column }}) as {{ rule.prefix ~ '_' if rule.prefix else '' }}month
            , EXTRACT(DAY FROM {{ rule.column }}) as {{ rule.prefix ~ '_' if rule.prefix else '' }}day
            , FORMAT_DATE('%A', {{ rule.column }}) as {{ rule.prefix ~ '_' if rule.prefix else '' }}day_name
        {% elif rule.type == 'BUCKET' %}
            , CASE
                {% for range, label in rule.buckets.items() %}
                    {% if range.startswith('<') %}
                        WHEN {{ rule.column }} {{ range }} THEN '{{ label }}'
                    {% elif range.startswith('>') %}
                        WHEN {{ rule.column }} {{ range }} THEN '{{ label }}'
                    {% elif '-' in range %}
                        {% set parts = range.split('-') %}
                        WHEN {{ rule.column }} BETWEEN {{ parts[0] }} AND {{ parts[1] }} THEN '{{ label }}'
                    {% endif %}
                {% endfor %}
                ELSE '{{ rule.default if rule.default else 'Other' }}'
            END as {{ rule.target if rule.target else rule.column ~ '_bucket' }}
        {% elif rule.type == 'LOOKUP' %}
            , CASE {{ rule.column }}
                {% for code, desc in rule.map.items() %}
                    WHEN '{{ code }}' THEN '{{ desc }}'
                {% endfor %}
                ELSE 'Unknown'
            END as {{ rule.target if rule.target else rule.column ~ '_desc' }}
        {% elif rule.type == 'EXPRESSION' %}
            , {{ rule.expression }} as {{ rule.target }}
        {% endif %}
    {% endfor %}
{% endmacro %}
