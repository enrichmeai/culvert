-- CDP Data Quality Checks
-- Uses patterns from gcp-pipeline-transform shared macros
-- (audit_columns, data_quality_check, pii_masking)
--
-- These macros validate CDP output before it is consumed by
-- downstream pipelines (e.g. mainframe-segment-transform).

{% macro validate_cdp_segment(model) %}
    {#
      Ensure every row in the CDP model has a valid cdp_segment value.
      Invalid segments would break the mainframe segment writer.
    #}
    SELECT *
    FROM {{ model }}
    WHERE cdp_segment NOT IN ('ACTIVE_APPROVED', 'DECLINED', 'REFERRED', 'PENDING')
{% endmacro %}


{% macro validate_risk_profile_completeness(model) %}
    {#
      Critical fields for the mainframe segment file must not be null.
      Maps to the fixed-width FIELD_WIDTHS in mainframe-segment-transform.
    #}
    SELECT *
    FROM {{ model }}
    WHERE customer_id IS NULL
       OR risk_profile_key IS NULL
       OR cdp_segment IS NULL
       OR _extract_date IS NULL
{% endmacro %}


{% macro validate_pii_masked(model) %}
    {#
      Verify that SSN values reaching the CDP layer are already masked
      (should have been masked in the FDP layer via mask_pii macro).
      Unmasked SSNs follow the pattern NNN-NN-NNNN.
    #}
    SELECT *
    FROM {{ model }}
    WHERE ssn_masked IS NOT NULL
      AND REGEXP_CONTAINS(ssn_masked, r'^\d{3}-\d{2}-\d{4}$')
{% endmacro %}
