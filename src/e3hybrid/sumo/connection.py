"""SumoTraciConnection — low-level TraCI wrapper.

This is the ONLY class in the codebase that communicates directly with
SUMO/TraCI. All other classes depend on this wrapper's abstractions.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from e3hybrid.sumo.config import SumoConfig


class SumoTraciConnection:
    """Encapsulates a connection to SUMO via TraCI or libsumo.

    Supports both TCP-based ``traci`` (default port 8813) and
    in-process ``libsumo`` (preferred when available).
    """

    def __init__(self, config: SumoConfig) -> None:
        self._config = config
        self._connected = False
        self._libsumo = None

    @property
    def is_connected(self) -> bool:
        """Return True if the connection is active."""
        return self._connected

    def start(self) -> None:
        """Launch SUMO and establish the TraCI connection."""
        if self._connected:
            return

        # Tear down any lingering traci connection from prior fixtures
        try:
            import traci as _tc
            _tc.close()
        except Exception:
            pass

        if self._config.use_libsumo:
            self._start_libsumo()
        else:
            self._start_traci()

        self._connected = True

    def _start_libsumo(self) -> None:
        try:
            import libsumo as _traci_mod
        except ImportError:
            import traci as _traci_mod

        self._mod = _traci_mod
        args = self._build_sumo_args()
        if self._config.use_gui:
            self._mod.start(args)
        else:
            self._mod.start(args)

    def _start_traci(self) -> None:
        import traci as _traci_mod

        self._mod = _traci_mod
        args = self._build_sumo_args()
        self._mod.start(args)

    def _build_sumo_args(self) -> list[str]:
        cfg = self._config
        binary = cfg.sumo_binary or ("sumo-gui" if cfg.use_gui else "sumo")
        args = [
            binary,
            "-n", str(cfg.sumo_net_file),
            "-r", str(cfg.sumo_route_file),
            "--seed", str(cfg.sumo_seed),
            "--step-length", f"{cfg.step_length_ms / 1000.0:.3f}",
            "--no-step-log", "true",
            "--duration-log.disable", "true",
            "--no-warnings", "true",
            "--verbose", "false",
        ]
        if cfg.sumo_additional_file:
            args.extend(["-a", str(cfg.sumo_additional_file)])
        if not cfg.use_libsumo:
            args.extend(["--remote-port", str(cfg.traci_port)])
        return args

    def step(self) -> int:
        """Advance the simulation by one timestep.

        Returns
        -------
        int
            Current simulation time in milliseconds.
        """
        self._mod.simulationStep()
        return self._mod.simulation.getTime()

    def stop(self) -> None:
        """Close the connection and terminate SUMO."""
        if not self._connected:
            return
        try:
            self._mod.close()
        except Exception:
            pass
        self._connected = False
        self._mod = None

    # ------------------------------------------------------------------
    # Edge queries
    # ------------------------------------------------------------------

    def get_edge_ids(self) -> list[str]:
        """Return all edge IDs in the network."""
        return list(self._mod.edge.getIDList())

    def get_edge_travel_time(self, edge_id: str) -> float:
        """Return current travel time on an edge (seconds)."""
        return self._mod.edge.getTraveltime(edge_id)

    def get_edge_mean_speed(self, edge_id: str) -> float:
        """Return mean speed on an edge (m/s)."""
        return self._mod.edge.getLastStepMeanSpeed(edge_id)

    def get_edge_occupancy(self, edge_id: str) -> float:
        """Return occupancy on an edge (0-1)."""
        return self._mod.edge.getLastStepOccupancy(edge_id)

    def get_edge_lane_count(self, edge_id: str) -> int:
        """Return number of lanes on an edge."""
        return self._mod.edge.getLaneNumber(edge_id)

    def get_edge_length(self, edge_id: str) -> float:
        """Return edge length in metres (via first lane for SUMO <1.19 compat)."""
        first_lane = f"{edge_id}_0"
        try:
            return float(self._mod.lane.getLength(first_lane))
        except Exception:
            return 100.0  # fallback default

    def get_edge_speed_limit(self, edge_id: str) -> float:
        """Return speed limit on an edge (m/s, via first lane max speed)."""
        first_lane = f"{edge_id}_0"
        try:
            return float(self._mod.lane.getMaxSpeed(first_lane))
        except Exception:
            return 13.89  # fallback ~50 km/h

    def get_edge_from_junction(self, edge_id: str) -> str:
        """Return the ID of the edge's source junction."""
        return self._mod.edge.getFromJunction(edge_id)

    def get_edge_to_junction(self, edge_id: str) -> str:
        """Return the ID of the edge's target junction."""
        return self._mod.edge.getToJunction(edge_id)

    # ------------------------------------------------------------------
    # Node / junction queries
    # ------------------------------------------------------------------

    def get_junction_ids(self) -> list[str]:
        """Return list of all junction (node) IDs."""
        return list(self._mod.junction.getIDList())

    def get_junction_position(self, junction_id: str) -> tuple[float, float]:
        """Return (x, y) position of a junction."""
        pos = self._mod.junction.getPosition(junction_id)
        return (float(pos[0]), float(pos[1]))

    # ------------------------------------------------------------------
    # Vehicle queries
    # ------------------------------------------------------------------

    def get_vehicle_ids(self) -> list[str]:
        """Return list of active vehicle IDs."""
        return list(self._mod.vehicle.getIDList())

    def get_vehicle_route(self, veh_id: str) -> list[str]:
        """Return the current route edge IDs for a vehicle."""
        return list(self._mod.vehicle.getRoute(veh_id))

    def get_vehicle_position(self, veh_id: str) -> tuple[float, float, str]:
        """Return (x, y, edge_id) for a vehicle's current position."""
        pos = self._mod.vehicle.getPosition(veh_id)
        edge_id = self._mod.vehicle.getRoadID(veh_id)
        return (float(pos[0]), float(pos[1]), str(edge_id))

    def get_vehicle_speed(self, veh_id: str) -> float:
        """Return current vehicle speed (m/s)."""
        return self._mod.vehicle.getSpeed(veh_id)

    def get_vehicle_type(self, veh_id: str) -> str:
        """Return the vehicle type ID."""
        return str(self._mod.vehicle.getTypeID(veh_id))

    def set_vehicle_route(self, veh_id: str, edge_ids: list[str]) -> None:
        """Set a vehicle's route to the given edge ID sequence."""
        self._mod.vehicle.setRoute(veh_id, edge_ids)

    def get_vehicle_emissions(self, veh_id: str) -> dict[str, float]:
        """Return emission values for a vehicle (g/s, mg/s)."""
        raw = self._mod.vehicle.getEmissionParameter(veh_id)
        if isinstance(raw, dict):
            return {k: float(v) for k, v in raw.items()}
        return {}

    # ------------------------------------------------------------------
    # Simulation queries
    # ------------------------------------------------------------------

    def get_simulation_time(self) -> int:
        """Return current simulation time in milliseconds."""
        return int(self._mod.simulation.getTime())

    def get_min_expected_number_vehicles(self) -> int:
        """Return total number of vehicles expected in the simulation."""
        return self._mod.simulation.getMinExpectedNumber()

    def get_teleport_count(self) -> int:
        """Return number of vehicles that started teleporting this timestep."""
        try:
            return self._mod.simulation.getStartingTeleportNumber()
        except Exception:
            return 0

    def get_arrived_count(self) -> int:
        """Return number of vehicles that arrived this timestep."""
        try:
            return self._mod.simulation.getArrivedNumber()
        except Exception:
            return 0