# Algorithm Notes

No routing or swarm algorithms are implemented in Phase 1 or Phase 2.

Before implementation, the following choices require explicit approval:

- ACO variant and primary reference.
- BCO variant and primary reference.
- PSO variant and primary reference.
- E3-Hybrid coordination strategy.
- EV energy-consumption model.
- Objective-function formulation.
- Emergency communication protocol.

Each future algorithm note must include theory, mathematical formulation,
pseudo-code, complexity analysis, design rationale, limitations, and primary
literature references.

## Dijkstra

Implementation: not started.

Required before implementation:

- Confirm objective compatibility.
- Confirm how blocked edges are represented to baselines.
- Confirm cost provider used for baseline comparisons.

## A*

Implementation: not started.

Required before implementation:

- Confirm admissible heuristic source.
- Confirm coordinate assumptions for heuristic distance.
- Confirm behavior when graph coordinates are unavailable.

## SUMO Baseline

Implementation: not started.

Required before implementation:

- Define whether this means SUMO fastest route, shortest route, or TraCI
  rerouting.
- Confirm what information the baseline receives to preserve fairness.

## ACO

Implementation: not started.

Required before implementation:

- Select exact ACO variant and primary paper.
- Define pheromone initialization and update rules from literature/config.
- Define candidate construction constraints.

## BCO

Implementation: not started.

Required before implementation:

- Select exact BCO/bee-colony variant and primary paper.
- Define scout, recruitment, and discovery behavior.
- Define how discovered alternatives are shared.

## PSO

Implementation: not started.

Required before implementation:

- Select exact discrete-route PSO variant and primary paper.
- Define route encoding and update operators.
- Define convergence and parameter adaptation rules.

## Hybrid

Implementation: not started.

Required before implementation:

- Define coordination strategy among ACO, BCO, and PSO.
- Define replaceable component interfaces.
- Confirm how the Decision Engine consumes hybrid outputs.
