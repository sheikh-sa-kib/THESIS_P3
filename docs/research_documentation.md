# Research Documentation Policy

Documentation must be maintained alongside the code.

The required research documents are:

- `architecture.md`
- `design_decisions.md`
- `algorithm_notes.md`
- `literature_mapping.md`
- `assumptions.md`
- `experiment_protocol.md`
- `api_reference.md`
- `development_log.md`
- `energy_model_design.md`
- `communication_architecture.md`
- `emergency_framework_design.md`
- `decision_engine_design.md`

Every future phase must update the relevant document before review. Design
changes belong in `design_decisions.md`; unknown or deferred choices belong in
`assumptions.md`; algorithm-specific rationale belongs in `algorithm_notes.md`;
and literature-backed formulas belong in `literature_mapping.md`.

---

## Phase 6 Documentation Status

All documentation updated for Decision Engine implementation:
- `architecture.md` — Phase 6 marked as complete
- `api_reference.md` — Phase 6 public interfaces documented
- `development_log.md` — Phase 6 implementation details recorded
- `design_decisions.md` — DD-021 through DD-027 added for approved decisions

---

## Phase 7A Documentation Status

All documentation updated for Routing Architecture design:
- `routing_architecture_design.md` — complete 18-section design document created
- `architecture.md` — Phase 7A marked as complete (awaiting approval)
- `api_reference.md` — Phase 7A planned interfaces documented
- `development_log.md` — Phase 7A design details recorded
- `design_decisions.md` — DD-028 through DD-035 added for routing architecture decisions

---

## Phase 7B Documentation Status

All documentation updated for Dijkstra baseline routing:
- `architecture.md` — Phase 7B marked as complete (approved)
- `api_reference.md` — Phase 7B interfaces documented as implemented
- `development_log.md` — Phase 7B implementation details recorded
- Dijkstra implementation tested: 18/18 tests pass, 91% code coverage
- Routing framework with 12 components implemented and verified

---

## Phase 7C Documentation Status

All documentation updated for benchmark and verification framework:
- `routing_benchmark_design.md` — complete design document created
- `architecture.md` — Phase 7C marked as complete (approved)
- `development_log.md` — Phase 7C implementation details recorded
- 53 comprehensive unit tests pass covering all benchmark components
- Benchmark framework reusable without modification for all future routing algorithms

---

## Phase 7D Documentation Status

A* baseline routing with heuristic architecture — Complete:
- `astar_algorithm_design.md` — full design document with algorithm overview, heuristic theory, complexity analysis
- `architecture.md` — Phase 7D marked as complete
- `api_reference.md` — Phase 7D public interfaces documented
- `development_log.md` — Phase 7D implementation details recorded
- `design_decisions.md` — DD-041 through DD-043 added for heuristic architecture decisions
- AStarRouting implements RoutingAlgorithm Protocol with same interface as Dijkstra
- Heuristic Protocol with ZeroHeuristic, EuclideanHeuristic, ManhattanHeuristic
- HeuristicFactory for configuration-driven heuristic selection
- HeuristicValidator for admissibility and consistency verification
- 135/135 tests pass across A*, Dijkstra, and Benchmark suites
- A* with ZeroHeuristic produces identical results to Dijkstra (verified by test suite)

---

## Phase 8A Documentation Status

Common swarm architecture design — Complete (approved):
- `swarm_architecture_design.md` — complete 12-section design document created
- `architecture.md` — Phase 8A marked as complete (approved)
- `api_reference.md` — Phase 8A planned interfaces documented
- `development_log.md` — Phase 8A design details recorded
- `design_decisions.md` — DD-044 through DD-046 added for swarm architecture decisions

---

## Phase 8B Documentation Status

Common swarm infrastructure implementation — Complete (awaiting approval):
- `swarm_infrastructure_design.md` — implementation details document created
- `architecture.md` — Phase 8B marked as complete (awaiting approval)
- `api_reference.md` — Phase 8B interfaces documented as implemented
- `development_log.md` — Phase 8B implementation details recorded
- 99 comprehensive unit tests pass
- All 135 existing routing tests still pass (234 total)
- No references to ACO, BCO, PSO, or E³-Hybrid anywhere in the framework
