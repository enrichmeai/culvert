-- dbt Macro: PII Masking
-- Generic PII masking for sensitive data across all migration projects
--
-- Masks Personally Identifiable Information (PII) for:
-- - SSN: Social Security Numbers
-- - Account Numbers
-- - Sensitive data
--
-- Usage:
--   SELECT
--       {{ mask_ssn('ssn') }} as ssn_masked,
--       {{ mask_account_number('account_number') }} as account_masked,
--       customer_name
--   FROM customers
--

-- Mask SSN: XXX-XX-XXXX format becomes XXX-XX-6789
{% macro mask_ssn(column) %}
    CONCAT(
        SUBSTRING({{ column }}, 1, 5),  -- Keep XXX-XX
        '-',
        SUBSTRING({{ column }}, -4)     -- Show last 4 digits
    )
{% endmacro %}


-- Alternative: Full masking (no digits visible)
{% macro mask_ssn_full(column) %}
    'XXX-XX-XXXX'
{% endmacro %}


-- Mask account number: Show only last 4 digits
{% macro mask_account_number(column) %}
    CONCAT(
        RPAD('*', LENGTH({{ column }}) - 4, '*'),  -- Asterisks for all but last 4
        SUBSTRING({{ column }}, -4)                 -- Last 4 digits
    )
{% endmacro %}


-- Mask email: Show domain only
{% macro mask_email(column) %}
    CONCAT(
        '****',
        SUBSTRING({{ column }}, POSITION('@' IN {{ column }}))
    )
{% endmacro %}


-- Mask phone number: Show country and last 4 digits
{% macro mask_phone(column) %}
    CONCAT(
        SUBSTRING({{ column }}, 1, 3),    -- Area code
        '-***-',
        SUBSTRING({{ column }}, -4)       -- Last 4 digits
    )
{% endmacro %}


-- Mask name: Show first letter and last name
{% macro mask_name(first_name, last_name) %}
    CONCAT(
        SUBSTRING({{ first_name }}, 1, 1),  -- First initial
        '****',
        ' ',
        {{ last_name }}                     -- Full last name
    )
{% endmacro %}


-- Generic PII masking function
{% macro mask_pii(column, pii_type) %}
    CASE
        WHEN '{{ pii_type }}' = 'SSN' THEN {{ mask_ssn(column) }}
        WHEN '{{ pii_type }}' = 'ACCOUNT' THEN {{ mask_account_number(column) }}
        WHEN '{{ pii_type }}' = 'EMAIL' THEN {{ mask_email(column) }}
        WHEN '{{ pii_type }}' = 'PHONE' THEN {{ mask_phone(column) }}
        ELSE {{ column }}
    END
{% endmacro %}


-- Create masked view for sensitive data
{% macro create_masked_view(source_table, view_name, masking_rules) %}
    {% set sql %}
        CREATE OR REPLACE VIEW {{ view_name }} AS
        SELECT
            {% for rule in masking_rules %}
                {% if rule.type == 'MASK' %}
                    {{ mask_pii(rule.column, rule.pii_type) }} as {{ rule.column }},
                {% elif rule.type == 'KEEP' %}
                    {{ rule.column }},
                {% elif rule.type == 'HIDE' %}
                    'REDACTED' as {{ rule.column }},
                {% endif %}
            {% endfor %}
        FROM {{ source_table }}
    {% endset %}

    {% do run_query(sql) %}
{% endmacro %}


-- Validate PII hasn't been exposed
{% macro validate_no_pii_in_export(table) %}
    {% set ssn_check %}
        SELECT COUNT(*) as ssn_count
        FROM {{ table }}
        WHERE ssn NOT REGEXP '^XXX-XX-' AND ssn IS NOT NULL
    {% endset %}

    {% set account_check %}
        SELECT COUNT(*) as account_count
        FROM {{ table }}
        WHERE account_number NOT LIKE '%****%' AND account_number IS NOT NULL
    {% endset %}

    {% if execute %}
        {% set ssn_result = run_query(ssn_check) %}
        {% set account_result = run_query(account_check) %}

        {% if ssn_result.columns[0].values()[0] > 0 %}
            {% do exceptions.raise_compiler_error("Unmasked SSN values found in " ~ table) %}
        {% endif %}

        {% if account_result.columns[0].values()[0] > 0 %}
            {% do exceptions.raise_compiler_error("Unmasked account numbers found in " ~ table) %}
        {% endif %}

        {% do log("PII validation passed for " ~ table, info=true) %}
    {% endif %}
{% endmacro %}


-- Configuration for environments (dev vs prod)
{% macro get_masking_level() %}
    {% if target.name == 'prod' %}
        'FULL'  -- Full masking in production
    {% elif target.name == 'staging' %}
        'PARTIAL'  -- Show last 4 digits in staging
    {% else %}
        'NONE'  -- No masking in development
    {% endif %}
{% endmacro %}

