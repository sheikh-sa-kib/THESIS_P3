"""Strongly typed identifiers for road-network entities."""

from typing import NewType

NodeId = NewType("NodeId", str)
EdgeId = NewType("EdgeId", str)
