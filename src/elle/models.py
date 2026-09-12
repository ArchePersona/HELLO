"""ELLE domain models (clean, immutable-friendly dataclasses)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class ParcelStage(str, Enum):
    INGESTED = "ingested"
    ACTIVE = "active"
    SETTLED = "settled"


class GossipState(str, Enum):
    """GRAY gossip states: GRAY means unverified/propagating."""
    WHITE = "white"    # untested / unknown
    GRAY = "gray"      # propagating, unverified
    BLACK = "black"    # verified valid
    DEAD = "dead"      # verified invalid


@dataclass
class Event:
    """One ingested external-learning event."""

    source: str
    kind: str
    payload: dict[str, Any] = field(default_factory=dict)

    def key(self) -> str:
        return f"{self.source}:{self.kind}"


@dataclass
class WorkParcel:
    """A unit of external learning work moving through its lifecycle."""

    parcel_id: str
    stage: ParcelStage = ParcelStage.INGESTED
    gossip: GossipState = GossipState.WHITE
    pressure: float = 0.0
    ancestry: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def touch(self, note: str) -> None:
        self.notes.append(note)


@dataclass
class Rule:
    """A promoted rule produced from settled parcels."""

    rule_id: str
    statement: str
    maturity: float = 0.0
    ancestry: list[str] = field(default_factory=list)

    def describe(self) -> str:
        return f"{self.rule_id}: {self.statement} (maturity={self.maturity:.2f})"


def find_parcel(parcels: list[WorkParcel], parcel_id: str) -> Optional[WorkParcel]:
    for parcel in parcels:
        if parcel.parcel_id == parcel_id:
            return parcel
    return None
