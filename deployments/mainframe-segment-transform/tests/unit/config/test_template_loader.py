"""Tests for segment template loading from YAML."""

import pytest
from segment_transform.config.template_loader import (
    load_system_config,
    get_available_segments,
    load_segment_template,
)

EXPECTED_SEGMENTS = ['customer']


class TestSystemConfig:

    def test_load_system_config(self, config_dir):
        config = load_system_config(config_dir)
        assert config['system_id'] == 'GENERIC'
        assert config['pipeline_name'] == 'mainframe-segment-transform'

    def test_get_available_segments(self, config_dir):
        segments = get_available_segments(config_dir)
        assert segments == EXPECTED_SEGMENTS


class TestLoadSegmentTemplate:

    @pytest.mark.parametrize('segment_id', EXPECTED_SEGMENTS)
    def test_load_all_segments(self, config_dir, segment_id):
        template = load_segment_template(segment_id, config_dir)
        assert template.segment_id == segment_id
        assert template.record_length == 200
        # Validate field widths sum to record_length
        total = sum(f.width for f in template.output.fields)
        assert total == 200, (
            f"Segment '{segment_id}': field widths sum to {total}, expected 200"
        )

    @pytest.mark.parametrize('segment_id', EXPECTED_SEGMENTS)
    def test_all_segments_have_query_with_placeholders(self, config_dir, segment_id):
        template = load_segment_template(segment_id, config_dir)
        assert '{project}' in template.query, (
            f"Segment '{segment_id}': query must contain {{project}} placeholder"
        )
        assert '{period_start}' in template.query, (
            f"Segment '{segment_id}': query must contain {{period_start}} placeholder"
        )
        assert '{period_end}' in template.query, (
            f"Segment '{segment_id}': query must contain {{period_end}} placeholder"
        )

    @pytest.mark.parametrize('segment_id', EXPECTED_SEGMENTS)
    def test_all_segments_have_source_with_partition(self, config_dir, segment_id):
        template = load_segment_template(segment_id, config_dir)
        assert template.source.dataset
        assert template.source.table
        assert template.source.partition_column, (
            f"Segment '{segment_id}': source must have a partition_column"
        )

    @pytest.mark.parametrize('segment_id', EXPECTED_SEGMENTS)
    def test_all_segments_have_sharding_config(self, config_dir, segment_id):
        template = load_segment_template(segment_id, config_dir)
        assert template.output.max_records_per_shard > 0, (
            f"Segment '{segment_id}': output must have max_records_per_shard > 0"
        )

    def test_load_unknown_segment_raises(self, config_dir):
        with pytest.raises(ValueError, match="not registered"):
            load_segment_template('nonexistent', config_dir)

    def test_customer_template_details(self, config_dir):
        template = load_segment_template('customer', config_dir)
        assert template.segment_name == 'Customer'
        assert template.source.table == 'customer_risk_profile'
        assert template.output.file_prefix == 'CUST'
        field_names = [f.name for f in template.output.fields]
        assert 'segment_type' in field_names
        assert 'customer_id' in field_names
        assert 'filler' in field_names

    def test_customer_has_status_filter_in_query(self, config_dir):
        template = load_segment_template('customer', config_dir)
        assert "status IN ('ACTIVE', 'DORMANT')" in template.query
