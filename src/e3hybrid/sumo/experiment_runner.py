"""SumoExperimentRunner — orchestrates a complete SUMO experiment."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from e3hybrid.sumo.adapters import SumoRoutingAdapter
from e3hybrid.sumo.connection import SumoTraciConnection
from e3hybrid.sumo.emergency_manager import SumoEmergencyManager
from e3hybrid.sumo.network_importer import SumoNetworkImporter
from e3hybrid.sumo.rerouting_manager import SumoReroutingManager
from e3hybrid.sumo.simulation import SumoSimulation

if TYPE_CHECKING:
    from e3hybrid.network.graph import DirectedGraph
    from e3hybrid.routing.protocol import RoutingAlgorithm
    from e3hybrid.sumo.config import SumoConfig


@dataclass(frozen=True, slots=True)
class SumoExperimentResult:
    """Result of a SUMO experiment."""

    total_steps: int
    total_vehicles: int
    reroute_count: int
    simulation_time_ms: int
    algorithm_names: tuple[str, ...]
    emergency_event_count: int = 0
    reroute_repair_count: int = 0
    reroute_repair_fail_count: int = 0
    reroute_reject_count: int = 0
    metadata: dict[str, object] = field(default_factory=dict)


class SumoExperimentRunner:
    """Orchestrates a complete SUMO experiment.

    1. Load SumoConfig from file or Mapping
    2. Start SUMO via SumoTraciConnection
    3. Import network via SumoNetworkImporter
    4. Create routing algorithm instances
    5. Build vehicle-to-algorithm mapping
    6. Create SumoSimulation and SumoReroutingManager
    7. Run step loop
    8. Collect metrics
    9. Log results
    10. Shut down SUMO

    Parameters
    ----------
    config:
        The SUMO experiment configuration.
    """

    def __init__(self, config: SumoConfig) -> None:
        self._config = config
        self._result: SumoExperimentResult | None = None
        self._connection: SumoTraciConnection | None = None
        self._simulation: SumoSimulation | None = None
        self._rerouting_managers: list[SumoReroutingManager] = []
        self._emergency_manager: SumoEmergencyManager | None = None

    @property
    def config(self) -> SumoConfig:
        return self._config

    @property
    def result(self) -> SumoExperimentResult | None:
        """Return collected experiment result (None if not yet run)."""
        return self._result

    @property
    def simulation(self) -> SumoSimulation | None:
        """Return the simulation instance (None if not yet started)."""
        return self._simulation

    def run(
        self,
        algorithms: dict[str, RoutingAlgorithm],
        vehicle_algorithm_map: dict[str, list[str]],
        *,
        total_steps: int = 3600,
    ) -> SumoExperimentResult:
        """Run the SUMO experiment.

        Parameters
        ----------
        algorithms:
            Mapping of algorithm_name -> RoutingAlgorithm instance.
        vehicle_algorithm_map:
            Mapping of algorithm_name -> list of vehicle IDs.
        total_steps:
            Number of simulation steps to run (default 3600 = 1 hour at 1s step).

        Returns
        -------
        SumoExperimentResult
            Collected metrics from the experiment.
        """
        # 1. Start SUMO
        connection = SumoTraciConnection(self._config)
        connection.start()
        self._connection = connection

        try:
            # 2. Import network
            importer = SumoNetworkImporter(connection)
            graph = importer.import_graph()

            # 3. Create routing adapters
            adapters: dict[str, SumoRoutingAdapter] = {}
            for algo_name, algo_instance in algorithms.items():
                adapters[algo_name] = SumoRoutingAdapter(algo_instance)

            # 4. Set up simulation
            sim = SumoSimulation(connection, self._config, graph)
            self._simulation = sim

            # 5. Set up emergency event infrastructure
            emergency_manager = SumoEmergencyManager(
                connection=connection,
                config=self._config,
                graph=graph,
            )
            self._emergency_manager = emergency_manager

            # 6. Set up rerouting managers (one per algorithm group)
            self._rerouting_managers = []
            for algo_name, vehicle_ids in vehicle_algorithm_map.items():
                if algo_name not in adapters:
                    continue
                reroute_mgr = SumoReroutingManager(
                    connection=connection,
                    config=self._config,
                    algorithm=adapters[algo_name],
                    vehicle_ids=vehicle_ids,
                )
                self._rerouting_managers.append(reroute_mgr)

            total_reroutes = 0
            total_repairs = 0
            total_repair_fails = 0
            total_rejects = 0
            total_emergency_events = 0

            # 7. Step loop with integrated rerouting and emergency handling
            for step_idx in range(total_steps):
                sim_time_ms = sim.step()

                emergency_events = emergency_manager.check_and_respond(sim_time_ms)
                if emergency_events:
                    total_emergency_events += len(emergency_events)

                for mgr in self._rerouting_managers:
                    if mgr.should_reroute(sim.step_count):
                        graph_snapshot = sim.graph
                        reroutes = mgr.compute_reroutes(graph_snapshot)
                        if reroutes:
                            mgr.apply_reroutes(reroutes)
                            total_reroutes += len(reroutes)

            # Aggregate reroute stats across all managers.
            for mgr in self._rerouting_managers:
                total_repairs += mgr.repair_count
                total_repair_fails += mgr.repair_fail_count
                total_rejects += mgr.reject_count

            # 8. Collect result
            all_vehicles: set[str] = set()
            for veh_list in vehicle_algorithm_map.values():
                all_vehicles.update(veh_list)

            self._result = SumoExperimentResult(
                total_steps=total_steps,
                total_vehicles=len(all_vehicles),
                reroute_count=total_reroutes,
                simulation_time_ms=connection.get_simulation_time(),
                algorithm_names=tuple(algorithms.keys()),
                emergency_event_count=total_emergency_events,
                reroute_repair_count=total_repairs,
                reroute_repair_fail_count=total_repair_fails,
                reroute_reject_count=total_rejects,
            )

        except Exception:
            self._cleanup()
            raise

        # 8. Shut down SUMO
        self._cleanup()

        return self._result

    def _cleanup(self) -> None:
        if self._connection is not None:
            try:
                self._connection.stop()
            except Exception:
                pass
            self._connection = None
        self._simulation = None