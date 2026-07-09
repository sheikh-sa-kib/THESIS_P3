"""Configuration loading and validation.

Configuration is the only approved source for experiment parameters that cannot
be derived from literature, SUMO, TraCI, or recorded simulation state.
"""

from e3hybrid.config.loader import load_project_config
from e3hybrid.config.schemas import ProjectConfig

__all__ = ["ProjectConfig", "load_project_config"]
