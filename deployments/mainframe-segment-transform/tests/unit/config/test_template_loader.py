"""Tests for segment template loading from YAML."""

import os
import tempfile

import pytest
import yaml
from segment_transform.config.template_loader import (
    load_system_config,
    get_available_segments,
    load_segment_template,
    _resolve_config_dir,
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

    def test_load_system_config_has_infrastructure(self, config_dir):
        config = load_system_config(config_dir)
        assert 'infrastructure' in config
        assert 'pubsub' in config['infrastructure']

    def test_missing_config_dir_raises(self):
        with pytest.raises(FileNotFoundError, match="Config directory not found"):
            _resolve_config_dir('/nonexistent/path')


class TestLoadSegmentTemplate:

    @pytest.mark.parametrize('segment_id', EXPECTED_SEGMENTS)
    def test_load_all_segments(self, config_dir, segment_id):
        template = load_segment_template(segment_id, config_dir)
        assert template.segment_id == segment_id
        assert template.record_length == 200
        total = sum(f.width for f in template.output.fields)
        assert total == 200, (
            f"Segment '{segment_id}': field widths sum to {total}, expected 200"
        )

    @pytest.mark.parametrize('segment_id', EXPECTED_SEGMENTS)
    def test_all_segments_have_query_with_placeholders(self, config_dir, segment_id):
        template = load_segment_template(segment_id, config_dir)
        assert '{project}' in template.query
        assert '{period_start}' in template.query
        assert '{period_end}' in template.query

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
        assert template.output.max_records_per_shard > 0

    def test_load_unknown_segment_raises(self, config_dir):
        with pytest.raises(ValueError, match="not registered"):
            load_segment_template('nonexistent', config_dir)

    def test_customer_template_details(self, config_dir):
        template = load_segment_template('customer', config_dir)
        assert template.segment_name == 'Customer'
        # Source is CDP — stable snapshot per extract date (idempotent retries)
        assert template.source.dataset == 'cdp_generic'
        assert template.source.table == 'customer_risk_profile'
        assert template.output.file_prefix == 'CUST'
        field_names = [f.name for f in template.output.fields]
        assert 'segment_type' in field_names
        assert 'customer_id' in field_names
        assert 'filler' in field_names

    def test_customer_has_status_filter_in_query(self, config_dir):
        template = load_segment_template('customer', config_dir)
        assert "customer_status IN ('ACTIVE', 'DORMANT')" in template.query

    def test_customer_reads_from_cdp_not_fdp(self, config_dir):
        """Customer template reads from CDP snapshot, not FDP directly.

        CDP is written once per _extract_date by dbt. This ensures segment-
        transform sees the same rows on a retry as on the original run.
        """
        template = load_segment_template('customer', config_dir)
        assert 'cdp_generic.customer_risk_profile' in template.query
        # No multi-table JOINs — dbt CDP handles the denormalisation
        assert 'JOIN' not in template.query.upper()


class TestMalformedYAML:
    """Test edge cases with crafted config directories."""

    def test_missing_template_file_raises(self, tmp_path):
        """Registered segment but missing template YAML."""
        config = tmp_path / 'config'
        config.mkdir()
        templates = config / 'templates'
        templates.mkdir()
        system = config / 'system.yaml'
        system.write_text(yaml.dump({
            'system_id': 'TEST',
            'pipeline_name': 'test',
            'segments': ['missing_segment'],
        }))
        with pytest.raises(FileNotFoundError, match="Template file not found"):
            load_segment_template('missing_segment', str(config))

    def test_malformed_yaml_raises(self, tmp_path):
        """Invalid YAML content should raise."""
        config = tmp_path / 'config'
        config.mkdir()
        templates = config / 'templates'
        templates.mkdir()
        system = config / 'system.yaml'
        system.write_text(yaml.dump({
            'system_id': 'TEST',
            'pipeline_name': 'test',
            'segments': ['bad'],
        }))
        bad_template = templates / 'bad.yaml'
        bad_template.write_text(': : invalid yaml {{{')
        with pytest.raises(Exception):
            load_segment_template('bad', str(config))

    def test_missing_required_keys_raises(self, tmp_path):
        """Template YAML missing required keys should raise."""
        config = tmp_path / 'config'
        config.mkdir()
        templates = config / 'templates'
        templates.mkdir()
        system = config / 'system.yaml'
        system.write_text(yaml.dump({
            'system_id': 'TEST',
            'pipeline_name': 'test',
            'segments': ['incomplete'],
        }))
        incomplete = templates / 'incomplete.yaml'
        incomplete.write_text(yaml.dump({
            'segment_id': 'incomplete',
            # Missing: segment_name, description, record_length, source, query, output
        }))
        with pytest.raises((KeyError, TypeError)):
            load_segment_template('incomplete', str(config))

    def test_field_widths_mismatch_raises(self, tmp_path):
        """Template where field widths don't sum to record_length."""
        config = tmp_path / 'config'
        config.mkdir()
        templates = config / 'templates'
        templates.mkdir()
        system = config / 'system.yaml'
        system.write_text(yaml.dump({
            'system_id': 'TEST',
            'pipeline_name': 'test',
            'segments': ['mismatch'],
        }))
        mismatch = templates / 'mismatch.yaml'
        mismatch.write_text(yaml.dump({
            'segment_id': 'mismatch',
            'segment_name': 'Mismatch',
            'description': 'Test',
            'record_length': 200,
            'source': {'dataset': 'cdp', 'table': 'test'},
            'query': 'SELECT * FROM test',
            'output': {
                'fields': [
                    {'name': 'f1', 'source': '_literal', 'literal_value': '',
                     'width': 50, 'type': 'filler'},
                ],
            },
        }))
        with pytest.raises(ValueError, match="field widths sum to"):
            load_segment_template('mismatch', str(config))
