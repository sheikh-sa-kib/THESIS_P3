# Routing Benchmark and Verification Framework

**Status:** Phase 7C — Complete (approved)

---

## 1. Purpose

The benchmark framework provides a **fair, reproducible, algorithm-independent**
system for evaluating all routing algorithms (Dijkstra, A\*, ACO, BCO, PSO,
E³-Hybrid, SUMO Baseline) under identical conditions.

Every algorithm is evaluated using:
- Same graph
- Same routing requests
- Same random seed
- Same cost provider
- Same configuration
- Same timeout
- Same graph state

No algorithm receives privileged information or special treatment.

---

## 2. Benchmark Lifecycle

```
Load BenchmarkConfig
↓
Validate configuration
↓
For each algorithm:
│
├── Create algorithm instance (via RoutingFactory)
├── For each request:
│   ├── Execute algorithm.compute_route(request, graph)
│   ├── Verify result (if enabled)
│   └── Collect metrics
│
├── Compute summary statistics
└── Store BenchmarkResult
│
For each result:
└── Write benchmark artifacts
    ├── benchmark_summary.csv
    ├── routing_results.csv
    ├── verification_report.csv
    ├── metadata.json
    └── configuration_snapshot.yaml
```

The `BenchmarkRunner` never inspects algorithm internals. It interacts with
algorithms only through the `RoutingAlgorithm` Protocol.

---

## 3. Verification Pipeline

The `RoutingVerifier` provides algorithm-independent verification:

```
RoutingVerifier
├── verify_route(route, graph)          → VerificationReport
│   ├── Node sequence non-empty
│   ├── Edge sequence length matches
│   ├── All nodes exist in graph
│   ├── All edges exist in graph
│   ├── Edge connectivity (edges connect consecutive nodes)
│   ├── No blocked edges (unless allowed)
│   ├── Source/destination match request
│   └── Distance consistency
│
├── verify_result(result, graph)        → VerificationReport
│   ├── Success/failure invariants
│   ├── Runtime non-negative
│   ├── Statistics valid
│   ├── Candidates valid
│   └── Primary route valid
│
├── verify_candidate(candidate, graph)  → VerificationReport
│   ├── Node/edge sequence valid
│   ├── All nodes and edges exist
│   ├── Edge connectivity
│   ├── Cost non-negative
│   ├── Algorithm name non-empty
│   └── Source/destination match request
│
├── verify_graph_integrity(graph)       → VerificationReport
│   ├── Outgoing adjacency consistent
│   ├── Incoming adjacency consistent
│   ├── Edge references valid
│   └── Source/target nodes exist
│
├── verify_deterministic_replay(algo, request, graph) → DeterministicReplayReport
│   ├── Multiple runs with deep copy
│   ├── Cost consistency across runs
│   ├── Route consistency across runs
│   └── Success consistency across runs
│
├── verify_cost_breakdown(candidate)    → VerificationReport
│
├── compute_expected_distance(route, graph)    → float
├── compute_expected_travel_time(route, graph) → float
└── compute_expected_cost(route, cost_calculator, graph) → float
```

All verification methods are algorithm-independent. They work on `Route`,
`RouteCandidate`, `RoutingResult`, and `DirectedGraph` — never on
algorithm-specific internals.

---

## 4. Metric Definitions

### BenchmarkMetrics (per request)

| Metric | Definition | Unit |
|--------|-----------|------|
| `algorithm_name` | Name of the routing algorithm | — |
| `runtime_s` | Wall-clock time for `compute_route()` | seconds |
| `expanded_nodes` | Nodes popped from priority queue / search frontier | count |
| `visited_nodes` | Nodes marked as visited / explored | count |
| `route_distance_m` | Total length of primary route (sum of edge lengths) | meters |
| `travel_time_s` | Estimated travel time of primary route | seconds |
| `total_cost` | Total cost of the best route (from CostProvider) | — |
| `route_valid` | Whether the route passed all verification checks | boolean |
| `success` | Whether routing succeeded (path found) | boolean |
| `failure_reason` | Human-readable failure explanation | string or null |
| `candidates_generated` | Number of route candidates returned | count |
| `memory_bytes` | Peak memory usage (optional, disabled by default) | bytes |

### BenchmarkSummary (aggregate)

| Metric | Definition |
|--------|-----------|
| `total_requests` | Number of routing requests executed |
| `successful_requests` | Requests where a route was found |
| `failed_requests` | Requests where no route was found |
| `avg_runtime_s` | Mean runtime per successful request |
| `max_runtime_s` | Maximum runtime across all requests |
| `min_runtime_s` | Minimum runtime across all requests |
| `avg_route_distance_m` | Mean route distance (successful only) |
| `avg_travel_time_s` | Mean estimated travel time (successful only) |
| `avg_total_cost` | Mean total cost (successful only) |
| `total_expanded_nodes` | Sum of expanded nodes across all requests |
| `avg_expanded_nodes` | Mean expanded nodes per request |
| `total_verified` | Number of routes that passed verification |
| `verification_failures` | Number of routes that failed verification |

