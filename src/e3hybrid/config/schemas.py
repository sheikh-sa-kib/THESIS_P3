"""Typed configuration schemas for Phase 1.

The schemas here intentionally cover infrastructure-level configuration only.
Algorithm parameters, EV energy formulas, emergency protocols, and objective
definitions will be added in later phases after explicit thesis approval.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Mapping

from e3hybrid.core.exceptions import ConfigError

DEFAULT_LOG_MAX_BYTES = 1_048_576
DEFAULT_LOG_BACKUP_COUNT = 5


class BackendName(StrEnum):
    """Supported simulation backend names.

    Phase 1 defines the names for validation only. Backend implementations are
    introduced in later phases.
    """

    LOCAL = "local"
    TRACI = "traci"


class LogLevel(StrEnum):
    """Allowed logging levels for framework loggers."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


@dataclass(frozen=True, slots=True)
class ExperimentConfig:
    """Configuration that identifies and reproduces an experiment run."""

    name: str
    seed: int
    output_dir: Path

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "ExperimentConfig":
        """Create an experiment configuration from a parsed mapping."""

        reject_unknown_keys(data, "experiment", ("name", "seed", "output_dir"))
        require_keys(data, "experiment", ("name", "seed", "output_dir"))
        name = require_non_empty_string(data["name"], "experiment.name")
        seed = require_seed(data["seed"], "experiment.seed")
        output_dir = require_project_path(data["output_dir"], "experiment.output_dir")
        return cls(name=name, seed=seed, output_dir=output_dir)


@dataclass(frozen=True, slots=True)
class SimulationConfig:
    """Infrastructure-level simulation settings.

    This class validates only the backend choice in Phase 1. Timing, movement,
    rerouting, and backend-specific parameters will be introduced with the
    simulation phase.
    """

    backend: BackendName

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "SimulationConfig":
        """Create a simulation configuration from a parsed mapping."""

        reject_unknown_keys(data, "simulation", ("backend",))
        require_keys(data, "simulation", ("backend",))
        backend_value = require_non_empty_string(data["backend"], "simulation.backend")
        try:
            backend = BackendName(backend_value)
        except ValueError as error:
            allowed = ", ".join(item.value for item in BackendName)
            raise ConfigError(
                f"simulation.backend must be one of: {allowed}"
            ) from error
        return cls(backend=backend)


@dataclass(frozen=True, slots=True)
class LoggingConfig:
    """Configuration for file and console logging."""

    level: LogLevel = LogLevel.INFO
    log_dir: Path = Path("outputs/logs")
    max_bytes: int = DEFAULT_LOG_MAX_BYTES
    backup_count: int = DEFAULT_LOG_BACKUP_COUNT

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any] | None) -> "LoggingConfig":
        """Create logging configuration from a parsed mapping."""

        if data is None:
            return cls()
        reject_unknown_keys(
            data,
            "logging",
            ("level", "log_dir", "max_bytes", "backup_count"),
        )
        level_value = require_non_empty_string(
            data.get("level", LogLevel.INFO.value), "logging.level"
        )
        try:
            level = LogLevel(level_value.upper())
        except ValueError as error:
            allowed = ", ".join(item.value for item in LogLevel)
            raise ConfigError(f"logging.level must be one of: {allowed}") from error
        log_dir = require_project_path(
            data.get("log_dir", "outputs/logs"), "logging.log_dir"
        )
        max_bytes = require_positive_int(
            data.get("max_bytes", DEFAULT_LOG_MAX_BYTES), "logging.max_bytes"
        )
        backup_count = require_non_negative_int(
            data.get("backup_count", DEFAULT_LOG_BACKUP_COUNT),
            "logging.backup_count",
        )
        return cls(
            level=level,
            log_dir=log_dir,
            max_bytes=max_bytes,
            backup_count=backup_count,
        )


@dataclass(frozen=True, slots=True)
class DocumentationConfig:
    """Configuration controlling the research documentation scaffold."""

    docs_dir: Path = Path("docs")
    require_research_docs: bool = True

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any] | None) -> "DocumentationConfig":
        """Create documentation configuration from a parsed mapping."""

        if data is None:
            return cls()
        reject_unknown_keys(
            data,
            "documentation",
            ("docs_dir", "require_research_docs"),
        )
        docs_dir = require_project_path(
            data.get("docs_dir", "docs"), "documentation.docs_dir"
        )
        require_docs = require_bool(
            data.get("require_research_docs", True),
            "documentation.require_research_docs",
        )
        return cls(docs_dir=docs_dir, require_research_docs=require_docs)


