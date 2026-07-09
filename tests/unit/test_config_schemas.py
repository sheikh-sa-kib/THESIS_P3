"""Unit tests for Phase 1 configuration schemas."""

from pathlib import Path

import pytest

from e3hybrid.config.schemas import (
    BackendName,
    ExperimentCollectionConfig,
    ProjectConfig,
)
from e3hybrid.core.exceptions import ConfigError


def test_project_config_from_mapping_accepts_valid_minimal_config() -> None:
    """A minimal Phase 1 configuration should validate successfully."""

    config = ProjectConfig.from_mapping(
        {
            "experiment": {
                "name": "phase_1",
                "seed": 7,
                "output_dir": "outputs/runs",
            },
            "simulation": {"backend": "local"},
        }
    )

    assert config.experiment.name == "phase_1"
    assert config.experiment.seed == 7
    assert config.experiment.output_dir == Path("outputs/runs")
    assert config.simulation.backend is BackendName.LOCAL


def test_project_config_rejects_missing_required_section() -> None:
    """Configuration validation should fail on missing required sections."""

    with pytest.raises(ConfigError, match="simulation"):
        ProjectConfig.from_mapping(
            {
                "experiment": {
                    "name": "phase_1",
                    "seed": 7,
                    "output_dir": "outputs/runs",
                }
            }
        )


def test_project_config_rejects_negative_seed() -> None:
    """Seeds must be explicit non-negative integers."""

    with pytest.raises(ConfigError, match="experiment.seed"):
        ProjectConfig.from_mapping(
            {
                "experiment": {
                    "name": "phase_1",
                    "seed": -1,
                    "output_dir": "outputs/runs",
                },
                "simulation": {"backend": "local"},
            }
        )


def test_project_config_rejects_unknown_backend() -> None:
    """Only declared backend names should pass validation."""

    with pytest.raises(ConfigError, match="simulation.backend"):
        ProjectConfig.from_mapping(
            {
                "experiment": {
                    "name": "phase_1",
                    "seed": 7,
                    "output_dir": "outputs/runs",
                },
                "simulation": {"backend": "unknown"},
            }
        )


def test_project_config_rejects_unknown_configuration_key() -> None:
    """Unknown configuration keys should fail validation."""

    with pytest.raises(ConfigError, match="unknown key"):
        ProjectConfig.from_mapping(
            {
                "experiment": {
                    "name": "phase_1",
                    "seed": 7,
                    "output_dir": "outputs/runs",
                },
                "simulation": {"backend": "local"},
                "unexpected": True,
            }
        )


def test_project_config_rejects_invalid_project_path() -> None:
    """Unsafe project paths should fail validation."""

    with pytest.raises(ConfigError, match="parent traversal"):
        ProjectConfig.from_mapping(
            {
                "experiment": {
                    "name": "phase_1",
                    "seed": 7,
                    "output_dir": "../outside",
                },
                "simulation": {"backend": "local"},
            }
        )


def test_project_config_rejects_negative_logging_value() -> None:
    """Negative numeric configuration values should fail validation."""

    with pytest.raises(ConfigError, match="logging.backup_count"):
        ProjectConfig.from_mapping(
            {
                "experiment": {
                    "name": "phase_1",
                    "seed": 7,
                    "output_dir": "outputs/runs",
                },
                "simulation": {"backend": "local"},
                "logging": {"max_bytes": 1024, "backup_count": -1},
            }
        )


def test_experiment_collection_rejects_duplicate_experiment_names() -> None:
    """Experiment collections should reject duplicated experiment names."""

    with pytest.raises(ConfigError, match="duplicate experiment"):
        ExperimentCollectionConfig.from_mappings(
            (
                {"name": "same", "seed": 1, "output_dir": "outputs/a"},
                {"name": "same", "seed": 2, "output_dir": "outputs/b"},
            )
        )
