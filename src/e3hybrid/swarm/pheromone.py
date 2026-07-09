"""HybridPheromoneMatrix — sparse pheromone matrix for swarm algorithms.

Algorithm-agnostic. Accepts primitive float parameters (not algorithm-specific config objects).
Used by E3HybridRouting. Compatible with the PheromoneMatrix pattern from aco.py.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from e3hybrid.network.types import EdgeId

_EPS = 1e-10


class HybridPheromoneMatrix:
    """Sparse pheromone matrix: one float per graph edge.

    All values clamped to [tau_min, tau_max] after every mutation.
    Initialization sets all edges to tau0.
    NaN and infinity replaced by nearest bound.

    Parameters
    ----------
    tau0:
        Initial pheromone value for every edge.
    tau_min:
        Minimum allowed pheromone value.
    tau_max:
        Maximum allowed pheromone value.
    edge_ids:
        Set of all edge IDs in the graph.
    """

    def __init__(
        self,
        tau0: float,
        tau_min: float,
        tau_max: float,
        edge_ids: set[EdgeId],
    ) -> None:
        self._tau0 = tau0
        self._tau_min = tau_min
        self._tau_max = tau_max
        self._data: dict[EdgeId, float] = {eid: tau0 for eid in edge_ids}

    def get(self, edge_id: EdgeId) -> float:
        """Get pheromone value for an edge (tau_min if not present)."""
        return self._data.get(edge_id, self._tau_min)

    def set(self, edge_id: EdgeId, value: float) -> None:
        """Set pheromone value for an edge, clamped to [tau_min, tau_max]."""
        if not math.isfinite(value):
            value = self._tau_max if value > 0 else self._tau_min
        clamped = max(self._tau_min, min(value, self._tau_max))
        self._data[edge_id] = clamped

    def local_update(self, edge_id: EdgeId, rho_local: float) -> None:
        """Evaporate toward tau0 (local update during route construction).

        Formula (Eq. 13): (1 - rho_local) * current + rho_local * tau0
        """
        current = self.get(edge_id)
        self.set(edge_id, (1.0 - rho_local) * current + rho_local * self._tau0)

    @property
    def values(self) -> dict[EdgeId, float]:
        """Return a copy of all pheromone data."""
        return dict(self._data)

    @property
    def edge_count(self) -> int:
        return len(self._data)

    def clone(self) -> HybridPheromoneMatrix:
        clone = object.__new__(HybridPheromoneMatrix)
        clone._tau_min = self._tau_min
        clone._tau_max = self._tau_max
        clone._data = dict(self._data)
        return clone