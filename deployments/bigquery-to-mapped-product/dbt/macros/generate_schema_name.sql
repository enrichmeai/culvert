-- Override dbt's default schema generation
--
-- Default behaviour: {profile_schema}_{custom_schema} → fdp_generic_staging
-- This override:     {custom_schema} directly          → fdp_generic
--
-- Maps logical schema names from dbt_project.yml to actual BigQuery datasets
-- created by Terraform (odp_generic, fdp_generic, cdp_generic, job_control).

{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- set schema_map = {
        'staging': var('source_dataset', 'odp_generic'),
        'fdp':     var('fdp_dataset', 'fdp_generic'),
        'marts':   var('marts_dataset', 'marts_generic'),
        'analytics': var('analytics_dataset', 'analytics_generic'),
    } -%}

    {%- if custom_schema_name is not none -%}
        {{ schema_map.get(custom_schema_name, custom_schema_name) }}
    {%- else -%}
        {{ target.schema }}
    {%- endif -%}
{%- endmacro %}
