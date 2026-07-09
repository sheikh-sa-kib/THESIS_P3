"""Unit tests for Decision validation."""

from __future__ import annotations

import pytest

from e3hybrid.decision.decision import Decision
from e3hybrid.decision.policy import PolicyRecommendation
from e3hybrid.decision.types import DecisionType
from e3hybrid.decision.validation import (
    DecisionValidationError,
    DecisionValidationReport,
    DecisionValidator,
)
from e3hybrid.vehicle.types import VehicleId


def test_decision_validator_valid_decision():
    """Test validation of a valid decision."""
    validator = DecisionValidator()

    recommendation = PolicyRecommendation(
        decision_type=DecisionType.KEEP_CURRENT_ROUTE,
        priority=50,
        confidence=1.0,
        explanation="Valid decision",
        policy_name="test",
    )

    decision = Decision.create(
        vehicle_id=VehicleId("v1"),
        sim_time_s=10.0,
        decision_type=DecisionType.KEEP_CURRENT_ROUTE,
        trigger="test",
        explanation="Valid decision explanation",
        winning_policy="test",
        applied_policies=("test",),
        recommendations=(recommendation,),
    )

    report = validator.validate(decision)
    assert report.is_valid is True
    assert len(report.errors) == 0


def test_decision_validator_empty_explanation():
    """Test validation fails with empty explanation."""
    validator = DecisionValidator()

    recommendation = PolicyRecommendation(
        decision_type=DecisionType.KEEP_CURRENT_ROUTE,
        priority=50,
        confidence=1.0,
        explanation="Valid recommendation",
        policy_name="test",
    )

    with pytest.raises(Exception):  # DecisionError from __post_init__
        Decision.create(
            vehicle_id=VehicleId("v1"),
            sim_time_s=10.0,
            decision_type=DecisionType.KEEP_CURRENT_ROUTE,
            trigger="test",
            explanation="",  # Empty explanation
            winning_policy="test",
            applied_policies=("test",),
            recommendations=(recommendation,),
        )


def test_decision_validator_invalid_confidence():
    """Test validation fails with invalid confidence."""
    validator = DecisionValidator()

    recommendation = PolicyRecommendation(
        decision_type=DecisionType.KEEP_CURRENT_ROUTE,
        priority=50,
        confidence=1.5,  # Invalid: > 1.0
        explanation="Valid recommendation",
        policy_name="test",
    )

    with pytest.raises(Exception):  # DecisionError from PolicyRecommendation
        Decision.create(
            vehicle_id=VehicleId("v1"),
            sim_time_s=10.0,
            decision_type=DecisionType.KEEP_CURRENT_ROUTE,
            trigger="test",
            explanation="Valid decision",
            winning_policy="test",
            applied_policies=("test",),
            recommendations=(recommendation,),
        )


def test_decision_validator_veto_consistency():
    """Test validation fails when veto has confidence < 1.0."""
    validator = DecisionValidator()

    recommendation = PolicyRecommendation(
        decision_type=DecisionType.EMERGENCY_STOP,
        priority=100,
        confidence=0.9,  # Invalid: veto must have confidence=1.0
        explanation="Emergency",
        policy_name="test",
        veto=True,
    )

    with pytest.raises(Exception):  # DecisionError from PolicyRecommendation
        Decision.create(
            vehicle_id=VehicleId("v1"),
            sim_time_s=10.0,
            decision_type=DecisionType.EMERGENCY_STOP,
            trigger="emergency",
            explanation="Emergency stop",
            winning_policy="test",
            applied_policies=("test",),
            recommendations=(recommendation,),
            veto=True,
            confidence=0.9,
        )


def test_decision_validator_winning_policy_not_in_applied():
    """Test validation fails when winning_policy is not in applied_policies."""
    validator = DecisionValidator()

    recommendation = PolicyRecommendation(
        decision_type=DecisionType.KEEP_CURRENT_ROUTE,
        priority=50,
        confidence=1.0,
        explanation="Valid recommendation",
        policy_name="test",
    )

    decision = Decision.create(
        vehicle_id=VehicleId("v1"),
        sim_time_s=10.0,
        decision_type=DecisionType.KEEP_CURRENT_ROUTE,
        trigger="test",
        explanation="Valid decision",
        winning_policy="other",  # Not in applied_policies
        applied_policies=("test",),
        recommendations=(recommendation,),
    )

    report = validator.validate(decision)
    assert report.is_valid is False
    assert any(e.field_name == "winning_policy" for e in report.errors)


def test_decision_validation_report_str():
    """Test string representation of validation report."""
    report = DecisionValidationReport(
        is_valid=False,
        errors=(
            DecisionValidationError(field_name="test", error_message="error"),
        ),
    )
    str_repr = str(report)
    assert "validation failed" in str_repr.lower()
    assert "test" in str_repr
