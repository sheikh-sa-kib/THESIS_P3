"""Tests for SumoConfig."""

from __future__ import annotations

from pathlib import Path

import pytest

from e3hybrid.core.exceptions import ConfigError
from e3hybrid.sumo.config import SumoConfig


class TestSumoConfigDefaults:
    def test_required_fields(self) -> None:
        c = SumoConfig(sumo_net_file=Path("net.xml"), sumo_route_file=Path("rou.xml"))
        assert c.sumo_net_file == Path("net.xml")
        assert c.sumo_route_file == Path("rou.xml")
        assert c.sumo_seed == 42
        assert c.step_length_ms == 1000

    def test_optional_additional_file(self) -> None:
        c = SumoConfig(
            sumo_net_file=Path("n.xml"), sumo_route_file=Path("r.xml"),
            sumo_additional_file=Path("a.xml"),
        )
        assert c.sumo_additional_file == Path("a.xml")


class TestSumoConfigValidation:
    def test_step_length_positive(self) -> None:
        with pytest.raises(ConfigError):
            SumoConfig(sumo_net_file=Path("n.xml"), sumo_route_file=Path("r.xml"),
                       step_length_ms=0)

    def test_step_length_negative(self) -> None:
        with pytest.raises(ConfigError):
            SumoConfig(sumo_net_file=Path("n.xml"), sumo_route_file=Path("r.xml"),
                       step_length_ms=-100)

    def test_reroute_interval_positive(self) -> None:
        with pytest.raises(ConfigError):
            SumoConfig(sumo_net_file=Path("n.xml"), sumo_route_file=Path("r.xml"),
                       reroute_interval_steps=0)

    def test_logging_interval_positive(self) -> None:
        with pytest.raises(ConfigError):
            SumoConfig(sumo_net_file=Path("n.xml"), sumo_route_file=Path("r.xml"),
                       logging_interval_steps=0)

    def test_port_range_low(self) -> None:
        with pytest.raises(ConfigError):
            SumoConfig(sumo_net_file=Path("n.xml"), sumo_route_file=Path("r.xml"),
                       traci_port=0)

    def test_port_range_high(self) -> None:
        with pytest.raises(ConfigError):
            SumoConfig(sumo_net_file=Path("n.xml"), sumo_route_file=Path("r.xml"),
                       traci_port=70000)

    def test_empty_algorithm_names(self) -> None:
        with pytest.raises(ConfigError):
            SumoConfig(sumo_net_file=Path("n.xml"), sumo_route_file=Path("r.xml"),
                       algorithm_names=())

    def test_split_weights_must_sum(self) -> None:
        with pytest.raises(ConfigError):
            SumoConfig(sumo_net_file=Path("n.xml"), sumo_route_file=Path("r.xml"),
                       algorithm_split=(("dijkstra", 0.5), ("e3hybrid", 0.3)))

    def test_split_weights_exact_sum(self) -> None:
        c = SumoConfig(sumo_net_file=Path("n.xml"), sumo_route_file=Path("r.xml"),
                       algorithm_split=(("aco", 0.6), ("pso", 0.4)))
        assert len(c.algorithm_split) == 2


class TestSumoConfigFromMapping:
    def test_basic_mapping(self) -> None:
        data = {
            "sumo_net_file": "net.xml",
            "sumo_route_file": "rou.xml",
            "algorithm_names": ["dijkstra", "aco"],
            "algorithm_split": {"dijkstra": 0.5, "aco": 0.5},
        }
        c = SumoConfig.from_mapping(data)
        assert c.sumo_net_file == Path("net.xml")
        assert c.algorithm_names == ("dijkstra", "aco")

    def test_mapping_with_optional(self) -> None:
        data = {
            "sumo_net_file": "n.xml",
            "sumo_route_file": "r.xml",
            "sumo_additional_file": "a.xml",
            "sumo_seed": 123,
            "step_length_ms": 500,
            "use_gui": True,
            "use_libsumo": False,
        }
        c = SumoConfig.from_mapping(data)
        assert c.sumo_seed == 123
        assert c.step_length_ms == 500
        assert c.use_gui is True
        assert c.use_libsumo is False