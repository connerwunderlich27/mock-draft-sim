# draft_engine.py
# ---------------------------
# This file will contain the core fantasy draft logic.
# We're building it in small pieces so it's understandable.

from dataclasses import dataclass

@dataclass
class Player:
    """Represents a single player in the draft pool."""
    name: str
    position: str
    team: str
    adp: float
