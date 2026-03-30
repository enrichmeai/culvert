"""
Segment Template Loader.

Loads segment templates from YAML files and validates them.
"""

import os
import logging
from typing import List

import yaml

from .models import SegmentTemplate

logger = logging.getLogger(__name__)

# Default config directory: three levels up from this file to deployment root's config/
_DEFAULT_CONFIG_DIR = os.path.join(
    os.path.dirname(__file__), '..', '..', '..', 'config'
)


def _resolve_config_dir(config_dir: str = None) -> str:
    """Resolve and validate the config directory path."""
    path = os.path.abspath(config_dir or _DEFAULT_CONFIG_DIR)
    if not os.path.isdir(path):
        raise FileNotFoundError(f"Config directory not found: {path}")
    return path


def load_system_config(config_dir: str = None) -> dict:
    """Load and return system.yaml as a dict."""
    path = os.path.join(_resolve_config_dir(config_dir), 'system.yaml')
    with open(path) as f:
        return yaml.safe_load(f)


def get_available_segments(config_dir: str = None) -> List[str]:
    """Return list of registered segment IDs from system.yaml."""
    config = load_system_config(config_dir)
    return config.get('segments', [])


def load_segment_template(segment_id: str, config_dir: str = None) -> SegmentTemplate:
    """
    Load a segment template YAML and return a validated SegmentTemplate.

    Args:
        segment_id: Segment ID (e.g. 'customer', 'loans')
        config_dir: Override path to config directory

    Returns:
        Validated SegmentTemplate instance

    Raises:
        FileNotFoundError: If template YAML does not exist
        ValueError: If template validation fails (e.g. field widths don't sum)
    """
    resolved_dir = _resolve_config_dir(config_dir)

    # Verify segment is registered
    available = get_available_segments(config_dir)
    if segment_id not in available:
        raise ValueError(
            f"Segment '{segment_id}' not registered in system.yaml. "
            f"Available: {available}"
        )

    # Load template YAML
    template_path = os.path.join(resolved_dir, 'templates', f'{segment_id}.yaml')
    if not os.path.isfile(template_path):
        raise FileNotFoundError(
            f"Template file not found: {template_path}"
        )

    with open(template_path) as f:
        data = yaml.safe_load(f)

    template = SegmentTemplate.from_dict(data)
    template.validate()

    logger.info(
        "Loaded segment template '%s': %d fields, record_length=%d, "
        "source=%s.%s",
        template.segment_id,
        len(template.output.fields),
        template.record_length,
        template.source.dataset,
        template.source.table,
    )

    return template
