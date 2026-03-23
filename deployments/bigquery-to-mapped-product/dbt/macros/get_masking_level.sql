-- Override library get_masking_level to fix whitespace bug
-- Library version uses {{ }} output which includes whitespace/comments
-- This version uses return() for a clean Jinja string comparison
{% macro get_masking_level() %}
    {{ return(var('masking_level', 'NONE')) }}
{% endmacro %}
