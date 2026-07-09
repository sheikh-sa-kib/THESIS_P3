# Assumptions

This document records assumptions so they remain visible and reviewable.

---

## Phase 1

- Python 3.12 or newer is targeted because the available bundled runtime is
  Python 3.12.13 and modern typing features are required.
- PyYAML is declared as a project dependency for YAML parsing; no custom YAML
  parser is introduced.
- No algorithmic, EV energy, emergency, communication, or objective-function
  assumptions are made in Phase 1.

---

## Phase 2

- The internal graph is simulator-agnostic and does not depend on SUMO.
- Synthetic networks under `network.fixtures` exist only for unit tests and
  must not be used as thesis evidence.
- Travel-time edge cost is a structural utility based on edge length and
  effective speed. It is not a routing algorithm.
- Node coordinates (`x`, `y`) are optional. Their absence does not break graph
  construction or traversal. Algorithms that require Euclidean distance (e.g.,
  the A* heuristic) must handle `None` coordinates explicitly.
- The adjacency-list representation is chosen over an adjacency matrix because
  road networks are sparse. For a 10,000-node city graph an adjacency matrix
  would require 100 million entries; adjacency lists keep memory proportional
  to actual road density.
- Insertion order in `dict` is guaranteed by CPython 3.7+ and is relied upon
  for deterministic graph traversal in experiments.

---

## Phase 3

- The `ElectricVehicle` and `Battery` domain models represent EV state during
  simulation. They do not implement charging-station logic, V2G, or fleet
  management — those are future phases.
- The energy consumption model interface is defined as a replaceable interface
  (`EnergyModel`) but **no physics equations or constants are implemented**
  until an explicit literature model is approved. See `algorithm_notes.md`.
- Battery capacity, initial SoC, and minimum SoC are treated as
  configuration parameters. They must not be hard-coded.
- Vehicle constraints (min/max SoC, max speed, payload) are validated at
  construction time. Violations raise `VehicleError`.
- The `VehicleFactory` creates vehicles from validated configuration mappings.
  It does not decide routing or communication behavior.
