# Experiment Protocol

---

## 1. Status

No automated experiment runner is implemented yet. This document records the
protocol that the future experiment runner must satisfy.

---

## 2. Required Run Artifacts

Every experiment run must produce a dedicated output folder named with the
UTC timestamp of the run start:

```
outputs/
  run_2026-07-08_14-35-21/
      config_snapshot.yaml        # exact copy of the YAML config used
      environment.json            # from collect_environment_metadata()
      git_commit.txt              # bare commit hash, or "unversioned"
      network_metadata.json       # node/edge counts, schema_version, source
      scenario_metadata.json      # scenario name, seed, demand parameters
      routing_log.csv             # per-vehicle routing decisions with timestamps
      vehicle_states.csv          # SoC, position, speed per vehicle per tick
      communication_log.csv       # V2V / V2I message log
      emergency_log.csv           # emergency events with location and duration
      metrics.csv                 # aggregate per-algorithm metrics
      plots/
          soc_over_time.png
          travel_time_cdf.png
          emergency_response_cdf.png
          network_utilization.png
```

This structure makes every run self-contained, auditable, and reproducible
without relying on external state. If two runs produce the same folder name
(unlikely due to second resolution), the second run must fail loudly rather
than silently overwrite the first.

The run folder name format is: `run_YYYY-MM-DD_HH-MM-SS` (UTC).

---

## 3. Minimum Content Requirements

| Artifact                 | Required content                                                   |
|--------------------------|--------------------------------------------------------------------|
| `config_snapshot.yaml`   | Byte-identical copy of the config file at run start                |
| `environment.json`       | Python version, OS, packages, git commit, seed, timestamp          |
| `git_commit.txt`         | Output of `git rev-parse HEAD`, or the string `"unversioned"`      |
| `network_metadata.json`  | `schema_version`, `node_count`, `edge_count`, `validation_status`  |
| `scenario_metadata.json` | Scenario name, random seed, demand model name and parameters       |
| `routing_log.csv`        | Columns: tick, vehicle_id, algorithm, route_id, cost               |
| `vehicle_states.csv`     | Columns: tick, vehicle_id, soc_kwh, position_node, speed_mps       |
| `communication_log.csv`  | Columns: tick, sender_id, receiver_id, message_type, latency_ms    |
| `emergency_log.csv`      | Columns: tick, event_id, event_type, affected_edges, duration_s    |
| `metrics.csv`            | Columns: algorithm, metric_name, value, unit                       |

---

## 4. Reproducibility Requirements

Every run must record:

- Configuration snapshot.
- Git commit hash when available.
- Random seed used for every named stream.
- Algorithm name and all parameters used.
- Wall-clock execution time.
- Full environment metadata (Python version, OS, CPU, installed packages).
- SUMO version when SUMO is used.
- Logs at INFO level minimum; DEBUG level on request.
- Raw simulation traces (vehicle states, events) before any aggregation.
- Metrics derived **only** from recorded simulation state — never from
  intermediate in-memory values that are not written to disk.

---

## 5. Scientific Integrity Rules

- If E3-Hybrid performs worse than a baseline in a valid scenario, that result
  must be preserved and reported. Results must never be selectively discarded.
- Metric aggregations must reference the raw `vehicle_states.csv` and
  `routing_log.csv` they were derived from.
- No algorithm may receive information that another algorithm does not receive
  in a comparable scenario unless this asymmetry is explicitly documented and
  justified in `design_decisions.md`.

---

## 6. Configuration for Output Path

The experiment output root is controlled by:

```yaml
experiment:
  name: my_run
  seed: 42
  output_dir: outputs/runs
```

The experiment runner will create the timestamped subfolder under `output_dir`.
`output_dir` must be a relative path with no parent traversal.
