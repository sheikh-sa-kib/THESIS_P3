"""SumoConfig — configuration for SUMO simulation experiments."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from e3hybrid.core.exceptions import ConfigError


@dataclass(frozen=True, slots=True)
class SumoConfig:
    """Configuration for a SUMO simulation experiment.

    Parameters
    ----------
    sumo_net_file:
        Path to the SUMO network file (.net.xml).
    sumo_route_file:
        Path to the SUMO route file (.rou.xml).
    sumo_additional_file:
        Optional additional SUMO file (.add.xml).
    sumo_seed:
        Random seed for SUMO's simulation engine (``--seed``).
    sumo_binary:
        Path to the SUMO binary (``sumo.exe`` on Windows). If None,
        the system PATH or ``SUMO_HOME`` environment variable is used
        to locate the binary (default None).
    step_length_ms:
        Simulation timestep in milliseconds (default 1000 = 1 s).
    reroute_interval_steps:
        How many simulation steps between reroute checks (default 10).
    logging_interval_steps:
        How many simulation steps between metrics logging (default 60).
    use_gui:
        If True, launch ``sumo-gui`` instead of ``sumo``.
    traci_port:
        TCP port for TraCI connection (default 8813, unused with libsumo).
    use_libsumo:
        Prefer in-process libsumo over TCP-based traci.
    algorithm_names:
        Names of routing algorithms to evaluate in the simulation
        (e.g., ``["dijkstra", "e3hybrid"]``).
    algorithm_split:
        Proportion of vehicles assigned to each algorithm.
        Keys are algorithm names; values are floats summing to 1.0.
    """

    sumo_net_file: Path
    sumo_route_file: Path
    sumo_additional_file: Path | None = None
    sumo_binary: str | None = None
    sumo_seed: int = 42
    step_length_ms: int = 1000
    reroute_interval_steps: int = 10
    logging_interval_steps: int = 60
    use_gui: bool = False
    traci_port: int = 8813
    use_libsumo: bool = True
    algorithm_names: tuple[str, ...] = ("dijkstra",)
    algorithm_split: tuple[tuple[str, float], ...] = (("dijkstra", 1.0),)

    def __post_init__(self) -> None:
        if self.step_length_ms <= 0:
            raise ConfigError("step_length_ms must be positive")
        if self.reroute_interval_steps <= 0:
            raise ConfigError("reroute_interval_steps must be positive")
        if self.logging_interval_steps <= 0:
            raise ConfigError("logging_interval_steps must be positive")
        if self.traci_port <= 0 or self.traci_port > 65535:
            raise ConfigError("traci_port must be in range 1-65535")
        if not self.algorithm_names:
            raise ConfigError("at least one algorithm_name required")
        total = sum(w for _, w in self.algorithm_split)
        if abs(total - 1.0) > 1e-9:
            raise ConfigError(f"algorithm_split weights must sum to 1.0, got {total}")

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> SumoConfig:
        """Create SumoConfig from a parsed mapping (e.g. YAML or dict)."""
        net = Path(data["sumo_net_file"])
        route = Path(data["sumo_route_file"])
        addl = Path(data["sumo_additional_file"]) if data.get("sumo_additional_file") else None
        binary = data.get("sumo_binary") if data.get("sumo_binary") else None
        seed = int(data.get("sumo_seed", 42))
        step = int(data.get("step_length_ms", 1000))
        reroute = int(data.get("reroute_interval_steps", 10))
        log_int = int(data.get("logging_interval_steps", 60))
        gui = bool(data.get("use_gui", False))
        port = int(data.get("traci_port", 8813))
        libsumo = bool(data.get("use_libsumo", True))
        names = tuple(data.get("algorithm_names", ["dijkstra"]))
        split_raw = data.get("algorithm_split", {"dijkstra": 1.0})
        split = tuple((k, float(v)) for k, v in split_raw.items())
        return cls(
            sumo_net_file=net, sumo_route_file=route,
            sumo_additional_file=addl, sumo_binary=binary, sumo_seed=seed,
            step_length_ms=step, reroute_interval_steps=reroute,
            logging_interval_steps=log_int, use_gui=gui,
            traci_port=port, use_libsumo=libsumo,
            algorithm_names=names, algorithm_split=split,
        )