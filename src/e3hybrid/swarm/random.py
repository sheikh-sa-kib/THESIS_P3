"""SwarmRandom — deterministic random number generation for swarm algorithms.

All swarm algorithms must use SwarmRandom for all stochastic decisions.
No direct random.random(), numpy.random, secrets, or time-based seeds.
"""

from __future__ import annotations

import hashlib
import random


class SwarmRandom:
    """Deterministic random number generation for swarm algorithms.

    Derives named sub-streams from the base random_stream.
    This ensures each stochastic component has its own deterministic
    sequence, and results are reproducible across runs with the same seed.

    Parameters
    ----------
    base_seed:
        Base seed for deterministic random generation.
    """

    def __init__(self, base_seed: int) -> None:
        if base_seed < 0:
            raise ValueError("base_seed must be non-negative")
        self._base_seed = base_seed
        self._streams: dict[str, random.Random] = {}

    def get_stream(self, name: str) -> random.Random:
        """Get or create a named sub-stream.

        Each stream is derived deterministically from the base seed.
        Adding or removing a stream does not affect other streams.

        Parameters
        ----------
        name:
            Stream name following the convention: <algorithm>.<component>.<purpose>
            Examples: "aco.ant_selection", "bco.scout_direction", "pso.velocity_noise"

        Returns
        -------
        random.Random
            A seeded Random instance unique to this stream name.
        """
        if name not in self._streams:
            digest = hashlib.sha256(name.encode()).digest()[:8]
            name_hash = int.from_bytes(digest, "big")
            stream_seed = (self._base_seed ^ name_hash) & 0x7FFFFFFF
            self._streams[name] = random.Random(stream_seed)
        return self._streams[name]

    def reset(self) -> None:
        """Clear all cached streams.

        Calling get_stream() after reset will recreate streams from the
        original base seed, producing the same sequences as the first use.
        """
        self._streams.clear()

    @property
    def base_seed(self) -> int:
        """Return the base seed used for stream derivation."""
        return self._base_seed
