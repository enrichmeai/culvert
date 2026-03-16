"""
Config loader for the data-pipeline-orchestrator.

Loads system.yaml and provides it as a typed dict for use by the DAG factory
and other orchestration components.
"""

import pathlib
from typing import Any, Dict

import yaml


_DEFAULT_PATH = pathlib.Path(__file__).parent / "system.yaml"


def load_system_config(
    config_path: pathlib.Path = _DEFAULT_PATH,
) -> Dict[str, Any]:
    """
    Load and return the parsed system.yaml configuration.

    Parameters
    ----------
    config_path : pathlib.Path
        Absolute or relative path to the YAML config file.
        Defaults to ``config/system.yaml`` next to this module.

    Returns
    -------
    dict
        The full parsed YAML configuration dictionary.

    Raises
    ------
    FileNotFoundError
        If the config file does not exist at the given path.
    yaml.YAMLError
        If the file is not valid YAML.
    """
    config_path = pathlib.Path(config_path)

    if not config_path.exists():
        raise FileNotFoundError(
            f"System config not found at {config_path.resolve()}. "
            "Ensure system.yaml is present in the config/ directory."
        )

    with open(config_path, "r") as fh:
        config = yaml.safe_load(fh)

    return config
