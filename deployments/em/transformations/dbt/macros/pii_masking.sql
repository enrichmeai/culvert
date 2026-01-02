-- Generic dbt Macro: PII Masking
-- Masks personally identifiable information (PII) in data
-- Works for any entity type and PII classification

{% macro mask_pii(column_name, pii_type) %}
  case
    when '{{ pii_type }}' = 'email' then concat(substr({{ column_name }}, 1, 1), '***@***')
    when '{{ pii_type }}' = 'phone' then concat(substr({{ column_name }}, 1, 3), '-***-', substr({{ column_name }}, -4))
    when '{{ pii_type }}' = 'ssn' then concat('***-**-', substr({{ column_name }}, -4))
    when '{{ pii_type }}' = 'name' then concat(substr({{ column_name }}, 1, 1), '***')
    when '{{ pii_type }}' = 'address' then '***MASKED***'
    else {{ column_name }}
  end as {{ column_name }}_masked
{% endmacro %}

