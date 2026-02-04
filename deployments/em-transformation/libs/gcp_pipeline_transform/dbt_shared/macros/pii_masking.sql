-- dbt Macro: PII Masking
-- Generic PII masking for sensitive data across all migration projects
--
-- Prioritizes generic masking strategies (Full, Partial, Redacted) to handle
-- cases where exact data formats are unknown. Metadata-driven via pii_type.
--
-- Usage:
--   SELECT
--       {{ mask_pii('sensitive_column', 'PARTIAL') }} as masked,
--       {{ mask_full('secret_key') }} as key_masked
--   FROM my_table
--

-- Generic: Full masking (replaces with constant)
{% macro mask_full(column, mask_char='*') %}
    RPAD('', LENGTH(CAST({{ column }} AS STRING)), '{{ mask_char }}')
{% endmacro %}


-- Generic: Redact (constant value regardless of input length)
{% macro mask_redacted(column) %}
    'REDACTED'
{% endmacro %}


-- Generic: Partial masking (shows last 4, masks rest)
{% macro mask_partial_last4(column, mask_char='*') %}
    CASE
        WHEN LENGTH(CAST({{ column }} AS STRING)) <= 4 THEN CAST({{ column }} AS STRING)
        ELSE CONCAT(
            RPAD('', LENGTH(CAST({{ column }} AS STRING)) - 4, '{{ mask_char }}'),
            SUBSTRING(CAST({{ column }} AS STRING), -4)
        )
    END
{% endmacro %}


-- Generic: Partial masking (shows first character, masks rest)
{% macro mask_partial_first1(column, mask_char='*') %}
    CASE
        WHEN LENGTH(CAST({{ column }} AS STRING)) <= 1 THEN CAST({{ column }} AS STRING)
        ELSE CONCAT(
            SUBSTRING(CAST({{ column }} AS STRING), 1, 1),
            RPAD('', LENGTH(CAST({{ column }} AS STRING)) - 1, '{{ mask_char }}')
        )
    END
{% endmacro %}


-- Supporting Specific Macros (Optional)
-- Use these when data format is known and standard (e.g. ID with suffix visible)

-- Generic: Mask with suffix visible (e.g. XXX-XX-6789)
{% macro mask_with_suffix(column, suffix_length=4, mask_pattern='XXX-XX-') %}
    CASE
        WHEN {{ column }} IS NULL THEN NULL
        ELSE CONCAT('{{ mask_pattern }}', SUBSTRING(CAST({{ column }} AS STRING), -{{ suffix_length }}))
    END
{% endmacro %}


-- Generic: Mask Email (e.g. ****@domain.com)
{% macro mask_email(column, mask_prefix='****') %}
    CASE
        WHEN {{ column }} IS NULL THEN NULL
        ELSE CONCAT(
            '{{ mask_prefix }}',
            SUBSTRING(CAST({{ column }} AS STRING), POSITION('@' IN CAST({{ column }} AS STRING)))
        )
    END
{% endmacro %}


-- Generic: Mask with prefix visible (e.g. +44-****-6789)
{% macro mask_phone_generic(column, prefix_length=3, suffix_length=4, mask_middle='-***-') %}
    CASE
        WHEN {{ column }} IS NULL THEN NULL
        ELSE CONCAT(
            SUBSTRING(CAST({{ column }} AS STRING), 1, {{ prefix_length }}),
            '{{ mask_middle }}',
            SUBSTRING(CAST({{ column }} AS STRING), -{{ suffix_length }})
        )
    END
{% endmacro %}


-- Generic PII masking function
{% macro mask_pii(column, pii_type) %}
    {% set level = get_masking_level() %}

    {% if level == 'NONE' %}
        {{ column }}
    {% else %}
        CASE
            WHEN '{{ pii_type }}' IN ('SSN', 'ID_SUFFIX') THEN {{ mask_with_suffix(column) }}
            WHEN '{{ pii_type }}' = 'EMAIL' THEN {{ mask_email(column) }}
            WHEN '{{ pii_type }}' = 'PHONE' THEN {{ mask_phone_generic(column) }}
            WHEN '{{ pii_type }}' = 'FULL' THEN {{ mask_full(column) }}
            WHEN '{{ pii_type }}' = 'REDACTED' THEN {{ mask_redacted(column) }}
            WHEN '{{ pii_type }}' = 'PARTIAL' THEN {{ mask_partial_last4(column) }}
            ELSE {{ column }}
        END
    {% endif %}
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
{% macro validate_no_pii_in_export(table, checks=None) %}
    {% if checks is none %}
        {% set checks = [
            {'column': 'masked_id', 'pattern': '.*[*].*'},
            {'column': 'email_address', 'pattern': '.*@.*'}
        ] %}
    {% endif %}

    {% if execute %}
        {% for check in checks %}
            {% set query %}
                SELECT COUNT(*) as count
                FROM {{ table }}
                WHERE {{ check.column }} NOT LIKE '{{ check.pattern }}'
                AND {{ check.column }} IS NOT NULL
            {% endset %}

            {% if 'REGEXP' in check.pattern or '^' in check.pattern %}
                 {% set query %}
                    SELECT COUNT(*) as count
                    FROM {{ table }}
                    WHERE NOT REGEXP_CONTAINS(CAST({{ check.column }} AS STRING), '{{ check.pattern }}')
                    AND {{ check.column }} IS NOT NULL
                {% endset %}
            {% endif %}

            {% set result = run_query(query) %}
            {% if result.columns[0].values()[0] > 0 %}
                {% do exceptions.raise_compiler_error("Unmasked values found in " ~ table ~ "." ~ check.column) %}
            {% endif %}
        {% endfor %}

        {% do log("PII validation passed for " ~ table, info=true) %}
    {% endif %}
{% endmacro %}


-- Configuration for environments (dev vs prod)
-- Can be overridden by project variables
{% macro get_masking_level() %}
    {% set env_level = var('masking_level', 'AUTO') %}

    {% if env_level != 'AUTO' %}
        {{ env_level }}
    {% elif target.name == var('prod_target_name', 'prod') %}
        'FULL'  -- Full masking in production
    {% elif target.name == var('staging_target_name', 'staging') %}
        'PARTIAL'  -- Show last 4 digits in staging
    {% else %}
        'NONE'  -- No masking in development
    {% endif %}
{% endmacro %}