---

## 5. Fairness Guarantees

The framework enforces fair comparison through structural guarantees:

### Identical Conditions

| Condition | Enforced By |
|-----------|-------------|
| Same graph | Single `DirectedGraph` passed to all algorithms |
| Same requests | Identical `BenchmarkRequest` sequence for all algorithms |
| Same seed | Single `BenchmarkConfig.seed` for all algorithms |
| Same cost provider | Algorithms use `CostProvider` through `RoutingAlgorithm` Protocol |
| Same configuration | Same `BenchmarkConfig` for all algorithms |
| Same timeout | Same `timeout_s` value for every request |
| Same graph state | Graph state is unchanged between algorithm runs |

### No Algorithm-Specific Advantages

- All algorithms access the graph through the same interface.
- All algorithms receive identical `RoutingRequest` objects.
- All algorithms have the same timeout constraints.
- All algorithms are verified using the same `RoutingVerifier`.
- All metrics are collected using the same procedure.

### Verification During Benchmark

When `verify_routes=True`, every route is verified immediately after computation.
Any verification failure is recorded in the `verification_report.csv` output.
This catches implementation bugs and ensures data integrity before analysis.

---

## 6. Artifact Formats

### Directory Structure

```
results/
  run_20260708_143021/
    benchmark_summary.csv
    routing_results.csv
    verification_report.csv
    metadata.json
    configuration_snapshot.yaml
```

### benchmark_summary.csv

```
algorithm,scenario,total_requests,successful_requests,failed_requests,avg_runtime_s,max_runtime_s,min_runtime_s,avg_route_distance_m,avg_travel_time_s,avg_total_cost,total_expanded_nodes,avg_expanded_nodes,total_verified,verification_failures
```

One row per algorithm per scenario.

### routing_results.csv

```
algorithm,scenario,request_index,request_description,success,failure_reason,runtime_s,expanded_nodes,visited_nodes,candidates_generated,route_distance_m,travel_time_s,total_cost,route_valid,memory_bytes
```

One row per request per algorithm.

### verification_report.csv

```
algorithm,scenario,request_index,is_valid,checks_performed,checks_passed,errors
```

One row per request per algorithm. The `errors` field is a semicolon-separated
list of `check_name: message` pairs for any failed checks.

### metadata.json

Contains benchmark metadata, configuration, per-algorithm summaries, and
timestamps in JSON format.

### configuration_snapshot.yaml

Complete benchmark configuration in YAML format, as a record of exactly how
the benchmark was configured.

---

## 7. Reproducibility Strategy

Every benchmark run records:

1. **Configuration snapshot** — exact `BenchmarkConfig` used
2. **Timestamp** — ISO-8601 UTC timestamp of when the benchmark was run
3. **Per-algorithm metadata** — algorithm name, version, parameters
4. **Per-request results** — all metrics for every individual request
5. **Verification results** — every check performed and its outcome

Given the same:
- Graph (same topological structure and edge states)
- Requests (same source-destination pairs)
- Configuration (same seed, weights, timeout)
- Algorithm version (same code)

The benchmark produces identical results across runs. This is verified by
`RoutingVerifier.verify_deterministic_replay()`.

---

## 8. Design Decisions

### DD-036: Algorithm-Independent Verification

The `RoutingVerifier` operates only on `Route`, `RoutingResult`,
`RouteCandidate`, and `DirectedGraph`. It never imports algorithm-specific
modules. This ensures verification is fair and reusable across all algorithms.

### DD-037: Standardized Metric Collection

All metrics are collected by the `BenchmarkRunner` from `RoutingResult` and
`RoutingStatistics`. Algorithms do not report custom metrics. This prevents
algorithm-specific metric bias and ensures comparability.

### DD-038: Separate Artifact Writing

The `BenchmarkReporter` is separate from `BenchmarkRunner`. This allows
artifact formats to change without modifying benchmark execution logic,
and allows results to be re-exported in different formats after the fact.

### DD-039: Optional Memory Collection

Memory collection via `tracemalloc` is disabled by default because it adds
overhead and may perturb timing measurements. It can be enabled for specific
memory profiling runs.

### DD-040: Verification Is Not Optional for Quality

While `verify_routes` can be disabled for performance benchmarking, it should
always be enabled during development and testing. Every algorithm should pass
verification before being accepted into the benchmark suite.
