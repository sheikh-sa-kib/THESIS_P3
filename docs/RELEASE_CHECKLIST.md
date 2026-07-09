# Release Checklist

**Project:** E3-Hybrid — Dynamic EV Routing with Swarm Intelligence  
**Purpose:** Step-by-step process for releasing the thesis repository to GitHub.  
**Instructions:** Execute each step in order. Mark `[x]` when completed. If any step fails, stop and fix before continuing.

---

## Phase 1: Pre-Release Audit

- [ ] **1. Verify repository is clean**
  ```bash
  git status
  # Should show: nothing to commit, working tree clean
  ```

- [ ] **2. Verify no tracked cache/bytecode files**
  ```bash
  git ls-files "*.pyc" "*.pyo" "__pycache__" ".pytest_cache" ".mypy_cache" ".ruff_cache"
  # Should be empty
  ```

- [ ] **3. Verify no output data tracked**
  ```bash
  git ls-files outputs/
  # Should be empty
  ```

- [ ] **4. Verify no absolute paths in source code**
  ```bash
  grep -r '[A-Z]:\\' src/ scripts/ --include="*.py"
  # Should be empty
  ```

- [ ] **5. Verify no absolute paths in documentation (excluding this file)**
  ```bash
  grep -r '[A-Z]:\\' docs/ --include="*.md" --exclude="RELEASE_CHECKLIST.md"
  # Should be empty
  ```

- [ ] **6. Verify no TODO/FIXME/HACK remains in production code**
  ```bash
  grep -r "TODO\|FIXME\|HACK\|XXX" src/ scripts/
  # Should be empty
  ```

- [ ] **7. Run final audit**
  ```bash
  python scripts/run_validation.py
  # Expected: [PASS] All 6 algorithms compute routes
  # Expected: [PASS] SUMO simulation ran without errors
  ```

- [ ] **8. Run full test suite**
  ```bash
  pytest -v
  # Expected: No failures
  ```

- [ ] **9. Run deterministic replay tests**
  ```bash
  pytest tests/integration/test_determinism.py -v
  # Expected: All tests PASSED
  ```

- [ ] **10. Run acceptance tests**
  ```bash
  pytest tests/acceptance/ -v
  # Expected: All tests PASSED
  ```

- [ ] **11. Run short determinism smoke test (two runs, identical config)**
  ```bash
  python scripts/run_experiment.py --seed 42 --steps 20 --vehicles 5 --algorithms dijkstra --timeout 30
  python scripts/run_experiment.py --seed 42 --steps 20 --vehicles 5 --algorithms dijkstra --timeout 30
  ```
  Then verify CSVs are identical:
  ```bash
  diff <(head -2 outputs/experiments/run_*/metrics_summary.csv) <(head -2 outputs/experiments/run_*/metrics_summary.csv)
  # Should show no differences
  ```

---

## Phase 2: Cleanup

- [ ] **12. Remove all `__pycache__` directories**
  ```bash
  # On Windows
  Get-ChildItem -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force
  # On Linux/macOS
  find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
  ```

- [ ] **13. Remove .egg-info directory if present**
  ```bash
  Get-ChildItem -Recurse -Directory -Filter "*.egg-info" | Remove-Item -Recurse -Force
  ```

- [ ] **14. Clean up outputs directory**
  ```bash
  Remove-Item -Recurse -Force outputs/validation/* -ErrorAction SilentlyContinue
  Remove-Item -Recurse -Force outputs/experiments/* -ErrorAction SilentlyContinue
  Remove-Item -Recurse -Force outputs/logs/* -ErrorAction SilentlyContinue
  ```

- [ ] **15. Verify all documentation files present**
  ```bash
  # Algorithm docs
  Get-ChildItem docs/algorithms/*.md | ForEach-Object { $_.Name }
  # Should list: ACO.md, ASTAR.md, BCO.md, DIJKSTRA.md, E3_HYBRID.md, PSO.md, SIMULATION_VALIDATION.md
  ```

- [ ] **16. Verify essential scripts present**
  ```bash
  # Scripts
  Test-Path scripts/run_validation.py
  Test-Path scripts/run_experiment.py
  # Config
  Test-Path data/maps/midtown_manhattan.net.xml
  Test-Path data/routes/midtown_manhattan.rou.xml
  Test-Path data/configs/midtown_manhattan.sumocfg
  # Core
  Test-Path pyproject.toml
  Test-Path README.md
  ```

- [ ] **17. Verify .gitignore covers all required patterns**
  ```
  .venv/          # Virtual environment
  __pycache__/    # Python cache
  *.py[cod]       # Compiled bytecode
  *.egg-info/     # Package metadata
  .pytest_cache/  # Pytest cache
  .mypy_cache/    # Mypy cache
  .ruff_cache/    # Ruff cache
  .cache/         # General cache
  outputs/        # Experiment outputs
  htmlcov/        # Coverage HTML
  .coverage       # Coverage data
  *.log           # Log files
  trips.*.xml     # Intermediate trip files
  tmp_*.py        # Temporary scripts
  .DS_Store       # macOS metadata
  thumbs.db       # Windows metadata
  .env            # Environment variables
  .vscode/        # VS Code settings
  .idea/          # JetBrains IDE settings
  ```

