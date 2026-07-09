"""Unit tests for YAML configuration loading."""

from pathlib import Path

import pytest

from e3hybrid.config.loader import load_project_config, load_yaml_mapping
from e3hybrid.core.exceptions import ConfigError


def test_load_project_config_reads_yaml_file(tmp_path: Path) -> None:
    """A valid YAML file should load into a validated project config."""

    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
experiment:
  name: loader_test
  seed: 3
  output_dir: outputs/runs
simulation:
  backend: local
""",
        encoding="utf-8",
    )

    config = load_project_config(config_path)

    assert config.experiment.name == "loader_test"
    assert config.experiment.seed == 3


def test_load_yaml_mapping_rejects_missing_file(tmp_path: Path) -> None:
    """Missing configuration files should raise configuration errors."""

    with pytest.raises(ConfigError, match="does not exist"):
        load_yaml_mapping(tmp_path / "missing.yaml")


def test_load_yaml_mapping_rejects_empty_file(tmp_path: Path) -> None:
    """Empty configuration files should fail validation."""

    config_path = tmp_path / "empty.yaml"
    config_path.write_text("", encoding="utf-8")

    with pytest.raises(ConfigError, match="empty"):
        load_yaml_mapping(config_path)


def test_load_yaml_mapping_rejects_non_mapping_file(tmp_path: Path) -> None:
    """Top-level YAML content must be a mapping."""

    config_path = tmp_path / "list.yaml"
    config_path.write_text("- a\n- b\n", encoding="utf-8")

    with pytest.raises(ConfigError, match="mapping"):
        load_yaml_mapping(config_path)