@dataclass(frozen=True, slots=True)
class ProjectConfig:
    """Validated Phase 1 project configuration."""

    experiment: ExperimentConfig
    simulation: SimulationConfig
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    documentation: DocumentationConfig = field(default_factory=DocumentationConfig)

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "ProjectConfig":
        """Create a validated project configuration from a parsed mapping."""

        reject_unknown_keys(
            data,
            "config",
            ("experiment", "simulation", "logging", "documentation"),
        )
        require_keys(data, "config", ("experiment", "simulation"))
        experiment_data = require_mapping(data["experiment"], "experiment")
        simulation_data = require_mapping(data["simulation"], "simulation")
        logging_data = optional_mapping(data.get("logging"), "logging")
        documentation_data = optional_mapping(data.get("documentation"), "documentation")
        return cls(
            experiment=ExperimentConfig.from_mapping(experiment_data),
            simulation=SimulationConfig.from_mapping(simulation_data),
            logging=LoggingConfig.from_mapping(logging_data),
            documentation=DocumentationConfig.from_mapping(documentation_data),
        )


@dataclass(frozen=True, slots=True)
class ExperimentCollectionConfig:
    """Validated collection of experiments for duplicate-name checks."""

    experiments: tuple[ExperimentConfig, ...]

    @classmethod
    def from_mappings(
        cls, experiment_mappings: tuple[Mapping[str, Any], ...]
    ) -> "ExperimentCollectionConfig":
        """Create an experiment collection and reject duplicate names."""

        experiments = tuple(
            ExperimentConfig.from_mapping(experiment_mapping)
            for experiment_mapping in experiment_mappings
        )
        require_unique_experiment_names(experiments)
        return cls(experiments=experiments)


def require_keys(
    data: Mapping[str, Any], section_name: str, required_keys: tuple[str, ...]
) -> None:
    """Raise a configuration error if required keys are missing."""

    missing_keys = [key for key in required_keys if key not in data]
    if missing_keys:
        joined = ", ".join(missing_keys)
        raise ConfigError(f"{section_name} is missing required key(s): {joined}")


def reject_unknown_keys(
    data: Mapping[str, Any], section_name: str, allowed_keys: tuple[str, ...]
) -> None:
    """Raise a configuration error if a mapping contains unsupported keys."""

    unknown_keys = [key for key in data if key not in allowed_keys]
    if unknown_keys:
        joined = ", ".join(str(key) for key in unknown_keys)
        raise ConfigError(f"{section_name} contains unknown key(s): {joined}")


def require_mapping(value: Any, field_name: str) -> Mapping[str, Any]:
    """Return a mapping value or raise a configuration error."""

    if not isinstance(value, Mapping):
        raise ConfigError(f"{field_name} must be a mapping")
    return value


def optional_mapping(value: Any, field_name: str) -> Mapping[str, Any] | None:
    """Return an optional mapping value or raise a configuration error."""

    if value is None:
        return None
    return require_mapping(value, field_name)


def require_non_empty_string(value: Any, field_name: str) -> str:
    """Return a non-empty string value or raise a configuration error."""

    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"{field_name} must be a non-empty string")
    return value.strip()


def require_non_negative_int(value: Any, field_name: str) -> int:
    """Return a non-negative integer or raise a configuration error."""

    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ConfigError(f"{field_name} must be a non-negative integer")
    return value


def require_positive_int(value: Any, field_name: str) -> int:
    """Return a positive integer or raise a configuration error."""

    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ConfigError(f"{field_name} must be a positive integer")
    return value


def require_seed(value: Any, field_name: str) -> int:
    """Return a non-negative integer seed or raise a configuration error."""

    return require_non_negative_int(value, field_name)


def require_project_path(value: Any, field_name: str) -> Path:
    """Return a safe relative project path from a string configuration value."""

    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"{field_name} must be a non-empty path string")
    path_text = value.strip()
    if any(character in path_text for character in '<>"|?*'):
        raise ConfigError(f"{field_name} contains invalid path character(s)")
    path = Path(path_text)
    if path.is_absolute():
        raise ConfigError(f"{field_name} must be relative to the project root")
    if any(part == ".." for part in path.parts):
        raise ConfigError(f"{field_name} must not contain parent traversal")
    return path


def require_bool(value: Any, field_name: str) -> bool:
    """Return a boolean value or raise a configuration error."""

    if not isinstance(value, bool):
        raise ConfigError(f"{field_name} must be a boolean")
    return value


def require_unique_experiment_names(experiments: tuple[ExperimentConfig, ...]) -> None:
    """Raise a configuration error if experiment names are duplicated."""

    seen_names: set[str] = set()
    duplicated_names: set[str] = set()
    for experiment in experiments:
        if experiment.name in seen_names:
            duplicated_names.add(experiment.name)
        seen_names.add(experiment.name)
    if duplicated_names:
        joined = ", ".join(sorted(duplicated_names))
        raise ConfigError(f"duplicate experiment name(s): {joined}")