---

## Phase 3: Commit

- [ ] **18. Stage all changes**
  ```bash
  git add -A
  ```

- [ ] **19. Verify staged changes are intentional**
  ```bash
  git status
  ```

- [ ] **20. Review diff**
  ```bash
  git diff --cached --stat
  # Verify only expected files are modified
  ```

- [ ] **21. Review diff for secrets or credentials**
  ```bash
  git diff --cached --check
  # Should show no issues
  ```

- [ ] **22. Commit with descriptive message**
  ```bash
  git commit -m "Thesis submission: E3-Hybrid swarm routing for EVs under urban emergencies

  - 6 routing algorithms: Dijkstra, A*, ACO, BCO, PSO, E3-Hybrid
  - Full SUMO 1.27.1 integration with TraCI
  - Emergency injection via graph-state updates (no algorithm-specific branches)
  - Experiment runner with CSV/plot outputs
  - Deterministic replay verification
  - Complete documentation suite"
  ```

---

## Phase 4: Push

- [ ] **23. Verify remote is correct**
  ```bash
  git remote -v
  # Verify origin points to the correct GitHub repository
  ```

- [ ] **24. Push to GitHub**
  ```bash
  git push origin main
  # (or master, depending on branch name)
  ```

- [ ] **25. Verify push succeeded**
  ```bash
  git log --oneline -5
  # Verify latest commit is on remote
  ```
  Visit the GitHub repository URL and verify all files appear correctly.

---

## Phase 5: Clone Verification

- [ ] **26. Clone on a fresh machine**
  ```bash
  git clone <repository-url> e3hybrid-verify
  cd e3hybrid-verify
  ```

- [ ] **27. Verify commit hash matches**
  ```bash
  git rev-parse HEAD
  # Should match the original commit
  ```

- [ ] **28. Create and verify environment**
  ```bash
  python3.12 -m venv .venv
  source .venv/bin/activate  # or .venv\Scripts\activate on Windows
  pip install -e ".[dev]"
  pip install matplotlib psutil
  ```

- [ ] **29. Verify SUMO is available**
  ```bash
  sumo --version
  # Must show: SUMO 1.27.1
  ```

- [ ] **30. Run smoke test**
  ```bash
  python scripts/run_validation.py
  # Expected: 6/6 PASS, 0 errors
  ```

- [ ] **31. Run short experiment**
  ```bash
  python scripts/run_experiment.py --seed 42 --steps 20 --vehicles 5 --algorithms dijkstra --timeout 30
  # Expected: completes successfully
  ```

---

## Phase 6: Full Verification (Optional, Time-Permitting)

- [ ] **32. Run full experiment**
  ```bash
  python scripts/run_experiment.py \
    --steps 300 --vehicles 300 --seed 42 \
    --algorithms dijkstra,astar,aco,bco,pso,e3hybrid \
    --reroute-interval 10 --emergency-count 3 --timeout 60
  # Expected: 20-35 minutes on mid-range hardware
  ```

- [ ] **33. Generate thesis figures**
  See `docs/FINAL_EXPERIMENT.md` section 22 for per-figure commands.

- [ ] **34. Verify CSV outputs against expected schema**
  ```bash
  # Verify metrics_summary.csv has required columns
  python -c "
  import csv
  with open('outputs/experiments/run_*/metrics_summary.csv') as f:
      reader = csv.DictReader(f)
      required = ['algorithm','total_reroutes','emergency_events','throughput']
      for col in required:
          assert col in reader.fieldnames, f'Missing column: {col}'
  print('Schema verified')
  "
  ```

---

## Phase 7: Archive

- [ ] **35. Archive experiment outputs**
  ```bash
  # Compress results for supplementary materials
  tar -czf thesis-experiment-results-<commit-hash>.tar.gz outputs/experiments/
  ```

- [ ] **36. Tag the release**
  ```bash
  git tag -a v1.0.0 -m "Thesis submission version"
  git push origin v1.0.0
  ```

---

## Phase 8: Post-Release

- [ ] **37. Create GitHub release**
  - Visit: `https://github.com/<username>/<repo>/releases`
  - Click "Create a new release"
  - Select tag: `v1.0.0`
  - Release title: "Thesis Submission — E3-Hybrid v1.0.0"
  - Description: Brief description of the thesis and repository contents
  - Attach: Experiment results archive (optional)

- [ ] **38. Verify GitHub release page is correct**
  - Source code archive (.zip, .tar.gz) attached automatically
  - Release notes visible
  - Tag points to correct commit

---

## Summary

| Phase | Steps | Status |
|-------|-------|--------|
| 1. Pre-Release Audit | 1–11 | [ ] |
| 2. Cleanup | 12–17 | [ ] |
| 3. Commit | 18–22 | [ ] |
| 4. Push | 23–25 | [ ] |
| 5. Clone Verification | 26–31 | [ ] |
| 6. Full Verification | 32–34 | [ ] |
| 7. Archive | 35–36 | [ ] |
| 8. Post-Release | 37–38 | [ ] |

---

*Generated: 2026-07-09*
