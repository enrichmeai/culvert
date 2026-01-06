-- Generic dbt Macro: Audit Columns
-- Adds standardized audit columns to all tables
-- Used across all migration blueprints for data lineage

{% macro add_audit_columns() %}
  -- Macro to add standard audit columns to tables
  created_at: timestamp_utc = now()
  updated_at: timestamp_utc = now()
  created_by: string = current_user()
  updated_by: string = current_user()
  job_id: string = env_var('JOB_ID', 'unknown')
  run_id: string = env_var('RUN_ID', 'unknown')
{% endmacro %}

