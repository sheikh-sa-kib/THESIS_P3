"""Unit tests for DecisionLog."""

from __future__ import annotations

import csv
from pathlib import Path
import tempfile

import pytest

from e3hybrid.decision.decision import Decision
from e3hybrid.decision.decision_log import DecisionLog
from e3hybrid.decision.policy import PolicyRecommendation
from e3hybrid.decision.types import DecisionType
from e3hybrid.vehicle.types import VehicleId


def test_decision_log_context_manager():
    """Test DecisionLog as a context manager."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = Path(tmpdir) / "test.csv"
        
        with DecisionLog(log_path) as log:
            assert log._initialized is True
        
        assert log._initialized is False


def test_decision_log_write_decision():
    """Test writing a decision to the log."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = Path(tmpdir) / "test.csv"
        
        recommendation = PolicyRecommendation(
            decision_type=DecisionType.KEEP_CURRENT_ROUTE,
            priority=50,
            confidence=1.0,
            explanation="Test recommendation",
            policy_name="test",
        )
        
        decision = Decision.create(
            vehicle_id=VehicleId("v1"),
            sim_time_s=10.0,
            decision_type=DecisionType.KEEP_CURRENT_ROUTE,
            trigger="test",
            explanation="Test decision",
            winning_policy="test",
            applied_policies=("test",),
            recommendations=(recommendation,),
        )
        
        with DecisionLog(log_path) as log:
            log.log(decision)
        
        # Verify the file was written
        assert log_path.exists()
        
        # Verify the content
        with log_path.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            assert len(rows) == 1
            assert rows[0]["vehicle_id"] == "v1"
            assert rows[0]["decision_type"] == "keep_current_route"


def test_decision_log_header_written_once():
    """Test that header is written only once."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = Path(tmpdir) / "test.csv"
        
        recommendation = PolicyRecommendation(
            decision_type=DecisionType.KEEP_CURRENT_ROUTE,
            priority=50,
            confidence=1.0,
            explanation="Test recommendation",
            policy_name="test",
        )
        
        decision = Decision.create(
            vehicle_id=VehicleId("v1"),
            sim_time_s=10.0,
            decision_type=DecisionType.KEEP_CURRENT_ROUTE,
            trigger="test",
            explanation="Test decision",
            winning_policy="test",
            applied_policies=("test",),
            recommendations=(recommendation,),
        )
        
        # Write first decision
        with DecisionLog(log_path) as log:
            log.log(decision)
        
        # Write second decision (should not write header again)
        with DecisionLog(log_path) as log:
            log.log(decision)
        
        with log_path.open("r", encoding="utf-8") as f:
            lines = f.readlines()
            # First line is header, then two data lines
            assert len(lines) == 3


def test_decision_log_get_log_path():
    """Test generation of standard log path."""
    output_dir = Path("/tmp/outputs")
    run_id = "test_run_001"
    
    log_path = DecisionLog.get_log_path(output_dir, run_id)
    
    assert log_path == output_dir / "decision_log_test_run_001.csv"


def test_decision_log_not_initialized_error():
    """Test error when logging without context manager."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = Path(tmpdir) / "test.csv"
        
        log = DecisionLog(log_path)
        
        recommendation = PolicyRecommendation(
            decision_type=DecisionType.KEEP_CURRENT_ROUTE,
            priority=50,
            confidence=1.0,
            explanation="Test recommendation",
            policy_name="test",
        )
        
        decision = Decision.create(
            vehicle_id=VehicleId("v1"),
            sim_time_s=10.0,
            decision_type=DecisionType.KEEP_CURRENT_ROUTE,
            trigger="test",
            explanation="Test decision",
            winning_policy="test",
            applied_policies=("test",),
            recommendations=(recommendation,),
        )
        
        with pytest.raises(RuntimeError, match="context manager"):
            log.log(decision)
