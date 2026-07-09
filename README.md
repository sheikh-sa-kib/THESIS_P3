# E3-Hybrid Swarm Routing for Electric Vehicles Under Dynamic Urban Emergencies

This repository contains the research software framework for an undergraduate
thesis on decentralized electric-vehicle routing under dynamic urban emergency
conditions.

The project is built in small reviewed phases. Phase 1 establishes only the
package skeleton, configuration foundations, logging, reproducibility utilities,
CLI entry points, tests, and documentation framework.

No routing, swarm optimization, SUMO integration, emergency simulation, or
metrics logic is implemented in Phase 1.

## Scientific Integrity

The framework is designed to produce reproducible experimental results without
hidden constants, fabricated metrics, privileged algorithm information, or biased
optimization. If E3-Hybrid performs worse than a baseline in a valid scenario,
that result must be preserved.

## Documentation

Research documentation lives in `docs/` and must be maintained alongside code.
It records design decisions, assumptions, algorithm notes, literature mapping,
experiment protocol, API notes, and the development log.
