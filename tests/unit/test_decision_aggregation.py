"""Unit tests for DecisionAggregationPolicy."""

from __future__ import annotations

import pytest

from e3hybrid.decision.aggregation import DecisionAggregationPolicy
from e3hybrid.decision.policy import PolicyRecommendation
from e3hybrid.decision.types import DecisionType
from e3hybrid.vehicle.types import VehicleId


def test_aggregation_no_recommendations():
    """Test aggregation with no recommendations."""
    aggregator = DecisionAggregationPolicy()
    
    decision = aggregator.aggregate(
        vehicle_id=VehicleId("v1"),
        sim_time_s=10.0,
        recommendations=(),
    )
    
    assert decision.decision_type == DecisionType.KEEP_CURRENT_ROUTE
    assert decision.winning_policy == "fallback"
    assert decision.veto is False


def test_aggregation_single_recommendation():
    """Test aggregation with a single recommendation."""
    aggregator = DecisionAggregationPolicy()
    
    recommendation = PolicyRecommendation(
        decision_type=DecisionType.REQUEST_REROUTE,
        priority=50,
        confidence=0.9,
        explanation="Test recommendation",
        policy_name="test",
    )
    
    decision = aggregator.aggregate(
        vehicle_id=VehicleId("v1"),
        sim_time_s=10.0,
        recommendations=(recommendation,),
    )
    
    assert decision.decision_type == DecisionType.REQUEST_REROUTE
    assert decision.winning_policy == "test"
    assert decision.veto is False


def test_aggregation_veto_takes_precedence():
    """Test that veto recommendations take precedence."""
    aggregator = DecisionAggregationPolicy()
    
    veto_rec = PolicyRecommendation(
        decision_type=DecisionType.EMERGENCY_STOP,
        priority=100,
        confidence=1.0,
        explanation="Emergency",
        policy_name="safety",
        veto=True,
    )
    
    normal_rec = PolicyRecommendation(
        decision_type=DecisionType.REQUEST_REROUTE,
        priority=50,
        confidence=0.9,
        explanation="Reroute",
        policy_name="routing",
    )
    
    decision = aggregator.aggregate(
        vehicle_id=VehicleId("v1"),
        sim_time_s=10.0,
        recommendations=(veto_rec, normal_rec),
    )
    
    assert decision.decision_type == DecisionType.EMERGENCY_STOP
    assert decision.winning_policy == "safety"
    assert decision.veto is True


def test_aggregation_highest_priority_wins():
    """Test that highest priority wins when no veto."""
    aggregator = DecisionAggregationPolicy()
    
    low_rec = PolicyRecommendation(
        decision_type=DecisionType.KEEP_CURRENT_ROUTE,
        priority=30,
        confidence=0.8,
        explanation="Low priority",
        policy_name="low",
    )
    
    high_rec = PolicyRecommendation(
        decision_type=DecisionType.REQUEST_REROUTE,
        priority=70,
        confidence=0.9,
        explanation="High priority",
        policy_name="high",
    )
    
    decision = aggregator.aggregate(
        vehicle_id=VehicleId("v1"),
        sim_time_s=10.0,
        recommendations=(low_rec, high_rec),
    )
    
    assert decision.decision_type == DecisionType.REQUEST_REROUTE
    assert decision.winning_policy == "high"


def test_aggregation_confidence_tiebreaker():
    """Test that confidence breaks priority ties."""
    aggregator = DecisionAggregationPolicy()
    
    rec1 = PolicyRecommendation(
        decision_type=DecisionType.REQUEST_REROUTE,
        priority=50,
        confidence=0.7,
        explanation="Lower confidence",
        policy_name="policy1",
    )
    
    rec2 = PolicyRecommendation(
        decision_type=DecisionType.REQUEST_REROUTE,
        priority=50,
        confidence=0.9,
        explanation="Higher confidence",
        policy_name="policy2",
    )
    
    decision = aggregator.aggregate(
        vehicle_id=VehicleId("v1"),
        sim_time_s=10.0,
        recommendations=(rec1, rec2),
    )
    
    assert decision.winning_policy == "policy2"


def test_aggregation_multiple_vetos():
    """Test that highest-priority veto wins when multiple vetos exist."""
    aggregator = DecisionAggregationPolicy()
    
    veto_low = PolicyRecommendation(
        decision_type=DecisionType.WAIT,
        priority=80,
        confidence=1.0,
        explanation="Low veto",
        policy_name="low",
        veto=True,
    )
    
    veto_high = PolicyRecommendation(
        decision_type=DecisionType.EMERGENCY_STOP,
        priority=100,
        confidence=1.0,
        explanation="High veto",
        policy_name="high",
        veto=True,
    )
    
    decision = aggregator.aggregate(
        vehicle_id=VehicleId("v1"),
        sim_time_s=10.0,
        recommendations=(veto_low, veto_high),
    )
    
    assert decision.decision_type == DecisionType.EMERGENCY_STOP
    assert decision.winning_policy == "high"
    assert decision.veto is True


def test_aggregation_applied_policies_recorded():
    """Test that all applied policies are recorded."""
    aggregator = DecisionAggregationPolicy()
    
    rec1 = PolicyRecommendation(
        decision_type=DecisionType.KEEP_CURRENT_ROUTE,
        priority=30,
        confidence=0.8,
        explanation="Policy 1",
        policy_name="policy1",
    )
    
    rec2 = PolicyRecommendation(
        decision_type=DecisionType.REQUEST_REROUTE,
        priority=70,
        confidence=0.9,
        explanation="Policy 2",
        policy_name="policy2",
    )
    
    decision = aggregator.aggregate(
        vehicle_id=VehicleId("v1"),
        sim_time_s=10.0,
        recommendations=(rec1, rec2),
    )
    
    assert "policy1" in decision.applied_policies
    assert "policy2" in decision.applied_policies
    assert len(decision.applied_policies) == 2
