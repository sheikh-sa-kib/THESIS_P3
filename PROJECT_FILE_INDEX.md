# Project File Index

## Source Code (`src/e3hybrid/`)

### `cli/` — Command-line interface
- `validate_config.py` — YAML config validation
- `write_metadata.py` — Environment metadata writer

### `communication/` — Message bus framework
- `bus.py` — MessageBus, Message, Packet
- `protocol.py` — Communication protocol types
- `subscription.py` — Subscription management

### `config/` — Configuration system
- `loader.py` — YAML loading and validation
- `schemas.py` — Typed configuration schemas

### `core/` — Core exceptions and shared types
- `exceptions.py` — Centralized exception hierarchy

### `decision/` — Decision engine
- `engine.py` — DecisionEngine
- `observation.py` — GraphSnapshot, VehicleObservation
- `observation_assembler.py` — ObservationAssembler
- `config.py` — DecisionConfig

### `emergency/` — Emergency framework
- (Various emergency modules)

### `network/` — Road network graph
- `graph.py` — DirectedGraph
- `node.py` — Node
- `edge.py` — Edge, MutableEdgeState
- `types.py` — NodeId, EdgeId

### `routing/` — Routing algorithms and benchmarks
- `protocol.py` — RoutingAlgorithm Protocol
- `dijkstra.py` — DijkstraRouting
- `astar.py` — AStarRouting
- `heuristic.py` — Heuristic Protocol and implementations
- `heuristic_factory.py` — HeuristicFactory
- `heuristic_validator.py` — HeuristicValidator
- `cost.py` — RouteCost
- `cost_calculator.py` — CompositeCostCalculator, CostWeights
- `candidate.py` — RouteCandidate, SearchStatistics
- `route.py` — Route, RouteSegment
- `request.py` — RoutingRequest
- `result.py` — RoutingResult
- `statistics.py` — RoutingStatistics
- `types.py` — RouteId
- `validator.py` — RouteValidator
- `verifier.py` — RoutingVerifier
- `exceptions.py` — RoutingError hierarchy
- `factory.py` — RoutingFactory (create_dijkstra, create_astar, create_aco)
- `benchmark_config.py` — BenchmarkConfig
- `benchmark_runner.py` — BenchmarkRunner
- `benchmark_scenario.py` — BenchmarkScenario
- `benchmark_result.py` — BenchmarkResult, BenchmarkSummary
- `benchmark_metrics.py` — AlgorithmMetadata, BenchmarkMetrics
- `benchmark_reporter.py` — BenchmarkReporter
- `benchmark_validator.py` — BenchmarkValidator

### `swarm/` — Swarm optimization infrastructure
- `__init__.py` — Public API exports (includes ACO components)
- `protocol.py` — SwarmAlgorithm Protocol
- `config.py` — SwarmConfig
- `context.py` — SwarmContext (with graph, cost_calculator)
- `models.py` — Solution, CandidateSolution, Population, etc.
- `state.py` — SwarmState
- `statistics.py` — SwarmStatistics, IterationStatistics
- `result.py` — SwarmResult
- `random.py` — SwarmRandom (named sub-streams)
- `lifecycle.py` — SwarmLifecycle
- `termination.py` — TerminationChecker, TerminationCondition
- `validator.py` — SwarmValidator, SwarmValidationReport
- `factory.py` — SwarmFactory
- `adapter.py` — SwarmToRoutingAdapter
- **`aco.py`** — ACS implementation (Phase 9B)

### `utils/` — Utilities
- `logging.py` — Logging configuration
- `reproducibility.py` — Environment metadata, SeededRandomFactory

### `vehicle/` — EV domain model
- `entity.py` — ElectricVehicle
- `battery.py` — Battery models
- `energy.py` — Energy models
- `state.py` — VehicleState
- `types.py` — VehicleId
- `factory.py` — VehicleFactory
- `validation.py` — Vehicle validation

## Tests (`tests/unit/`)

- `test_aco.py` — 98 ACS tests (Phase 9B) **NEW**
- `test_swarm_infrastructure.py` — 99 swarm infrastructure tests (Phase 8B)
- `test_dijkstra.py` — 37 Dijkstra tests (Phase 7B)
- `test_astar.py` — 73 A* tests (Phase 7D, 1 pre-existing failure)
- `test_benchmark.py` — Benchmark framework tests
- `test_network_core.py` — Graph tests
- `test_vehicle_core.py` — Vehicle tests
- `test_decision_engine.py` — Decision engine tests
- `test_emergency_core.py` — Emergency tests
- `test_communication_core.py` — Communication tests
- `test_config_loader.py` — Config tests
- `test_reproducibility.py` — Reproducibility tests
- (Additional test files for various modules)

## Documentation (`docs/`)

- `architecture.md` — System architecture and phase roadmap
- `aco_algorithm_design.md` — ACS algorithm design specification
- `astar_algorithm_design.md` — A* design specification
- `swarm_architecture_design.md` — Swarm architecture design
- `swarm_infrastructure_design.md` — Swarm implementation details
- `routing_architecture_design.md` — Routing architecture
- `routing_benchmark_design.md` — Benchmark design
- `algorithm_notes.md` — Algorithm implementation notes
- `api_reference.md` — Public API documentation
- `assumptions.md` — Design assumptions
- `communication_architecture.md` — Communication design
- `decision_engine_design.md` — Decision engine design
- `emergency_framework_design.md` — Emergency framework design
- `energy_model_design.md` — Energy model design
- `experiment_protocol.md` — Experiment protocol
- `literature_mapping.md` — Literature mapping
- `literature_traceability.md` — Source-to-implementation traceability
- `design_decisions.md` — Design decisions log (DD-001 through DD-046+)
- `development_log.md` — Phase-by-phase development history
- `research_documentation.md` — Documentation policy and status

## Project Management (Root Level)

- `PROJECT_MASTER_CONTEXT.md` — Current project state and roadmap
- `PROJECT_HANDOFF.md` — Handoff instructions
- `PROJECT_FILE_INDEX.md` — This file
- `PROJECT_STATUS.md` — Detailed status tracking
- `README.md` — Project overview
- `pyproject.toml` — Build configuration
- `.editorconfig` — Editor settings
- `.pre-commit-config.yaml` — Pre-commit hooks
