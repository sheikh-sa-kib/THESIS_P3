"""Shared fixtures for SUMO integration tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from e3hybrid.routing.factory import RoutingFactory
from e3hybrid.sumo.config import SumoConfig
from e3hybrid.sumo.experiment_runner import SumoExperimentRunner


TEST_DATA = Path(__file__).resolve().parent.parent / "data"
GRID_NET = TEST_DATA / "grid.net.xml"
GRID_ROUTE = TEST_DATA / "grid.rou.xml"
GRID_CFG = TEST_DATA / "configs" / "grid.sumocfg"


def pytest_configure() -> None:
    """Register custom markers."""
    for m in ("sumo_integration", "determinism", "acceptance", "benchmark"):
        pytest.mark.skipif(False, reason=f"register {m}")


@pytest.fixture(scope="session")
def sumo_available() -> bool:
    """Check if SUMO is available on this system."""
    import shutil
    if shutil.which("sumo"):
        return True
    try:
        import traci  # noqa: F401
        return True
    except ImportError:
        return False


@pytest.fixture
def grid_config() -> SumoConfig:
    """Return a SumoConfig for the grid network."""
    return SumoConfig(
        sumo_net_file=GRID_NET,
        sumo_route_file=GRID_ROUTE,
        sumo_seed=42,
        step_length_ms=1000,
        reroute_interval_steps=10,
        algorithm_names=("dijkstra",),
        algorithm_split=(("dijkstra", 1.0),),
    )


@pytest.fixture
def all_algorithms() -> dict[str, object]:
    """Create one instance of each of the 6 routing algorithms."""
    return {
        "dijkstra": RoutingFactory.create_algorithm("dijkstra"),
        "astar": RoutingFactory.create_algorithm("astar"),
        "aco": RoutingFactory.create_algorithm("aco"),
        "bco": RoutingFactory.create_algorithm("bco"),
        "pso": RoutingFactory.create_algorithm("pso"),
        "e3hybrid": RoutingFactory.create_algorithm("e3hybrid"),
    }


@pytest.fixture
def single_algorithm_map() -> dict[str, list[str]]:
    """Vehicle-to-algorithm map using only Dijkstra."""
    return {"dijkstra": []}


@pytest.fixture
def experiment_runner(grid_config) -> SumoExperimentRunner:
    """Create a SumoExperimentRunner."""
    return SumoExperimentRunner(grid_config)
